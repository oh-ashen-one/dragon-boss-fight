from pathlib import Path
exec(compile((Path(__file__).parent/'common.py').read_text(),str(Path(__file__).parent/'common.py'),'exec'))
import importlib.util,shutil
RUN=SRC/'feedback-v4-20261021/tripo_r2/run_Blender_v1.blend'
IDLE1=SRC/'feedback-v4-20261021/er_v2r4/idle_one_Blender_v1.blend'
IDLE2=SRC/'feedback-v4-20261021/er_v2r4/idle_two_Blender_v1.blend'
def snapshot(path):
 open_scene(path);s=bpy.context.scene;s.frame_set(0);fk=bpy.data.objects['Pose_Control_Rig'];h=bpy.data.objects['Hilt_Control'];
 return {'swordMeshName':next(o.data.name for o in s.objects if o.get('review_attachment')),'ctrl':{n:bpy.data.objects[n].matrix_world.copy() for n in ['Hilt_Control','RightArm_Target','LeftArm_Target','RightArm_Pole','LeftArm_Pole','RightLeg_Target','LeftLeg_Target','RightLeg_Pole','LeftLeg_Pole']},'fk':{b.name:b.matrix_basis.copy() for b in fk.pose.bones},'fk_world':{b.name:fk.matrix_world@b.matrix.copy() for b in fk.pose.bones},'deform':{b.name:b.matrix_basis.copy() for b in bpy.data.objects['Knight_Deform'].pose.bones},'meshes':[(o.name,[list(r) for r in o.matrix_world],o.get('review_attachment'),o.get('export_body'),o.parent.name if o.parent else None,[(x.type,x.target.name if hasattr(x,'target') and x.target else None) for x in o.constraints]) for o in s.objects if o.type=='MESH']}
def audit_knight():
 for path in [IDLE1,IDLE2,RUN]:
  p=snapshot(path);print(path.name,str(path.parent));print('ctrl',json.dumps({k:[list(x) for x in v] for k,v in p['ctrl'].items()}));print('meshes',p['meshes'])
def core_module():
 path=ROOT/'tools/art/blender/rebuild/approved_actions.py';sp=importlib.util.spec_from_file_location('polish_core',path);c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c);c.OWNER=OWNER;return c

