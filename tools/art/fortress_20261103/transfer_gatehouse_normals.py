"""Transfer source shading onto the reduced topology; retain a full-source fallback."""
import bpy,json,sys,hashlib
from pathlib import Path
source=Path(sys.argv[sys.argv.index('--')+1]);out=Path(sys.argv[sys.argv.index('--')+2]);out.mkdir(parents=True,exist_ok=True);assert not (out/'FortressGatehouse_baked.glb').exists()
bpy.ops.wm.open_mainfile(filepath=str((source/'FortressGatehouse.blend').resolve()));scene=bpy.context.scene;assert scene.get('session_owner')=='veyr-fortress-20261103';raw=bpy.data.objects['SOURCE_Gatehouse'];low=bpy.data.objects['FortressGatehouse'];raw.hide_set(False)
for obj in scene.objects:obj.select_set(False)
raw.select_set(True);bpy.context.view_layer.objects.active=raw
bpy.ops.export_scene.gltf(filepath=str((out/'FortressGatehouse_full_source.glb').resolve()),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
raw.select_set(False);low.select_set(True);bpy.context.view_layer.objects.active=low
transfer=low.modifiers.new('Source_to_reduced_normals','DATA_TRANSFER');transfer.object=raw;transfer.use_loop_data=True;transfer.data_types_loops={'CUSTOM_NORMAL'};transfer.loop_mapping='POLYINTERP_NEAREST';transfer.mix_mode='REPLACE';transfer.mix_factor=1.
bpy.ops.object.modifier_apply(modifier=transfer.name)
raw.hide_render=True;low.hide_render=False
bpy.ops.export_scene.gltf(filepath=str((out/'FortressGatehouse_baked.glb').resolve()),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
scene.render.filepath=str((out/'threequarter.png').resolve());bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str((out/'FortressGatehouse.blend').resolve()))
(out/'repair.json').write_text(json.dumps({'change':'DataTransfer POLYINTERP_NEAREST source corner normals onto reduced topology; original PBR textures retained','faces':len(low.data.polygons),'outputSHA256':hashlib.sha256((out/'FortressGatehouse_baked.glb').read_bytes()).hexdigest()},indent=2)+'\n');print('SOURCE_NORMAL_TRANSFER_COMPLETE',flush=True)
