"""Refine measured boot support by common-body translation in actual Blender.

Source joint rotations, relative poses, lengths and grips remain untouched.
Only measured near-ground support receives a bounded root-path correction.
Airborne cycle boundaries and all relative joint poses remain unchanged.

STOPPED STUDY: both fixed-anchor and rolling-support whole-body approaches
exceeded the original correction bounds. Preserve for diagnostic reproduction;
do not tune the bounds or use this as an importable motion generator.
"""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,action='append',required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--reproduce-stopped-study',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
if not a.reproduce_stopped_study:raise SystemExit('Whole-body support study stopped after two failed approaches; use a different contact method')
sources=[s.resolve(strict=True) for s in a.source];out=a.output.resolve()
assert 1<=len(sources)<=2 and all(s.is_relative_to(ROOT/'Local') for s in sources)
assert out.is_relative_to(ROOT/'Local') and not out.exists()
scale=json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
metadata=[json.loads(s.with_suffix('.json').read_text()) for s in sources]
for source,meta in zip(sources,metadata):
    assert meta['provider']=='accad' and not meta.get('candidateStopped')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==meta['editableSceneSHA256']
bpy.ops.wm.open_mainfile(filepath=str(sources[0]),load_ui=False)
scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison'];fps=scene.render.fps/scene.render.fps_base
assert fps==120;end=scene.frame_end
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(meshes)==1, 'Use an explicit multi-mesh support sampler for another rig'
body=meshes[0];indices={}
for side in ['Left','Right']:
    groups={g.index for g in body.vertex_groups if g.name in [side+'Foot',side+'ToeBase']}
    indices[side]=[v.index for v in body.data.vertices if sum(w.weight for w in v.groups if w.group in groups)>.75]
    assert len(indices[side])>20
samples=[]
for frame in range(end+1):
    scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();obj=body.evaluated_get(deps);mesh=obj.to_mesh()
    feet={side:[obj.matrix_world @ mesh.vertices[i].co for i in ids] for side,ids in indices.items()}
    obj.to_mesh_clear();samples.append({'feet':feet,'hip':(rig.matrix_world @ rig.pose.bones['Hips'].matrix).translation.copy()})
heights={side:[min(v.z for v in row['feet'][side])*scale for row in samples] for side in indices}
speeds=[]
for i in range(end+1):
    lo,hi=max(0,i-1),min(end,i+1);v=samples[hi]['hip']-samples[lo]['hip'];v.z=0;speeds.append(v.length*scale*fps/(hi-lo))
def smooth(v):
    v=max(0.,min(1.,v));return v*v*(3-2*v)
contributions=[[] for _ in samples];regions=[]
for side,hs in heights.items():
    groups=[];active=[]
    for i,h in enumerate(hs):
        if h<6. and speeds[i]>20.:active.append(i)
        elif active:groups.append(active);active=[]
    if active:groups.append(active)
    for frames in groups:
        if len(frames)<4:continue
        minimum=min(hs[i] for i in frames)
        core=min(4.5,minimum+1.5);edge=min(6.,minimum+3.)
        core_frames=[i for i in frames if hs[i]<=core]
        if not core_frames:continue
        regions.append({'side':side,'firstFrame':frames[0],'lastFrame':frames[-1],'minimumBootCm':minimum,'fullSupportHeightCm':core,'fadeHeightCm':edge})
        for i in frames:
            weight=smooth((edge-hs[i])/max(.1,edge-core))*smooth((speeds[i]-20)/40)
            contributions[i].append((weight,(.05-hs[i])/scale))
vertical=[]
for i,parts in enumerate(contributions):
    total=sum(w for w,_ in parts);dz=sum(d*w for w,d in parts)/max(1.,total)
    vertical.append(max(dz,(.05-min(heights[s][i] for s in indices))/scale))
