#!/usr/bin/env python3
"""Prepare Blender-authored planted-run derivatives on the canonical mesh.

CPU preparation only; never modifies the active native definition. Original
run clips remain inherited so one Shipping build can film a matched comparison.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import inspect_glb, compatible

BASE = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v042heal/import-plan-KnightB.json'
OUT = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v044blender'


def main():
    assert not OUT.exists(), 'Preserve existing versioned preparation'
    base = json.loads(BASE.read_text())
    canonical = Path(base['rig']['file'])
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == base['rig']['sha256']
    body = GLB(canonical)
    vertices = np.concatenate([body.accessor(p['attributes']['POSITION']) for m in body.json['meshes'] for p in m['primitives']])
    native_scale = base['target_height_cm']/(float(np.ptp(vertices[:, 1]))*100)
    sources = [('RunOneHandPlanted', ROOT/'Local/AttackSources20261104/BlenderMotion/FabMixamo_OneHandRun_v2blender.glb'),
               ('RunTwoHandPlanted', ROOT/'Local/AttackSources20261103/ForwardRigidPlants/Mixamo_ForwardRun_v4rigid.glb')]
    plan = {k: v for k, v in base.items() if k != 'clips'}
    plan.update(version='v044blender', replace_runtime_source='/Game/Characters/Customuse/KnightB/v042heal/DA_KnightB',
                owner_approved=False, purpose='Blender-authored sourced run candidates; native contacts and blind review pending', clips=[])
    for key, source in sources:
        filename = source.name
        fit = json.loads(source.with_suffix('.json').read_text())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fit['sha256']
        assert fit.get('authoringApplication') == 'Blender', 'CPU diagnostics are not importable animation sources'
        scene = ROOT/fit['editableScene']
        assert scene.is_file() and hashlib.sha256(scene.read_bytes()).hexdigest() == fit['editableSceneSHA256']
        duration = SourceGLB(source).duration()
        normal = normalize_file(source, SourceGLB(canonical), OUT/'intermediate'/filename, 120, duration, False, True)
        target = OUT/'knight'/filename
        proof = graft(canonical, OUT/'intermediate'/filename, target)
        entry = {'file': str(target), 'sha256': proof['outputSHA256']}
        compatible(inspect_glb(base['rig']), inspect_glb(entry))
        nominal = float(np.linalg.norm(np.array(normal['rootTranslationSamplesCm'][-1])[:2])*native_scale/duration)
        assert 100 < nominal < 900
        plan['clips'].append(dict(name=key, **entry, mesh_variant=base['canonical_mesh_variant'], start_seconds=0., end_seconds=duration,
                                 loop=True, gameplay_play_rate=1., nominal_speed_cm_per_second=nominal, damage_windows=[], impact_seconds=-1.,
                                 weapon_file=base['clips'][0]['weapon_file'], root_motion_policy='preserve', root_motion_removed=True,
                                 root_motion_vertical=False, root_sample_rate=normal['rootSampleRate'],
                                 root_translation_samples_cm=normal['rootTranslationSamplesCm'], root_yaw_samples_degrees=[],
                                 source_duration=duration, approved_source_file=filename, approved_source_sha256=fit['sha256']))
        (OUT/('preparation-'+key+'.json')).write_text(json.dumps({'normalization': normal, 'graft': proof, 'nominalSpeedCmS': nominal, 'accepted': False}, indent=2)+'\n')
        print(key, 'prepared', round(duration, 3), 'seconds;', round(nominal, 2), 'cm/s')
    plan['required_clips'] = sorted(set(base['required_clips']) | {key for key, _ in sources})
    (OUT/'import-plan-KnightB.json').write_text(json.dumps(plan, indent=2)+'\n')


if __name__ == '__main__':
    main()
