"""Blender-authored motion controls, native limb IK, and an editable baked action.

Run once after prepare_knight_walk.py. The preserved source action is sampled as
a reference. Sparse Blender curves direct the revision; native Blender IK solves
the limbs, and the deform rig retains its original rest matrices/skin.
"""
import os
import bpy
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector, Euler

ROOT=Path(os.environ.get('VEYR_BLENDER_WORK', '/Users/midir/veyr-blender-walk-20261021'))
scene=bpy.context.scene
rig=bpy.data.objects['Knight_Walk_Rig']
socket=bpy.data.objects['ReviewWeaponSocket']
reuse_controls=bool(bpy.data.objects.get('Walk_Pelvis_Control'))
source_action=bpy.data.actions.get('REFERENCE_Walk_v2_UNAPPROVED') or rig.animation_data.action
rig.animation_data.action=source_action
rig.animation_data.action_slot=source_action.slots['OBArmature']
socket.animation_data.action=source_action
socket.animation_data.action_slot=source_action.slots['OBReviewWeaponSocket']
source_action.name='REFERENCE_Walk_v2_UNAPPROVED'
source_action.use_fake_user=True
reference=[]
for f in range(211):
    scene.frame_set(f)
    reference.append(({b.name:b.matrix.copy() for b in rig.pose.bones},socket.matrix_world.copy()))
rig.animation_data_clear()
socket.animation_data_clear()

if not reuse_controls:
    collection=bpy.data.collections.new('WALK_AUTHORING_CONTROLS')
    scene.collection.children.link(collection)
    def empty(name):
        obj=bpy.data.objects.new(name,None);collection.objects.link(obj)
        obj.empty_display_type='PLAIN_AXES';obj.empty_display_size=.07
        obj.rotation_mode='XYZ'
        return obj
    
    pelvis=empty('Walk_Pelvis_Control')
    torso=empty('Walk_Torso_Control')
    hilt=empty('Walk_Hilt_Follow_Control')
    breath=empty('Walk_Breath_Control')
    # Sparse pose beats, in Blender Z-up coordinates. Forward is -Y.
    # The final idle and first idle are preserved exactly.
    beats=[
        (0,0,0,0,0), (14,0,.3,0,0),
        (30,-1,1,-1,1), (44,0,1,.25,-.25),
        (65,1,1,1,-1), (80,0,1,-.25,.25),
        (102,-1,1,-1,1), (116,0,1,.25,-.25),
        (138,1,1,1,-1), (152,0,1,-.25,.25),
        (174,-1,1,-1,1), (189,0,.6,0,0), (210,0,0,0,0)]
    def key(obj,f,loc,deg):
        obj.location=loc;obj.rotation_euler=tuple(math.radians(x) for x in deg)
        obj.keyframe_insert('location',frame=f)
        obj.keyframe_insert('rotation_euler',frame=f)
    for f,weight,ready,chest,lag in beats:
        key(pelvis,f,(.006*weight,0,-.004*ready+.002*abs(weight)),(0,1.7*weight,1.5*weight))
        key(torso,f,(0,0,0),(3.0*ready,2.8*chest,-2.0*chest))
        key(hilt,f,(.004*lag,-.008*ready,.003*abs(lag)),(-1.0*ready,2.5*lag,2.0*lag))
    for f,v in [(0,0),(15,.25),(36,1),(63,0),(90,-1),(117,0),(144,1),(171,0),(192,-.5),(210,0)]:
        key(breath,f,(0,-.002*v,.003*v),(.8*v,0,0))
    for obj in (pelvis,torso,hilt,breath):
        obj['purpose']='Editable additive motion curve; rerun bake after changes'
        for layer in obj.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for k in fc.keyframe_points:
                            k.interpolation='BEZIER';k.handle_left_type='AUTO_CLAMPED';k.handle_right_type='AUTO_CLAMPED'
    
    # A separate anatomical control rig has bones whose tails reach the actual
    # joints. Imported deform-bone axes remain untouched.
    data=bpy.data.armatures.new('Walk_Anatomical_IK')
    control=bpy.data.objects.new('Walk_Anatomical_IK',data);collection.objects.link(control)
    bpy.context.view_layer.objects.active=control;control.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    chains={}
    for side in ('Left','Right'):
        for kind,names in [('Arm',(side+'Arm',side+'ForeArm',side+'Hand')),('Leg',(side+'UpLeg',side+'Leg',side+'Foot'))]:
            label=side+kind
            points=[reference[0][0][n].translation for n in names]
            a=data.edit_bones.new(label+'_Upper');a.head=points[0];a.tail=points[1]
            b=data.edit_bones.new(label+'_Lower');b.head=points[1];b.tail=points[2];b.parent=a;b.use_connect=True
            chains[label]=names
    bpy.ops.object.mode_set(mode='OBJECT')
    targets={};poles={}
    for label in chains:
        targets[label]=empty(label+'_Target');poles[label]=empty(label+'_Pole')
        ik=control.pose.bones[label+'_Lower'].constraints.new('IK')
        ik.name='Natural two-bone '+label
        ik.target=targets[label];ik.pole_target=poles[label];ik.chain_count=2
        ik.use_stretch=False;ik.iterations=200
        control.pose.bones[label+'_Upper'].ik_stretch=0
        control.pose.bones[label+'_Lower'].ik_stretch=0
