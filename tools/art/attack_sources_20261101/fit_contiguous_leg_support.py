"""Blender supporting-leg correction for the licensed contiguous run/stop.

Preserve captured foot rotation/rolling, original limb lengths and upper-body
poses relative to the pelvis. Correct each foot separately during its measured
support interval, returning to the captured pose before lift-off. Never freeze
the whole stride or enlarge the original correction bounds to force a pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=a.source.resolve(strict=True);dest=a.output.resolve()
assert source.is_relative_to(ROOT/'Local') and dest.is_relative_to(ROOT/'Local') and not dest.with_suffix('.blend').exists()
meta=json.loads(source.with_suffix('.json').read_text());assert meta['provider']=='accad' and not meta.get('candidateStopped')
assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['editableSceneSHA256']
helper=Path(__file__).with_name('fit_paired_grip.py');ns={'__file__':str(helper)}
exec(compile(helper.read_text().split('reports=[]')[0],str(helper),'exec'),ns);solve=ns['solve']
scale=json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];fps=scene.render.fps/scene.render.fps_base;end=scene.frame_end
assert fps==120
body=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(body)==1;body=body[0];indices={}
for side in ['Left','Right']:
    groups={g.index for g in body.vertex_groups if g.name in [side+'Foot',side+'ToeBase']}
    indices[side]=[v.index for v in body.data.vertices if sum(w.weight for w in v.groups if w.group in groups)>.75]
    assert len(indices[side])>20
def world(name):return (rig.matrix_world @ rig.pose.bones[name].matrix).copy()
def boot_vertices():
    obj=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh()
    feet={s:[obj.matrix_world @ mesh.vertices[i].co for i in ids] for s,ids in indices.items()}
    obj.to_mesh_clear();return feet
def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)
original=rig.animation_data.action;original.use_fake_user=True;samples=[]
for frame in range(end+1):
    scene.frame_set(frame);bpy.context.view_layer.update()
    samples.append({'basis':{b.name:b.matrix_basis.copy() for b in rig.pose.bones},'worlds':{b.name:world(b.name) for b in rig.pose.bones},'feet':boot_vertices()})
# Use the captured toe trajectory, rather than inventing a fixed floor point.
# The ankle-only retarget preserves ankle travel but mismatches the target boot's
# toe lever. Map the original BVH toe at the actual source time and solve the
# ankle translation needed to retain that trace with the target foot rotation.
src=bpy.data.objects['Source_accad'];retarget_scale=float(scene['retarget_scale'])
source_start,source_end=map(float,src.animation_data.action.frame_range)
source_rest={n:(src.matrix_world @ src.data.bones[n].matrix_local).translation.copy() for n in ['Hips','LeftToeBase','RightToeBase']}
target_rest={n:(rig.matrix_world @ rig.data.bones[n].matrix_local).translation.copy() for n in ['LeftToeBase','RightToeBase']}
scene.frame_set(int(source_start),subframe=source_start-int(source_start));bpy.context.view_layer.update()
source_offset=(src.matrix_world @ src.pose.bones['Hips'].matrix).translation-source_rest['Hips'];source_offset.z=0
mapped={side:[] for side in indices}
for i in range(end+1):
    f=source_start+(source_end-source_start)*i/end
    scene.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update()
    for side in indices:
        name=side+'ToeBase';point=(src.matrix_world @ src.pose.bones[name].matrix).translation
        mapped[side].append(target_rest[name]+(point-source_rest[name]-source_offset)*retarget_scale)
# Running forefoot contact occurs above the standing toe-joint reference.
# Derive stance envelopes from local minima of the actual boot, then constrain
# its sole directly. A toe marker staying above ground is not floor contact.
source_heights={side:[min(v.z for v in row['feet'][side])*scale for row in samples] for side in indices}
speeds=[]
for i in range(end+1):
    lo,hi=max(0,i-1),min(end,i+1);v=samples[hi]['worlds']['Hips'].translation-samples[lo]['worlds']['Hips'].translation;v.z=0
    speeds.append(v.length*scale*fps/(hi-lo))
contact_weights={side:[0. for _ in samples] for side in indices};regions=[]
for side,hs in source_heights.items():
    groups=[];active=[]
    for i,h in enumerate(hs):
        if h<6. and speeds[i]>20:active.append(i)
        elif active:groups.append(active);active=[]
    if active:groups.append(active)
    for frames in groups:
        if len(frames)<4:continue
        minimum=min(hs[i] for i in frames);core=min(4.5,minimum+1.5);edge=min(6.,minimum+3.)
        for i in frames:contact_weights[side][i]=smooth((edge-hs[i])/max(.1,edge-core))*smooth((speeds[i]-20)/40)
        regions.append({'side':side,'firstFrame':frames[0],'lastFrame':frames[-1],'minimumBootCm':minimum,'fullSupportHeightCm':core,'fadeHeightCm':edge,'method':'Captured toe X/Y with actual boot-sole stance envelope; no fixed world-point locking'})
# Place the foot before landing, not while its sole is already near the floor.
# Hold the captured toe-path alignment through a grounded deceleration even as
# capsule speed falls. The endpoint anchor already returns its X/Y offset to0.
horizontal_weights={side:[] for side in indices}
for side,hs in source_heights.items():
    held=0.;release=0.;air_frames=8
    for i,h in enumerate(hs):
        anticipated=max(contact_weights[side][i:min(end+1,i+9)])
        if h<=6.:
            held=max(held,anticipated);air_frames=0;release=held
        else:
            air_frames+=1;held=max(anticipated,release*(1-smooth(air_frames/8)))
        horizontal_weights[side].append(held)
offsets={side:[Vector() for _ in samples] for side in indices}
desired_soles={side:[] for side in indices}
for side,goals in mapped.items():
    name=side+'ToeBase';anchor=samples[-1]['worlds'][name].translation-goals[-1]
    for i,point in enumerate(goals):
        weight=contact_weights[side][i];delta=point+anchor-samples[i]['worlds'][name].translation
        offsets[side][i]=Vector((delta.x*horizontal_weights[side][i],delta.y*horizontal_weights[side][i],0))
        desired_soles[side].append((1-weight)*source_heights[side][i]+weight*.05)
for side in indices:
    for i,v in enumerate(offsets[side]):
        planar=Vector((v.x,v.y,0)).length*scale
        assert planar<=12 and abs(v.z)*scale<=6, f'{side} frame{i}: source-toe retarget {planar:.3f}cm planar/{abs(v.z)*scale:.3f}cm vertical exceeds12/6cm'
    assert all(offsets[side][i].length*scale<.01 for i in [16,96,end]), 'Cycle boundary or final stance target changed'
action=bpy.data.actions.new(dest.stem);rig.animation_data.action=action;previous={};measurements=[]
leg_names={s+n for s in indices for n in ['UpLeg','Leg','Foot','ToeBase']}
for frame,row in enumerate(samples):
    scene.frame_set(frame)
    targets={side:row['worlds'][side+'Foot'].translation+offsets[side][frame] for side in indices}
    sole_lifts={side:0. for side in indices}
    for sole_iteration in range(4):
        for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.matrix_basis=row['basis'][bone.name]
        bpy.context.view_layer.update();chains={side:[world(side+n) for n in ['UpLeg','Leg','Foot']] for side in indices}
        shift=Vector()
        for side in indices:
            correction=targets[side]-row['worlds'][side+'Foot'].translation
            assert Vector((correction.x,correction.y,0)).length*scale<=12 and abs(correction.z)*scale<=6, f'Frame{frame}: sole fitting exceeded original foot correction bounds'
        for _ in range(80):
            for side,chain in chains.items():
                maximum=sum((chain[i+1].translation-chain[i].translation).length for i in range(2))-.0001
                delta=targets[side]-chain[0].translation-shift
                if delta.length>maximum:shift+=delta.normalized()*(delta.length-maximum)
        assert shift.length*scale<=6, f'Frame{frame}: pelvis correction {shift.length*scale:.3f}cm exceeds6cm'
        hip=world('Hips');hip.translation+=shift;rig.pose.bones['Hips'].matrix=rig.matrix_world.inverted() @ hip;bpy.context.view_layer.update()
        for side in indices:
            chain=[world(side+n) for n in ['UpLeg','Leg','Foot']]
            fitted=chain if (chain[2].translation-targets[side]).length<1e-7 else solve(chain,targets[side])
            for suffix,matrix in zip(['UpLeg','Leg','Foot'],fitted):
                rig.pose.bones[side+suffix].matrix=rig.matrix_world.inverted() @ matrix;bpy.context.view_layer.update()
        actual_feet=boot_vertices();minima={side:min(v.z for v in points)*scale for side,points in actual_feet.items()}
        if all(abs(minima[side]-desired_soles[side][frame])<.01 for side in indices) and min(minima.values())>=.04:break
        for side in indices:
            lift=(desired_soles[side][frame]-minima[side])/scale;targets[side].z+=lift;sole_lifts[side]+=lift*scale
    else:raise ValueError(f'Frame{frame}: actual boot sole did not converge to the floor')
    # WeaponSocket is a root child, so carry it with the translated torso/hand.
    socket=row['worlds']['WeaponSocket'].copy();socket.translation+=shift;rig.pose.bones['WeaponSocket'].matrix=rig.matrix_world.inverted() @ socket;bpy.context.view_layer.update()
    upper_error=length_error=target_error=0.
    for bone in rig.pose.bones:
        actual=world(bone.name)
        if bone.name not in leg_names and bone.name!='VeyrRoot':
            expected=row['worlds'][bone.name].copy();expected.translation+=shift
            upper_error=max(upper_error,max(abs(actual[i][j]-expected[i][j]) for i in range(4) for j in range(4)))
        q=bone.rotation_quaternion.copy()
        if bone.name in previous:q.make_compatible(previous[bone.name])
        bone.rotation_quaternion=q;previous[bone.name]=q.copy()
        for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(prop,frame=frame)
    for side in indices:
        after=[world(side+n) for n in ['UpLeg','Leg','Foot']]
        target_error=max(target_error,(after[2].translation-targets[side]).length*scale)
        length_error=max(length_error,max(abs((after[i+1].translation-after[i].translation).length-(chains[side][i+1].translation-chains[side][i].translation).length)*scale for i in range(2)))
    feet=boot_vertices();minimum=min(v.z*scale for points in feet.values() for v in points)
    assert upper_error<1e-5 and length_error<.01 and target_error<.01
    assert minimum>=.04, f'Frame{frame}: actual skinned sole penetrates {minimum:.3f}cm'
    measurements.append({'frame':frame,'pelvisShiftCm':shift.length*scale,'upperPoseMatrixError':upper_error,'limbLengthErrorCm':length_error,'targetErrorCm':target_error,'minimumBootCm':minimum,'soleFitIterations':sole_iteration+1,'additionalSoleLiftCm':sole_lifts,'contactWeights':{side:contact_weights[side][frame] for side in indices},'horizontalWeights':{side:horizontal_weights[side][frame] for side in indices},'desiredSoleCm':{side:desired_soles[side][frame] for side in indices},'actualSoleCm':minima})
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
dest.parent.mkdir(parents=True,exist_ok=True);scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
report={k:meta[k] for k in ['provider','license','sourceURL','attribution']};report.update(authoringApplication='Blender',source=str(source.relative_to(ROOT)),editableScene=str(dest.with_suffix('.blend').relative_to(ROOT)),editableSceneSHA256=hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),sha256=hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),fps=fps,duration=end/fps,contactRegions=regions,sourceToeCaptureFrames=[source_start,source_end],horizontalPlacementLeadSeconds=2/30,measurements=measurements,nativeImported=False,accepted=False)
dest.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
print('CONTIGUOUS_SUPPORTING_LEGS_AUTHORED',flush=True)
