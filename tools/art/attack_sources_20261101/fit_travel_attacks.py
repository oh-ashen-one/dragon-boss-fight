"""Fit sourced running/leaping attacks, preserving their travel and airborne motion."""
import bpy,json,hashlib,math
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports'
h=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(h)};exec(compile(h.read_text().split('reports=[]')[0],str(h),'exec'),ns)
solve,chain,paired_shift=ns['solve'],ns['chain'],ns['paired_shift']
def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def mix(a,b,w):
    p,q,s=a.decompose();pp,qq,ss=b.decompose();return Matrix.LocRotScale(p.lerp(pp,w),q.slerp(qq,w),s.lerp(ss,w))
def world(rig,n):return (rig.matrix_world@rig.pose.bones[n].matrix).copy()
for key in ['JumpAttack','SlideAttack']:
    source=OUT/f'Mixamo_{key}_v1.blend';dest=OUT/f'Mixamo_{key}_v2';assert not dest.with_suffix('.blend').exists()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.context.scene.frame_set(0);bpy.context.view_layer.update()
    idle={b.name:b.matrix_basis.copy() for b in rig.pose.bones};idle_feet={s:world(rig,s+'Foot') for s in ['Left','Right']}
    idle_grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
    inv=rig.data.bones['LeftHand'].matrix_local.inverted();pts={n:inv@rig.data.bones['LeftHand'+n].head_local for n in ['Index','Pinky','Middle']}
    long=pts['Middle'].normalized();across=(long-(pts['Index']-pts['Pinky']).normalized()*long.dot((pts['Index']-pts['Pinky']).normalized())).normalized();palm=(pts['Index']+pts['Pinky'])*.5-across*.010
    idle_palm=world(rig,'WeaponSocket').inverted()@(world(rig,'LeftHand')@palm)
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False);s=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];original=rig.animation_data.action;source_fps=s.render.fps/s.render.fps_base;duration=s.frame_end/source_fps
    s.frame_set(0);bpy.context.view_layer.update();first_hip=world(rig,'Hips').translation;start_feet={side:world(rig,side+'Foot') for side in ['Left','Right']};grip=world(rig,'RightHand').inverted()@world(rig,'WeaponSocket')
    s.frame_set(s.frame_end);bpy.context.view_layer.update();net=world(rig,'Hips').translation-first_hip;net.z=0;end_feet={side:world(rig,side+'Foot') for side in ['Left','Right']}
    end_idle={n:m.copy() for n,m in idle.items()}
    root_basis=rig.matrix_world@rig.data.bones['VeyrRoot'].matrix_local
    end_idle['VeyrRoot'].translation+=root_basis.inverted().to_3x3()@net
    final_feet={side:m.copy() for side,m in idle_feet.items()}
    for m in final_feet.values():m.translation+=net
    intro=.30;outro=.35;fps=120;end=round((intro+duration+outro)*fps);poses=[]
    for f in range(end+1):
        st=max(0.,min(duration,f/fps-intro))*source_fps;rig.animation_data.action=original;s.frame_set(int(st),subframe=st-int(st));bpy.context.view_layer.update();poses.append({b.name:b.matrix_basis.copy() for b in rig.pose.bones})
    s.render.fps=fps;s.render.fps_base=1;s.frame_start=0;s.frame_end=end;action=bpy.data.actions.new(dest.stem);rig.animation_data.action=action;previous={};shifts=[]
    for f,pose in enumerate(poses):
        t=f/fps;s.frame_set(f);entry=t<intro;exit=t>intro+duration;w=smooth(t/intro) if entry else 1-smooth((t-intro-duration)/outro) if exit else 1.
        base=idle if entry else end_idle
        for b in rig.pose.bones:b.rotation_mode='QUATERNION';b.matrix_basis=mix(base[b.name],pose[b.name],w)
        bpy.context.view_layer.update()
        if entry or exit:
            targets={}
            for side in ['Right','Left']:
                if entry:
                    a,b=(0.,intro*.6) if side=='Right' else (intro*.4,intro);phase=max(0.,min(1.,(t-a)/(b-a)));u=smooth((phase-.25)/.5);foot=mix(idle_feet[side],start_feet[side],u)
                else:
                    ot=t-intro-duration;a,b=(outro*.4,outro) if side=='Right' else (0.,outro*.6);phase=max(0.,min(1.,(ot-a)/(b-a)));u=smooth((phase-.25)/.5);foot=mix(end_feet[side],final_feet[side],u)
                foot.translation.z+=.05*min(smooth(phase/.25),smooth((1-phase)/.25));targets[side]=foot
            drop=0.
            for side,foot in targets.items():
                old=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']];limit=sum((old[i+1].translation-old[i].translation).length for i in range(2))-.0001;delta=old[0].translation-foot.translation
                if delta.length>=limit:
                    planar=delta.x**2+delta.y**2
                    if planar>=limit*limit:raise ValueError(f'{key} entry/exit foot unreachable at {f}')
                    drop=max(drop,delta.z-math.sqrt(limit*limit-planar))
            if drop>.08:raise ValueError(f'{key} excessive pelvis correction at {f}')
            if drop:
                hip=world(rig,'Hips');hip.translation.z-=drop;rig.pose.bones['Hips'].matrix=rig.matrix_world.inverted()@hip;bpy.context.view_layer.update()
            for side,foot in targets.items():
                old=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']];solved=old if (old[-1].translation-foot.translation).length<1e-6 else solve(old,foot.translation);solved[-1]=foot
                for suffix,m in zip(['UpLeg','Leg','Foot'],solved):rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
        socket=world(rig,'RightHand')@mix(idle_grip,grip,w);left,right=chain(rig,'Left'),chain(rig,'Right');desired=socket@idle_palm.lerp(Vector((0,-.245,0)),w);target=desired-left[2].to_3x3()@palm;shift=paired_shift(left,right,target,.10)
        if shift is None:raise ValueError(f'{key} paired grip unreachable at {f}')
        for side,old,target in [('Right',right,right[2].translation+shift),('Left',left,target+shift)]:
            for suffix,m in zip(['Arm','ForeArm','Hand'],solve(old,target)):rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
        socket.translation+=shift;rig.pose.bones['WeaponSocket'].matrix=rig.matrix_world.inverted()@socket;bpy.context.view_layer.update();shifts.append(shift.length)
        for b in rig.pose.bones:
            q=b.rotation_quaternion.copy()
            if b.name in previous:q.make_compatible(previous[b.name])
            b.rotation_quaternion=q;previous[b.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=f)
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for k in curve.keyframe_points:k.interpolation='LINEAR'
    s.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for o in s.objects:
        if o.type=='MESH' and not o.hide_render:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
    dest.with_suffix('.json').write_text(json.dumps({'source':str(source),'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),'duration':end/fps,'fps':fps,'intro':intro,'outro':outro,'sourceTravelPreserved':True,'sourceLegMotionPreservedOutsideJoins':True,'rootTravelWorld':list(net),'maxPairedGripShiftWorld':max(shifts),'accepted':False},indent=2)+'\n')
print('MIXAMO_TRAVEL_ATTACKS_FITTED',flush=True)
