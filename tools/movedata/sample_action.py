"""Sample one Blender Action into a move-data sample file (runs inside Blender, headless).

    blender --background --factory-startup <file.blend> --python tools/movedata/sample_action.py -- \
        --action roar_sd_v2 --move roar --out Local/movedata/samples [--rig tools/movedata/veyr_rig.json]

Writes <out>/<move>.sample.npz. Everything spatial is converted to Unreal axes and centimetres at RIG
scale: Unreal (x, y, z) cm = (100 x, -100 y, 100 z) Blender metres (x forward, y right, z up). The game
scale (the presentation's component scale) is applied later by build_moves.py, not here.

The file holds, per frame at 24 fps: every bone's world head and tail, every bone's world rotation,
every bone's local (basis) quaternion for twist, the root bone transform, the named part points from the
rig map (bone points plus vertex-tracked foot soles, toe tips and body undersides), the mesh bounds, and
a stride subsample of the deformed mesh. It also holds the rest pose, every rest vertex with its
dominant bone, and provenance (blend path, md5, action, frame range).
"""
import argparse
import hashlib
import json
import os
import sys

import bpy
import numpy as np

FLIP = np.array([1.0, -1.0, 1.0])  # Blender -> Unreal axis flip (y)
S = np.diag(FLIP)


def ue_pos(p):
    """Blender metres (..., 3) -> Unreal cm, same rig scale."""
    return np.asarray(p, dtype=np.float64) * 100.0 * FLIP


