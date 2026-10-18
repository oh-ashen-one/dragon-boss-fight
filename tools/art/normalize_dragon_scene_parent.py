#!/usr/bin/env python3
"""Fold a translated non-joint scene parent into its mesh/root children.

This handles the verified UE Interchange bind/animation disagreement for the
reviewed Veyr dragon: the mesh cancels its Armature translation, while the skin
root animation retains it. It is intentionally narrow and rejects other rigs.
Geometry, weights, inverse binds, rotations and all original files are preserved.
CPU equivalence is not native import or visual acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from inspect_weapon_topology import GLB, EVALUATOR


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(source):
    result = GLB(source.bytes())
    if len(source.json.get('skins', [])) != 1:
        raise ValueError('Exactly one skin required')
    mesh = source.mesh_node()
    joints = set(source.json['skins'][0]['joints'])
    roots = [i for i in joints if source.parents.get(i) not in joints]
    if len(roots) != 1:
        raise ValueError('Exactly one skeleton root required')
    root = roots[0]
    parent = source.parents.get(root)
    if parent is None or source.parents.get(mesh) != parent or parent in source.parents:
        raise ValueError('Mesh and skeleton root must share one scene-root parent')
    if set(source.json['nodes'][parent].get('children', [])) != {mesh, root}:
        raise ValueError('Unrelated scene children would be affected')
    if set(source.json['scenes'][source.json.get('scene', 0)]['nodes']) != {parent}:
        raise ValueError('Unexpected scene roots')
    world = source.world_matrices()
    if not np.allclose(world[parent][:3, :3], np.eye(3), atol=1e-10, rtol=0):
        raise ValueError('Only a translation-only parent can be folded')
    if not np.allclose(world[mesh], np.eye(4), atol=1e-10, rtol=0):
        raise ValueError('Mesh world transform must already be identity')
    if 'matrix' in source.json['nodes'][root] or source.json['nodes'][mesh].get('children'):
        raise ValueError('Root must use TRS and mesh must have no children')
    shift = world[parent][:3, 3]
    if np.linalg.norm(shift) < 1e-10:
        raise ValueError('Parent is already normalized')
    for channel in (c for a in source.json.get('animations', []) for c in a['channels']):
        if channel['target']['node'] in (parent, mesh):
            raise ValueError('Animated parent/mesh cannot be statically folded')
    changed = set()
    for animation in source.json.get('animations', []):
        for channel in animation['channels']:
            if channel['target'] != {'node': root, 'path': 'translation'}:
                continue
            sampler = animation['samplers'][channel['sampler']]
            if sampler.get('interpolation', 'LINEAR') not in ('LINEAR', 'STEP'):
                raise ValueError('Only LINEAR/STEP root translations supported')
            index = sampler['output']
            if index not in changed:
                accessor = result.json['accessors'][index]
                if accessor['componentType'] != 5126 or accessor['type'] != 'VEC3':
                    raise ValueError('Float32 VEC3 root translation required')
                values = result.accessor(index)
                values[:] = values.astype(float) + shift
                for key, op in [('min', np.min), ('max', np.max)]:
                    if key in accessor:
                        accessor[key] = op(values, axis=0).tolist()
                changed.add(index)
    # Refuse shared output data that would mutate a different target or input.
    for animation in source.json.get('animations', []):
        for channel in animation['channels']:
            sampler = animation['samplers'][channel['sampler']]
            if sampler['input'] in changed or (sampler['output'] in changed and
                    channel['target'] != {'node': root, 'path': 'translation'}):
                raise ValueError('Root accessor is shared with unrelated animation data')
    result.json['nodes'][root]['translation'] = (
        np.array(source.json['nodes'][root].get('translation', [0, 0, 0])) + shift).tolist()
    for index in (parent, mesh):
        for key in ('matrix', 'rotation', 'translation', 'scale'):
            result.json['nodes'][index].pop(key, None)
    return result, changed, {'parentNode': parent, 'rootNode': root, 'meshNode': mesh,
                            'foldedParentTranslationGLTF': shift.tolist()}


def validate(source, result, changed, cm_per_unit):
    for field in ('meshes', 'skins', 'materials', 'textures', 'images', 'samplers', 'scenes', 'animations'):
        if source.json.get(field) != result.json.get(field):
            raise ValueError('Unexpected structural change: ' + field)
    for index in range(len(source.json['accessors'])):
        if index not in changed and not np.array_equal(source.accessor(index), result.accessor(index)):
            raise ValueError('Unexpected accessor change: ' + str(index))
    for image in source.json.get('images', []):
        if 'bufferView' in image:
            view = source.json['bufferViews'][image['bufferView']]
            start = view.get('byteOffset', 0); end = start + view['byteLength']
            if source.binary[start:end] != result.binary[start:end]:
                raise ValueError('Embedded texture bytes changed')
    # Validate the actual serialized float32 derivative, not higher precision
    # temporary arrays. Include all authored keys and every adjacent midpoint.
    result = GLB(result.bytes())
    indices = source.json['skins'][0]['joints'] + [source.mesh_node()]
    rows = []
    for animation in [None] + list(range(len(source.json.get('animations', [])))):
        if animation is None:
            times = [0.0]; name = 'ReferencePose'
        else:
            clip = source.json['animations'][animation]
            keys = np.unique(np.concatenate([source.accessor(s['input']).reshape(-1) for s in clip['samplers']])).astype(float)
            times = np.unique(np.r_[keys, (keys[1:] + keys[:-1]) * .5])
            name = clip.get('name', str(animation))
        matrix_error = skin_error = 0.0
        for time in times:
            a = source.world_matrices(animation, float(time))[indices]
            b = result.world_matrices(animation, float(time))[indices]
            matrix_error = max(matrix_error, float(np.max(np.abs(a-b))))
            a = source.skinned_positions(animation, float(time))
            b = result.skinned_positions(animation, float(time))
            if not np.isfinite(b).all():
                raise ValueError('Non-finite skinned derivative: ' + name)
            skin_error = max(skin_error, float(np.linalg.norm(a-b, axis=1).max())*cm_per_unit)
        if matrix_error > 1e-6 or skin_error > .001:
            raise ValueError('World-space equivalence failed: ' + name)
        rows.append({'clip': name, 'samples': len(times), 'maxJointMeshMatrixError': matrix_error,
                     'maxSkinnedVertexWorldErrorCm': skin_error})
    bounds = result.skinned_positions()
    return {'allClipsAndEveryKeyAndMidpointChecked': True, 'checks': rows,
            'sampleCount': sum(row['samples'] for row in rows),
            'maxSkinnedVertexWorldErrorCm': max(row['maxSkinnedVertexWorldErrorCm'] for row in rows),
            'unchangedGeometryWeightsInverseBindsAndOtherAccessors': True,
            'unchangedEmbeddedTextureBytes': True,
            'restMeshBoundsGLTF': [bounds.min(0).tolist(), bounds.max(0).tolist()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--world-cm-per-unit', type=float, required=True)
    args = parser.parse_args()
    if not np.isfinite(args.world_cm_per_unit) or args.world_cm_per_unit <= 0:
        raise ValueError('Positive finite world scale required')
    proof = args.output.with_suffix('.scene-parent-proof.json')
    if args.output.exists() or proof.exists() or args.source.resolve() == args.output.resolve():
        raise ValueError('Use a fresh immutable output path')
    before = digest(args.source)
    source = GLB(args.source)
    result, changed, description = normalize(source)
    evidence = validate(source, result, changed, args.world_cm_per_unit)
    if digest(args.source) != before:
        raise ValueError('Source changed during normalization')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(result.bytes())
    receipt = {'status': 'CPU_EQUIVALENT_NATIVE_IMPORT_PENDING', 'source': str(args.source.resolve()),
               'sourceSHA256': before, 'output': str(args.output.resolve()), 'outputSHA256': digest(args.output),
               'helperSHA256': digest(__file__), 'worldCmPerUnit': args.world_cm_per_unit,
               'rootTranslationAccessorsChanged': len(changed), 'nativeAcceptance': False,
               **description, **evidence}
    with proof.open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    print(json.dumps({'output': str(args.output), 'proof': str(proof), 'sha256': receipt['outputSHA256'],
                      'samples': evidence['sampleCount'], 'maxVertexErrorCm': evidence['maxSkinnedVertexWorldErrorCm']}))


if __name__ == '__main__':
    main()
