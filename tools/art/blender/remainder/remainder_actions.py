"""Native Blender authoring for the remaining Knight set; execute through owned MCP.

Keeps previous approved files immutable. Reference motion supplies sparse body
poses; approved hand shapes, native FK corrections, anatomical IK, and closed
locomotion curves are authored and evaluated inside Blender.
"""
from pathlib import Path
import importlib.util
import bpy, math, json
from mathutils import Matrix,Vector,Quaternion
REPO=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('veyr_blender_core',REPO/'tools/art/blender/rebuild/approved_actions.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
core.OUT=REPO/'Local/Blender/remainder-20261021'
core.OWNER='codex-veyr-remainder-20261021'
NAMES={
 'walk':'WalkOneHand_Blender_v1','walk_two':'WalkTwoHand_Blender_v4',
 'run':'RunOneHand_Blender_v1','backpedal':'Backpedal_Blender_v1',
 'strafe_left':'StrafeLeft_Blender_v1','strafe_right':'StrafeRight_Blender_v1',
 'guard':'GuardOneHand_Blender_v1','guard_two':'GuardTwoHand_Blender_v1',
 'heavy':'HeavyAttackOneHand_Blender_v1','jump':'Jump_Blender_v1',
 'heal':'Heal_Blender_v1','stagger':'Stagger_Blender_v1','death':'Death_Blender_v1'}
DURATIONS={'walk':1.2,'walk_two':3.5,'run':.6,'backpedal':1.6,'strafe_left':1.25,'strafe_right':1.3,'guard':4.,'guard_two':4.,'heavy':1.4,'jump':1.,'heal':1.25,'stagger':.42,'death':4.4}
SOURCES={'walk':'Reference_Walk','walk_two':'WalkTwoHand_Blender_v3','run':'Reference_Run','backpedal':'Reference_Backpedal','strafe_left':'Reference_StrafeLeft','strafe_right':'Reference_StrafeRight','guard':'IdleOneHand_Breathing_v3','guard_two':'IdleTwoHand_ReadyBreath_v6','heavy':'StrongAttackTwoHand_Sweep_v9','jump':'Reference_Jump','heal':'Reference_Heal','stagger':'Reference_Stagger','death':'Reference_Death'}
LOOPS={'walk','run','backpedal','strafe_left','strafe_right','guard','guard_two'}
CYCLES={'walk','run','backpedal','strafe_left','strafe_right'}
core.JOBS={j:(SOURCES[j],d,[d*i/(28 if j=='walk_two' else 16 if j in CYCLES or j=='death' else 12) for i in range((28 if j=='walk_two' else 16 if j in CYCLES or j=='death' else 12)+1)],j in ('guard_two','walk_two')) for j,d in DURATIONS.items()}
core.SOURCE_RANGES={'walk':(.625,2.275),'backpedal':(0,1.6666666269),'strafe_left':(0,1.2460161448),'strafe_right':(0,1.2941379547),'heavy':(0,4.4/3)}

# Read approved idle key poses through Blender, not an external transform solver.
def approved_pose(two=False):
 before=set(bpy.data.objects)
 name='IdleTwoHand_ReadyBreath_v6' if two else 'IdleOneHand_Breathing_v3'
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.import_scene.gltf(filepath=str(core.ASSETS/(name+'.glb')))
 added=set(bpy.data.objects)-before;r=next(o for o in added if o.type=='ARMATURE');core.at(0)
 result={b.name:b.matrix_basis.copy() for b in r.pose.bones}
 for o in added:bpy.data.objects.remove(o,do_unlink=True)
 return result

APPROVED={}
def refine(rig,snapshots,job,offset):
 two=job in ('guard_two','walk_two');approved=APPROVED[two];duration=DURATIONS[job];result=[]
 rig.animation_data_clear()
 for t,poses,bases,weapon in snapshots:
  u=t/duration;wave=math.sin(u*math.tau)
  for b in rig.pose.bones:b.matrix_basis=bases[b.name]
  # Preserve the approved hand shapes and wrist alignment, never knuckle grips.
  if not two:
   for side in ('Left','Right'):
    for b in [rig.pose.bones[side+'Hand'],*rig.pose.bones[side+'Hand'].children_recursive]:b.matrix_basis=approved[b.name]
  if job in CYCLES or job in ('jump','heal','stagger'):
   for n in ('RightShoulder','RightArm','RightForeArm'):rig.pose.bones[n].matrix_basis=approved[n]
   b=rig.pose.bones['RightArm'];b.rotation_mode='QUATERNION'
   b.rotation_quaternion=b.rotation_quaternion@Quaternion((0,0,1),math.radians((5 if job=='run' else 2)*wave))
  if job in ('run','strafe_left','strafe_right'):
   for n in ('Hips','Spine','Spine1','Spine2','Neck','Head'):
    b=rig.pose.bones[n];b.rotation_mode='QUATERNION';b.rotation_quaternion=approved[n].to_quaternion().slerp(b.rotation_quaternion,.35)
  if job=='jump':
   hips=rig.pose.bones['Hips'];hips.location+=rig.data.bones['Hips'].matrix_local.to_3x3().inverted()@Vector((0,0,.18*math.sin(math.pi*u)**2))
  if job=='guard':
   # Defensive diagonal sword with the free hand guarding the upper body.
   for n in ('RightArm','RightForeArm','LeftArm','LeftForeArm'):rig.pose.bones[n].matrix_basis=approved[n]
   for n,deg in [('RightArm',-38),('RightForeArm',-32),('LeftArm',-18),('LeftForeArm',-50)]:
    b=rig.pose.bones[n];b.rotation_mode='QUATERNION';b.rotation_quaternion=b.rotation_quaternion@Quaternion((0,0,1),math.radians(deg))
  if job=='death' and u>.3:
   for side in ('Left','Right'):
    for b in rig.pose.bones[side+'Hand'].children_recursive:
     b.rotation_mode='QUATERNION';b.rotation_quaternion=b.rotation_quaternion.slerp(Quaternion(),min(.65,(u-.3)*2))
  if job=='heavy':
   # Released free arm guards and counterbalances the approved sweep body mechanics.
   for n in ('LeftShoulder','LeftArm','LeftForeArm'):rig.pose.bones[n].matrix_basis=approved[n]
   b=rig.pose.bones['LeftForeArm'];b.rotation_mode='QUATERNION';b.rotation_quaternion=b.rotation_quaternion@Quaternion((0,0,1),math.radians(-25*math.sin(math.pi*u)**2))
  if job in ('heal','jump','stagger','heavy','death') and (u<1e-8 or (u>1-1e-8 and job!='death')):
   for b in rig.pose.bones:b.matrix_basis=approved[b.name]
  bpy.context.view_layer.update()
  poses={b.name:b.matrix.copy() for b in rig.pose.bones};bases={b.name:b.matrix_basis.copy() for b in rig.pose.bones}
  if not two:weapon=rig.matrix_world@poses['RightHand']@offset
  if job=='guard_two':
   pivot=weapon.translation.copy();delta=Matrix.Translation(pivot+Vector((.015,-.02,.035)))@Matrix.Rotation(math.radians(22),4,'Y')@Matrix.Translation(-pivot)
   weapon=delta@weapon
   for side in ('Right','Left'):
    for b in [rig.pose.bones[side+'Hand'],*rig.pose.bones[side+'Hand'].children_recursive]:poses[b.name]=delta@poses[b.name]
  result.append((t,poses,bases,weapon))
 # Close repeated motions using a matching final pose; never wrap a death.
 if job in LOOPS:
  _,p,b,w=result[0];result[-1]=(duration,{n:m.copy() for n,m in p.items()},{n:m.copy() for n,m in b.items()},w.copy())
 return result
core.SNAPSHOT_REFINER=refine

def follow_fk_targets(job):
 # One-handed arms and moving feet follow the native FK arcs exactly between
 # pose beats. This prevents independently interpolated world targets stretching
 # a chain. Static guards retain anchored foot targets; two hands share the hilt.
 coll=bpy.data.collections['AUTHORING_'+job];fk=bpy.data.objects['Pose_Control_Rig']
 labels=[]
 if job not in ('walk_two','guard_two'):labels+=['LeftArm','RightArm']
 if job not in ('walk_two','guard','guard_two'):labels+=['LeftLeg','RightLeg']
 core.at(0)
 for label in labels:
  side='Left' if label.startswith('Left') else 'Right';end=side+('Hand' if label.endswith('Arm') else 'Foot')
  target=bpy.data.objects[label+'_Target'];target.parent=None;target.animation_data_clear();target.matrix_basis=Matrix.Identity(4)
  c=target.constraints.new('COPY_TRANSFORMS');c.target=fk;c.subtarget=end
  # Place a pole in the FK bend plane with a bone-parented offset control.
  mid=side+('ForeArm' if label.endswith('Arm') else 'Leg');start=side+('Arm' if label.endswith('Arm') else 'UpLeg')
  a,m,z=[fk.matrix_world@fk.pose.bones[n].matrix.translation for n in (start,mid,end)];axis=(z-a).normalized();direction=m-a-axis*(m-a).dot(axis)
  if direction.length<1e-6:direction=Vector((0,-1,0))
  point=m+direction.normalized()*.3
  follow=core.empty(label+'_Pole_Follow',coll);c=follow.constraints.new('COPY_TRANSFORMS');c.target=fk;c.subtarget=mid
  pole=bpy.data.objects[label+'_Pole'];pole.animation_data_clear();pole.parent=follow;pole.matrix_basis=(fk.matrix_world@fk.pose.bones[mid].matrix).inverted()@Matrix.Translation(point)


def clean_body():
 """Use the approved clean Knight skin on the unchanged named deform skeleton."""
 scene=bpy.context.scene;rig=bpy.data.objects['Knight_Deform'];before=set(bpy.data.objects)
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):bpy.ops.import_scene.gltf(filepath=str(core.ASSETS/'IdleOneHand_Breathing_v3.glb'))
 added=set(bpy.data.objects)-before;reference=next(o for o in added if o.type=='ARMATURE')
 error=max(max(abs(b.matrix_local[i][j]-reference.data.bones[b.name].matrix_local[i][j]) for i in range(4) for j in range(4)) for b in rig.data.bones)
 assert error<1e-5,('Clean body rest skeleton mismatch',error)
 old=[o for o in before if o.get('export_body')]
 for o in added:
  if o.type=='MESH':
   matrix=o.matrix_world.copy();o.parent=rig;o.matrix_world=matrix
   for mod in o.modifiers:
    if mod.type=='ARMATURE':mod.object=rig
   o['export_body']=True;o.name='Knight_Approved_Body'
 for o in old:bpy.data.objects.remove(o,do_unlink=True)
 for o in added:
  if o.type!='MESH':bpy.data.objects.remove(o,do_unlink=True)
 scene['clean_body_rest_error']=error


