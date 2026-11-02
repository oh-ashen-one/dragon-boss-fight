"""Blender correction of sourced heavy contacts and idle joins; retain the source strike."""
import bpy, json, hashlib, math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget/Exports'
source = OUT/'Kevin_Heavy_M_v7.blend'
dest = OUT/'Kevin_Heavy_M_v8'
assert not dest.with_suffix('.blend').exists()
helper = Path(__file__).with_name('fit_paired_grip.py')
ns = {'__file__': str(helper)}
exec(compile(helper.read_text().split('reports=[]')[0], str(helper), 'exec'), ns)
solve, chain, paired_shift = ns['solve'], ns['chain'], ns['paired_shift']

def smooth(x):
    x = min(1., max(0., x))
    return x*x*(3-2*x)

def mix(a,b,w):
    p,q,s=a.decompose(); pp,qq,ss=b.decompose()
    return Matrix.LocRotScale(p.lerp(pp,w), q.slerp(qq,w), s.lerp(ss,w))

def pose(rig):
    return {b.name:b.matrix_basis.copy() for b in rig.pose.bones}

def world(rig,n):
    return (rig.matrix_world@rig.pose.bones[n].matrix).copy()

idle_path=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(idle_path))
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
bpy.context.scene.frame_set(0);bpy.context.view_layer.update()
idle=pose(rig); idle_feet={s:world(rig,s+'Foot') for s in ['Left','Right']}
idle_grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
inv=rig.data.bones['LeftHand'].matrix_local.inverted()
points={n:inv@rig.data.bones['LeftHand'+n].head_local for n in ['Index','Pinky','Middle']}
longitudinal=points['Middle'].normalized();blade=(points['Index']-points['Pinky']).normalized()
across=(longitudinal-blade*longitudinal.dot(blade)).normalized()
palm=(points['Index']+points['Pinky'])*.5-across*.010
idle_palm=world(rig,'WeaponSocket').inverted()@(world(rig,'LeftHand')@palm)

source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
rig=bpy.data.objects['Knight_Comparison'];scene=bpy.context.scene;original=rig.animation_data.action
scene.frame_set(0);bpy.context.view_layer.update()
source_feet={s:world(rig,s+'Foot') for s in ['Left','Right']}
source_grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
original_fps=scene.render.fps/scene.render.fps_base
fps=120; intro=.45; strike=1.6; outro=.65; total=int(round((intro+strike+outro)*fps))
samples=[]
for f in range(total+1):
    t=f/fps; st=max(0.,min(strike,t-intro))*original_fps
    rig.animation_data.action=original;scene.frame_set(int(st),subframe=st-int(st));bpy.context.view_layer.update()
    samples.append(pose(rig))
scene.render.fps=fps;scene.render.fps_base=1;scene.frame_start=0;scene.frame_end=total
action=bpy.data.actions.new('Kevin_Heavy_M_v8_ContactAndIdleJoins');rig.animation_data.action=action
previous={};report=[]
for f,src_pose in enumerate(samples):
    t=f/fps;scene.frame_set(f)
    w=smooth(t/intro) if t<intro else 1-smooth((t-intro-strike)/outro) if t>intro+strike else 1.
    for b in rig.pose.bones:
        b.rotation_mode='QUATERNION';b.matrix_basis=mix(idle[b.name],src_pose[b.name],w)
    bpy.context.view_layer.update()
    # Step into/out of the sourced stance with separate planted support feet.
    targets={}
    for side in ['Right','Left']:
        if t<intro:
            start,end=(0.,.25) if side=='Right' else (.20,.45)
            u=smooth((t-start)/(end-start));foot=mix(idle_feet[side],source_feet[side],u)
        elif t>intro+strike:
            ot=t-intro-strike;start,end=(.25,.65) if side=='Right' else (0.,.35)
            u=smooth((ot-start)/(end-start));foot=mix(source_feet[side],idle_feet[side],u)
        else:
            u=0.;foot=source_feet[side].copy()
        foot.translation.z+=.035*math.sin(math.pi*u)
        targets[side]=foot
    drop=0.
    for side,foot in targets.items():
        old=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']]
        maximum=sum((old[i+1].translation-old[i].translation).length for i in range(2))-.0001
        delta=old[0].translation-foot.translation
        if delta.length>=maximum:
            planar=delta.x*delta.x+delta.y*delta.y
            if planar>=maximum*maximum:raise ValueError(f'Foot target beyond planar reach at {f}')
            drop=max(drop,delta.z-math.sqrt(maximum*maximum-planar))
    if drop>.08:raise ValueError(f'Pelvis correction too large at {f}: {drop}')
    if drop>0:
        hip=world(rig,'Hips');hip.translation.z-=drop
        rig.pose.bones['Hips'].matrix=rig.matrix_world.inverted()@hip;bpy.context.view_layer.update()
    for side,foot in targets.items():
        old=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']]
        try:
            solved=old if (old[-1].translation-foot.translation).length<1e-6 else solve(old,foot.translation)
        except ValueError as error:
            lengths=[(old[i+1].translation-old[i].translation).length for i in range(2)]
            raise ValueError(f'{error}; frame={f} side={side} distance={(foot.translation-old[0].translation).length} lengths={lengths}') from error
        solved[-1]=foot
        for suffix,m in zip(['UpLeg','Leg','Foot'],solved):
            rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
    # Recompute the rigid hand/socket relationship at 120 Hz. Interpolating a
    # root-child socket independently at 30 Hz caused 12 cm grip excursions.
    grip=mix(idle_grip,source_grip,w);sock=world(rig,'RightHand')@grip
    desired_palm=sock@idle_palm.lerp(Vector((0,-.245,0)),w)
    left,right=chain(rig,'Left'),chain(rig,'Right')
    target=desired_palm-left[2].to_3x3()@palm
    shift=paired_shift(left,right,target)
    if shift is None:raise ValueError(f'Unreachable paired grip at {f}')
    for side,old,target in [('Right',right,right[2].translation+shift),('Left',left,target+shift)]:
        for suffix,m in zip(['Arm','ForeArm','Hand'],solve(old,target)):
            rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
    sock.translation+=shift;rig.pose.bones['WeaponSocket'].matrix=rig.matrix_world.inverted()@sock;bpy.context.view_layer.update()
    report.append({'frame':f,'sharedGripShift':shift.length,'leftPalmError':((world(rig,'LeftHand')@palm)-(desired_palm+shift)).length})
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
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
dest.with_suffix('.json').write_text(json.dumps({'sourceSHA256':source_hash,'sha256':hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),'fps':fps,'duration':total/fps,'intro':intro,'outro':outro,'sourceStrikeSeconds':strike,'corrections':'Blender contact cleanup, separate step-in/step-out support, rigid socket rebake at 120 Hz; original source upper-body strike retained','samples':report,'accepted':False},indent=2)+'\n')
print('VEYR_HEAVY_JOINS_EXPORTED',flush=True)
