import bpy, json
import numpy as np
from mathutils.bvhtree import BVHTree
s = bpy.context.scene; arm = bpy.data.objects['DRAGON_DEFORM']; me = bpy.data.objects['DRAGON_MESH']; m = me.data
gi = {g.index: g.name for g in me.vertex_groups}; nv = len(m.vertices); Wt = {}
for v in m.vertices:
    for g in v.groups: Wt.setdefault(gi[g.group], np.zeros(nv))[v.index] = g.weight
def ws(n): return sum((Wt.get(x, np.zeros(nv)) for x in n), np.zeros(nv)) > .5
bones = [b.name for b in arm.data.bones]
wing = {'R': ws([b for b in bones if b.startswith('VeyrWingPosZ')]), 'L': ws([b for b in bones if b.startswith('VeyrWingNegZ')])}
LEG = {'F': ['tripo::1_Left_Limb_1', 'bone_9', 'tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3', 'bone_14', 'bone_7', 'tripo::1_Left_Limb_0', 'tripo::0_Left_Limb_0', 'tripo::0_Left_Limb_1'],
       'H': ['tripo::1_Right_Limb_2', 'tripo::1_Right_Limb_3', 'tripo::1_Right_Limb_4', 'tripo::0_Right_Limb_2', 'tripo::0_Right_Limb_3', 'tripo::0_Right_Limb_4', 'tripo::1_Right_Limb_0', 'tripo::1_Right_Limb_1', 'tripo::0_Right_Limb_0', 'tripo::0_Right_Limb_1']}
legs = {k: ws(v) for k, v in LEG.items()}
polys = [list(p.vertices) for p in m.polygons]
def rp(mask): return [p for p in polys if all(mask[j] for j in p)]
out = {}
for f in FR:
    s.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); e = me.evaluated_get(dg); mm = e.to_mesh(); V = [me.matrix_world @ v.co for v in mm.vertices]; e.to_mesh_clear()
    T = {k: BVHTree.FromPolygons(V, rp(msk)) for k, msk in list(wing.items()) + list(legs.items())}
    out[f] = {w + l: len(T[w].overlap(T[l])) for w in 'RL' for l in 'FH'}
print('RES', json.dumps(out))
