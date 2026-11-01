"""Bind an existing Blender action to a compatible canonical rig, without saving sources.

No motion authoring: refuse any rest/pose mismatch, preserve the canonical mesh,
and export its copy with the source's action at the original frame rate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--canonical', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
if args.output.exists() or args.output.with_suffix('.json').exists():
    raise RuntimeError('Refusing overwrite')
bpy.ops.wm.open_mainfile(filepath=str(args.source), load_ui=False)
source = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
action = source.animation_data.action
start, end = (int(round(x)) for x in action.frame_range)
fps, fps_base = bpy.context.scene.render.fps, bpy.context.scene.render.fps_base
source_slot = source.animation_data.action_slot
old_objects = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(args.canonical))
imported = set(bpy.data.objects) - old_objects
target = next(o for o in imported if o.type == 'ARMATURE')
meshes = [o for o in imported if o.type == 'MESH' and
          any(m.type == 'ARMATURE' and m.object == target for m in o.modifiers)]
if len(meshes) != 1:
    raise RuntimeError('Expected one canonical skin')
for mesh in meshes:
    if mesh.data.shape_keys:
        # The canonical file carries old flight morph animation. The sourced
        # death has none: do not accidentally export a second flight action.
        mesh.data.shape_keys.animation_data_clear()
        for key in mesh.data.shape_keys.key_blocks:key.value = 0.0
names = set(source.data.bones.keys())
if names - set(target.data.bones.keys()):
    raise RuntimeError('Canonical rig lacks source bones')
rest_error = max(abs(a - b) for name in names
                 for ra, rb in zip(source.data.bones[name].matrix_local, target.data.bones[name].matrix_local)
                 for a, b in zip(ra, rb))
if rest_error > 1e-5:
    raise RuntimeError('Source rest rig differs from canonical')
target.animation_data_clear()
for bone in target.pose.bones:
    bone.rotation_mode = 'QUATERNION'
    bone.matrix_basis.identity()
target.animation_data_create()
target.animation_data.action = action.copy()
target.animation_data.action_slot = target.animation_data.action.slots[0]
scene = bpy.context.scene
scene.render.fps, scene.render.fps_base = fps, fps_base
scene.frame_start, scene.frame_end = start, end
pose_error = 0.0
for frame in range(start, end + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    for name in names:
        a = source.matrix_world @ source.pose.bones[name].matrix
        b = target.matrix_world @ target.pose.bones[name].matrix
        pose_error = max(pose_error, max(abs(x-y) for ra, rb in zip(a, b) for x,y in zip(ra,rb)))
if pose_error > 1e-4:
    raise RuntimeError(f'Action transfer changed evaluated pose: {pose_error}')
bpy.ops.object.select_all(action='DESELECT')
for obj in [target, *meshes]: obj.select_set(True)
bpy.context.view_layer.objects.active = target
args.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(args.output), export_format='GLB', use_selection=True,
    export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_frame_range=True,
    export_force_sampling=True, export_optimize_animation_size=False,
    export_morph_animation=False, export_cameras=False, export_lights=False)
receipt = {'source': str(args.source), 'sourceSHA256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
           'canonical': str(args.canonical), 'canonicalSHA256': hashlib.sha256(args.canonical.read_bytes()).hexdigest(),
           'outputSHA256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
           'frameRange': [start,end], 'fps': fps/fps_base, 'sourceAction': action.name,
           'restMaxError': rest_error, 'evaluatedPoseMaxError': pose_error,
           'scope': 'Representation equivalence only; native import and rendered quality not established'}
args.output.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('ACTION_TRANSFER_POSE_EQUIVALENT', pose_error)
