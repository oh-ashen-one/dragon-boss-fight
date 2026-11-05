#!/usr/bin/env python3
"""Prepare the blind-reviewed Blender start for an isolated native trial.

Factor planar actor travel and graft animation onto canonical geometry. This
changes representation only; it does not import, activate or accept the motion.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB, UE
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import compatible, inspect_glb

BASE = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v045turns/import-plan-KnightB.json'
SOURCE = ROOT/'Local/AttackSources20261105/ACCADMale1/WeaponStartV6/ACCAD_StandToRunTwoHand_v6weapon.glb'
OUT = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v046start'


def main():
    assert not OUT.exists(), 'Preserve previous preparation'
    review = json.loads((ROOT/'docs/master-goal-20261103/blind-accad-weapon-receipt.json').read_text())
    assert review['nativeTrialAllowed'] and review['visiblyBetter'] and not review['finalQualityAccepted']
    meta = json.loads(SOURCE.with_suffix('.json').read_text())
    assert not meta.get('candidateStopped') and not (SOURCE.parent/'DO_NOT_IMPORT.md').exists()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == meta['sha256']
    assert hashlib.sha256(SOURCE.with_suffix('.blend').read_bytes()).hexdigest() == meta['editableSceneSHA256']
    base = json.loads(BASE.read_text()); canonical = Path(base['rig']['file'])
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == base['rig']['sha256']
    body = GLB(canonical)
    vertices = np.concatenate([body.accessor(p['attributes']['POSITION']) for m in body.json['meshes'] for p in m['primitives']])
    scale = base['target_height_cm']/float(np.ptp(vertices[:, 1]))
    duration = SourceGLB(SOURCE).duration()
    normal_path = OUT/'intermediate'/SOURCE.name
    normal = normalize_file(SOURCE, SourceGLB(canonical), normal_path, 120, duration)
    target = OUT/'knight'/SOURCE.name
    proof = graft(canonical, normal_path, target)
    entry = {'file': str(target), 'sha256': proof['outputSHA256']}
    compatible(inspect_glb(base['rig']), inspect_glb(entry))
    original, converted = SourceGLB(SOURCE), SourceGLB(target)
    translations = np.asarray(normal['rootTranslationSamplesCm'])
    times = np.linspace(0, duration, 2*(len(translations)-1)+1)
    worst = 0.
    for t in times:
        f = min(float(t)*normal['rootSampleRate'], len(translations)-1)
        i = int(f); j = min(i+1, len(translations)-1); alpha = f-i
        actor = np.eye(4); actor[:3, 3] = UE.T @ (translations[i]*(1-alpha)+translations[j]*alpha)/100
        old, _ = original.sample(float(t)); new, _ = converted.sample(float(t))
        worst = max(worst, max(float(np.max(np.abs(actor @ new[converted.names[n]]-old[original.names[n]]))) for n in original.skin_names()))
    assert worst < 3e-5, 'Actor/pose factoring changed captured world motion'
    g = GLB(target); ids = {n.get('name'): i for i, n in enumerate(g.json['nodes'])}
    mesh = g.json['nodes'][g.mesh_node()]; skin = g.json['skins'][mesh['skin']]
    groups = [i for i, n in enumerate(skin['joints']) if n in [ids[s+n] for s in ['Left', 'Right'] for n in ['Foot', 'ToeBase']]]
    mask = np.concatenate([(np.isin(g.accessor(p['attributes']['JOINTS_0']), groups)*g.accessor(p['attributes']['WEIGHTS_0'])).sum(axis=1) > .75 for p in g.json['meshes'][mesh['mesh']]['primitives']])
    minimum_sole = min(float(g.skinned_positions(0, float(t))[mask, 1].min()*scale) for t in np.linspace(0, duration, round(duration*60)+1))
    plan = {k: v for k, v in base.items() if k != 'clips'}
    key = 'RunStartTwoHandSourced'
    plan.update(version='v046start', replace_runtime_source='/Game/Characters/Customuse/KnightB/v045turns/DA_KnightB',
        owner_approved=False, purpose='Blind-preferred source start for isolated native trial; shoulder/weight/clearance and gameplay acceptance remain open',
        scale_aware_compression=True, rotation_precision_codec='least_destructive')
    plan['clips'] = [dict(name=key, **entry, mesh_variant=base['canonical_mesh_variant'], start_seconds=0., end_seconds=duration,
        loop=False, gameplay_play_rate=1., nominal_speed_cm_per_second=0., damage_windows=[], impact_seconds=-1.,
        weapon_file=base['clips'][0]['weapon_file'], root_motion_policy='preserve', root_motion_removed=True, root_motion_vertical=False,
        root_sample_rate=normal['rootSampleRate'], root_translation_samples_cm=normal['rootTranslationSamplesCm'], root_yaw_samples_degrees=[],
        source_duration=duration, approved_source_file=SOURCE.name, approved_source_sha256=meta['sha256'])]
    plan['required_clips'] = sorted(set(base['required_clips']) | {key})
    (OUT/'import-plan-KnightB.json').write_text(json.dumps(plan, indent=2)+'\n')
    report = {'sourceSHA256': meta['sha256'], 'normalization': normal, 'graft': proof,
        'worldReconstructionSamples': len(times), 'maximumWorldMatrixError': worst,
        'canonicalMinimumBootHeightCm': minimum_sole, 'nativeImported': False, 'accepted': False,
        'scope': 'Representation and canonical-mesh preparation only; native trial and all critic caveats remain'}
    (OUT/'preparation-RunStartTwoHandSourced.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Prepared isolated start trial:', round(duration, 3), 'seconds; world error', worst, 'canonical sole minimum cm', minimum_sole)


if __name__ == '__main__':
    main()
