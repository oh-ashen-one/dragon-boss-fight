"""Dump the evaluated (skinned) dragon mesh per frame for CPU measurement; no rendering, no GPU.
Usage: blender -b --factory-startup <file.blend> --python dump_verts.py -- <action> <out.npz> [every=1]
npz: v [F,V,3] int16 world position in 0.1 mm, tri [T,3], vgroup [V] dominant vertex-group index, groups (names), frames,
bones (names) + bone_head/bone_tail [F,B,3] float32 (world, m).
"""
import bpy, sys, numpy as np
args = sys.argv[sys.argv.index("--") + 1:]
ACT, OUT = args[0], args[1]
opt = dict(a.split("=", 1) for a in args[2:])
sc = bpy.context.scene
A = next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act = bpy.data.actions[ACT]
A.animation_data.action = act
if act.slots: A.animation_data.action_slot = act.slots[0]
for t in list(A.animation_data.nla_tracks): A.animation_data.nla_tracks.remove(t)
f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
frames = list(range(f0, f1 + 1, int(opt.get("every", 1))))
me = M.data
me.calc_loop_triangles()
tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
names = [g.name for g in M.vertex_groups]
vg = np.array([max(v.groups, key=lambda g: g.weight).group if len(v.groups) else -1 for v in me.vertices], np.int16)
bones = [b.name for b in A.pose.bones]
V = np.empty((len(frames), len(me.vertices), 3), np.int16)
BH = np.empty((len(frames), len(bones), 3), np.float32); BT = np.empty_like(BH)
for i, f in enumerate(frames):
    sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
    Me = M.evaluated_get(dg); m2 = Me.to_mesh()
    co = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    mw = np.array(Me.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]
    V[i] = np.round(co * 1e4).astype(np.int16); Me.to_mesh_clear()
    Ae = A.evaluated_get(dg); aw = Ae.matrix_world
    for j, b in enumerate(bones):
        pb = Ae.pose.bones[b]; BH[i, j] = tuple(aw @ pb.head); BT[i, j] = tuple(aw @ pb.tail)
np.savez_compressed(OUT, v=V, tri=tri, vgroup=vg, groups=np.array(names), frames=np.array(frames), bones=np.array(bones), bone_head=BH, bone_tail=BT,
                    fps=np.array(sc.render.fps / sc.render.fps_base))
print("DUMPED", ACT, OUT, len(frames), "frames", flush=True)