def healing_flask():
 """Small native Blender review prop, parented to the animated left palm."""
 rig=bpy.data.objects['Knight_Deform'];core.at(0)
 profile=[(-.04,.012),(-.035,.020),(.012,.022),(.027,.012),(.045,.008),(.053,.009)]
 vertices=[];faces=[];segments=16
 for z,r in profile:
  for i in range(segments):vertices.append((r*math.cos(math.tau*i/segments),r*math.sin(math.tau*i/segments),z))
 for row in range(len(profile)-1):
  for i in range(segments):a=row*segments+i;b=row*segments+(i+1)%segments;faces.append((a,b,b+segments,a+segments))
 faces.extend([tuple(reversed(range(segments))),tuple((len(profile)-1)*segments+i for i in range(segments))])
 mesh=bpy.data.meshes.new('HealingFlask');mesh.from_pydata(vertices,[],faces);mesh.update()
 o=bpy.data.objects.new('HealingFlask',mesh);bpy.context.scene.collection.objects.link(o)
 mat=bpy.data.materials.new('Flask_Amber');mat.diffuse_color=(.55,.19,.025,1);mat.use_nodes=True;bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.55,.19,.025,1);bsdf.inputs['Metallic'].default_value=.45;bsdf.inputs['Roughness'].default_value=.3;o.data.materials.append(mat)
 o.parent=rig;o.parent_type='BONE';o.parent_bone='LeftHand';bpy.context.view_layer.update()
 o.matrix_world=rig.matrix_world@rig.pose.bones['LeftHand'].matrix@Matrix.Translation((.055,0,0))
 o['export_body']=True;o['review_prop']=True


