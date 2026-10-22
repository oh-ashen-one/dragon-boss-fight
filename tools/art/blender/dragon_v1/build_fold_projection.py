"""Corrective shape key VeyrWingFold (r3): in the r3 fold pose, project the wing skin into the flank envelope -
below the back line, above the legs (z >= ZMIN), behind the chest (x <= XMAX), within body half-width +15%, and
outside the body surface - with Laplacian smoothing over the welded wing surface; converted to rest space."""
import bpy, json
import numpy as np
from mathutils import Vector
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {}; exec(src, g)
ENV_FRAMES = globals().get('ENV_FRAMES')
SWEPT = None
if ENV_FRAMES:
    # sweep the non-wing surface through the clip in the chest frame (the folded membrane rides the chest)
    Mk = bpy.data.objects['DRAGON_MESH']; Dk = bpy.data.objects['DRAGON_DEFORM']; kk = Mk.data.shape_keys
    for kb_ in kk.key_blocks[1:]: kb_.value = 0.0
    if kk.animation_data: kk.animation_data.action = None
    ww_ = g['wsum']([b_.name for b_ in Dk.data.bones if b_.name.startswith('VeyrWing')])
    bi_ = np.where(ww_ < 0.15)[0]; SWEPT = []
    for f_ in ENV_FRAMES:
        bpy.context.scene.frame_set(f_); Vk = g['eval_verts']()
        Mc = np.array(Dk.matrix_world @ Dk.pose.bones['bone_2'].matrix); Mi = np.linalg.inv(Mc)
        SWEPT.append((Mi @ np.c_[Vk[bi_], np.ones(len(bi_))].T).T[:, :3])
    SWEPT = np.vstack(SWEPT)
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
M = bpy.data.objects['DRAGON_MESH']; me = M.data; D = bpy.data.objects['DRAGON_DEFORM']
KEY = globals().get('KEY', 'VeyrWingFold')
if KEY in me.shape_keys.key_blocks: M.shape_key_remove(me.shape_keys.key_blocks[KEY]); bpy.context.view_layer.update()
V = g['eval_verts'](); n = len(V)
wingw = g['wsum']([b.name for b in D.data.bones if b.name.startswith('VeyrWing')])
wm = wingw > 0.15
body = np.where(wingw < 0.15)[0]; bx = V[body]
if SWEPT is not None:
    Mc0 = np.array(D.matrix_world @ D.pose.bones['bone_2'].matrix)
    bx = np.vstack([bx, (Mc0 @ np.c_[SWEPT, np.ones(len(SWEPT))].T).T[:, :3]])
xb = np.clip(((bx[:,0]+0.6)/0.02).astype(int), 0, 79); top = np.full(80, -1.0); np.maximum.at(top, xb, bx[:,2])
for i in range(1, 79):
    if top[i] < 0: top[i] = max(top[i-1], top[i+1])
envs = {}
for sgn in (-1, 1):
    sb = bx[bx[:,1]*sgn > 0]
    cx = np.clip(((sb[:,0]+0.6)/0.012).astype(int), 0, 124); cz = np.clip((sb[:,2]/0.012).astype(int), 0, 59)
    e = np.zeros((125, 60)); np.maximum.at(e, (cx, cz), np.abs(sb[:,1]))
    # fill small gaps by 1-cell dilation
    e2 = e.copy()
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1): e2 = np.maximum(e2, np.roll(np.roll(e, dx, 0), dz, 1))
    envs[sgn] = e2
