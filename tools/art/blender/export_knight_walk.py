import os
import bpy,json,hashlib
from pathlib import Path
from mathutils import Vector
root=Path(os.environ.get('VEYR_BLENDER_WORK', '/Users/midir/veyr-blender-walk-20261021'));scene=bpy.context.scene
rig=bpy.data.objects['Knight_Walk_Rig'];socket=bpy.data.objects['ReviewWeaponSocket']
# Compare baked endpoint poses to the preserved reference in the same Blender rig.
new_action=rig.animation_data.action;new_slot=rig.animation_data.action_slot
source=bpy.data.actions['REFERENCE_Walk_v2_UNAPPROVED']
endpoint_errors=[]
for f in (0,210):
 scene.frame_set(f);baked={b.name:b.matrix.copy() for b in rig.pose.bones}
 rig.animation_data.action=source;rig.animation_data.action_slot=source.slots['OBArmature'];scene.frame_set(f);bpy.context.view_layer.update()
 endpoint_errors.append(max(max(abs(baked[b.name][i][j]-b.matrix[i][j]) for i in range(4) for j in range(4)) for b in rig.pose.bones))
 rig.animation_data.action=new_action;rig.animation_data.action_slot=new_slot
 scene.frame_set(f);bpy.context.view_layer.update()
assert max(endpoint_errors)<1e-4, f'Idle endpoint mismatch: {endpoint_errors}'
scene.frame_set(70)
scene.render.resolution_x=1000;scene.render.resolution_y=1000
travel=rig.pose.bones['Hips'].matrix.translation.y
cam=scene.camera;cam.location=Vector((2.2,-3.4+travel,1.5));cam.rotation_euler=(Vector((0,travel-.15,.87))-cam.location).to_track_quat('-Z','Y').to_euler()
for o in scene.objects:o.select_set(False)
for name in ['Knight_Walk_Rig','mesh','ReviewWeaponSocket']:bpy.data.objects[name].select_set(True)
bpy.context.view_layer.objects.active=rig
out=root/'WalkTwoHand_Blender_v3.glb'
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name='WalkTwoHand_Blender_v3',export_frame_range=True,export_frame_step=1,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
# Preserve the executable recipe alongside its editable controls in the blend.
for name in ['refine_knight_walk.py','prepare_knight_walk.py']:
 txt=bpy.data.texts.get(name) or bpy.data.texts.new(name);txt.clear();txt.write((root/name).read_text())
bpy.ops.wm.save_as_mainfile(filepath=str(root/'Knight_Walk_Blender_v3.blend'),compress=True)
report={'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'blenderEndpointMatrixError':endpoint_errors,'ownerApproved':False,'file':out.name}
(root/'blender-walk-v3-export.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
