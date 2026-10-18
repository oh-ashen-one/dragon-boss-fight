#!/usr/bin/env python3
"""Bake original, bounded FK/IK dragon motion onto an explicitly reviewed rig.

Never changes geometry, weights, inverse binds, node bind transforms or source
files. Appends named glTF animation tracks and a CPU evidence receipt. Actor
travel remains external; only world-vertical root posture is authored. Import
with root-motion extraction/force-root-lock OFF to retain that local posture.
CPU checks are mechanical evidence, not native deformation/visual acceptance.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from inspect_weapon_topology import GLB, ASSETS, primitive, sha, EVALUATOR


UP = np.array([0., 1., 0.])
FORWARD = np.array([1., 0., 0.])
PITCH = np.array([0., 0., 1.])
IDENTITY = np.array([0., 0., 0., 1.])


def unit(v):
    length = np.linalg.norm(v)
    return v / length if length > 1e-12 else np.zeros(3)


def qmul(a, b):
    q = np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3], b[:3]), a[3]*b[3]-np.dot(a[:3], b[:3])]
    return q / np.linalg.norm(q)


def axis_angle(axis, degrees):
    axis = unit(np.asarray(axis, float))
    half = np.radians(degrees)*.5
    return np.r_[axis*np.sin(half), np.cos(half)]


def ease(t):
    t = np.clip(t, 0., 1.)
    return t*t*(3.-2.*t)


def envelope(t):
    return np.sin(np.pi*np.clip(t, 0., 1.))**2


def append_accessor(model, values, kind):
    values = np.ascontiguousarray(values, dtype='<f4')
    model.binary.extend(b'\0'*(-len(model.binary) % 4))
    offset = len(model.binary)
    model.binary.extend(values.tobytes())
    view = len(model.json['bufferViews'])
    model.json['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': values.nbytes})
    index = len(model.json['accessors'])
    accessor = {'bufferView': view, 'componentType': 5126, 'count': len(values), 'type': kind}
    if kind == 'SCALAR':
        accessor.update({'min': [float(values.min())], 'max': [float(values.max())]})
    model.json['accessors'].append(accessor)
    model.json['buffers'][0]['byteLength'] = len(model.binary)
    return index


class Pose:
    def __init__(self, rig):
        self.rig = rig
        self.q = rig.rest_q.copy()
        self.t = rig.rest_t.copy()
        self.ik_corrections = np.zeros(4)
        self._world = None

    def world(self):
        if self._world is None:
            local = self.rig.rest_local.copy()
            for node in self.rig.joints:
                local[node] = EVALUATOR.trs({'translation': self.t[node], 'rotation': self.q[node], 'scale': self.rig.rest_s[node]})
            result = np.empty_like(local)
            for node in self.rig.order:
                parent = self.rig.parents.get(node)
                result[node] = local[node] if parent is None else result[parent] @ local[node]
            self._world = result
        return self._world

    def rotate_world(self, node, axis, degrees, limit=None):
        if abs(degrees) < 1e-10:
            return
        parent = self.rig.parents.get(node)
        parent_rotation = self.world()[parent, :3, :3] if parent is not None else np.eye(3)
        local_axis = unit(np.linalg.solve(parent_rotation, axis))
        candidate = qmul(axis_angle(local_axis, degrees), self.q[node])
        if limit is not None:
            rest_inverse = self.rig.rest_q[node]*np.array([-1., -1., -1., 1.])
            delta = qmul(candidate, rest_inverse)
            if delta[3] < 0:
                delta = -delta
            angle = np.degrees(2*np.arccos(np.clip(delta[3], -1., 1.)))
            if angle > limit:
                delta = EVALUATOR.slerp(IDENTITY, delta, limit/angle)
                candidate = qmul(delta, self.rig.rest_q[node])
        self.q[node] = candidate
        self._world = None

    def root_height(self, delta):
        root = self.rig.root
        parent = self.rig.parents.get(root)
        matrix = self.rig.rest_world[parent, :3, :3] if parent is not None else np.eye(3)
        self.t[root] += np.linalg.solve(matrix, UP*delta)
        self._world = None

    def set_leaf_rest_orientation(self, node):
        # Counter-rotate terminal toe/jaw-excluded foot joints only. Their pivot
        # positions and all link lengths remain fixed by the solved chain.
        parent = self.rig.parents.get(node)
        parent_matrix = self.world()[parent, :3, :3] if parent is not None else np.eye(3)
        rotation = np.linalg.solve(parent_matrix, self.rig.rest_world[node, :3, :3])
        rotation = rotation @ np.diag(1/self.rig.rest_s[node])
        u, _, vt = np.linalg.svd(rotation)
        rotation = u @ vt
        self.q[node] = matrix_quaternion(rotation)
        self._world = None

    def solve_leg(self, leg, target):
        # Analytic two-bone solve with the anatomical bind-pose knee plane.
        # The terminal ankle is held at its bind WORLD orientation, rather than
        # allowing a redundant toe link to spin through an arbitrary CCD solution.
        chain, end = leg['chain'], leg['end']
        hip, upper, knee = chain[:3]
        ankle = end if len(chain)==3 else chain[3]
        for node in set(chain+leg.get('leaves',[end])):
            self.q[node]=self.rig.rest_q[node].copy()
        self._world=None
        rest=self.rig.rest_world
        toe_offset=rest[end,:3,3]-rest[ankle,:3,3]
        goal=target-toe_offset
        l1=np.linalg.norm(rest[knee,:3,3]-rest[upper,:3,3])
        l2=np.linalg.norm(rest[ankle,:3,3]-rest[knee,:3,3])
        reach=(l1+l2)*.985
        world=self.world();hip_position=world[hip,:3,3];hip_vector=world[upper,:3,3]-hip_position
        if np.linalg.norm(goal-world[upper,:3,3])>reach:
            a,b=unit(hip_vector),unit(goal-hip_position);axis=unit(np.cross(a,b))
            full=np.arctan2(np.linalg.norm(np.cross(a,b)),np.dot(a,b))
            def moved(angle):
                return hip_position+hip_vector*np.cos(angle)+np.cross(axis,hip_vector)*np.sin(angle)+axis*np.dot(axis,hip_vector)*(1-np.cos(angle))
            if np.linalg.norm(axis)>0 and np.linalg.norm(goal-moved(full))<=reach:
                lo,hi=0.,full
                for _ in range(20):
                    mid=(lo+hi)*.5
                    if np.linalg.norm(goal-moved(mid))>reach:lo=mid
                    else:hi=mid
                self.rotate_world(hip,axis,np.degrees(hi),75.)
        world=self.world();origin=world[upper,:3,3]
        direction=unit(goal-origin);distance=np.linalg.norm(goal-origin)
        distance=np.clip(distance,abs(l1-l2)+1e-6,l1+l2-1e-6)
        along=(l1*l1-l2*l2+distance*distance)/(2*distance)
        height=np.sqrt(max(0.,l1*l1-along*along))
        rest_normal=unit(np.cross(rest[ankle,:3,3]-rest[upper,:3,3],rest[knee,:3,3]-rest[upper,:3,3]))
        parent=self.rig.parents[upper]
        normal=world[parent,:3,:3]@np.linalg.solve(rest[parent,:3,:3],rest_normal)
        bend=unit(np.cross(normal,direction))
        if np.linalg.norm(bend)<.5:raise ValueError('Leg target aligned with anatomical knee plane normal')
        desired_knee=origin+direction*along+bend*height
        def aim(node,current,desired,limit):
            a,b=unit(current),unit(desired);axis=np.cross(a,b)
            if np.linalg.norm(axis)>1e-10:
                angle=np.degrees(np.arctan2(np.linalg.norm(axis),np.dot(a,b)))
                self.rotate_world(node,unit(axis),angle,limit)
        aim(upper,world[knee,:3,3]-origin,desired_knee-origin,110.)
        world=self.world();origin=world[knee,:3,3]
        aim(knee,world[ankle,:3,3]-origin,goal-origin,135.)
        self.set_leaf_rest_orientation(ankle)
        for leaf in leg.get('leaves', [end]):
            self.set_leaf_rest_orientation(leaf)
        return float(np.linalg.norm(self.world()[end, :3, 3]-target))


def matrix_quaternion(r):
    k = np.array([[r[0, 0]-r[1, 1]-r[2, 2], r[1, 0]+r[0, 1], r[2, 0]+r[0, 2], r[2, 1]-r[1, 2]],
                  [r[1, 0]+r[0, 1], r[1, 1]-r[0, 0]-r[2, 2], r[2, 1]+r[1, 2], r[0, 2]-r[2, 0]],
                  [r[2, 0]+r[0, 2], r[2, 1]+r[1, 2], r[2, 2]-r[0, 0]-r[1, 1], r[1, 0]-r[0, 1]],
                  [r[2, 1]-r[1, 2], r[0, 2]-r[2, 0], r[1, 0]-r[0, 1], np.trace(r)]])/3
    _, vectors = np.linalg.eigh(k)
    q = vectors[:, -1]
    return q if q[3] >= 0 else -q


class DragonRig:
    def __init__(self, source, semantic, cm_per_unit):
        self.source, self.semantic, self.cm = source, semantic, cm_per_unit
        self.parents = source.parents
        self.nodes = source.json['nodes']
        self.lookup = {n.get('name'): i for i, n in enumerate(self.nodes)}
        if len(self.lookup) != len(self.nodes):
            raise ValueError('Node names must be unique')
        self.joints = list(source.json['skins'][0]['joints'])
        if any('matrix' in self.nodes[i] for i in self.joints):
            raise ValueError('Animated joints must use TRS bind transforms')
        self.rest_world = source.world_matrices()
        self.rest_local = np.array([EVALUATOR.trs(n) for n in self.nodes])
        self.rest_q = np.array([n.get('rotation', IDENTITY) for n in self.nodes], dtype=float)
        self.rest_t = np.array([n.get('translation', [0, 0, 0]) for n in self.nodes], dtype=float)
        self.rest_s = np.array([n.get('scale', [1, 1, 1]) for n in self.nodes], dtype=float)
        def depth(i):
            return 0 if i not in self.parents else depth(self.parents[i])+1
        self.order = sorted(range(len(self.nodes)), key=depth)
        self.root = self.lookup[semantic.get('motionRoot', 'tripo::Root')]
        self.head = self.lookup[semantic['head']]
        self.jaw = self.lookup[semantic['jaw']]
        self.neck = [self.parents[self.parents[self.head]], self.parents[self.head], self.head]
        self.tail = [self.lookup[n] for n in ('bone_18', 'tripo::Tail_0', 'tripo::Tail_1', 'tripo::Tail_2')]
        self.wings = [[self.lookup[n] for n in semantic[key]] for key in ('positiveZWing', 'negativeZWing')]
        defaults = [
            {'joints': ['bone_6', 'bone_7', 'tripo::1_Left_Limb_0'], 'end': 'tripo::1_Left_Limb_1'},
            {'joints': ['bone_11', 'tripo::0_Left_Limb_0', 'tripo::0_Left_Limb_1', 'tripo::0_Left_Limb_2'], 'end': 'tripo::0_Left_Limb_3'},
            {'joints': ['tripo::1_Right_Limb_0', 'tripo::1_Right_Limb_1', 'tripo::1_Right_Limb_2', 'tripo::1_Right_Limb_3'], 'end': 'tripo::1_Right_Limb_4'},
            {'joints': ['tripo::0_Right_Limb_0', 'tripo::0_Right_Limb_1', 'tripo::0_Right_Limb_2', 'tripo::0_Right_Limb_3'], 'end': 'tripo::0_Right_Limb_4'},
        ]
        self.legs = []
        for index, spec in enumerate(semantic.get('motionLegChains', defaults)):
            chain = [self.lookup[n] for n in spec['joints']]
            end = self.lookup[spec['end']]
            sequence = chain+[end]
            if any(self.parents[b] != a for a, b in zip(sequence, sequence[1:])):
                raise ValueError('Leg chain is not an actual parent-child path: '+str(index))
            self.legs.append({'chain': chain, 'end': end, 'rest': self.rest_world[end, :3, 3].copy()})
        if len(self.legs) != 4:
            raise ValueError('Exactly four independent leg chains are required')
        self.ik_tolerance = .6/self.cm  # sub-centimetre point-target tolerance
        self.joint_edges = [(self.parents[i], i) for i in self.joints if self.parents.get(i) in self.joints]
        self.lengths = np.array([np.linalg.norm(self.rest_world[b, :3, 3]-self.rest_world[a, :3, 3]) for a, b in self.joint_edges])
        self.rest_vertices = source.skinned_positions()
        _, primitive_data, _, _ = primitive(source)
        js = source.accessor(primitive_data['attributes']['JOINTS_0'])
        ws = source.accessor(primitive_data['attributes']['WEIGHTS_0'])
        self.foot_masks = []
        for leg in self.legs:
            descendants = set(leg['chain'])|{leg['end']}
            changed = True
            while changed:
                new = {i for i in self.joints if self.parents.get(i) in descendants}
                changed = not new.issubset(descendants); descendants |= new
            leg['leaves'] = [i for i in descendants if not self.nodes[i].get('children')]
            skin_ids = [self.joints.index(i) for i in descendants]
            influence = np.sum(np.where(np.isin(js, skin_ids), ws, 0), axis=1)
            mask = (influence > .75) & (self.rest_vertices[:, 1] < .018)
            self.foot_masks.append(mask)
        self.inverse_binds = source.accessor(source.json['skins'][0]['inverseBindMatrices']).copy().reshape(-1, 4, 4).transpose(0, 2, 1)
        self.foot_geometry = []
        positions = source.accessor(primitive_data['attributes']['POSITION']).astype(float)
        for mask in self.foot_masks:
            if not mask.any(): raise ValueError('No strongly leg-weighted sole vertices available for contact validation')
            self.foot_geometry.append((np.column_stack((positions[mask], np.ones(int(mask.sum())))), js[mask].copy(), ws[mask].copy()))

    def sole_minimum(self, pose, index):
        positions, joints, weights = self.foot_geometry[index]
        matrices = pose.world()[self.joints] @ self.inverse_binds
        posed = sum(np.einsum('nij,nj->ni', matrices[joints[:, i]], positions)*weights[:, i, None] for i in range(4))
        return float(posed[:, 1].min())

    def pose(self, clip, t, previous=None):
        p = Pose(self)
        targets = [leg['rest'].copy() for leg in self.legs]
        planted = [True]*4
        # All profiles are deliberate posture/anticipation/contact/recovery
        # curves. No stochastic noise or decorative per-bone random oscillation.
        down, pitch, roll, neck_pitch, neck_yaw, jaw = 0., 0., 0., 0., 0., 0.
        flap, wing_fold, tail_yaw, skull_correction = 0., 10., 0., 0.
        if clip == 'Idle':
            down = -.0018*np.sin(2*np.pi*t)
            neck_pitch = 1.2*np.sin(2*np.pi*t)
        elif clip == 'Walk':
            down = .003*(1-np.cos(4*np.pi*t))
            for i in range(4):
                phase = (t+[0., .5, .75, .25][i]) % 1.
                if phase < .75:
                    targets[i][0] += .031*(1.-2.*phase/.75)
                else:
                    u = (phase-.75)/.25
                    targets[i][0] += -.031+.062*ease(u)
                    targets[i][1] += .026*np.sin(np.pi*u)**2
                    planted[i] = False
        elif clip.startswith('Buckle'):
            index = int(clip[-1]); u = ease(t)
            down = .025*u; roll = (1 if index % 2 else -1)*6*u
            targets[index][0] += (-1 if index < 2 else 1)*.022*u
            targets[index][2] += np.sign(targets[index][2])*.013*u
            neck_pitch = -8*u
        elif clip in ('Collapse', 'Exposed', 'Rise', 'Death', 'DeathDown'):
            u = ease(t) if clip in ('Collapse', 'Death') else 1-ease(t) if clip == 'Rise' else 1.
            down = (.025+.045*u) if clip == 'Collapse' else .070*u
            pitch = -8*u; neck_pitch = -66*u; wing_fold = 10+10*u
            jaw = 8*u
            if clip == 'Exposed':
                neck_pitch += .4*np.sin(2*np.pi*t);jaw += .5*np.sin(2*np.pi*t)
            if clip in ('Death', 'DeathDown'):
                settle=ease(t) if clip == 'DeathDown' else u
                roll = 2*settle;neck_pitch -= 5*settle
                jaw = 8+8*settle if clip == 'DeathDown' else 16*u;tail_yaw = 4*settle
            # Lower the articulated neck while keeping the skull level enough
            # to expose its crown rather than drive the snout through the floor.
            skull_correction = -neck_pitch-pitch
        else:
            suffix = next(s for s in ('Windup', 'Active', 'Recovery') if clip.endswith(s))
            move = clip[:-len(suffix)]
            if move == 'Fire':
                if suffix == 'Windup':
                    u = ease(t);neck_pitch=10*u;neck_yaw=-64*u;jaw=24*u;down=.006*u;skull_correction=-35*u
                elif suffix == 'Active':
                    neck_pitch=10;neck_yaw=-64+128*t;jaw=24;down=.006;skull_correction=-35
                else:
                    u=1-ease(t);neck_pitch=10*u;neck_yaw=64*u;jaw=24*u;down=.006*u;skull_correction=-35*u
            elif move == 'Bite':
                if suffix == 'Windup':
                    gather=ease(t/.65);strike=ease((t-.75)/.25)
                    neck_pitch=18*gather-88*strike;jaw=25*gather*(1-.85*strike);pitch=3*gather-9*strike
                    down=.045*strike;skull_correction=61*strike
                elif suffix == 'Active':
                    neck_pitch=-70;jaw=3.75*(1-ease(t/.25));pitch=-6;down=.045;skull_correction=61
                else:
                    u=1-ease(t);neck_pitch=-70*u;pitch=-6*u;down=.045*u;skull_correction=61*u
            elif move == 'Flight':
                if suffix == 'Windup':
                    u=ease(t);down=.022*u;wing_fold=10*(1-u);flap=-22*u
                elif suffix == 'Active':
                    # FlightSeconds=2.4; ActiveDuration=2.75. Actor supplies all
                    # altitude and horizontal reposition. Local legs tuck only.
                    airborne=min(1., t*2.75/2.4)
                    landing=ease((t*2.75-1.85)/.55)
                    flap=30*np.sin(airborne*4*np.pi-np.pi/4)*(1-landing)
                    wing_fold=10*landing
                    down=.030*landing
                    for i in range(4):
                        targets[i][1] += .080*(1-landing)*ease(t/.12)
                        targets[i][0] -= .025*(1-landing)*ease(t/.12)
                        planted[i] = landing >= .999
                else:
                    down=.030*(1-ease(t));wing_fold=10
            elif move.startswith('Stomp'):
                index=int(move[-1])
                if suffix == 'Windup': lift=ease(t/.65)*(1-ease((t-.75)/.25));down=.004*lift
                elif suffix == 'Active': lift=0.;down=.018*envelope(t/.5)
                else: lift=0.;down=0.
                targets[index][1] += .065*lift;targets[index][0] += .012*lift
                planted[index] = lift < .001
            elif move in ('Claw','Claw0','Claw1'):
                index=1 if move=='Claw1' else 0
                mirror=-1 if index else 1
                if suffix == 'Windup':
                    u=ease(t);targets[index] += [0., .055*u, -.035*u*mirror];roll=3*u*mirror;neck_yaw=-12*u*mirror
                elif suffix == 'Active':
                    u=ease(t);targets[index] += [.045*np.sin(np.pi*u), .055*(1-.7*u), (-.035+.090*u)*mirror]
                    roll=(3-6*u)*mirror;neck_yaw=(-12+24*u)*mirror
                else:
                    u=1-ease(t);targets[index] += [0., .0165*u, .055*u*mirror];roll=-3*u*mirror;neck_yaw=12*u*mirror
                planted[index] = suffix == 'Recovery' and t >= .999
            elif move == 'Tail':
                if suffix == 'Windup': tail_yaw=-85*ease(t);pitch=2*ease(t)
                elif suffix == 'Active': tail_yaw=-85+170*ease(t);pitch=2
                else: tail_yaw=85*(1-ease(t));pitch=2*(1-ease(t))
            else:
                raise ValueError('Unsupported motion '+clip)
        p.root_height(-down)
        p.rotate_world(self.root, PITCH, pitch, 14.)
        p.rotate_world(self.root, FORWARD, roll, 10.)
        for node, share in zip(self.neck, (.76, .24, 0.)):
            p.rotate_world(node, PITCH, neck_pitch*share, 75.)
        for node, share in zip(self.neck, (.45, .35, .20)):
            # UE imports source (X,Y,Z) as (X,Z,Y). Its handedness flip means
            # a positive gameplay yaw requires negative source-world Y rotation.
            p.rotate_world(node, UP, -neck_yaw*share, 78.)
        skull_axis = p.world()[self.head, :3, :3] @ np.linalg.solve(self.rest_world[self.head, :3, :3], PITCH)
        p.rotate_world(self.head, skull_axis, skull_correction, 85.)
        jaw_axis = np.asarray(self.semantic.get('jawOpenWorldAxis', [0, 0, 1]), float)
        jaw_axis = p.world()[self.head, :3, :3] @ np.linalg.solve(self.rest_world[self.head, :3, :3], jaw_axis)
        p.rotate_world(self.jaw, jaw_axis, jaw*self.semantic.get('jawOpenAngleSign', -1), 32.)
        # Mirrored world-axis signs come from the reviewed rig map. Both branches
        # are separately animated; no polluted legacy Head-labelled wing joints.
        signs = self.semantic.get('wingDownAngleSigns', {'PosZ': 1, 'NegZ': -1})
        for side, chain in zip(('PosZ', 'NegZ'), self.wings):
            sign = signs[side]
            # Ground fold lifts the low membrane edge while folding the elbow
            # rearward; positive flap still means the reviewed downstroke sign.
            p.rotate_world(chain[0], FORWARD, sign*(flap-wing_fold), 45.)
            p.rotate_world(chain[1], UP, -sign*wing_fold*.7, 28.)
            p.rotate_world(chain[3], UP, -sign*wing_fold*.45, 22.)
        for node, share in zip(self.tail, (.20, .25, .30, .25)):
            p.rotate_world(node, UP, -tail_yaw*share, 35.)
        tail_grounding=np.clip((down-.025)/.045,0.,1.15)
        for node, degrees in zip(self.tail,(-18.,14.,10.,0.)):
            p.rotate_world(node,PITCH,degrees*tail_grounding,35.)
        errors = []
        for index, (leg, target) in enumerate(zip(self.legs, targets)):
            # Point IK alone does not ground a skinned sole on this unusual
            # imported rig. Measure actual weighted sole vertices, then correct
            # only the IK target height. No geometry/weights/link lengths change.
            sole_height = max(0., target[1]-leg['rest'][1]) if not planted[index] else 0.
            raw_target_height=float(target[1])
            if previous is not None: target[1] += previous.ik_corrections[index]
            error = p.solve_leg(leg, target)
            best_error=float('inf');best_q=p.q.copy();best_target=target.copy()
            for _ in range(13):
                correction = sole_height-self.sole_minimum(p, index)
                if abs(correction)<best_error:
                    best_error=abs(correction);best_q=p.q.copy();best_target=target.copy()
                if abs(correction)*self.cm < 1.25: break
                target[1] += np.clip(correction*.85, -.030, .040)
                error = p.solve_leg(leg, target)
            p.q=best_q;p._world=None;target[:]=best_target
            p.ik_corrections[index]=target[1]-raw_target_height
            errors.append(float(np.linalg.norm(p.world()[leg['end'], :3, 3]-target)))
        return p, targets, planted, errors


def clips():
    result = {'Idle': (4., True), 'Walk': (1.1, True), **{'Buckle'+str(i): (.65, False) for i in range(4)},
              'Collapse': (1., False), 'Exposed': (7., False), 'Rise': (2., False), 'Death': (3.4, False), 'DeathDown': (3.4, False)}
    for move, durations in {'Fire': (1.75, 2.1, 2.), 'Flight': (1.6, 2.75, 2.3), 'Claw': (1.15, .48, 1.6),
                            'Claw0': (1.15, .48, 1.6), 'Claw1': (1.15, .48, 1.6),
                            'Stomp2': (1.25, .28, 1.5), 'Stomp3': (1.25, .28, 1.5), 'Tail': (1.45, .65, 1.8), 'Bite': (1.05, .30, 1.6)}.items():
        for suffix, duration in zip(('Windup', 'Active', 'Recovery'), durations):
            result[move+suffix] = (duration, False)
    return result


def author(source, semantic, cm_per_unit, fps):
    if len(source.json.get('skins', [])) != 1 or source.json.get('animations'):
        raise ValueError('Use one reviewed, animation-free base rig')
    rig = DragonRig(source, semantic, cm_per_unit)
    output = GLB(source.bytes())
    output.json['animations'] = []
    original_binary = bytes(source.binary)
    reports = [];end_poses={}
    for name, (duration, loop) in clips().items():
        count=max(3, int(np.ceil(duration*fps))+1)
        times=np.linspace(0, duration, count)
        predecessor = name.replace('Active','Windup') if name.endswith('Active') else name.replace('Recovery','Active') if name.endswith('Recovery') else {
            'Exposed':'Collapse','Rise':'Exposed','DeathDown':'Exposed'}.get(name,'Idle')
        previous=end_poses.get(predecessor)
        # Analytic knee planes remove redundant-joint branch flips. Warm-start
        # sole-height correction and settle loop traversals before recording.
        if loop:
            for _ in range(2):
                for seconds in times:
                    previous=rig.pose(name,seconds/duration,previous)[0]
        rotations={node: [] for node in rig.joints}
        translations=[]; trajectories=[]; max_ik=0.; max_length_error=0.; max_planted_sole=0.
        previous_world_rotation=None;first_world_rotation=None;maximum_world_angle=0.
        for index, seconds in enumerate(times):
            pose, targets, planted, errors=rig.pose(name, seconds/duration,previous)
            previous=pose
            world=pose.world()
            world_rotation=world[:,:3,:3]/np.linalg.norm(world[:,:3,:3],axis=-2,keepdims=True)
            if previous_world_rotation is not None:
                angles=np.degrees(np.arccos(np.clip((np.sum(world_rotation*previous_world_rotation,axis=(1,2))-1)/2,-1,1)))
                maximum_world_angle=max(maximum_world_angle,float(angles.max()))
            if first_world_rotation is None:first_world_rotation=world_rotation.copy()
            previous_world_rotation=world_rotation.copy()
            max_ik=max(max_ik, max(errors)*cm_per_unit)
            lengths=np.array([np.linalg.norm(world[b, :3, 3]-world[a, :3, 3]) for a, b in rig.joint_edges])
            max_length_error=max(max_length_error, float(np.max(np.abs(lengths-rig.lengths)))*cm_per_unit)
            if max_length_error>.05: raise ValueError('Bone-length preservation failed: '+name)
            if not np.isfinite(world).all() or not np.isfinite(pose.q).all():
                raise ValueError('Non-finite pose '+name)
            for node in rig.joints:
                q=pose.q[node]
                if rotations[node] and np.dot(q, rotations[node][-1])<0: q=-q
                rotations[node].append(q.copy())
            translations.append(pose.t[rig.root].copy())
            soles=[rig.sole_minimum(pose, i)*cm_per_unit for i in range(4)]
            max_planted_sole=max(max_planted_sole,max([abs(soles[i]) for i in range(4) if planted[i]] or [0.]))
            trajectories.append({'seconds': float(seconds), 'headCm': (world[rig.head, :3, 3]*cm_per_unit).tolist(),
                                 'footCm': [(world[leg['end'], :3, 3]*cm_per_unit).tolist() for leg in rig.legs],
                                 'footTargetCm': [(v*cm_per_unit).tolist() for v in targets], 'planted': [bool(value) for value in planted],
                                 'footSurfaceMinimumYCm': soles, 'ikErrorCm': (np.asarray(errors)*cm_per_unit).tolist()})
        animation={'name': name, 'samplers': [], 'channels': [], 'extras': {'originalVeyrMotion': True, 'loop': loop, 'actorTravelNotAuthored': True}}
        alias=name.replace('Claw0','Claw') if name.startswith('Claw0') else None
        if alias:animation['extras']['aliasOf']=alias
        timeline=append_accessor(output, np.asarray(times).reshape(-1, 1), 'SCALAR')
        for node, values in rotations.items():
            accessor=append_accessor(output, values, 'VEC4')
            animation['channels'].append({'sampler': len(animation['samplers']), 'target': {'node': node, 'path': 'rotation'}})
            animation['samplers'].append({'input': timeline, 'output': accessor, 'interpolation': 'LINEAR'})
        accessor=append_accessor(output, translations, 'VEC3')
        animation['channels'].append({'sampler': len(animation['samplers']), 'target': {'node': rig.root, 'path': 'translation'}})
        animation['samplers'].append({'input': timeline, 'output': accessor, 'interpolation': 'LINEAR'})
        output.json['animations'].append(animation)
        end_poses[name]=previous
        max_rotation_step=max(float(np.max(np.degrees(2*np.arccos(np.clip(np.abs(np.sum(np.asarray(v)[1:]*np.asarray(v)[:-1],axis=1)),0,1))))) for v in rotations.values())
        striking_leg=1 if name.startswith('Claw1') else 0 if name.startswith('Claw') else int(name[5]) if name.startswith('Stomp') else None
        reports.append({'clip': name, 'durationSeconds': duration, 'loop': loop, 'keyFrames': count, 'aliasOf':alias,'strikingLegIndex':striking_leg,
                        'maximumIKPointErrorCm': max_ik, 'maximumBoneLengthChangeCm': max_length_error,
                        'maximumPlantedSoleAbsoluteHeightCm': max_planted_sole, 'plantedSolesWithin5cm': max_planted_sole<=5.,
                        'maximumAdjacentJointRotationDegrees': max_rotation_step,
                        'maximumAdjacentWorldJointRotationDegrees': maximum_world_angle,
                        'loopSeamMaximumJointAngleDegrees': max(float(np.degrees(2*np.arccos(np.clip(abs(np.dot(v[0],v[-1])),0,1)))) for v in rotations.values()) if loop else None,
                        'loopSeamMaximumWorldJointAngleDegrees': float(np.degrees(np.arccos(np.clip((np.sum(first_world_rotation*previous_world_rotation,axis=(1,2))-1)/2,-1,1))).max()) if loop else None,
                        'trajectories': trajectories})
        print(json.dumps({'authored':name,'frames':count,'ikCm':max_ik,'plantedSoleCm':max_planted_sole}),flush=True)
    if bytes(output.binary[:len(original_binary)]) != original_binary:
        raise AssertionError('Original binary prefix changed')
    for field in ('accessors','bufferViews'):
        if output.json[field][:len(source.json[field])] != source.json[field]:
            raise AssertionError('Original accessor/view definitions changed')
    for field in ('meshes', 'skins', 'nodes', 'materials', 'textures', 'images', 'samplers'):
        if output.json.get(field) != source.json.get(field):
            raise AssertionError('Forbidden original-data mutation: '+field)
    # Reopen final GLB and use the independent existing CPU skin evaluator at
    # interval boundaries and midpoints, not only authoring solver matrices.
    reopened=GLB(output.bytes())
    for index, report in enumerate(reports):
        samples=[]
        for fraction in (0., .125, .25, .5, .75, .875, 1.):
            seconds=report['durationSeconds']*fraction
            vertices=reopened.skinned_positions(index, seconds)
            if not np.isfinite(vertices).all(): raise ValueError('Non-finite skinned mesh '+report['clip'])
            world=reopened.world_matrices(index, seconds)
            horizontal=float(np.linalg.norm((world[rig.root, :3, 3]-rig.rest_world[rig.root, :3, 3])[[0, 2]]))*cm_per_unit
            if horizontal>1e-3: raise ValueError('Animation authored horizontal root travel')
            actor_altitude=1400*np.sin(np.pi*min(seconds/2.4,1.)) if report['clip']=='FlightActive' and seconds<2.4 else 0.
            samples.append({'seconds': seconds, 'meshBoundsCm': (np.array([vertices.min(0), vertices.max(0)])*cm_per_unit).tolist(),
                            'authoredActorFlightAltitudeForContextCm': float(actor_altitude),
                            'minimumMeshYWithActorFlightCm': float(vertices[:,1].min()*cm_per_unit+actor_altitude),
                            'rootHorizontalTravelCm': horizontal,
                            'footSurfaceMinimumYCm': [float(vertices[mask, 1].min()*cm_per_unit) if mask.any() else None for mask in rig.foot_masks]})
        report['independentCPUSkinProbes']=samples
    return reopened, reports


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--semantic-map', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--world-cm-per-unit', type=float, required=True)
    parser.add_argument('--rig-review-reference', required=True)
    parser.add_argument('--fps', type=int, choices=(24, 30, 60), default=30)
    args=parser.parse_args()
    if not np.isfinite(args.world_cm_per_unit) or args.world_cm_per_unit<=0: raise ValueError('Invalid world scale')
    destination=args.output.resolve()
    if not destination.is_relative_to(ASSETS.resolve()) or destination.exists() or destination==args.source.resolve():
        raise ValueError('Use a fresh output inside ignored Local/CustomuseAssets; source is immutable')
    source_hash=sha(args.source)
    semantic=json.loads(args.semantic_map.read_text())
    if semantic.get('rigSHA256') != source_hash: raise ValueError('Semantic map does not match source rig SHA256')
    model, reports=author(GLB(args.source), semantic, args.world_cm_per_unit, args.fps)
    if sha(args.source)!=source_hash: raise ValueError('Source rig changed during authoring; no output accepted')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(model.bytes())
    receipt={'status': 'ORIGINAL_MOTION_CANDIDATE_NATIVE_REVIEW_REQUIRED', 'sourceSHA256': source_hash,
             'authorScriptSHA256': sha(Path(__file__)),
             'semanticMapSHA256': sha(args.semantic_map), 'rigReviewReference': args.rig_review_reference,
             'outputSHA256': sha(destination), 'worldCentimetersPerSourceUnit': args.world_cm_per_unit,
             'sourceBinaryGeometryWeightsInverseBindsPreserved': True, 'clipCount': len(reports), 'clips': reports,
             'sourceStillUnchanged': sha(args.source)==source_hash, 'nativeVisualAcceptance': False,
             'probeCoordinateSpace': 'glTF world XYZ (X forward, Y up), scaled to cm before UE actor mesh translation; UE remaps XYZ to XZY',
             'constraints': ['Actor supplies horizontal travel and flight altitude; no animated horizontal root translation.',
                             'Vertical root posture must not be removed by root-motion extraction or force-root-lock.',
                             'Point IK does not prove sole contact, self-collision, skin quality or native imports.',
                             'Front foot branch lacks a dedicated shared ankle; inspect sole tilt during deep collapse.',
                             'All authored motion remains a candidate until root reviews actual native playback.']}
    destination.with_suffix('.motion.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'output': str(destination), 'sha256': receipt['outputSHA256'], 'clips': len(reports),
                      'worstIKErrorCm': max(r['maximumIKPointErrorCm'] for r in reports), 'nativeAccepted': False}))


if __name__ == '__main__':
    main()
