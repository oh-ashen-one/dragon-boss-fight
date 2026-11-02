"""Correct the off-hand contact of sourced attacks; preserve body/right-hand motion and limb lengths."""
import bpy
import hashlib
import json
import math
from pathlib import Path
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
HELPER=ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
g={'__file__':str(HELPER)};exec(compile(HELPER.read_text(),str(HELPER),'exec'),g);g['OUT']=OUT

def solve(world,target):
    shoulder,elbow,wrist=[m.translation.copy() for m in world]
    l1=(elbow-shoulder).length;l2=(wrist-elbow).length;delta=target-shoulder;distance=delta.length
    reach=max(abs(l1-l2)+2e-5,min(distance,l1+l2-2e-5))
    solve.last_projection=abs(reach-distance)
    if solve.last_projection>.01:raise ValueError(f'Sourced wrist requires excessive reach correction {solve.last_projection}')
    target=shoulder+delta.normalized()*reach;delta=target-shoulder;distance=reach
    direction=delta.normalized();pole=elbow-shoulder;pole-=direction*pole.dot(direction)
    if pole.length<1e-6:raise ValueError('Ambiguous elbow plane')
    along=(l1*l1-l2*l2+distance*distance)/(2*distance)
    new_elbow=shoulder+direction*along+pole.normalized()*math.sqrt(max(0,l1*l1-along*along))
    upper=(elbow-shoulder).rotation_difference(new_elbow-shoulder)@world[0].to_quaternion()
    fore=(wrist-elbow).rotation_difference(target-new_elbow)@world[1].to_quaternion()
    return [Matrix.LocRotScale(shoulder,upper,world[0].to_scale()),Matrix.LocRotScale(new_elbow,fore,world[1].to_scale()),Matrix.LocRotScale(target,world[2].to_quaternion(),world[2].to_scale())]

def body_frame(points,left,right,neck,hips):
    center=(points[left].translation+points[right].translation)*.5
    r=(points[right].translation-points[left].translation).normalized()
    up=points[neck].translation-points[hips].translation;up=(up-r*up.dot(r)).normalized()
    front=up.cross(r).normalized()
    return center,Matrix((r,front,up)).transposed()

