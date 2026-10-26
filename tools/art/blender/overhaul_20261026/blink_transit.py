"""Blender root-trajectory adaptation of fitted sourced blink strafes.

Only VeyrRoot translation is authored. Source joint channels, geometry, skin,
materials, morphs and sample times are copied unchanged into the deliverable.
"""
import copy
import hashlib
import json
import struct
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'Local/Overhaul20261026/blink-v2'
OWNER = 'codex-veyr-flight-join-r2'
HIDDEN_SOURCE = (.207, .391)
PLAY_RATE = 1.15


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_glb(path):
    raw = Path(path).read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20+size]), bytearray(raw[28+size:])


def channel(gltf, name, path):
    return next(c for c in gltf['animations'][0]['channels']
                if gltf['nodes'][c['target']['node']]['name'] == name
                and c['target']['path'] == path)


def scalar_accessor(gltf, binary, index):
    acc = gltf['accessors'][index]
    assert acc['componentType'] == 5126 and acc['type'] == 'SCALAR'
    view = gltf['bufferViews'][acc['bufferView']]
    offset = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    return struct.unpack_from('<'+'f'*acc['count'], binary, offset)


def package_root_translation(source, baked, destination):
    """Copy the Blender-authored root channel only; do not re-export the mesh."""
    gltf, binary = read_glb(source)
    other, other_binary = read_glb(baked)
    src_channel = channel(gltf, 'VeyrRoot', 'translation')
    baked_channel = channel(other, 'VeyrRoot', 'translation')
    src_sampler = gltf['animations'][0]['samplers'][src_channel['sampler']]
    baked_sampler = other['animations'][0]['samplers'][baked_channel['sampler']]
    assert gltf['accessors'][src_sampler['output']]['count'] == other['accessors'][baked_sampler['output']]['count']
    accessor = copy.deepcopy(other['accessors'][baked_sampler['output']])
    assert 'sparse' not in accessor
    view = copy.deepcopy(other['bufferViews'][accessor['bufferView']])
    offset = view.get('byteOffset', 0)
    payload = other_binary[offset:offset+view['byteLength']]
    binary.extend(b'\0'*(-len(binary)%4))
    view['byteOffset'], view['buffer'] = len(binary), 0
    binary.extend(payload)
    accessor['bufferView'] = len(gltf['bufferViews'])
    gltf['bufferViews'].append(view)
    src_sampler['output'] = len(gltf['accessors'])
    gltf['accessors'].append(accessor)
    src_sampler['interpolation'] = 'LINEAR'
    gltf['animations'][0]['name'] = destination.stem
    binary.extend(b'\0'*(-len(binary)%4))
    gltf['buffers'] = [{'byteLength': len(binary)}]
    data = json.dumps(gltf, separators=(',', ':')).encode()
    data += b' '*(-len(data)%4)
    destination.write_bytes(struct.pack('<III', 0x46546c67, 2, 28+len(data)+len(binary)) +
                           struct.pack('<II', len(data), 0x4e4f534a) + data +
                           struct.pack('<II', len(binary), 0x004e4942) + binary)


def smootherstep(x):
    x = max(0., min(1., x))
    return x*x*x*(x*(x*6-15)+10)


def progress(t, duration):
    start, end = HIDDEN_SOURCE
    if t <= start:
        return .03*smootherstep(t/start)
    if t <= end:
        return .03+.94*smootherstep((t-start)/(end-start))
    return .97+.03*smootherstep((t-end)/(duration-end))


def run(side):
    scene = bpy.context.scene
    assert scene.get('session_owner') == OWNER, 'Foreign Blender'
    source = ROOT / 'Local/Overhaul20261026/blink/Exports' / ('Sourced_Blink'+side+'_v1.glb')
    provenance = json.loads(source.with_suffix('.json').read_text())
    data, binary = read_glb(source)
    root_channel = channel(data, 'VeyrRoot', 'translation')
    sampler = data['animations'][0]['samplers'][root_channel['sampler']]
    times = scalar_accessor(data, binary, sampler['input'])
    fps = int(round((len(times)-1)/times[-1]))
    assert fps == provenance['fps'] == 120
    assert max(abs(t-i/fps) for i,t in enumerate(times)) < 1e-6
    end = len(times)-1
    duration = end/fps
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.render.fps, scene.render.fps_base = fps, 1
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene['session_owner'], scene['mcp_port'] = OWNER, 9892
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    root = rig.pose.bones['VeyrRoot']
    assert root.parent is None
    scene.frame_start, scene.frame_end = 0, end
    original = {}
    for frame in range(end+1):
        scene.frame_set(frame)
        original[frame] = {'hip': (rig.matrix_world @ rig.pose.bones['Hips'].matrix).translation.copy(),
                           'root': root.matrix.copy(), 'location': root.location.copy()}
    travel = original[end]['hip']-original[0]['hip']
    # Blender is Z-up. Preserve the vertical hop exactly; adapt the planar
    # principal lateral direction, including its tiny authored forward component.
    travel.z = 0
    distance = travel.length
    assert distance > .5
    direction = travel.normalized()
    original_action = rig.animation_data.action
    rig.animation_data.action = original_action.copy()
    name = 'Sourced_Blink'+side+'_Transit_v2'
    rig.animation_data.action.name = name
    for frame in range(end+1):
        scene.frame_set(frame)
        old = original[frame]
        current = (old['hip']-original[0]['hip']).dot(direction)
        correction = direction*(progress(frame/fps, duration)*distance-current)
        posed = old['root'].copy()
        posed.translation += rig.matrix_world.inverted().to_3x3() @ correction
        basis = root.bone.convert_local_to_pose(posed, root.bone.matrix_local, invert=True)
        root.location = basis.translation if frame not in (0,end) else old['location']
        root.keyframe_insert('location', frame=frame)
    for obj in scene.objects:
        obj.select_set(obj == rig or (obj.type == 'MESH' and any(m.type == 'ARMATURE' for m in obj.modifiers)))
    bpy.context.view_layer.objects.active = rig
    baked = OUT/(name+'_BlenderExport.glb')
    final = OUT/(name+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(baked), export_format='GLB', use_selection=True,
        export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_frame_range=True,
        export_force_sampling=True, export_optimize_animation_size=False,
        export_cameras=False, export_lights=False)
    package_root_translation(source, baked, final)
    script = bpy.data.texts.get('blink_transit.py') or bpy.data.texts.new('blink_transit.py')
    script.clear()
    script.write(Path(__file__).read_text())
    scene.frame_set(0)
    blend = OUT/(name+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    report = {'name':name, 'source':str(source.relative_to(ROOT)), 'sourceSHA256':sha(source),
              'provenance':provenance, 'fps':fps, 'sampleCount':len(times), 'duration':duration,
              'sourceHiddenInterval':list(HIDDEN_SOURCE), 'nativeHiddenInterval':[.18,.34],
              'nativePlayRate':PLAY_RATE, 'targetHiddenTravelFraction':.94,
              'sourceTotalPlanarDisplacementBlenderXYZ':list(travel),
              'modifiedChannel':'VeyrRoot.translation only',
              'geometryAndOtherChannels':'Preserved source payload and sample times exactly',
              'sha256':sha(final), 'blendSHA256':sha(blend), 'blenderExportSHA256':sha(baked),
              'runtimeAcceptance':'Pending parent native integration and gameplay evaluation'}
    (OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


OUT.mkdir(parents=True,exist_ok=True)
for side in ('Left','Right'):
    run(side)
