"""Import the preserved walk as reference into the session-owned Blender scene."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path('/Users/midir/veyr-blender-walk-20261021')
ASSETS = Path('/Users/midir/Documents/Codex/2026-10-17/task-3/Local/art-pass-20261019/knight/twohand-strong-review-20261019-codex')
assert not ROOT.joinpath('Knight_Walk_Blender_v3.blend').exists(), 'Preserve existing authoring scene'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.render.fps = 60
bpy.ops.import_scene.gltf(filepath=str(ASSETS/'WalkTwoHand_Ready_v2.glb'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
rig.name = 'Knight_Walk_Rig'
rig['source_candidate'] = 'WalkTwoHand_Ready_v2.glb (unapproved reference)'
socket = bpy.data.objects.get('ReviewWeaponSocket')
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ASSETS/'BoatGreatsword_StrongGrip_v1.glb'))
sword_objects = set(bpy.data.objects) - before
for obj in sword_objects:
    if obj.parent not in sword_objects:
        obj.parent = socket
        obj.location = (0,0,0)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = (1,0,0,0)
        obj.scale = (1,1,1)
    obj['review_attachment'] = True
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 211
scene.frame_set(70)
bpy.ops.object.camera_add(location=(2.2,-3.4,1.5))
cam=bpy.context.object;cam.name='Review_Camera'
cam.rotation_euler=(Vector((0,-.27,.63))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=1.9;scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.display.shading.light='STUDIO'
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.display.shading.background_type='WORLD'
scene.world.color=(.055,.055,.055)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Knight_Walk_Blender_v3.blend'))
info={'blender':bpy.app.version_string,'objects':[(o.name,o.type) for o in scene.objects], 'bones':[(b.name,b.parent.name if b.parent else None,list(b.head_local),list(b.tail_local)) for b in rig.data.bones], 'actions':[(a.name,list(a.frame_range)) for a in bpy.data.actions]}
ROOT.joinpath('import-inspection.json').write_text(json.dumps(info,indent=2))
scene.render.filepath=str(ROOT/'walk-import.png')
bpy.ops.render.render(write_still=True)
print(json.dumps(info))