for variant in ['M','F']:
    old=f'Kevin_Heavy_{variant}_v1';name=f'Kevin_Heavy_{variant}_v2'
    source=OUT/'Exports'/(old+'.blend');sha=hashlib.sha256(source.read_bytes()).hexdigest()
    assert not (OUT/'Exports'/(name+'.blend')).exists()
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
    rig=bpy.data.objects['Knight_Comparison'];s=bpy.context.scene
    old_action=rig.animation_data.action;action=old_action.copy();action.name=name;rig.animation_data.action=action
    hand=rig.data.bones['LeftHand'];inverse=hand.matrix_local.inverted()
    points={n:inverse@rig.data.bones['LeftHand'+n].head_local for n in ['Index','Pinky','Middle']}
    longitudinal=points['Middle'].normalized();blade=(points['Index']-points['Pinky']).normalized()
    across=(longitudinal-blade*longitudinal.dot(blade)).normalized()
    palm=(points['Index']+points['Pinky'])*.5-across*.010
    fk=[];right_solutions=[]
    src=bpy.data.objects['Source_kevin_iglesias'];src.hide_set(False);src.hide_render=True
    for frame in range(49):
        s.frame_set(frame+1);bpy.context.view_layer.update()
        source_names=['B-upperArm.L','B-upperArm.R','B-forearm.L','B-forearm.R','B-hand.L','B-hand.R','B-neck','B-hips']
        sw={n:(src.matrix_world@src.pose.bones[n].matrix).copy() for n in source_names}
        rig.animation_data.action=old_action;s.frame_set(frame);bpy.context.view_layer.update()
        target_names=['LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand','Neck','Hips']
        tw={n:(rig.matrix_world@rig.pose.bones[n].matrix).copy() for n in target_names}
        world=[(rig.matrix_world@rig.pose.bones[n].matrix).copy() for n in ['LeftArm','LeftForeArm','LeftHand']]
        socket=(rig.matrix_world@rig.pose.bones['WeaponSocket'].matrix).copy()
        sc,sf=body_frame(sw,'B-upperArm.L','B-upperArm.R','B-neck','B-hips')
        tc,tf=body_frame(tw,'LeftArm','RightArm','Neck','Hips')
        source_length=sum((sw['B-'+a+'.'+side].translation-sw['B-'+b+'.'+side].translation).length for side in ['L','R'] for a,b in [('upperArm','forearm'),('forearm','hand')])
        target_length=sum((tw[side+a].translation-tw[side+b].translation).length for side in ['Left','Right'] for a,b in [('Arm','ForeArm'),('ForeArm','Hand')])
        target_right=tc+tf@(sf.transposed()@(sw['B-hand.R'].translation-sc))*(target_length/source_length)
        right=[tw[n] for n in ['RightArm','RightForeArm','RightHand']]
        solved=solve(right,target_right)
        socket=solved[2]@right[2].inverted()@socket
        right_solutions.append((solved,socket,solve.last_projection))
        fk.append((world,socket))
    choices=[]
    # Select one constant grip along the existing shaft, rather than forcing
    # the old authored 28 cm spacing onto a differently proportioned source.
    for step in range(65):
        offset=-.40+step*.005;cost=0.;valid=True
        for world,socket in fk:
            target=socket@Vector((0,offset,0))-world[2].to_3x3()@palm
            p0,p1,p2=[m.translation for m in world];l1=(p1-p0).length;l2=(p2-p1).length;distance=(target-p0).length
            if not abs(l1-l2)+1e-5<distance<l1+l2-1e-5:valid=False;break
            cost+=(target-p2).length_squared
        if valid:choices.append((cost,offset))
    if not choices:raise ValueError('No reachable stable grip on the existing shaft')
    _,grip_offset=min(choices)
    samples=[];previous={}
    for frame in range(49):
        s.frame_set(frame);bpy.context.view_layer.update()
        # Always start from that frame's original FK sample. New keys on earlier
        # frames must never influence evaluation of a later source sample.
        rig.animation_data.action=old_action;s.frame_set(frame);bpy.context.view_layer.update()
        bones=[rig.pose.bones[n] for n in ['LeftArm','LeftForeArm','LeftHand']]
        world=[(rig.matrix_world@b.matrix).copy() for b in bones]
        right_solution,socket,right_projection=right_solutions[frame]
        # The existing preview attachment's blade axis is socket +Y; its
        # measured left handle grip is 0.28 source metres below the right grip.
        desired_palm=socket@Vector((0,grip_offset,0))
        before_palm=world[2]@palm
        target=desired_palm-world[2].to_3x3()@palm
        shoulder,elbow,wrist=[m.translation.copy() for m in world]
        l1=(elbow-shoulder).length;l2=(wrist-elbow).length;delta=target-shoulder;distance=delta.length
        if not abs(l1-l2)+1e-6<distance<l1+l2-1e-6:raise ValueError(f'Unreachable off-hand target {name} frame {frame}')
        direction=delta.normalized();pole=elbow-shoulder;pole-=direction*pole.dot(direction)
        if pole.length<1e-6:raise ValueError('Ambiguous elbow plane')
        along=(l1*l1-l2*l2+distance*distance)/(2*distance)
        new_elbow=shoulder+direction*along+pole.normalized()*math.sqrt(max(0,l1*l1-along*along))
        upper_rot=(elbow-shoulder).rotation_difference(new_elbow-shoulder)@world[0].to_quaternion()
        fore_rot=(wrist-elbow).rotation_difference(target-new_elbow)@world[1].to_quaternion()
        desired=[Matrix.LocRotScale(shoulder,upper_rot,world[0].to_scale()),
                 Matrix.LocRotScale(new_elbow,fore_rot,world[1].to_scale()),
                 Matrix.LocRotScale(target,world[2].to_quaternion(),world[2].to_scale())]
        rig.animation_data.action=action
        for bone_name,m in zip(['RightArm','RightForeArm','RightHand'],right_solution):
            b=rig.pose.bones[bone_name];b.matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
            q=b.rotation_quaternion.copy()
            if b.name in previous:q.make_compatible(previous[b.name])
            b.rotation_quaternion=q;previous[b.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=frame)
        sock=rig.pose.bones['WeaponSocket'];sock.matrix=rig.matrix_world.inverted()@socket;bpy.context.view_layer.update()
        for prop in ['location','rotation_quaternion','scale']:sock.keyframe_insert(prop,frame=frame)
        for b,m in zip(bones,desired):
            b.matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
            q=b.rotation_quaternion.copy()
            if b.name in previous:q.make_compatible(previous[b.name])
            b.rotation_quaternion=q;previous[b.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=frame)
        bpy.context.view_layer.update();after=[rig.matrix_world@b.matrix for b in bones]
        error=((after[2]@palm)-desired_palm).length
        length_error=max(abs((after[1].translation-after[0].translation).length-l1),abs((after[2].translation-after[1].translation).length-l2))
        assert error<1e-5 and length_error<1e-5
        samples.append({'frame':frame,'beforeGripError':(before_palm-desired_palm).length,'afterGripError':error,'maxLimbLengthError':length_error,'rightSourceReachProjection':right_projection})
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    s.frame_set(0);body=[o for o in s.objects if o.type=='MESH' and not o.hide_render]
    for o in s.objects:o.select_set(False)
    rig.select_set(True)
    for o in body:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    path=OUT/'Exports'/name
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    report={'name':name,'sourceRetargetSHA256':sha,'sourceRetargetPreserved':True,'correction':'Sourced right-wrist trajectory retargeted relative to anatomical chest using arm-length ratio, then constant off-hand shaft contact; source body and finger motion retained',
            'units':'Blender world units','constantGripOffsetOnShaft':grip_offset,'feasibleGripChoices':len(choices),'samples':samples,'accepted':False,'sha256':hashlib.sha256(path.with_suffix('.glb').read_bytes()).hexdigest()}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    g['render'](name,[0,12,24,36,48])
print('VEYR_KEVIN_GRIP_FIT_COMPLETE',flush=True)
