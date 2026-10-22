"""Dump the evaluated local channels of DRAGON_CTRL control bones at FRAME of the open scene to OUT (json)."""
import bpy, json
s = bpy.context.scene; s.frame_set(FRAME)
C = bpy.data.objects['DRAGON_CTRL']
d = {pb.name: {'loc': list(pb.location), 'q': list(pb.rotation_quaternion), 'sc': list(pb.scale)} for pb in C.pose.bones
     if pb.name.startswith('C_') and not pb.name.startswith('C_tripo::Root')}
open(OUT, 'w').write(json.dumps(d)); print('RES', len(d))
