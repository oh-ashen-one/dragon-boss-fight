"""Fit target boot soles to native floor0 inside Blender, without planar locking.

The licensed source determines contact/heel/toe phases. Preserve ankle XY,
foot orientation, timing, limb lengths and the hand-relative weapon attachment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--name',default='Mixamo_Turn180_A')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert a.name in ['Mixamo_Turn180_A','Mixamo_Turn180_B','Mixamo_Turn_A','Mixamo_Turn_B']
SOURCE=ROOT/'Local/AttackSources20261104/SourcedTurnContacts'/(a.name+'_v3contacts.blend')
OUT=ROOT/'Local/AttackSources20261105/GroundedTurns';OUT.mkdir(parents=True,exist_ok=True)
DEST=OUT/(a.name+'_v4grounded')
assert not DEST.with_suffix('.blend').exists()
native_scale=json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
helper=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(helper)}
exec(compile(helper.read_text().split('reports=[]')[0],str(helper),'exec'),ns)
solve=ns['solve']


def world(rig,name):return (rig.matrix_world@rig.pose.bones[name].matrix).copy()
def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)


bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False)
scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];src=bpy.data.objects['Source_mixamo']
original=rig.animation_data.action;original.use_fake_user=True
end=scene.frame_end;fps=scene.render.fps/scene.render.fps_base
source_start=round(src.animation_data.action.frame_range[0]);scale=float(scene['retarget_scale'])
sides=['Left','Right'];frames=[]
for f in range(end+1):
    scene.frame_set(source_start+f);bpy.context.view_layer.update()
    source_heights={s:[world(src,'mixamorig:'+s+n).translation.z for n in ['Foot','ToeBase']] for s in sides}
    scene.frame_set(f);bpy.context.view_layer.update()
    frames.append({'basis':{b.name:b.matrix_basis.copy() for b in rig.pose.bones},
                   'feet':{s:world(rig,s+'Foot') for s in sides},'sourceHeights':source_heights,
                   'grip':rig.pose.bones['RightHand'].matrix.inverted()@rig.pose.bones['WeaponSocket'].matrix})
low={s:[sorted(row['sourceHeights'][s][b] for row in frames)[round(end*.1)] for b in range(2)] for s in sides}
meshes=[]
for obj in scene.objects:
    if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):continue
    ids={}
    for side in sides:
        groups={g.index for g in obj.vertex_groups if g.name in [side+'Leg',side+'Foot',side+'ToeBase']}
        ankle=(rig.matrix_world@rig.data.bones[side+'Foot'].matrix_local).translation.z
        ids[side]=[v.index for v in obj.data.vertices if (obj.matrix_world@v.co).z<=ankle+1/native_scale
                   and sum(w.weight for w in v.groups if w.group in groups)>.75]
    meshes.append((obj,ids))
assert all(sum(len(ids[s]) for _,ids in meshes)>20 for s in sides)


def soles():
    result={s:float('inf') for s in sides};deps=bpy.context.evaluated_depsgraph_get()
    for obj,ids in meshes:
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
        assert len(mesh.vertices)==len(obj.data.vertices)
        for side in sides:
            if ids[side]:result[side]=min(result[side],min((evaluated.matrix_world@mesh.vertices[i].co).z for i in ids[side]))
        evaluated.to_mesh_clear()
    return result


action=original.copy();action.name=DEST.stem;rig.animation_data.action=action
previous={};records=[];maximum_planar_error=maximum_length_error=maximum_shift=0.
for f,data in enumerate(frames):
    scene.frame_set(f)
    for b in rig.pose.bones:b.rotation_mode='QUATERNION';b.matrix_basis=data['basis'][b.name]
    bpy.context.view_layer.update();initial=soles()
    weights={s:1-smooth((min(data['sourceHeights'][s][b]-low[s][b] for b in range(2))*scale*native_scale-1.)/3.) for s in sides}
    desired={s:max(0.,initial[s])*(1-weights[s]) for s in sides}
    targets={s:data['feet'][s].translation.copy() for s in sides};total_shift=Vector()
    initial_lengths={s:[(world(rig,s+b).translation-world(rig,s+c).translation).length
                        for b,c in [('Leg','UpLeg'),('Foot','Leg')]] for s in sides}
    for iteration in range(8):
        measured=soles();errors={s:desired[s]-measured[s] for s in sides}
        if max(abs(v) for v in errors.values())<.00015:break
        for side in sides:
            targets[side].z+=errors[side]
            assert abs(targets[side].z-data['feet'][side].translation.z)<.08,'Excessive grounding correction'
        chains={s:[world(rig,s+n) for n in ['UpLeg','Leg','Foot']] for s in sides};shift=Vector()
        for _ in range(80):
            for side,chain in chains.items():
                limit=sum((chain[i+1].translation-chain[i].translation).length for i in range(2))-.0001
                delta=targets[side]-chain[0].translation-shift
                if delta.length>limit:shift+=delta.normalized()*(delta.length-limit)
        total_shift+=shift;assert total_shift.length<.08,'Excessive pelvis reach correction'
        hip=world(rig,'Hips');hip.translation+=shift;rig.pose.bones['Hips'].matrix=rig.matrix_world.inverted()@hip
        bpy.context.view_layer.update()
        for side in sides:
            chain=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']]
            if (chain[2].translation-targets[side]).length<1e-7:continue
            solved=solve(chain,targets[side]);solved[2]=data['feet'][side].copy();solved[2].translation=targets[side]
            for suffix,m in zip(['UpLeg','Leg','Foot'],solved):
                rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted()@m;bpy.context.view_layer.update()
    final=soles();assert min(final.values())>=-.0002,'Boot still penetrates native floor'
    assert max(abs(final[s]-desired[s]) for s in sides)<.0002,'Ground target did not converge'
    for side in sides:
        actual=world(rig,side+'Foot').translation;delta=actual-data['feet'][side].translation;delta.z=0
        maximum_planar_error=max(maximum_planar_error,delta.length)
        chain=[world(rig,side+n) for n in ['UpLeg','Leg','Foot']]
        maximum_length_error=max(maximum_length_error,max(abs((chain[i+1].translation-chain[i].translation).length-initial_lengths[side][i]) for i in range(2)))
    maximum_shift=max(maximum_shift,total_shift.length)
    rig.pose.bones['WeaponSocket'].matrix=rig.pose.bones['RightHand'].matrix@data['grip'];bpy.context.view_layer.update()
    for bone in rig.pose.bones:
        q=bone.rotation_quaternion.copy()
        if bone.name in previous:q.make_compatible(previous[bone.name])
        bone.rotation_quaternion=q;previous[bone.name]=q.copy()
        for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(prop,frame=f)
    records.append({'frame':f,'contactWeights':weights,'beforeSoles':initial,'afterSoles':final,'desiredSoles':desired})
assert maximum_planar_error<1e-5 and maximum_length_error<1e-5
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for obj,_ in meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(DEST.with_suffix('.glb')),export_format='GLB',use_selection=True,
    export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,
    export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(DEST.with_suffix('.blend')),compress=True)
report={'authoringApplication':'Blender','source':str(SOURCE.relative_to(ROOT)),
        'sourceSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'duration':end/fps,'fps':fps,
        'editableScene':str(DEST.with_suffix('.blend').relative_to(ROOT)),
        'editableSceneSHA256':hashlib.sha256(DEST.with_suffix('.blend').read_bytes()).hexdigest(),
        'sha256':hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest(),
        'maximumAnklePlanarDeviationSourceUnits':maximum_planar_error,'maximumLimbLengthErrorSourceUnits':maximum_length_error,
        'maximumPelvisShiftSourceUnits':maximum_shift,'nativeFloorSourceUnits':0.,
        'handRelativeWeaponPreserved':True,'nativeImported':False,'accepted':False,'frames':records}
DEST.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
print('TARGET_BOOT_GROUNDING_AUTHORED_NOT_ACCEPTED',flush=True)
