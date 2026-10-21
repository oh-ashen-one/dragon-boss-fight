"""Owner feedback v3. Execute only inside the owned Blender MCP session.
Native FK/IK authoring; approved walk and heal arm action are immutable references.
"""
from pathlib import Path
import bpy,importlib.util,math,json,hashlib
from mathutils import Vector,Matrix,Quaternion
REPO=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('feedback2',REPO/'tools/art/blender/feedback/feedback_actions.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
c=f.c;c.OUT=REPO/'Local/Blender/feedback-v3-20261021';c.OWNER='codex-veyr-feedback-v3-20261021'
f.NAMES={j:n.replace('_v2','_v3') for j,n in f.NAMES.items()}
f.DUR.update(guard_two=.7,strafe_left=.7,strafe_right=.7)
f.TIMES['guard_two']=[0,.08,.14,.22,.3,.4,.7]
for j in ('strafe_left','strafe_right'):f.TIMES[j]=[0,.06,.12,.18,.28,.34,.4,.5,.7]
for j in f.DUR:
 source='HeavyAttackOneHand_Blender_v1' if j=='heavy' else 'IdleTwoHand_ReadyBreath_v6' if j=='guard_two' else 'IdleOneHand_Breathing_v3'
 c.JOBS[j]=(source,f.DUR[j],f.TIMES[j],j=='guard_two')


def world_rotate(b,axis,degrees):
 m=b.matrix.copy();b.matrix=Matrix.Translation(m.translation)@Matrix.Rotation(math.radians(degrees),4,axis)@m.to_3x3().to_4x4();bpy.context.view_layer.update()


def free_arm():
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];c.at(0)
 bases={b.name:b.matrix_basis.copy() for b in fk.pose.bones};start=fk.pose.bones['LeftHand'].matrix.copy();target=bpy.data.objects['LeftArm_Target'];pole=bpy.data.objects['LeftArm_Pole'];f.reset_animation(target);f.reset_animation(pole);p0=f.rest_arm_pole(fk,'Left')
 # The free hand counterbalances OUTSIDE and BEHIND the left shoulder. Never reaches for hilt.
 for t in f.TIMES['heavy']:
  c.at(t*s.render.fps)
  for name in ('LeftShoulder','LeftArm','LeftForeArm','LeftHand'):
   fk.pose.bones[name].matrix_basis=bases[name];c.key(fk.pose.bones[name],t*s.render.fps,{})
  bpy.context.view_layer.update();shoulder=fk.pose.bones['LeftArm'].matrix.translation.copy()
  phase=min(1.,t/.22,(f.DUR['heavy']-t)/.25);phase=max(0,phase)
  m=start.copy();m.translation=start.translation.lerp(shoulder+Vector((.14,.18,-.09)),phase)
  f.key_matrix(target,t,m);f.key_vector(pole,t,p0.lerp(shoulder+Vector((.24,.20,-.12)),phase))
 for o in bpy.data.collections['AUTHORING_heavy'].objects:c.smooth(o)


def ready_backpedal():
 f.idle_based_movement('backpedal')
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];snap=[]
 for t in f.TIMES['backpedal']:
  c.at(t*s.render.fps);snap.append((t,{b.name:b.matrix_basis.copy() for b in fk.pose.bones}))
 fk.animation_data_clear()
 for t,bases in snap:
  u=t/f.DUR['backpedal'];active=min(1,t/.3,(2.4-t)/.35);active=max(0,active);beat=math.sin(t/0.8*math.tau)
  f.set_fk_pose(fk,t,bases,Vector((.016*beat*active,0,-.006*active)))
  world_rotate(fk.pose.bones['Spine'],'X',5*active)
  world_rotate(fk.pose.bones['Spine2'],'Z',6*beat*active)
  world_rotate(fk.pose.bones['Spine2'],'Y',2.5*beat*active)
  world_rotate(fk.pose.bones['Head'],'Z',-4*beat*active)
  for side in ('Right','Left'):
   world_rotate(fk.pose.bones[side+'Arm'],'X',(-12 if side=='Right' else -10)*active)
   world_rotate(fk.pose.bones[side+'ForeArm'],'X',(-30 if side=='Right' else -36)*active)
  for b in fk.pose.bones:c.key(b,t*s.render.fps,{})
 c.smooth(fk)
 # Refresh anatomical pole attachments to follow the posed torso.
 for side in ('Left','Right'):f.follow_arm(side)


