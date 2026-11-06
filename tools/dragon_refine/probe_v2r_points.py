"""Per-frame world positions of the dragon's effectors for a raw video2rig action (phase finding for cuts).

blender RAW.blend --background --factory-startup --python probe_v2r_points.py -- --out points.json
"""
import argparse
import json
import math
import sys

import bpy

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
POINTS = {'mouth': 'bone_5', 'foot_front_a': 'bone_9', 'foot_front_b': 'bone_14',
          'foot_hind_a': 'tripo::1_Right_Limb_4', 'foot_hind_b': 'tripo::0_Right_Limb_4', 'tail_tip': 'tripo::Tail_2'}
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)
act = arm.animation_data.action
scene = bpy.context.scene
start, end = (int(round(x)) for x in act.frame_range)
out = {'fps': scene.render.fps / scene.render.fps_base, 'frames': [start, end], 'points': {k: [] for k in POINTS}, 'spine0': [], 'spine0_yaw_deg': []}
for f in range(start, end + 1):
    scene.frame_set(f)
    for key, bone in POINTS.items():
        out['points'][key].append([round(c, 5) for c in (arm.matrix_world @ arm.pose.bones[bone].tail)])
    sp = arm.pose.bones['tripo::Spine_0']
    m = arm.matrix_world @ sp.matrix
    out['spine0'].append([round(c, 5) for c in m.translation])
    fwd = m.to_3x3() @ __import__('mathutils').Vector((0, 1, 0))
    out['spine0_yaw_deg'].append(round(math.degrees(math.atan2(fwd.y, fwd.x)), 2))
json.dump(out, open(a.out, 'w'))
print('POINTS_OK', a.out)
