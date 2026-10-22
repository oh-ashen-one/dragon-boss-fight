"""World (armature-space) matrices of the IK foot controls at FRAME of the open scene -> OUT json."""
import bpy, json
s = bpy.context.scene; s.frame_set(FRAME); C = bpy.data.objects['DRAGON_CTRL']
d = {n: [list(r) for r in (C.matrix_world @ C.pose.bones[n].matrix)] for n in ('IK_FL', 'IK_FR', 'IK_HL', 'IK_HR')}
open(OUT, 'w').write(json.dumps(d)); print('RES', len(d))