def fast_guard():
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];h=bpy.data.objects['Hilt_Control'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};raised=h.matrix_world.copy();fk.animation_data_clear();h.animation_data_clear()
 # Low two-handed ready: hands at belt, blade tipped sideways away from the face.
 # 0.08s readable idle, then 0.22s rapid raise, with small settle.
 for t,v in [(0,0),(.08,0),(.14,.22),(.22,.78),(.3,1.04),(.4,1),(.7,1)]:
  f.set_fk_pose(fk,t,base,Vector((0,0,-.015*v)))
  angle=math.radians(-48*(1-v)+18*v)
  m=Matrix.Translation(raised.translation+Vector((0,.015,-.14))*(1-v)+Vector((.005,-.015,.055))*v)@Matrix.Rotation(angle,4,'Y')@raised.to_3x3().to_4x4()
  f.key_matrix(h,t,m)
 for o in bpy.data.collections['AUTHORING_guard_two'].objects:c.smooth(o)
 s['guard_ready_seconds']=.3;s['guard_raise_seconds']=.22


def blink_dodge(job):
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};world={b.name:b.matrix.copy() for b in fk.pose.bones};fk.animation_data_clear()
 for side in ('Left','Right'):
  f.reset_animation(bpy.data.objects[side+'Leg_Target']);f.reset_animation(bpy.data.objects[side+'Leg_Pole'])
 sign=1 if job=='strafe_left' else -1
 # Fast anticipation, sideways hop, hidden transit, decisive landing and ready recovery.
 beats=[(0,0,0,0),(.06,0,-.035,0),(.12,.07,.025,.025),(.18,.19,.09,.105),(.28,.67,.10,.13),(.34,.92,.035,.045),(.4,1.,-.035,0),(.5,1.,-.015,0),(.7,1.,0,0)]
 for t,x,z,footz in beats:
  delta=Vector((sign*x,0,z));f.set_fk_pose(fk,t,base,delta)
  lean=0 if t in (0,.7) else (-10 if t<.28 else 6 if t<.5 else 0)*sign
  world_rotate(fk.pose.bones['Spine2'],'Y',lean)
  world_rotate(fk.pose.bones['LeftForeArm'],'X',-18*math.sin(math.pi*t/.7))
  for b in fk.pose.bones:c.key(b,t*s.render.fps,{})
  for side in ('Left','Right'):
   m=world[side+'Foot'].copy();m.translation+=Vector((sign*x,0,footz));f.key_matrix(bpy.data.objects[side+'Leg_Target'],t,m)
   a,mid,end=[world[side+n].translation for n in ('UpLeg','Leg','Foot')];axis=(end-a).normalized();d=mid-a-axis*(mid-a).dot(axis)
   f.key_vector(bpy.data.objects[side+'Leg_Pole'],t,mid+d.normalized()*.3+delta)
 for side in ('Left','Right'):f.follow_arm(side)
 for o in bpy.data.collections['AUTHORING_'+job].objects:c.smooth(o)
 s['root_motion']=f'{sign:+d} X, 1.0 model units';s['blink_vfx']=json.dumps({'vanish':.18,'reappear':.34,'distance':1.,'direction':sign,'duration':.7})


def blink_visibility():
 """Native render visibility plus explicit glTF extras consumed by review VFX.
 glTF has no standard visibility animation; no zero-scale skin deformation.
 """
 s=bpy.context.scene
 for o in s.objects:
  if o.type=='MESH' and (o.get('export_body') or o.get('review_attachment')):
   for t,hidden in [(0,False),(.18,True),(.34,False),(.7,False)]:o.hide_render=hidden;o.keyframe_insert('hide_render',frame=t*s.render.fps)
   for fc in c.curves(o.animation_data.action):
    for k in fc.keyframe_points:k.interpolation='CONSTANT'
 bpy.data.objects['Knight_Deform']['veyrBlink']=s['blink_vfx']


