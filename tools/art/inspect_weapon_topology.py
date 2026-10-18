#!/usr/bin/env python3
"""Inspect whole welded surfaces; never reweight, reshape or edit a source GLB.

A candidate is selected explicitly by its minimum original triangle index, not
by a spatial bounding box. Outputs are confined to ignored Local/CustomuseAssets.
The colored derivative changes primitive partition/material only. Root must
visually review the candidate before any later rigid-weight operation.
Requires numpy and the sibling CPU glTF evaluator; matplotlib is optional.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'Local/CustomuseAssets'
SPEC = importlib.util.spec_from_file_location('veyr_glb_evaluator', ROOT / 'tools/unreal/normalize_customuse_glb.py')
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)
GLB = EVALUATOR.GLB


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def topology(positions, triangles, relative_tolerance):
    height = float(np.ptp(positions[:, 1]))
    if height <= 0:
        raise ValueError('Invalid vertical extent')
    step = height * relative_tolerance
    # Quantization only identifies coincident surface vertices for analysis.
    # The original vertex arrays are never welded or rewritten.
    keys = positions if step == 0 else np.rint(positions / step).astype(np.int64)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    parents = np.arange(int(inverse.max()) + 1)

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for a, b, c in inverse[triangles]:
        a, b, c = find(int(a)), find(int(b)), find(int(c))
        parents[b] = a
        parents[c] = a
    vertex_roots = np.array([find(int(i)) for i in inverse])
    groups = defaultdict(list)
    for index, tri in enumerate(triangles):
        groups[int(vertex_roots[tri[0]])].append(index)
    # Minimum original triangle is stable and source-addressable.
    return {min(v): np.asarray(v, dtype=np.int64) for v in groups.values()}, inverse, step


def primitive(g):
    node = g.json['nodes'][g.mesh_node()]
    parts = g.json['meshes'][node['mesh']]['primitives']
    if len(parts) != 1 or parts[0].get('mode', 4) != 4 or 'indices' not in parts[0]:
        raise ValueError('Exactly one indexed triangle primitive is required')
    if parts[0].get('targets') or parts[0].get('extensions'):
        raise ValueError('Morph/compressed primitives are unsupported')
    p = parts[0]
    return node, p, g.accessor(p['attributes']['POSITION']).astype(float), g.accessor(p['indices']).reshape(-1, 3)


def influence_stats(g, p, vertices):
    skin = g.json['skins'][g.json['nodes'][g.mesh_node()]['skin']]
    joints = g.accessor(p['attributes']['JOINTS_0'])[vertices]
    weights = g.accessor(p['attributes']['WEIGHTS_0'])[vertices].astype(float)
    totals = np.bincount(joints.reshape(-1), weights=weights.reshape(-1), minlength=len(skin['joints']))
    return [{'jointIndex': int(i), 'name': g.json['nodes'][skin['joints'][i]].get('name', str(i)),
             'meanWeight': float(totals[i] / len(vertices))}
            for i in np.argsort(-totals) if totals[i] > 1.e-8]


def component_stats(g, p, positions, triangles, groups, inverse, hand):
    output = []
    for cid, faces in groups.items():
        vertices = np.unique(triangles[faces])
        xyz = positions[vertices]
        center = xyz.mean(0)
        _, _, axes = np.linalg.svd(xyz - center, full_matrices=False)
        extents = np.ptp((xyz - center) @ axes.T, axis=0)
        edges = Counter()
        for tri in inverse[triangles[faces]]:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edges[tuple(sorted((int(a), int(b))))] += 1
        output.append({'componentId': int(cid), 'triangleCount': len(faces), 'vertexCount': len(vertices),
                       'centroidMeshSpace': center.tolist(), 'boundsMeshSpace': [xyz.min(0).tolist(), xyz.max(0).tolist()],
                       'pcaExtents': extents.tolist(), 'pcaLongAxis': axes[0].tolist(),
                       'minimumDistanceToHandBind': float(np.linalg.norm(xyz - hand, axis=1).min()),
                       'boundaryEdgesAfterAnalysisWeld': sum(n == 1 for n in edges.values()),
                       'nonmanifoldEdgesAfterAnalysisWeld': sum(n > 2 for n in edges.values()),
                       'meanVertexSkinInfluences': influence_stats(g, p, vertices)[:8]})
    return sorted(output, key=lambda x: max(x['pcaExtents']), reverse=True)


def highlight(g, p, triangle_mask, output):
    derived = GLB(g.bytes())
    node, _, _, triangles = primitive(derived)
    triangles = triangles.copy()  # Never retain a bytearray-backed view across buffer growth.
    attrs = copy.deepcopy(p['attributes'])
    original_binary = bytes(g.binary)
    material_index = len(derived.json.get('materials', []))
    derived.json.setdefault('materials', []).append({
        'name': 'INSPECTION_ONLY_candidate_surface_not_reweighted',
        'pbrMetallicRoughness': {'baseColorFactor': [1, .08, .015, 1], 'metallicFactor': 0, 'roughnessFactor': 1},
        'extensions': {'KHR_materials_unlit': {}}, 'doubleSided': True})
    derived.json.setdefault('extensionsUsed', [])
    if 'KHR_materials_unlit' not in derived.json['extensionsUsed']:
        derived.json['extensionsUsed'].append('KHR_materials_unlit')
    parts = []
    for selected, mat in ((~triangle_mask, p.get('material', 0)), (triangle_mask, material_index)):
        idx = triangles[selected].astype('<u4').reshape(-1)
        derived.binary.extend(b'\0' * (-len(derived.binary) % 4))
        offset = len(derived.binary)
        derived.binary.extend(idx.tobytes())
        view = len(derived.json['bufferViews'])
        derived.json['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': idx.nbytes, 'target': 34963})
        accessor = len(derived.json['accessors'])
        derived.json['accessors'].append({'bufferView': view, 'componentType': 5125, 'count': len(idx), 'type': 'SCALAR',
                                          'min': [int(idx.min())], 'max': [int(idx.max())]})
        parts.append({'attributes': copy.deepcopy(attrs), 'indices': accessor, 'mode': 4, 'material': mat})
    derived.json['meshes'][node['mesh']]['primitives'] = parts
    derived.json['buffers'][0]['byteLength'] = len(derived.binary)
    # Preserve every original byte, attribute, texture, weight, transform and clip.
    assert bytes(derived.binary[:len(original_binary)]) == original_binary
    assert derived.json['nodes'] == g.json['nodes'] and derived.json['skins'] == g.json['skins']
    assert derived.json.get('animations') == g.json.get('animations')
    assert sum(derived.accessor(x['indices']).size for x in parts) == triangles.size
    assert np.array_equal(derived.accessor(parts[0]['indices']).reshape(-1, 3), triangles[~triangle_mask])
    assert np.array_equal(derived.accessor(parts[1]['indices']).reshape(-1, 3), triangles[triangle_mask])
    output.write_bytes(derived.bytes())
    return {'file': output.name, 'sha256': sha(output), 'originalBinaryPrefixUnchanged': True,
            'allOriginalVertexAttributesUnchanged': True, 'skinAndAnimationsUnchanged': True,
            'allTrianglesPreservedOnce': True, 'changes': 'Two index subsets and one unlit inspection material only'}


def deformation(g, vertices, triangles, times):
    rest = g.skinned_positions()
    reference = rest[vertices]
    height = float(np.ptp(rest[:, 1]))
    edges = np.unique(np.sort(np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]])), axis=1), axis=0)
    lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    keep = lengths > height * 1.e-8
    edges, lengths = edges[keep], lengths[keep]
    centered = reference - reference.mean(0)
    rows = []
    for time in times:
        posed_all = g.skinned_positions(animation=0, time=time)
        posed = posed_all[vertices]
        centered_posed = posed - posed.mean(0)
        u, _, vt = np.linalg.svd(centered.T @ centered_posed)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u[:, -1] *= -1
            rotation = u @ vt
        residual = np.linalg.norm(centered @ rotation - centered_posed, axis=1)
        ratio = np.linalg.norm(posed_all[edges[:, 0]] - posed_all[edges[:, 1]], axis=1) / lengths
        rows.append({'timeSeconds': time, 'bestRigidFitRms': float(np.sqrt(np.mean(residual**2))),
                     'bestRigidFitMax': float(residual.max()), 'rmsCentimetersAt244cmCharacterHeight': float(np.sqrt(np.mean(residual**2)) / height * 244),
                     'maxCentimetersAt244cmCharacterHeight': float(residual.max() / height * 244),
                     'edgeLengthRatioMin': float(ratio.min()), 'edgeLengthRatioMax': float(ratio.max()),
                     'p95AbsoluteEdgeLengthChangeFraction': float(np.percentile(np.abs(ratio-1), 95))})
    return {'method': 'Existing CPU glTF jointWorld * inverseBind * position evaluation; best-fit rigid Kabsch residual, no reweighting',
            'worldRestHeight': height, 'rows': rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--compare', type=Path, nargs='*', default=[])
    ap.add_argument('--candidate-component', type=int, required=True, help='Minimum original triangle index of an explicitly reviewed component candidate')
    ap.add_argument('--relative-weld', type=float, default=1.e-6)
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to(ASSETS.resolve()) or out == ASSETS.resolve():
        raise ValueError('Use a NEW subdirectory under ignored Local/CustomuseAssets')
    out.mkdir(parents=True, exist_ok=False)
    source_hash = sha(args.source)
    g = GLB(args.source)
    node, p, positions, triangles = primitive(g)
    skin = g.json['skins'][node['skin']]
    names = [g.json['nodes'][n].get('name', '') for n in skin['joints']]
    hand_index = next(i for i, name in enumerate(names) if name in ('RightHand', 'right_wrist'))
    ibm = g.accessor(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    hand = np.linalg.inv(ibm[hand_index])[:3, 3]
    groups, inverse, step = topology(positions, triangles, args.relative_weld)
    if args.candidate_component not in groups:
        raise ValueError('Candidate component not present at selected tolerance')
    faces = groups[args.candidate_component]
    vertices = np.unique(triangles[faces])
    tri_mask = np.zeros(len(triangles), dtype=bool)
    tri_mask[faces] = True
    stats = component_stats(g, p, positions, triangles, groups, inverse, hand)
    candidate = next(x for x in stats if x['componentId'] == args.candidate_component)
    stability = []
    for tolerance in (0., 1.e-8, 1.e-7, 1.e-6, 1.e-5, 1.e-4):
        alt, _, _ = topology(positions, triangles, tolerance)
        containing = next(v for v in alt.values() if args.candidate_component in v)
        stability.append({'relativeTolerance': tolerance, 'componentCount': len(alt), 'candidateTriangles': len(containing),
                          'sameExactTriangleSet': bool(np.array_equal(np.sort(containing), np.sort(faces)))})
    comparisons = []
    for path in args.compare:
        other = GLB(path)
        _, otherp, otherpos, othertri = primitive(other)
        scale = float(np.sum(positions * otherpos) / np.sum(positions * positions))
        comparisons.append({'file': path.name, 'sha256': sha(path), 'identicalTriangleIndices': bool(np.array_equal(triangles, othertri)),
                            'positionScaleRelativeToSource': scale, 'maxPositionResidualAfterScale': float(np.abs(otherpos - positions*scale).max()),
                            'identicalJoints': bool(np.array_equal(g.accessor(p['attributes']['JOINTS_0']), other.accessor(otherp['attributes']['JOINTS_0']))),
                            'identicalWeights': bool(np.array_equal(g.accessor(p['attributes']['WEIGHTS_0']), other.accessor(otherp['attributes']['WEIGHTS_0'])))})
    mask = {'status': 'CANDIDATE_REQUIRES_ROOT_VISUAL_REVIEW_NO_REWEIGHT_AUTHORIZED', 'sourceFile': args.source.name,
            'sourceSHA256': source_hash, 'meshIndex': node['mesh'], 'primitiveIndex': 0,
            'componentId': args.candidate_component, 'vertexIndices': vertices.tolist(), 'triangleIndices': faces.tolist(),
            'selectionMethod': 'Entire quantized-position-welded connected component, explicitly selected by source triangle seed; no bounding-box cut',
            'relativeWeldCellSize': args.relative_weld, 'absoluteWeldCellSize': step,
            'handJointIndex': hand_index, 'handJointName': names[hand_index], 'handBindMeshSpace': hand.tolist(),
            'weightsModified': False, 'geometryModified': False}
    (out/'candidate-mask.json').write_text(json.dumps(mask, indent=2))
    (out/'components.json').write_text(json.dumps(stats, indent=2))
    report = {'sourceFile': args.source.name, 'sourceSHA256': source_hash, 'candidate': candidate, 'weldStability': stability,
              'comparisons': comparisons, 'componentCount': len(groups), 'weldMethodCaveat': 'Quantized cell equality, not a distance-radius weld. Used only for analysis, never rewriting vertices.',
              'candidateIsFullWeapon': 'UNCONFIRMED until root checks the highlighted blade, guard, grip and pommel against non-highlighted fingers/armor',
              'boundaryToExcludedTrianglesThroughWeldedVertices': 0,
              'highlight': highlight(g, p, tri_mask, out/'candidate-highlight.glb')}
    report['deformation'] = deformation(g, vertices, triangles[faces], [0., 1/30, .5, 1., 1.5, 2., 2.5, 3.5, 4.5, 5.])
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        rest = g.skinned_positions()
        fig, axs = plt.subplots(1, 3, figsize=(15, 7))
        labels = [('X','Y'), ('Z','Y'), ('X','Z')]
        for ax, (a,b), names2 in zip(axs, ((0,1),(2,1),(0,2)), labels):
            ax.scatter(rest[::3,a], rest[::3,b], s=.6, c='#78909c', alpha=.22, linewidths=0)
            ax.scatter(rest[vertices,a], rest[vertices,b], s=1.5, c='#ff3b16', alpha=.8, linewidths=0)
            ax.set(xlabel=names2[0], ylabel=names2[1], aspect='equal')
            ax.grid(alpha=.2)
        fig.suptitle(f'Candidate connected surface {args.candidate_component} (red) — unchanged geometry, no weight repair\nOrthographic CPU bind-pose projections; full GLB visual review still required')
        fig.tight_layout()
        fig.savefig(out/'candidate-projections.png', dpi=160)
        plt.close(fig)
    except ImportError:
        report['projectionPlot'] = 'matplotlib unavailable; no installation attempted'
    assert sha(args.source) == source_hash
    report['sourceFileUnchanged'] = True
    (out/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'candidateComponent': args.candidate_component, 'triangles': len(faces), 'vertices': len(vertices),
                      'components': len(groups), 'sourceUnchanged': True, 'outputDirectory': str(out),
                      'maxRigidFitDeviationCmAt244cm': max(x['maxCentimetersAt244cmCharacterHeight'] for x in report['deformation']['rows'])}, indent=2))


if __name__ == '__main__':
    main()
