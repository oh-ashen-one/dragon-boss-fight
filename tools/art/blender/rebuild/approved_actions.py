"""Execute INSIDE the owned Blender MCP session. No external motion solver.

Reconstruct approved silhouettes as sparse editable Blender FK/control curves,
solve limbs with Blender native IK, then bake a separate deform action. The
approved source action remains a reference, never the export action.
"""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion

REPO = Path(__file__).resolve().parents[4]
ASSETS = REPO/'tools/asset-review/.asset-cache/review'
OUT = REPO/'Local/Blender/approved-rebuild-20261021'
OWNER = 'codex-veyr-walk-20261021'
SOURCE_RANGES = {}
SNAPSHOT_REFINER = None
JOBS = {
 'idle_one': ('IdleOneHand_Breathing_v3',4.,[0,.5,1,1.5,2,2.5,3,3.5,4],False),
 'idle_two': ('IdleTwoHand_ReadyBreath_v6',4.,[0,.5,1,1.5,2,2.5,3,3.5,4],True),
 'overhead': ('LightAttack_BlackKnightReference_v10',2.8,[0,.2,.35,.5,.6,.65,.72,.79,.83,.88,.94,1.05,1.3,1.84,2.15,2.4,2.65,2.8],False),
 'sweep': ('StrongAttackTwoHand_Sweep_v9',4.4/3,[x/3 for x in [0,.35,.8,1.15,1.4,1.75,2.05,2.4,2.8,3.5,4.4]],True),
 'thrust': ('StrongAttackTwoHand_Thrust_v7',6.92/3,[x/3 for x in [0,.4,1,1.6,1.95,2.25,2.6,3.2,4.6,5.65,6.92]],True),
 'light_two': ('LightAttackTwoHand_Compact_v1',1.1,[0,.1,.24,.33,.43,.54,.66,.83,1.1],True),
}

def at(f):
 bpy.context.scene.frame_set(int(f), subframe=f-int(f));bpy.context.view_layer.update()

def curves(action):
 return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]

def smooth(obj):
 if not obj.animation_data or not obj.animation_data.action:return
 obj.animation_data.action.use_fake_user=True
 for fc in curves(obj.animation_data.action):
  for k in fc.keyframe_points:
   k.interpolation='BEZIER';k.handle_left_type='AUTO_CLAMPED';k.handle_right_type='AUTO_CLAMPED'

def key(obj,f,previous):
 obj.rotation_mode='QUATERNION'
 q=obj.rotation_quaternion.copy()
 if obj.name in previous:q.make_compatible(previous[obj.name])
 obj.rotation_quaternion=q;previous[obj.name]=q.copy()
 for p in ('location','rotation_quaternion','scale'):obj.keyframe_insert(p,frame=f)

def empty(name,collection):
 o=bpy.data.objects.new(name,None);collection.objects.link(o)
 o.empty_display_type='PLAIN_AXES';o.empty_display_size=.06;o.rotation_mode='QUATERNION'
 return o