def release_death_weapon():
 scene=bpy.context.scene;hilt=bpy.data.objects['Hilt_Control'];fk=bpy.data.objects['Pose_Control_Rig'];core.at(0)
 first=hilt.matrix_world.copy();hand0=fk.matrix_world@fk.pose.bones['RightHand'].matrix
 release_frame=.30*scene.frame_end;core.at(release_frame)
 release=(fk.matrix_world@fk.pose.bones['RightHand'].matrix)@hand0.inverted()@first
 hilt.parent=None;hilt.animation_data_clear();hilt.constraints.clear();previous={}
 landing=Matrix.LocRotScale(Vector((-.38,-.12,.075)),Quaternion((1,0,0),math.pi/2),Vector((.4096359623,)*3))
 middle=release.copy();middle.translation=(release.translation+landing.translation)*.5+Vector((0,0,.025))
 for f,m in [(0,first),(release_frame-.001,first),(release_frame,release),(.37*scene.frame_end,middle),(.45*scene.frame_end,landing),(.49*scene.frame_end,landing),(scene.frame_end,landing)]:
  hilt.matrix_basis=m;core.key(hilt,f,previous)
 core.smooth(hilt)
 # Native Child Of constraint maintains exact wrist attachment until release.
 c=hilt.constraints.new('CHILD_OF');c.name='Held until release';c.target=fk;c.subtarget='RightHand';c.inverse_matrix=hand0.inverted()
 for f,v in [(0,1),(release_frame-.001,1),(release_frame,0),(scene.frame_end,0)]:c.influence=v;c.keyframe_insert('influence',frame=f)
 for fc in core.curves(hilt.animation_data.action):
  for k in fc.keyframe_points:
   if k.co.x<release_frame:k.interpolation='CONSTANT'
 hilt['purpose']='Native wrist attachment until release, then a separate fall and ground settle'


