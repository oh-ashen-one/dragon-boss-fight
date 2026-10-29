"""Round 3 (2026-10-29): survey the local Mixamo Sword and Shield clips that could base a blink launch/landing or a
lateral sprint. Headless, no render: blender --background --factory-startup --python analyze_round3_sources.py -- OUT.json FBX...
Per clip: frames, hips height curve (cm above its frame-0 height, source units), foot heights (airborne frames),
hips planar travel, and the facing (shoulder line) at start."""
import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
out, files = Path(args[0]), args[1:]
rows = []
for f in files:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=f)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    a, b = (round(x) for x in arm.animation_data.action.frame_range)
    pb = arm.pose.bones; mw = arm.matrix_world; s = bpy.context.scene
    P = lambda n: mw @ pb["mixamorig:" + n].head
    s.frame_set(a); h0 = P("Hips").copy(); f0 = {sd: P(sd + "Foot").z for sd in ("Left", "Right")}
    leg = (P("LeftUpLeg") - P("LeftLeg")).length + (P("LeftLeg") - P("LeftFoot")).length
    hz, lz, rz, trav, width, tilt = [], [], [], [], [], []
    for fr in range(a, b + 1):
        s.frame_set(fr)
        h = P("Hips"); hz.append(round((h.z - h0.z) / leg, 3)); trav.append([round((h.x - h0.x) / leg, 3), round((h.y - h0.y) / leg, 3)])
        lz.append(round((P("LeftFoot").z - f0["Left"]) / leg, 3)); rz.append(round((P("RightFoot").z - f0["Right"]) / leg, 3))
        d = P("LeftFoot") - P("RightFoot"); d.z = 0; width.append(round(d.length / leg, 3))
        sp = P("Neck") - P("Hips"); tilt.append(round(math.degrees(math.atan2(math.hypot(sp.x, sp.y), sp.z)), 1))
    s.frame_set(a); L = P("LeftArm") - P("RightArm")
    rows.append({"file": Path(f).name, "frames": b - a + 1, "fps": s.render.fps, "legLengthSourceUnits": round(leg, 4),
                 "units": "hips/feet in leg lengths (knight leg = 0.46 rig m = 110 game cm)", "hipsZ": hz, "leftFootZ": lz, "rightFootZ": rz,
                 "hipsTravelXY": trav, "ankleWidth": width, "spineTiltDeg": tilt, "shoulderLineStart": [round(L.x, 3), round(L.y, 3)]})
    print("SURVEY", Path(f).name, b - a + 1, "minHipsZ", min(hz), "maxFootZ", max(max(lz), max(rz)), flush=True)
out.write_text(json.dumps(rows, indent=1) + "\n")