def ue_rot(r):
    """Blender rotation (..., 3, 3) -> Unreal axes (S R S, keeps det +1)."""
    return S @ np.asarray(r, dtype=np.float64) @ S


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True)
    ap.add_argument("--move", required=True, help="move name used in moves.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rig", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "veyr_rig.json"))
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--vertex-stride", type=int, default=8)
    return ap.parse_args(argv)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    args = parse_args()
    rig = json.load(open(args.rig))
    scene = bpy.context.scene
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"
              and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
    if not meshes:
        raise SystemExit("no mesh skinned to %s" % arm.name)
    mesh = max(meshes, key=lambda o: len(o.data.vertices))

    act = bpy.data.actions.get(args.action)
    if act is None:
        raise SystemExit("action %r not in %s; have %s" % (args.action, bpy.data.filepath, [a.name for a in bpy.data.actions]))
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    try:  # Blender 4.4+ slotted actions
        if getattr(act, "slots", None) and len(act.slots) and arm.animation_data.action_slot is None:
            arm.animation_data.action_slot = act.slots[0]
    except AttributeError:
        pass

    f0, f1 = (int(round(x)) for x in act.frame_range)
    scene_fps = scene.render.fps / scene.render.fps_base
    n = int(round((f1 - f0) / scene_fps * args.fps)) + 1
    times = np.arange(n) / args.fps
    src_frames = f0 + times * scene_fps

    bones = list(arm.pose.bones)
    names = [pb.name for pb in bones]
    index = {nm: i for i, nm in enumerate(names)}
    parent = np.array([index[pb.parent.name] if pb.parent else -1 for pb in bones])
    B = len(bones)
    mw = np.array(arm.matrix_world)

    # rest pose
    rest_head = np.array([(arm.matrix_world @ pb.bone.head_local)[:] for pb in bones])
    rest_tail = np.array([(arm.matrix_world @ pb.bone.tail_local)[:] for pb in bones])
    rest_rot = np.array([np.array(arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()) for pb in bones])

    # rest mesh (undeformed) and dominant bone per vertex
    vg_bone = {g.index: index.get(g.name, -1) for g in mesh.vertex_groups}
    V = len(mesh.data.vertices)
    vrest = np.empty(V * 3)
    mesh.data.vertices.foreach_get("co", vrest)
    vrest = vrest.reshape(V, 3) @ np.array(mesh.matrix_world)[:3, :3].T + np.array(mesh.matrix_world)[:3, 3]
    dom = np.full(V, -1, dtype=np.int32)
    domw = np.zeros(V, dtype=np.float32)
    for v in mesh.data.vertices:
        best, bw = -1, 0.0
        for g in v.groups:
            b = vg_bone.get(g.group, -1)
            if b >= 0 and g.weight > bw:
                best, bw = b, g.weight
        dom[v.index], domw[v.index] = best, bw

    def bone_set(bnames):
        ids = [index[b] for b in bnames if b in index]
        missing = [b for b in bnames if b not in index]
        if missing:
            raise SystemExit("rig map names missing bones: %s" % missing)
        return np.isin(dom, ids)

    # vertex-tracked points, chosen once on the rest mesh
    vpoints = {}
    k_sole = int(rig.get("foot_sole_vertices", 32))
    k_toe = int(rig.get("foot_toe_vertices", 16))
    for foot, spec in rig["feet"].items():
        ids = np.nonzero(bone_set(spec["bones"]))[0]
        if len(ids) < k_sole:
            raise SystemExit("foot %s has only %d vertices" % (foot, len(ids)))
        z = vrest[ids, 2]
        sole = ids[np.argsort(z)[:k_sole]]
        low = ids[z <= np.quantile(z, 0.3)]
        toe = low[np.argsort(-vrest[low, 0])[:k_toe]]  # most forward (+X) of the low third
        vpoints["sole_" + foot] = sole
        vpoints["toe_" + foot] = toe
    k_body = int(rig.get("body_low_vertices", 32))
    for name, bnames in rig.get("body_low", {}).items():
        ids = np.nonzero(bone_set(bnames))[0]
        vpoints[name] = ids[np.argsort(vrest[ids, 2])[:k_body]]

    # whole vertex sets, for the per-frame lowest vertex (contact height) of each foot / body underside
    low_sets = {"foot_" + f: np.nonzero(bone_set(spec["bones"]))[0] for f, spec in rig["feet"].items()}
    low_sets.update({nm: np.nonzero(bone_set(b))[0] for nm, b in rig.get("body_low", {}).items()})
    low_names = list(low_sets)

    bpoints = rig["points"]
    part_names = list(bpoints) + list(vpoints)
    P = len(part_names)
    sub_idx = np.arange(0, V, max(1, args.vertex_stride))

    heads = np.zeros((n, B, 3)); tails = np.zeros((n, B, 3)); rots = np.zeros((n, B, 3, 3))
    lquat = np.zeros((n, B, 4)); parts = np.zeros((n, P, 3))
    mesh_min = np.zeros((n, 3)); mesh_max = np.zeros((n, 3))
    sub_pos = np.zeros((n, len(sub_idx), 3), dtype=np.float32)
    root_i = index[rig["root_bone"]]
    root_mat = np.zeros((n, 4, 4))
    lows = np.zeros((n, len(low_names), 3))

    buf = np.empty(V * 3)
    for i, sf in enumerate(src_frames):
        fi = int(np.floor(sf + 1e-6)); sub = float(sf - fi)
        scene.frame_set(fi, subframe=sub)
        dg = bpy.context.evaluated_depsgraph_get()
        for b, pb in enumerate(bones):
            m = mw @ np.array(pb.matrix)
            heads[i, b] = m[:3, 3]
            tails[i, b] = (arm.matrix_world @ pb.tail)[:]
            rots[i, b] = m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0)
            q = pb.matrix_basis.to_quaternion()
            lquat[i, b] = (q.w, q.x, q.y, q.z)
        root_mat[i] = mw @ np.array(bones[root_i].matrix)
        ev = mesh.evaluated_get(dg)
        me = ev.to_mesh()
        me.vertices.foreach_get("co", buf)
        co = buf.reshape(V, 3) @ np.array(mesh.matrix_world)[:3, :3].T + np.array(mesh.matrix_world)[:3, 3]
        ev.to_mesh_clear()
        mesh_min[i], mesh_max[i] = co.min(0), co.max(0)
        sub_pos[i] = co[sub_idx]
        for L, nm in enumerate(low_names):
            ids = low_sets[nm]
            lows[i, L] = co[ids[np.argmin(co[ids, 2])]]
        for p, nm in enumerate(part_names):
            if nm in bpoints:
                spec = bpoints[nm]; b = index[spec["bone"]]
                at = spec.get("at", "head")
                parts[i, p] = heads[i, b] if at == "head" else tails[i, b] if at == "tail" else 0.5 * (heads[i, b] + tails[i, b])
            else:
                parts[i, p] = co[vpoints[nm]].mean(0)

    # rest-frame (bind) values of the part points
    rest_parts = np.zeros((P, 3))
    for p, nm in enumerate(part_names):
        if nm in bpoints:
            spec = bpoints[nm]; b = index[spec["bone"]]; at = spec.get("at", "head")
            rest_parts[p] = rest_head[b] if at == "head" else rest_tail[b] if at == "tail" else 0.5 * (rest_head[b] + rest_tail[b])
        else:
            rest_parts[p] = vrest[vpoints[nm]].mean(0)

    root_mat_ue = np.zeros_like(root_mat)
    root_mat_ue[:, :3, :3] = ue_rot(root_mat[:, :3, :3])
    root_mat_ue[:, :3, 3] = ue_pos(root_mat[:, :3, 3])
    root_mat_ue[:, 3, 3] = 1.0

    os.makedirs(args.out, exist_ok=True)
    out = os.path.join(args.out, "%s.sample.npz" % args.move)
    blend = bpy.data.filepath
    np.savez_compressed(
        out,
        format=np.array("veyr-movedata-sample/1"),
        units=np.array("Unreal axes (x forward, y right, z up), cm at rig scale = Blender m x 100 with y flipped; game scale not applied"),
        move=np.array(args.move), action=np.array(act.name),
        blend=np.array(blend), blend_md5=np.array(md5(blend)),
        rig_map=np.array(json.dumps(rig)),
        fps=np.array(args.fps), times=times, src_frames=src_frames, frame_range=np.array([f0, f1]),
        bone_names=np.array(names), bone_parent=parent,
        heads=ue_pos(heads), tails=ue_pos(tails), rots=ue_rot(rots), local_quat=lquat,
        rest_heads=ue_pos(rest_head), rest_tails=ue_pos(rest_tail), rest_rots=ue_rot(rest_rot),
        root_name=np.array(rig["root_bone"]), root_mat=root_mat_ue,
        part_names=np.array(part_names), parts=ue_pos(parts), rest_parts=ue_pos(rest_parts),
        vpoint_names=np.array(list(vpoints)),
        low_names=np.array(low_names), lows=ue_pos(lows),
        vpoint_index=np.array([json.dumps({k: v.tolist() for k, v in vpoints.items()})]),
        mesh_name=np.array(mesh.name), mesh_vertices=np.array(V),
        mesh_height_cm=np.array(float(np.ptp(vrest[:, 2])) * 100.0),
        mesh_min=np.minimum(ue_pos(mesh_min), ue_pos(mesh_max)), mesh_max=np.maximum(ue_pos(mesh_min), ue_pos(mesh_max)),
        vert_rest=ue_pos(vrest).astype(np.float32), vert_bone=dom, vert_weight=domw,
        sub_idx=sub_idx, sub_pos=ue_pos(sub_pos).astype(np.float32),
    )
    h = (mesh_max[:, 2] - mesh_min[:, 2]) * 100.0
    print("MOVEDATA_SAMPLE %s action=%s frames=%d (%d..%d) bones=%d parts=%d verts=%d mesh_height_cm=%.2f..%.2f -> %s"
          % (args.move, act.name, n, f0, f1, B, P, V, h.min(), h.max(), out))


if __name__ == "__main__":
    main()
