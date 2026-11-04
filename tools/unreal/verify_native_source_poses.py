#!/usr/bin/env python3
"""Compare saved native local poses with the hash-locked source animations.

glTF right/up/back coordinates become Unreal right/back/up via Interchange;
translation metres become centimetres. This measures import/compression fidelity
at the native probe's sample times. It is not a rendered quality verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from normalize_customuse_glb import GLB, trs

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--plan', required=True, type=Path)
p.add_argument('--proof', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
plan = json.loads(a.plan.read_text())
proof = json.loads(a.proof.read_text())
assert proof['passed'] and proof['definition'].startswith(f"/Game/Characters/Customuse/{plan['character']}/{plan['version']}/")
C = np.array([[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]], dtype=float)
rows = []
for clip in plan['clips']:
    source = Path(clip['file'])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == clip['sha256']
    g = GLB(source)
    ids = {n.get('name'): i for i,n in enumerate(g.json['nodes'])}
    worst = {'translationCm': 0., 'rotationDegrees': 0., 'scale': 0.}
    locations = {}
    samples = [s for s in proof['samples'] if s['clip'] == clip['name']]
    assert len(samples) == 6
    count = 0
    for sample in samples:
        worlds = g.world_matrices(0, sample['time'])
        for bone, value in sample['pose'].items():
            assert bone in ids, 'Native skeleton contains an unexpected source bone'
            i = ids[bone]
            local = np.linalg.inv(worlds[g.parents[i]]) @ worlds[i] if i in g.parents else worlds[i]
            expected = C @ local @ C
            expected[:3,3] *= 100
            actual = trs({'translation': value['translation'], 'rotation': value['rotation'], 'scale': value['scale']})
            es, ns = np.linalg.norm(expected[:3,:3], axis=0), np.linalg.norm(actual[:3,:3], axis=0)
            angle = np.degrees(np.arccos(np.clip((np.trace((expected[:3,:3]/es).T @ (actual[:3,:3]/ns))-1)*.5, -1, 1)))
            errors = {'translationCm': float(np.linalg.norm(expected[:3,3]-actual[:3,3])),
                      'rotationDegrees': float(angle), 'scale': float(np.max(np.abs(es-ns)))}
            for key, error in errors.items():
                if error > worst[key]:
                    worst[key] = error
                    locations[key] = {'bone': bone, 'timeSeconds': sample['time']}
            count += 1
    rows.append({'clip': clip['name'], 'samples': len(samples), 'boneComparisons': count,
                 'maximumErrors': worst, 'worstLocations': locations})
limits = {'translationCm': .1, 'rotationDegrees': .1, 'scale': .001}
passed = all(row['maximumErrors'][k] <= limit for row in rows for k,limit in limits.items())
report = {'passed': passed, 'scope': 'Native import/compression fidelity at six sampled times per new clip; not visual/gameplay acceptance',
          'planSHA256': hashlib.sha256(a.plan.read_bytes()).hexdigest(), 'nativeProofSHA256': hashlib.sha256(a.proof.read_bytes()).hexdigest(),
          'limits': limits, 'clips': rows}
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(json.dumps(report, indent=2)+'\n')
print('Source/native sampled pose fidelity', 'PASS' if passed else 'FAIL', 'bone comparisons', sum(r['boneComparisons'] for r in rows))
raise SystemExit(0 if passed else 1)
