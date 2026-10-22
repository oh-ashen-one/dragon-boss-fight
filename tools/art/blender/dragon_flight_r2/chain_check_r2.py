#!/usr/bin/env python3
"""(flight_r2 copy) Pose continuity between clip boundaries (exported GLBs): max joint world position delta (cm) and rotation (deg)."""
import sys, json, importlib.util
from pathlib import Path
import numpy as np
ROOT = Path('/Users/midir/veyr-review-fable-20261021'); W = ROOT/'Local/Blender/dragon-v1-20261021/export'
spec = importlib.util.spec_from_file_location('ev', ROOT/'tools/unreal/normalize_customuse_glb.py'); EV = importlib.util.module_from_spec(spec); spec.loader.exec_module(EV)
def load(n):
    g = EV.GLB(W/(n+'.glb'))
    for a in g.json['animations']: a['channels'] = [c for c in a['channels'] if c['target']['path'] != 'weights']
    T = float(g.accessor(g.json['animations'][0]['samplers'][0]['input']).max())
    names = {g.json['nodes'][i]['name']: i for i in g.json['skins'][0]['joints']}
    return g, T, names
def pose(g, names, t): W_ = g.world_matrices(0, t); return {n: W_[i] for n, i in names.items()}
out = {}
for a, ta, b, tb in [('Dragon_Idle_Blender_v1r3', 0, 'Dragon_Takeoff_Blender_v1r2', 0), ('Dragon_Takeoff_Blender_v1r2', 'end', 'Dragon_FlyHover_Blender_v1r2', 0),
                     ('Dragon_FlyHover_Blender_v1r2', 'end', 'Dragon_FlyHover_Blender_v1r2', 0), ('Dragon_FlyHover_Blender_v1r2', 0, 'Dragon_Land_Blender_v1r2', 0), ('Dragon_Land_Blender_v1r2', 'end', 'Dragon_Idle_Blender_v1r3', 0)]:
    ga, Ta, na = load(a); gb, Tb, nb = load(b)
    pa = pose(ga, na, Ta if ta == 'end' else ta); pb = pose(gb, nb, Tb if tb == 'end' else tb)
    dp = max(np.linalg.norm(pa[n][:3, 3] - pb[n][:3, 3]) for n in pa) * 2155.818
    Ra = {n: pa[n][:3, :3]/np.linalg.norm(pa[n][:3, :3], axis=0) for n in pa}; Rb = {n: pb[n][:3, :3]/np.linalg.norm(pb[n][:3, :3], axis=0) for n in pb}
    dr = max(np.degrees(np.arccos(np.clip((np.trace(Ra[n].T @ Rb[n]) - 1)/2, -1, 1))) for n in pa)
    worst = max(pa, key=lambda n: np.linalg.norm(pa[n][:3, 3] - pb[n][:3, 3]))
    out[f'{a}@{ta} -> {b}@{tb}'] = {'max_joint_pos_cm': round(float(dp), 1), 'max_joint_rot_deg': round(float(dr), 1), 'worst_joint': worst}
print(json.dumps(out, indent=1))
