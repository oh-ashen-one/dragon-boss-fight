"""Blender composition of corrected ACCAD start and existing greatsword holds.

Preserve the lower body and torso exactly. Phase-match the licensed Mixamo run
arms by distance/foot heights, blend from the existing idle, and correct the
paired grip with bounded no-stretch arm IK. No motion is authored from scratch.
"""
import hashlib
import argparse
import json
import math
from pathlib import Path
import statistics
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'Local/AttackSources20261105/ACCADMale1/SupportFitV5/ACCAD_StandToRun_v5support.blend'
IDLE = ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'
RUN = ROOT/'Local/AttackSources20261103/ForwardRigidPlants/Mixamo_ForwardRun_v4rigid.glb'
DEST = ROOT/'Local/AttackSources20261105/ACCADMale1/WeaponStartV6/ACCAD_StandToRunTwoHand_v6weapon'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path)
parser.add_argument('--output',type=Path)
parser.add_argument('--loop-frames',type=int,nargs=2,help='Match donor arm phase to one measured source stride')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert bool(args.source)==bool(args.output)
if args.source:
    SOURCE=args.source.resolve(strict=True);DEST=args.output.resolve()
    assert SOURCE.is_relative_to(ROOT/'Local') and DEST.is_relative_to(ROOT/'Local') and SOURCE.suffix=='.blend'
assert not DEST.with_suffix('.blend').exists()
meta = json.loads(SOURCE.with_suffix('.json').read_text())
assert meta['editableSceneSHA256'] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert meta['provider'] == 'accad' and not meta.get('candidateStopped')
helper = Path(__file__).with_name('fit_paired_grip.py')
ns = {'__file__': str(helper)}
exec(compile(helper.read_text().split('reports=[]')[0], str(helper), 'exec'), ns)
solve, chain, paired_shift = ns['solve'], ns['chain'], ns['paired_shift']
scale = json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']


def mix(a, b, w):
    p, q, s = a.decompose(); pp, qq, ss = b.decompose()
    return Matrix.LocRotScale(p.lerp(pp, w), q.slerp(qq, w), s.lerp(ss, w))


def world(rig, name):
    return (rig.matrix_world @ rig.pose.bones[name].matrix).copy()


def pose(rig):
    return {b.name: b.matrix_basis.copy() for b in rig.pose.bones}


def heights(rig):
    h = world(rig, 'Hips').translation.z
    return [world(rig, s+'Foot').translation.z-h for s in ['Left', 'Right']]


def smooth(t):
    t = min(1., max(0., t)); return t*t*(3-2*t)


bpy.ops.wm.open_mainfile(filepath=str(SOURCE), load_ui=False)
scene = bpy.context.scene; rig = bpy.data.objects['Knight_Comparison']
fps = scene.render.fps/scene.render.fps_base; end = scene.frame_end
rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
samples = []
for f in range(end+1):
    scene.frame_set(f); bpy.context.view_layer.update()
    samples.append({'basis': pose(rig), 'heights': heights(rig), 'hip': world(rig, 'Hips').translation})
distances = [0.]
for a, b in zip(samples, samples[1:]):
    delta = b['hip']-a['hip']; delta.z = 0
    distances.append(distances[-1]+delta.length)