def prepare(job):
 scene=bpy.context.scene
 assert scene.get('session_owner')==OWNER
 stem,duration,times,two=JOBS[job]
 assert not (OUT/(job+'_Blender_v1.blend')).exists(),'Preserve candidate; use the saved scene to revise'
 if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 for o in list(scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 for collection in list(bpy.data.collections):
  if collection.name.startswith('AUTHORING_') and not collection.objects:bpy.data.collections.remove(collection)
 scene.render.fps=60;scene.render.fps_base=1
 bpy.ops.import_scene.gltf(filepath=str(ASSETS/(stem+'.glb')))
 rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.name='Knight_Deform'
 meshes=[o for o in scene.objects if o.type=='MESH']
 for o in meshes:o['export_body']=True
 source=rig.animation_data.action;source.name='REFERENCE_'+stem;source.use_fake_user=True
 old_socket=bpy.data.objects.get('ReviewWeaponSocket')
 # Bone attachment transforms use the imported glTF local basis unchanged.
 C=Matrix.Rotation(math.pi/2,4,'X')
 q=Quaternion((-.62364586,.78155554,.0047625,.01463231));q.normalize()
 grip=Vector((.0616763,-.00199617,.00555098))
 if two:grip+=q@Vector((0,.075*.4096359622825952,0))
 offset=Matrix.LocRotScale(grip,q,Vector((.4096359622825952,)*3))@C.inverted()
 snapshots=[]
 for t in times:
  start,finish=SOURCE_RANGES.get(job,(0,duration))
  at((start+t/duration*(finish-start))*60)
  poses={b.name:b.matrix.copy() for b in rig.pose.bones}
  bases={b.name:b.matrix_basis.copy() for b in rig.pose.bones}
  weapon=old_socket.matrix_world.copy() if old_socket else rig.matrix_world@poses['RightHand']@offset
  snapshots.append((t,poses,bases,weapon))
 if SNAPSHOT_REFINER:
  snapshots=SNAPSHOT_REFINER(rig,snapshots,job,offset)
 scene['rebuild_job']=job;scene['duration']=duration;scene['reference_sha256']=hashlib.sha256((ASSETS/(stem+'.glb')).read_bytes()).hexdigest()
 scene['source_action']=source.name;scene['two_hand']=two
 scene['authoring']='Sparse Blender FK poses, native four-limb IK, editable target/pole/hilt curves; baked separately'
 rig.animation_data_clear()
 if old_socket:bpy.data.objects.remove(old_socket,do_unlink=True)
 controls=bpy.data.collections.new('AUTHORING_'+job);scene.collection.children.link(controls)
 fk=rig.copy();fk.data=rig.data.copy();fk.name='Pose_Control_Rig';controls.objects.link(fk);fk.animation_data_clear();fk.show_in_front=True
 weapon=empty('Hilt_Control',controls)
 socket=empty('ReviewWeaponSocket',scene.collection)
 chains={s+k:tuple(s+n for n in names) for s in ('Left','Right') for k,names in [('Arm',('Arm','ForeArm','Hand')),('Leg',('UpLeg','Leg','Foot'))]}
 targets={};poles={}
 for label in chains:
  targets[label]=empty(label+'_Target',controls);poles[label]=empty(label+'_Pole',controls)
  if 'Arm' in label and (two or label.startswith('Right')):targets[label].parent=weapon
 prev={}
 for t,poses,bases,w in snapshots:
  f=t*60
  for b in fk.pose.bones:b.matrix_basis=bases[b.name];key(b,f,prev)
  weapon.matrix_world=w;key(weapon,f,prev)
  for label,names in chains.items():
   tar=targets[label];end=rig.matrix_world@poses[names[2]]
   tar.matrix_basis=w.inverted()@end if tar.parent else end
   key(tar,f,prev)
   a,m,z=[rig.matrix_world@poses[n].translation for n in names]
   axis=(z-a).normalized();direction=(m-a)-axis*(m-a).dot(axis)
   if direction.length<1e-5:direction=Vector((0,-1,0))
   poles[label].location=m+direction.normalized()*.3;key(poles[label],f,prev)
 for o in [fk,weapon,*targets.values(),*poles.values()]:smooth(o)
 fk.animation_data.action.name=job+'_EDITABLE_FK_POSES'
 # Anatomical IK bones point down each actual limb. Skin/rest matrices remain intact.
 data=bpy.data.armatures.new('Native_Anatomical_IK')
 ikrig=bpy.data.objects.new('Native_Anatomical_IK',data);controls.objects.link(ikrig)
 bpy.context.view_layer.objects.active=ikrig;ikrig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
 for label,names in chains.items():
  pts=[rig.matrix_world@snapshots[0][1][n].translation for n in names]
  a=data.edit_bones.new(label+'_Upper');a.head=pts[0];a.tail=pts[1]
  b=data.edit_bones.new(label+'_Lower');b.head=pts[1];b.tail=pts[2];b.parent=a;b.use_connect=True
 bpy.ops.object.mode_set(mode='OBJECT')
 for label in chains:
  c=ikrig.pose.bones[label+'_Lower'].constraints.new('IK');c.name='Blender anatomical '+label
  c.target=targets[label];c.pole_target=poles[label];c.chain_count=2;c.use_stretch=False;c.iterations=200
  for suffix in ('_Upper','_Lower'):ikrig.pose.bones[label+suffix].ik_stretch=0
 # Render-only approved sword; exported separately like the established viewer.
 swordfile='BoatGreatsword_StrongGrip_v1.glb' if job in ('sweep','thrust','light_two') else 'BoatGreatsword_Grip_v6.glb' if two else 'BoatGreatsword_OneHand_v4.glb'
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ASSETS/swordfile))
 imported=set(bpy.data.objects)-before
 for o in imported:
  if o.parent not in imported:o.parent=socket;o.matrix_basis=Matrix.Identity(4)
  o['review_attachment']=True
 scene.frame_start=0;scene.frame_end=round(duration*60);scene.render.fps_base=60*duration/scene.frame_end
 for i,t in enumerate(times):scene.timeline_markers.new('Pose %02d'%i,frame=round(t/duration*scene.frame_end))
 # Retiming only changes fractional terminal frame for thrust. Exact approved duration.
 ratio=scene.frame_end/(duration*60)
 for o in [fk,weapon,*targets.values(),*poles.values()]:
  for fc in curves(o.animation_data.action):
   for k in fc.keyframe_points:k.co.x*=ratio;k.handle_left.x*=ratio;k.handle_right.x*=ratio
 for o in controls.objects:o.hide_render=True
 scene['sword_file']=swordfile
 bpy.ops.object.camera_add(location=(2.4,-3.4,1.5));scene.camera=bpy.context.object;scene.camera.name='Review_Camera';scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=2.5
 scene.camera.rotation_euler=(Vector((0,-.1,.8))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
 scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100
 scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.04,.04,.04)
 if not two:wrist_follow()
 exact_sample_rate()
 print('Prepared native Blender controls:',job,len(times),'poses')

