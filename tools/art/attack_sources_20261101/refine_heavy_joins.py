"""Blender correction of sourced heavy contacts and idle joins; retain the source strike."""
import bpy, json, hashlib, math, argparse, sys
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget/Exports'
source = OUT/'Kevin_Heavy_M_v7.blend'
parser=argparse.ArgumentParser();parser.add_argument('--version',default='v8');parser.add_argument('--stepped-clearance',action='store_true');parser.add_argument('--soften-strike',action='store_true')
parser.add_argument('--entry-glb',type=Path);parser.add_argument('--entry-seconds',type=float,default=0.)
parser.add_argument('--source-blend',type=Path);parser.add_argument('--output-name');parser.add_argument('--intro',type=float,default=.45);parser.add_argument('--outro',type=float,default=.65)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert args.version.isalnum()
if args.source_blend:source=args.source_blend
dest = (source.parent/args.output_name) if args.output_name else OUT/f'Kevin_Heavy_M_{args.version}'
assert .1<=args.intro<=1. and .1<=args.outro<=1.
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
entry=idle;entry_feet=idle_feet;entry_grip=idle_grip;entry_palm=idle_palm
if args.entry_glb:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=120
    bpy.ops.import_scene.gltf(filepath=str(args.entry_glb));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    ef=args.entry_seconds*120;bpy.context.scene.frame_set(int(ef),subframe=ef-int(ef));bpy.context.view_layer.update()
    entry=pose(rig);entry_feet={s:world(rig,s+'Foot') for s in ['Left','Right']}
    entry_grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
    entry_palm=world(rig,'WeaponSocket').inverted()@(world(rig,'LeftHand')@palm)

source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
rig=bpy.data.objects['Knight_Comparison'];scene=bpy.context.scene;original=rig.animation_data.action
scene.frame_set(0);bpy.context.view_layer.update()
source_feet={s:world(rig,s+'Foot') for s in ['Left','Right']}
source_grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
original_fps=scene.render.fps/scene.render.fps_base
source_seconds=(scene.frame_end-scene.frame_start)/original_fps
fps=120; intro=args.intro; strike=1.73 if args.soften_strike else source_seconds; outro=args.outro; total=int(round((intro+strike+outro)*fps))
def source_time(t):
    if not args.soften_strike:return t
    # Monotone cubic DCC time warp: preserve the sourced path, spread the
    # concentrated torso drop, and keep nonzero velocity through the cut.
    xs=[0.,.40,.48,.68,.76,1.73];ys=[0.,.40,.46,.55,.63,1.6]
    slopes=[(ys[i+1]-ys[i])/(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
    tangents=[slopes[0]]+[2*slopes[i-1]*slopes[i]/(slopes[i-1]+slopes[i]) for i in range(1,len(slopes))]+[slopes[-1]]
    i=min(len(xs)-2,next((j for j in range(len(xs)-1) if t<=xs[j+1]),len(xs)-2))
    h=xs[i+1]-xs[i];u=max(0.,min(1.,(t-xs[i])/h))
    return (2*u**3-3*u**2+1)*ys[i]+(u**3-2*u**2+u)*h*tangents[i]+(-2*u**3+3*u**2)*ys[i+1]+(u**3-u*u)*h*tangents[i+1]
samples=[]
for f in range(total+1):
    t=f/fps; st=source_time(max(0.,min(strike,t-intro)))*original_fps
    rig.animation_data.action=original;scene.frame_set(int(st),subframe=st-int(st));bpy.context.view_layer.update()
    samples.append(pose(rig))
scene.render.fps=fps;scene.render.fps_base=1;scene.frame_start=0;scene.frame_end=total
action=bpy.data.actions.new(f'Kevin_Heavy_M_{args.version}_ContactAndIdleJoins');rig.animation_data.action=action
previous={};report=[]
for f,src_pose in enumerate(samples):
    t=f/fps;scene.frame_set(f)
    w=smooth(t/intro) if t<intro else 1-smooth((t-intro-strike)/outro) if t>intro+strike else 1.
    base_pose=entry if t<intro else idle
    for b in rig.pose.bones:
        b.rotation_mode='QUATERNION';b.matrix_basis=mix(base_pose[b.name],src_pose[b.name],w)
    bpy.context.view_layer.update()
    # Step into/out of the sourced stance with separate planted support feet.
    targets={}
    for side in ['Right','Left']:
        if t<intro:
            start,end=(0.,intro*5/9) if side=='Right' else (intro*4/9,intro)
            phase=max(0.,min(1.,(t-start)/(end-start)))
            u=smooth((phase-.25)/.5) if args.stepped_clearance else smooth(phase)
            foot=mix(entry_feet[side],source_feet[side],u)
        elif t>intro+strike:
            ot=t-intro-strike;start,end=(outro*5/13,outro) if side=='Right' else (0.,outro*7/13)
            phase=max(0.,min(1.,(ot-start)/(end-start)))
            u=smooth((phase-.25)/.5) if args.stepped_clearance else smooth(phase)
            foot=mix(source_feet[side],idle_feet[side],u)
        else:
            phase=u=0.;foot=source_feet[side].copy()
        lift=.05*min(smooth(phase/.25),smooth((1-phase)/.25)) if args.stepped_clearance else .035*math.sin(math.pi*u)
        foot.translation.z+=lift
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
    grip=mix(entry_grip if t<intro else idle_grip,source_grip,w);sock=world(rig,'RightHand')@grip
    desired_palm=sock@(entry_palm if t<intro else idle_palm).lerp(Vector((0,-.245,0)),w)
    left,right=chain(rig,'Left'),chain(rig,'Right')
    target=desired_palm-left[2].to_3x3()@palm
    # The old combo exits with a different grip. Its corrective handover may
    # move the rigid pair up to 10% of character height; the sourced strike
    # retains the tighter 6% bound, and no limb is stretched in either case.
    shift=paired_shift(left,right,target,.10 if args.entry_glb and t<intro else .06)
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
dest.with_suffix('.json').write_text(json.dumps({'sourceSHA256':source_hash,'sha256':hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),'fps':fps,'entryReference':str(args.entry_glb) if args.entry_glb else str(idle_path),'entrySeconds':args.entry_seconds,'duration':total/fps,'intro':intro,'outro':outro,'sourceStrikeSeconds':strike,'corrections':'Blender contact cleanup, separate step-in/step-out support, rigid socket rebake at 120 Hz; original source upper-body strike retained','samples':report,'accepted':False},indent=2)+'\n')
print('VEYR_HEAVY_JOINS_EXPORTED',flush=True)
