"""Extract a sourced run/exit pair in Blender with a small airborne loop seam.

The exit retains the entire loop prefix, so any running phase has an identical
exit entry pose. Contact frames remain the source poses. No whole stride freeze,
limb stretching, generated motion, or native acceptance is implied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
source=a.source.resolve(strict=True);out=a.output.resolve()
assert source.is_relative_to(ROOT/'Local') and out.is_relative_to(ROOT/'Local') and not out.exists()
metadata=json.loads(source.with_suffix('.json').read_text())
assert metadata['provider']=='accad' and not metadata.get('candidateStopped')
assert hashlib.sha256(source.read_bytes()).hexdigest()==metadata['editableSceneSHA256']
bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];fps=scene.render.fps/scene.render.fps_base
assert abs(fps-120)<.001
for obj in scene.objects:
    if obj.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):
        group=obj.vertex_groups.get('VeyrRoot')
        if group:assert not any(w.group==group.index and w.weight>1e-6 for v in obj.data.vertices for w in v.groups), 'Helper root has visible skin weights'
first,last,fade=16,96,8 # Original 30fps capture frames4..24; two airborne frames per side.
end=scene.frame_end;assert end>last+fade
scale=json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
original=rig.animation_data.action;original.use_fake_user=True
rows=[]
for f in range(first,end+1):
    scene.frame_set(f);bpy.context.view_layer.update()
    rows.append({'locals':{b.name:(b.parent.matrix.inverted() @ b.matrix if b.parent else b.matrix.copy()) for b in rig.pose.bones},
                 'worlds':{b.name:(rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones}})
length=last-first;start,finish=rows[0],rows[length]
seam={}
for bone in rig.pose.bones:
    if bone.name=='WeaponSocket':continue # Root-parented prop, not an anatomical limb.
    loc0,q0,sc0=start['locals'][bone.name].decompose();loc1,q1,sc1=finish['locals'][bone.name].decompose()
    q1.make_compatible(q0)
    if bone.name not in ['Hips','VeyrRoot']:
        assert abs(loc0.length-loc1.length)*scale<.01, f'{bone.name}: source limb length changes'
    assert (sc0-sc1).length<.0001
    mid=(loc0+loc1)*.5
    if bone.name not in ['Hips','VeyrRoot'] and mid.length>1e-8:mid=mid.normalized()*loc0.length
    seam[bone.name]=(mid,q0.slerp(q1,.5),(sc0+sc1)*.5)
origin=start['worlds']['Hips'].translation.copy();origin.z=0
seam_height=(start['worlds']['Hips'].translation.z+finish['worlds']['Hips'].translation.z)*.5
out.mkdir(parents=True)
all_worlds={};reports=[]
def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)

for name,count in [('ACCAD_RunCycle_v9seam',length),('ACCAD_RunExit_v9seam',end-first)]:
    action=bpy.data.actions.new(name);rig.animation_data.action=action
    scene.frame_start,scene.frame_end=0,count
    previous={};worlds=[];max_change=0.;max_root_rebase=0.;max_contact_change=0.;max_length_change=0.
    for f in range(count+1):
        row=rows[f];scene.frame_set(f)
        weight=0.
        if f<fade:weight=1-smooth(f/fade)
        elif abs(f-length)<fade:weight=1-smooth(abs(f-length)/fade)
        for bone in rig.pose.bones:
            if bone.name=='WeaponSocket':continue
            bone.rotation_mode='QUATERNION';local=row['locals'][bone.name].copy()
            if weight:
                loc,q,sc=local.decompose();sl,sq,ss=seam[bone.name];sq=sq.copy();sq.make_compatible(q)
                fitted=loc.lerp(sl,weight)
                if bone.name not in ['Hips','VeyrRoot'] and fitted.length>1e-8:fitted=fitted.normalized()*loc.length
                local=Matrix.LocRotScale(fitted,q.slerp(sq,weight),sc)
            bone.matrix=bone.parent.matrix @ local if bone.parent else local
            bpy.context.view_layer.update()
        bpy.context.view_layer.update()
        desired=row['worlds']['Hips'].translation.copy()-origin
        desired.z=(1-weight)*desired.z+weight*seam_height
        actual=rig.matrix_world @ rig.pose.bones['Hips'].matrix
        root=rig.pose.bones['VeyrRoot'];m=rig.matrix_world @ root.matrix;m.translation+=desired-actual.translation
        root.matrix=rig.matrix_world.inverted() @ m;bpy.context.view_layer.update()
        # This socket is parented to VeyrRoot, but its actual grip is constant
        # relative to RightHand. Restore that grip after changing the arm pose.
        grip=row['worlds']['RightHand'].inverted() @ row['worlds']['WeaponSocket']
        rig.pose.bones['WeaponSocket'].matrix=rig.pose.bones['RightHand'].matrix @ grip
        bpy.context.view_layer.update()
        current={b.name:(rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones};worlds.append(current)
        for bone in rig.pose.bones:
            expected=row['worlds'][bone.name].translation-origin
            change=(current[bone.name].translation-expected).length*scale
            # The unskinned helper root absorbs planar pelvis re-expression;
            # measure visible/anatomical corrections separately from that rebase.
            if bone.name=='VeyrRoot':max_root_rebase=max(max_root_rebase,change)
            else:max_change=max(max_change,change)
            if weight==0:max_contact_change=max(max_contact_change,change)
            # Root-to-pelvis distance contains authored locomotion translation,
            # not a bone length. Only anatomical links are length constrained.
            if bone.parent and bone.name not in ['WeaponSocket','Hips','VeyrRoot']:
                before=(row['worlds'][bone.name].translation-row['worlds'][bone.parent.name].translation).length
                after=(current[bone.name].translation-current[bone.parent.name].translation).length
                max_length_change=max(max_length_change,abs(before-after)*scale)
            q=bone.rotation_quaternion.copy()
            if bone.name in previous:q.make_compatible(previous[bone.name])
            bone.rotation_quaternion=q;previous[bone.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(prop,frame=f)
    assert max_contact_change<.01 and max_length_change<.01, f'Uncorrected pose change {max_contact_change:.6f}cm; anatomical length change {max_length_change:.6f}cm'
    assert max_change<20, 'Airborne seam correction too large; reject source fit'
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    all_worlds[name]=worlds
    scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for obj in scene.objects:
        if obj.type=='MESH' and not obj.hide_render and any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):obj.select_set(True)
    bpy.context.view_layer.objects.active=rig;dest=out/name
    bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
    report={k:metadata[k] for k in ['provider','license','sourceURL','attribution']}
    report.update(source=str(source.relative_to(ROOT)),authoringApplication='Blender',editableScene=str(dest.with_suffix('.blend').relative_to(ROOT)),editableSceneSHA256=hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),sha256=hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),sourceFrames120fps=[first,first+count],fps=fps,duration=count/fps,maximumAirborneSeamChangeCm=max_change,maximumHelperRootRebaseCm=max_root_rebase,maximumUncorrectedPoseChangeCm=max_contact_change,maximumLimbLengthChangeCm=max_length_change,nativeImported=False,accepted=False)
    dest.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
loop,exit=all_worlds.values()
prefix_error=max(abs(loop[f][n][i][j]-exit[f][n][i][j]) for f in range(length+1) for n in loop[f] for i in range(4) for j in range(4))
travel=loop[-1]['Hips'].translation-loop[0]['Hips'].translation
seam_error=max((loop[-1][n].translation-loop[0][n].translation-travel).length*scale for n in loop[0])
assert prefix_error<1e-5 and seam_error<.01
(out/'pair.json').write_text(json.dumps({'clips':reports,'loopPrefixPoseEqualityError':prefix_error,'loopSeamRelativePositionErrorCm':seam_error,'rootTravelSourceUnits':list(travel),'scope':'Actual Blender source adaptation; source/native contacts and visual quality remain unaccepted'},indent=2)+'\n')
print('CONTIGUOUS_RUN_EXIT_EXTRACTED',prefix_error,seam_error,flush=True)
