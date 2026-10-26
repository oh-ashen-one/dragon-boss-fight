"""Owned Blender MCP: weapon-aware IK refinement over the downloaded motion."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/FabRigTesting';OWNER='codex-veyr-fab-grip'
BASE=ROOT/'Local/CustomuseAssets/Polish20261025/knight'
_geo={'__file__':str(Path(__file__).with_name('clearance.py'))};exec(compile(Path(_geo['__file__']).read_text(),_geo['__file__'],'exec'),_geo)
_allpoints,_=_geo['glb_geometry'](ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb');SWORD_POINTS=_allpoints[::24]+[min(_allpoints,key=lambda v:v[i]) for i in range(3)]+[max(_allpoints,key=lambda v:v[i]) for i in range(3)]
def clear():
 assert bpy.context.scene.get('session_owner')==OWNER
 for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True)
def load(path,fps=30):
 clear();s=bpy.context.scene;s.render.fps=fps;s.render.fps_base=1;bpy.ops.import_scene.gltf(filepath=str(path));s['session_owner']=OWNER
 t=next(o for o in s.objects if o.type=='ARMATURE');t.name='Knight_Comparison';return t

def reference(file,end=False):
 t=load(BASE/file);s=bpy.context.scene;s.frame_set(round(t.animation_data.action.frame_range[1]) if end else 0);p=t.pose.bones;h=p['WeaponSocket'].matrix.copy();ch=p['Spine2'].matrix.copy()
 return {'h':h,'ch':ch,'carry':ch.inverted()@h,'g':{side:h.inverted()@p[side+'Hand'].matrix for side in ('Right','Left')},'left':ch.inverted()@p['LeftHand'].matrix,'handToFore':{side:p[side+'Hand'].matrix.inverted()@p[side+'ForeArm'].matrix for side in ('Right','Left')},'finger':{b.name:b.matrix_basis.copy() for b in p if 'Hand' in b.name and not b.name.endswith('Hand')}}
def roll_reference():
 t=load(BASE/'Roll_Blender_polish_v2.glb',25);s=bpy.context.scene;end=t.animation_data.action.frame_range[1];rows=[]
 for i in range(26):
  f=end*i/25;s.frame_set(int(f),subframe=f-int(f));p=t.pose.bones;rows.append({n:p[n].matrix.copy() for n in ('Hips','WeaponSocket','RightHand','LeftHand','RightForeArm','LeftForeArm')})
 return rows

def key_obj(o,m,f):
 o.rotation_mode='QUATERNION';o.matrix_world=m
 for prop in ('location','rotation_quaternion','scale'):o.keyframe_insert(prop,frame=f)
def empty(name):
 o=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(o);o.empty_display_size=.025;return o

def make_ik(t,source):
 s=bpy.context.scene;data=bpy.data.armatures.new('WeaponFit_AnatomicalIK');rig=bpy.data.objects.new('WeaponFit_AnatomicalIK',data);s.collection.objects.link(rig)
 
 for o in s.objects:o.select_set(False)
 bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
 for side in ('Right','Left'):
  a=t.data.bones[side+'Arm'];b=t.data.bones[side+'ForeArm'];h=t.data.bones[side+'Hand']
  u=data.edit_bones.new(side+'_Upper');u.head=a.head_local;u.tail=b.head_local
  l=data.edit_bones.new(side+'_Lower');l.head=b.head_local;l.tail=h.head_local;l.parent=u;l.use_connect=True
  for suffix,parent,orig in [('Arm',u,a),('ForeArm',l,b)]:
   proxy=data.edit_bones.new(side+'_Copy'+suffix);proxy.length=.035;proxy.matrix=orig.matrix_local;proxy.parent=parent;proxy.use_connect=False
 bpy.ops.object.mode_set(mode='OBJECT');targets={}
 for side in ('Right','Left'):
  for suffix in ('Arm','ForeArm'):
   a=data.bones[side+'_Copy'+suffix].matrix_local;b=t.data.bones[side+suffix].matrix_local
   assert max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4))<1e-5,'Proxy rest orientation changed'
 for side in ('Right','Left'):
  hand=empty(side+'_PalmTarget');pole=empty(side+'_ElbowPole');targets[side]=(hand,pole)
  ik=rig.pose.bones[side+'_Lower'].constraints.new('IK');ik.target=hand;ik.pole_target=pole;ik.chain_count=2;ik.use_stretch=False;ik.iterations=128
  for suffix in ('Arm','ForeArm'):
   con=t.pose.bones[side+suffix].constraints.new('COPY_TRANSFORMS');con.target=rig;con.subtarget=side+'_Copy'+suffix;con.target_space='WORLD';con.owner_space='WORLD'
  con=t.pose.bones[side+'Hand'].constraints.new('COPY_ROTATION');con.target=hand;con.target_space='WORLD';con.owner_space='WORLD'
 return rig,targets

def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
def mixmat(a,b,w):
 x,q,sc=a.decompose();y,r,ss=b.decompose();return Matrix.LocRotScale(x.lerp(y,w),q.slerp(r,w),sc.lerp(ss,w))
def fit(kind,refs,version='v2',grip_override=None,output_name=None):
 names={'walk':'Mixamo_Walk','attack':'Mixamo_Attack','guard':'Mixamo_Block','run':'Fab_Run','roll':'Fab_Roll'};name=output_name or names[kind]+'_'+version;two_hand=(kind in ('run','guard')) if grip_override is None else grip_override=='two'
 meta=json.loads((OUT/'Exports'/(names[kind]+'_v1.json')).read_text());t=load(OUT/'Exports'/(names[kind]+'_v1.glb'),int(meta['fps']));s=bpy.context.scene;N=round(meta['duration']*meta['fps']);s.frame_start=0;s.frame_end=N;p=t.pose.bones
 body=[o for o in s.objects if o.type=='MESH'];source={}
 for f in range(N+1):s.frame_set(f);source[f]={b.name:b.matrix.copy() for b in p}
 original=t.animation_data.action;original.use_fake_user=True;t.animation_data.action=original.copy();t.animation_data.action.name=name+'_SourceMotionAndGrip'
 ref=refs['guard'] if kind=='guard' else refs['two'] if two_hand else refs['one'];grip={side:m.copy() for side,m in ref['g'].items()};hscale=ref['h'].to_scale()
 if kind=='attack':grip['Right'].translation.y=-.10
 if kind=='roll':grip['Right']=refs['roll'][0]['WeaponSocket'].inverted()@refs['roll'][0]['RightHand'];grip['Right'].translation.y-=.04
 if two_hand:grip['Right'].translation.y=-.04;grip['Left'].translation.y=-.39
 rig,targets=make_ik(t,source)
 if kind=='run' and not two_hand:
  for suffix in ('Arm','ForeArm','Hand'):
   for con in list(p['Left'+suffix].constraints):p['Left'+suffix].constraints.remove(con)
 hilt=empty('Weapon_Hilt_Control');socket=p['WeaponSocket'];con=socket.constraints.new('COPY_TRANSFORMS');con.target=hilt;con.owner_space='WORLD';con.target_space='WORLD'
 desired={};reach=[]
 for f in range(N+1):
  src=source[f];ch=src['Spine2'];u=f/max(N,1);wave=math.sin(2*math.pi*u)
  if kind in ('walk','run'):H=ch@(refs['two']['carry'] if kind=='run' else ref['carry']);H.translation+=Vector((0,0,.006*wave))
  elif kind=='guard':H=mixmat(ch@refs['two']['carry'],ch@refs['guard']['carry'],smooth(u/.50))
  elif kind=='attack':
   # Source footwork, chest rotation and cadence drive a fitted heavy-blade arc.
   # The original short-sword wrist roll is unsuitable for this broad weapon.
   keys=[(0,.17,.18,.02,(.10,.35,.94)),(.22,.18,.18,.12,(.28,.35,.90)),(.43,.09,.24,-.12,(-.20,.96,-.10)),(.62,.04,.25,-.08,(-.50,.85,.15)),(.85,.16,.20,.02,(.10,.35,.94)),(1,.17,.18,.02,(.10,.35,.94))]
   aa,bb=next((a,b) for a,b in zip(keys,keys[1:]) if a[0]<=u<=b[0]);w=smooth((u-aa[0])/(bb[0]-aa[0]));offset=Vector(aa[1:4]).lerp(Vector(bb[1:4]),w);aimlocal=Vector(aa[4]).lerp(Vector(bb[4]),w).normalized()
   delta=ch.to_quaternion()@refs['one']['ch'].to_quaternion().inverted();front=delta@Vector((0,-1,0));front.z=0;front.normalize();right=Vector((front.y,-front.x,0));up=Vector((0,0,1));wrist=ch.translation+right*offset.x+front*offset.y+up*offset.z
   aim=(right*aimlocal.x+front*aimlocal.y+up*aimlocal.z).normalized();q=refs['one']['h'].to_quaternion();q=(q@Vector((0,1,0))).rotation_difference(aim)@q;H=Matrix.LocRotScale(wrist,q,hscale);H.translation-=H.to_3x3()@grip['Right'].translation
  else:
   rr=refs['roll'][round(u*25)];offset=src['Hips'].translation-rr['Hips'].translation+Vector((-.10,0,0));H=rr['WeaponSocket'].copy();H.translation+=offset;H.translation+=H.to_3x3()@Vector((0,.04,0))
  if kind=='roll':
   wrist=(H@grip['Right']).translation;q=Quaternion(Vector((0,0,1)),math.radians(-25*smooth((u-.30)/.12)*(1-smooth((u-.56)/.08))))@H.to_quaternion();H=Matrix.LocRotScale(wrist,q,hscale);H.translation-=H.to_3x3()@grip['Right'].translation
  # Move the rear shaft clear of the cuirass; supporting palm remains lower.
  if two_hand or kind=='run':
   front=(ch.to_quaternion()@ref['ch'].to_quaternion().inverted())@Vector((0,-1,0));front.z=0;front.normalize();H.translation+=front*.10
  if two_hand or kind=='run':
   blade=H.to_quaternion()@Vector((0,1,0))
   if blade.z<.72:
    horizontal=Vector((blade.x,blade.y,0)).normalized();aim=horizontal*math.sqrt(1-.72**2)+Vector((0,0,.72));H=Matrix.LocRotScale(H.translation,blade.rotation_difference(aim)@H.to_quaternion(),hscale)
  # Keep the blade above the ground in upright carries without changing scale.
  if kind in ('walk','run'):
   blade=H.to_quaternion()@Vector((0,1,0))
   if blade.z<.08:
    target=Vector((blade.x,blade.y,.12)).normalized();H=Matrix.LocRotScale(H.translation,blade.rotation_difference(target)@H.to_quaternion(),hscale)
  # Solve ground clearance around the gripping palm, preserving blade scale.
  corners=SWORD_POINTS
  if min((H@v).z for v in corners)<.055:
   wrist=(H@grip['Right']).translation;oldq=H.to_quaternion();blade=oldq@Vector((0,1,0));dq=blade.rotation_difference(Vector((0,0,1)))
   for step in range(1,81):
    q=Quaternion((1,0,0,0)).slerp(dq,step/80)@oldq;trial=Matrix.LocRotScale(wrist,q,hscale);trial.translation-=trial.to_3x3()@grip['Right'].translation
    if min((trial@v).z for v in corners)>=.055:H=trial;break
  # Both grips must be reachable. Translate the hilt toward the shoulder for
  # small differences in proportions, never stretch the knight's arms.
  sides=('Right','Left') if two_hand else ('Right',)
  for _ in range(5):
   for side in sides:
    shoulder=src[side+'Arm'].translation;a=t.data.bones[side+'Arm'].head_local;b=t.data.bones[side+'ForeArm'].head_local;c=t.data.bones[side+'Hand'].head_local;limit=((a-b).length+(b-c).length)*.965
    wrist=(H@grip[side]).translation;delta=wrist-shoulder
    if delta.length>limit:H.translation-=delta.normalized()*(delta.length-limit)
  desired[f]={'H':H}
  for side,sign in [('Right',-1),('Left',1)]:
   if side in sides:hand=H@grip[side]
   elif kind=='run':hand=src['LeftHand'].copy()
   elif kind=='roll':
    rr=refs['roll'][round(u*25)];hand=rr['LeftHand'].copy();hand.translation+=src['Hips'].translation-rr['Hips'].translation
   else:
    hand=ch@refs['one']['left'];hand.translation+=Vector((.06,-.015*wave,-.045))
   shoulder=src[side+'Arm'].translation;a=t.data.bones[side+'Arm'].head_local;b=t.data.bones[side+'ForeArm'].head_local;c=t.data.bones[side+'Hand'].head_local;limit=((a-b).length+(b-c).length)*.97
   if side not in sides and (hand.translation-shoulder).length>limit:hand.translation=shoulder+(hand.translation-shoulder).normalized()*limit
   desired[f][side]=hand
 # Parallel transport the wide boat's frame through the source slash. The
 # source wrist roll is not allowed to flip the hull around its long axis.
 if kind=='attack':
  previous=None
  for f in range(N+1):
   H=desired[f]['H'];blade=H.to_quaternion()@Vector((0,1,0));q=H.to_quaternion() if previous is None else (previous@Vector((0,1,0))).rotation_difference(blade)@previous
   q.normalize()
   if previous is not None:q.make_compatible(previous)
   previous=q.copy();wrist=desired[f]['Right'].translation;H=Matrix.LocRotScale(wrist,q,hscale);H.translation-=H.to_3x3()@grip['Right'].translation
   low=min((H@v).z for v in SWORD_POINTS)
   if low<.06:H.translation.z+=.06-low
   desired[f]['H']=H;desired[f]['Right']=H@grip['Right']
 # Dense Blender controller keys preserve the source body's original timing.
 for f in range(N+1):
  s.frame_set(f);src=source[f];key_obj(hilt,desired[f]['H'],f)
  for side,sign in [('Right',-1),('Left',1)]:
   hand,pole=targets[side];key_obj(hand,desired[f][side],f)
   shoulder=src[side+'Arm'].translation;upper=rig.pose.bones[side+'_Upper'];rest=rig.data.bones[side+'_Upper'].matrix_local;upper.matrix=Matrix.LocRotScale(shoulder,rest.to_quaternion(),Vector((1,1,1)));upper.keyframe_insert('location',frame=f)
   axis=desired[f]['H'].to_quaternion()@Vector((0,1,0));origin=desired[f]['H'].translation;radial=hand.location-origin-axis*(hand.location-origin).dot(axis)
   if kind=='roll':
    rr=refs['roll'][round(f/max(N,1)*25)];elbow=rr[side+'ForeArm'].translation+src['Hips'].translation-rr['Hips'].translation;pole.location=shoulder+(elbow-shoulder)*3
    if side=='Right':pole.location.y+=.25*(1-smooth(f/max(N,1)/.2))
   elif side=='Right' or two_hand:pole.location=hand.location+radial.normalized()*.35
   else:pole.location=shoulder+Vector((sign*.25,.025,-.08))
   pole.keyframe_insert('location',frame=f)
  for n,m in ref['finger'].items():
   if n in p:p[n].matrix_basis=m
   for prop in ('location','rotation_quaternion','scale'):p[n].keyframe_insert(prop,frame=f)
 s.frame_set(0)
 for side,sign in [('Right',-1),('Left',1)]:
  ik=rig.pose.bones[side+'_Lower'].constraints[0];sh=source[0][side+'Arm'].translation;goal=targets[side][1].location;best=None
  for deg in range(-180,181,5):
   ik.pole_angle=math.radians(deg);bpy.context.view_layer.update();score=(rig.pose.bones[side+'_Lower'].head-goal).length
   if best is None or score<best[0]:best=(score,ik.pole_angle)
  ik.pole_angle=best[1]
 # Palm targets are actual children of the hilt, so contact is exact between keys.
 for side in (('Right','Left') if two_hand else ('Right',)):
  target=targets[side][0];target.animation_data_clear();target.parent=hilt;target.matrix_parent_inverse=Matrix.Identity(4);target.matrix_basis=grip[side]
 if kind=='attack':
  lower=rig.pose.bones['Right_Lower'];proxy=rig.pose.bones['Right_CopyForeArm'];proxy.rotation_mode='QUATERNION';last_q=None;last_upper=None
  for f in range(N+1):
   s.frame_set(f);bpy.context.view_layer.update();base=lower.matrix@lower.bone.matrix_local.inverted()@t.data.bones['RightForeArm'].matrix_local;axis=(lower.tail-lower.head).normalized();wanted=targets['Right'][0].matrix_world.to_quaternion()@ref['handToFore']['Right'].to_quaternion();cosine=0;sine=0
   for local in (Vector((0,1,0)),Vector((0,0,1))):
    a=base.to_quaternion()@local;b=wanted@local;a-=axis*a.dot(axis);b-=axis*b.dot(axis);cosine+=a.dot(b);sine+=axis.dot(a.cross(b))
   twist=math.atan2(sine,cosine);proxy.matrix=Matrix.LocRotScale(base.translation,Quaternion(axis,twist)@base.to_quaternion(),base.to_scale());q=proxy.rotation_quaternion.copy()
   if last_q is not None:q.make_compatible(last_q)
   proxy.rotation_quaternion=q;last_q=q.copy();proxy.keyframe_insert('rotation_quaternion',frame=f)
   upper=rig.pose.bones['Right_Upper'];up=rig.pose.bones['Right_CopyArm'];up.rotation_mode='QUATERNION';ubase=upper.matrix@upper.bone.matrix_local.inverted()@t.data.bones['RightArm'].matrix_local;uaxis=(upper.tail-upper.head).normalized();up.matrix=Matrix.LocRotScale(ubase.translation,Quaternion(uaxis,twist*.30)@ubase.to_quaternion(),ubase.to_scale());uq=up.rotation_quaternion.copy()
   if last_upper is not None:uq.make_compatible(last_upper)
   up.rotation_quaternion=uq;last_upper=uq.copy();up.keyframe_insert('rotation_quaternion',frame=f)
 if kind=='roll':
  lower=rig.pose.bones['Right_Lower'];proxy=rig.pose.bones['Right_CopyForeArm'];proxy.rotation_mode='QUATERNION'
  for f in range(N+1):
   s.frame_set(f);bpy.context.view_layer.update();base=lower.matrix@lower.bone.matrix_local.inverted()@t.data.bones['RightForeArm'].matrix_local;axis=(lower.tail-lower.head).normalized();proxy.matrix=Matrix.LocRotScale(base.translation,Quaternion(axis,math.radians(20))@base.to_quaternion(),base.to_scale());proxy.keyframe_insert('rotation_quaternion',frame=f)
 for f in range(N+1):
  s.frame_set(f);bpy.context.view_layer.update();reach.append({side:(p[side+'Hand'].head-targets[side][0].matrix_world.translation).length for side in ('Right','Left')})
 # Bake denser samples to preserve grip during fast arcs between source frames.
 source_fps=s.render.fps;factor=4;actions=set()
 for o in s.objects:
  if o.animation_data and o.animation_data.action:actions.add(o.animation_data.action)
 for act in actions:
  curves=[fc for layer in act.layers for strip in layer.strips for cb in strip.channelbags for fc in cb.fcurves]
  quaternion_groups={}
  for fc in curves:
   if fc.data_path.endswith('rotation_quaternion'):quaternion_groups.setdefault(fc.data_path,{})[fc.array_index]=fc
  for path,group in quaternion_groups.items():
   if set(group)!={0,1,2,3}:continue
   points={i:sorted(list(fc.keyframe_points),key=lambda p:p.co.x) for i,fc in group.items()}
   if len({len(p) for p in points.values()})!=1:raise RuntimeError('Unaligned quaternion channels: '+path)
   previous=None
   for i in range(len(points[0])):
    q=Quaternion(tuple(points[c][i].co.y for c in range(4)))
    if previous is not None and q.dot(previous)<0:
     for c in range(4):points[c][i].co.y*=-1;points[c][i].handle_left.y*=-1;points[c][i].handle_right.y*=-1
     q.negate()
    previous=q
  for fc in curves:
   # Descending order avoids reordering live keyframe collections mid-retime.
   for kp in sorted(list(fc.keyframe_points),key=lambda p:p.co.x,reverse=True):
    kp.co.x*=factor;kp.interpolation='LINEAR'
   fc.update()
 s.render.fps=source_fps*factor;N*=factor;s.frame_end=N
 # Bake the solved arm constraints to the delivered rig; controllers stay editable.
 for o in s.objects:o.select_set(False)
 t.select_set(True);bpy.context.view_layer.objects.active=t;bpy.ops.object.mode_set(mode='POSE')
 bpy.ops.nla.bake(frame_start=0,frame_end=N,step=1,only_selected=False,visual_keying=True,clear_constraints=False,clear_parents=False,use_current_action=False,clean_curves=False,bake_types={'POSE'},channel_types={'LOCATION','ROTATION','SCALE'})
 bpy.ops.object.mode_set(mode='OBJECT');t.animation_data.action.name=name
 mutes=[c for b in p for c in b.constraints]
 for c in mutes:c.mute=True
 for o in s.objects:o.select_set(False)
 t.select_set(True)
 for o in body:o.select_set(True)
 path=OUT/'Exports'/name
 assert not path.with_suffix('.glb').exists(),name
 bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 for c in mutes:c.mute=False
 s.frame_set(0);s['session_owner']=OWNER;s['weapon_fit']='Native Blender two-bone IK; approved palm/finger grip references; source lowerbody preserved'
 bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
 meta.update({'name':name,'sourceFPS':source_fps,'fps':s.render.fps,'bakeSampleRate':s.render.fps,'sha256':hashlib.sha256(path.with_suffix('.glb').read_bytes()).hexdigest(),'weaponAdapted':True,'gripMode':'two-handed' if two_hand else 'one-handed','maxPalmTargetError':{side:max(r[side] for r in reach) for side in ('Right','Left')}});path.with_suffix('.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))

def run(kinds=('walk','run','guard','roll','attack'),version='v2',grip_override=None,output_name=None):
 refs={'one':reference('WalkOneHand_Blender_v2r2.glb'),'two':reference('RunTwoHand_Blender_polish_v2.glb'),'guard':reference('GuardReadyTwoHand_Blender_v4r4.glb',True)}
 if 'roll' in kinds:refs['roll']=roll_reference()
 for kind in kinds:fit(kind,refs,version,grip_override,output_name)
