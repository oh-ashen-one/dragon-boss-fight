"""Match retargeted feet to licensed source trajectories with no-stretch leg IK.

This is a contact/retarget correction: timing, upper body, source foot paths and
foot orientation are retained. A bounded common pelvis translation is permitted
only to keep both original-length leg chains reachable. Fail rather than stretch.
"""
import bpy,json,hashlib,math,argparse,sys
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3]
helper=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(helper)};exec(compile(helper.read_text().split('reports=[]')[0],str(helper),'exec'),ns);solve=ns['solve']
SOURCES=[ROOT/'Local/AttackSources20261103/ForwardRun/Exports/Mixamo_ForwardRun_v1.blend']+[ROOT/'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports'/('Mixamo_'+n+'_v1.blend') for n in ['RunStopOneHand','RunStopTwoHand']]
OUT=ROOT/'Local/AttackSources20261103/LocomotionContacts';OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-directory',type=Path)
parser.add_argument('--output',type=Path)
parser.add_argument('--suffix',default='_v2contacts')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.source_directory:
 directory=args.source_directory.resolve(strict=True);assert directory.is_relative_to(ROOT/'Local') and args.output
 SOURCES=sorted(directory.glob('*.blend'));assert SOURCES
if args.output:
 OUT=args.output.resolve();assert OUT.is_relative_to(ROOT/'Local');OUT.mkdir(parents=True,exist_ok=True)
assert args.suffix.startswith('_v') and args.suffix.replace('_','').isalnum()
def world(rig,name):return (rig.matrix_world@rig.pose.bones[name].matrix).copy()
def legs(rig,side):return [world(rig,side+n) for n in ['UpLeg','Leg','Foot']]
reports=[]
for source in SOURCES:
 name=source.stem.rsplit('_v',1)[0]+args.suffix;dest=OUT/name;assert not dest.with_suffix('.blend').exists()
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False);scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];src=bpy.data.objects['Source_mixamo'];original=rig.animation_data.action;original.use_fake_user=True
 scale=float(scene['retarget_scale']);source_start=round(src.animation_data.action.frame_range[0]);end=scene.frame_end
 source_rest={n:(src.matrix_world@src.data.bones['mixamorig:'+n].matrix_local).copy() for n in ['Hips','LeftFoot','RightFoot']}
 target_rest={n:(rig.matrix_world@rig.data.bones[n].matrix_local).copy() for n in ['Hips','LeftFoot','RightFoot']}
 scene.frame_set(source_start);bpy.context.view_layer.update();first=world(src,'mixamorig:Hips').translation;offset=first-source_rest['Hips'].translation;offset.z=0
 frames=[]
 for f in range(end+1):
  scene.frame_set(source_start+f);bpy.context.view_layer.update();targets={side:target_rest[side+'Foot'].translation+(world(src,'mixamorig:'+side+'Foot').translation-source_rest[side+'Foot'].translation-offset)*scale for side in ['Left','Right']}
  rig.animation_data.action=original;scene.frame_set(f);bpy.context.view_layer.update();frames.append((targets,{b.name:b.matrix_basis.copy() for b in rig.pose.bones},rig.pose.bones['RightHand'].matrix.inverted()@rig.pose.bones['WeaponSocket'].matrix))
 action=original.copy();action.name=name;rig.animation_data.action=action;previous={};measurements=[]
 for f,(targets,bases,grip) in enumerate(frames):
  scene.frame_set(f)
  for b in rig.pose.bones:b.matrix_basis=bases[b.name]
  bpy.context.view_layer.update();chains={side:legs(rig,side) for side in ['Left','Right']};shift=Vector()
  for _ in range(80):
   for side,w in chains.items():
    limit=sum((w[i+1].translation-w[i].translation).length for i in range(2))-.0001;delta=targets[side]-w[0].translation-shift
    if delta.length>limit:shift+=delta.normalized()*(delta.length-limit)
  if shift.length>.08:raise ValueError(f'{name} frame {f}: excessive pelvis compensation {shift.length:.4f}; source-fit rejected')
  hip=world(rig,'Hips');hip.translation+=shift;rig.pose.bones['Hips'].matrix=rig.matrix_world.inverted()@hip;bpy.context.view_layer.update()
  for side in ['Left','Right']:
   chain=legs(rig,side);length=sum((chain[i+1].translation-chain[i].translation).length for i in range(2));target=targets[side]
   if (chain[2].translation-target).length<1e-7:continue
   solved=solve(chain,target)
   for suffix,m in zip(['UpLeg','Leg','Foot'],solved):rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
   after=legs(rig,side);error=(after[2].translation-target).length;length_error=abs(sum((after[i+1].translation-after[i].translation).length for i in range(2))-length)
   if error>1e-5 or length_error>1e-5:raise ValueError('No-stretch/source-foot invariant failed')
  # Preserve the original hand-relative socket through a pelvis reach correction.
  rig.pose.bones['WeaponSocket'].matrix=rig.pose.bones['RightHand'].matrix@grip;bpy.context.view_layer.update()
  for b in rig.pose.bones:
   q=b.rotation_quaternion.copy()
   if b.name in previous:q.make_compatible(previous[b.name])
   b.rotation_quaternion=q;previous[b.name]=q.copy()
   for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
  measurements.append({'frame':f,'pelvisShiftSourceUnits':shift.length})
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for curve in bag.fcurves:
     for key in curve.keyframe_points:key.interpolation='LINEAR'
 scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
 for o in scene.objects:
  if o.type=='MESH' and not o.hide_render and o.name!='Review_BoatSword':
   if any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers):o.select_set(True)
 bpy.context.view_layer.objects.active=rig
 bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
 report={'source':str(source.relative_to(ROOT)),'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),'maxPelvisShiftSourceUnits':max(m['pelvisShiftSourceUnits'] for m in measurements),'sourceFootPathsMatched':True,'handRelativeWeaponPreserved':True,'limbStretchAllowed':False,'authoringApplication':'Blender','editableScene':str(dest.with_suffix('.blend').relative_to(ROOT)),'editableSceneSHA256':hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),'nativeIntegrated':False,'accepted':False};dest.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
print('SOURCED_LOCOMOTION_CONTACTS_PREPARED',len(reports),flush=True)
