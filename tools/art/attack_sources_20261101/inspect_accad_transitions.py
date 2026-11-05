#!/usr/bin/env python3
"""Measure existing exported mocap; never creates or modifies animation keys.

Native floor is zero. Report source timing/contact defects without shifting the
review floor or treating source diagnostics as gameplay or quality acceptance.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB

SOURCE = ROOT/'Local/AttackSources20261105/ACCADMale1/RetargetStartsReferenceV3/Exports'
OUT = ROOT/'docs/master-goal-20261103/accad-transition-diagnostics.json'


def inspect(path, scale):
    g = GLB(path)
    meta = json.loads(path.with_suffix('.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == meta['sha256']
    ids = {n.get('name'): i for i, n in enumerate(g.json['nodes'])}
    duration = max(float(g.accessor(s['input'])[-1, 0]) for s in g.json['animations'][0]['samplers'])
    times = np.linspace(0, duration, round(duration*60)+1)
    worlds = np.array([g.world_matrices(0, float(t)) for t in times])
    hips = worlds[:, ids['Hips'], :3, 3]
    speed = np.linalg.norm(np.diff(hips[:, [0, 2]], axis=0), axis=1)/np.diff(times)*scale
    mesh = g.json['nodes'][g.mesh_node()]
    joints = g.json['skins'][mesh['skin']]['joints']
    masks = {}
    for side in ['Left', 'Right']:
        joint_ids = [i for i, n in enumerate(joints) if n in [ids[side+'Foot'], ids[side+'ToeBase']]]
        masks[side] = np.concatenate([
            (np.isin(g.accessor(p['attributes']['JOINTS_0']), joint_ids)*
             g.accessor(p['attributes']['WEIGHTS_0'])).sum(axis=1) > .75
            for p in g.json['meshes'][mesh['mesh']]['primitives']])
        assert masks[side].sum() > 20
    soles = {side: [] for side in masks}
    for t in times:
        vertices = g.skinned_positions(0, float(t))
        for side, mask in masks.items():
            soles[side].append(float(vertices[mask, 1].min()*scale))
    foot_report = {}
    for side in masks:
        ankle = worlds[:, ids[side+'Foot'], :3, 3]
        planar = np.linalg.norm(np.diff(ankle[:, [0, 2]], axis=0), axis=1)/np.diff(times)*scale
        sole = np.asarray(soles[side])
        near_floor = (sole[:-1] < 3) & (sole[1:] < 3)
        foot_report[side] = {
            'minimumSoleCm': float(sole.min()),
            'maximumSoleCm': float(sole.max()),
            'samplesBelowMinusOneCm': int((sole < -1).sum()),
            'nearFloorIntervals': int(near_floor.sum()),
            'maximumNearFloorAnkleSpeedCmS': float(planar[near_floor].max()) if near_floor.any() else None,
            'note': 'Ankle speed is a source diagnostic; toe-off/heel-roll require inspection. Not the native contact gate.'}
    # These keep the actual anticipation/braking and discard only excess
    # standing or redundant steady travel. No retiming or pose changes here.
    kind = path.stem.split('_')[1]
    ranges = {'StandToRun': (24, 90), 'RunToStand': (20, 98), 'StandToWalk': (73, 145)}
    first, last = ranges[kind]
    return {
        'clip': path.stem, 'source': str(path.relative_to(ROOT)), 'sha256': meta['sha256'],
        'durationSeconds': duration, 'sampleRate': 60, 'floorCm': 0,
        'maximumRootSpeedCmS': float(speed.max()), 'feet': foot_report,
        'proposedSourceFrameRange': [first, last], 'sourceFPS': meta['fps'],
        'proposedDurationSeconds': (last-first)/meta['fps'],
        'speedSamples': [{'seconds': float(times[i]), 'cmS': float(speed[i])}
                         for i in range(0, len(speed), 10)],
        'sourceModified': False, 'nativeImported': False, 'accepted': False}


def main():
    scale = json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
    report = {'scope': 'Read-only inspection of the actual v3 Blender exports; no acceptance or new animation',
              'scaleCmPerSourceUnit': scale,
              'clips': [inspect(p, scale) for p in sorted(SOURCE.glob('*.glb'))]}
    assert len(report['clips']) == 3
    OUT.write_text(json.dumps(report, indent=2)+'\n')
    for clip in report['clips']:
        print(clip['clip'], 'trim', clip['proposedSourceFrameRange'],
              'seconds', round(clip['proposedDurationSeconds'], 3),
              'sole min cm', {s: round(v['minimumSoleCm'], 2) for s, v in clip['feet'].items()})


if __name__ == '__main__':
    main()
