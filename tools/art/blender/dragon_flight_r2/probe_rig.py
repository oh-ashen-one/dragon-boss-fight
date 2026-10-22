import bpy, json
C = bpy.data.objects['DRAGON_CTRL']; D = bpy.data.objects['DRAGON_DEFORM']; M = bpy.data.objects['DRAGON_MESH']
wing = {b.name: (b.parent.name if b.parent else None, round(b.length, 4), [round(x, 3) for x in b.head_local], [round(x, 3) for x in b.tail_local]) for b in C.data.bones if 'WingPosZ' in b.name}
ik = {b.name: (b.parent.name if b.parent else None, [round(x, 4) for x in b.head_local]) for b in C.data.bones if b.name.startswith('IK_')}
cons = {pb.name: [(c.type, getattr(c, 'subtarget', ''), getattr(c, 'chain_count', None), getattr(c, 'pole_subtarget', '')) for c in pb.constraints] for pb in D.pose.bones if any(c.type == 'IK' for c in pb.constraints)}
neck = {b.name: (b.parent.name if b.parent else None, round(b.length, 4)) for b in C.data.bones if b.name in ('C_bone_2', 'C_bone_3', 'C_bone_4', 'C_bone_5', 'C_tripo::Spine_0', 'C_tripo::Spine_1', 'C_tripo::Root', 'C_bone_18', 'C_tripo::Tail_0', 'C_tripo::Tail_1', 'C_tripo::Tail_2')}
import numpy as np
co = np.array([v.co for v in M.data.vertices]); mw = np.array(M.matrix_world)
w = (mw @ np.c_[co, np.ones(len(co))].T).T[:, :3]
print('RES', json.dumps({'wing': wing, 'ik': ik, 'ikcons': cons, 'neck': neck, 'mesh_bbox': [list(np.round(w.min(0), 4)), list(np.round(w.max(0), 4))], 'shape_keys': [k.name for k in M.data.shape_keys.key_blocks], 'deform_wing': [b.name for b in D.data.bones if 'Wing' in b.name]}))
