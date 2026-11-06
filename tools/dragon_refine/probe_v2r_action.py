"""Read-only probe of a video2rig action: per-bone motion ranges, jaw axis, mouth path.

blender SOURCE.blend --background --factory-startup --python probe_v2r_action.py -- --out report.json
"""
import argparse
import json
import math
import sys

import bpy
from mathutils import Quaternion

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])


def armature():
    return next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)


def quat_tracks(arm):
    act = arm.animation_data.action
    tracks = {}
    # Blender 5 layered actions: evaluate the pose instead of reading curves.
    scene = bpy.context.scene
    start, end = (int(round(x)) for x in act.frame_range)
    for f in range(start, end + 1):
        scene.frame_set(f)
        for pb in arm.pose.bones:
            tracks.setdefault(pb.name, []).append(pb.matrix_basis.to_quaternion())
    return tracks, start, end


def jaw_axis(arm):
    tracks, _, _ = quat_tracks(arm)
    q = tracks.get('VeyrJaw')
    if not q:
        return None
    rest = q[0]
    best, axis = 0.0, None
    for x in q:
        d = rest.rotation_difference(x)
        ang = d.angle
        if ang > best:
            best, axis = ang, list(d.axis)
    return {'max_deg': math.degrees(best), 'axis_local': axis}


report = {}
arm = armature()
scene = bpy.context.scene
act = arm.animation_data.action
tracks, start, end = quat_tracks(arm)
ranges = {}
for name, q in tracks.items():
    ranges[name] = round(max(math.degrees(q[0].rotation_difference(x).angle) for x in q), 2)
mouth = []
for f in range(start, end + 1):
    scene.frame_set(f)
    pb = arm.pose.bones['bone_5']
    tip = arm.matrix_world @ pb.tail
    base = arm.matrix_world @ arm.pose.bones['tripo::Spine_0'].head
    mouth.append([round(v, 5) for v in (tip.x, tip.y, tip.z)] + [round(base.x, 5), round(base.y, 5), round(base.z, 5)])
report.update(file=bpy.data.filepath, action=act.name, frames=[start, end], fps=scene.render.fps / scene.render.fps_base,
              bone_range_deg=dict(sorted(ranges.items(), key=lambda kv: -kv[1])), jaw=jaw_axis(arm), mouth_and_spine0=mouth)
with open(a.out, 'w') as fh:
    json.dump(report, fh, indent=1)
print('PROBE_OK', a.out)
