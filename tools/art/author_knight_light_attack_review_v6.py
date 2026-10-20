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
from author_knight_hold import align, unit
from inspect_weapon_topology import GLB


DURATION = 2.80
SAMPLES = 169
SOCKET_ROTATION = Rotation.from_quat([0.78155554, 0.0047625, 0.01463231, -0.62364586]).as_matrix()
# Time, right hand relative to upper-arm joint, blade direction, torso yaw,
# forward pitch, hips displacement, left/right foot displacement, left hand
# relative to its upper-arm joint. Rig coordinates: Y up, Z forward.
CONTROLS = [
    (0.00, None, None, 0., 0., [0., 0., 0.], [0., 0., 0.], [0., 0., 0.], None),
    (0.20, [-.10, -.22, .07], [-.70, -.12, .70], -5., -2., [0., -.008, 0.], [0., 0., 0.], [0., 0., 0.], [.04, -.16, .12]),
    (0.43, [-.11, -.05, -.03], [-.65, .48, -.58], -20., -5., [0., -.01, .008], [0., 0., 0.], [0., .04, .04], [.03, .015, .15]),
    (0.64, [-.08, .15, -.07], [-.10, .05, -.99], -24., -8., [0., .005, .025], [0., .015, .01], [0., .15, .08], [.16, .045, .07]),
    (0.80, [-.06, .225, -.02], [-.03, .20, -.98], -9., -2., [0., .025, .065], [0., .065, .02], [0., .17, .15], [.20, .07, -.015]),
    (0.855, [-.17, .10, .04], [.03, .98, .20], 7., 15., [0., -.03, .12], [0., .03, .015], [0., .08, .19], [.13, .07, .025]),
    (0.91, [-.025, -.243, .075], [.03, -.31, .95], 22., 55., [0., -.11, .145], [0., 0., .015], [0., 0., .21], [.09, .07, .06]),
    (1.04, [-.025, -.243, .075], [.03, -.31, .95], 24., 58., [0., -.12, .16], [0., 0., .015], [0., 0., .21], [.09, .075, .06]),
    (1.84, [-.025, -.24, .08], [.03, -.31, .95], 23., 56., [0., -.115, .16], [0., 0., .015], [0., 0., .21], [.09, .075, .06]),
    (2.38, [-.07, -.22, .12], [.15, .06, .99], 7., 14., [0., -.035, .065], [0., 0., .01], [0., .015, .08], [.08, -.12, .04]),
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


def sword_arm(r: Rig, pose: dict, chain: list, target: np.ndarray,
              desired: np.ndarray, time: float, state: dict) -> dict:
    """Solve elbow and axial sword roll together, keeping the wrist anatomical.

    A shortest-arc rotation from the bind forearm flips when the lifted arm
    passes its antipode. Build the forearm frame from the grip instead and
    carry the elbow plane continuously through the overhead swing.
    """
    world = r.world(pose)
    upper, fore, hand = chain
    shoulder = world[upper, :3, 3]
    l1 = np.linalg.norm(world[fore, :3, 3] - shoulder)
    l2 = np.linalg.norm(world[hand, :3, 3] - world[fore, :3, 3])
    delta = target - shoulder
    requested = np.linalg.norm(delta)
    distance = np.clip(requested, abs(l1 - l2) + .005, (l1 + l2) * .985)
    direction = unit(delta)
    target = shoulder + direction * distance
    along = (l1*l1 - l2*l2 + distance*distance) / (2*distance)
    height = math.sqrt(max(0., l1*l1 - along*along))
    center = shoulder + direction * along
    previous_elbow = state.get('elbow', r.baseW[fore, :3, 3])
    pole = previous_elbow - center
    pole -= direction * (pole @ direction)
    if np.linalg.norm(pole) < 1e-5:
        pole = np.array([-1., 0., 0.])
        pole -= direction * (pole @ direction)
    pole = unit(pole)
    other = np.cross(direction, pole)
    palm = unit((np.linalg.inv(r.rest[hand]) @ np.r_[r.rest[r.names['RightHandMiddle'], :3, 3], 1.])[:3])
    blade = desired @ SOCKET_ROTATION[:, 1]
    previous_roll = state.get('roll', 0.)
    envelope = 180. * max(0., min(1., time/.25, (DURATION-time)/.35))
    rolls = np.unique(np.clip(previous_roll + np.linspace(-12., 12., 25), -envelope, envelope))
    best = None
    for roll in rolls:
        rotation = Rotation.from_rotvec(blade * np.deg2rad(roll)).as_matrix() @ desired
        ideal = target - rotation @ palm * l2 - center
        angle = np.clip(math.atan2(ideal @ other, ideal @ pole), -.35, .35)
        elbow = center + height * (pole*math.cos(angle) + other*math.sin(angle))
        fore_direction = unit(target-elbow)
        bend = math.acos(float(np.clip(fore_direction @ (rotation @ palm), -1., 1.)))
        score = bend*bend + .012*np.deg2rad(roll)**2 + .025*np.deg2rad(roll-previous_roll)**2
        if best is None or score < best[0]:
            best = (score, rotation, elbow, roll, bend)
    _, rotation, elbow, roll, bend = best
    ref_hand = Rotation.from_quat(r.g.json['nodes'][hand]['rotation']).as_matrix()
    ref_fore = Rotation.from_quat(r.g.json['nodes'][fore]['rotation']).as_matrix()
    fore_hint = rotation @ ref_hand.T
    fore_rotation = align(fore_hint @ r.g.json['nodes'][hand]['translation'], target-elbow) @ fore_hint
    upper_hint = fore_rotation @ ref_fore.T
    upper_rotation = align(upper_hint @ r.g.json['nodes'][fore]['translation'], elbow-shoulder) @ upper_hint
    r.set_world_rotation(pose, upper, upper_rotation)
    r.set_world_rotation(pose, fore, fore_rotation)
    r.set_world_rotation(pose, hand, rotation)
    state.update(elbow=elbow, roll=float(roll))
    elbow_angle = math.degrees(math.acos(float(np.clip(unit(shoulder-elbow) @ unit(target-elbow), -1., 1.))))
    return {'reachClampCm': float(abs(requested-distance)*r.factor),
            'elbowInteriorDegrees': elbow_angle, 'wristBendDegrees': math.degrees(bend),
            'swordRollDegrees': float(roll)}


def control_at(time: float, start_rotation: np.ndarray, start_axis: np.ndarray,
               right_start: np.ndarray, left_start: np.ndarray) -> tuple:
    i = max(0, min(len(CONTROLS) - 2, int(np.searchsorted([c[0] for c in CONTROLS], time, side='right') - 1)))
    a, b = CONTROLS[i:i + 2]
    raw = float(np.clip((time - a[0]) / (b[0] - a[0]), 0., 1.))
    # Anticipation briefly hangs, then the falling stroke accelerates into its
    # planted contact instead of easing through every interpolation key.
    u = raw ** 2 if a[0] == .80 else float(smooth(raw))

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
    arm_state = {}
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
        arm = sword_arm(r, pose, right, right_target, hand_rotation, float(time), arm_state)
        left_target = r.world(pose)[left[0], :3, 3] + left_rel
        spine = r.names['Spine2']
        torso_delta = r.world(pose)[spine, :3, :3] @ donor_world[spine, :3, :3].T
        left_rotation = torso_delta @ donor_world[left[2], :3, :3]
        left_arm = r.limb(pose, left, left_target, left_rotation, np.array([1., -.20, -.50]))
        # The empty hand follows the forearm with its approved local wrist pose.
        pose[(left[2], 'rotation')] = donor[(left[2], 'rotation')].copy()
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
            'freeHand': world[left[2], :3, 3].tolist(),
            'head': world[r.names['Head'], :3, 3].tolist(),
            'swordElbowDegrees': arm['elbowInteriorDegrees'],
            'swordWristBendDegrees': arm['wristBendDegrees'],
            'swordRollDegrees': arm['swordRollDegrees'],
            'rightShoulder': world[right[0], :3, 3].tolist(),
            'leftShoulder': world[left[0], :3, 3].tolist(),
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
    peak = min(metrics, key=lambda row: abs(row['seconds'] - .80))
    contact = min(metrics, key=lambda row: abs(row['seconds'] - 1.04))
    if peak['hand'][1] < peak['head'][1] + .04:
        raise ValueError('Sword hand must rise above the head in the reference windup')
    if contact['freeHand'][1] - contact['hand'][1] < .25 or contact['swordElbowDegrees'] < 150:
        raise ValueError('Impact must extend the sword arm independently of the raised free arm')
    result = build(g, poses, times, 'LightAttack_BlackKnightReference_v6')
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
        'keyMoments': {str(moment): min(metrics, key=lambda row: abs(row['seconds'] - moment)) for moment in (0., .43, .64, .80, .91, 1.25, 1.84, DURATION)},
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
