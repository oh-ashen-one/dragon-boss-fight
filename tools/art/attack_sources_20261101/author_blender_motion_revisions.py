"""Author sourced one-hand run composition and running-entry trim in Blender.

Run only in the task-owned Blender through gpu_slot. The lower run must first
be refined from its editable source by refine_forward_run_contacts.py with
--rigid-stance. CPU diagnostic GLBs are not input to this authoring workflow.
"""
import bpy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'Local/AttackSources20261104/BlenderMotion'
LOWER = ROOT/'Local/AttackSources20261103/ForwardRigidPlants/Mixamo_ForwardRun_v4rigid.blend'
UPPER = ROOT/'Local/CustomuseAssets/Sourced20261025b/knight/Fab_RunOneHand_v18.glb'
RUNNING = ROOT/'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports/Mixamo_SlideAttack_v2.blend'


def linear(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'


def save_export(rig, name, report):
    dest = OUT/name
    assert not dest.with_suffix('.blend').exists()
    bpy.context.scene.frame_set(0)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in obj.modifiers):
            obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')), export_format='GLB', use_selection=True,
        export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_frame_range=True,
        export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')), compress=True)
    report.update(authoringApplication='Blender', editableScene=str(dest.with_suffix('.blend').relative_to(ROOT)),
        editableSceneSHA256=hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),
        sha256=hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(), accepted=False, nativeImported=False)
    dest.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')


def height_pair(rig):
    hip = (rig.matrix_world @ rig.pose.bones['Hips'].matrix).translation.z
    return [(rig.matrix_world @ rig.pose.bones[side+'Foot'].matrix).translation.z-hip for side in ['Left', 'Right']]


def normalized(values):
    means = [sum(v[i] for v in values)/len(values) for i in range(2)]
    deviations = [math.sqrt(sum((v[i]-means[i])**2 for v in values)/len(values)) for i in range(2)]
    assert min(deviations) > 1e-5
    return [[(v[i]-means[i])/deviations[i] for i in range(2)] for v in values]


def compose_run():
    bpy.ops.wm.open_mainfile(filepath=str(LOWER), load_ui=False)
    scene = bpy.context.scene
    rig = bpy.data.objects['Knight_Comparison']
    names = ['VeyrRoot', 'Hips']+[side+n for side in ['Left', 'Right'] for n in ['UpLeg', 'Leg', 'Foot', 'ToeBase']]
    fps, end = scene.render.fps/scene.render.fps_base, scene.frame_end
    rest = {n: rig.data.bones[n].matrix_local.copy() for n in names}
    lower = []
    for frame in range(end+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        lower.append({n: rig.pose.bones[n].matrix_basis.copy() for n in names})
    low_heights = []
    for i in range(60):
        t = end*i/60
        scene.frame_set(int(t), subframe=t-int(t))
        bpy.context.view_layer.update()
        low_heights.append(height_pair(rig))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = round(fps)
    bpy.ops.import_scene.gltf(filepath=str(UPPER))
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    rig.name = 'Knight_Comparison'
    original = rig.animation_data.action
    original.use_fake_user = True
    upper_end = float(original.frame_range[1])
    assert max(abs(rest[n][i][j]-rig.data.bones[n].matrix_local[i][j]) for n in names for i in range(4) for j in range(4)) < 1e-5
    upper_heights = []
    for i in range(60):
        t = upper_end*i/60
        scene.frame_set(int(t), subframe=t-int(t))
        bpy.context.view_layer.update()
        upper_heights.append(height_pair(rig))
    ah, bh = normalized(upper_heights), normalized(low_heights)
    offset = min(range(60), key=lambda k: sum((ah[(i+k)%60][s]-bh[i][s])**2 for i in range(60) for s in range(2)))/60
    poses = []
    for frame in range(end+1):
        t = ((frame/end+offset)%1)*upper_end
        scene.frame_set(int(t), subframe=t-int(t))
        bpy.context.view_layer.update()
        poses.append(({b.name: b.matrix_basis.copy() for b in rig.pose.bones},
                      rig.pose.bones['RightHand'].matrix.inverted() @ rig.pose.bones['WeaponSocket'].matrix))
    name = 'FabMixamo_OneHandRun_v2blender'
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    scene.frame_start, scene.frame_end = 0, end
    previous = {}
    for frame, (pose, grip) in enumerate(poses):
        scene.frame_set(frame)
        for bone in rig.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.matrix_basis = lower[frame][bone.name] if bone.name in names else pose[bone.name]
        bpy.context.view_layer.update()
        rig.pose.bones['WeaponSocket'].matrix = rig.pose.bones['RightHand'].matrix @ grip
        bpy.context.view_layer.update()
        for bone in rig.pose.bones:
            q = bone.rotation_quaternion.copy()
            if bone.name in previous:
                q.make_compatible(previous[bone.name])
            bone.rotation_quaternion = q
            previous[bone.name] = q.copy()
            for prop in ['location', 'rotation_quaternion', 'scale']:
                bone.keyframe_insert(prop, frame=frame)
    linear(action)
    save_export(rig, name, {'lowerSource': str(LOWER.relative_to(ROOT)), 'upperSource': str(UPPER.relative_to(ROOT)),
        'lowerSourceSHA256': hashlib.sha256(LOWER.read_bytes()).hexdigest(), 'upperSourceSHA256': hashlib.sha256(UPPER.read_bytes()).hexdigest(),
        'upperPhaseOffsetCycles': offset, 'duration': end/fps,
        'method': 'Blender source-action sampling, phase-matched lower-body composition and authored TRS keyframes; source hand-relative sword retained'})


def trim_running_entry():
    bpy.ops.wm.open_mainfile(filepath=str(RUNNING), load_ui=False)
    scene = bpy.context.scene
    rig = bpy.data.objects['Knight_Comparison']
    original = rig.animation_data.action
    original.use_fake_user = True
    fps = scene.render.fps/scene.render.fps_base
    first = round(.3*fps)
    last = scene.frame_end
    retained = []
    for frame in range(first, last+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        retained.append({b.name: b.matrix.copy() for b in rig.pose.bones})
    action = original.copy()
    action.name = 'Mixamo_SlideAttack_v4blender'
    rig.animation_data.action = action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for index in reversed(range(len(curve.keyframe_points))):
                        key = curve.keyframe_points[index]
                        if key.co.x < first-1e-5:
                            curve.keyframe_points.remove(key, fast=True)
                    for key in curve.keyframe_points:
                        key.co.x -= first
                        key.handle_left.x -= first
                        key.handle_right.x -= first
                    curve.update()
    scene.frame_start, scene.frame_end = 0, last-first
    maximum = 0.
    for frame, source_pose in enumerate(retained):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        maximum = max(maximum, max(abs(b.matrix[i][j]-source_pose[b.name][i][j]) for b in rig.pose.bones for i in range(4) for j in range(4)))
    assert maximum < 3e-5, 'Blender curve trim altered retained poses'
    save_export(rig, action.name, {'source': str(RUNNING.relative_to(ROOT)), 'sourceSHA256': hashlib.sha256(RUNNING.read_bytes()).hexdigest(),
        'duration': (last-first)/fps, 'intro': 0., 'outro': .35, 'fps': fps, 'removedStandingJoinSeconds': first/fps,
        'maximumRetainedPoseMatrixError': maximum, 'method': 'Copied source Blender action; removed added idle-prefix keys and shifted retained keyframe/handle times'})


OUT.mkdir(parents=True, exist_ok=True)
compose_run()
trim_running_entry()
print('BLENDER_MOTION_REVISIONS_AUTHORED', flush=True)