# A fixed vertex chosen later in a long stance fights heel-to-toe rolling.
# Instead cancel the measured tangential motion of overlapping near-floor
# vertices, changing the support patch as the foot rolls. Release in flight.
offset=Vector();release=Vector();release_age=8;was_supported=False
support_counts={side:0 for side in indices}
corrections=[]
for i in range(end+1):
    displacements=[]
    if i:
        for side in indices:
            before=samples[i-1]['feet'][side];after=samples[i]['feet'][side]
            support=[j for j,(v,w) in enumerate(zip(before,after)) if -.5<=(v.z+vertical[i-1])*scale<=1.05 and -.5<=(w.z+vertical[i])*scale<=1.05]
            if len(support)<8:continue
            displacements.append(Vector((statistics.median(after[j].x-before[j].x for j in support),statistics.median(after[j].y-before[j].y for j in support),0)))
            if 16<=i<=96:support_counts[side]+=1
    if displacements:
        offset-=sum(displacements,Vector())/len(displacements);release_age=0;was_supported=True
    else:
        if was_supported:release=offset.copy();release_age=0
        was_supported=False;release_age+=1;offset=release*(1-smooth(release_age/8))
    delta=Vector((offset.x,offset.y,vertical[i]))
    planar=Vector((delta.x,delta.y,0)).length*scale
    assert planar<=12. and abs(delta.z)*scale<=6., f'Frame{i}: support correction {planar:.3f}cm planar/{abs(delta.z)*scale:.3f}cm vertical exceeds12cm/6cm'
    corrections.append(delta)
assert all(count>=4 for count in support_counts.values()), 'Running stride still has insufficient actual boot support'
assert all(corrections[i].length*scale<.01 for i in [16,96]), 'Airborne cycle boundary was modified'
out.mkdir(parents=True);reports=[]
for source,meta in zip(sources,metadata):
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False);scene=bpy.context.scene;rig=bpy.data.objects['Knight_Comparison']
    assert scene.frame_end==end and scene.render.fps/scene.render.fps_base==fps
    original=rig.animation_data.action;original.use_fake_user=True;poses=[]
    for frame in range(end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        hip=(rig.matrix_world @ rig.pose.bones['Hips'].matrix).translation
        assert (hip-samples[frame]['hip']).length*scale<.01, 'Sources do not share the same lower-body motion'
        poses.append({'basis':{b.name:b.matrix_basis.copy() for b in rig.pose.bones},'worlds':{b.name:(rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones}})
    name=source.stem.rsplit('_v',1)[0]+'_v11support';action=bpy.data.actions.new(name);rig.animation_data.action=action;previous={};error=0.
    for frame,row in enumerate(poses):
        scene.frame_set(frame)
        for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.matrix_basis=row['basis'][bone.name]
        bpy.context.view_layer.update();root=rig.pose.bones['VeyrRoot'];m=rig.matrix_world @ root.matrix;m.translation+=corrections[frame];root.matrix=rig.matrix_world.inverted() @ m;bpy.context.view_layer.update()
        for bone in rig.pose.bones:
            expected=row['worlds'][bone.name].copy();expected.translation+=corrections[frame];actual=rig.matrix_world @ bone.matrix
            error=max(error,max(abs(actual[i][j]-expected[i][j]) for i in range(4) for j in range(4)))
            q=bone.rotation_quaternion.copy()
            if bone.name in previous:q.make_compatible(previous[bone.name])
            bone.rotation_quaternion=q;previous[bone.name]=q.copy()
            for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(prop,frame=frame)
    assert error<1e-5
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(0);bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for obj in scene.objects:
        if obj.type=='MESH' and not obj.hide_render and any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):obj.select_set(True)
    bpy.context.view_layer.objects.active=rig;dest=out/name
    bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')),compress=True)
    report={k:meta[k] for k in ['provider','license','sourceURL','attribution']};report.update(authoringApplication='Blender',source=str(source.relative_to(ROOT)),editableScene=str(dest.with_suffix('.blend').relative_to(ROOT)),editableSceneSHA256=hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),sha256=hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),fps=fps,duration=end/fps,relativePoseMatrixMaxError=error,maximumPlanarBodyCorrectionCm=max(Vector((v.x,v.y,0)).length*scale for v in corrections),maximumVerticalBodyCorrectionCm=max(abs(v.z)*scale for v in corrections),candidateStopped=True,diagnosticOnly=True,nativeImported=False,accepted=False)
    dest.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
(out/'support.json').write_text(json.dumps({'regions':regions,'runningSupportIntervals':support_counts,'supportMethod':'Median tangential displacement of the same near-floor boot vertices across each adjacent pair; source foot rolling preserved; eight-frame smooth airborne release','bodyCorrectionSourceUnits':[list(v) for v in corrections],'clips':reports,'scope':'Actual Blender bounded root-path adaptation; visual/native quality unaccepted'},indent=2)+'\n')
print('CONTIGUOUS_BOOT_SUPPORT_AUTHORED',len(reports),flush=True)
