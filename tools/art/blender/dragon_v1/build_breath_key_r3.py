"""VeyrBreath (r3): ribcage/belly expansion along rest normals (belly 0.021 u, ribs 0.010 u, back 0.003 u), and the
folded membrane resting on the flank follows the flank outward (displacement mapped through the fold-pose skinning)."""
import bpy, json
import numpy as np
from mathutils import Vector, kdtree
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {}; exec(src, g)
M = bpy.data.objects['DRAGON_MESH']; me = M.data; D = bpy.data.objects['DRAGON_DEFORM']; key = me.shape_keys
if 'VeyrBreath' in key.key_blocks: M.shape_key_remove(key.key_blocks['VeyrBreath'])
key.key_blocks['VeyrWingFold'].value = 1.0; bpy.context.view_layer.update()
Vf = g['eval_verts']()                       # fold pose with corrective
n = len(Vf); co = g['rest']; nor = np.array([v.normal for v in me.vertices]); ws = g['wsum']
torso = ws(['tripo::Spine_0', 'bone_2', 'tripo::Spine_1']) + 0.5*ws(['bone_6', 'bone_11', 'tripo::Spine_2', 'tripo::Spine_3'])
wing = ws([b.name for b in D.data.bones if b.name.startswith('VeyrWing')])
def sstep(a, b, x): t = np.clip((x-a)/(b-a), 0, 1); return t*t*(3-2*t)
mask = np.clip(torso, 0, 1) * (1-np.clip(wing*2, 0, 1)) * sstep(-0.04, 0.04, co[:, 0]) * (1 - sstep(0.27, 0.34, co[:, 0])) * (1 - sstep(0.30, 0.36, co[:, 2]))
amp = 0.041*np.clip(-nor[:, 2], 0, 1) + 0.014*np.abs(nor[:, 1]) + 0.003*np.clip(nor[:, 2], 0, 1)
disp = nor * (amp*mask)[:, None]
# membrane follows the nearest flank point (posed displacement ~ rest displacement for the torso)
body = np.where((wing < 0.15) & (np.linalg.norm(disp, axis=1) > 0))[0]
kd = kdtree.KDTree(len(body))
for k_, i in enumerate(body): kd.insert(Vector(Vf[i]), int(i))
kd.balance()
gi = {gg.index: gg.name for gg in M.vertex_groups}
mats = {bb.name: (np.array(D.matrix_world @ D.pose.bones[bb.name].matrix @ bb.matrix_local.inverted()))[:3, :3] for bb in D.data.bones}
wv = np.where(wing > 0.15)[0]; followed = 0
for i in wv:
    hits = kd.find_n(Vector(Vf[i]), 6)
    near = [(j, d) for (_, j, d) in hits if d < 0.03]
    if not near: continue
    wsum_ = sum(1/(d+1e-3) for _, d in near); dpos = sum(disp[j]/(d+1e-3) for j, d in near) / wsum_
    dpos = dpos * 1.15                     # a touch more so the flank never catches the membrane
    S = np.zeros((3, 3))
    for gg in me.vertices[i].groups: S += gg.weight * mats[gi[gg.group]]
    disp[i] = np.linalg.solve(S, dpos); followed += 1
key_ = np.round(co/1e-5).astype(np.int64); _, inv = np.unique(key_, axis=0, return_inverse=True); inv = inv.ravel()
acc = np.zeros((inv.max()+1, 3)); np.add.at(acc, inv, disp); cnt = np.bincount(inv).astype(float); disp = acc[inv] / cnt[inv, None]
kb = M.shape_key_add(name='VeyrBreath', from_mix=False)
for i in np.where(np.linalg.norm(disp, axis=1) > 1e-8)[0]: kb.data[i].co = Vector(co[i] + disp[i])
kb.slider_max = 1.0; kb.value = 0.0
print('RES', json.dumps({'torso_moved': int(((np.linalg.norm(disp, axis=1) > 1e-6) & (wing < 0.15)).sum()), 'membrane_followed': followed}))
