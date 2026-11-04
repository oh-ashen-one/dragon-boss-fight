#!/usr/bin/env python3
"""Remove the added standing-idle join from an already fitted running strike.

Retains every sourced strike/recovery pose, grip, travel and timing after the
join. The engine must blend directly from the current running pose. This CPU
derivative is unreviewed and does not activate or import anything.
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

SOURCE = ROOT/'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports/Mixamo_SlideAttack_v2.glb'
OUTPUT = ROOT/'Local/AttackSources20261104/ContinuousRunningAttack/Mixamo_SlideAttack_v3direct.glb'


def main():
    assert not OUTPUT.exists(), 'Preserve existing candidate'
    source_bytes = SOURCE.read_bytes()
    original = GLB(source_bytes)
    fit = json.loads(SOURCE.with_suffix('.json').read_text())
    assert hashlib.sha256(source_bytes).hexdigest() == fit['sha256']
    start = float(fit['intro'])
    assert abs(start-.3) < 1e-6
    end = max(float(original.accessor(s['input'])[-1, 0]) for s in original.json['animations'][0]['samplers'])
    ids = {n.get('name'): i for i, n in enumerate(original.json['nodes'])}
    # Verify the diagnosed artificial pause instead of trimming by name alone.
    roots = np.array([original.world_matrices(0, float(t))[ids['Hips'], :3, 3] for t in np.linspace(0, start, 19)])
    assert np.ptp(roots[:, [0, 2]], axis=0).max() < 1e-5
    times = np.linspace(0, end-start, round((end-start)*120)+1)
    worlds = [original.world_matrices(0, float(t+start)) for t in times]
    animated = {c['target']['node'] for c in original.json['animations'][0]['channels']}
    result = GLB(source_bytes)
    clip = {'name': OUTPUT.stem, 'samplers': [], 'channels': []}
    timeline = add_accessor(result, times[:, None], 'SCALAR')
    for i in sorted(animated):
        matrices = np.array([np.linalg.inv(w[original.parents[i]]) @ w[i] if i in original.parents else w[i] for w in worlds])
        scales = np.linalg.norm(matrices[:, :3, :3], axis=1)
        rotations = Rotation.from_matrix(matrices[:, :3, :3]/scales[:, None, :]).as_quat()
        for k in range(1, len(rotations)):
            if rotations[k-1] @ rotations[k] < 0:
                rotations[k] *= -1
        for path, values, kind in [('translation', matrices[:, :3, 3], 'VEC3'), ('rotation', rotations, 'VEC4'), ('scale', scales, 'VEC3')]:
            output = add_accessor(result, values, kind)
            sampler = len(clip['samplers'])
            clip['samplers'].append({'input': timeline, 'output': output, 'interpolation': 'LINEAR'})
            clip['channels'].append({'sampler': sampler, 'target': {'node': i, 'path': path}})
    result.json['animations'] = [clip]
    result.json['buffers'][0]['byteLength'] = len(result.binary)
    data = result.bytes()
    check = GLB(data)
    maximum_error = 0.
    # Dense independent playback comparison includes interval midpoints.
    for t in np.linspace(0, end-start, 2*len(times)-1):
        maximum_error = max(maximum_error, float(np.max(np.abs(check.world_matrices(0, float(t))-original.world_matrices(0, float(t+start))))))
    assert maximum_error < 3e-5, 'Trim changed the retained motion'
    assert result.binary[:len(original.binary)] == original.binary
    for field in ['nodes', 'skins', 'meshes', 'materials', 'images', 'textures']:
        assert result.json.get(field) == original.json.get(field)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    report = {'source': str(SOURCE.relative_to(ROOT)), 'sourceSHA256': hashlib.sha256(source_bytes).hexdigest(),
              'sha256': hashlib.sha256(data).hexdigest(), 'removedStandingJoinSeconds': start,
              'duration': end-start, 'intro': 0., 'outro': fit['outro'], 'fps': 120,
              'maximumRetainedPoseMatrixError': maximum_error, 'retainedStrikeTravelGripAndRecovery': True,
              'nativeImported': False, 'visuallyReviewed': False, 'accepted': False}
    OUTPUT.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
