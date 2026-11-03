"""Reuse the cleaner licensed stop footwork beneath the licensed two-hand upper-body stop."""
import bpy,json,hashlib
from pathlib import Path
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'Local/AttackSources20261103/LocomotionContacts'
LOWER=BASE/'Mixamo_RunStopOneHand_v2contacts.blend';UPPER=BASE/'Mixamo_RunStopTwoHand_v2contacts.blend';OUT=BASE/'Mixamo_RunStopTwoHand_v3composed';assert not OUT.with_suffix('.blend').exists()
names=['VeyrRoot','Hips']+[side+n for side in ['Left','Right'] for n in ['UpLeg','Leg','Foot','ToeBase']]
bpy.ops.wm.open_mainfile(filepath=str(LOWER),load_ui=False);s=bpy.context.scene;r=bpy.data.objects['Knight_Comparison'];fps=s.render.fps/s.render.fps_base;end=s.frame_end;rest={b.name:b.matrix_local.copy() for b in r.data.bones};lower=[]
for f in range(end+1):s.frame_set(f);bpy.context.view_layer.update();lower.append({n:r.pose.bones[n].matrix_basis.copy() for n in names})
bpy.ops.wm.open_mainfile(filepath=str(UPPER),load_ui=False);s=bpy.context.scene;r=bpy.data.objects['Knight_Comparison'];original=r.animation_data.action
assert set(rest)==set(r.data.bones.keys()) and max(abs(rest[n][i][j]-r.data.bones[n].matrix_local[i][j]) for n in rest for i in range(4) for j in range(4))<1e-6
upper=[];upper_end=s.frame_end
for f in range(end+1):
 t=upper_end*f/end;s.frame_set(int(t),subframe=t-int(t));bpy.context.view_layer.update();upper.append(({b.name:b.matrix_basis.copy() for b in r.pose.bones},r.pose.bones['RightHand'].matrix.inverted()@r.pose.bones['WeaponSocket'].matrix))
s.render.fps=60;s.render.fps_base=1;s.frame_start=0;s.frame_end=end;action=bpy.data.actions.new(OUT.stem);r.animation_data.action=action;previous={}
for f,(pose,grip) in enumerate(upper):
 s.frame_set(f)
 for b in r.pose.bones:b.rotation_mode='QUATERNION';b.matrix_basis=lower[f][b.name] if b.name in names else pose[b.name]
 bpy.context.view_layer.update();r.pose.bones['WeaponSocket'].matrix=r.pose.bones['RightHand'].matrix@grip;bpy.context.view_layer.update()
 for b in r.pose.bones:
  q=b.rotation_quaternion.copy()
  if b.name in previous:q.make_compatible(previous[b.name])
  b.rotation_quaternion=q;previous[b.name]=q.copy()
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
for layer in action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
s.frame_set(0);bpy.ops.object.select_all(action='DESELECT');r.select_set(True)
for o in s.objects:
 if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==r for m in o.modifiers):o.select_set(True)
bpy.context.view_layer.objects.active=r
bpy.ops.export_scene.gltf(filepath=str(OUT.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT.with_suffix('.blend')),compress=True)
OUT.with_suffix('.json').write_text(json.dumps({'lowerSourceSHA256':hashlib.sha256(LOWER.read_bytes()).hexdigest(),'upperSourceSHA256':hashlib.sha256(UPPER.read_bytes()).hexdigest(),'sha256':hashlib.sha256(OUT.with_suffix('.glb').read_bytes()).hexdigest(),'duration':end/fps,'sourceComposition':'One-hand stop pelvis/legs under retimed two-hand stop upper body; exact source hand-relative weapon transform preserved','wholeMotionAuthoredFromScratch':False,'accepted':False},indent=2)+'\n')
print('SOURCED_TWO_HAND_STOP_COMPOSED',flush=True)
