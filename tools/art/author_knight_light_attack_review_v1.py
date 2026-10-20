#!/usr/bin/env python3
"""Author a one-hand sword cut that begins and ends in the approved idle.

The approved idle supplies every body track and the exact endpoint pose. Only
additive torso response and a solved right-arm sword path are authored here.
The source GLB, sword, meshes, skin and bind matrices remain untouched.
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


DURATION = 1.35
SAMPLES = 82
SOCKET_ROTATION = Rotation.from_quat([0.78155554, 0.0047625, 0.01463231, -0.62364586]).as_matrix()
# Time, right-hand displacement in Knight rig units, sword direction, torso yaw,
# and chest pitch. The cut travels from the Knight's right shoulder across the
# body, with the blade kept in front of the armor.
CONTROLS = [
    (0.00, [0.000, 0.000, 0.000], None, 0.0, 0.0),
    (0.16, [-0.015, 0.025, 0.005], [0.15, 0.35, 0.92], -2.0, -1.0),
    (0.37, [-0.045, 0.155, 0.075], [-0.27, 0.88, 0.39], -9.0, -3.0),
    (0.50, [-0.030, 0.175, 0.110], [-0.12, 0.94, 0.32], -12.0, -4.0),
    (0.66, [0.080, 0.110, 0.110], [0.48, 0.62, 0.62], 2.0, 1.5),
    (0.76, [0.105, 0.090, 0.110], [0.77, -0.43, 0.47], 11.0, 6.0),
    (0.89, [0.100, 0.015, 0.090], [0.66, -0.61, 0.44], 13.0, 7.0),
    (1.12, [0.020, 0.020, 0.020], [0.32, 0.13, 0.94], 3.0, 1.0),
    (DURATION, [0.000, 0.000, 0.000], None, 0.0, 0.0),
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


def control_at(time: float, start_rotation: np.ndarray, start_axis: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    i = max(0, min(len(CONTROLS) - 2, int(np.searchsorted([c[0] for c in CONTROLS], time, side='right') - 1)))
    a, b = CONTROLS[i:i + 2]
    u = float(smooth((time - a[0]) / (b[0] - a[0])))

    def orientation(axis: list[float] | None) -> Rotation:
        if axis is None:
            return Rotation.from_matrix(start_rotation)
        direction = np.asarray(axis, dtype=float)
        direction /= np.linalg.norm(direction)
        align, _ = Rotation.align_vectors([direction], [start_axis])
        return align * Rotation.from_matrix(start_rotation)

    rotations = Rotation.from_quat([orientation(a[2]).as_quat(), orientation(b[2]).as_quat()])
    hand_rotation = Slerp([0., 1.], rotations)(u).as_matrix()
    displacement = (1. - u) * np.asarray(a[1]) + u * np.asarray(b[1])
    yaw = (1. - u) * a[3] + u * b[3]
    pitch = (1. - u) * a[4] + u * b[4]
    return displacement, hand_rotation, yaw, pitch


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
    chain = [r.names[name] for name in ('RightArm', 'RightForeArm', 'RightHand')]
    rest_rotations = {node: np.asarray(g.json['nodes'][node].get('rotation', [0., 0., 0., 1.]), dtype=float) for node in chain}
    start = r.baseW[chain[2], :3, :3]
    start_axis = start @ SOCKET_ROTATION[:, 1]
    times = np.unique(np.r_[np.linspace(0., DURATION, SAMPLES), [c[0] for c in CONTROLS]])
    poses = []
    metrics = []
    feet = [r.names['RightFoot'], r.names['LeftFoot']]
    for time in times:
        # A short inhale/exhale from the approved four-second loop stays under
        # the action. Mapping the full loop also makes both endpoints identical.
        donor = sample(idle, 4. * float(time) / DURATION)
        for node in chain:
            donor.setdefault((node, 'rotation'), rest_rotations[node].copy())
        pose = {key: value.copy() for key, value in donor.items()}
        displacement, hand_rotation, yaw, pitch = control_at(float(time), start, start_axis)
        turn(r, pose, 'Spine', (pitch * .18, yaw * .30, 0.))
        turn(r, pose, 'Spine1', (pitch * .30, yaw * .35, 0.))
        turn(r, pose, 'Spine2', (pitch * .52, yaw * .35, 0.))
        turn(r, pose, 'Neck', (-pitch * .25, -yaw * .35, 0.))
        donor_world = r.world(donor)
        target = donor_world[chain[2], :3, 3] + displacement
        arm = r.limb(pose, chain, target, hand_rotation, np.array([-1., -.35, .30]))
        # Solve away from the approved pose only after the windup starts. At
        # the final key the exact approved pose is restored for clean blending.
        fade = min(1., float(time) / .09, (DURATION - float(time)) / .13)
        pose = blend(donor, pose, max(0., fade))
        world = r.world(pose)
        sword_axis = world[chain[2], :3, :3] @ SOCKET_ROTATION[:, 1]
        metrics.append({
            'seconds': float(time),
            'hand': world[chain[2], :3, 3].tolist(),
            'swordAxis': sword_axis.tolist(),
            'footDrift': max(float(np.linalg.norm(world[foot, :3, 3] - donor_world[foot, :3, 3])) for foot in feet),
            'reachClampCm': arm['reachClampCm'],
        })
        poses.append(pose)
    if any(set(pose) != set(poses[0]) for pose in poses):
        raise ValueError('Animation channel set changes between samples')
    if any(not np.allclose(poses[0][key], poses[-1][key], atol=1e-6) for key in poses[0]):
        raise ValueError('The attack does not return to the approved idle pose')
    worst_foot = max(row['footDrift'] for row in metrics)
    worst_clamp = max(row['reachClampCm'] for row in metrics)
    if worst_foot > 1e-5 or worst_clamp > 1.0:
        worst_row = max(metrics, key=lambda row: row['reachClampCm'])
        raise ValueError(f'Feet or right arm lost contact: {worst_foot}, {worst_clamp} at {worst_row["seconds"]:.3f}s, hand {worst_row["hand"]}')
    result = build(g, poses, times, 'LightAttack_FromApprovedIdle_v1')
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
        'maximumFootDriftRigUnits': worst_foot,
        'maximumReachClampCm': worst_clamp,
        'maximumExportMatrixError': export_error,
        'startAndEndMatchApprovedIdle': True,
        'sourceGeometryAndBindDataPreserved': True,
        'nativeUnrealReview': False,
        'keyMoments': {str(moment): min(metrics, key=lambda row: abs(row['seconds'] - moment)) for moment in (0., .37, .50, .76, .89, DURATION)},
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
