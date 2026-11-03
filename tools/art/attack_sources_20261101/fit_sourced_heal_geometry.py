"""Fit the approved cup using measured socket coordinates and preserved CC0 wrist motion."""
import bpy,json,hashlib,math,sys,argparse
import numpy as np
from pathlib import Path
from mathutils import Matrix,Vector
parser=argparse.ArgumentParser();parser.add_argument('--helmet-fit',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'Local/AttackSources20261103/HealGeometry';OUT.mkdir(parents=True,exist_ok=True);DEST=OUT/('Quaternius_Heal_v6helmet' if args.helmet_fit else 'Quaternius_Heal_v5geometry');assert not DEST.with_suffix('.blend').exists()
APPROVED=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/Heal_Blender_v4.glb';SOURCE=ROOT/'Local/AttackSources20261102/QuaterniusRetarget/Exports/Quaternius_Consume_v1.blend';CUP=ROOT/'Local/CustomuseAssets/Polish20261025/props/DrinkingCup.glb'
measured=json.loads((ROOT/'docs/master-goal-20261103/heal-socket-basis.json').read_text());basis=Matrix(measured['samples'][0]['staticMeshLocalToBoneLocal']);assert max(abs(basis[i][j]-(1 if i==j else 0)) for i in range(4) for j in range(4))<1e-5
RIM=basis@Vector((.060,-.023,-.091));NORMAL=(basis.to_3x3()@Vector((0,-1,0))).normalized()
def smooth(x):x=max(0.,min(1.,x));return x*x*(3-2*x)
def mix(a,b,w):
 p,q,s=a.decompose();pp,qq,ss=b.decompose();return Matrix.LocRotScale(p.lerp(pp,w),q.slerp(qq,w),s.lerp(ss,w))
def world(r,n):return (r.matrix_world@r.pose.bones[n].matrix).copy()
helper=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(helper)};exec(compile(helper.read_text().split('reports=[]')[0],str(helper),'exec'),ns);solve=ns['solve']
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=120;bpy.ops.import_scene.gltf(filepath=str(APPROVED));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');scene=bpy.context.scene
scene.frame_set(42);bpy.context.view_layer.update();hold=world(rig,'LeftHand');grip=hold.inverted()@world(rig,'CupSocket');cup_normal=(hold@grip).to_3x3()@NORMAL;up_fix=cup_normal.normalized().rotation_difference(Vector((0,0,1)));hold_rotation=up_fix@hold.to_quaternion()
head_ref=world(rig,'Head');mouth_ref=head_ref.translation+Vector((0,-.10,.03));helmet_bounds=None
if args.helmet_fit:
 coords=[];deps=bpy.context.evaluated_depsgraph_get()
 for obj in scene.objects:
  if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):continue
  group=obj.vertex_groups.get('Head')
  if group is None:continue
  ids=[v.index for v in obj.data.vertices if any(g.group==group.index and g.weight>.75 for g in v.groups)]
  evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
  coords.extend([list(evaluated.matrix_world@mesh.vertices[i].co) for i in ids]);evaluated.to_mesh_clear()
 points=np.array(coords);assert len(points)>50
 lo,hi=points.min(0),points.max(0);x=float((lo[0]+hi[0])*.5);z=float(lo[2]+(hi[2]-lo[2])*.30)
 band=points[(abs(points[:,0]-x)<.025)&(abs(points[:,2]-z)<.015)];assert len(band)>10
 mouth_ref=Vector((x,float(np.quantile(band[:,1],.02))-.006,z));helmet_bounds=[lo.tolist(),hi.tolist()]
mouth_local=head_ref.inverted()@mouth_ref;face_local=head_ref.to_3x3().inverted()@Vector((0,-1,0))
fingers={b.name:b.matrix_basis.copy() for b in rig.pose.bones if b.name.startswith('LeftHand') and b.name!='LeftHand'};rest={b.name:b.matrix_local.copy() for b in rig.data.bones};approved=[]
for f in range(289):scene.frame_set(f);bpy.context.view_layer.update();approved.append({b.name:b.matrix_basis.copy() for b in rig.pose.bones})
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False);scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];original=rig.animation_data.action;end=scene.frame_end
rest_error=max(abs(rest[n][i][j]-rig.data.bones[n].matrix_local[i][j]) for n in rest for i in range(4) for j in range(4));assert rest_error<1e-4,('Pose basis mismatch',rest_error)
source_poses=[];source_hands=[]
for f in range(289):
 sf=f/288*end;scene.frame_set(int(sf),subframe=sf-int(sf));bpy.context.view_layer.update();source_poses.append({b.name:b.matrix_basis.copy() for b in rig.pose.bones});source_hands.append(world(rig,'LeftHand'))