def build(job):
 assert bpy.context.scene.get('session_owner')==core.OWNER
 APPROVED[False]=approved_pose(False);APPROVED[True]=approved_pose(True)
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):core.prepare(job)
 follow_fk_targets(job)
 clean_body()
 if job=='heal':healing_flask()
 # Use an integer timebase for exact endpoints; sparse controls remain editable.
 scene=bpy.context.scene;rate=200 if job in ('stagger','strafe_left','heal') else 150
 end=round(DURATIONS[job]*rate);ratio=end/scene.frame_end;seen=set()
 for o in bpy.data.collections['AUTHORING_'+job].objects:
  if o.animation_data and o.animation_data.action and o.animation_data.action.name not in seen:
   a=o.animation_data.action;seen.add(a.name)
   for fc in core.curves(a):
    for k in fc.keyframe_points:k.co.x*=ratio;k.handle_left.x*=ratio;k.handle_right.x*=ratio
 for marker in scene.timeline_markers:marker.frame=round(marker.frame*ratio)
 scene.frame_end=end;scene.render.fps=rate;scene.render.fps_base=1
 if job=='death':release_death_weapon()
 core.bake()
 # Bundle the extension as editable documentation beside the core recipe.
 txt=bpy.data.texts.get('remainder_actions.py') or bpy.data.texts.new('remainder_actions.py');txt.clear();txt.write(Path(__file__).read_text());txt.use_fake_user=True
 scene['review_name']=NAMES[job];scene['loop_expected']=job in LOOPS
 bpy.ops.wm.save_as_mainfile(filepath=str(core.OUT/(job+'_Blender_v1.blend')),compress=True)
 p=core.OUT/(job+'-report.json');r=json.loads(p.read_text());r.update({'reviewName':NAMES[job],'loopExpected':job in LOOPS,'authoring':'Blender sparse FK poses, approved grip shapes, native IK and native bone follow constraints','sourceWindow':core.SOURCE_RANGES.get(job,[0,DURATIONS[job]]),'ownerApproved':False});p.write_text(json.dumps(r,indent=2))
 print('REMAINDER_READY',job)