def export_knight(name,key,postprocess=None):
 s=bpy.context.scene;c=core_module();folder=OUT/name;folder.mkdir(parents=True,exist_ok=True);c.OUT=folder;job=s['rebuild_job'];c.JOBS[job]=(name,s['duration'],[0,s['duration']],bool(s.get('two_hand')))
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):c.bake()
 if postprocess:
  postprocess()
  with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
   bpy.ops.wm.save_as_mainfile(filepath=str(folder/(job+'_Blender_v1.blend')),compress=True)
   bpy.ops.export_scene.gltf(filepath=str(folder/(job+'_Blender_v1.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=name,export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 glb=OUT/(name+'.glb');blend=OUT/(name+'.blend');assert not glb.exists() and not blend.exists();shutil.copyfile(folder/(job+'_Blender_v1.glb'),glb);shutil.copyfile(folder/(job+'_Blender_v1.blend'),blend)
 report={'key':key,'file':str(glb),'blend':str(blend),'sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'duration':s['duration'],'fps':s.render.fps,'candidate':True,'bake':json.loads((folder/(job+'-report.json')).read_text())}
 (OUT/(name+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report));return report

def key_object(o,m,frame,prev):
 o.rotation_mode='QUATERNION';o.matrix_world=m
 q=o.rotation_quaternion.copy()
 if o.name in prev:q.make_compatible(prev[o.name])
 prev[o.name]=q.copy();o.rotation_quaternion=q
 for prop in ('location','rotation_quaternion','scale'):o.keyframe_insert(prop,frame=frame)

def render_knight(label,frames=(0,24,47,70,94),views=('front','side','threequarter'),close=False):
 s=bpy.context.scene;cam=s.camera
 for o in s.objects:
  if o.type=='MESH':
   visible=bool(o.get('export_body') or o.get('review_attachment'));o.hide_render=not visible;o.hide_set(not visible)
 if 'POLISH_REVIEW_FLOOR' not in bpy.data.objects:
  me=bpy.data.meshes.new('POLISH_REVIEW_FLOOR');me.from_pydata([(-10,-10,-.005),(10,-10,-.005),(10,10,-.005),(-10,10,-.005)],[],[(0,1,2,3)]);o=bpy.data.objects.new('POLISH_REVIEW_FLOOR',me);s.collection.objects.link(o);m=bpy.data.materials.new('POLISH_REVIEW_FLOOR');m.diffuse_color=(.25,.26,.28,1);me.materials.append(m)
 bpy.data.objects['POLISH_REVIEW_FLOOR'].hide_render=False;bpy.data.objects['POLISH_REVIEW_FLOOR'].hide_set(False)
 s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='TEXTURE';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.display.shading.background_type='WORLD';s.world.color=(.08,.08,.09);s.view_settings.view_transform='Standard';s.view_settings.exposure=.8
 s.render.resolution_x=640;s.render.resolution_y=640;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
 center=Vector((0,-.10,.8));viewpos={'front':Vector((0,-5,1)),'side':Vector((5,0,1)),'threequarter':Vector((3,-4,1.2))}
 folder=OUT/label;folder.mkdir(parents=True,exist_ok=True)
 for v in views:
  cam.location=center+viewpos[v];cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=2.5
  for i,f in enumerate(frames):
   s.frame_set(int(f),subframe=f-int(f))
   if close:
    rig=bpy.data.objects['Knight_Deform'];focus=(rig.pose.bones['LeftHand'].head+rig.pose.bones['RightHand'].head)*.5;focus=rig.matrix_world@focus
    cam.location=focus+viewpos[v];cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.62
   s.render.filepath=str(folder/(v+'_'+str(i).zfill(4)+'.png'));bpy.ops.render.render(write_still=True)
 return str(folder)

def replace_body(file):
 s=bpy.context.scene;rig=bpy.data.objects['Knight_Deform'];before=set(s.objects);properties=dict(s.items());settings=(s.frame_start,s.frame_end,s.render.fps,s.render.fps_base)
 for o in list(s.objects):
  if o.type=='MESH' and o.get('export_body'):bpy.data.objects.remove(o,do_unlink=True)
 before=set(s.objects)
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.import_scene.gltf(filepath=str(file))
 new=set(s.objects)-before
 for k,v in properties.items():s[k]=v
 s.frame_start,s.frame_end,s.render.fps,s.render.fps_base=settings
 for o in new:
  if o.type=='MESH':
   m=o.matrix_world.copy();o.parent=rig;o.matrix_world=m;o['export_body']=True
   for mod in o.modifiers:
    if mod.type=='ARMATURE':mod.object=rig
  else:bpy.data.objects.remove(o,do_unlink=True)

def use_sword(snapshot,path):
 if Path(bpy.data.filepath).resolve()==Path(path).resolve():return
 o=next(o for o in bpy.context.scene.objects if o.get('review_attachment'))
 with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.meshes=[snapshot['swordMeshName']]
 o.data=dst.meshes[0]

def author_run(name='RunTwoHand_Blender_polish_v1'):
 two=snapshot(IDLE2);one=snapshot(IDLE1);open_scene(RUN);s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];h=bpy.data.objects['Hilt_Control'];T=s.frame_end
 relative=two['fk_world']['Spine2'].inverted()@two['ctrl']['Hilt_Control']
 grip={side:two['ctrl']['Hilt_Control'].inverted()@two['ctrl'][side+'Arm_Target'] for side in ('Left','Right')}
 baseline={}
 for f in range(T+1):
  s.frame_set(f);baseline[f]=fk.matrix_world@fk.pose.bones['Spine2'].matrix.copy()
 for n in ['Hilt_Control','LeftArm_Target','RightArm_Target','LeftArm_Pole','RightArm_Pole']:
  o=bpy.data.objects[n];m=o.matrix_world.copy();o.animation_data_clear();o.constraints.clear();o.parent=None;o.matrix_world=m
 prev={}
 for f in range(T+1):
  s.frame_set(f);ch=baseline[f];H=ch@relative;H.translation+=Vector((0,-.07,-.015));q=Quaternion(Vector((1,0,0)),math.radians(18))@H.to_quaternion();H=Matrix.LocRotScale(H.translation,q,H.to_scale());key_object(h,H,f,prev)
  for side,sign in [('Left',1),('Right',-1)]:
   key_object(bpy.data.objects[side+'Arm_Target'],H@grip[side],f,prev)
   pole=two['fk_world']['Spine2'].inverted()@two['ctrl'][side+'Arm_Pole'];key_object(bpy.data.objects[side+'Arm_Pole'],ch@pole,f,prev)
  for b in fk.pose.bones:
   if 'Hand' in b.name and b.name not in ('LeftHand','RightHand'):
    b.matrix_basis=two['fk'][b.name]
    for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
 s['two_hand']=True;s['duration']=T/150.;s['polish_note']='Approved Tripo run lowerbody/timing; Blender IK two palms on hilt; no slower shuffle.'
 use_sword(one,IDLE1);s['sword_file']='BoatGreatsword_OneHand_v4.glb';replace_body(Path('/Users/midir/veyr-review-fable-20261021/tools/asset-review/.asset-cache/review/RunOneHand_Blender_tripo_r2.glb'))
 result=export_knight(name,'RunTwoHand');print(render_knight(name+'-review'));return result

def author_grip(to_two=True,name=None):
 name=name or ('GripToTwoHand' if to_two else 'GripToOneHand')+'_Blender_polish_v1'
 one=snapshot(IDLE1);two=snapshot(IDLE2);a,b=(one,two) if to_two else (two,one)
 open_scene(IDLE1 if to_two else IDLE2);s=bpy.context.scene;s.frame_start=0;s.frame_end=75;s.render.fps=150;s['duration']=.5;s['two_hand']=to_two;fk=bpy.data.objects['Pose_Control_Rig'];fk.animation_data_clear()
 # All controls are keyed in Blender; the hand visibly travels before contact.
 for n in a['ctrl']:
  o=bpy.data.objects[n];m=o.matrix_world.copy();o.animation_data_clear();o.constraints.clear();o.parent=None;o.matrix_world=m
 prev={}
 for f in range(76):
  t=f/75;u=t*t*(3-2*t);s.frame_set(f)
  for bone in fk.pose.bones:
   x,xq,xs=a['fk'][bone.name].decompose();y,yq,ys=b['fk'][bone.name].decompose();bone.matrix_basis=Matrix.LocRotScale(x.lerp(y,u),xq.slerp(yq,u),xs.lerp(ys,u))
   for prop in ('location','rotation_quaternion','scale'):bone.keyframe_insert(prop,frame=f)
  for n in a['ctrl']:
   x,xq,xs=a['ctrl'][n].decompose();y,yq,ys=b['ctrl'][n].decompose();pos=x.lerp(y,u)
   if n=='LeftArm_Target':pos+=Vector((.035,-.035,.025))*math.sin(math.pi*t) # clearance arc in front of cuirass
   key_object(bpy.data.objects[n],Matrix.LocRotScale(pos,xq.slerp(yq,u),xs.lerp(ys,u)),f,prev)
 # Right palm follows the carried hilt throughout; left reaches/relinquishes it.
 rg=a['ctrl']['Hilt_Control'].inverted()@a['ctrl']['RightArm_Target'];rg2=b['ctrl']['Hilt_Control'].inverted()@b['ctrl']['RightArm_Target']
 for f in range(76):
  s.frame_set(f);t=f/75;u=t*t*(3-2*t);x,xq,xs=rg.decompose();y,yq,ys=rg2.decompose();rel=Matrix.LocRotScale(x.lerp(y,u),xq.slerp(yq,u),xs.lerp(ys,u));key_object(bpy.data.objects['RightArm_Target'],bpy.data.objects['Hilt_Control'].matrix_world@rel,f,prev)
 use_sword(one,IDLE1);s['sword_file']='BoatGreatsword_OneHand_v4.glb'
 result=export_knight(name,'GripToTwoHand' if to_two else 'GripToOneHand');print(render_knight(name+'-review',(0,15,30,45,60,75)));return result

def author_roll(attack=False,name=None):
 name=name or ('RollAttack' if attack else 'Roll')+'_Blender_polish_v1';one=snapshot(IDLE1)
 source=SRC/'newclips-20261021/roll_attack/roll_attack_Blender_v1.blend';open_scene(source);s=bpy.context.scene;D=bpy.data.objects['Knight_Deform'];fk=bpy.data.objects['Pose_Control_Rig'];socket=bpy.data.objects['ReviewWeaponSocket'];h=bpy.data.objects['Hilt_Control'];T=330 if attack else 117
 original={};world={};sockets={}
 for f in range(T+1):
  s.frame_set(f);original[f]={b.name:b.matrix_basis.copy() for b in D.pose.bones};world[f]={b.name:D.matrix_world@b.matrix.copy() for b in D.pose.bones};sockets[f]=socket.matrix_world.copy()
 fk.animation_data_clear();fk.animation_data_create();fk.animation_data.action=bpy.data.actions.new(name+'_PreservedRollBodyReference')
 for f in range(T+1):
  for b in fk.pose.bones:
   b.matrix_basis=original[f][b.name]
   for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
 for n in ['Hilt_Control','RightArm_Target','RightArm_Pole']:
  o=bpy.data.objects[n];m=o.matrix_world.copy();o.animation_data_clear();o.constraints.clear();o.parent=None;o.matrix_world=m
 carry=one['fk_world']['Spine2'].inverted()@(Matrix.Translation(Vector((.10,-.08,.02)))@one['ctrl']['Hilt_Control'])
 grip=one['ctrl']['Hilt_Control'].inverted()@one['ctrl']['RightArm_Target'];prev={}
 for f in range(T+1):
  s.frame_set(f);ch=world[f]['Spine2']
  # The approved palm trajectory travels with the rolling body; the long boat
  # is stabilized forward rather than spearing the floor during torso inversion.
  palm=world[f]['RightHand'].translation.copy();palm.z=max(palm.z,.12)
  rightq=one['ctrl']['Hilt_Control'].to_quaternion()@grip.to_quaternion()
  Right=Matrix.LocRotScale(palm,rightq,world[f]['RightHand'].to_scale());H=Right@grip.inverted()
  if f>117:
   t=min(1,(f-117)/30);u=t*t*(3-2*t);a,aq,asc=H.decompose();b,bq,bsc=sockets[f].decompose();H=Matrix.LocRotScale(a.lerp(b,u),aq.slerp(bq,u),asc.lerp(bsc,u))
   a,aq,asc=Right.decompose();b,bq,bsc=world[f]['RightHand'].decompose();Right=Matrix.LocRotScale(a.lerp(b,u),aq.slerp(bq,u),asc.lerp(bsc,u))
  key_object(h,H,f,prev);key_object(bpy.data.objects['RightArm_Target'],Right,f,prev)
  a=world[f]['RightArm'].translation;b=world[f]['RightForeArm'].translation;c=world[f]['RightHand'].translation;axis=(c-a).normalized();direction=(b-a)-axis*(b-a).dot(axis)
  if direction.length<1e-5:direction=Vector((-.2,0,0))
  key_object(bpy.data.objects['RightArm_Pole'],Matrix.Translation(b+direction.normalized()*.25),f,prev)
 s.frame_end=T;s['duration']=T/150.;s['two_hand']=False;s['polish_note']='All non-right-arm body tracks restored exactly from praised roll prefix. Sword carried forward in chest frame by native right-arm IK.'
 replace_body(Path('/Users/midir/veyr-review-fable-20261021/tools/asset-review/.asset-cache/review/RollAttack_Blender_v1.glb'))
 def preserve_body():
  changed={'RightArm','RightForeArm','RightHand'}|{b.name for b in D.pose.bones['RightHand'].children_recursive}
  for f in range(T+1):
   s.frame_set(f)
   for b in D.pose.bones:
    if b.name in changed and f<147:continue
    b.matrix_basis=original[f][b.name]
    for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
  s.frame_set(0)
 result=export_knight(name,'RollAttack' if attack else 'Roll',preserve_body)
 print(render_knight(name+'-review',(0,24,47,70,94,117)+( (150,180,240,330) if attack else ())))
 return result
