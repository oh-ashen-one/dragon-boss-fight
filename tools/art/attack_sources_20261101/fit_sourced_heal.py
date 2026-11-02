"""Fit the existing handled cup to CC0 Consume; retain the game's heal duration."""
import bpy,json,hashlib,math,argparse,sys
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Local/AttackSources20261102/QuaterniusRetarget/Exports'
parser=argparse.ArgumentParser();parser.add_argument('--version',default='v2');parser.add_argument('--fit-rim',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert args.version.isalnum()
source=OUT/'Quaternius_Consume_v1.blend';dest=OUT/f'Quaternius_Heal_{args.version}'
assert not dest.with_suffix('.blend').exists()
def smooth(x):
    x=max(0.,min(1.,x));return x*x*(3-2*x)
def mix(a,b,w):
    p,q,s=a.decompose();pp,qq,ss=b.decompose();return Matrix.LocRotScale(p.lerp(pp,w),q.slerp(qq,w),s.lerp(ss,w))
def pose(rig):return {b.name:b.matrix_basis.copy() for b in rig.pose.bones}
def world(rig,n):return (rig.matrix_world@rig.pose.bones[n].matrix).copy()
approved=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/Heal_Blender_v4.glb'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=120
bpy.ops.import_scene.gltf(filepath=str(approved));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
scene=bpy.context.scene;scene.frame_set(144);bpy.context.view_layer.update()
cup_grip=world(rig,'LeftHand').inverted()@world(rig,'CupSocket')
fingers={b.name:b.matrix_basis.copy() for b in rig.pose.bones if b.name.startswith('LeftHand') and b.name!='LeftHand'}
approved_poses=[];approved_hands=[]
for f in range(289):
    scene.frame_set(f);approved_poses.append(pose(rig));approved_hands.append(world(rig,'LeftHand'))
helper=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(helper)}
exec(compile(helper.read_text().split('reports=[]')[0],str(helper),'exec'),ns)
solve=ns['solve'];rim_local=Vector((.060,-.023,-.091));rim_hand=cup_grip@rim_local
bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False);scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];original=rig.animation_data.action
source_fps=scene.render.fps/scene.render.fps_base;source_end=scene.frame_end;source_poses=[]
for f in range(289):
    sf=(f/288)*source_end;scene.frame_set(int(sf),subframe=sf-int(sf));bpy.context.view_layer.update();source_poses.append(pose(rig))
scene.render.fps=120;scene.render.fps_base=1;scene.frame_start=0;scene.frame_end=288
action=bpy.data.actions.new(f'Quaternius_Heal_{args.version}_FittedCup');rig.animation_data.action=action;previous={};contacts=[]
moving={'LeftShoulder','LeftArm','LeftForeArm','LeftHand','Neck','Head'}
for f in range(289):
    scene.frame_set(f);t=f/120;weight=min(smooth(t/.20),smooth((2.4-t)/.20))
    for b in rig.pose.bones:
        b.rotation_mode='QUATERNION'
        b.matrix_basis=mix(approved_poses[f][b.name],source_poses[f][b.name],weight) if b.name in moving else approved_poses[f][b.name]
        if b.name in fingers:b.matrix_basis=fingers[b.name]
    bpy.context.view_layer.update()
    if args.fit_rim:
        contact=min(smooth(t/.8),smooth((2.4-t)/.8))
        current=world(rig,'LeftHand');desired=mix(current,approved_hands[f],contact)
        head=world(rig,'Head').translation;mouth=head+Vector((0,-.10,.03))
        target=mouth-desired.to_3x3()@rim_hand
        desired.translation=current.translation.lerp(target,contact)
        old=[world(rig,'Left'+n) for n in ['Arm','ForeArm','Hand']]
        solved=solve(old,desired.translation);solved[-1]=desired
        for suffix,m in zip(['Arm','ForeArm','Hand'],solved):
            rig.pose.bones['Left'+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
        if contact>.999:contacts.append((world(rig,'LeftHand')@rim_hand-mouth).length)
    cup=world(rig,'LeftHand')@cup_grip
    # Keep a nonsingular transform for canonical decomposition; runtime's
    # existing visibility threshold still hides this tiny endpoint scale.
    location,rotation,scale=cup.decompose();visible=max(1e-5,min(smooth(t/.12),smooth((2.4-t)/.12)))
    rig.pose.bones['CupSocket'].matrix=rig.matrix_world.inverted()@Matrix.LocRotScale(location,rotation,scale*visible);bpy.context.view_layer.update()
    for b in rig.pose.bones:
        q=b.rotation_quaternion.copy()
        if b.name in previous:q.make_compatible(previous[b.name])
        b.rotation_quaternion=q;previous[b.name]=q.copy()
        for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(0)
for o in scene.objects:o.select_set(False)
rig.select_set(True)
for o in scene.objects:
    if o.type=='MESH' and not o.hide_render:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
dest.with_suffix('.json').write_text(json.dumps({'source':str(source),'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),'license':'CC0 source motion; existing project-owned cup and approved support pose','duration':2.4,'fps':120,'corrections':'Consume retimed to unchanged heal duration; existing legs/right sword carry; retained cup grip and finger hold; 0.2s endpoint joins; 120Hz rigid cup attachment','fittedRimToHelmetFront':args.fit_rim,'contactSamples':len(contacts),'maxRimContactErrorWorld':max(contacts,default=None),'accepted':False},indent=2)+'\n')
print('VEYR_SOURCED_HEAL_FITTED',flush=True)
