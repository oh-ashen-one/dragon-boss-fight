"""Shape key VeyrBreath: ribcage/belly expansion along rest normals (inhale = 1)."""
import bpy, json
import numpy as np
from mathutils import Vector
M = bpy.data.objects['DRAGON_MESH']; me = M.data; D = bpy.data.objects['DRAGON_DEFORM']
if me.shape_keys and 'VeyrBreath' in me.shape_keys.key_blocks: M.shape_key_remove(me.shape_keys.key_blocks['VeyrBreath'])
gi = {g.index: g.name for g in M.vertex_groups}; n = len(me.vertices)
Wt = {}
for v in me.vertices:
    for g in v.groups: Wt.setdefault(gi[g.group], np.zeros(n))[v.index] = g.weight
def ws(names): return sum((Wt.get(k, np.zeros(n)) for k in names), np.zeros(n))
co = np.array([v.co for v in me.vertices]); nor = np.array([v.normal for v in me.vertices])
torso = ws(['tripo::Spine_0', 'bone_2', 'tripo::Spine_1']) + 0.5*ws(['bone_6', 'bone_11', 'tripo::Spine_2', 'tripo::Spine_3'])
wing = ws([b.name for b in D.data.bones if b.name.startswith('VeyrWing')])
def sstep(a, b, x): t = np.clip((x-a)/(b-a), 0, 1); return t*t*(3-2*t)
mask = np.clip(torso, 0, 1) * (1-np.clip(wing*2, 0, 1)) * sstep(-0.04, 0.04, co[:, 0]) * (1 - sstep(0.27, 0.34, co[:, 0])) * (1 - sstep(0.30, 0.36, co[:, 2]))
amp = 0.0105*np.clip(-nor[:, 2], 0, 1) + 0.0058*np.abs(nor[:, 1]) + 0.0014*np.clip(nor[:, 2], 0, 1)
disp = nor * (amp*mask)[:, None]
# weld coincident (UV-seam duplicated) vertices so the skin cannot split
key = np.round(co/1e-5).astype(np.int64)
_, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
acc = np.zeros((inv.max()+1, 3)); np.add.at(acc, inv, disp); cnt = np.bincount(inv).astype(float)
disp = acc[inv] / cnt[inv, None]
if me.shape_keys is None: M.shape_key_add(name='Basis', from_mix=False)
kb = M.shape_key_add(name='VeyrBreath', from_mix=False)
for i in np.where(np.linalg.norm(disp, axis=1) > 1e-8)[0]: kb.data[i].co = Vector(co[i] + disp[i])
kb.value = 0.0
print('RES', json.dumps({'moved': int((np.linalg.norm(disp, axis=1) > 1e-6).sum()), 'max_cm': float(np.linalg.norm(disp, axis=1).max()*2155.818),
      'lat_extent_change_u': float(disp[:,1].max()-disp[:,1].min()), 'belly_drop_u': float(-disp[:,2].min())}))
