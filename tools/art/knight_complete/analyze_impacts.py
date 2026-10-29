"""Headless Blender: per-frame torso pitch/roll/yaw (chest vs start) and shoulder travel for impact clips."""
import bpy, sys, json, math
args = sys.argv[sys.argv.index("--")+1:]
out, files = args[0], args[1:]
rows = []
for f in files:
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=f)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    s, e = (int(round(x)) for x in arm.animation_data.action.frame_range)
    def W(fr, b): bpy.context.scene.frame_set(fr); return (arm.matrix_world @ arm.pose.bones[b].head).copy()
    series = []
    for fr in range(s, e+1):
        ls, rs, hip, head = W(fr,"mixamorig:LeftArm"), W(fr,"mixamorig:RightArm"), W(fr,"mixamorig:Hips"), W(fr,"mixamorig:Head")
        sh = ls - rs  # points to character left (+X when facing -Y)
        yaw = math.degrees(math.atan2(sh.y, sh.x))      # + = left shoulder moved back (+Y) => torso turned to its left
        roll = math.degrees(math.atan2(sh.z, sh.xy.length))  # + = left shoulder up => leaning right
        up = head - hip
        pitch = math.degrees(math.atan2(up.y, up.z))   # + = head back (+Y)
        side = math.degrees(math.atan2(up.x, up.z))    # + = head toward character left (+X)
        series.append((yaw, roll, pitch, side, (ls.y+rs.y)/2, ls.y, rs.y))
    b = series[0]
    d = [[v - b[i] for i, v in enumerate(r)] for r in series]
    def peak(i): j = max(range(len(d)), key=lambda k: abs(d[k][i])); return round(d[j][i], 2), round((j)/30, 3)
    rows.append({"file": f.split("/")[-1], "seconds": (e-s)/30, "yawDeg": peak(0), "rollDeg": peak(1), "pitchBackDeg": peak(2), "sideLeftDeg": peak(3),
                 "leftShoulderBackM": peak(5), "rightShoulderBackM": peak(6)})
json.dump(rows, open(out, "w"), indent=1); print("DONE")
