#!/usr/bin/env python3
"""Grounded start/walk/stop study from the approved two-hand ready pose.

Root motion is baked. Each stance foot is fixed in world space; only its
scheduled swing advances. No original mesh, skeleton, skin or clip is edited.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation
from author_knight_actions import build
from author_knight_light_attack_review import setup_rig, turn
from author_knight_twohand_strong_review import solve_leg, solve_arm, fit_weapon, hand_target, GRIP, SOCKET, SCALE
from inspect_weapon_topology import GLB

DURATION = 3.5
# side, liftoff, touchdown, destination forward offset, stance width
STEPS = [('Left', .25, .73, .18, .09), ('Right', .85, 1.33, .36, -.09),
         ('Left', 1.45, 1.93, .54, .09), ('Right', 2.05, 2.53, .72, None),
         ('Left', 2.65, 3.13, .72, None)]
ROOT = PchipInterpolator([0,.15,.73,1.33,1.93,2.53,3.13,DURATION],
                         [0,0,.09,.27,.45,.63,.72,.72])


def ease(u):
    return u*u*u*(10+u*(-15+6*u))


def foot_at(side, t, base):
    target = base.copy(); pitch = 0.; swinging = False
    for limb, start, end, z, x in STEPS:
        if limb != side or t <= start: continue
        dest = base.copy(); dest[2] += z
        if x is not None: dest[0] = x
        if t >= end:
            target = dest
        else:
            u = (t-start)/(end-start)
            target = target+(dest-target)*ease(u)
            target[1] += .048*math.sin(math.pi*u)**2
            pitch = 9*math.sin(2*math.pi*u)*math.sin(math.pi*u)
            swinging = True
            break
    return target, pitch, swinging


def author(body, idle, output):
    g, donor = GLB(body), GLB(idle)
    r = setup_rig(g, donor)
    pose0 = {k:v.copy() for k,v in r.base.items()}
    hips = r.names['Hips']; rh = r.names['RightHand']
    legs = {s:[r.names[s+n] for n in ('UpLeg','Leg','Foot')] for s in ('Left','Right')}
    for chain in legs.values():
        for n in chain: pose0.setdefault((n,'rotation'), np.array(g.json['nodes'][n].get('rotation',[0,0,0,1]),float))
    base = r.world(pose0)
    chains={side:[r.names[side+n] for n in ('Arm','ForeArm','Hand')] for side in ('Right','Left')}
    chest=r.names['Spine2']
    grip0=base[rh,:3,3]+base[rh,:3,:3]@GRIP
    arm_states={side:{} for side in chains}; fit_state=np.zeros(4)
    max_wrist=0.;max_grip=0.
    times = np.unique(np.r_[np.linspace(0,DURATION,round(DURATION*120)+1),np.array(STEPS,dtype=object)[:,1:3].astype(float).ravel()])
    poses=[]; max_foot_error=0.; stance_frames=0
    for t in times:
        p={k:v.copy() for k,v in pose0.items()}
        envelope = ease(min(1,t/.45))*ease(min(1,(DURATION-t)/.45))
        sway=0.; bob=0.; yaw=0.
        for side,start,end,_,_ in STEPS:
            u=(t-start)/(end-start)
            if 0<u<1:
                pulse=math.sin(math.pi*u)**2
                sway=(-.034 if side=='Left' else .034)*pulse
                bob=.017*pulse
                yaw=(5 if side=='Left' else -5)*math.sin(math.pi*u)
        breath=math.sin(2*math.pi*t/1.8)*envelope
        # Load the body forward, with pelvis/chest counter-rotation and a
        # slower breathing layer. The arms follow one shared, moving hilt.
        p[(hips,'translation')] += [sway,(-.024+bob)*envelope+.003*breath,float(ROOT(t))]
        turn(r,p,'Hips',(2.5*envelope,yaw,-sway*24))
        turn(r,p,'Spine',((3.5+1.1*breath)*envelope,-yaw*.7,-sway*34))
        turn(r,p,'Spine1',((3.0+.8*breath)*envelope,-yaw*.7,-sway*25))
        turn(r,p,'Spine2',((2.5+.9*breath)*envelope,-yaw*.5,-sway*22))
        turn(r,p,'Neck',(-5*envelope,yaw*.15,sway*20))
        turn(r,p,'Head',(-2*envelope,0,0))
        for side,sign in [('Left',1),('Right',-1)]:
            if side+'Shoulder' in r.names:
                turn(r,p,side+'Shoulder',(0,-sign*5*envelope,sign*(2.5+1.5*breath)*envelope))
        w=r.world(p);torso=w[chest,:3,:3]@base[chest,:3,:3].T
        center=w[chest,:3,3]+torso@(grip0-base[chest,:3,3]+np.array([.012*math.sin(2*math.pi*t/1.2)*envelope,.008*breath,-.012*envelope]))
        weapon=torso@Rotation.from_euler('yx',[-7*envelope+2.5*math.sin(2*math.pi*t/1.2)*envelope,3*breath],degrees=True).as_matrix()
        center,weapon,fit_state=fit_weapon(r,p,chains,base,grip0,center,weapon,torso,fit_state)
        for side,chain in chains.items():
            target,desired=hand_target(base,chains,grip0,center,weapon,side,0)
            info=solve_arm(r,p,chain,target,desired,arm_states[side])
            max_wrist=max(max_wrist,info['wristDeltaDegrees'])
            max_grip=max(max_grip,float(np.linalg.norm(r.world(p)[chain[2],:3,3]-target)))
        for side,chain in legs.items():
            target,pitch,swing=foot_at(side,float(t),base[chain[2],:3,3])
            solve_leg(r,p,chain,base,target,0)
            if pitch:
                desired=Rotation.from_euler('x',pitch,degrees=True).as_matrix()@base[chain[2],:3,:3]
                r.set_world_rotation(p,chain[2],desired)
            max_foot_error=max(max_foot_error,float(np.linalg.norm(r.world(p)[chain[2],:3,3]-target)))
            stance_frames+=int(not swing)
        if t==0 or t==DURATION:
            p={k:v.copy() for k,v in pose0.items()}
            p[(hips,'translation')][2]+=float(ROOT(t))
        w=r.world(p)
        grip=w[rh,:3,3]+w[rh,:3,:3]@GRIP
        p[(len(g.json['nodes']),'translation')]=grip+w[rh,:3,:3]@SOCKET[:,1]*(.075*SCALE)
        p[(len(g.json['nodes']),'rotation')]=Rotation.from_matrix(w[rh,:3,:3]@SOCKET).as_quat()
        poses.append(p)
    source=GLB(g.bytes())
    source.json['nodes'].append({'name':'ReviewWeaponSocket','scale':[SCALE]*3})
    source.json['scenes'][source.json.get('scene',0)]['nodes'].append(len(g.json['nodes']))
    result=build(source,poses,times,output.stem)
    assert result.binary[:len(g.binary)]==g.binary
    assert result.json['nodes'][:len(g.json['nodes'])]==g.json['nodes']
    assert all(result.json[k]==g.json[k] for k in ('skins','meshes','materials'))
    error=max(float(np.abs(result.world_matrices(0,float(t))[:len(g.json['nodes'])]-r.world(p)).max()) for t,p in zip(times,poses))
    assert max_foot_error<1e-6 and error<1e-5 and max_grip<1e-6 and max_wrist<35
    with output.open('xb') as f:f.write(result.bytes())
    return {'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'durationSeconds':DURATION,
            'sampleCount':len(times),'rootTravelRigUnits':.72,'steps':len(STEPS),
            'maximumFootTargetError':max_foot_error,'exportMatrixError':error,
            'maximumWristDeviationDegrees':max_wrist,'maximumHandTargetError':max_grip,
            'stanceSamples':stance_frames,'meshSkinBindPreserved':True,'ownerApproved':False,
            'approvedIdleSHA256':hashlib.sha256(idle.read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('body','idle','output','report'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();report=author(a.body,a.idle,a.output)
    with a.report.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))
