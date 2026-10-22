"""Bake DRAGON_CTRL-driven deform pose into one action, export GLB (skin + animation), save blend.
Writes only under Local/Blender/dragon-v1-20261021/. Refuses to overwrite unless ALLOW_OVERWRITE."""
import bpy, json, hashlib
from pathlib import Path
W = Path("/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021")
OUTD = W / "flight_r2"
NAME = globals().get('CLIP', 'Dragon_Idle_Blender_v1'); RUNTIME = globals().get('RUNTIME_CLIP', 'Idle')
F0, F1 = globals().get('RANGE', (0, 180))
glb = W/"export"/(NAME+".glb"); blend = OUTD/(NAME+".blend")
assert NAME.endswith("_v1r2"), NAME
if not globals().get('ALLOW_OVERWRITE'):
    assert not glb.exists() and not blend.exists(), 'refusing to overwrite '+NAME
glb.parent.mkdir(parents=True, exist_ok=True)
s = bpy.context.scene; owner = s['session_owner']
D = bpy.data.objects['DRAGON_DEFORM']; M = bpy.data.objects['DRAGON_MESH']; C = bpy.data.objects['DRAGON_CTRL']
win = bpy.context.window_manager.windows[0]
old = bpy.data.actions.get(NAME)
if old: bpy.data.actions.remove(old)
with bpy.context.temp_override(window=win):
    if bpy.context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    for o in s.objects: o.select_set(False)
    D.hide_set(False); D.select_set(True); bpy.context.view_layer.objects.active = D
    bpy.ops.object.mode_set(mode='POSE')
    for pb in D.pose.bones:
        try: pb.select = True
        except AttributeError: pb.bone.select = True
    bpy.ops.nla.bake(frame_start=F0, frame_end=F1, step=1, only_selected=False, visual_keying=True,
                     clear_constraints=False, clear_parents=False, use_current_action=False, clean_curves=False,
                     bake_types={'POSE'}, channel_types={'LOCATION','ROTATION','SCALE'})
    bpy.ops.object.mode_set(mode='OBJECT')
act = D.animation_data.action; act.name = NAME; act.use_fake_user = True
act['veyr_runtime_clip'] = RUNTIME; act['loop'] = bool(globals().get('LOOP', True)); act['fps'] = s.render.fps
act['authoring'] = globals().get('AUTHORING', 'Blender 5.2 layered NLA on DRAGON_CTRL; baked visual keys; rig v008-weightfix')
for k_, v_ in globals().get('EXTRAS', {}).items(): act[k_] = v_
for fc in (f for l in act.layers for st in l.strips for cb in st.channelbags for f in cb.fcurves):
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
mutes = [(c, c.mute) for pb in D.pose.bones for c in pb.constraints]
for c, _ in mutes: c.mute = True
ctrl_hidden = C.hide_get(); C.hide_set(True)
with bpy.context.temp_override(window=win):
    for o in s.objects: o.select_set(False)
    D.select_set(True); M.hide_set(False); M.select_set(True); bpy.context.view_layer.objects.active = D
    s.frame_start, s.frame_end = F0, F1
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_animations=True,
        export_animation_mode='ACTIVE_ACTIONS', export_nla_strips_merged_animation_name=NAME, export_frame_range=True,
        export_frame_step=1, export_force_sampling=True, export_optimize_animation_size=False, export_skins=True,
        export_extras=True, export_morph=True, export_morph_normal=False, export_morph_animation=True, export_cameras=False, export_lights=False, export_def_bones=False, export_yup=True)
for c, mu in mutes: c.mute = mu
D.animation_data.action = None
C.hide_set(ctrl_hidden)
for name in ("author_hover_r2.py", "dcommon.py", "flight_metrics.py", "bake_r2.py", "audit_r2.py"):
    p = Path("/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2")/name
    if p.exists():
        t = bpy.data.texts.get(name) or bpy.data.texts.new(name); t.clear(); t.write(p.read_text())
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
s['session_owner'] = owner
rep = {'glb': str(glb), 'sha256': hashlib.sha256(glb.read_bytes()).hexdigest(), 'bytes': glb.stat().st_size, 'blend': str(blend),
       'action': NAME, 'runtime_clip': RUNTIME, 'frames': [F0, F1], 'fps': s.render.fps, 'ownerApproved': False}
(OUTD/"reports"/(NAME+".export.json")).write_text(json.dumps(rep, indent=1))
print('RES', json.dumps(rep))
