#!/usr/bin/env python3
"""Apply an explicitly reviewed whole-surface mask to one rigid hand influence.

Only creates new derivatives under Local/CustomuseAssets. Requires a root visual
review reference and source-hash-addressed mask; never guesses a weapon region.
Uses normalized inputs, preserves every other accessor/texture/node/animation,
and checks all-pair shape distances plus non-weapon CPU skin invariance.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'Local/CustomuseAssets'
SPEC = importlib.util.spec_from_file_location('veyr_glb_evaluator', ROOT / 'tools/unreal/normalize_customuse_glb.py')
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)
GLB = EVALUATOR.GLB


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data(g):
    node = g.json['nodes'][g.mesh_node()]
    parts = g.json['meshes'][node['mesh']]['primitives']
    if len(parts) != 1 or parts[0].get('mode', 4) != 4:
        raise ValueError('Exactly one triangle primitive is required')
    p = parts[0]
    return node, p, g.accessor(p['indices']).reshape(-1, 3)


def chain_is_rigid(g, node_index):
    """Unit-scale TRS chains and quaternion interpolation preserve all distances."""
    chain = {node_index}
    while node_index in g.parents:
        node_index = g.parents[node_index]
        chain.add(node_index)
    for index in chain:
        n = g.json['nodes'][index]
        m = EVALUATOR.trs(n)
        if not np.allclose(m[:3, :3].T @ m[:3, :3], np.eye(3), atol=1e-6):
            return False
        if not np.isclose(np.linalg.det(m[:3, :3]), 1, atol=1e-6):
            return False
    for clip in g.json.get('animations', []):
        for channel in clip['channels']:
            if channel['target']['node'] not in chain:
                continue
            sampler = clip['samplers'][channel['sampler']]
            if sampler.get('interpolation', 'LINEAR') not in ('LINEAR', 'STEP'):
                return False
            if channel['target']['path'] == 'scale' and not np.allclose(g.accessor(sampler['output']), 1, atol=1e-7):
                return False
    return True


def process(source, out, mask, reference, approval):
    if not out.resolve().is_relative_to(ASSETS.resolve()) or out.exists():
        raise ValueError('Output must be a NEW file inside Local/CustomuseAssets')
    source_sha = sha(source)
    original = GLB(source)
    derived = GLB(original.bytes())
    node, p, triangles = data(original)
    _, reference_p, reference_triangles = data(reference)
    if not np.array_equal(triangles, reference_triangles):
        raise ValueError('Topology differs from the approved source mask')
    if not np.allclose(original.world_matrices()[original.mesh_node()], np.eye(4), atol=1e-6):
        raise ValueError('Normalize mesh bind space before applying rigid weights')
    vertices = np.asarray(mask['vertexIndices'], dtype=np.int64)
    faces = np.asarray(mask['triangleIndices'], dtype=np.int64)
    if not np.array_equal(vertices, np.unique(triangles[faces])):
        raise ValueError('Mask vertex/triangle sets disagree')
    excluded_faces = np.ones(len(triangles), dtype=bool)
    excluded_faces[faces] = False
    if np.intersect1d(vertices, np.unique(triangles[excluded_faces])).size:
        raise ValueError('Candidate shares indexed vertices with excluded body geometry')
    attrs = p['attributes']
    if not np.array_equal(original.accessor(attrs['_FBXVERTEXID']), reference.accessor(reference_p['attributes']['_FBXVERTEXID'])):
        raise ValueError('Original vertex identity mapping differs')
    joints = derived.accessor(attrs['JOINTS_0'])
    weights = derived.accessor(attrs['WEIGHTS_0'])
    if joints.shape != weights.shape or joints.shape[1] != 4:
        raise ValueError('Expected four skin influences')
    skin = original.json['skins'][node['skin']]
    names = [original.json['nodes'][n].get('name') for n in skin['joints']]
    hand = names.index('RightHand')
    nonweapon = np.ones(len(weights), dtype=bool)
    nonweapon[vertices] = False
    joints[vertices] = [hand, 0, 0, 0]
    weights[vertices] = [1, 0, 0, 0]
    assert original.json == derived.json
    changed_accessors = {attrs['JOINTS_0'], attrs['WEIGHTS_0']}
    for i in range(len(original.json['accessors'])):
        if i not in changed_accessors:
            assert np.array_equal(original.accessor(i), derived.accessor(i)), i
        else:
            assert np.array_equal(original.accessor(i)[nonweapon], derived.accessor(i)[nonweapon]), i
    for image in original.json.get('images', []):
        view = original.json['bufferViews'][image['bufferView']]
        begin = view.get('byteOffset', 0); end = begin + view['byteLength']
        assert original.binary[begin:end] == derived.binary[begin:end]
    rest_before, rest_after = original.skinned_positions(), derived.skinned_positions()
    rest_delta = float(np.linalg.norm(rest_before-rest_after, axis=1).max())
    if rest_delta > 1e-5:
        raise ValueError(f'Rest shape unexpectedly moved: {rest_delta}')
    pair_i, pair_j = np.triu_indices(len(vertices), 1)
    rest_sword = rest_after[vertices]
    pair_distances = np.linalg.norm(rest_sword[pair_i]-rest_sword[pair_j], axis=1)
    world_height = float(np.ptp(rest_after[:, 1]))
    rigid_chain = chain_is_rigid(derived, skin['joints'][hand])
    if not rigid_chain:
        raise ValueError('RightHand ancestor chain has scale/shear or unsupported animation')
    rows = []
    for clip_index, clip in enumerate(original.json.get('animations', [])):
        duration = max(float(original.accessor(s['input']).max()) for s in clip['samplers'])
        times = sorted(set([0., 1/30, .5, 1., 1.5, 2., 2.5, 3.5, 4.5, duration]))
        for time in times:
            if time > duration: continue
            before = original.skinned_positions(clip_index, time)
            after = derived.skinned_positions(clip_index, time)
            nonweapon_delta = float(np.linalg.norm(before[nonweapon]-after[nonweapon], axis=1).max())
            assert nonweapon_delta == 0., nonweapon_delta
            sword = after[vertices]
            lengths = np.linalg.norm(sword[pair_i]-sword[pair_j], axis=1)
            shape_error = float(np.abs(lengths-pair_distances).max())
            if shape_error > 1e-6:
                raise ValueError(f'Weapon is not rigid at {time}: {shape_error}')
            old_sword = before[vertices]
            old_lengths = np.linalg.norm(old_sword[pair_i]-old_sword[pair_j], axis=1)
            rows.append({'clipIndex': clip_index, 'timeSeconds': time,
                         'nonweaponWorldSkinMaxDelta': nonweapon_delta,
                         'allPairwiseDistancesMaxErrorAfter': shape_error,
                         'allPairwiseDistancesMaxErrorBefore': float(np.abs(old_lengths-pair_distances).max())})
    out.write_bytes(derived.bytes())
    assert sha(source) == source_sha
    receipt = {'status': 'RIGID_WEIGHT_DERIVATIVE_VERIFIED_CPU_NATIVE_QA_PENDING', 'approvalReference': approval,
               'sourceFile': source.name, 'sourceSHA256': source_sha, 'outputFile': out.name, 'outputSHA256': sha(out),
               'maskSourceSHA256': mask['sourceSHA256'], 'componentId': mask['componentId'],
               'selectedVertices': len(vertices), 'selectedTriangles': len(faces), 'handJointIndex': hand,
               'handJointName': 'RightHand', 'newInfluences': [[hand, 1.0]],
               'nonweaponJointAndWeightBytesUnchanged': True, 'nonSkinAccessorsAndTextureBytesUnchanged': True,
               'nodeSkeletonAndAnimationDeclarationsUnchanged': True, 'restShapeMaxDelta': rest_delta,
               'analyticRigidChainCheck': rigid_chain,
               'pairwiseDistancesCheckedPerPose': len(pair_i), 'samples': rows,
               'worldRestHeight': world_height,
               'maxPairwiseErrorCentimetersAt244cmHeight': max(r['allPairwiseDistancesMaxErrorAfter'] for r in rows)/world_height*244,
               'sourceUnchanged': True, 'limitation': 'Preserves the approved full sword as one rigid surface; does not fix hand grip pose, body motion, native importer or dragon rig.'}
    out.with_suffix('.rigid-sword.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: receipt[k] for k in ('outputFile', 'selectedVertices', 'restShapeMaxDelta', 'maxPairwiseErrorCentimetersAt244cmHeight', 'analyticRigidChainCheck')}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mask', type=Path, required=True)
    ap.add_argument('--mask-source', type=Path, required=True)
    ap.add_argument('--approval-ref', required=True)
    ap.add_argument('--source', type=Path, nargs='+', required=True)
    ap.add_argument('--version', default='v1')
    args = ap.parse_args()
    if not args.version.isalnum(): raise ValueError('Use an alphanumeric version')
    mask = json.loads(args.mask.read_text())
    if sha(args.mask_source) != mask['sourceSHA256']:
        raise ValueError('Approved mask source hash mismatch')
    reference = GLB(args.mask_source)
    for source in args.source:
        output = ASSETS / (source.stem + '-rigid-sword-' + args.version + '.glb')
        process(source, output, mask, reference, args.approval_ref)


if __name__ == '__main__': main()
