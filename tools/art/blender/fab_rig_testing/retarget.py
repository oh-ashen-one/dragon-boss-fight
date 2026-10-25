"""Blender-MCP-only anatomical rest-pose calibration and FK motion retarget test."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/FabRigTesting';OWNER='codex-veyr-fab-rig-testing'
TARGET=ROOT/'Local/CustomuseAssets/Polish20261025/knight/WalkOneHand_Blender_v2r2.glb'
MAIN={'Hips':'Spine','Spine':'Spine1','Spine1':'Spine2','Spine2':'Neck','Neck':'Head'}
for side in ('Left','Right'):
 MAIN.update({side+'Shoulder':side+'Arm',side+'Arm':side+'ForeArm',side+'ForeArm':side+'Hand',side+'Hand':side+'HandMiddle',side+'UpLeg':side+'Leg',side+'Leg':side+'Foot',side+'Foot':side+'ToeBase'})
UE={'Hips':'pelvis','Spine':'spine_01','Spine1':'spine_03','Spine2':'spine_05','Neck':'neck_01','Head':'head'}
for side,suffix in [('Left','l'),('Right','r')]:
 for a,b in [('Shoulder','clavicle'),('Arm','upperarm'),('ForeArm','lowerarm'),('Hand','hand'),('UpLeg','thigh'),('Leg','calf'),('Foot','foot'),('ToeBase','ball')]:UE[side+a]=b+'_'+suffix
 for finger in ('Index','Middle','Ring','Pinky','Thumb'):
  UE[side+'Hand'+finger]=finger.lower()+'_01_'+suffix

def source_name(n,kind):
 if kind=='fab':return UE.get(n)
 if 'Hand' in n and n not in ('LeftHand','RightHand'):return 'mixamorig:'+n+'1'
 return 'mixamorig:'+n

def reset():
 assert bpy.context.scene.get('session_owner')==OWNER
 for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 s=bpy.context.scene;s.render.fps=30;s.render.fps_base=1
 return s

def render(label,frames):
 s=bpy.context.scene
 # Attach the intact boat sword only for review; GLB retains the same socket.
 before=set(s.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb'))
 imported=set(s.objects)-before;attach=bpy.data.objects.new('Review_BoatSword',None);s.collection.objects.link(attach)
 for o in imported:
  if o.parent not in imported:
   m=o.matrix_world.copy();o.parent=attach;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Rotation(-math.pi/2,4,'X')@m
 con=attach.constraints.new('COPY_TRANSFORMS');con.target=bpy.data.objects['Knight_Comparison'];con.subtarget='WeaponSocket'

 cam=bpy.data.objects.new('ComparisonCamera',bpy.data.cameras.new('ComparisonCamera'));s.collection.objects.link(cam);s.camera=cam
 s.render.engine='BLENDER_WORKBENCH';sh=s.display.shading;sh.light='STUDIO';sh.color_type='TEXTURE';sh.show_shadows=True;sh.show_cavity=True;sh.background_type='WORLD'
 if not s.world:s.world=bpy.data.worlds.new('ReviewWorld')
 s.world.color=(.065,.07,.08);s.view_settings.view_transform='Standard';s.view_settings.exposure=.8
 s.render.resolution_x=640;s.render.resolution_y=640;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
 center=Vector((0,0,.5));folder=OUT/'Evidence'/label;folder.mkdir(parents=True,exist_ok=True)
 for v,off in {'front':(0,-3,.4),'side':(3,0,.4),'threequarter':(2,-3,.5)}.items():
  cam.location=center+Vector(off);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=2.1
  for f in frames:
   s.frame_set(f)
   hip=bpy.data.objects['Knight_Comparison'].pose.bones['Hips'].head;focus=Vector((hip.x,hip.y,.5));cam.location=focus+Vector(off);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler()
   s.render.filepath=str(folder/f'{v}_{f:04d}.png');bpy.ops.render.render(write_still=True)

def run(file,kind,name,travel=False):
 s=reset();bpy.ops.import_scene.gltf(filepath=str(TARGET));t=next(o for o in s.objects if o.type=='ARMATURE');t.name='Knight_Comparison'
 body=[o for o in s.objects if o.type=='MESH'];s.frame_set(0)
 grip=t.pose.bones['RightHand'].matrix.inverted()@t.pose.bones['WeaponSocket'].matrix
 t.animation_data_clear()
 for b in t.pose.bones:b.matrix_basis=Matrix.Identity(4);b.rotation_mode='QUATERNION'
 before=set(s.objects);bpy.ops.import_scene.fbx(filepath=str(file));src=next(o for o in set(s.objects)-before if o.type=='ARMATURE');src.name='Source_'+kind
 for o in set(s.objects)-before:
  o.hide_render=True
  if o.type=='MESH':o.hide_set(True)
 ad=src.animation_data;start,end=(round(x) for x in ad.action.frame_range);source_fps=s.render.fps/s.render.fps_base;N=end-start;s.frame_start=0;s.frame_end=N
 mapping={n:source_name(n,kind) for n in list(MAIN)+['Head','LeftToeBase','RightToeBase']};mapping={n:v for n,v in mapping.items() if v in src.data.bones}
 sw=src.matrix_world.copy();tw=t.matrix_world.copy();rest={n:(tw@b.matrix_local).copy() for n,b in t.data.bones.items()};sr={n:(sw@src.data.bones[v].matrix_local).copy() for n,v in mapping.items()}
 # Calibrate each segment's anatomical direction; imported glTF bone axes are
 # arbitrary and the knight's bind pose has relaxed arms instead of a T-pose.
 refs={}
 for n in mapping:
  correction=Quaternion((1,0,0,0))
  child=MAIN.get(n)
  if child and child in mapping:
   a=(rest[child].translation-rest[n].translation).normalized();b=(sr[child].translation-sr[n].translation).normalized();correction=a.rotation_difference(b)
  elif n.endswith('Hand'):
   child=source_name(n+'Middle',kind)
   if child in src.data.bones:
    a=(rest[n+'Middle'].translation-rest[n].translation).normalized();b=((sw@src.data.bones[child].head_local)-sr[n].translation).normalized();correction=a.rotation_difference(b)
  refs[n]=correction@rest[n].to_quaternion()
 scale=sum((rest[a].translation-rest[b].translation).length for a,b in [('LeftUpLeg','LeftLeg'),('LeftLeg','LeftFoot')])/sum((sr[a].translation-sr[b].translation).length for a,b in [('LeftUpLeg','LeftLeg'),('LeftLeg','LeftFoot')])
 samples={}
 for f in range(start,end+1):
  s.frame_set(f);samples[f-start]={n:(src.matrix_world@src.pose.bones[v].matrix).copy() for n,v in mapping.items()}
 first=samples[0]['Hips'].translation;last=samples[N]['Hips'].translation
 act=bpy.data.actions.new(name);t.animation_data_create();t.animation_data.action=act;previous={}
 for f in range(N+1):
  s.frame_set(f)
  for b in t.pose.bones:
   n=b.name
   if n not in mapping:continue
   desired=samples[f][n].to_quaternion()@sr[n].to_quaternion().inverted()@refs[n]
   pos=(t.matrix_world@b.head).copy()
   if n=='Hips':
    h=samples[f][n].translation;pos=rest[n].translation+Vector((h.x-first.x,h.y-first.y,h.z-sr[n].translation.z))*scale
    if not travel:pos.x-=(last.x-first.x)*scale*f/max(N,1);pos.y-=(last.y-first.y)*scale*f/max(N,1)
   b.matrix=tw.inverted()@Matrix.LocRotScale(pos,desired,Vector((1,1,1)));bpy.context.view_layer.update()
   q=b.rotation_quaternion.copy()
   if n in previous:q.make_compatible(previous[n])
   b.rotation_quaternion=q;previous[n]=q.copy()
   for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
  sock=t.pose.bones['WeaponSocket'];sock.matrix=t.pose.bones['RightHand'].matrix@grip;bpy.context.view_layer.update()
  for prop in ('location','rotation_quaternion','scale'):sock.keyframe_insert(prop,frame=f)
 for layer in act.layers:
  for st in layer.strips:
   for cb in st.channelbags:
    for fc in cb.fcurves:
     for k in fc.keyframe_points:k.interpolation='LINEAR'
 # The comparison carries the same blade from the hand socket; source shield
 # poses remain labeled as shield poses, not a fabricated two-hand guard.
 s.frame_set(0);src.hide_set(True)
 path=OUT/'Exports'/name;path.parent.mkdir(parents=True,exist_ok=True)
 for o in s.objects:o.select_set(False)
 t.select_set(True)
 for o in body:o.select_set(True)
 bpy.context.view_layer.objects.active=t
 bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 s['session_owner']=OWNER;s['retarget_source']=str(file);s['retarget_scale']=scale
 bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
 render(name,[0,N//4,N//2,3*N//4,N])
 report={'name':name,'source':str(file.relative_to(ROOT)),'provider':kind,'duration':N/source_fps,'fps':source_fps,'mappedBones':mapping,'scale':scale,'rootTravel':travel,'sha256':hashlib.sha256(path.with_suffix('.glb').read_bytes()).hexdigest()};path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
