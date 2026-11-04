#!/usr/bin/env python3
"""CPU-only contact refinement of an already licensed/retargeted run.

Preserve geometry, skin, materials, source timing, swing and upper-body local
motion. A brief measured plant gets one stable boot transform; the two-bone
solve retains limb lengths and the original knee plane. This writes a private
candidate, never an import or a quality acceptance. No renderer is started.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/unreal'))
from normalize_customuse_glb import GLB, slerp


def rigid_blend(a, b, weight):
    out = a.copy()
    sa = np.linalg.norm(a[:3, :3], axis=0)
    sb = np.linalg.norm(b[:3, :3], axis=0)
    assert np.allclose(sa, sb, atol=1e-5), 'Changing boot scale is unsupported'
    qa = Rotation.from_matrix(a[:3, :3] / sa).as_quat()
    qb = Rotation.from_matrix(b[:3, :3] / sb).as_quat()
    out[:3, :3] = Rotation.from_quat(slerp(qa, qb, weight)).as_matrix() @ np.diag(sa)
    out[:3, 3] = a[:3, 3] * (1-weight) + b[:3, 3] * weight
    return out


def direction_rotation(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    q = np.r_[np.cross(a, b), 1 + a @ b]
    assert np.linalg.norm(q) > 1e-6, 'Ambiguous 180-degree segment correction'
    return Rotation.from_quat(q / np.linalg.norm(q)).as_matrix()


def solve(chain, target):
    a, b, c = [m[:3, 3].copy() for m in chain]
    upper, lower = np.linalg.norm(b-a), np.linalg.norm(c-b)
    delta = target-a
    distance = np.linalg.norm(delta)
    assert abs(upper-lower)+1e-6 < distance < upper+lower-1e-6, 'Unreachable leg target'
    direction = delta/distance
    pole = b-a-direction*np.dot(b-a, direction)
    assert np.linalg.norm(pole) > 1e-6, 'Ambiguous knee plane'
    along = (upper*upper-lower*lower+distance*distance)/(2*distance)
    knee = a+direction*along+pole/np.linalg.norm(pole)*np.sqrt(max(0., upper*upper-along*along))
    result = [m.copy() for m in chain]
    result[0][:3, :3] = direction_rotation(b-a, knee-a) @ chain[0][:3, :3]
    result[1][:3, :3] = direction_rotation(c-b, target-knee) @ chain[1][:3, :3]
    result[1][:3, 3] = knee
    result[2][:3, 3] = target
    return result


def cyclic_groups(mask):
    assert any(mask) and not all(mask), 'Need a distinct planted and swing phase'
    start = next(i for i, v in enumerate(mask) if not v)
    groups, group = [], []
    for k in range(start+1, start+len(mask)+1):
        if mask[k % len(mask)]:
            group.append(k)
        elif group:
            if len(group) >= 2:
                groups.append(group)
            group = []
    if len(group) >= 2:
        groups.append(group)
    assert groups, 'No measurable contact phase'
    return groups


def add_accessor(g, values, kind):
    values = np.asarray(values, dtype='<f4')
    g.binary.extend(b'\0' * (-len(g.binary) % 4))
    offset = len(g.binary)
    g.binary.extend(values.tobytes())
    view = len(g.json['bufferViews'])
    g.json['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': values.nbytes})
    index = len(g.json['accessors'])
    g.json['accessors'].append({'bufferView': view, 'componentType': 5126,
                              'count': len(values), 'type': kind,
                              'min': values.min(axis=0).tolist(), 'max': values.max(axis=0).tolist()})
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'Local/AttackSources20261103/LocomotionContacts/Mixamo_ForwardRun_v2contacts.glb')
    parser.add_argument('--output', type=Path, default=ROOT/'Local/AttackSources20261104/CPUBootPlants/Mixamo_ForwardRun_v4cpu.glb')
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve existing candidates'
    source_bytes = args.source.read_bytes()
    g = GLB(source_bytes)
    assert len(g.json['animations']) == 1
    ids = {n.get('name'): i for i, n in enumerate(g.json['nodes'])}
    clip = g.json['animations'][0]
    duration = max(float(g.accessor(s['input'])[-1, 0]) for s in clip['samplers'])
    count = round(duration*60)
    times = np.linspace(0, duration, count+1)
    worlds = np.array([g.world_matrices(0, t) for t in times])
    scale_cm = 244 / np.ptp(g.skinned_positions()[:, 1])
    net = worlds[-1, ids['Hips'], :3, 3]-worlds[0, ids['Hips'], :3, 3]
    net[1] = 0
    assert np.linalg.norm(net) > .2
    mesh = g.json['nodes'][g.mesh_node()]
    skin = g.json['skins'][mesh['skin']]
    primitives = g.json['meshes'][mesh['mesh']]['primitives']
    sides = ['Left', 'Right']
    foot_vertices = {}
    for side in sides:
        joint_ids = [i for i, n in enumerate(skin['joints']) if n in (ids[side+'Foot'], ids[side+'ToeBase'])]
        mask = []
        for primitive in primitives:
            joints = g.accessor(primitive['attributes']['JOINTS_0']).copy()
            weights = g.accessor(primitive['attributes']['WEIGHTS_0']).copy()
            mask.extend(((np.isin(joints, joint_ids)*weights).sum(axis=1) > .75).tolist())
        foot_vertices[side] = np.flatnonzero(mask)
        assert len(foot_vertices[side]) > 20
    soles = {side: [] for side in sides}
    for t in times:
        positions = g.skinned_positions(0, t)
        for side in sides:
            soles[side].append(float(positions[foot_vertices[side], 1].min()))
    floor = min(min(v) for v in soles.values())
    targets, groups_report = {}, {}
    for side in sides:
        foot, toe = ids[side+'Foot'], ids[side+'ToeBase']
        assert g.parents[toe] == foot
        foot_y, toe_y = worlds[:-1, foot, 1, 3], worlds[:-1, toe, 1, 3]
        mask = (foot_y <= np.percentile(foot_y, 10)+2.5/scale_cm) & (toe_y <= np.percentile(toe_y, 10)+2.5/scale_cm)
        groups = cyclic_groups(mask)
        groups_report[side] = [[i % count for i in group] for group in groups]
        targets[side] = {}
        for group in groups:
            ref = min(group, key=lambda k: worlds[k % count, foot, 1, 3])
            planted = worlds[ref % count, foot].copy()
            planted[:3, 3] += net*(ref // count)
            planted[1, 3] += floor-soles[side][ref % count]
            toe_local = np.linalg.inv(worlds[ref % count, foot]) @ worlds[ref % count, toe]
            for k in range(group[0]-3, group[-1]+4):
                distance = max(group[0]-k, k-group[-1], 0)
                x = distance/4
                weight = 1-x*x*(3-2*x)
                i = k % count
                if weight > targets[side].get(i, (None, None, -1))[2]:
                    target = planted.copy()
                    target[:3, 3] -= net*(k // count)
                    targets[side][i] = (target, toe_local, weight)
    modified = {ids['Hips'], ids['WeaponSocket']}
    modified.update(ids[side+n] for side in sides for n in ['UpLeg', 'Leg', 'Foot', 'ToeBase'])
    sampled = {i: [] for i in modified}
    max_shift, max_error, max_length_error = 0., 0., 0.
    children = {i: node.get('children', []) for i, node in enumerate(g.json['nodes'])}
    for frame, original in enumerate(worlds):
        w = original.copy()
        def set_world(i, matrix):
            delta = matrix @ np.linalg.inv(w[i])
            def update(j):
                w[j] = delta @ w[j]
                for child in children[j]:
                    update(child)
            update(i)
        desired, desired_toes = {}, {}
        for side in sides:
            foot, toe = ids[side+'Foot'], ids[side+'ToeBase']
            original_toe = np.linalg.inv(original[foot]) @ original[toe]
            target, local_toe, weight = targets[side].get(frame % count, (original[foot], original_toe, 0.))
            target = target.copy()
            if frame == count:
                target[:3, 3] += net
            desired[side] = rigid_blend(original[foot], target, weight)
            desired_toes[side] = rigid_blend(original_toe, local_toe, weight)
        shift = np.zeros(3)
        for _ in range(80):
            for side in sides:
                chain = [original[ids[side+n]] for n in ['UpLeg', 'Leg', 'Foot']]
                limit = sum(np.linalg.norm(chain[i+1][:3, 3]-chain[i][:3, 3]) for i in range(2))-.0001
                delta = desired[side][:3, 3]-chain[0][:3, 3]-shift
                distance = np.linalg.norm(delta)
                if distance > limit:
                    shift += delta/distance*(distance-limit)
        assert np.linalg.norm(shift)*scale_cm < 20, 'Excessive pelvis adjustment'
        max_shift = max(max_shift, np.linalg.norm(shift))
        hip = w[ids['Hips']].copy()
        hip[:3, 3] += shift
        set_world(ids['Hips'], hip)
        for side in sides:
            indices = [ids[side+n] for n in ['UpLeg', 'Leg', 'Foot']]
            chain = [w[i].copy() for i in indices]
            lengths = [np.linalg.norm(chain[i+1][:3, 3]-chain[i][:3, 3]) for i in range(2)]
            result = solve(chain, desired[side][:3, 3])
            result[2] = desired[side]
            for i, matrix in zip(indices, result):
                set_world(i, matrix)
            set_world(ids[side+'ToeBase'], w[ids[side+'Foot']] @ desired_toes[side])
            max_error = max(max_error, np.linalg.norm(w[indices[-1]][:3, 3]-desired[side][:3, 3]))
            max_length_error = max(max_length_error, *[abs(np.linalg.norm(w[indices[i+1]][:3, 3]-w[indices[i]][:3, 3])-lengths[i]) for i in range(2)])
        grip = np.linalg.inv(original[ids['RightHand']]) @ original[ids['WeaponSocket']]
        set_world(ids['WeaponSocket'], w[ids['RightHand']] @ grip)
        for i in modified:
            sampled[i].append(np.linalg.inv(w[g.parents[i]]) @ w[i] if i in g.parents else w[i])
    assert max_length_error < 1e-6 and max_error < 1e-6
    clip['channels'] = [c for c in clip['channels'] if c['target']['node'] not in modified]
    timeline = add_accessor(g, times[:, None], 'SCALAR')
    for i in sorted(modified):
        matrices = np.asarray(sampled[i])
        scales = np.linalg.norm(matrices[:, :3, :3], axis=1)
        rotations = Rotation.from_matrix(matrices[:, :3, :3] / scales[:, None, :]).as_quat()
        for k in range(1, len(rotations)):
            if np.dot(rotations[k-1], rotations[k]) < 0:
                rotations[k] *= -1
        for path, values, kind in [('translation', matrices[:, :3, 3], 'VEC3'), ('rotation', rotations, 'VEC4'), ('scale', scales, 'VEC3')]:
            output = add_accessor(g, values, kind)
            sampler = len(clip['samplers'])
            clip['samplers'].append({'input': timeline, 'output': output, 'interpolation': 'LINEAR'})
            clip['channels'].append({'sampler': sampler, 'target': {'node': i, 'path': path}})
    g.json['buffers'][0]['byteLength'] = len(g.binary)
    clip['name'] = args.output.stem
    result = g.bytes()
    # Original binary data is unchanged: geometry, weights, textures, and all
    # unaffected animation channels remain the licensed source's exact bytes.
    original = GLB(source_bytes)
    assert g.binary[:len(original.binary)] == original.binary
    for field in ['nodes', 'skins', 'meshes', 'materials', 'images', 'textures']:
        assert g.json.get(field) == original.json.get(field)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    report = {'source': str(args.source.relative_to(ROOT)), 'sourceSHA256': hashlib.sha256(source_bytes).hexdigest(),
              'output': str(args.output.relative_to(ROOT)), 'sha256': hashlib.sha256(result).hexdigest(),
              'durationSeconds': duration, 'stanceFrames': groups_report, 'maxPelvisAdjustmentCm': max_shift*scale_cm,
              'maxIKErrorCm': max_error*scale_cm, 'maxLimbLengthChangeCm': max_length_error*scale_cm,
              'originalPayloadPreserved': True, 'sourceUpperLocalMotionPreserved': True,
              'nativeImported': False, 'visuallyReviewed': False, 'accepted': False}
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
