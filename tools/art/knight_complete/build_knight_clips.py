"""Headless Blender driver for the knight completion pass (2026-10-28).
Stage retarget: Mixamo strafes/impacts -> knight rig via fab_rig_testing/retarget.py (+ one mirrored impact).
Stage fit: weapon-aware IK carry via fab_rig_testing/fit_weapon.py, one-hand and two-hand grips.
Run: Blender --background --factory-startup --python build_knight_clips.py -- retarget|fit [NAME ...]"""
import bpy, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
FAB = HERE.parent / "blender/fab_rig_testing"
args = sys.argv[sys.argv.index("--")+1:]
stage, only = args[0], set(args[1:])
SRC = "Local/FabRigTesting/Source/Mixamo/"
# (name, fbx, travel, mirror, classification)
RETARGET = [
 ("Mixamo_StrafeLeft_v1",     "sword and shield strafe (2).fbx", False, False, "walk strafe left: hips +1.41 m along +X (character left) in 1.30 s"),
 ("Mixamo_StrafeRight_v1",    "sword and shield strafe.fbx",     False, False, "walk strafe right: hips -1.39 m along X in 1.13 s"),
 ("Mixamo_StrafeRunLeft_v1",  "sword and shield strafe (3).fbx", False, False, "run strafe left: +2.32 m in 0.67 s"),
 ("Mixamo_StrafeRunRight_v1", "sword and shield strafe (4).fbx", False, False, "run strafe right: -2.38 m in 0.70 s"),
 ("Mixamo_ImpactFront_v1",    "sword and shield impact (3).fbx", False, False, "hit from front: head pitches back 39 deg, both shoulders back 0.26-0.28 m"),
 ("Mixamo_ImpactBack_v1",     "sword and shield impact (2).fbx", False, False, "hit from behind: head pitches forward 25 deg"),
 ("Mixamo_ImpactLeft_v1",     "sword and shield impact.fbx",     False, False, "hit from front-left: left shoulder back 0.18 m vs right 0.11, torso yaw 22 deg"),
 ("Mixamo_ImpactRight_v1",    "sword and shield impact.fbx",     False, True,  "mirror of ImpactLeft"),
]
if stage == "retarget":
    g = {"__file__": str(FAB/"retarget.py")}
    exec(compile((FAB/"retarget.py").read_text(), str(FAB/"retarget.py"), "exec"), g)
    root = g["ROOT"]
    for name, fbx, travel, mirror, why in RETARGET:
        if only and name not in only: continue
        if (g["OUT"]/"Exports"/(name+".glb")).exists(): print("SKIP existing", name); continue
        bpy.context.scene["session_owner"] = g["OWNER"]
        g["run"](root/SRC/fbx, "mixamo", name, travel, mirror)
        rep = g["OUT"]/"Exports"/(name+".json"); d = json.loads(rep.read_text()); d["classification"] = why; rep.write_text(json.dumps(d, indent=2))
        print("RETARGETED", name, flush=True)
elif stage == "fit":
    g = {"__file__": str(FAB/"fit_weapon.py")}
    exec(compile((FAB/"fit_weapon.py").read_text(), str(FAB/"fit_weapon.py"), "exec"), g)
    bpy.context.scene["session_owner"] = g["OWNER"]
    refs = {"one": g["reference"]("WalkOneHand_Blender_v2r2.glb"), "two": g["reference"]("RunTwoHand_Blender_polish_v2.glb"), "guard": g["reference"]("GuardReadyTwoHand_Blender_v4r4.glb", True)}
    for name, *_ in RETARGET:
        base = name[:-3]
        for grip, suffix in (("one", ""), ("two", "TwoHand")):
            out = base.replace("Mixamo_", "Mixamo_") + suffix + "_v2"
            if only and out not in only: continue
            if (g["OUT"]/"Exports"/(out+".glb")).exists(): print("SKIP existing", out); continue
            bpy.context.scene["session_owner"] = g["OWNER"]
            g["fit"]("walk", refs, "v2", grip, out, name)
            print("FITTED", out, flush=True)
