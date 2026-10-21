"""Owner-directed revisions. Native Blender controls/IK, not source-pose retouching.

Movement starts from approved idle. Feet are independently planted in world space;
no rejected locomotion poses are reused. Heal and heavy use explicit outward elbow
poles and a neutral forearm-to-wrist relationship.
"""
from pathlib import Path
import importlib.util,json,math,hashlib
import bpy
from mathutils import Vector,Matrix,Quaternion
REPO=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('veyr_core',REPO/'tools/art/blender/rebuild/approved_actions.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
c.OUT=REPO/'Local/Blender/feedback-20261021';c.OWNER='codex-veyr-feedback-20261021'
NAMES={'heal':'Heal_Blender_v2','heavy':'HeavyAttackOneHand_Blender_v2','backpedal':'Backpedal_Blender_v2','guard_two':'GuardReadyTwoHand_Blender_v2','strafe_left':'StrafeLeft_Blender_v2','strafe_right':'StrafeRight_Blender_v2'}
DUR={'heal':2.4,'heavy':1.4,'backpedal':2.4,'guard_two':1.1,'strafe_left':1.3,'strafe_right':1.3}
TIMES={'heal':[0,.18,.35,.65,.95,1.2,1.45,1.7,2.,2.25,2.4],
 'heavy':[0,.12,.25,.42,.58,.74,.9,1.08,1.25,1.4],
 'backpedal':[0,.2,.4,.6,.8,1.,1.2,1.4,1.6,1.8,2.,2.2,2.4],
 'guard_two':[0,.12,.25,.45,.65,.85,1.1],
 'strafe_left':[0,.15,.3,.45,.6,.75,.9,1.05,1.2,1.3],
 'strafe_right':[0,.15,.3,.45,.6,.75,.9,1.05,1.2,1.3]}
c.JOBS={j:('HeavyAttackOneHand_Blender_v1' if j=='heavy' else 'IdleTwoHand_ReadyBreath_v6' if j=='guard_two' else 'IdleOneHand_Breathing_v3',DUR[j],TIMES[j],j=='guard_two') for j in DUR}
c.SOURCE_RANGES={j:(0,4.) for j in DUR if j!='heavy'}

def configure(job):
 c.END_FOLLOW_LOWER={'LeftArm'} if job in ('heal','heavy') else set()

def key_matrix(o,t,m):
 o.matrix_basis=m;c.key(o,t*bpy.context.scene.render.fps,{})

def key_vector(o,t,v):
 o.location=v;o.keyframe_insert('location',frame=t*bpy.context.scene.render.fps)

def reset_animation(o):
 world=o.matrix_world.copy();o.parent=None;o.constraints.clear();o.animation_data_clear();o.matrix_basis=world

def set_fk_pose(fk,t,bases,delta=Vector((0,0,0))):
 for b in fk.pose.bones:b.matrix_basis=bases[b.name]
 hips=fk.pose.bones['Hips'];hips.location+=fk.data.bones['Hips'].matrix_local.to_3x3().inverted()@delta
 bpy.context.view_layer.update()
 for b in fk.pose.bones:c.key(b,t*bpy.context.scene.render.fps,{})

def idle_based_movement(job):
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};world={b.name:b.matrix.copy() for b in fk.pose.bones}
 fk.animation_data_clear()
 for label in ('LeftLeg','RightLeg'):
  reset_animation(bpy.data.objects[label+'_Target']);reset_animation(bpy.data.objects[label+'_Pole'])
 if job=='backpedal':
  # Three alternating backward steps: each foot remains planted outside its swing.
  beats=[(0,0,0,0,0,0),(.2,0,0,0,0,0),(.4,.045,.09,.05,0,0),(.6,.09,.18,0,0,0),(.8,.12,.18,0,0,0),(1.,.18,.18,0,.18,.055),(1.2,.24,.18,0,.36,0),(1.4,.27,.18,0,.36,0),(1.6,.315,.27,.05,.36,0),(1.8,.36,.36,0,.36,0),(2.,.36,.36,0,.36,0),(2.2,.36,.36,0,.36,0),(2.4,.36,.36,0,.36,0)]
  for t,travel,ly,lz,ry,rz in beats:
   active=0<t<2.;delta=Vector((0,travel,-.022 if active else 0))
   set_fk_pose(fk,t,base,delta)
   for side,offset in [('Left',Vector((0,ly,lz))),('Right',Vector((0,ry,rz)))]:
    m=world[side+'Foot'].copy();m.translation+=offset;key_matrix(bpy.data.objects[side+'Leg_Target'],t,m)
    a,mid,end=[world[side+n].translation for n in ('UpLeg','Leg','Foot')];axis=(end-a).normalized();direction=mid-a-axis*(mid-a).dot(axis)
    pole=mid+direction.normalized()*.3+delta;key_vector(bpy.data.objects[side+'Leg_Pole'],t,pole)
 else:
  sign=1 if job=='strafe_left' else -1;lead='Left' if sign==1 else 'Right';trail='Right' if sign==1 else 'Left'
  # Lead foot opens stance; trailing foot follows. The lateral order never changes.
  beats=[(0,0,0,0,0,0),(.15,0,0,0,0,0),(.3,.035,.11,.045,0,0),(.45,.11,.22,0,0,0),(.6,.11,.22,0,0,0),(.75,.155,.22,0,.11,.045),(.9,.20,.22,0,.22,0),(1.05,.22,.22,0,.22,0),(1.2,.22,.22,0,.22,0),(1.3,.22,.22,0,.22,0)]
  for t,travel,lx,lz,tx,tz in beats:
   delta=Vector((sign*travel,0,-.025 if .15<t<1.05 else 0));set_fk_pose(fk,t,base,delta)
   for side,offset in [(lead,Vector((sign*lx,0,lz))),(trail,Vector((sign*tx,0,tz)))]:
    m=world[side+'Foot'].copy();m.translation+=offset;key_matrix(bpy.data.objects[side+'Leg_Target'],t,m)
    a,mid,end=[world[side+n].translation for n in ('UpLeg','Leg','Foot')];axis=(end-a).normalized();direction=mid-a-axis*(mid-a).dot(axis)
    key_vector(bpy.data.objects[side+'Leg_Pole'],t,mid+direction.normalized()*.3+delta)
 # Arms follow the upright moving torso; no independent old world-space arm path.
 follow_arm('Left');follow_arm('Right')
 for o in bpy.data.collections['AUTHORING_'+job].objects:c.smooth(o)
 s['root_motion']='backward .36' if job=='backpedal' else ('left .22' if sign==1 else 'right .22')