def cup_with_handle():
 s=bpy.context.scene;rig=bpy.data.objects['Knight_Deform'];c.at(.35*s.render.fps)
 old=bpy.data.objects.get('DrinkingCup')
 if old:bpy.data.objects.remove(old,do_unlink=True)
 # Bowl is outside the glove; the four curled fingers wrap around the D-handle bar.
 center=Vector((.060,.091,.010));rings=[(-.031,.019),(-.026,.023),(.029,.028),(.033,.028),(.033,.024),(-.023,.018)]
 verts=[];faces=[]
 for z,r in rings:
  for i in range(48):
   a=i*math.tau/48;verts.append(center+Vector((r*math.cos(a),r*math.sin(a),-z)))
 for j in range(len(rings)-1):
  for i in range(48):faces.append((j*48+i,j*48+(i+1)%48,(j+1)*48+(i+1)%48,(j+1)*48+i))
 faces.append(tuple((len(rings)-1)*48+i for i in range(48)))
 # D handle in the hand's Y/Z plane, centered in the curled fingers.
 path=[Vector((.060,.067,-.017)),Vector((.060,.052,-.029)),Vector((.060,.029,-.027)),Vector((.060,.023,-.015)),Vector((.060,.023,.034)),Vector((.060,.030,.045)),Vector((.060,.052,.047)),Vector((.060,.067,.036))]
 start=len(verts)
 for i,p in enumerate(path):
  tangent=(path[min(i+1,len(path)-1)]-path[max(0,i-1)]).normalized();u=Vector((1,0,0));v=tangent.cross(u).normalized()
  for k in range(12):verts.append(p+.004*(u*math.cos(k*math.tau/12)+v*math.sin(k*math.tau/12)))
 for i in range(len(path)-1):
  for k in range(12):faces.append((start+i*12+k,start+i*12+(k+1)%12,start+(i+1)*12+(k+1)%12,start+(i+1)*12+k))
 mesh=bpy.data.meshes.new('Cup_Outside_Glove_With_D_Handle');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('DrinkingCup',mesh);s.collection.objects.link(o)
 mat=bpy.data.materials.get('Weathered_Bronze_Cup') or bpy.data.materials.new('Weathered_Bronze_Cup');mat.diffuse_color=(.27,.12,.035,1);mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.27,.12,.035,1);bsdf.inputs['Metallic'].default_value=.4;bsdf.inputs['Roughness'].default_value=.4;o.data.materials.append(mat)
 world=rig.matrix_world@rig.pose.bones['LeftHand'].matrix;o.parent=rig;o.parent_type='BONE';o.parent_bone='LeftHand';bpy.context.view_layer.update();o.matrix_world=world
 scale=o.scale.copy()
 for t,v in [(0,1e-5),(.18,1e-5),(.2,1),(2.15,1),(2.25,1e-5),(2.4,1e-5)]:o.scale=scale*v;o.keyframe_insert('scale',frame=t*s.render.fps)
 for fc in c.curves(o.animation_data.action):
  for k in fc.keyframe_points:k.interpolation='CONSTANT'
 o['export_body']=True;o['review_prop']=True;o['grip']='Exterior D handle, bowl outside fingers';o['bowl_hand_local_y']=.091


def export(job):
 s=bpy.context.scene;c.at(0);rig=bpy.data.objects['Knight_Deform']
 for o in s.objects:o.select_set(o==rig or o.name=='ReviewWeaponSocket' or bool(o.get('export_body')))
 bpy.context.view_layer.objects.active=rig;p=c.OUT/(job+'_Blender_v1.glb')
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.export_scene.gltf(filepath=str(p),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=f.NAMES[job],export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False,export_extras=True)
 tx=bpy.data.texts.get('feedback_v3_revise.py') or bpy.data.texts.new('feedback_v3_revise.py');tx.clear();tx.write(Path(__file__).read_text());tx.use_fake_user=True
 bpy.ops.wm.save_as_mainfile(filepath=str(c.OUT/(job+'_Blender_v1.blend')),compress=True)
 rp=c.OUT/(job+'-report.json');r=json.loads(rp.read_text()) if rp.exists() else {};r.update(job=job,reviewName=f.NAMES[job],duration=s['duration'],sha256=hashlib.sha256(p.read_bytes()).hexdigest(),ownerApproved=False,feedbackRevision=3,rootMotion=s.get('root_motion','none'),blink=json.loads(s['blink_vfx']) if s.get('blink_vfx') else None);rp.write_text(json.dumps(r,indent=2)+'\n');print('V3_READY',job)


def build(job):
 if job=='heal':
  bpy.ops.wm.open_mainfile(filepath=str(REPO/'Local/Blender/feedback-20261021/heal_Blender_v1.blend'),load_ui=False);bpy.context.scene['session_owner']=c.OWNER
  # Preserve timing/gesture; translate only the mouth approach enough to clear the helmet.
  f.configure('heal');target=bpy.data.objects['LeftArm_Target'];samples=[]
  for t in f.TIMES['heal']:
   c.at(t*bpy.context.scene.render.fps);m=target.matrix_basis.copy()
   amount=max(0,min(1,(t-.65)/.3,(1.7-t)/.25));m.translation+=Vector((0,-.040,.010))*amount;samples.append((t,m))
  target.animation_data_clear()
  for t,m in samples:f.key_matrix(target,t,m)
  c.smooth(target)
  old=bpy.data.objects.get('DrinkingCup')
  if old:bpy.data.objects.remove(old,do_unlink=True)
  c.bake();cup_with_handle();export(job);return
 f.configure(job)
 bpy.context.scene['root_motion']='none'
 if 'blink_vfx' in bpy.context.scene:del bpy.context.scene['blink_vfx']
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):c.prepare(job)
 if job=='heavy':free_arm()
 elif job=='backpedal':ready_backpedal()
 elif job=='guard_two':fast_guard()
 else:blink_dodge(job)
 c.bake()
 if job.startswith('strafe'):blink_visibility()
 export(job)
