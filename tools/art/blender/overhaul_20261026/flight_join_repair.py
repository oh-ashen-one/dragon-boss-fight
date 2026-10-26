"""Correct existing flight joins in owned Blender; no whole-motion synthesis.

Run through veyr_rpc.py on the dedicated flight-r2 session. Rest-aware conversion
uses the common original GLB rest pose and includes every bone, including helpers.
Only the 0.4-second airborne join is changed. Geometry and morph actions are kept.
"""
import hashlib
import json
import copy
import struct
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'Local/Overhaul20261026/flight-r2'
OWNER = 'codex-veyr-flight-join-r2'
HOVER = ROOT / 'Local/Blender/dangle-20261025/Dragon_FlyHover_Blender_dangle_v2.glb'
SOURCES = [
    ('Dragon_Takeoff_Blender_polish_v3', 'Dragon_Takeoff_DangleJoin_v2', True),
    ('Dragon_Land_Blender_polish_v4', 'Dragon_Land_DangleJoin_v2', False),
]


def load(path):
    assert bpy.context.scene.get('session_owner') == OWNER, 'Foreign Blender'
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.scene.render.fps = 30
    bpy.context.scene.render.fps_base = 1
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.scene['session_owner'] = OWNER
    return next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preserve_source_payload(source, authored, destination):
    """Structural packaging only: copy Blender-authored bone channels unchanged.

    Blender may split mesh vertices at seams on export. Retain the entire original
    source payload and source morph animation, changing only named bone TRS.
    """
    def read(path):
        data = Path(path).read_bytes()
        size = struct.unpack_from('<I', data, 12)[0]
        return json.loads(data[20:20+size]), bytearray(data[28+size:])
    original, binary = read(source)
    exported, exported_binary = read(authored)
    names = {n['name']: i for i, n in enumerate(original['nodes'])}
    joint_names = {original['nodes'][i]['name'] for i in original['skins'][0]['joints']}
    authored_animation = exported['animations'][0]
    animation = {'name': destination.stem, 'channels': [], 'samplers': []}
    accessors = {}
    views = {}
    def copy_accessor(index):
        if index in accessors:
            return accessors[index]
        acc = copy.deepcopy(exported['accessors'][index])
        assert 'sparse' not in acc, 'Unexpected sparse animation accessor'
        view_index = acc['bufferView']
        if view_index not in views:
            view = copy.deepcopy(exported['bufferViews'][view_index])
            offset = view.get('byteOffset', 0)
            payload = exported_binary[offset:offset+view['byteLength']]
            binary.extend(b'\0' * (-len(binary) % 4))
            view['byteOffset'] = len(binary)
            view['buffer'] = 0
            binary.extend(payload)
            views[view_index] = len(original['bufferViews'])
            original['bufferViews'].append(view)
        acc['bufferView'] = views[view_index]
        result = len(original['accessors'])
        original['accessors'].append(acc)
        accessors[index] = result
        return result
    for channel in authored_animation['channels']:
        target = channel['target']
        name = exported['nodes'][target['node']]['name']
        if name not in joint_names or target['path'] == 'weights':
            continue
        sampler = copy.deepcopy(authored_animation['samplers'][channel['sampler']])
        sampler['input'] = copy_accessor(sampler['input'])
        sampler['output'] = copy_accessor(sampler['output'])
        animation['channels'].append({'sampler': len(animation['samplers']),
                                      'target': {'node': names[name], 'path': target['path']}})
        animation['samplers'].append(sampler)
    assert len(animation['channels']) == 3 * len(joint_names)
    source_animation = original['animations'][0]
    for channel in source_animation['channels']:
        if original['nodes'][channel['target']['node']]['name'] in joint_names:
            continue
        copied = copy.deepcopy(channel)
        copied['sampler'] = len(animation['samplers'])
        animation['channels'].append(copied)
        animation['samplers'].append(copy.deepcopy(source_animation['samplers'][channel['sampler']]))
    original['animations'] = [animation]
    binary.extend(b'\0' * (-len(binary) % 4))
    original['buffers'] = [{'byteLength': len(binary)}]
    payload = json.dumps(original, separators=(',', ':')).encode()
    payload += b' ' * (-len(payload) % 4)
    raw = (struct.pack('<III', 0x46546c67, 2, 28+len(payload)+len(binary)) +
           struct.pack('<II', len(payload), 0x4e4f534a) + payload +
           struct.pack('<II', len(binary), 0x004e4942) + binary)
    destination.write_bytes(raw)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = load(HOVER)
    scene = bpy.context.scene
    scene.frame_set(0)
    # Deformation from the target rest pose to the target airborne pose.
    # This removes each import's rest-bone orientation before applying the
    # deformation to the destination rest bone. matrix_basis is not portable.
    target_deformation = {
        p.name: (target.matrix_world @ p.matrix) @
                (target.matrix_world @ p.bone.matrix_local).inverted()
        for p in target.pose.bones
    }
    for source_name, name, takeoff in SOURCES:
        source = ROOT / 'Local/Blender/polish-20261025' / (source_name + '.glb')
        rig = load(source)
        scene = bpy.context.scene
        old_action = rig.animation_data.action
        end = round(old_action.frame_range[1])
        assert end == 45, (name, old_action.frame_range[:])
        scene.frame_start, scene.frame_end = 0, end
        assert set(target_deformation) == set(rig.pose.bones.keys())
        # Desired pose matrices in the destination armature's space.
        goal_pose = {
            p.name: rig.matrix_world.inverted() @ target_deformation[p.name] @
                    rig.matrix_world @ p.bone.matrix_local
            for p in rig.pose.bones
        }
        goal_basis = {}
        for p in rig.pose.bones:
            args = {}
            if p.parent:
                args = dict(parent_matrix=goal_pose[p.parent.name],
                            parent_matrix_local=p.parent.bone.matrix_local)
            goal_basis[p.name] = p.bone.convert_local_to_pose(
                goal_pose[p.name], p.bone.matrix_local, invert=True, **args)
        original = {}
        for frame in range(end + 1):
            scene.frame_set(frame)
            original[frame] = {p.name: p.matrix_basis.copy() for p in rig.pose.bones}
        endpoint_frame = end if takeoff else 0
        changed = {
            name for name, matrix in original[endpoint_frame].items()
            if max(abs(matrix[i][j] - goal_basis[name][i][j])
                   for i in range(4) for j in range(4)) > 1e-5
        }
        rig.animation_data.action = old_action.copy()
        rig.animation_data.action.name = name
        # Original source is sampled at 30Hz. Keep its timing and keyframes.
        for frame in range(end + 1):
            x = (frame - 33) / 12 if takeoff else 1 - frame / 12
            if x < 0:
                continue
            x = min(1, x)
            weight = x*x*(3-2*x)
            scene.frame_set(frame)
            for p in rig.pose.bones:
                if p.name not in changed:
                    continue
                a, q, scale = original[frame][p.name].decompose()
                b, r, other_scale = goal_basis[p.name].decompose()
                p.rotation_mode = 'QUATERNION'
                p.matrix_basis = Matrix.LocRotScale(
                    a.lerp(b, weight), q.slerp(r, weight), scale.lerp(other_scale, weight))
                for prop in ('location', 'rotation_quaternion', 'scale'):
                    p.keyframe_insert(prop, frame=frame)
        scene.frame_set(end if takeoff else 0)
        bpy.context.view_layer.update()
        error = max(abs(p.matrix[i][j] - goal_pose[p.name][i][j])
                    for p in rig.pose.bones for i in range(4) for j in range(4))
        assert error < 1e-5, ('Blender endpoint pose mismatch', error)
        for obj in scene.objects:
            obj.select_set(obj == rig or obj.type == 'MESH')
        bpy.context.view_layer.objects.active = rig
        path = OUT / (name + '.glb')
        authored_path = OUT / (name + '_BlenderExport.glb')
        bpy.ops.export_scene.gltf(
            filepath=str(authored_path), export_format='GLB', use_selection=True,
            export_animations=True, export_animation_mode='ACTIVE_ACTIONS',
            export_frame_range=True, export_force_sampling=True,
            export_optimize_animation_size=False, export_morph=True,
            export_morph_animation=True, export_cameras=False, export_lights=False)
        preserve_source_payload(source, authored_path, path)
        text = bpy.data.texts.get('flight_join_repair.py') or bpy.data.texts.new('flight_join_repair.py')
        text.clear()
        text.write(Path(__file__).read_text())
        blend = OUT / (name + '.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
        report = {
            'source': str(source.relative_to(ROOT)), 'sourceSHA256': sha(source),
            'hoverTarget': str(HOVER.relative_to(ROOT)), 'hoverSHA256': sha(HOVER),
            'name': name, 'fps': 30, 'duration': 1.5, 'sampleCount': 46,
            'joinSeconds': 0.4, 'allBoneCount': len(goal_basis),
            'changedJoinBasisBones': sorted(changed), 'blenderEndpointError': error,
            'correction': 'Existing source flight; all named bones converted through rest-aware pose space; only airborne 0.4-second join adapted in Blender',
            'sha256': sha(path), 'blendSHA256': sha(blend),
            'blenderExportSHA256': sha(authored_path),
            'packaging': 'Original source mesh/materials/skin/morph animation retained; bone TRS channels copied unchanged from Blender export',
            'runtimeAcceptance': 'Not evaluated by this Blender correction task',
        }
        (OUT / (name + '.json')).write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


main()