def rest_arm_pole(fk,side):
 a,m,z=[fk.matrix_world@fk.pose.bones[side+n].matrix.translation for n in ('Arm','ForeArm','Hand')]
 axis=(z-a).normalized();direction=m-a-axis*(m-a).dot(axis)
 return m+direction.normalized()*.3


def follow_arm(side):
 fk=bpy.data.objects['Pose_Control_Rig'];c.at(0);target=bpy.data.objects[side+'Arm_Target'];reset_animation(target)
 cons=target.constraints.new('COPY_TRANSFORMS');cons.target=fk;cons.subtarget=side+'Hand'
 # Pole in the unchanged idle arm plane, translated with the torso.
 pole=bpy.data.objects[side+'Arm_Pole'];reset_animation(pole);pole.matrix_world=Matrix.Translation(rest_arm_pole(fk,side))
 offset=(fk.matrix_world@fk.pose.bones['Spine2'].matrix).inverted()@pole.matrix_world
 follow=c.empty(side+'_Chest_Follow',bpy.data.collections['AUTHORING_'+bpy.context.scene['rebuild_job']]);cons=follow.constraints.new('COPY_TRANSFORMS');cons.target=fk;cons.subtarget='Spine2'
 pole.parent=follow;pole.matrix_basis=offset


def simple_drink():
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};start=fk.pose.bones['LeftHand'].matrix.copy();fk.animation_data_clear()
 target=bpy.data.objects['LeftArm_Target'];pole=bpy.data.objects['LeftArm_Pole'];reset_animation(target);reset_animation(pole);rest_pole=rest_arm_pole(fk,'Left')
 # Wrist positions: rest -> cup at waist -> mouth -> lower -> rest.
 positions=[start.translation,Vector((.19,-.09,.57)),Vector((.18,-.17,.66)),Vector((.11,-.18,.78)),Vector((.045,-.145,.845)),Vector((.04,-.135,.85)),Vector((.04,-.135,.85)),Vector((.11,-.18,.78)),Vector((.18,-.17,.66)),Vector((.19,-.09,.57)),start.translation]
 for t,position in zip(TIMES['heal'],positions):
  set_fk_pose(fk,t,base)
  m=start.copy();m.translation=position;key_matrix(target,t,m)
  # Elbow bends forward and out at chest level, never toward the hip.
  blend=min(1.,t/.35,(2.4-t)/.35)
  p=rest_pole.lerp(Vector((.32,-.035,.55)),max(0,blend))
  key_vector(pole,t,p)
 follow_arm('Right')
 for o in bpy.data.collections['AUTHORING_heal'].objects:c.smooth(o)


def free_heavy_arm():
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};initial_chest=fk.pose.bones['Spine2'].matrix.to_quaternion();initial_hand=fk.pose.bones['LeftHand'].matrix.copy()
 target=bpy.data.objects['LeftArm_Target'];pole=bpy.data.objects['LeftArm_Pole'];reset_animation(target);reset_animation(pole);rest_pole=rest_arm_pole(fk,'Left')
 for t in TIMES['heavy']:
  c.at(t*s.render.fps)
  for n in ('LeftShoulder','LeftArm','LeftForeArm','LeftHand'):
   fk.pose.bones[n].matrix_basis=base[n];c.key(fk.pose.bones[n],t*s.render.fps,{})
  bpy.context.view_layer.update();shoulder=fk.pose.bones['LeftArm'].matrix.translation.copy();chest=fk.pose.bones['Spine2'].matrix.to_quaternion();rotation=chest@initial_chest.inverted();out=rotation@Vector((1,0,0));front=rotation@Vector((0,-1,0))
  phase=math.sin(math.pi*t/DUR['heavy'])**.6
  rest=fk.pose.bones['LeftHand'].matrix.translation.copy();raised=shoulder+out*(.065+.035*phase)+front*(.11+.025*phase)+Vector((0,0,-.07+.03*phase))
  m=initial_hand.copy();m.translation=rest.lerp(raised,min(1,phase*1.5));key_matrix(target,t,m)
  key_vector(pole,t,rest_pole.lerp(shoulder+out*.24+front*.02+Vector((0,0,-.18)),min(1,phase*1.5)))
 for o in bpy.data.collections['AUTHORING_heavy'].objects:c.smooth(o)


