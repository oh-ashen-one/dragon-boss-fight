"""Blender-native composition of approved sourced roll and fitted slash.

No new body motion: exact roll prefix, then source slash at the intended counter
cadence, with a short local-pose join and a palm-locked rigid sword throughout.
"""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/FabRigTesting/Exports';OWNER='codex-veyr-fab-grip';FPS=300

def open_scene(name):
 assert bpy.context.scene.get('session_owner')==OWNER
 bpy.ops.wm.open_mainfile(filepath=str(OUT/(name+'.blend')),load_ui=False);bpy.context.scene['session_owner']=OWNER;return bpy.data.objects['Knight_Comparison']
def pose_basis(t):
 result={}
 for b in t.pose.bones:
  args={'parent_matrix':b.parent.matrix,'parent_matrix_local':b.parent.bone.matrix_local} if b.parent else {}
  result[b.name]=b.bone.convert_local_to_pose(b.matrix,b.bone.matrix_local,invert=True,**args).copy()
 return result

def capture(name,output_duration):
 t=open_scene(name);s=bpy.context.scene;original_fps=s.render.fps;duration=json.loads((OUT/(name+'.json')).read_text())['duration'];count=round(output_duration*FPS);rows=[];hips=[];grip=None
 for i in range(count+1):
  f=i/count*duration*original_fps;s.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update();rows.append(pose_basis(t));hips.append(t.pose.bones['Hips'].head.copy())
  if grip is None:grip=t.pose.bones['WeaponSocket'].matrix.inverted()@t.pose.bones['RightHand'].matrix
 return rows,hips,grip
roll,rhip,rg=capture('Fab_Roll_v17',1.0);attack,ahip,ag=capture('Mixamo_Attack_v17',1.2);t=open_scene('Fab_Roll_v17');s=bpy.context.scene
for b in t.pose.bones:
 for c in list(b.constraints):b.constraints.remove(c)
 b.rotation_mode='QUATERNION'
body=[o for o in s.objects if o.type=='MESH']
for o in list(s.objects):
 if o!=t and o not in body:bpy.data.objects.remove(o,do_unlink=True)
t.animation_data_clear();t.animation_data_create();t.animation_data.action=bpy.data.actions.new('Sourced_RollAttack_v2');s.render.fps=FPS;s.frame_start=0;s.frame_end=660;offset=rhip[-1]-ahip[0];offset.z=0;previous={}
def mix(a,b,u):
 x,q,sc=a.decompose();y,r,ss=b.decompose();return Matrix.LocRotScale(x.lerp(y,u),q.slerp(r,u),sc.lerp(ss,u))
for f in range(661):
 s.frame_set(f)
 if f<=300:pose=roll[f];grip=rg
 else:
  j=f-300;u=min(1,j/36);u=u*u*(3-2*u);pose={n:m.copy() for n,m in attack[j].items()};pose['VeyrRoot'].translation+=t.data.bones['VeyrRoot'].matrix_local.to_3x3().inverted()@offset;pose={n:mix(roll[-1][n],m,u) for n,m in pose.items()};grip=mix(rg,ag,u)
 for b in t.pose.bones:b.matrix_basis=pose[b.name]
 bpy.context.view_layer.update();t.pose.bones['WeaponSocket'].matrix=t.pose.bones['RightHand'].matrix@grip.inverted();bpy.context.view_layer.update()
 for b in t.pose.bones:
  q=b.rotation_quaternion.copy()
  if b.name in previous:q.make_compatible(previous[b.name])
  previous[b.name]=q.copy();b.rotation_quaternion=q
  for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
for layer in t.animation_data.action.layers:
 for st in layer.strips:
  for cb in st.channelbags:
   for fc in cb.fcurves:
    for kp in fc.keyframe_points:kp.interpolation='LINEAR'
for o in s.objects:o.select_set(False)
t.select_set(True)
for o in body:o.select_set(True)
bpy.context.view_layer.objects.active=t;name='Sourced_RollAttack_v2';path=OUT/name;assert not path.with_suffix('.glb').exists();s.frame_set(0)
with bpy.context.temp_override(window=bpy.context.window_manager.windows[0],active_object=t,object=t,selected_objects=[t]+body):
 bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
s['session_owner']=OWNER;s['source_composition']='Fab roll full1s prefix, Mixamo slash1.5s retimedto1.2s; .12s local-pose join; palm-locked sword'
bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
row={'name':name,'duration':2.2,'fps':FPS,'rollPrefixSeconds':1.0,'attackSourceDuration':1.5,'attackComposedDuration':1.2,'joinSeconds':.12,'sha256':hashlib.sha256(path.with_suffix('.glb').read_bytes()).hexdigest(),'sources':['Fab_Roll_v17','Mixamo_Attack_v17'],'gripMode':'one-handed'};path.with_suffix('.json').write_text(json.dumps(row,indent=2));print(json.dumps(row))
