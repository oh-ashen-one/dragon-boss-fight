#!/usr/bin/env python3
"""Max per-frame local joint rotation step (deg) in an exported dragon GLB (30 fps sampling), worst joints."""
import sys, json, importlib.util
from pathlib import Path
import numpy as np
ROOT = Path('/Users/midir/veyr-review-fable-20261021'); W = ROOT / 'Local/Blender/dragon-v1-20261021/export'
spec = importlib.util.spec_from_file_location('ev', ROOT / 'tools/unreal/normalize_customuse_glb.py'); EV = importlib.util.module_from_spec(spec); spec.loader.exec_module(EV)
g = EV.GLB(W / (sys.argv[1] + '.glb'))
for a in g.json['animations']: a['channels'] = [c for c in a['channels'] if c['target']['path'] != 'weights']
T = float(g.accessor(g.json['animations'][0]['samplers'][0]['input']).max()); n = round(T * 30)
joints = g.json['skins'][0]['joints']; names = [g.json['nodes'][i]['name'] for i in joints]
par = {c: p for p, nd in enumerate(g.json['nodes']) for c in nd.get('children', [])}
prev = None; worst = {}
for k in range(n + 1):
    Wm = g.world_matrices(0, k / 30.)
    L = {}
    for j, nm in zip(joints, names):
        R = Wm[j][:3, :3] / np.linalg.norm(Wm[j][:3, :3], axis=0)
        if j in par: Rp = Wm[par[j]][:3, :3] / np.linalg.norm(Wm[par[j]][:3, :3], axis=0); R = Rp.T @ R
        L[nm] = R
    if prev is not None:
        for nm in names:
            d = float(np.degrees(np.arccos(np.clip((np.trace(prev[nm].T @ L[nm]) - 1) / 2, -1, 1))))
            if d > worst.get(nm, (0, 0))[0]: worst[nm] = (round(d, 1), k)
    prev = L
print(json.dumps(sorted(((v, nm) for nm, v in worst.items()), reverse=True)[:5]))