def guard_entry():
 s=bpy.context.scene;fk=bpy.data.objects['Pose_Control_Rig'];hilt=bpy.data.objects['Hilt_Control'];c.at(0)
 base={b.name:b.matrix_basis.copy() for b in fk.pose.bones};w0=hilt.matrix_world.copy();fk.animation_data_clear();hilt.animation_data_clear()
 # Begin at the exact two-hand idle; raise and angle the weapon into guard.
 for t,v in [(0,0),(.12,.03),(.25,.18),(.45,.62),(.65,.92),(.85,1),(1.1,1)]:
  set_fk_pose(fk,t,base,Vector((0,0,-.012*v)))
  m=Matrix.Translation(w0.translation+Vector((.01,-.015,.045))*v)@Matrix.Rotation(math.radians(20*v),4,'Y')@w0.to_3x3().to_4x4()
  key_matrix(hilt,t,m)
 for o in bpy.data.collections['AUTHORING_guard_two'].objects:c.smooth(o)


def cup_prop():
 s=bpy.context.scene;rig=bpy.data.objects['Knight_Deform'];c.at(.35*s.render.fps)
 # Hollow tapered cup, calibrated upright at pickup. Bone parenting carries it.
 rings=[(-.03,.017),(-.025,.020),(.027,.027),(.031,.027),(.031,.023),(-.021,.016)]
 verts=[(r*math.cos(i*math.tau/24),r*math.sin(i*math.tau/24),z) for z,r in rings for i in range(24)];faces=[]
 for j in range(len(rings)-1):
  for i in range(24):faces.append((j*24+i,j*24+(i+1)%24,(j+1)*24+(i+1)%24,(j+1)*24+i))
 faces.append(tuple((len(rings)-1)*24+i for i in range(24)))
 mesh=bpy.data.meshes.new('DrinkingCup');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('DrinkingCup',mesh);s.collection.objects.link(o)
 mat=bpy.data.materials.new('Weathered_Bronze_Cup');mat.diffuse_color=(.27,.12,.035,1);mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.27,.12,.035,1);bsdf.inputs['Metallic'].default_value=.4;bsdf.inputs['Roughness'].default_value=.4;o.data.materials.append(mat)
 palm=rig.matrix_world@rig.pose.bones['LeftHand'].matrix@Vector((.055,0,0))
 o.parent=rig;o.parent_type='BONE';o.parent_bone='LeftHand';bpy.context.view_layer.update();o.matrix_world=Matrix.Translation(palm)
 scale=o.scale.copy()
 for t,v in [(0,0),(.18,0),(.2,1),(2.15,1),(2.25,0),(2.4,0)]:o.scale=scale*max(v,1e-5);o.keyframe_insert('scale',frame=t*s.render.fps)
 for fc in c.curves(o.animation_data.action):
  for k in fc.keyframe_points:k.interpolation='CONSTANT'
 o['export_body']=True;o['review_prop']=True


def export_current(job):
 s=bpy.context.scene;rig=bpy.data.objects['Knight_Deform'];c.at(0)
 for o in s.objects:o.select_set(o==rig or o.name=='ReviewWeaponSocket' or bool(o.get('export_body')))
 bpy.context.view_layer.objects.active=rig;p=c.OUT/(job+'_Blender_v1.glb')
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.export_scene.gltf(filepath=str(p),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=NAMES[job],export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 for filename in ('feedback_actions.py',):
  tx=bpy.data.texts.get(filename) or bpy.data.texts.new(filename);tx.clear();tx.write(Path(__file__).read_text());tx.use_fake_user=True
 bpy.ops.wm.save_as_mainfile(filepath=str(c.OUT/(job+'_Blender_v1.blend')),compress=True)
 r=json.loads((c.OUT/(job+'-report.json')).read_text());r.update({'reviewName':NAMES[job],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'ownerApproved':False,'rootMotion':s.get('root_motion','none'),'feedbackRevision':2});(c.OUT/(job+'-report.json')).write_text(json.dumps(r,indent=2)+'\n')
 print('FEEDBACK_READY',job)


def build(job):
 configure(job)
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):c.prepare(job)
 if job in ('backpedal','strafe_left','strafe_right'):idle_based_movement(job)
 elif job=='heal':simple_drink()
 elif job=='heavy':free_heavy_arm()
 elif job=='guard_two':guard_entry()
 c.bake()
 if job=='heal':cup_prop()
 export_current(job)