else:
    collection=bpy.data.collections['WALK_AUTHORING_CONTROLS']
    pelvis=bpy.data.objects['Walk_Pelvis_Control']
    torso=bpy.data.objects['Walk_Torso_Control']
    hilt=bpy.data.objects['Walk_Hilt_Follow_Control']
    breath=bpy.data.objects['Walk_Breath_Control']
    control=bpy.data.objects['Walk_Anatomical_IK'];data=control.data
    chains={side+kind:tuple(side+n for n in names) for side in ('Left','Right') for kind,names in [('Arm',('Arm','ForeArm','Hand')),('Leg',('UpLeg','Leg','Foot'))]}
    targets={label:bpy.data.objects[label+'_Target'] for label in chains}
    poles={label:bpy.data.objects[label+'_Pole'] for label in chains}

def around(pivot,rotation,offset=Vector((0,0,0))):
    return Matrix.Translation(pivot+offset)@rotation.to_matrix().to_4x4()@Matrix.Translation(-pivot)

max_contact=0.;min_knee=180.;max_knee=0.
previous_quaternions={}
for f,(base,weapon) in enumerate(reference):
    scene.frame_set(f)
    for b in rig.pose.bones:
        b.matrix=base[b.name]
    bpy.context.view_layer.update()
    hip=base['Hips'].translation
    body_delta=around(hip,pelvis.rotation_euler.to_quaternion(),pelvis.location)
    chest_pivot=(body_delta@base['Spine'].translation)
    chest_rotation=(torso.rotation_euler.to_quaternion()@breath.rotation_euler.to_quaternion())
    chest_delta=around(chest_pivot,chest_rotation,breath.location)
    total=chest_delta@body_delta
    desired={}
    for b in rig.pose.bones:
        n=b.name
        if n=='Hips' or any(n.startswith(s+x) for s in ('Left','Right') for x in ('UpLeg','Leg','Foot','Toe')):
            desired[n]=body_delta@base[n]
        else:
            desired[n]=total@base[n]
    # Neck counteracts half the added lean so attention stays forward.
    head_pivot=desired['Neck'].translation
    head_delta=around(head_pivot,Euler((-torso.rotation_euler.x*.5,0,0)).to_quaternion())
    for n in ('Neck','Head'):
        desired[n]=head_delta@desired[n]
    # Hands share one weapon transform, with a small delayed follow-through.
    hand_pivot=(total@weapon).translation
    weapon_delta=around(hand_pivot,hilt.rotation_euler.to_quaternion(),hilt.location)
    w_new=weapon_delta@total@weapon
    hand_delta=w_new@weapon.inverted()
    end_matrices={}
    for label,names in chains.items():
        arm='Arm' in label
        start=desired[names[0]].translation
        endpoint=(hand_delta@base[names[2]]) if arm else base[names[2]].copy()
        end_matrices[label]=endpoint
        middle=desired[names[1]].translation
        axis=(endpoint.translation-start).normalized()
        pole_dir=(middle-start)-axis*(middle-start).dot(axis)
        if pole_dir.length<1e-5: pole_dir=Vector((0,-1,0))
        pole_pos=middle+pole_dir.normalized()*.3
        upper=control.pose.bones[label+'_Upper']
        upper.matrix=Matrix.Translation(start)@data.bones[label+'_Upper'].matrix_local.to_3x3().to_4x4()
        upper.keyframe_insert('location',frame=f)
        targets[label].location=endpoint.translation;poles[label].location=pole_pos
        targets[label].keyframe_insert('location',frame=f);poles[label].keyframe_insert('location',frame=f)
    bpy.context.view_layer.update()
    # Align each native IK bend plane with the anatomical reference elbow/knee.
    # Blender's default pole angle depends on edit-bone roll and is not portable
    # from the glTF axes. Calibrate rather than accepting a sideways joint.
    for label,names in chains.items():
        upper=control.pose.bones[label+'_Upper'];lower=control.pose.bones[label+'_Lower']
        ik=lower.constraints[0]
        start=upper.head.copy();axis=(targets[label].location-start).normalized()
        wanted=poles[label].location-start;wanted-=axis*wanted.dot(axis);wanted.normalize()
        def pole_error(value):
            ik.pole_angle=(value+math.pi)%(2*math.pi)-math.pi
            bpy.context.view_layer.update()
            direction=lower.head-start;direction-=axis*direction.dot(axis);direction.normalize()
            return math.atan2(axis.dot(direction.cross(wanted)),direction.dot(wanted))
        value=0.
        for iteration in range(12):
            error=pole_error(value)
            if abs(error)<1e-6: break
            next_error=pole_error(value+.001)
            derivative=((next_error-error+math.pi)%(2*math.pi)-math.pi)/.001
            if abs(derivative)<.05: derivative=-1.
            value-=max(-.8,min(.8,error/derivative))
        pole_error(value)
        ik.keyframe_insert('pole_angle',frame=f)
    bpy.context.view_layer.update()
    for label,names in chains.items():
        upper=control.pose.bones[label+'_Upper'];lower=control.pose.bones[label+'_Lower']
        points=[upper.head.copy(),lower.head.copy(),lower.tail.copy()]
        for i in (0,1):
            olddir=(base[names[i+1]].translation-base[names[i]].translation).normalized()
            newdir=(points[i+1]-points[i]).normalized()
            orientation=olddir.rotation_difference(newdir)@base[names[i]].to_quaternion()
            desired[names[i]]=Matrix.LocRotScale(points[i],orientation,base[names[i]].to_scale())
        desired[names[2]]=end_matrices[label]
        max_contact=max(max_contact,(points[2]-end_matrices[label].translation).length)
        if 'Leg' in label:
            flex=180-math.degrees((points[0]-points[1]).angle(points[2]-points[1]))
            min_knee=min(min_knee,flex);max_knee=max(max_knee,flex)
        # All fingers/toes follow the hand/foot's rigid transform.
        delta=desired[names[2]]@base[names[2]].inverted()
        for child in rig.pose.bones[names[2]].children_recursive:
            desired[child.name]=delta@base[child.name]
    for b in rig.pose.bones:
        b.matrix=desired[b.name]
        bpy.context.view_layer.update()
        if b.name in previous_quaternions:
            q=b.rotation_quaternion.copy();q.make_compatible(previous_quaternions[b.name]);b.rotation_quaternion=q
        previous_quaternions[b.name]=b.rotation_quaternion.copy()
        b.keyframe_insert('location',frame=f,group=b.name)
        b.keyframe_insert('rotation_quaternion',frame=f,group=b.name)
        b.keyframe_insert('scale',frame=f,group=b.name)
    socket.matrix_world=w_new
    if 'weapon' in previous_quaternions:
        q=socket.rotation_quaternion.copy();q.make_compatible(previous_quaternions['weapon']);socket.rotation_quaternion=q
    previous_quaternions['weapon']=socket.rotation_quaternion.copy()
    socket.keyframe_insert('location',frame=f)
    socket.keyframe_insert('rotation_quaternion',frame=f)
    socket.keyframe_insert('scale',frame=f)

rig.animation_data.action.name='WalkTwoHand_Blender_v3'
socket.animation_data.action.name='WalkTwoHand_Blender_v3_Socket'
rig['authoring']='Blender sparse pelvis/chest/breath/hilt curves and native four-limb IK, baked at 60 fps'
scene.frame_start=0;scene.frame_end=210;scene.frame_set(70)
collection.hide_render=True
control.show_in_front=True
for obj in collection.objects: obj.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Knight_Walk_Blender_v3.blend'),compress=True)
report={'authoring':'Blender curves and native IK','blender':bpy.app.version_string,'frames':211,'fps':60,'durationSeconds':3.5,'maximumIKTargetError':max_contact,'kneeFlexionDegrees':[min_knee,max_knee],'approved':False,'editableControls':[pelvis.name,torso.name,breath.name,hilt.name]}
ROOT.joinpath('blender-walk-v3-authoring.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
