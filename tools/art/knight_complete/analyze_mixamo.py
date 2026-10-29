"""Headless Blender: measure Mixamo source clips (travel, duration, lean) to classify direction.
blender --background --factory-startup --python analyze_mixamo.py -- OUT.json FBX..."""
import bpy, sys, json
from mathutils import Vector
args = sys.argv[sys.argv.index("--")+1:]
out, files = args[0], args[1:]
rows = []
for f in files:
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=f)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    act = arm.animation_data.action; s, e = (int(round(x)) for x in act.frame_range)
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    def P(fr, bone):
        bpy.context.scene.frame_set(fr); return (arm.matrix_world @ arm.pose.bones[bone].head).copy()
    hips = [P(fr, "mixamorig:Hips") for fr in range(s, e+1)]
    head = [P(fr, "mixamorig:Head") for fr in range(s, e+1)]
    lf = [P(fr, "mixamorig:LeftFoot") for fr in range(s, e+1)]
    rf = [P(fr, "mixamorig:RightFoot") for fr in range(s, e+1)]
    d = hips[-1]-hips[0]
    lean = [(head[i]-hips[i]) - (head[0]-hips[0]) for i in range(len(hips))]
    peak = max(range(len(lean)), key=lambda i: lean[i].xy.length)
    # facing: from hips to the toes average at frame 0
    bpy.context.scene.frame_set(s)
    toe = (arm.matrix_world @ arm.pose.bones["mixamorig:LeftToeBase"].head + arm.matrix_world @ arm.pose.bones["mixamorig:RightToeBase"].head)/2
    face = (toe - (lf[0]+rf[0])/2); face.z = 0
    rows.append({"file": f.split("/")[-1], "frames": e-s, "fps": fps, "seconds": (e-s)/fps,
                 "hipsTravel": [round(v,4) for v in d], "facingAtStart": [round(v,3) for v in face.normalized()],
                 "headLeanPeak": [round(v,4) for v in lean[peak]], "headLeanPeakSec": round(peak/fps,3),
                 "hipsDropMax": round(min(h.z for h in hips)-hips[0].z,4),
                 "maxHipsOffset": [round(v,4) for v in max((h-hips[0] for h in hips), key=lambda v: v.xy.length)]})
json.dump(rows, open(out, "w"), indent=1)
print("ANALYZED", len(rows))