speeds = [(distances[min(end, i+1)]-distances[max(0, i-1)])*fps*scale/(1 if i in [0, end] else 2) for i in range(end+1)]
arm_names = [n for n in rest if any(n.startswith(side+x) for side in ['Left', 'Right'] for x in ['Shoulder', 'Arm', 'ForeArm', 'Hand'])]
assert len(arm_names) >= 18
donors = {}
for key, path in [('idle', IDLE), ('run', RUN)]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.render.fps = 120
    bpy.ops.import_scene.gltf(filepath=str(path))
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    assert set(rig.data.bones.keys()) == set(rest)
    assert max(abs(rest[n][i][j]-rig.data.bones[n].matrix_local[i][j]) for n in rest for i in range(4) for j in range(4)) < 1e-5
    length = float(rig.animation_data.action.frame_range[1])
    scene.frame_set(0); bpy.context.view_layer.update(); first = world(rig, 'Hips').translation
    scene.frame_set(int(length), subframe=length-int(length)); bpy.context.view_layer.update()
    delta = world(rig, 'Hips').translation-first; delta.z = 0
    rows = []
    for i in range(60):
        f = length*i/60; scene.frame_set(int(f), subframe=f-int(f)); bpy.context.view_layer.update()
        rows.append({'basis': pose(rig), 'heights': heights(rig),
                     'grip': world(rig, 'RightHand').inverted() @ world(rig, 'WeaponSocket')})
    donors[key] = {'rows': rows, 'travel': delta.length}
    if key == 'idle':
        scene.frame_set(0); bpy.context.view_layer.update()
        inv = rig.data.bones['LeftHand'].matrix_local.inverted()
        pts = {n: inv @ rig.data.bones['LeftHand'+n].head_local for n in ['Index', 'Pinky', 'Middle']}
        longitudinal = pts['Middle'].normalized(); shaft = (pts['Index']-pts['Pinky']).normalized()
        across = (longitudinal-shaft*longitudinal.dot(shaft)).normalized()
        palm = (pts['Index']+pts['Pinky'])*.5-across*.010
        idle_palm = world(rig, 'WeaponSocket').inverted() @ (world(rig, 'LeftHand') @ palm)
stride = donors['run']['travel']; assert .1 < stride < 5
active = [i for i in range(0, end+1, 4) if speeds[i] > .6*max(speeds)]
if args.loop_frames:
    first,last=args.loop_frames;assert 0<=first<last<=end
    stride=distances[last]-distances[first];assert .1<stride<5
    active=list(range(first,last,4))
assert len(active) > 5
def norm(rows):
    means = [statistics.mean(row[s] for row in rows) for s in range(2)]
    dev = [max(.001, statistics.pstdev(row[s] for row in rows)) for s in range(2)]
    return [[(row[s]-means[s])/dev[s] for s in range(2)] for row in rows]
target = norm([samples[i]['heights'] for i in active]); donor = norm([r['heights'] for r in donors['run']['rows']])
offset = min(range(60), key=lambda k: sum((target[j][s]-donor[(round(distances[i]/stride*60)+k)%60][s])**2 for j, i in enumerate(active) for s in range(2)))/60
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), load_ui=False)
scene = bpy.context.scene; rig = bpy.data.objects['Knight_Comparison']
rig.animation_data.action.use_fake_user = True
action = bpy.data.actions.new(DEST.stem); rig.animation_data.action = action
previous = {}; shifts = []; errors = []; lower_error = 0.
blended = []
for f, sample in enumerate(samples):
    scene.frame_set(f)
    phase = ((distances[f]/stride+offset)%1)*60; index = int(phase); alpha = phase-index
    ar, br = donors['run']['rows'][index], donors['run']['rows'][(index+1)%60]
    idle = donors['idle']['rows'][0]; weight = smooth((speeds[f]-20)/220)
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        bone.matrix_basis = mix(idle['basis'][bone.name], mix(ar['basis'][bone.name], br['basis'][bone.name], alpha), weight) if bone.name in arm_names else sample['basis'][bone.name]
    bpy.context.view_layer.update()
    grip = mix(idle['grip'], mix(ar['grip'], br['grip'], alpha), weight)
    socket = world(rig, 'RightHand') @ grip
    left, right = chain(rig, 'Left'), chain(rig, 'Right')
    blended.append({'basis': pose(rig), 'socket': socket, 'left': left, 'right': right, 'weight': weight})
# Find one handle location that both original-length arms can reach throughout
# the clip. The heavy attack's contact distance is not necessarily suitable
# for a different running hold. Keep the same bounded common-shift limit.
choices = []
for step in range(45):
    hold_offset = -.36+step*.005
    cost = 0.
    for row in blended:
        target_palm = row['socket'] @ idle_palm.lerp(Vector((0, hold_offset, 0)), row['weight'])
        desired = target_palm-row['left'][2].to_3x3() @ palm
        shift = paired_shift(row['left'], row['right'], desired, .06)
        if shift is None: break
        cost += (desired+shift-row['left'][2].translation).length_squared+2*shift.length_squared
    else:
        choices.append((cost, hold_offset))
