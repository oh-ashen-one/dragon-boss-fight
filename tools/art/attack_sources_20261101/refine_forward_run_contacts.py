"""Refine licensed forward-run contacts in Blender, preserving timing and travel.

A stance is measured from the source's low sole and low world-space toe speed.
Only those brief intervals are anchored; swing poses remain free. Both sole
heights are calibrated from the actual deformed knight mesh, not joint height.
"""
import bpy,json,hashlib,math,sys
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'Local/AttackSources20261103/LocomotionContacts/Mixamo_ForwardRun_v2contacts.blend'
RIGID='--rigid-stance' in sys.argv
OUT=ROOT/('Local/AttackSources20261103/ForwardRigidPlants' if RIGID else 'Local/AttackSources20261103/ForwardPlants');OUT.mkdir(parents=True,exist_ok=True)
NAME='Mixamo_ForwardRun_v4rigid' if RIGID else 'Mixamo_ForwardRun_v3plants';DEST=OUT/NAME
assert not DEST.with_suffix('.blend').exists(),'Preserve existing source candidate'
h=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(h)};exec(compile(h.read_text().split('reports=[]')[0],str(h),'exec'),ns);solve=ns['solve']
def world(r,n):return (r.matrix_world@r.pose.bones[n].matrix).copy()
def smooth(x):x=max(0.,min(1.,x));return x*x*(3-2*x)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False)
s=bpy.context.scene;r=bpy.data.objects['Knight_Comparison'];original=r.animation_data.action
fps=s.render.fps/s.render.fps_base;end=s.frame_end;assert s.frame_start==0 and end>=12
sides=['Left','Right'];meshes=[]
for o in s.objects:
 if o.type!='MESH' or not any(m.type=='ARMATURE' and m.object==r for m in o.modifiers):continue
 ids={}
 for side in sides:
  groups={g.index for g in o.vertex_groups if g.name in (side+'Foot',side+'ToeBase')}
  ids[side]=[v.index for v in o.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>.5]
 if any(ids.values()):meshes.append((o,ids))
assert all(sum(len(ids[side]) for _,ids in meshes)>20 for side in sides)
frames=[];deps=bpy.context.evaluated_depsgraph_get()
for f in range(end+1):
 s.frame_set(f);bpy.context.view_layer.update();sole={side:float('inf') for side in sides}
 for o,ids in meshes:
  evaluated=o.evaluated_get(deps);mesh=evaluated.to_mesh()
  assert len(mesh.vertices)==len(o.data.vertices),'Contact geometry topology changed'
  for side in sides:
   if ids[side]:sole[side]=min(sole[side],min((evaluated.matrix_world@mesh.vertices[i].co).z for i in ids[side]))
  evaluated.to_mesh_clear()
 frames.append({'basis':{b.name:b.matrix_basis.copy() for b in r.pose.bones},'sole':sole,'toe':{side:world(r,side+'ToeBase').translation for side in sides},'foot':{side:world(r,side+'Foot') for side in sides},'hip':world(r,'Hips').translation,'grip':r.pose.bones['RightHand'].matrix.inverted()@r.pose.bones['WeaponSocket'].matrix})
