"""Make ab-idle-20261028/work/prepared_<label>.blend from a refined clip, using the same normalisation as
ab-idle-20261028/scripts/prep_export_measure.py (deform armature + body mesh only, neutral names), minus GLB/metrics.
Usage: blender -b --factory-startup Dragon_Idle_v2r_v2.blend --python prep_render.py -- <action> <label> <out.blend>
"""
import bpy, sys
args = sys.argv[sys.argv.index("--") + 1:]
ACTION, label, out = args
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
D = next(m.object for m in M.modifiers if m.type == "ARMATURE")
for pb in D.pose.bones:
    for c in list(pb.constraints): pb.constraints.remove(c)
for o in list(bpy.data.objects):
    if o not in (D, M): bpy.data.objects.remove(o, do_unlink=True)
act = bpy.data.actions[ACTION]
D.animation_data.action = act
if act.slots: D.animation_data.action_slot = act.slots[0]
for t in list(D.animation_data.nla_tracks): D.animation_data.nla_tracks.remove(t)
if M.animation_data: M.animation_data_clear()
sc = bpy.context.scene
sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
act.name = f"clip_{label}"
D.name = "DragonArmature"; D.data.name = "DragonArmature"; M.name = "DragonMesh"; M.data.name = "DragonMesh"
for i, m in enumerate(M.data.materials):
    if m: m.name = f"DragonMat{i}"
for o in (D, M): o.hide_set(False); o.hide_viewport = False; o.hide_render = False
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("PREPARED", out, act.name, tuple(act.frame_range), sc.render.fps)
