"""RollAttack_Blender_v1: the owner-praised RollBoat (copied exactly) + an authored rising one-hand slash into the
approved one-hand idle. Execute only in the task-owned Blender (port 9885) via run_nc.py."""
from pathlib import Path
import bpy, math, json, importlib.util
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent
_sp = importlib.util.spec_from_file_location("veyr_nc_clips", HERE / "clips.py"); C = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(C)
core = C.core; REPO = C.REPO; OUT = C.OUT
ROLL = OUT / "roll_source/RollBoat.glb"
BASE = REPO / "Local/Blender/approved-rebuild-20261021/idle_one_Blender_v1.blend"


def probe():
    C.open_scene(BASE); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.import_scene.gltf(filepath=str(ROLL))
    added = set(bpy.data.objects) - before; r = next(o for o in added if o.type == "ARMATURE")
    names_r = [b.name for b in r.data.bones]; names_k = [b.name for b in rig.data.bones]
    common = [n for n in names_k if n in names_r]
    err = max(max(abs(rig.data.bones[n].matrix_local[i][j] - r.data.bones[n].matrix_local[i][j]) for i in range(4) for j in range(4)) for n in common)
    act = r.animation_data.action if r.animation_data else None
    fr = act.frame_range if act else None
    out = {"rollBones": len(names_r), "knightBones": len(names_k), "common": len(common), "missingInRoll": [n for n in names_k if n not in names_r][:10], "extraInRoll": [n for n in names_r if n not in names_k][:10],
           "restMaxDiff": err, "rigWorld": [list(x) for x in r.matrix_world], "action": act.name if act else None, "frameRange": list(fr) if fr else None, "fps": s.render.fps,
           "objects": [(o.name, o.type, o.parent.name if o.parent else None) for o in added]}
    # hips path
    if act:
        hp = []
        for f in range(int(fr[0]), int(fr[1]) + 1, max(1, int((fr[1] - fr[0]) / 12))):
            s.frame_set(f); hp.append((f, [round(x, 3) for x in (r.matrix_world @ r.pose.bones["Hips"].head)], [round(x, 3) for x in (r.matrix_world @ r.pose.bones["RightHand"].head)]))
        out["hips"] = hp
    return out


def roll_preview():
    """Approved one-hand scene with the RollBoat action on the deform rig and our boat sword on the right hand (preview only, never saved)."""
    C.open_scene(BASE); s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]
    s.frame_set(0); bpy.context.view_layer.update()
    off = (rig.matrix_world @ rig.pose.bones["RightHand"].matrix).inverted() @ sock.matrix_world
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.import_scene.gltf(filepath=str(ROLL))
    added = set(bpy.data.objects) - before; r = next(o for o in added if o.type == "ARMATURE"); act = r.animation_data.action
    for o in added: bpy.data.objects.remove(o, do_unlink=True)
    rig.animation_data.action = act
    if hasattr(rig.animation_data, "action_slot") and act.slots: rig.animation_data.action_slot = act.slots[0]
    s.frame_start = 0; s.frame_end = 117; s["duration"] = .78
    sock.animation_data_clear(); prev = {}
    for f in range(118):
        s.frame_set(f); bpy.context.view_layer.update(); sock.matrix_world = (rig.matrix_world @ rig.pose.bones["RightHand"].matrix) @ off; core.key(sock, f, prev)
    s.frame_set(117); end = {n: [round(x, 4) for x in (rig.matrix_world @ rig.pose.bones[n].head)] for n in ("Hips", "Spine2", "Head", "LeftFoot", "RightFoot", "LeftHand", "RightHand")}
    bd = (sock.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    s.frame_set(0); st = {n: [round(x, 4) for x in (rig.matrix_world @ rig.pose.bones[n].head)] for n in ("Hips", "LeftFoot", "RightFoot", "RightHand")}
    return {"gripOffset": [list(x) for x in off], "end": end, "endBlade": list(bd), "start": st}