net=frames[-1]['hip']-frames[0]['hip'];net.z=0.;duration=end/fps;speed=net.length/duration;assert speed>.2
minimum={side:min(f['sole'][side] for f in frames[:-1]) for side in sides};floor=min(minimum.values());bias={side:floor-minimum[side] for side in sides}
rigid_targets={side:{} for side in sides}
corrections={side:[Vector() for _ in range(end)] for side in sides};weights={side:[0. for _ in range(end)] for side in sides};groups_report={}
for side in sides:
 toe=[f['toe'][side] for f in frames[:-1]];mask=[]
 for i in range(end):
  before=toe[(i-1)%end]-(net if i==0 else Vector());after=toe[(i+1)%end]+(net if i==end-1 else Vector());v=(after-before)*fps*.5;v.z=0
  if RIGID:
   # Use both low ankle and low toe to identify the whole planted phase,
   # including touchdown. The earlier toe-only window began too late.
   ankles=sorted(f['foot'][side].translation.z for f in frames[:-1]);toes=sorted(f['toe'][side].z for f in frames[:-1]);q=round((end-1)*.1)
   mask.append(frames[i]['foot'][side].translation.z<=ankles[q]+.0102 and frames[i]['toe'][side].z<=toes[q]+.0102)
  else:mask.append(frames[i]['sole'][side]<=minimum[side]+.008 and v.length<speed*.45)
 assert any(mask) and not all(mask),side+' requires a distinct stance and swing'
 start=next(i for i,x in enumerate(mask) if not x);groups=[];group=[]
 for k in range(start+1,start+end+1):
  if mask[k%end]:group.append(k)
  elif group:
   if len(group)>=2:groups.append(group)
   group=[]
 if group and len(group)>=2:groups.append(group)
 assert groups,side+' has no usable contact interval'
 groups_report[side]=[[k%end for k in g] for g in groups]
 for group in groups:
  if RIGID:
   ref=min(group,key=lambda k:frames[k%end]['foot'][side].translation.z)
   planted=frames[ref%end]['foot'][side].copy();planted.translation+=net*(ref//end)
   planted.translation.z+=floor-frames[ref%end]['sole'][side]
   toe_basis=frames[ref%end]['basis'][side+'ToeBase']
   for k in range(group[0]-3,group[-1]+4):
    distance=max(group[0]-k,k-group[-1],0);weight=1. if not distance else 1-smooth(distance/4)
    i=k%end;target=planted.copy();target.translation-=net*(k//end)
    if weight>weights[side][i]:
     weights[side][i]=weight;rigid_targets[side][i]=(target,toe_basis,weight)
   continue
  points=[toe[k%end]+net*(k//end) for k in group];anchor=Vector((sum(p.x for p in points)/len(points),sum(p.y for p in points)/len(points),0))
  for k in range(group[0]-2,group[-1]+3):
   distance=max(group[0]-k,k-group[-1],0);weight=1. if not distance else 1-smooth(distance/3)
   i=k%end;delta=anchor-(toe[i]+net*(k//end));delta.z=0
   if weight>weights[side][i]:weights[side][i]=weight;corrections[side][i]=delta*weight
 assert max(v.length for v in corrections[side])<.08,'Excessive planar retarget correction'
action=original.copy();action.name=NAME;r.animation_data.action=action;previous={};max_shift=0.;max_error=0.;max_length_error=0.
for f,data in enumerate(frames):
 s.frame_set(f)
 for b in r.pose.bones:b.rotation_mode='QUATERNION';b.matrix_basis=data['basis'][b.name]
 bpy.context.view_layer.update();targets={side:data['foot'][side].translation+corrections[side][f%end]+Vector((0,0,bias[side])) for side in sides}
 desired_feet={}
 if RIGID:
  for side in sides:
   target,toe_basis,weight=rigid_targets[side].get(f%end,(data['foot'][side],data['basis'][side+'ToeBase'],0.))
   target=target.copy()
   if f==end:target.translation+=net
   current=data['foot'][side];desired_feet[side]=Matrix.LocRotScale(current.translation.lerp(target.translation,weight),current.to_quaternion().slerp(target.to_quaternion(),weight),current.to_scale())
   targets[side]=desired_feet[side].translation
   original_toe=data['basis'][side+'ToeBase'];r.pose.bones[side+'ToeBase'].matrix_basis=Matrix.LocRotScale(original_toe.translation,original_toe.to_quaternion().slerp(toe_basis.to_quaternion(),weight),original_toe.to_scale())
  bpy.context.view_layer.update()
 chains={side:[world(r,side+n) for n in ['UpLeg','Leg','Foot']] for side in sides};shift=Vector()
 for _ in range(80):
  for side,chain in chains.items():
   limit=sum((chain[i+1].translation-chain[i].translation).length for i in range(2))-.0001;delta=targets[side]-chain[0].translation-shift
   if delta.length>limit:shift+=delta.normalized()*(delta.length-limit)
 assert shift.length<.08,'Excessive pelvis reach correction'
 hip=world(r,'Hips');hip.translation+=shift;r.pose.bones['Hips'].matrix=r.matrix_world.inverted()@hip;bpy.context.view_layer.update();max_shift=max(max_shift,shift.length)
 for side in sides:
  chain=[world(r,side+n) for n in ['UpLeg','Leg','Foot']];lengths=[(chain[i+1].translation-chain[i].translation).length for i in range(2)]
  solved=solve(chain,targets[side])
  if RIGID:solved[2]=desired_feet[side]
  for suffix,m in zip(['UpLeg','Leg','Foot'],solved):r.pose.bones[side+suffix].matrix=r.matrix_world.inverted()@m;bpy.context.view_layer.update()
  result=[world(r,side+n) for n in ['UpLeg','Leg','Foot']];max_error=max(max_error,(result[2].translation-targets[side]).length);max_length_error=max(max_length_error,max(abs((result[i+1].translation-result[i].translation).length-lengths[i]) for i in range(2)))
 # The socket is an independent root child: carry the original hand-relative
 # grip with the corrected pelvis, instead of leaving the sword behind.
 r.pose.bones['WeaponSocket'].matrix=r.pose.bones['RightHand'].matrix@data['grip'];bpy.context.view_layer.update()
 for b in r.pose.bones:
  q=b.rotation_quaternion.copy()
  if b.name in previous:q.make_compatible(previous[b.name])
  b.rotation_quaternion=q;previous[b.name]=q.copy()
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
assert max_error<1e-5 and max_length_error<1e-5
for layer in action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for curve in bag.fcurves:
    for k in curve.keyframe_points:k.interpolation='LINEAR'
s.frame_set(0);bpy.ops.object.select_all(action='DESELECT');r.select_set(True)
for o in s.objects:
 if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==r for m in o.modifiers):o.select_set(True)
bpy.context.view_layer.objects.active=r
bpy.ops.export_scene.gltf(filepath=str(DEST.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(DEST.with_suffix('.blend')),compress=True)
report={'source':str(SOURCE.relative_to(ROOT)),'sourceSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'sha256':hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest(),'duration':duration,'fps':fps,'sourcePlanarTravel':list(net),'soleBiasSourceUnits':bias,'stanceFrames':groups_report,'maxPelvisShiftSourceUnits':max_shift,'maxTargetErrorSourceUnits':max_error,'maxLimbLengthErrorSourceUnits':max_length_error,'sourceUpperLocalMotionAndTimingPreserved':True,'handRelativeSocketPreserved':True,'stanceCorrection':'Full boot orientation and ankle anchor during measured plant, with free sourced swing' if RIGID else 'Toe anchor only','nativeImported':False,'accepted':False}
DEST.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
# A real reference ground exposes floating/sliding in review; added after export.
if RIGID:
 bpy.ops.mesh.primitive_plane_add(size=12,location=(0,0,floor-.0005));ground=bpy.context.object;ground.name='ContactReviewGround';ground.color=(.18,.20,.22,1)
 mat=bpy.data.materials.new('ContactReviewGround');mat.diffuse_color=ground.color;ground.data.materials.append(mat)
 for axis in range(2):
  for i in range(-12,13):
   curve=bpy.data.curves.new('GridLine','CURVE');curve.dimensions='3D';curve.bevel_depth=.001;line=curve.splines.new('POLY');line.points.add(1)
   line.points[0].co=(-6,i*.25,floor+.0002,1) if axis==0 else (i*.25,-6,floor+.0002,1)
   line.points[1].co=(6,i*.25,floor+.0002,1) if axis==0 else (i*.25,6,floor+.0002,1)
   obj=bpy.data.objects.new('GridLine',curve);s.collection.objects.link(obj)
h=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';review={'__file__':str(h)};exec(compile(h.read_text(),str(h),'exec'),review);review['OUT']=OUT;review['render'](NAME,[round(end*i/8) for i in range(9)])
print('FORWARD_RUN_CONTACT_CANDIDATE_EXPORTED',flush=True)
