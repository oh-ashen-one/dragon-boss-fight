"""Correct boot penetration with a shared vertical body offset inside Blender.

Keep every relative joint pose, limb length, foot XY path and weapon grip.
Unlike independent leg IK this cannot crumple a knee. Only lift when actual
skinned boot geometry penetrates floor0; source airborne motion stays airborne.
This is a new ACCAD retarget study, not a revision of the stopped Mixamo turn.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
source, dest = a.source.resolve(strict=True), a.output.resolve()
assert source.is_relative_to(ROOT/'Local') and dest.is_relative_to(ROOT/'Local')
assert source.suffix == '.blend' and not dest.with_suffix('.blend').exists()
metadata = json.loads(source.with_suffix('.json').read_text())
assert metadata['provider'] == 'accad' and not metadata.get('candidateStopped')
assert not (source.parent/'DO_NOT_IMPORT.md').exists()
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
assert source_hash == metadata['editableSceneSHA256']
native_scale = json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
scene = bpy.context.scene
rig = bpy.data.objects['Knight_Comparison']
original = rig.animation_data.action
original.use_fake_user = True
source_fps = scene.render.fps/scene.render.fps_base
duration = scene.frame_end/source_fps
count = round(duration*120)
body = []
for obj in scene.objects:
    if obj.type != 'MESH' or not any(m.type == 'ARMATURE' and m.object == rig for m in obj.modifiers):
        continue
    groups = {g.index for g in obj.vertex_groups if g.name in ['LeftFoot', 'LeftToeBase', 'RightFoot', 'RightToeBase']}
    indices = [v.index for v in obj.data.vertices if sum(w.weight for w in v.groups if w.group in groups) > .75]
    assert len(indices) > 40
    body.append((obj, indices))
assert body


def sole():
    floor = float('inf')
    deps = bpy.context.evaluated_depsgraph_get()
    for obj, indices in body:
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        floor = min(floor, min((evaluated.matrix_world @ mesh.vertices[i].co).z for i in indices))
        evaluated.to_mesh_clear()
    return floor


samples = []
for i in range(count+1):
    f = (i/count)*duration*source_fps
    scene.frame_set(int(f), subframe=f-int(f))
    bpy.context.view_layer.update()
    samples.append({'bases': {b.name: b.matrix_basis.copy() for b in rig.pose.bones},
        'worlds': {b.name: (rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones},
        'sole': sole()})
scene.render.fps, scene.render.fps_base = 120, 1
scene.frame_start, scene.frame_end = 0, count
action = bpy.data.actions.new(dest.stem)
rig.animation_data.action = action
previous, corrections = {}, []
max_relative_error = 0.
for i, row in enumerate(samples):
    scene.frame_set(i)
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        bone.matrix_basis = row['bases'][bone.name]
    bpy.context.view_layer.update()
    lift = max(0., .05/native_scale-row['sole'])
    assert lift < .08, 'Excessive body lift; reject rather than conceal source defects'
    root = rig.pose.bones['VeyrRoot']
    matrix = root.matrix.copy()
    matrix.translation += rig.matrix_world.inverted().to_3x3() @ Vector((0, 0, lift))
    root.matrix = matrix
    bpy.context.view_layer.update()
    for bone in rig.pose.bones:
        actual = rig.matrix_world @ bone.matrix
        expected = row['worlds'][bone.name].copy()
        expected.translation.z += lift
        max_relative_error = max(max_relative_error, max(abs(actual[r][c]-expected[r][c]) for r in range(4) for c in range(4)))
        q = bone.rotation_quaternion.copy()
        if bone.name in previous:
            q.make_compatible(previous[bone.name])
        bone.rotation_quaternion = q
        previous[bone.name] = q.copy()
        for prop in ['location', 'rotation_quaternion', 'scale']:
            bone.keyframe_insert(prop, frame=i)
    assert sole() >= -.0001, 'Skinned boot remains below native floor'
    corrections.append(lift*native_scale)
assert max_relative_error < 3e-5, 'Shared lift altered a relative pose'
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = 'LINEAR'
scene.frame_set(0)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
for obj, _ in body:
    obj.select_set(True)
bpy.context.view_layer.objects.active = rig
dest.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(dest.with_suffix('.glb')), export_format='GLB', use_selection=True,
    export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_frame_range=True,
    export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(dest.with_suffix('.blend')), compress=True)
assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
report = {'provider': 'accad', 'source': str(source.relative_to(ROOT)), 'sourceSHA256': source_hash,
    'sha256': hashlib.sha256(dest.with_suffix('.glb').read_bytes()).hexdigest(),
    'authoringApplication': 'Blender', 'editableScene': str(dest.with_suffix('.blend').relative_to(ROOT)),
    'editableSceneSHA256': hashlib.sha256(dest.with_suffix('.blend').read_bytes()).hexdigest(),
    'fps': 120, 'duration': count/120, 'maximumBodyLiftCm': max(corrections),
    'maximumRelativePoseMatrixError': max_relative_error,
    'method': 'Shared upward body offset only where skinned boot support penetrates floor0; no independent limb reshaping or planar locking',
    'relativePosesAndPlanarPathsPreserved': True, 'nativeImported': False, 'accepted': False,
    'license': metadata.get('license'), 'sourceURL': metadata.get('sourceURL'), 'attribution': metadata.get('attribution')}
dest.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
print('ACCAD_SUPPORT_CORRECTION_AUTHORED_NOT_ACCEPTED', flush=True)
