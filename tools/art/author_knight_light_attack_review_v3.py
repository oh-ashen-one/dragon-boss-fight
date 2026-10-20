#!/usr/bin/env python3
"""Author a one-hand plunging strike from the approved idle.

The owner-provided Black Knight reference moves from a low one-hand guard to a
raised windup, then leaps into a forward ground strike and briefly holds low.
The approved idle supplies frame zero and the return pose. Separate whole-body
motion is solved between them; the original GLBs and bind data remain intact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from author_knight_actions import blend, build, sample, smooth
from author_knight_stances import Rig
from inspect_weapon_topology import GLB


DURATION = 2.40
SAMPLES = 145
SOCKET_ROTATION = Rotation.from_quat([0.78155554, 0.0047625, 0.01463231, -0.62364586]).as_matrix()
# Time, right hand relative to upper-arm joint, blade direction, torso yaw,
# forward pitch, hips displacement, left/right foot displacement, left hand
# relative to its upper-arm joint. Rig coordinates: Y up, Z forward.
CONTROLS = [
    (0.00, None, None, 0., 0., [0., 0., 0.], [0., 0., 0.], [0., 0., 0.], None),
    (0.18, [-.10, -.21, .09], [-.68, -.10, .73], -3., -2., [0., -.005, 0.], [0., 0., 0.], [0., 0., 0.], None),
    (0.39, [-.13, -.15, .13], [-.72, .25, .65], -11., -5., [0., -.015, .005], [0., 0., 0.], [0., 0., 0.], [.09, -.17, .10]),
    (0.60, [-.15, -.05, .16], [-.30, .82, .49], -14., -7., [0., .012, .035], [0., .035, .045], [0., .025, .015], [.09, -.10, .13]),
    (0.75, [-.13, .015, .18], [-.10, .90, .43], -7., 2., [0., .025, .060], [0., .080, .120], [0., .070, .035], [.09, -.07, .16]),
    (0.94, [-.06, -.18, .16], [.02, -.45, .90], 6., 33., [0., -.135, .155], [0., 0., .175], [0., 0., -.045], [.09, -.13, .17]),
    (1.10, [-.06, -.18, .16], [.02, -.45, .90], 6., 33., [0., -.145, .165], [0., 0., .175], [0., 0., -.045], [.09, -.13, .17]),
    (1.68, [-.06, -.18, .16], [.02, -.45, .90], 6., 33., [0., -.145, .165], [0., 0., .175], [0., 0., -.045], [.09, -.13, .17]),
    (2.10, [-.08, -.20, .10], [.20, .10, .97], 2., 7., [0., -.070, .045], [0., 0., .045], [0., 0., -.015], [.08, -.19, .10]),
    (DURATION, None, None, 0., 0., [0., 0., 0.], [0., 0., 0.], [0., 0., 0.], None),
]


def setup_rig(g: GLB, idle: GLB) -> Rig:
    r = Rig.__new__(Rig)
    r.g = g
    r.names = {node.get('name'): i for i, node in enumerate(g.json['nodes'])}
    r.rest = g.world_matrices()
    r.scale = np.asarray([node.get('scale', [1., 1., 1.]) for node in g.json['nodes']])
    r.factor = 244. / np.ptp(g.skinned_positions()[:, 1])
    r.order = []

    def visit(node: int) -> None:
        if node in r.order:
            return
        if node in g.parents:
            visit(g.parents[node])
        r.order.append(node)

    for node in range(len(g.json['nodes'])):
        visit(node)
    r.base = sample(idle, 0.)
    r.baseW = r.world(r.base)
    r.soft = True
    r.palm_axes = {}
    r.previous_elbows = {}
    r.previous_upper_rotations = {}
    r.elbow_delta_degrees = 15.
    return r


def turn(r: Rig, pose: dict, name: str, degrees: tuple[float, float, float]) -> None:
    node = r.names[name]
    world = r.world(pose)
    desired = Rotation.from_rotvec(np.deg2rad(degrees)).as_matrix() @ world[node, :3, :3]
    r.set_world_rotation(pose, node, desired, world)


def control_at(time: float, start_rotation: np.ndarray, start_axis: np.ndarray,
               right_start: np.ndarray, left_start: np.ndarray) -> tuple:
    i = max(0, min(len(CONTROLS) - 2, int(np.searchsorted([c[0] for c in CONTROLS], time, side='right') - 1)))
    a, b = CONTROLS[i:i + 2]
    raw = float(np.clip((time - a[0]) / (b[0] - a[0]), 0., 1.))
    # Anticipation briefly hangs, then the falling stroke accelerates into its
    # planted contact instead of easing through every interpolation key.
    u = 1. - (1. - raw) ** 3 if a[0] == .75 else float(smooth(raw))

    def orientation(axis: list[float] | None) -> Rotation:
        if axis is None:
            return Rotation.from_matrix(start_rotation)
        direction = np.asarray(axis, dtype=float)
        direction /= np.linalg.norm(direction)
        align, _ = Rotation.align_vectors([direction], [start_axis])
        return align * Rotation.from_matrix(start_rotation)

    rotations = Rotation.from_quat([orientation(a[2]).as_quat(), orientation(b[2]).as_quat()])
    hand_rotation = Slerp([0., 1.], rotations)(u).as_matrix()
    def lerp(index: int, fallback: np.ndarray | None = None) -> np.ndarray:
        left = fallback if a[index] is None else np.asarray(a[index], dtype=float)
        right = fallback if b[index] is None else np.asarray(b[index], dtype=float)
        return (1. - u) * left + u * right

    return (lerp(1, right_start), hand_rotation, float(lerp(3)), float(lerp(4)),
            lerp(5), lerp(6), lerp(7), lerp(8, left_start))


def write_candidate(body_path: Path, approved_idle_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite a review clip: {output}')
    g = GLB(body_path)
    idle = GLB(approved_idle_path)
    if g.json.get('animations') or len(idle.json.get('animations', [])) != 1:
        raise ValueError('Expected a static Knight rig and one approved idle clip')
    if g.json['nodes'] != idle.json['nodes'] or g.json['skins'] != idle.json['skins']:
        raise ValueError('The approved idle and Knight body do not share the exact bind skeleton')
    r = setup_rig(g, idle)
    arms = {side: [r.names[side + name] for name in ('Arm', 'ForeArm', 'Hand')] for side in ('Right', 'Left')}
    legs = {side: [r.names[side + name] for name in ('UpLeg', 'Leg', 'Foot')] for side in ('Right', 'Left')}
    animated = [node for chain in (*arms.values(), *legs.values()) for node in chain]
    rest_rotations = {node: np.asarray(g.json['nodes'][node].get('rotation', [0., 0., 0., 1.]), dtype=float) for node in animated}
    right = arms['Right']
    left = arms['Left']
    start = r.baseW[right[2], :3, :3]
    start_axis = start @ SOCKET_ROTATION[:, 1]
    right_start = r.baseW[right[2], :3, 3] - r.baseW[right[0], :3, 3]
    left_start = r.baseW[left[2], :3, 3] - r.baseW[left[0], :3, 3]
    times = np.unique(np.r_[np.linspace(0., DURATION, SAMPLES), [c[0] for c in CONTROLS]])
    poses = []
    metrics = []
    for time in times:
        # Frame zero and the final recovery frame exactly match the approved
        # one-hand idle. A small breath from that clip persists during action.
        idle_time = .8 * math.sin(math.pi * float(time) / DURATION) ** 2
        donor = sample(idle, idle_time)
        for node in animated:
            donor.setdefault((node, 'rotation'), rest_rotations[node].copy())
        hips = r.names['Hips']
        donor.setdefault((hips, 'translation'), np.asarray(g.json['nodes'][hips].get('translation', [0., 0., 0.]), dtype=float))
        pose = {key: value.copy() for key, value in donor.items()}
        right_rel, hand_rotation, yaw, pitch, hip_shift, left_step, right_step, left_rel = control_at(
            float(time), start, start_axis, right_start, left_start)
        pose[(hips, 'translation')] = donor[(hips, 'translation')] + hip_shift
        turn(r, pose, 'Spine', (pitch * .27, yaw * .26, 0.))
        turn(r, pose, 'Spine1', (pitch * .37, yaw * .34, 0.))
        turn(r, pose, 'Spine2', (pitch * .36, yaw * .40, 0.))
        turn(r, pose, 'Neck', (-pitch * .15, -yaw * .25, 0.))
        turn(r, pose, 'Head', (-pitch * .10, -yaw * .15, 0.))
        donor_world = r.world(donor)
        leg_errors = {}
        foot_targets = {}
        for side, shift, pole in (('Left', left_step, np.array([.12, 0., 1.])),
                                  ('Right', right_step, np.array([-.12, 0., 1.]))):
            chain = legs[side]
            target = donor_world[chain[2], :3, 3] + shift
            foot_targets[side] = target
            result = r.limb(pose, chain, target, donor_world[chain[2], :3, :3], pole)
            leg_errors[side] = result['reachClampCm']
        right_target = r.world(pose)[right[0], :3, 3] + right_rel
        arm = r.limb(pose, right, right_target, hand_rotation, np.array([-1., -.35, .30]))
        left_target = r.world(pose)[left[0], :3, 3] + left_rel
        left_arm = r.limb(pose, left, left_target, donor_world[left[2], :3, :3], np.array([1., -.35, .30]))
        # Solve away from the approved pose only after the windup starts. At
        # the final key the exact approved pose is restored for clean blending.
        fade = min(1., float(time) / .10, (DURATION - float(time)) / .18)
        pose = blend(donor, pose, max(0., fade))
        world = r.world(pose)
        sword_axis = world[right[2], :3, :3] @ SOCKET_ROTATION[:, 1]
        sword_tip = world[right[2], :3, 3] + world[right[2], :3, :3] @ np.array([.0616763, -.00199617, .00555098]) + sword_axis * (.4096359622825952 * 2.35)
        feet_error = {side: float(np.linalg.norm(world[chain[2], :3, 3] - foot_targets[side])) for side, chain in legs.items()}
        metrics.append({
            'seconds': float(time),
            'hips': world[hips, :3, 3].tolist(),
            'hand': world[right[2], :3, 3].tolist(),
            'swordAxis': sword_axis.tolist(),
            'swordTip': sword_tip.tolist(),
            'feetTargetError': feet_error,
            'reachClampCm': max(arm['reachClampCm'], left_arm['reachClampCm'], *leg_errors.values()),
            'reachClampByLimbCm': {'RightArm': arm['reachClampCm'], 'LeftArm': left_arm['reachClampCm'], **{side + 'Leg': value for side, value in leg_errors.items()}},
            'knees': {side: world[chain[1], :3, 3].tolist() for side, chain in legs.items()},
        })
        poses.append(pose)
    if any(set(pose) != set(poses[0]) for pose in poses):
        raise ValueError('Animation channel set changes between samples')
    if any(not np.allclose(poses[0][key], poses[-1][key], atol=1e-6) for key in poses[0]):
        raise ValueError('The attack does not return to the approved idle pose')
    worst_foot = max(max(row['feetTargetError'].values()) for row in metrics)
    worst_clamp = max(row['reachClampCm'] for row in metrics)
    if worst_foot > .012 or worst_clamp > 2.0:
        worst_row = max(metrics, key=lambda row: row['reachClampCm'])
        raise ValueError(f'Foot placement or arm reach failed: {worst_foot}, {worst_clamp} at {worst_row["seconds"]:.3f}s {worst_row["reachClampByLimbCm"]}')
    result = build(g, poses, times, 'LightAttack_BlackKnightReference_v3')
    if result.binary[:len(g.binary)] != g.binary or any(result.json.get(key) != g.json.get(key) for key in ('nodes', 'skins', 'meshes', 'materials', 'textures', 'images')):
        raise ValueError('Source body geometry or bind data changed')
    export_error = 0.
    for time, pose in zip(times, poses):
        export_error = max(export_error, float(np.abs(result.world_matrices(0, float(time)) - r.world(pose)).max()))
    if export_error > 1e-5:
        raise ValueError(f'Exported motion differs from authored poses: {export_error}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(result.bytes())
    return {
        'bodySourceSha256': hashlib.sha256(body_path.read_bytes()).hexdigest(),
        'approvedIdleSha256': hashlib.sha256(approved_idle_path.read_bytes()).hexdigest(),
        'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'durationSeconds': DURATION,
        'sampleCount': len(times),
        'maximumFootTargetErrorRigUnits': worst_foot,
        'maximumReachClampCm': worst_clamp,
        'maximumExportMatrixError': export_error,
        'startAndEndMatchApprovedIdle': True,
        'sourceGeometryAndBindDataPreserved': True,
        'nativeUnrealReview': False,
        'reference': 'https://cdnb.artstation.com/p/assets/images/images/032/421/303/original/elhuevocosmic-black-knight-gif-2.gif?1606387799',
        'keyMoments': {str(moment): min(metrics, key=lambda row: abs(row['seconds'] - moment)) for moment in (0., .39, .75, .94, 1.25, 1.68, DURATION)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', required=True, type=Path)
    parser.add_argument('--approved-idle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(write_candidate(args.body, args.approved_idle, args.output), indent=2))


if __name__ == '__main__':
    main()
