"""Recompute reduced-mesh corner normals; preserve source and failed reduction evidence."""
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
source=Path(sys.argv[sys.argv.index('--')+1]);out=Path(sys.argv[sys.argv.index('--')+2]);out.mkdir(parents=True,exist_ok=True);assert not (out/'FortressGatehouse_baked.glb').exists()
bpy.ops.wm.open_mainfile(filepath=str((source/'FortressGatehouse.blend').resolve()));scene=bpy.context.scene;assert scene.get('session_owner')=='veyr-fortress-20261103';obj=bpy.data.objects['FortressGatehouse'];mesh=obj.data
# Blender documents zero custom normals as automatic normals. Decimation had
# left source corner normals mapped onto a different reduced topology.
mesh.normals_split_custom_set([(0.,0.,0.)]*len(mesh.loops));mesh.update()
for other in scene.objects:other.select_set(False)
obj.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.ops.export_scene.gltf(filepath=str((out/'FortressGatehouse_baked.glb').resolve()),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
bounds=[obj.matrix_world@Vector(v) for v in obj.bound_box];lo=Vector(tuple(min(v[i] for v in bounds) for i in range(3)));hi=Vector(tuple(max(v[i] for v in bounds) for i in range(3)));center=(lo+hi)*.5;size=max(hi-lo);cam=scene.camera
for name,offset in [('front',(0,-3,.05)),('side',(3,0,.05)),('threequarter',(2.5,-3,1))]:
 cam.location=center+Vector(offset)*size;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();points=[cam.matrix_world.inverted()@v for v in bounds];cam.data.ortho_scale=max(max(v.x for v in points)-min(v.x for v in points),max(v.y for v in points)-min(v.y for v in points))*1.15;scene.render.filepath=str((out/(name+'.png')).resolve());bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str((out/'FortressGatehouse.blend').resolve()))
(out/'repair.json').write_text(json.dumps({'sourceBlend':str(source/'FortressGatehouse.blend'),'faces':len(mesh.polygons),'change':'Recomputed automatic corner normals on 150k reduced mesh. Geometry, UVs and material textures unchanged.','outputSHA256':hashlib.sha256((out/'FortressGatehouse_baked.glb').read_bytes()).hexdigest()},indent=2)+'\n');print('GATEHOUSE_NORMALS_REPAIRED',flush=True)
