exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/dcommon.py').read())
import numpy as np
s.frame_set(0)
TUCK2 = {'IK_FL': (Vector((-0.03, 0.004, 0.135)), R(Y, 70)), 'IK_FR': (Vector((-0.03, -0.004, 0.135)), R(Y, 70)), 'IK_HL': (Vector((-0.09, -0.006, 0.10)), R(Y, 75)), 'IK_HR': (Vector((-0.09, 0.006, 0.10)), R(Y, 75))}
hip = C.matrix_world @ P['C_tripo::Spine_1'].head; t0 = C.matrix_world @ P['C_tripo::Tail_0'].head; back = (t0 - hip).normalized()
D = bpy.data.objects['DRAGON_DEFORM']; me = bpy.data.objects['DRAGON_MESH']
dg = bpy.context.evaluated_depsgraph_get(); e = me.evaluated_get(dg); mm = e.to_mesh(); zs = [v.co.z for v in mm.vertices]; e.to_mesh_clear()
roots = {'IK_FL': 'C_tripo::1_Left_Limb_0', 'IK_FR': 'C_tripo::0_Left_Limb_1', 'IK_HL': 'C_tripo::1_Right_Limb_1', 'IK_HR': 'C_tripo::0_Right_Limb_1'}
chainroot = {k: C.matrix_world @ C.pose.bones[C.data.bones[v].parent.name if False else v].head for k, v in roots.items()}
out = {}
for ik in TUCK2:
    Wp = C.matrix_world @ P[ik].head
    if ik.startswith('IK_H'):
        r = C.matrix_world @ C.pose.bones[C.data.bones[roots[ik]].parent.name].head if C.data.bones[roots[ik]].parent else chainroot[ik]
        T = Vector((Wp.x, Wp.y, Wp.z)); T.xz = (hip + back * DIST_H).xz; T.z += LIFT_H
    else:
        T = Wp + Vector((0, 0, DZ_F))
    dl = P[ik].matrix.to_3x3().inverted() @ (T - Wp)
    newl = local_v(ik, TUCK2[ik][0]) + dl; neww = B[ik].matrix_local.to_3x3() @ newl
    out[ik] = [round(x, 4) for x in neww]
print('RES', json.dumps({'tuck': out, 'hip': [round(x, 4) for x in hip], 'back': [round(x, 3) for x in back]}))
