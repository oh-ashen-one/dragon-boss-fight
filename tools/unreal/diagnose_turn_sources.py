#!/usr/bin/env python3
"""Read-only contact measurements of Blender-authored turn candidates.

No animation channels or assets are written. Source diagnostics do not replace
grounded visual inspection, native fidelity or a gameplay contact test.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from normalize_customuse_glb import GLB

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'Local/AttackSources20261104/SourcedTurns/Exports'
native = json.loads((ROOT/'Local/NativeBlenderV04420261104/result.json').read_text())
scale_cm = float(native['import']['componentScale'])*100
rows = []
for path in sorted(source.glob('*.glb')):
    meta = json.loads(path.with_suffix('.json').read_text())
    g = GLB(path)
    ids = {n.get('name'): i for i, n in enumerate(g.json['nodes'])}
    duration = meta['duration']
    times = np.linspace(0, duration, round(duration*120)+1)
    points = np.asarray([[g.world_matrices(0, float(t))[ids[n]][:3,3]
                          for n in ('LeftToeBase','LeftFoot','RightToeBase','RightFoot')]
                         for t in times])*scale_cm
    heights = points[:,:,1]
    low = np.quantile(heights,.1,axis=0)+2.5
    planted = heights<=low
    sides = []
    for side in range(2):
        toe, ankle = side*2, side*2+1
        mask = planted[:,toe]&planted[:,ankle]
        windows = []
        for end in range(1,len(times)):
            start = max(0,end-4)
            if times[end]-times[start] < 1/30-1e-5 or not mask[start:end+1].all():
                continue
            delta = np.diff(points[start:end+1,[toe,ankle],:][:,:,[0,2]],axis=0)
            travel = np.max(np.linalg.norm(delta,axis=2),axis=1).sum()
            windows.append((float(travel/(times[end]-times[start])),float(times[end])))
        peak = max(windows,default=(None,None))
        sides.append({'side': ['left','right'][side], 'measuredWindows': len(windows),
                      'peakLowFootMotionCmPerSecond': peak[0], 'peakTimeSeconds': peak[1]})
    rows.append({'name': path.stem, 'sourceSHA256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'durationSeconds': duration, 'observedTurnDegrees': meta['observedFinalTurnDegrees'],
                 'feet': sides, 'editableBlenderScene': meta['editableScene'],
                 'editableSceneSHA256': hashlib.sha256((ROOT/meta['editableScene']).read_bytes()).hexdigest()})
out = ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json'
out.write_text(json.dumps({'sourceOnly': True, 'nativeImported': False, 'accepted': False,
                          'scaleCmPerSourceUnit': scale_cm, 'scope': 'Low toe-and-ankle windows sampled at120Hz, 1/30s motion window; no gameplay turning/transition claim.',
                          'candidates': rows},indent=2)+'\n')
print('Read-only sourced-turn diagnostics saved')
