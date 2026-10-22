#!/usr/bin/env python3
"""Independent check of an exported dragon GLB against the v007 source rig using the repo's
numpy glTF evaluator (tools/unreal/normalize_customuse_glb.py). No Blender involved.
usage: verify_export.py SOURCE_RIG.glb EXPORT.glb REPORT.json"""
import sys, json, importlib.util
from pathlib import Path
import numpy as np
ROOT = Path('/Users/midir/veyr-review-fable-20261021')
spec = importlib.util.spec_from_file_location('ev', ROOT/'tools/unreal/normalize_customuse_glb.py'); EV = importlib.util.module_from_spec(spec); spec.loader.exec_module(EV)
CM = 2155.818
src, exp = EV.GLB(Path(sys.argv[1])), EV.GLB(Path(sys.argv[2]))
# the repo evaluator handles skeletal TRS only: keep morph info aside, drop weight channels for the skeletal checks
morph = {'targets': [len(p.get('targets', [])) for m in exp.json['meshes'] for p in m['primitives']],
         'names': [m.get('extras', {}).get('targetNames') for m in exp.json['meshes']],
         'weight_channels': sum(1 for a in exp.json.get('animations', []) for c in a['channels'] if c['target']['path'] == 'weights')}
for a in exp.json.get('animations', []):
    keep = [c for c in a['channels'] if c['target']['path'] != 'weights']
    a['channels'] = keep
def joints(g): return [g.json['nodes'][i]['name'] for i in g.json['skins'][0]['joints']]
js, je = joints(src), joints(exp)
rep = {'morph': morph, 'source_joints': len(js), 'export_joints': len(je), 'same_joint_names': sorted(js) == sorted(je), 'same_joint_order': js == je}
# rest TRS per joint (by name)
sn = {n['name']: n for n in src.json['nodes'] if 'name' in n}; en = {n['name']: n for n in exp.json['nodes'] if 'name' in n}
dt = dr = 0.
for name in js:
    a, b = sn[name], en[name]
    dt = max(dt, float(np.abs(np.array(a.get('translation', [0,0,0])) - np.array(b.get('translation', [0,0,0]))).max()))
    qa, qb = np.array(a.get('rotation', [0,0,0,1])), np.array(b.get('rotation', [0,0,0,1]))
    dr = max(dr, float(np.degrees(2*np.arccos(min(1., abs(qa @ qb))))))
rep['rest_translation_max_delta_units'] = dt; rep['rest_rotation_max_delta_deg'] = dr
sp = src.skinned_positions(); ep = exp.skinned_positions()
rep['bind_vertices'] = [len(sp), len(ep)]
if len(sp) == len(ep): rep['bind_mesh_max_delta_cm'] = float(np.abs(sp - ep).max()*CM)
rep['materials'] = [m.get('name') for m in exp.json.get('materials', [])]
anims = exp.json.get('animations', []); rep['animations'] = [a.get('name') for a in anims]
a = anims[0]; times = exp.accessor(a['samplers'][0]['input']); T = float(times.max())
rep['duration_s'] = T; rep['keys'] = len(times); rep['channels'] = len(a['channels'])
rep['animation_extras'] = a.get('extras')
paths = {}
for ch in a['channels']: paths[ch['target']['path']] = paths.get(ch['target']['path'], 0) + 1
rep['channel_paths'] = paths
fps = 30; ts = np.linspace(0, T, int(round(T*fps))+1)
jidx = exp.json['skins'][0]['joints']
Wm = np.array([exp.world_matrices(0, t)[jidx] for t in ts])
rep['finite'] = bool(np.isfinite(Wm).all())
rep['seam_joint_world_max_delta_cm'] = float(np.abs(Wm[0][:, :3, 3] - Wm[-1][:, :3, 3]).max()*CM)
R = Wm[:, :, :3, :3] / np.linalg.norm(Wm[:, :, :3, :3], axis=2, keepdims=True)
cosang = (np.einsum('fjab,fjab->fj', R[1:], R[:-1]) - 1) / 2
rep['max_joint_world_rot_step_deg_per_frame'] = float(np.degrees(np.arccos(np.clip(cosang, -1, 1))).max())
# root motion: skeleton root world translation range
roots = [i for i in jidx if exp.parents.get(i) not in set(jidx)]
rt = np.array([exp.world_matrices(0, t)[roots[0]][:3, 3] for t in ts]) * CM
rep['root_joint'] = exp.json['nodes'][roots[0]]['name']; rep['root_translation_range_cm'] = (rt.max(0) - rt.min(0)).tolist()
# feet on CPU-skinned export (glTF Y up): contact band = lowest 6.5 cm per foot region
P0 = exp.skinned_positions(0, 0.)
feet = {'FL': (0.2825, -0.1043), 'FR': (0.2825, 0.0997), 'HL': (0.0707, -0.1043), 'HR': (0.0864, 0.1154)}   # glTF (x, z) = Blender (x, -y)
res = {}
samples = ts[::3]
Ps = [exp.skinned_positions(0, t) for t in samples]
for k, (x, z) in feet.items():
    near = np.where((np.hypot(P0[:, 0]-x, P0[:, 2]-z) < 0.07) & (P0[:, 1] < 0.04))[0]
    if len(near) == 0: res[k] = 'airborne at t=0'; continue
    band = near[P0[near, 1] < P0[near, 1].min() + 0.003]
    A = np.array([p[band] for p in Ps]) * CM
    res[k] = {'contact_verts': int(len(band)), 'min_y_cm_range': [float(A[:, :, 1].min(1).min()), float(A[:, :, 1].min(1).max())],
              'max_drift_cm': float(np.linalg.norm(A - A[0][None], axis=2).max())}
rep['feet_cpu_skinned'] = res
rep['mesh_min_y_cm'] = float(min(p[:, 1].min() for p in Ps) * CM)
Path(sys.argv[3]).write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))
