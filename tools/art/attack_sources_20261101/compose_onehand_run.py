#!/usr/bin/env python3
"""Compose existing licensed one-hand upper motion with the corrected run legs.

CPU-only derivative. Match the gait phase from both source foot-height curves,
preserve the one-hand local torso/arm/finger motion and hand-relative sword,
and retain the corrected lower body's actual cycle travel. Native playback and
blind quality review remain required. Source files are never overwritten.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB
from refine_locomotion_glb_contacts import add_accessor

UPPER = ROOT/'Local/CustomuseAssets/Sourced20261025b/knight/Fab_RunOneHand_v18.glb'
LOWER = ROOT/'Local/AttackSources20261104/CPUBootPlants/Mixamo_ForwardRun_v4cpu.glb'
OUTPUT = ROOT/'Local/AttackSources20261104/CPUBootPlants/FabMixamo_OneHandRun_v1composed.glb'


def main():
    assert not OUTPUT.exists(), 'Preserve existing candidates'
    a, b = GLB(UPPER), GLB(LOWER)
    ma, mb = [{n.get('name'): i for i, n in enumerate(g.json['nodes'])} for g in (a, b)]
    bind_a, bind_b = a.world_matrices(), b.world_matrices()
    legs = [side+suffix for side in ['Left', 'Right'] for suffix in ['UpLeg', 'Leg', 'Foot', 'ToeBase']]
    for name in ['Hips', 'Spine', *legs]:
        assert np.max(np.abs(bind_a[ma[name]]-bind_b[mb[name]])) < 1e-5, 'Source rigs differ'
    da, db = [max(float(g.accessor(s['input'])[-1, 0]) for s in g.json['animations'][0]['samplers']) for g in (a, b)]
    phases = np.arange(60)/60
    aw = np.array([a.world_matrices(0, float(t*da)) for t in phases])
    bw = np.array([b.world_matrices(0, float(t*db)) for t in phases])
    def heights(worlds, names):
        h = np.column_stack([worlds[:, names[side+'Foot'], 1, 3]-worlds[:, names['Hips'], 1, 3] for side in ['Left', 'Right']])
        return (h-h.mean(axis=0))/h.std(axis=0)
    ah, bh = heights(aw, ma), heights(bw, mb)
    phase = min(range(60), key=lambda k: float(np.mean((np.roll(ah, -k, axis=0)-bh)**2))) / 60
    children = {i: n.get('children', []) for i, n in enumerate(a.json['nodes'])}
    animated = {c['target']['node'] for c in a.json['animations'][0]['channels']}
    animated.update(ma[n] for n in ['Hips', 'WeaponSocket', *legs])
    samples = {i: [] for i in animated}
    times = np.linspace(0, db, round(db*60)+1)
    max_upper_error, max_grip_error, max_lower_error = 0., 0., 0.
    upper_ids = [i for n, i in ma.items() if n not in ['Hips', 'WeaponSocket', *legs] and i in animated]
    for time in times:
        source_time = ((time/db+phase) % 1)*da
        original = a.world_matrices(0, source_time)
        lower = b.world_matrices(0, time)
        w = original.copy()
        def set_world(i, matrix):
            delta = matrix @ np.linalg.inv(w[i])
            def update(j):
                w[j] = delta @ w[j]
                for child in children[j]:
                    update(child)
            update(i)
        set_world(ma['Hips'], lower[mb['Hips']])
        for name in legs:
            set_world(ma[name], lower[mb[name]])
            max_lower_error = max(max_lower_error, float(np.max(np.abs(w[ma[name]]-lower[mb[name]]))))
        grip = np.linalg.inv(original[ma['RightHand']]) @ original[ma['WeaponSocket']]
        set_world(ma['WeaponSocket'], w[ma['RightHand']] @ grip)
        actual_grip = np.linalg.inv(w[ma['RightHand']]) @ w[ma['WeaponSocket']]
        max_grip_error = max(max_grip_error, float(np.max(np.abs(actual_grip-grip))))
        for i in animated:
            local = np.linalg.inv(w[a.parents[i]]) @ w[i] if i in a.parents else w[i]
            samples[i].append(local)
            if i in upper_ids:
                source_local = np.linalg.inv(original[a.parents[i]]) @ original[i] if i in a.parents else original[i]
                max_upper_error = max(max_upper_error, float(np.max(np.abs(local-source_local))))
    assert max(max_upper_error, max_grip_error, max_lower_error) < 1e-6
    clip = {'name': OUTPUT.stem, 'channels': [], 'samplers': []}
    timeline = add_accessor(a, times[:, None], 'SCALAR')
    for i in sorted(animated):
        matrices = np.asarray(samples[i])
        scales = np.linalg.norm(matrices[:, :3, :3], axis=1)
        rotations = Rotation.from_matrix(matrices[:, :3, :3]/scales[:, None, :]).as_quat()
        for k in range(1, len(rotations)):
            if rotations[k-1] @ rotations[k] < 0:
                rotations[k] *= -1
        for path, values, kind in [('translation', matrices[:, :3, 3], 'VEC3'), ('rotation', rotations, 'VEC4'), ('scale', scales, 'VEC3')]:
            output = add_accessor(a, values, kind)
            index = len(clip['samplers'])
            clip['samplers'].append({'input': timeline, 'output': output, 'interpolation': 'LINEAR'})
            clip['channels'].append({'sampler': index, 'target': {'node': i, 'path': path}})
    a.json['animations'] = [clip]
    a.json['buffers'][0]['byteLength'] = len(a.binary)
    original = GLB(UPPER)
    assert a.binary[:len(original.binary)] == original.binary
    for field in ['nodes', 'skins', 'meshes', 'materials', 'images', 'textures']:
        assert a.json.get(field) == original.json.get(field)
    result = a.bytes()
    OUTPUT.write_bytes(result)
    report = {'sources': [{'file': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [UPPER, LOWER]],
              'sha256': hashlib.sha256(result).hexdigest(), 'durationSeconds': db, 'upperSourceDurationSeconds': da,
              'upperPhaseOffsetCycles': phase, 'phaseFitMethod': 'Least squares over normalized two-foot heights,60 phase candidates',
              'maxUpperLocalMatrixError': max_upper_error, 'maxHandRelativeSocketMatrixError': max_grip_error,
              'maxLowerWorldMatrixError': max_lower_error, 'originalGeometrySkinMaterialsPreserved': True,
              'nativeImported': False, 'visuallyReviewed': False, 'accepted': False}
    OUTPUT.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