initial_rotation=source_hands[0].to_quaternion();scene.render.fps=120;scene.render.fps_base=1;scene.frame_start=0;scene.frame_end=288;action=bpy.data.actions.new(DEST.stem);rig.animation_data.action=action;previous={};contacts=[];angles=[];cup_matrices=[]
moving={'LeftShoulder','LeftArm','LeftForeArm','LeftHand','Neck','Head'}
# Rim centre remains the measured mesh point. Its near edge, not the centre of
# the opening, meets the helmet, so the bowl need not penetrate the face.
rim_edge=RIM+Vector((0,0,.026))
for f in range(289):
 scene.frame_set(f);t=f/120;w=min(smooth(t/.2),smooth((2.4-t)/.2))
 for b in rig.pose.bones:
  b.rotation_mode='QUATERNION';b.matrix_basis=mix(approved[f][b.name],source_poses[f][b.name],w) if b.name in moving else approved[f][b.name]
  if b.name in fingers:b.matrix_basis=fingers[b.name]
 bpy.context.view_layer.update();current=world(rig,'LeftHand');source_rotation=source_hands[f].to_quaternion()@initial_rotation.inverted()@hold_rotation;desired_rotation=current.to_quaternion().slerp(source_rotation,w)
 contact=min(smooth(t/.8),smooth((2.4-t)/.8));head_matrix=world(rig,'Head');mouth=head_matrix@mouth_local if args.helmet_fit else head_matrix.translation+Vector((0,-.10,.03))
 if args.helmet_fit:
  face=(head_matrix.to_3x3()@face_local).normalized();raw_normal=(desired_rotation.to_matrix()@grip.to_3x3()@NORMAL).normalized();theta=math.acos(max(-1.,min(1.,raw_normal.z)));limit=math.radians(80);theta=limit*math.tanh(theta/limit)
  inward=Vector((-face.x,-face.y,0)).normalized();normal_goal=Vector((0,0,math.cos(theta)))+inward*math.sin(theta);correction=raw_normal.rotation_difference(normal_goal);desired_rotation=Matrix.Identity(3).to_quaternion().slerp(correction,contact)@desired_rotation
  cup_linear=Matrix.LocRotScale(Vector(),desired_rotation,current.to_scale()).to_3x3()@grip.to_3x3();normal=(cup_linear@NORMAL).normalized();toward=-(face-normal*face.dot(normal))
  if toward.length<1e-5:toward=Vector((0,0,-1))-normal*normal.dot(Vector((0,0,-1)))
  rim_edge=RIM+(cup_linear.inverted()@toward.normalized()).normalized()*.026
 rim_hand=grip@rim_edge;target=mouth-Matrix.LocRotScale(Vector(),desired_rotation,current.to_scale()).to_3x3()@rim_hand;position=current.translation.lerp(target,contact)
 old=[world(rig,'Left'+n) for n in ['Arm','ForeArm','Hand']];solved=solve(old,position);solved[-1]=Matrix.LocRotScale(position,desired_rotation,current.to_scale())
 for suffix,m in zip(['Arm','ForeArm','Hand'],solved):rig.pose.bones['Left'+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
 cup=world(rig,'LeftHand')@grip;location,rotation,scale=cup.decompose();visible=max(1e-5,min(smooth(t/.12),smooth((2.4-t)/.12)));rig.pose.bones['CupSocket'].matrix=rig.matrix_world.inverted()@Matrix.LocRotScale(location,rotation,scale*visible);bpy.context.view_layer.update()
 if contact>=1.-1e-7:contacts.append((cup@rim_edge-mouth).length)
 normal=(cup.to_3x3()@NORMAL).normalized();angles.append(math.degrees(math.acos(max(-1.,min(1.,normal.z)))));cup_matrices.append(world(rig,'CupSocket'))
 for b in rig.pose.bones:
  q=b.rotation_quaternion.copy()
  if b.name in previous:q.make_compatible(previous[b.name])
  b.rotation_quaternion=q;previous[b.name]=q.copy()
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
for layer in action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
(OUT/('fit-helmet-diagnostic.json' if args.helmet_fit else 'fit-diagnostic.json')).write_text(json.dumps({'fullContactSamples':len(contacts),'maxFullContactError':max(contacts,default=None),'maximumSipTiltDegrees':max(angles[48:240]),'minimumVisibleTiltDegrees':min(angles[24:264])},indent=2)+'\n')
assert max(contacts)<1e-5 and max(angles[48:240])>50,'Contact or visible tipping requirement not met'
scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in scene.objects:
 if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers):o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
# Real approved cup for editable visual review. Its imported mesh coordinates
# are converted back into the measured exported socket-local basis.
before=set(scene.objects);bpy.ops.import_scene.gltf(filepath=str(CUP));cup_obj=next(o for o in set(scene.objects)-before if o.type=='MESH');cup_obj.name='PREVIEW_ApprovedDrinkingCup';import_basis=cup_obj.matrix_world.copy();cup_obj.rotation_mode='QUATERNION';B=Matrix.Rotation(math.pi/2,4,'X')
for f,m in enumerate(cup_matrices):
 scene.frame_set(f);cup_obj.matrix_world=m@basis@B.inverted()@import_basis;cup_obj.keyframe_insert('location',frame=f);cup_obj.keyframe_insert('rotation_quaternion',frame=f);cup_obj.keyframe_insert('scale',frame=f)
scene.frame_set(144);bpy.ops.wm.save_as_mainfile(filepath=str(DEST.with_suffix('.blend')),compress=True)
report={'source':str(SOURCE.relative_to(ROOT)),'sourceSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'approvedCupSHA256':hashlib.sha256(CUP.read_bytes()).hexdigest(),'sha256':hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest(),'license':'CC0 Consume gesture; unchanged project-owned cup and support pose','duration':2.4,'fps':120,'restBasisMaximumError':rest_error,'measuredRimBoneLocal':list(RIM),'rimBasisCorrectionRequired':False,'approachChange':'Preserve source wrist rotation delta; calibrate upright grasp once; fit near rim by no-stretch IK without substituting the rejected old sip orientation','maxRimContactErrorSourceUnits':max(contacts),'contactSamples':len(contacts),'cupTiltDegreesMinMax':[min(angles[24:264]),max(angles[24:264])],'accepted':False,'nativeImported':False,'helmetLandmarkMeasured':args.helmet_fit,'helmetReferenceBounds':helmet_bounds,'mouthReferencePoint':list(mouth_ref),'sourceTiltAdaptation':'Source timing retained; soft80-degree limit and face-directed opening during contact' if args.helmet_fit else 'Original source rotation delta'}
DEST.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print('HEAL_SOURCE_ROTATION_AND_RIM_FITTED',flush=True)
