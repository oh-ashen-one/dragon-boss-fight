"""Find the frame with the widest wing-tip span and dump that frame's wing-bone local rotations.

blender RAW.blend --background --factory-startup --python probe_wing_spread.py -- --out wing_target.json
"""
import argparse
import json
import sys

import bpy

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)
scene = bpy.context.scene
start, end = (int(round(x)) for x in arm.animation_data.action.frame_range)
best = (-1.0, start)
for f in range(start, end + 1):
    scene.frame_set(f)
    l = arm.matrix_world @ arm.pose.bones['VeyrWingPosZTip'].tail
    r = arm.matrix_world @ arm.pose.bones['VeyrWingNegZTip'].tail
    best = max(best, ((l - r).length, f))
scene.frame_set(best[1])
quats = {pb.name: list(pb.matrix_basis.to_quaternion()) for pb in arm.pose.bones if 'VeyrWing' in pb.name}
scene.frame_set(start)
l0 = arm.matrix_world @ arm.pose.bones['VeyrWingPosZTip'].tail
r0 = arm.matrix_world @ arm.pose.bones['VeyrWingNegZTip'].tail
json.dump({'blend': bpy.data.filepath, 'frame': best[1], 'span': best[0], 'span_frame0': (l0 - r0).length, 'quats': quats}, open(a.out, 'w'), indent=1)
print('SPREAD', bpy.data.filepath.rsplit('/', 1)[-1], 'frame', best[1], 'span', round(best[0], 4), 'frame0', round((l0 - r0).length, 4))
