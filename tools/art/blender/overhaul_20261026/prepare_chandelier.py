import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Overhaul20261026/architecture';OWNER='codex-veyr-overhaul-20261026'
assert bpy.context.scene.get('session_owner')==OWNER
for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(OUT/'Chandelier_Fab_Source.glb'))
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH');world=mesh.matrix_world.copy();mesh.parent=None;mesh.matrix_world=world
for o in bpy.context.scene.objects:o.select_set(o==mesh)
bpy.context.view_layer.objects.active=mesh;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
lo=Vector([min(v.co[i] for v in mesh.data.vertices) for i in range(3)]);hi=Vector([max(v.co[i] for v in mesh.data.vertices) for i in range(3)])
scale=4.0/max(hi.x-lo.x,hi.y-lo.y)
for v in mesh.data.vertices:v.co=(v.co-Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z)))*scale
before=sum(len(p.vertices)-2 for p in mesh.data.polygons)
if before>50000:
 mod=mesh.modifiers.new('MeasuredGameBudget','DECIMATE');mod.ratio=50000/before;bpy.ops.object.modifier_apply(modifier=mod.name)
for im in bpy.data.images:
 if im.size[0]>2048 or im.size[1]>2048:
  factor=2048/max(im.size);im.scale(round(im.size[0]*factor),round(im.size[1]*factor))
mesh.name='Chandelier';file=OUT/'Chandelier_Normalized.glb'
bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_animations=False,export_cameras=False,export_lights=False,export_image_format='AUTO')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Chandelier_Adapted.blend'),compress=True)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.display.shading.color_type='TEXTURE';s.display.shading.light='STUDIO';s.view_settings.view_transform='Standard';s.view_settings.exposure=.5
cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));s.collection.objects.link(cam);s.camera=cam
bounds=[mesh.matrix_world@Vector(x) for x in mesh.bound_box];center=sum(bounds,Vector())/8;cam.location=center+Vector((7,-8,-1));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=7
s.render.resolution_x=720;s.render.resolution_y=720;s.render.resolution_percentage=100;s.render.filepath=str(OUT/'chandelier-review.png');bpy.ops.render.render(write_still=True)
report={'source':'https://www.fab.com/listings/8205433d-52b5-40ae-add1-577e769655f5','creator':'Mikhail Kadilnikov','license':'CC BY 4.0','licenseURL':'https://creativecommons.org/licenses/by/4.0/','modifications':'Applied transforms, normalized to4m diameter, reduced to50k triangles if needed, textures resized at most2K in Blender MCP','trianglesBefore':before,'trianglesAfter':sum(len(p.vertices)-2 for p in mesh.data.polygons),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()};(OUT/'manifest.json').write_text(json.dumps(report,indent=2));print(report)
