"""Adapt the generated stone wall for paint on masonry, preserving its base UVs and relief."""
import bpy,json,hashlib
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];SOURCE=ROOT/'Local/Fortress20261103/Prepared/CurtainWall_v001/FortressCurtainWall.blend';OUT=ROOT/'Local/Fortress20261103/Prepared/PaintedWall_v001';OUT.mkdir(parents=True,exist_ok=True)
export=OUT/'FortressPaintedWall_baked.glb';assert not export.exists()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False);scene=bpy.context.scene;o=bpy.data.objects['FortressCurtainWall'];o.name='FortressPaintedWall';mesh=o.data
assert len(mesh.uv_layers)==1 and len(mesh.materials)==1
base=mesh.materials[0];paint_source=base.copy();paint_source.name='FortressStonePaintSurface';mesh.materials.append(paint_source)
# Entire masonry patch gets a second UV set. UV0 still drives original stone
# albedo/normal maps; UV1 drives the 2:1 painting and its distressed edge blend.
uv=mesh.uv_layers.new(name='MuralUV');vertices=np.empty((len(mesh.vertices),3),dtype=np.float32);mesh.vertices.foreach_get('co',vertices.ravel());loops=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',loops)
coords=vertices[loops][:,[0,2]];coords=(coords-np.array([-.34,.04],dtype=np.float32))/np.array([.68,.34],dtype=np.float32);uv.data.foreach_set('uv',coords.ravel());mesh.uv_layers.active_index=0;mesh.uv_layers[0].active_render=True
centers=np.empty((len(mesh.polygons),3),dtype=np.float32);normals=np.empty_like(centers);mesh.polygons.foreach_get('center',centers.ravel());mesh.polygons.foreach_get('normal',normals.ravel())
mask=(abs(centers[:,0])<.36)&(centers[:,2]>.025)&(centers[:,2]<.40)&(centers[:,1]>-.142)&(centers[:,1]<-.105)&(normals[:,1]<-.25)
assert mask.sum()>10000,'Generated wall front selection needs review';mesh.polygons.foreach_set('material_index',mask.astype(np.int32));mesh.update()
for obj in scene.objects:obj.select_set(False)
o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o
bpy.ops.export_scene.gltf(filepath=str(export),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_texcoords=True)
# The editable Blender file also contains an explicit material preview of the
# intended native blend; export above retains original stone PBR as a safe base.
preview=paint_source.copy();preview.name='PREVIEW_PaintOnStone';mesh.materials[1]=preview;nt=preview.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');original=bs.inputs['Base Color'].links[0].from_socket
uv_node=nt.nodes.new('ShaderNodeUVMap');uv_node.uv_map='MuralUV';sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(uv_node.outputs['UV'],sep.inputs[0])
def math_node(op,a=None,b=None,clamp=False):
 n=nt.nodes.new('ShaderNodeMath');n.operation=op;n.use_clamp=clamp
 for i,x in enumerate([a,b]):
  if x is None:continue
  if isinstance(x,(int,float)):n.inputs[i].default_value=x
  else:nt.links.new(x,n.inputs[i])
 return n.outputs[0]
u,v=sep.outputs['X'],sep.outputs['Y'];edge=math_node('MULTIPLY',math_node('MINIMUM',math_node('MINIMUM',u,math_node('SUBTRACT',1,u)),math_node('MINIMUM',v,math_node('SUBTRACT',1,v))),10,True)
bw=nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(original,bw.inputs[0]);coverage=math_node('ADD',math_node('MULTIPLY',bw.outputs[0],12),.35,True);alpha=math_node('MULTIPLY',math_node('MULTIPLY',edge,coverage),.85)
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'ArtSource/Fortress20261103/Murals/mural-01-siege.png'),check_existing=True);tex.extension='EXTEND';nt.links.new(uv_node.outputs['UV'],tex.inputs['Vector'])
mix=nt.nodes.new('ShaderNodeMixRGB');nt.links.new(alpha,mix.inputs[0]);nt.links.new(original,mix.inputs[1]);nt.links.new(tex.outputs['Color'],mix.inputs[2]);nt.links.new(mix.outputs[0],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.94;bs.inputs['Metallic'].default_value=0
for im in bpy.data.images:
 if im.source=='FILE' and not im.packed_file:im.pack()
from mathutils import Vector
bounds=[o.matrix_world@Vector(v) for v in o.bound_box];lo=Vector(tuple(min(v[i] for v in bounds) for i in range(3)));hi=Vector(tuple(max(v[i] for v in bounds) for i in range(3)));center=(lo+hi)*.5;size=max(hi-lo);cam=scene.camera
for label,offset in [('front',(0,-3,.05)),('threequarter',(1.5,-3,.4))]:
 cam.location=center+Vector(offset)*size;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();pts=[cam.matrix_world.inverted()@v for v in bounds];cam.data.ortho_scale=max(max(v.x for v in pts)-min(v.x for v in pts),max(v.y for v in pts)-min(v.y for v in pts))*1.15;scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'FortressPaintedWall.blend'))
(OUT/'prepare.json').write_text(json.dumps({'sourceBlendSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(export.read_bytes()).hexdigest(),'selectedFaces':int(mask.sum()),'uvChannels':2,'paintingAspectRatio':2,'paintUVSourceRectangle':[-.34,.34,.04,.38],'geometryChanged':False,'originalStoneUVsPreserved':True,'railExclusion':'Paint section limited to inset front masonry depth; projecting iron bands retain original material','previewOnly':True,'nativeQualityAccepted':False},indent=2)+'\n')
print('PAINTED_STONE_PREPARED',int(mask.sum()),flush=True)
