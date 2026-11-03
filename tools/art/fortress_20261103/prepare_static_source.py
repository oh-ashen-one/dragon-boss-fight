"""Bake imported transforms without destructive offline reduction; render source views for native LOD import."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:]
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--name',required=True);a=p.parse_args(args)
a.output.mkdir(parents=True,exist_ok=True)
assert not (a.output/(a.name+'_baked.glb')).exists(),'Preserve previous version'
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene['session_owner']='veyr-fortress-20261103'
bpy.ops.import_scene.gltf(filepath=str(a.source.resolve()))
meshes=[o for o in scene.objects if o.type=='MESH'];assert len(meshes)==1
raw=meshes[0];raw.name='SOURCE_'+a.name;bpy.context.view_layer.objects.active=raw;raw.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
raw.data.calc_loop_triangles();original_triangles=len(raw.data.loop_triangles)
working=raw.copy();working.data=raw.data.copy();scene.collection.objects.link(working);working.name=a.name
raw.hide_render=True;raw.hide_set(True);raw.select_set(False);working.select_set(True);bpy.context.view_layer.objects.active=working
working.data.calc_loop_triangles();triangles=len(working.data.loop_triangles)
for image in bpy.data.images:
 if image.source=='FILE' and not image.packed_file:image.pack()
bounds=[working.matrix_world@Vector(v) for v in working.bound_box];lo=Vector(tuple(min(v[i] for v in bounds) for i in range(3)));hi=Vector(tuple(max(v[i] for v in bounds) for i in range(3)));center=(lo+hi)*.5;size=max(hi-lo)
# A true open lower gateway is required. Probe mesh only before adding review scenery.
origin=Vector((center.x,lo.y-size,lo.z+(hi.z-lo.z)*.2));hit=working.ray_cast(working.matrix_world.inverted()@origin,Vector((0,1,0)))[0]
report={'sourceSHA256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'sourceTriangles':original_triangles,'gameTriangles':triangles,'vertices':len(working.data.vertices),'boundsBlenderMeters':[list(lo),list(hi)],'lowerCentralRayClear':not hit,'materialSlots':len(working.data.materials),'textures':[{'name':i.name,'size':list(i.size),'packed':bool(i.packed_file)} for i in bpy.data.images if i.type=='IMAGE'],'changes':'Applied existing node transform only. Full source topology, UVs, corner normals and embedded textures retained. Reduction deferred to Unreal.'}
# Solid walls are expected; the central ray is diagnostic only.
for o in scene.objects:o.select_set(False)
working.select_set(True);bpy.context.view_layer.objects.active=working
bpy.ops.export_scene.gltf(filepath=str((a.output/(a.name+'_baked.glb')).resolve()),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
world=bpy.data.worlds.new('ReviewWorld');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.28,.32,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4;scene.world=world
for name,offset,power,color in [('Key',(-1,-1.5,1.5),1400,(1,.93,.85)),('Fill',(1.3,-.4,.6),700,(.8,.88,1)),('Rim',(.3,1.2,1.4),1500,(1,1,1))]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power*size*size;data.shape='DISK';data.size=size
 obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=center+Vector(offset)*size;obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));scene.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.clip_end=size*100;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8
scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-3
views=[]
for name,offset in [('front',(0,-3,.05)),('side',(3,0,.05)),('threequarter',(2.5,-3,1))]:
 cam.location=center+Vector(offset)*size;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();points=[cam.matrix_world.inverted()@v for v in bounds];cam.data.ortho_scale=max(max(v.x for v in points)-min(v.x for v in points),max(v.y for v in points)-min(v.y for v in points))*1.15
 path=a.output/(name+'.png');scene.render.filepath=str(path.resolve());bpy.ops.render.render(write_still=True);views.append(str(path))
report['views']=views;report['outputSHA256']=hashlib.sha256((a.output/(a.name+'_baked.glb')).read_bytes()).hexdigest();(a.output/'prepare.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str((a.output/(a.name+'.blend')).resolve()))
print('FORTRESS_SOURCE_PREPARED',triangles,flush=True)