def bake():
 scene=bpy.context.scene;assert scene.get('session_owner')==OWNER
 job=scene['rebuild_job'];rig=bpy.data.objects['Knight_Deform'];fk=bpy.data.objects['Pose_Control_Rig'];ikrig=bpy.data.objects['Native_Anatomical_IK'];socket=bpy.data.objects['ReviewWeaponSocket'];weapon=bpy.data.objects['Hilt_Control']
 rig.animation_data_clear();socket.animation_data_clear();previous={};maxerror=0.;endpoint=[]
 chains={s+k:tuple(s+n for n in names) for s in ('Left','Right') for k,names in [('Arm',('Arm','ForeArm','Hand')),('Leg',('UpLeg','Leg','Foot'))]}
 for f in range(scene.frame_end+1):
  at(f);base={b.name:rig.matrix_world@b.matrix.copy() for b in fk.pose.bones};desired={n:m.copy() for n,m in base.items()}
  for label,names in chains.items():
   upper=ikrig.pose.bones[label+'_Upper'];upper.matrix=Matrix.Translation(base[names[0]].translation)@ikrig.data.bones[label+'_Upper'].matrix_local.to_3x3().to_4x4()
  bpy.context.view_layer.update()
  for label,names in chains.items():
   upper=ikrig.pose.bones[label+'_Upper'];lower=ikrig.pose.bones[label+'_Lower'];c=lower.constraints[0]
   start=upper.head.copy();axis=(c.target.matrix_world.translation-start).normalized();wanted=c.pole_target.matrix_world.translation-start;wanted-=axis*wanted.dot(axis);wanted.normalize()
   def error(value):
    c.pole_angle=(value+math.pi)%(2*math.pi)-math.pi;bpy.context.view_layer.update()
    d=lower.head-start;d-=axis*d.dot(axis);d.normalize()
    return math.atan2(axis.dot(d.cross(wanted)),d.dot(wanted))
   value=c.pole_angle
   for _ in range(12):
    e=error(value)
    if abs(e)<1e-6:break
    en=error(value+.001);derivative=((en-e+math.pi)%(2*math.pi)-math.pi)/.001
    if abs(derivative)<.05:derivative=-1
    value-=max(-.8,min(.8,e/derivative))
   error(value)
   pts=[upper.head.copy(),lower.head.copy(),lower.tail.copy()]
   for i in (0,1):
    old=(base[names[i+1]].translation-base[names[i]].translation).normalized();new=(pts[i+1]-pts[i]).normalized()
    desired[names[i]]=Matrix.LocRotScale(pts[i],old.rotation_difference(new)@base[names[i]].to_quaternion(),base[names[i]].to_scale())
   desired[names[2]]=c.target.matrix_world.copy()
   maxerror=max(maxerror,(pts[2]-desired[names[2]].translation).length)
   delta=desired[names[2]]@base[names[2]].inverted()
   for child in rig.pose.bones[names[2]].children_recursive:desired[child.name]=delta@base[child.name]
  for b in rig.pose.bones:
   b.matrix=rig.matrix_world.inverted()@desired[b.name];bpy.context.view_layer.update();key(b,f,previous)
  socket.matrix_world=weapon.matrix_world;key(socket,f,previous)
  if f in (0,scene.frame_end):endpoint.append(max(max(abs(desired[n][i][j]-base[n][i][j]) for i in range(4) for j in range(4)) for n in base))
 rig.animation_data.action.name=job+'_Blender_v1_BAKED';socket.animation_data.action.name=job+'_Blender_v1_SOCKET'
 for o in (rig,socket):
  for fc in curves(o.animation_data.action):
   for k in fc.keyframe_points:k.interpolation='LINEAR'
 for o in bpy.data.collections['AUTHORING_'+job].objects:o.hide_set(True)
 at(0)
 text=bpy.data.texts.get('approved_actions.py') or bpy.data.texts.new('approved_actions.py');text.clear();text.write(Path(__file__).read_text())
 OUT.mkdir(parents=True,exist_ok=True)
 bpy.data.orphans_purge(do_recursive=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(job+'_Blender_v1.blend')),compress=True)
 for o in scene.objects:o.select_set(False)
 for o in scene.objects:
  if o==rig or o==socket or o.get('export_body'):o.select_set(True)
 bpy.context.view_layer.objects.active=rig
 out=OUT/(job+'_Blender_v1.glb')
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
  bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=job+'_Blender_v1',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 report={'job':job,'duration':scene['duration'],'source':JOBS[job][0],'sourceSHA256':scene['reference_sha256'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'nativeIKError':maxerror,'endpointMatrixDelta':endpoint,'sparsePoses':len(JOBS[job][2]),'ownerApproved':False,'visualReview':'pending','blender':bpy.app.version_string}
 (OUT/(job+'-report.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))

def wrist_follow():
 """Native bone constraint keeps a one-hand weapon on its FK wrist arc."""
 scene=bpy.context.scene;assert not scene['two_hand'];at(0)
 fk=bpy.data.objects['Pose_Control_Rig'];weapon=bpy.data.objects['Hilt_Control']
 offset=(fk.matrix_world@fk.pose.bones['RightHand'].matrix).inverted()@weapon.matrix_world
 follow=empty('Right_Wrist_Follow',bpy.data.collections['AUTHORING_'+scene['rebuild_job']])
 c=follow.constraints.new('COPY_TRANSFORMS');c.target=fk;c.subtarget='RightHand'
 weapon.animation_data_clear();weapon.parent=follow;weapon.matrix_basis=offset
 weapon['purpose']='Editable local hilt placement on native FK wrist constraint'
 for f in (0,scene.frame_end):key(weapon,f,{})
 smooth(weapon)

def exact_sample_rate():
 """150 Hz gives every approved duration an integer end frame, with no fps_base ambiguity."""
 scene=bpy.context.scene;end=round(scene['duration']*150);ratio=end/scene.frame_end
 seen=set()
 for o in bpy.data.collections['AUTHORING_'+scene['rebuild_job']].objects:
  if not o.animation_data or not o.animation_data.action:continue
  action=o.animation_data.action
  if action.name in seen:continue
  seen.add(action.name)
  for fc in curves(action):
   for k in fc.keyframe_points:k.co.x*=ratio;k.handle_left.x*=ratio;k.handle_right.x*=ratio
 for marker in scene.timeline_markers:marker.frame=round(marker.frame*ratio)
 scene.frame_end=end;scene.render.fps=150;scene.render.fps_base=1
