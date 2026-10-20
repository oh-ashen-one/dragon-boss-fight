#!/usr/bin/env python3
"""Author a planted, full-body two-hand breathing review from the intact rig.

The previous two-hand clip supplies only the arm pose. The straight reference
rig supplies the body, pelvis, legs, feet, mesh, skin and bind matrices. Both
inputs and the approved one-hand review remain untouched. A separate sword
review copy narrows the wooden handle under each palm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from author_knight_actions import build, sample
from author_knight_hold import unit
from author_knight_stances import Rig
from inspect_weapon_topology import GLB


DURATION = 4.0
SAMPLES = 97
SOCKET_ROTATION = Rotation.from_quat([0.78155554, 0.0047625, 0.01463231, -0.62364586]).as_matrix()
SOCKET_SCALE = 0.4096359622825952
UPPER_GRIP_Y = -0.075  # Raw wooden-sword meters, down from its thick shaft.
LOWER_GRIP_Y = -0.255


def setup_rig(g: GLB, source: GLB) -> Rig:
    """Initialize the reusable kinematic solver without old v012 topology IDs."""
    r = Rig.__new__(Rig)
    r.g = g
    r.names = {node.get('name'): i for i, node in enumerate(g.json['nodes'])}
    r.rest = g.world_matrices()
    r.factor = 244 / np.ptp(g.skinned_positions()[:, 1])
    r.scale = np.array([node.get('scale', [1, 1, 1]) for node in g.json['nodes']])
    r.order = []
    def visit(i):
        if i in r.order:
            return
        if i in g.parents:
            visit(g.parents[i])
        r.order.append(i)
    for i in range(len(g.json['nodes'])):
        visit(i)
    r.hips = r.names['Hips']
    r.chains = {side: [r.names[side + name] for name in ('Arm', 'ForeArm', 'Hand')] for side in ('Right', 'Left')}
    r.legs = {side: [r.names[side + name] for name in ('UpLeg', 'Leg', 'Foot')] for side in ('Right', 'Left')}
    r.grip = {}
    r.frames = {}
    r.palm_axes = {}
    for side in ('Right', 'Left'):
        hand = r.chains[side][2]
        inv = np.linalg.inv(r.rest[hand])
        fingers = {part: (inv @ np.r_[r.rest[r.names[side + 'Hand' + part], :3, 3], 1])[:3]
                   for part in ('Index', 'Pinky', 'Middle')}
        length = unit(fingers['Middle'])
        width = unit(fingers['Index'] - fingers['Pinky'])
        across = unit(length - width * np.dot(length, width))
        r.grip[side] = (fingers['Index'] + fingers['Pinky']) * 0.5 - across * .010
        # The older stance helper's middle axis is reflected. A reflected
        # target cannot be represented by a bone quaternion, which was why
        # the palms missed the shaft even when the hand bones reached it.
        r.frames[side] = np.column_stack([across, np.cross(width, across), width])
        if side == 'Left':
            r.frames[side] = r.frames[side] @ np.diag([-1., -1., 1.])
        r.palm_axes[hand] = length
    r.soft = True
    r.previous_elbows = {}
    r.previous_upper_rotations = {}
    r.elbow_delta_degrees = 15.
    pose = sample(source, 0.)
    # Keep only the original two-hand arm geometry and glove closure.
    arm_nodes = set()
    for side in ('Right', 'Left'):
        arm_nodes.update(r.chains[side])
        pending = list(g.json['nodes'][r.chains[side][2]].get('children', []))
        while pending:
            node = pending.pop()
            arm_nodes.add(node)
            pending.extend(g.json['nodes'][node].get('children', []))
    r.base = {(node, path): value.copy() for (node, path), value in pose.items() if node in arm_nodes and path == 'rotation'}
    for name in ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head', 'RightShoulder', 'LeftShoulder'):
        node = r.names[name]
        r.base[(node, 'rotation')] = np.asarray(g.json['nodes'][node].get('rotation', [0., 0., 0., 1.]), dtype=float)
    r.baseW = r.world(r.base)
    return r


def turn(r: Rig, pose: dict, name: str, degrees: tuple[float, float, float]) -> None:
    if np.linalg.norm(degrees) < 1e-12:
        return
    node = r.names[name]
    world = r.world(pose)
    rotation = Rotation.from_rotvec(np.deg2rad(degrees)).as_matrix() @ world[node, :3, :3]
    r.set_world_rotation(pose, node, rotation, world)


def animate_frame(r: Rig, time: float) -> tuple[dict, dict]:
    pose = {key: value.copy() for key, value in r.base.items()}
    phase = 2 * math.pi * time / DURATION
    inhale = .5 - .5 * math.cos(phase)
    drift = math.sin(phase)
    # Pelvis absorbs the breath and weight shift. The leg IK below keeps both
    # soles in world space while knees and ankles respond to it.
    hips = r.hips
    ref = np.asarray(r.g.json['nodes'][hips].get('translation', [0., 0., 0.]), dtype=float)
    pose[(hips, 'translation')] = ref + np.array([.005 * drift, -.012 * inhale, .003 * drift])
    turn(r, pose, 'Hips', (.5 * inhale, .45 * drift, -.8 * drift))
    turn(r, pose, 'Spine', (-1.4 * inhale, .2 * drift, .6 * drift))
    turn(r, pose, 'Spine1', (-1.8 * inhale, -.15 * drift, -.4 * drift))
    turn(r, pose, 'Spine2', (1.3 * inhale, .1 * drift, .2 * drift))
    chest = r.names['Spine2']
    chest_ref = np.asarray(r.g.json['nodes'][chest]['translation'], dtype=float)
    pose[(chest, 'translation')] = chest_ref + r.world(pose)[r.g.parents[chest], :3, :3].T @ np.array([0., .035 * inhale, 0.])
    turn(r, pose, 'Neck', (.35 * inhale, 0, -.15 * drift))
    turn(r, pose, 'Head', (-.45 * inhale, 0, -.2 * drift))
    turn(r, pose, 'RightShoulder', (0., -.5 * inhale, -2.5 * inhale))
    turn(r, pose, 'LeftShoulder', (0., .5 * inhale, 2.5 * inhale))

    foot_residuals = {}
    for side in ('Right', 'Left'):
        upper, knee, foot = r.legs[side]
        target = r.rest[foot, :3, 3].copy()
        world = r.world(pose)
        line = unit(target - world[upper, :3, 3])
        pole = world[knee, :3, 3] - world[upper, :3, 3]
        pole -= line * np.dot(line, pole)
        if np.linalg.norm(pole) < 1e-5:
            pole = np.array([0., 0., 1.])
        # Small ankle pressure rolls with the body, while the foot pivot stays
        # fixed. The toe and heel remain visually planted.
        foot_rot = Rotation.from_rotvec(np.deg2rad([.4 * inhale, 0., .35 * drift])).as_matrix() @ r.rest[foot, :3, :3]
        r.limb(pose, [upper, knee, foot], target, foot_rot, pole)
        after = r.world(pose)
        foot_residuals[side] = float(np.linalg.norm(after[foot, :3, 3] - target))

    # Build both arms around one continuous sword axis. The previous clip's two
    # palm centers are ~83 cm apart, so carrying over either arm would preserve
    # a broken grip. The guard sits in front of the chest, ready to strike.
    axis = unit(np.array([-.15047918 + .012 * drift, .92768552, .34169517 + .007 * inhale]))
    across_hint = np.array([.98412306, .10765986, .14110688])
    across = unit(across_hint - axis * np.dot(axis, across_hint))
    blade_side = unit(np.cross(axis, across))
    weapon_frame = np.column_stack([across, blade_side, axis])
    right_center = np.array([-.03958 + .006 * drift, .745 + .026 * inhale, .120 + .012 * inhale])
    left_center = right_center + axis * (LOWER_GRIP_Y - UPPER_GRIP_Y) * SOCKET_SCALE
    arm_info = {}
    for side, center, pole in [('Right', right_center, np.array([-.85, -.30, -.4])),
                               ('Left', left_center, np.array([.85, -.30, -.4]))]:
        hand = r.chains[side][2]
        desired = weapon_frame @ r.frames[side].T
        hand_target = center - desired @ r.grip[side]
        arm_info[side] = r.limb(pose, r.chains[side], hand_target, desired, pole, 35.)
    final = r.world(pose)
    actual_grips = {side: final[r.chains[side][2], :3, 3] + final[r.chains[side][2], :3, :3] @ r.grip[side]
                    for side in ('Right', 'Left')}
    right_error = float(np.linalg.norm(actual_grips['Right'] - right_center))
    left_error = float(np.linalg.norm(actual_grips['Left'] - left_center))
    return pose, {'feetWorldResidual': foot_residuals, 'leftPalmGripResidual': left_error,
                  'rightPalmGripResidual': right_error,
                  'chestWorldY': float(final[chest, 1, 3]), 'hipWorldY': float(final[hips, 1, 3]),
                  'leftWristBendDegrees': arm_info['Left']['wristBendDegrees'],
                  'rightWristBendDegrees': arm_info['Right']['wristBendDegrees']}


def make_sword(source: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    glb = GLB(source)
    mesh = glb.json['meshes'][0]['primitives'][0]
    pos = glb.accessor(mesh['attributes']['POSITION'])
    original = pos.copy()
    y = pos[:, 1].astype(float)
    # Taper only the handle, with full-width transitions hidden beneath the
    # guard and pommel. The separate bow/blade geometry is untouched.
    fade_bottom = np.clip((y + .43) / .12, 0, 1)
    fade_top = np.clip((.33 - y) / .12, 0, 1)
    influence = np.minimum(fade_bottom, fade_top)
    factor = 1. - .38 * influence
    pos[:, 0] *= factor
    pos[:, 2] *= factor
    accessor = glb.json['accessors'][mesh['attributes']['POSITION']]
    accessor['min'] = pos.min(0).tolist()
    accessor['max'] = pos.max(0).tolist()
    if np.any(pos[y > .43] != original[y > .43]):
        raise ValueError('Sword blade changed')
    # The actual glove surfaces project to [-.154,.022] and [-.346,-.159]
    # along the raw handle at time zero. The portion buried in those two palms
    # must not render through their knuckles. Leave the shaft visible above
    # the upper fist and the pommel visible below the lower fist.
    faces = glb.accessor(mesh['indices']).reshape(-1, 3)
    center_y = original[faces, 1].mean(axis=1)
    hidden = (center_y >= -.35) & (center_y <= .04)
    kept = np.asarray(faces[~hidden].ravel(), dtype='<u4')
    glb.binary.extend(b'\0' * (-len(glb.binary) % 4))
    offset = len(glb.binary)
    glb.binary.extend(kept.tobytes())
    view = len(glb.json['bufferViews'])
    glb.json['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': kept.nbytes, 'target': 34963})
    index = len(glb.json['accessors'])
    glb.json['accessors'].append({'bufferView': view, 'componentType': 5125, 'count': len(kept), 'type': 'SCALAR'})
    mesh['indices'] = index
    glb.json['buffers'][0]['byteLength'] = len(glb.binary)
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(glb.bytes())
    return {'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'handleTaper': .62, 'hiddenGripRawY': [-.35, .04],
            'removedHiddenHandleTriangles': int(hidden.sum())}


def write_candidate(body: Path, previous: Path, sword: Path, output: Path, sword_output: Path) -> dict:
    if output.exists() or sword_output.exists():
        raise FileExistsError('Review output already exists; choose a new candidate name')
    g = GLB(body)
    old = GLB(previous)
    r = setup_rig(g, old)
    times = np.linspace(0., DURATION, SAMPLES)
    results = [animate_frame(r, float(t)) for t in times]
    poses = [pose for pose, _ in results]
    metrics = [item for _, item in results]
    keys = set(poses[0])
    if any(set(pose) != keys for pose in poses):
        raise ValueError('An animated bone is missing from the first keyframe')
    for key in poses[0]:
        if not np.allclose(poses[0][key], poses[-1][key], atol=1e-7):
            raise ValueError(f'Loop closure failed for {key}')
    worst_foot = max(max(m['feetWorldResidual'].values()) for m in metrics)
    worst_grip = max(max(m['leftPalmGripResidual'], m['rightPalmGripResidual']) for m in metrics)
    worst_wrist = max(max(m['leftWristBendDegrees'], m['rightWristBendDegrees']) for m in metrics)
    if worst_foot > 1e-4 or worst_grip > .006 or worst_wrist > 30:
        raise ValueError(f'Contact failed: feet {worst_foot} grip {worst_grip}')
    result = build(g, poses, times, output.stem)
    if result.binary[:len(g.binary)] != g.binary or any(result.json.get(k) != g.json.get(k) for k in ('nodes', 'skins', 'meshes', 'materials', 'textures', 'images')):
        raise ValueError('Source body geometry or bind data changed')
    baked_error = 0.
    baked_foot_error = 0.
    for t, pose in zip(times, poses):
        baked = result.world_matrices(0, float(t))
        authored = r.world(pose)
        baked_error = max(baked_error, float(np.abs(baked - authored).max()))
        for side in ('Right', 'Left'):
            foot = r.legs[side][2]
            baked_foot_error = max(baked_foot_error, float(np.linalg.norm(baked[foot, :3, 3] - r.rest[foot, :3, 3])))
    if baked_error > 1e-5 or baked_foot_error > 1e-5:
        raise ValueError(f'Exported tracks differ from authored poses: {baked_error}, {baked_foot_error}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(result.bytes())
    sword_info = make_sword(sword, sword_output)
    return {'bodySourceSha256': hashlib.sha256(body.read_bytes()).hexdigest(),
            'previousTwoHandSha256': hashlib.sha256(previous.read_bytes()).hexdigest(),
            'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'sword': sword_info, 'durationSeconds': DURATION, 'sampleCount': SAMPLES,
            'maximumFootPivotDriftRigUnits': worst_foot,
            'maximumBakedFootPivotDriftRigUnits': baked_foot_error,
            'maximumBakedPoseErrorRigUnits': baked_error,
            'maximumLeftPalmGripErrorRigUnits': worst_grip,
            'maximumWristBendDegrees': worst_wrist,
            'chestWorldTravelRigUnits': max(m['chestWorldY'] for m in metrics) - min(m['chestWorldY'] for m in metrics),
            'hipsWorldTravelRigUnits': max(m['hipWorldY'] for m in metrics) - min(m['hipWorldY'] for m in metrics),
            'bladeAndBodyBindPreserved': True, 'nativeUnrealReview': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('body', 'previous', 'sword', 'output', 'sword-output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(write_candidate(args.body, args.previous, args.sword, args.output, args.sword_output), indent=2))


if __name__ == '__main__':
    main()