assert choices, 'No constant shaft contact is reachable within the original correction bound'
_, hold_offset = min(choices)
for f, (sample, row) in enumerate(zip(samples, blended)):
    scene.frame_set(f)
    for bone in rig.pose.bones: bone.matrix_basis = row['basis'][bone.name]
    bpy.context.view_layer.update()
    socket = row['socket'].copy(); left, right = chain(rig, 'Left'), chain(rig, 'Right')
    shaft_point = idle_palm.lerp(Vector((0, hold_offset, 0)), row['weight'])
    target_palm = socket @ shaft_point
    left_target = target_palm-left[2].to_3x3() @ palm
    shift = paired_shift(left, right, left_target, .06)
    assert shift is not None, f'Unreachable paired grip at frame{f}'
    for side, original, target in [('Right', right, right[2].translation+shift), ('Left', left, left_target+shift)]:
        solved = original if (original[2].translation-target).length < 1e-7 else solve(original, target)
        for suffix, matrix in zip(['Arm', 'ForeArm', 'Hand'], solved):
            rig.pose.bones[side+suffix].matrix = rig.matrix_world.inverted() @ matrix
            bpy.context.view_layer.update()
    socket.translation += shift
    rig.pose.bones['WeaponSocket'].matrix = rig.matrix_world.inverted() @ socket
    bpy.context.view_layer.update()
    error = ((world(rig, 'LeftHand') @ palm)-(socket @ shaft_point)).length
    assert error < 1e-5
    for bone in rig.pose.bones:
        if bone.name not in arm_names and bone.name != 'WeaponSocket':
            lower_error = max(lower_error, max(abs(bone.matrix_basis[i][j]-sample['basis'][bone.name][i][j]) for i in range(4) for j in range(4)))
        q = bone.rotation_quaternion.copy()
        if bone.name in previous: q.make_compatible(previous[bone.name])
        bone.rotation_quaternion = q; previous[bone.name] = q.copy()
        for prop in ['location', 'rotation_quaternion', 'scale']: bone.keyframe_insert(prop, frame=f)
    shifts.append(shift.length*scale); errors.append(error*scale)
assert lower_error < 3e-5
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points: key.interpolation = 'LINEAR'
scene.frame_set(0); bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
for obj in scene.objects:
    if obj.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in obj.modifiers): obj.select_set(True)
bpy.context.view_layer.objects.active = rig; DEST.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(DEST.with_suffix('.glb')), export_format='GLB', use_selection=True,
    export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_frame_range=True,
    export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(DEST.with_suffix('.blend')), compress=True)
report = {'provider': 'accad', 'authoringApplication': 'Blender', 'sources': [{'file': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [SOURCE, IDLE, RUN]],
    'editableScene': str(DEST.with_suffix('.blend').relative_to(ROOT)), 'editableSceneSHA256': hashlib.sha256(DEST.with_suffix('.blend').read_bytes()).hexdigest(),
    'sha256': hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest(), 'fps': fps, 'duration': end/fps,
    'upperPhaseOffsetCycles': offset, 'constantRunGripOffsetOnShaft': hold_offset,
    'maximumPairedGripShiftCm': max(shifts), 'maximumLeftGripErrorCm': max(errors),
    'maximumLowerTorsoBasisError': lower_error, 'lowerBodyAndTorsoPreserved': True,
    'licenses': ['ACCAD CC BY 3.0', 'Adobe Mixamo project incorporation; no raw-library redistribution'],
    'license':meta.get('license','CC BY 3.0'),'sourceURL':meta.get('sourceURL','https://accad.ohio-state.edu/research/motion-lab/mocap-system-and-data'),
    'phaseMatchedSourceLoopFrames':args.loop_frames,
    'attribution': meta['attribution'], 'nativeImported': False, 'accepted': False}
DEST.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
print('ACCAD_GREATSWORD_START_AUTHORED_NOT_ACCEPTED', flush=True)
