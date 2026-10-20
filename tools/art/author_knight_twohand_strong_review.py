#!/usr/bin/env python3
"""Author the selected first two-hand sweep from the approved two-hand idle.

One rigid weapon frame drives both palm targets. Elbows bend in anatomical
planes, with continuous swivel selection and fixed bone lengths. Source mesh,
bind skeleton, approved clips, and the approved grip sword are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize_scalar, least_squares
from scipy.spatial.transform import Rotation

from author_knight_actions import build, sample
from author_knight_hold import unit
from author_knight_light_attack_review import setup_rig, turn
from inspect_weapon_topology import GLB

DURATION = 4.4
SOCKET = Rotation.from_quat([.78155554, .0047625, .01463231, -.62364586]).as_matrix()
GRIP = np.array([.0616763, -.00199617, .00555098])
SCALE = .4096359622825952

# Time progression follows the first sweep in the owner's 13.72s GIF.
# The later thrust is intentionally outside this clip.
KEYS = np.array([0, .35, .8, 1.15, 1.4, 1.75, 2.05, 2.4, 2.8, 3.5, 4.4])
VALUES = {
    'bladeYaw': [0, -12, -24, -30, -20, 5, 25, 35, 32, 15, 0],
    'bladeElev': [0, -20, -54, -58, -57, -55, -51, -46, -46, -25, 0],
    'torsoYaw': [0, -21, -61, -76, -48, 35, 88, 101, 99, 35, 0],
    'hipYaw': [0, -8, -30, -40, -20, 18, 50, 65, 60, 20, 0],
    'pitch': [0, 2, 4, 4, 8, 18, 34, 42, 38, 12, 0],
    'hipY': [0, -.01, -.025, -.032, -.045, -.065, -.08, -.085, -.075, -.025, 0],
    'hipZ': [0, 0, -.015, -.02, .025, .085, .11, .12, .12, .045, 0],
    'gripX': [0, -.01, -.02, -.025, -.015, .005, .015, .02, .015, .005, 0],
    'gripY': [0, -.035, -.095, -.10, -.08, -.055, -.09, -.10, -.085, -.03, 0],
    'gripZ': [0, -.015, -.015, -.015, .02, .035, .025, .015, .015, .005, 0],
    'stepY': [0, 0, .015, .04, .055, .015, 0, 0, 0, .035, 0],
    'stepZ': [0, 0, 0, .025, .10, .17, .18, .18, .18, .09, 0],
}


THRUST_KEYS = np.array([0,.4,1.,1.6,1.95,2.25,2.6,3.2,4.6,5.65,6.92])
THRUST_VALUES = {
    'bladeYaw': [0,-8,-19,-24,-18,8,24,24,24,10,0],
    'bladeElev': [0,-24,-50,-60,-60,-58,-54,-54,-54,-24,0],
    'torsoYaw': [0,-11,-35,-46,-28,12,24,24,24,10,0],
    'hipYaw': [0,-3,-12,-20,-10,7,16,16,16,7,0],
    'pitch': [0,0,-3,-6,-3,16,25,25,24,12,0],
    'hipY': [0,-.01,-.025,-.04,-.035,-.08,-.095,-.095,-.09,-.035,0],
    'hipZ': [0,0,-.025,-.045,-.025,.14,.22,.22,.22,.10,0],
    'gripX': [0,-.015,-.035,-.04,-.025,.015,.025,.025,.025,.01,0],
    'gripY': [0,-.025,-.07,-.085,-.065,-.045,-.04,-.04,-.04,-.01,0],
    'gripZ': [0,-.01,-.035,-.045,-.025,.09,.15,.15,.15,.04,0],
    'extension': [0,0,0,0,0,.6,1,1,1,.2,0],
    'stepY': [0,0,.015,.035,.065,.035,0,0,0,.045,0],
    'stepZ': [0,0,0,.015,.06,.21,.30,.30,.30,.16,0],
}


def basis(direction, hinge):
    x = unit(direction)
    z = unit(hinge - x * np.dot(x, hinge))
    return np.column_stack([x, np.cross(z, x), z])


def solve_arm(r, pose, chain, target, desired, state):
    """Solve the elbow circle with a real hinge, choosing its swivel smoothly."""
    upper, fore, hand = chain
    world = r.world(pose)
    shoulder = world[upper, :3, 3]
    u0 = r.baseW[fore, :3, 3] - r.baseW[upper, :3, 3]
    f0 = r.baseW[hand, :3, 3] - r.baseW[fore, :3, 3]
    hinge0 = unit(np.cross(u0, f0))
    l1, l2 = np.linalg.norm(u0), np.linalg.norm(f0)
    delta = target - shoulder
    distance = np.linalg.norm(delta)
    # Preserve a bent elbow, rather than silently moving a palm off the handle.
    max_distance = math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(math.radians(8)))
    if distance > max_distance:
        raise ValueError(f'Unreachable {r.g.json["nodes"][hand]["name"]}: {distance:.5f} > {max_distance:.5f}')
    direction = unit(delta)
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    radius = math.sqrt(max(0, l1*l1-along*along))
    center = shoulder + direction*along
    spine=r.names['Spine2']
    torso=world[spine,:3,:3]@r.baseW[spine,:3,:3].T
    pole=torso@u0
    pole = unit(pole-direction*np.dot(pole, direction))
    other = np.cross(direction, pole)
    base_wrist = r.baseW[fore, :3, :3].T @ r.baseW[hand, :3, :3]
    previous_upper = state.get('upper', r.baseW[upper, :3, :3])

    def evaluate(phi):
        elbow = center+radius*(pole*math.cos(phi)+other*math.sin(phi))
        u, f = elbow-shoulder, target-elbow
        hinge = unit(np.cross(u, f))
        upper_r = basis(u, hinge) @ basis(u0, hinge0).T @ r.baseW[upper, :3, :3]
        fore_r = basis(f, hinge) @ basis(f0, hinge0).T @ r.baseW[fore, :3, :3]
        # Forearm pronation/supination rotates around its long axis; it must
        # not be dumped into a 90-degree wrist bend. Keep it within the available pronation/supination travel from the approved grip.
        desired_fore = desired @ base_wrist.T
        q = Rotation.from_matrix(fore_r.T @ desired_fore).as_quat()
        local_axis = unit(fore_r.T @ f)
        twist = 2*math.atan2(float(q[:3] @ local_axis), float(q[3]))
        twist = (twist+math.pi) % (2*math.pi)-math.pi
        twist = float(np.clip(twist, -math.radians(155), math.radians(155)))
        fore_r = Rotation.from_rotvec(unit(f)*twist).as_matrix() @ fore_r
        wrist_delta = Rotation.from_matrix(base_wrist.T @ fore_r.T @ desired).magnitude()
        shoulder_step = Rotation.from_matrix(previous_upper.T @ upper_r).magnitude()
        score = wrist_delta**2 + .12*shoulder_step**2 + .025*phi**2 + .008*twist**2 + max(0,elbow[1]-shoulder[1]+.01)**2*300
        return score, elbow, upper_r, fore_r, wrist_delta, twist

    choices=np.linspace(-.8,.8,33)
    seed=min(choices,key=lambda p:evaluate(float(p))[0])
    optimum = minimize_scalar(lambda p: evaluate(p)[0], bounds=(max(-.8,seed-.06),min(.8,seed+.06)), method='bounded')
    _, elbow, upper_r, fore_r, wrist_delta, twist = evaluate(float(optimum.x))
    r.set_world_rotation(pose, upper, upper_r)
    r.set_world_rotation(pose, fore, fore_r)
    r.set_world_rotation(pose, hand, desired)
    state.update(elbow=elbow, upper=upper_r)
    bend = math.degrees(math.acos(float(np.clip(unit(elbow-shoulder) @ unit(target-elbow), -1, 1))))
    return {'wristDeltaDegrees': math.degrees(wrist_delta), 'elbowFlexDegrees': bend, 'forearmTwistDegrees': math.degrees(twist)}


def hand_target(base, chains, grip, center, weapon, side, extension):
    hand=chains[side][2]
    axis0=base[chains['Right'][2],:3,:3]@SOCKET[:,1]
    palm0=grip if side=='Right' else grip+axis0*(-.18*SCALE)
    local_grip=base[hand,:3,:3].T@(palm0-base[hand,:3,3])
    desired=weapon@base[hand,:3,:3]
    # A small oblique hilt grip lets the thrust extend without a cocked wrist.
    # Rotate about the palm center, keeping the same two handle contact points.
    palm_axis=unit(desired@GRIP)
    blade=weapon@axis0
    tilt_axis=unit(np.cross(palm_axis,blade))
    tilt=math.radians(30 if side=='Right' else 15)*extension
    desired=Rotation.from_rotvec(tilt_axis*tilt).as_matrix()@desired
    palm=center+weapon@(palm0-grip)
    return palm-desired@local_grip, desired


def solve_leg(r,pose,chain,base,target,heading):
    upper,knee,foot=chain
    world=r.world(pose);origin=world[upper,:3,3]
    u0=base[knee,:3,3]-base[upper,:3,3]
    f0=base[foot,:3,3]-base[knee,:3,3]
    h0=unit(np.cross(u0,f0));l1,l2=np.linalg.norm(u0),np.linalg.norm(f0)
    delta=target-origin;distance=np.linalg.norm(delta);direction=unit(delta)
    if distance>l1+l2:raise ValueError('Leg target beyond anatomical reach')
    a=(l1*l1-l2*l2+distance*distance)/(2*distance)
    radius=math.sqrt(max(0,l1*l1-a*a))
    yaw=Rotation.from_euler('y',heading,degrees=True).as_matrix()
    pole=unit(np.cross(direction,yaw@h0))
    elbow=origin+direction*a+pole*radius
    u,f=elbow-origin,target-elbow;hinge=unit(np.cross(u,f))
    r.set_world_rotation(pose,upper,basis(u,hinge)@basis(u0,h0).T@base[upper,:3,:3])
    r.set_world_rotation(pose,knee,basis(f,hinge)@basis(f0,h0).T@base[knee,:3,:3])
    r.set_world_rotation(pose,foot,yaw@base[foot,:3,:3])


def fit_weapon(r, pose, chains, base, grip, center, weapon, torso, previous, extension=0):
    """Fit a shared hilt position and axial roll to both forearm bend cones."""
    world = r.world(pose)
    blade = weapon @ (base[chains['Right'][2],:3,:3] @ SOCKET[:,1])
    def transform(x):
        return center+torso@x[:3], Rotation.from_rotvec(blade*x[3]).as_matrix()@weapon
    def residual(x):
        cc, ww = transform(x)
        errors=[]
        for side, (upper,fore,hand) in chains.items():
            shoulder=world[upper,:3,3]
            u0=base[fore,:3,3]-base[upper,:3,3]
            f0=base[hand,:3,3]-base[fore,:3,3]
            l1,l2=np.linalg.norm(u0),np.linalg.norm(f0)
            target, desired_hand=hand_target(base,chains,grip,cc,ww,side,extension)
            base_wrist=base[fore,:3,:3].T@base[hand,:3,:3]
            desired_fore=desired_hand@base_wrist.T
            desired_f=desired_fore@(base[fore,:3,:3].T@f0)
            delta=target-shoulder; d=np.linalg.norm(delta); direction=unit(delta)
            dc=float(np.clip(d,abs(l1-l2)+.001,(l1+l2)*.995))
            along=(l1*l1-l2*l2+dc*dc)/(2*dc)
            rad=math.sqrt(max(0,l1*l1-along*along))
            ec=shoulder+direction*along
            ideal=target-desired_f
            pref=torso@u0;pref=unit(pref-direction*np.dot(pref,direction))
            side_axis=np.cross(direction,pref)
            ideal_pole=ideal-ec
            phi=float(np.clip(math.atan2(ideal_pole@side_axis,ideal_pole@pref),-.8,.8))
            pole=pref*math.cos(phi)+side_axis*math.sin(phi)
            elbow=ec+rad*pole
            errors.extend((unit(target-elbow)-unit(desired_f))*2.)
            errors.append(max(0,elbow[1]-shoulder[1]+.02)*35.)
            errors.append(max(0,d-(l1+l2)*.98)*50.)
            bend=math.acos(float(np.clip(unit(elbow-shoulder)@unit(target-elbow),-1,1)))
            errors.append(max(0,bend-math.radians(125))*3.)
        errors.extend(x[:3]*np.array([1.5,1.5,1.5+extension*8]))
        errors.append(x[3]*.015)
        errors.extend((x-previous)*np.array([.12,.12,.12,.025]))
        return errors
    lower=np.array([-.12,-.05,-.12+.113*extension,-math.pi])
    upper=np.array([.12,.05,.12,math.pi])
    previous=np.clip(previous,lower+1e-8,upper-1e-8)
    result=least_squares(residual,previous,bounds=(lower,upper),max_nfev=45,ftol=1e-7,xtol=1e-7,gtol=1e-7)
    cc,ww=transform(result.x)
    return cc,ww,result.x


def write_candidate(body, approved_idle, output, move="sweep"):
    keys, values = (THRUST_KEYS, THRUST_VALUES) if move == "thrust" else (KEYS, VALUES)
    duration = float(keys[-1])
    if output.exists():
        raise FileExistsError(output)
    g, idle = GLB(body), GLB(approved_idle)
    if g.json['nodes'] != idle.json['nodes'] or g.json['skins'] != idle.json['skins']:
        raise ValueError('Approved idle and body must share the exact bind skeleton')
    r = setup_rig(g, idle)
    chains = {s: [r.names[s+n] for n in ('Arm', 'ForeArm', 'Hand')] for s in ('Right', 'Left')}
    legs = {s: [r.names[s+n] for n in ('UpLeg', 'Leg', 'Foot')] for s in ('Right', 'Left')}
    hips, chest = r.names['Hips'], r.names['Spine2']
    donor = {k: v.copy() for k, v in r.base.items()}
    for chain in (*chains.values(), *legs.values()):
        for n in chain:
            donor.setdefault((n, 'rotation'), np.array(g.json['nodes'][n].get('rotation', [0, 0, 0, 1]), dtype=float))
    donor.setdefault((hips, 'translation'), np.array(g.json['nodes'][hips]['translation'], dtype=float))
    base = r.world(donor)
    rh = chains['Right'][2]
    grip = base[rh, :3, 3] + base[rh, :3, :3] @ GRIP
    axis = base[rh, :3, :3] @ SOCKET[:, 1]
    yaw0 = math.degrees(math.atan2(axis[0], axis[2]))
    elev0 = math.degrees(math.asin(axis[1]))
    frame0 = Rotation.from_euler('y', yaw0, degrees=True).as_matrix() @ Rotation.from_euler('x', -elev0, degrees=True).as_matrix()
    curves = {k: PchipInterpolator(keys, v) for k, v in values.items()}
    times = np.unique(np.r_[np.linspace(0, duration, round(duration*60)+1), keys])
    states = {s: {} for s in chains}
    poses, metrics = [], []
    fit_state = np.zeros(4)
    for t in times:
        c = {k: float(f(t)) for k, f in curves.items()}
        pose = {k: v.copy() for k, v in donor.items()}
        pose[(hips, 'translation')] += [0, c['hipY'], c['hipZ']]
        turn(r, pose, 'Hips', (0, c['hipYaw'], 0))
        for name, weight in [('Spine', .27), ('Spine1', .36), ('Spine2', .37)]:
            turn(r, pose, name, (c['pitch']*weight*math.cos(math.radians(c['torsoYaw'])), (c['torsoYaw']-c['hipYaw'])*weight, -c['pitch']*weight*math.sin(math.radians(c['torsoYaw']))))
        turn(r, pose, 'Neck', (-c['pitch']*.2, -c['torsoYaw']*.16, 0))
        turn(r, pose, 'Head', (-c['pitch']*.1, -c['torsoYaw']*.1, 0))
        w = r.world(pose)
        torso = w[chest, :3, :3] @ base[chest, :3, :3].T
        center = w[chest, :3, 3] + torso @ (grip-base[chest, :3, 3] + [c['gripX'], c['gripY'], c['gripZ']])
        frame = Rotation.from_euler('y', yaw0+c['bladeYaw'], degrees=True).as_matrix() @ Rotation.from_euler('x', -elev0-c['bladeElev'], degrees=True).as_matrix()
        weapon = torso @ frame @ frame0.T
        center, weapon, fit_state = fit_weapon(r, pose, chains, base, grip, center, weapon, torso, fit_state, c.get('extension',0))
        arm_info, residuals = {}, {}
        for side, chain in chains.items():
            h = chain[2]
            target, desired = hand_target(base, chains, grip, center, weapon, side, c.get('extension',0))
            try:
                arm_info[side] = solve_arm(r, pose, chain, target, desired, states[side])
            except ValueError as error:
                raise ValueError(f'{t:.3f}s: {error}') from error
            residuals[side] = float(np.linalg.norm(r.world(pose)[h, :3, 3]-target))
        feet = {}
        for side, chain in legs.items():
            upper, knee, foot = chain
            target = base[foot, :3, 3] + (np.array([.025*c['stepZ']/.18, c['stepY'], c['stepZ']]) if side == 'Left' else np.zeros(3))
            solve_leg(r,pose,chain,base,target,c['hipYaw'])
            feet[side] = float(np.linalg.norm(r.world(pose)[foot, :3, 3]-target))
        if t == 0 or t == duration:
            pose = {k: v.copy() for k, v in donor.items()}
        if t == 0 or t == duration:
            center, weapon = grip.copy(), np.eye(3)
        # Independent socket preserves the blade path while palms tilt around
        # their fixed hilt contacts. It is a non-skin node, not a bind change.
        socket_node=len(g.json['nodes'])
        pose[(socket_node,'translation')]=center+weapon@axis*(.075*SCALE)
        pose[(socket_node,'rotation')]=Rotation.from_matrix(weapon@base[rh,:3,:3]@SOCKET).as_quat()
        poses.append(pose)
        metrics.append({'seconds': float(t), 'arms': arm_info, 'handTargetResidual': residuals, 'footTargetResidual': feet})
    if any(set(p) != set(poses[0]) for p in poses):
        raise ValueError('Channel set changed')
    worst_grip = max(max(m['handTargetResidual'].values()) for m in metrics)
    worst_foot = max(max(m['footTargetResidual'].values()) for m in metrics)
    worst_wrist = max(a['wristDeltaDegrees'] for m in metrics for a in m['arms'].values())
    if worst_wrist > 35:
        raise ValueError(f'Wrist motion exceeds review limit: {worst_wrist}')
    if worst_grip > 1e-5 or worst_foot > .01:
        raise ValueError(f'Contact drift: grip {worst_grip}, foot {worst_foot}')
    export_source=GLB(g.bytes())
    export_source.json['nodes'].append({'name':'ReviewWeaponSocket','scale':[SCALE]*3})
    export_source.json['scenes'][export_source.json.get('scene',0)]['nodes'].append(len(g.json['nodes']))
    result = build(export_source, poses, times, output.stem)
    if result.binary[:len(g.binary)] != g.binary or result.json['nodes'][:len(g.json['nodes'])] != g.json['nodes'] or any(result.json[k] != g.json[k] for k in ('skins', 'meshes', 'materials')):
        raise ValueError('Source geometry/bind changed')
    export_error = max(float(np.abs(result.world_matrices(0, float(t))[:len(g.json['nodes'])]-r.world(p)).max()) for t, p in zip(times, poses))
    if export_error > 1e-5:
        raise ValueError(f'Export matrix mismatch: {export_error}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
        f.write(result.bytes())
    return {'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'approvedIdleSha256': hashlib.sha256(approved_idle.read_bytes()).hexdigest(), 'move': move, 'durationSeconds': duration, 'sampleCount': len(times), 'maximumGripError': worst_grip, 'maximumFootError': worst_foot, 'maximumWristDeltaDegrees': worst_wrist, 'exportError': export_error, 'keyMoments': [min(metrics, key=lambda m: abs(m['seconds']-t)) for t in keys], 'nativeUnrealReview': False}


def make_review_sword(source, output):
    """Continuous narrow hilt for the oblique thrust grip; preserve the blade."""
    if output.exists():raise FileExistsError(output)
    g=GLB(source);primitive=g.json['meshes'][0]['primitives'][0]
    positions=g.accessor(primitive['attributes']['POSITION']);original=positions.copy()
    y=positions[:,1].astype(float)
    amount=np.minimum(np.clip((y+.43)/.12,0,1),np.clip((.33-y)/.12,0,1))
    positions[:,0]*=1-.52*amount;positions[:,2]*=1-.52*amount
    if np.any(positions[y>.43]!=original[y>.43]):raise ValueError('Blade changed')
    accessor=g.json['accessors'][primitive['attributes']['POSITION']]
    accessor['min']=positions.min(0).tolist();accessor['max']=positions.max(0).tolist()
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(g.bytes())
    return {'outputSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'handleTaper':.48,'allTrianglesPreserved':True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', required=True, type=Path)
    parser.add_argument('--approved-idle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--move', choices=['sweep', 'thrust'], default='sweep')
    args = parser.parse_args()
    print(json.dumps(write_candidate(args.body, args.approved_idle, args.output, args.move), indent=2))
