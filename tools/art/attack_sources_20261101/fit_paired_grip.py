"""Adapt a sourced two-hand hold to this rig through bounded paired-arm IK, never stretching bones."""
import bpy,hashlib,json,math
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
HELPER=ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
g={'__file__':str(HELPER)};exec(compile(HELPER.read_text(),str(HELPER),'exec'),g);g['OUT']=OUT

def chain(rig,side):return [(rig.matrix_world@rig.pose.bones[side+n].matrix).copy() for n in ['Arm','ForeArm','Hand']]
def length(w):return sum((w[i+1].translation-w[i].translation).length for i in range(2))
def solve(w,target):
    a,b,c=[m.translation.copy() for m in w];u=(b-a).length;v=(c-b).length;delta=target-a;d=delta.length
    if not abs(u-v)+1e-6<d<u+v-1e-6:raise ValueError('Unreachable IK target')
    direction=delta.normalized();pole=b-a;pole-=direction*pole.dot(direction)
    if pole.length<1e-6:raise ValueError('Ambiguous elbow plane')
    along=(u*u-v*v+d*d)/(2*d);joint=a+direction*along+pole.normalized()*math.sqrt(max(0,u*u-along*along))
    q0=(b-a).rotation_difference(joint-a)@w[0].to_quaternion();q1=(c-b).rotation_difference(target-joint)@w[1].to_quaternion()
    return [Matrix.LocRotScale(a,q0,w[0].to_scale()),Matrix.LocRotScale(joint,q1,w[1].to_scale()),Matrix.LocRotScale(target,w[2].to_quaternion(),w[2].to_scale())]

def paired_shift(left,right,left_target):
    shift=Vector();right_target=right[2].translation
    # Alternating projections of the common rigid grip translation into the
    # two reachable-arm balls. Both wrists move together; the source handle
    # orientation and each bone's length are retained.
    for _ in range(80):
        for w,target in [(left,left_target),(right,right_target)]:
            delta=target+shift-w[0].translation;maximum=length(w)-.0001
            if delta.length>maximum:shift+=delta.normalized()*maximum-delta
    if shift.length>.06:return None
    for w,target in [(left,left_target),(right,right_target)]:
        if (target+shift-w[0].translation).length>length(w)-.00005:return None
    return shift

reports=[]
for variant in ['M','F']:
    old=f'Kevin_Heavy_{variant}_v6';name=f'Kevin_Heavy_{variant}_v7'
    path=OUT/'Exports'/name;assert not path.with_suffix('.blend').exists()
    source=OUT/'Exports'/(old+'.blend');sha=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False);rig=bpy.data.objects['Knight_Comparison'];s=bpy.context.scene;original=rig.animation_data.action
    inv=rig.data.bones['LeftHand'].matrix_local.inverted();points={n:inv@rig.data.bones['LeftHand'+n].head_local for n in ['Index','Pinky','Middle']}
    longitudinal=points['Middle'].normalized();blade=(points['Index']-points['Pinky']).normalized();across=(longitudinal-blade*longitudinal.dot(blade)).normalized();palm=(points['Index']+points['Pinky'])*.5-across*.010
    frames=[]
    for frame in range(49):
        s.frame_set(frame);bpy.context.view_layer.update();frames.append((chain(rig,'Left'),chain(rig,'Right'),(rig.matrix_world@rig.pose.bones['WeaponSocket'].matrix).copy()))
    choices=[]
    for step in range(45):
        offset=-.36+step*.005;cost=0.;shifts=[]
        for left,right,socket in frames:
            desired=socket@Vector((0,offset,0))-left[2].to_3x3()@palm
            shift=paired_shift(left,right,desired)
            if shift is None:break
            cost+=(desired+shift-left[2].translation).length_squared+2*shift.length_squared;shifts.append(shift)
        if len(shifts)==49:choices.append((cost,offset,shifts))
    if not choices:
        reports.append({'name':name,'accepted':False,'reason':'No bounded reachable paired grip'});continue
    _,offset,shifts=min(choices,key=lambda row:row[0]);action=original.copy();action.name=name;previous={};samples=[]
    for frame,(left,right,socket) in enumerate(frames):
        rig.animation_data.action=original;s.frame_set(frame);bpy.context.view_layer.update();shift=shifts[frame];new_socket=socket.copy();new_socket.translation+=shift
        desired_palm=new_socket@Vector((0,offset,0));left_target=desired_palm-left[2].to_3x3()@palm
        solved={'Left':solve(left,left_target),'Right':solve(right,right[2].translation+shift)}
        rig.animation_data.action=action
        for side in ['Right','Left']:
            for suffix,m in zip(['Arm','ForeArm','Hand'],solved[side]):
                b=rig.pose.bones[side+suffix];b.matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update();q=b.rotation_quaternion.copy()
                if b.name in previous:q.make_compatible(previous[b.name])
                b.rotation_quaternion=q;previous[b.name]=q.copy()
                for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(prop,frame=frame)
        sock=rig.pose.bones['WeaponSocket'];sock.matrix=rig.matrix_world.inverted()@new_socket;bpy.context.view_layer.update()
        for prop in ['location','rotation_quaternion','scale']:sock.keyframe_insert(prop,frame=frame)
        actual=chain(rig,'Left');error=((actual[2]@palm)-desired_palm).length
        lengths=max(abs(length(chain(rig,'Left'))-length(left)),abs(length(chain(rig,'Right'))-length(right)))
        assert error<1e-5 and lengths<1e-5
        samples.append({'frame':frame,'sharedGripTranslation':shift.length,'gripError':error,'limbLengthError':lengths})
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    s.frame_set(0)
    for o in s.objects:o.select_set(False)
    rig.select_set(True)
    for o in s.objects:
        if o.type=='MESH' and not o.hide_render:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    report={'name':name,'sourceRetargetSHA256':sha,'sourceRetargetPreserved':True,'sourceMotionRetained':'timing, torso, legs, fingers and hand orientation','correction':'Bounded shared grip translation and paired-arm IK for one fixed shaft contact; no limb stretching','constantGripOffsetOnShaft':offset,'samples':samples,'accepted':False,'sha256':hashlib.sha256(path.with_suffix('.glb').read_bytes()).hexdigest()}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
    g['render'](name,[0,12,24,36,48])
summary=OUT/'paired-grip-v7-results.json';assert not summary.exists();summary.write_text(json.dumps(reports,indent=2)+'\n')
print('VEYR_PAIRED_GRIP_COMPLETE',flush=True)
