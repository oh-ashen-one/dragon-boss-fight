"""F1/F3/F4 (2026-11-18): per-frame playback measurements of a cut video2rig dragon action.

Read-only on the .blend (run it on a copy; nothing is saved). For every output frame of the active (cut)
action it records, in Blender metres:
  - the root bone (tripo::Spine_0) world head position and planar yaw (same yaw rule as cut_v2r_move.py),
  - the lowest joint (bone head) of each of the four feet (wrist/hock and toe bones),
  - the largest bone rotation step from the previous frame (degrees), wings excluded (hold detection).

blender COPY.blend --background --factory-startup --python measure_playback_tracks.py -- --out OUT.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--root', default='tripo::Spine_0')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])

FEET = {  # creature.json limbs: wrist/hock bone plus toe bones; index order = game leg order (FL, FR, HL, HR)
    0: ['bone_9', 'tripo::1_Left_Limb_1'],
    1: ['bone_14', 'tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3'],
    2: ['tripo::1_Right_Limb_3', 'tripo::1_Right_Limb_4'],
    3: ['tripo::0_Right_Limb_3', 'tripo::0_Right_Limb_4'],
}
scene = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)
act = arm.animation_data.action
f0, f1 = (int(round(v)) for v in act.frame_range)
fps = scene.render.fps / scene.render.fps_base
mw = arm.matrix_world
skip = [n for n in arm.pose.bones.keys() if 'Wing' in n]
frames, prev = [], None
for f in range(f0, f1 + 1):
    scene.frame_set(f)
    root = arm.pose.bones[a.root]
    m = mw @ root.matrix
    fwd = m.to_3x3() @ Vector((0, 1, 0))
    feet = []
    for leg in range(4):
        pts = []
        for name in FEET[leg]:
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            pts.append(mw @ pb.head)
        low = min(pts, key=lambda p: p.z)
        feet.append([round(low.x, 6), round(low.y, 6), round(low.z, 6)])
    q = {n: (mw.to_quaternion() @ pb.matrix.to_quaternion()) for n, pb in arm.pose.bones.items() if n not in skip}
    step = 0.0
    if prev:
        step = max(math.degrees(2 * math.acos(min(1.0, abs(prev[n].dot(q[n]))))) for n in q)
    prev = q
    head = mw @ root.head
    frames.append({'root': [round(head.x, 6), round(head.y, 6), round(head.z, 6)], 'yaw': round(math.atan2(fwd.y, fwd.x), 6),
                   'feet': feet, 'step_deg': round(step, 4)})
a.out.write_text(json.dumps({'blend': bpy.data.filepath, 'action': act.name, 'fps': fps, 'frames': frames}))
print('MEASURE_OK', act.name, len(frames), a.out)
