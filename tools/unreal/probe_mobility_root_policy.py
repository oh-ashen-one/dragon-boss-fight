"""Read saved native mobility policy without creating a renderer or saving assets.

Compare the active runtime definition to the original imported travel attacks.
This diagnoses asset/runtime provenance; it cannot establish gameplay quality.
"""
import hashlib
import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
assert Path(unreal.Paths.project_dir()).resolve() == ROOT/'Unreal/Veyr'
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower()
OUT = ROOT/'Local/Fortress20261103/native-mobility-root-policy.json'
assert not OUT.exists(), 'Preserve prior probe evidence'
PLAN = ROOT/'Local/CustomuseAssets/Polish20261025/knight-v039mixamo/import-plan-KnightB.json'
plan = json.loads(PLAN.read_text())
expected = {c['name']: c for c in plan['clips'] if c['name'] in ['LeapAttackSourced', 'RunningAttackSourced']}
paths = ['/Game/Characters/Customuse/KnightB/v039mixamo/DA_KnightB',
         '/Game/Characters/Customuse/KnightB/v045turns/DA_KnightB',
         '/Game/Characters/Customuse/RuntimePolish/DA_Knight']
report = {'readOnly': True, 'nullRHI': True, 'success': False, 'renderedQualityAccepted': False,
          'engine': unreal.SystemLibrary.get_engine_version(),
          'planSHA256': hashlib.sha256(PLAN.read_bytes()).hexdigest(), 'definitions': []}


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


try:
    for path in paths:
        definition = unreal.load_asset(path)
        assert definition, 'Missing native definition: '+path
        transform = definition.get_editor_property('mesh_relative_transform')
        origin = unreal.MathLibrary.transform_location(transform, unreal.Vector())
        row = {'path': path, 'meshScale': vec(transform.scale3d),
               'runtimeSource': unreal.EditorAssetLibrary.get_metadata_tag(definition, 'VeyrPolishSourceDefinition'),
               'clips': []}
        clips = definition.get_editor_property('clips')
        for name, spec in expected.items():
            c = clips[name]
            samples = list(c.root_translation_samples_cm)
            actual = [vec(v) for v in samples]
            wanted = spec['root_translation_samples_cm']
            same_count = len(actual) == len(wanted)
            error = max(abs(x-y) for a, b in zip(actual, wanted) for x, y in zip(a, b)) if same_count and actual else None
            transformed = [vec(unreal.MathLibrary.transform_location(transform, v)-origin) for v in samples]
            row['clips'].append({'name': name, 'sequence': c.sequence.get_path_name(),
                'rootMotionRemoved': bool(c.root_motion_removed), 'rootMotionVertical': bool(c.root_motion_vertical),
                'expectedRootMotionVertical': spec.get('root_motion_vertical', False),
                'sampleRate': float(c.root_sample_rate), 'sampleCount': len(samples),
                'expectedSampleCount': len(wanted), 'maximumSourceSampleErrorCm': error,
                'transformedRootHeightRangeCm': max(v[2] for v in transformed)-min(v[2] for v in transformed) if transformed else 0,
                'matchesPlan': same_count and error is not None and error < .0001 and
                    bool(c.root_motion_vertical) == spec.get('root_motion_vertical', False) and
                    bool(c.root_motion_removed) == spec['root_motion_removed']})
        report['definitions'].append(row)
    report['success'] = True
finally:
    OUT.write_text(json.dumps(report, indent=2)+'\n')
unreal.log('VEYR_MOBILITY_ROOT_POLICY_PROBE_COMPLETE')
