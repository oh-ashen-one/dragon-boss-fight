"""Measure actual skinned glove proximity to the approved shaft and render close contact views."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
WEAPON=ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb'
g=GLB(WEAPON);positions=[]
for m in g.json['meshes']:
 for p in m['primitives']:positions.extend(g.accessor(p['attributes']['POSITION']).tolist())
shaft=[Vector(p) for p in positions if -.44<=p[1]<=.15]
tree=KDTree(len(shaft))
for i,v in enumerate(shaft):tree.insert(v,i)
tree.balance();records=[]
for variant in ['M','F']:
 name=f'Kevin_Heavy_{variant}_v4';bpy.ops.wm.open_mainfile(filepath=str(OUT/'Exports'/(name+'.blend')),load_ui=False)
 rig=bpy.data.objects['Knight_Comparison'];s=bpy.context.scene;body=[o for o in s.objects if o.type=='MESH' and not o.hide_render]
 groups={}
 for side in ['Left','Right']:
  groups[side]={o.name:[v.index for v in o.data.vertices if sum(w.weight for w in v.groups if o.vertex_groups[w.group].name.startswith(side+'Hand'))>.5] for o in body}
 samples=[]
 for frame in range(49):
  s.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();socket=rig.matrix_world@rig.pose.bones['WeaponSocket'].matrix;inverse=socket.inverted();distances={'Left':[],'Right':[]}
  for o in body:
   ev=o.evaluated_get(deps);mesh=ev.to_mesh();assert len(mesh.vertices)==len(o.data.vertices)
   for side in distances:
    for index in groups[side][o.name]:
     local=inverse@(ev.matrix_world@mesh.vertices[index].co)
     if -.48<=local.y<=.18:distances[side].append(tree.find(local)[2]*100)
   ev.to_mesh_clear()
  samples.append({'frame':frame,**{side:{'minimumCm':min(ds) if ds else None,'verticesWithin1Cm':sum(d<1 for d in ds),'testedVertices':len(ds)} for side,ds in distances.items()}})
 before=set(s.objects);bpy.ops.import_scene.gltf(filepath=str(WEAPON));imported=set(s.objects)-before
 attach=bpy.data.objects.new('Contact_Weapon',None);s.collection.objects.link(attach)
 for o in imported:
  if o.parent not in imported:
   matrix=o.matrix_world.copy();o.parent=attach;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Rotation(-math.pi/2,4,'X')@matrix
 con=attach.constraints.new('COPY_TRANSFORMS');con.target=rig;con.subtarget='WeaponSocket'
 camera=bpy.data.objects.new('ContactCamera',bpy.data.cameras.new('ContactCamera'));s.collection.objects.link(camera);s.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=.40
 s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='TEXTURE';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
 s.render.resolution_x=900;s.render.resolution_y=900;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='Standard';s.view_settings.exposure=.8
 folder=OUT/'Evidence'/(name+'_contacts');assert not folder.exists();folder.mkdir(parents=True)
 for frame in [0,12,24]:
  s.frame_set(frame);bpy.context.view_layer.update();socket=rig.matrix_world@rig.pose.bones['WeaponSocket'].matrix;focus=socket@Vector((0,-.15,0))
  for side,offset in [('front',Vector((.2,0,-1))),('back',Vector((-.2,0,1)))]:
   camera.location=focus+(socket.to_quaternion()@offset);camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(folder/f'{side}_{frame:04}.png');bpy.ops.render.render(write_still=True)
 records.append({'name':name,'shaftCoordinateUnits':'Original weapon metres, converted to native cm','metric':'Nearest shaft mesh vertex distance; proximity only, not a grasp/penetration or quality proof','samples':samples})
p=OUT/'mesh-contact-measurements.json';assert not p.exists();p.write_text(json.dumps(records,indent=2)+'\n');print('VEYR_MESH_CONTACTS_MEASURED')