ZMIN, XMAX, HALF, GAP = globals().get('ZMIN', 0.115), globals().get('XMAX', 0.27), 0.193, 0.004
# welded adjacency on wing verts
key_ = np.round(g['rest']/1e-5).astype(np.int64); _, rep = np.unique(key_, axis=0, return_inverse=True); rep = rep.ravel()
nr = rep.max()+1
edges = np.array([e.vertices[:] for e in me.edges]); a, b = rep[edges[:,0]], rep[edges[:,1]]
wr = np.zeros(nr, bool); wr[rep[wm]] = True
sel = wr[a] & wr[b] & (a != b); a, b = a[sel], b[sel]
P0 = np.zeros((nr, 3)); np.add.at(P0, rep, V); cnt = np.bincount(rep, minlength=nr).astype(float); P0 /= np.maximum(cnt, 1)[:, None]
X = P0.copy()
def project(X):
    idx = np.where(wr)[0]; p = X[idx]
    sgn = np.where(p[:,1] >= 0, 1, -1)
    xi = np.clip(((p[:,0]+0.6)/0.02).astype(int), 0, 79)
    p[:,2] = np.minimum(p[:,2], top[xi] - 0.006)
    p[:,2] = np.maximum(p[:,2], ZMIN)
    p[:,0] = np.minimum(p[:,0], XMAX)
    cx = np.clip(((p[:,0]+0.6)/0.012).astype(int), 0, 124); cz = np.clip((p[:,2]/0.012).astype(int), 0, 59)
    env = np.where(sgn > 0, envs[1][cx, cz], envs[-1][cx, cz])
    CLING = globals().get('CLING', 0.012)
    ay = np.abs(p[:,1]); ay = np.maximum(ay, np.where(env > 0, env + GAP, 0))
    ay = np.where(env > 0, np.minimum(ay, env + GAP + CLING), ay); ay = np.minimum(ay, HALF)
    p[:,1] = sgn*ay
    X[idx] = p
    return X
deg = np.bincount(np.r_[a, b], minlength=nr).astype(float)
for it in range(int(globals().get('ITERS', 60))):
    X = project(X)
    Dd = X - P0
    nb = np.zeros((nr, 3)); np.add.at(nb, a, Dd[b]); np.add.at(nb, b, Dd[a])
    avg = nb / np.maximum(deg, 1)[:, None]
    Dd = np.where((deg > 0)[:, None] & wr[:, None], 0.5*Dd + 0.5*avg, Dd)
    X = P0 + Dd
X = project(X)
delta = (X - P0)[rep] * wm[:, None]
# posed -> rest through skinning matrices
gi = {gg.index: gg.name for gg in M.vertex_groups}
mats = {bb.name: (np.array(D.matrix_world @ D.pose.bones[bb.name].matrix @ bb.matrix_local.inverted()))[:3, :3] for bb in D.data.bones}
co = g['rest']; rest_delta = np.zeros_like(delta)
for i in np.where(np.linalg.norm(delta, axis=1) > 1e-7)[0]:
    S = np.zeros((3, 3))
    for gg in me.vertices[i].groups: S += gg.weight * mats[gi[gg.group]]
    rest_delta[i] = np.linalg.solve(S, delta[i])
kb = M.shape_key_add(name=KEY, from_mix=False)
for i in np.where(np.linalg.norm(rest_delta, axis=1) > 1e-7)[0]: kb.data[i].co = Vector(co[i] + rest_delta[i])
kb.value = 1.0
bpy.context.view_layer.update()
V2 = g['eval_verts']()
el = np.array([e.vertices[:] for e in me.edges]); em = wm[el[:,0]] & wm[el[:,1]]; el = el[em]
L0 = np.linalg.norm(co[el[:,0]] - co[el[:,1]], axis=1); ok = L0 > 1e-5
r1 = np.linalg.norm(V[el[:,0]] - V[el[:,1]], axis=1)[ok]/L0[ok]; r2 = np.linalg.norm(V2[el[:,0]] - V2[el[:,1]], axis=1)[ok]/L0[ok]
w2 = V2[wm]
print('RES', json.dumps({'moved': int((np.linalg.norm(delta, axis=1) > 1e-6).sum()), 'max_move_cm': float(np.linalg.norm(delta, axis=1).max()*2155.8),
   'overlaps_before': g['overlaps'](V), 'overlaps_after': g['overlaps'](V2), 'tear_before': float((r1 > 1.6).mean()), 'tear_after': float((r2 > 1.6).mean()),
   'crush_after': float((r2 < 0.3).mean()), 'wing_x_max': float(w2[:,0].max()), 'wing_y_abs_max': float(np.abs(w2[:,1]).max()), 'wing_z': [float(w2[:,2].min()), float(w2[:,2].max())]}))
