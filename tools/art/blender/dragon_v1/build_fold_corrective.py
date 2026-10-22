"""Corrective shape key VeyrWingFold: in the r2 folded idle stance, push wing skin that lies inside
(or within CLR of) the body/leg surface out along the surface normal, smooth the push over the
welded wing surface, convert to rest space through each vertex's skinning matrix. Value 1 = folded."""
import bpy, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils import kdtree
CLR = globals().get('CLR', 0.006)
s = bpy.context.scene
D = bpy.data.objects['DRAGON_DEFORM']; M = bpy.data.objects['DRAGON_MESH']; me = M.data
KEY = globals().get('KEY', 'VeyrWingFold')
if me.shape_keys and KEY in me.shape_keys.key_blocks:
    M.shape_key_remove(me.shape_keys.key_blocks[KEY])
    bpy.context.view_layer.update()
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {'ARM': 'DRAGON_DEFORM', 'MESH': 'DRAGON_MESH'}; exec(src, g)
V = g['eval_verts'](); n = len(V)
wingw = g['wsum']([b.name for b in D.data.bones if b.name.startswith('VeyrWing')])
movable = wingw > 0.2
# lateral envelope of the non-wing surface (spikes included) around each wing vertex
RAD = globals().get('RAD', 0.010)
body_idx = np.where(wingw < 0.3)[0]
kd2 = kdtree.KDTree(len(body_idx))
for k, i in enumerate(body_idx): kd2.insert(Vector((V[i, 0], 0.0, V[i, 2])), int(i))
kd2.balance()
delta = np.zeros((n, 3)); pushed = 0; inside_n = 0
for i in np.where(movable)[0]:
    sg = 1.0 if V[i, 1] >= 0 else -1.0
    near = [j for (_, j, _) in kd2.find_range(Vector((V[i, 0], 0.0, V[i, 2])), RAD) if V[j, 1]*sg > 0]
    if not near: continue
    env = max(V[j, 1]*sg for j in near)
    need = env + CLR - V[i, 1]*sg
    if need > 0:
        if V[i, 1]*sg < env - 0.002: inside_n += 1
        delta[i] = np.array((0, sg, 0)) * need * min(1.0, wingw[i] / 0.6); pushed += 1
# welded adjacency (UV seams split the mesh into islands)
co = g['rest']
kd = kdtree.KDTree(n)
for i in range(n): kd.insert(co[i], i)
kd.balance()
weld = {}
for i in range(n):
    if i in weld: continue
    hits = [j for (_, j, _) in kd.find_range(co[i], 1e-5)]
    for j in hits: weld[j] = hits[0]
rep_of = np.array([weld[i] for i in range(n)])
adj = {}
for e in me.edges:
    a, b = rep_of[e.vertices[0]], rep_of[e.vertices[1]]
    if a != b: adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
reps = np.unique(rep_of)
R = np.zeros((n, 3)); np.add.at(R, rep_of, delta); cnt = np.bincount(rep_of, minlength=n).astype(float)
R[reps] /= cnt[reps, None]
fixed = np.linalg.norm(R, axis=1) > 0
mov_rep = np.zeros(n, bool); mov_rep[rep_of[movable]] = True
for it in range(25):
    newR = R.copy()
    for a in reps:
        if not mov_rep[a] or a not in adj: continue
        nb = [b for b in adj[a] if mov_rep[b]]
        if not nb: continue
        avg = R[nb].mean(0)
        if fixed[a]:
            if np.linalg.norm(avg) > np.linalg.norm(R[a]): newR[a] = avg
        else: newR[a] = 0.5*R[a] + 0.5*avg
    R = newR
delta = R[rep_of] * movable[:, None]
# posed -> rest through skinning matrices
gi = {gg.index: gg.name for gg in M.vertex_groups}
mats = {b.name: (np.array(D.matrix_world @ D.pose.bones[b.name].matrix @ b.matrix_local.inverted()))[:3, :3] for b in D.data.bones}
rest_delta = np.zeros_like(delta)
for i in np.where(np.linalg.norm(delta, axis=1) > 1e-7)[0]:
    S = np.zeros((3, 3))
    for gg in me.vertices[i].groups: S += gg.weight * mats[gi[gg.group]]
    rest_delta[i] = np.linalg.solve(S, delta[i])
# keep a side's correction only if it reduces that side's intersections
def side_overlaps(Vx):
    o = g['overlaps'](Vx); return o['wingR/body'] + o['wingR/legs'], o['wingL/body'] + o['wingL/legs']
base_o = side_overlaps(V)
def posed_with(dl):
    return V + dl
kept = {}
for si, sgn in ((0, -1), (1, 1)):
    side_mask = (np.sign(co[:, 1]) == sgn)[:, None]
    trial = side_overlaps(posed_with(delta * side_mask))
    kept['R' if si == 0 else 'L'] = bool(trial[si] < base_o[si])
    if not kept['R' if si == 0 else 'L']: delta = delta * (~side_mask); rest_delta = rest_delta * (~side_mask)
if me.shape_keys is None: M.shape_key_add(name='Basis', from_mix=False)
kb = M.shape_key_add(name=KEY, from_mix=False)
for i in np.where(np.linalg.norm(rest_delta, axis=1) > 1e-7)[0]:
    kb.data[i].co = Vector(co[i] + rest_delta[i])
kb.value = 1.0
bpy.context.view_layer.update()
V2 = g['eval_verts'](); o2 = g['overlaps'](V2)
print('RES', json.dumps({'kept_sides': kept, 'pushed_direct': int(pushed), 'inside': int(inside_n), 'moved_after_smooth': int((np.linalg.norm(delta, axis=1) > 1e-6).sum()),
      'max_push_cm': float(np.linalg.norm(delta, axis=1).max()*2155.818), 'overlaps_before': g['overlaps'](V), 'overlaps_after': o2}))
