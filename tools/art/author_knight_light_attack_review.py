#!/usr/bin/env python3
"""Continuous one-hand overhead attack with anatomical FK arm hinges.

Approved idle supplies the bind-compatible resting pose and wrist grip.
Arm joints are authored in torso space; no endpoint IK or antipodal alignment
is used for shoulders or elbows. PCHIP channels carry velocity through the
windup, with staggered shoulder/elbow extrema so the sword keeps moving.
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
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation
from author_knight_actions import build, sample, smooth
from author_knight_stances import Rig
from author_knight_hold import unit
from inspect_weapon_topology import GLB

DURATION = 2.8
SAMPLES = 169
SOCKET_ROTATION = Rotation.from_quat([.78155554,.0047625,.01463231,-.62364586]).as_matrix()

# Each curve is continuous in position and first derivative. Intermediate
# rising/falling keys retain velocity instead of easing to a stop at each key.
CURVES = {
    'rightFlex': ([0,.30,.60,.72,.80,.91,1.04,1.84,2.4,2.8], [0,50,125,145,132,37,35,35,20,0]),
    'rightAbduct': ([0,.50,.72,.91,1.84,2.8], [0,10,15,8,8,0]),
    'rightElbow': ([0,.35,.65,.79,.91,1.84,2.8], [0,10,30,40,-20,-20,0]),
    'leftFlex': ([0,.45,.80,.94,1.84,2.8], [0,35,75,80,75,0]),
    'leftAbduct': ([0,.50,.91,1.84,2.8], [0,15,25,25,0]),
    'leftElbow': ([0,.45,.80,1.04,1.84,2.8], [0,35,65,65,60,0]),
    'pitch': ([0,.45,.72,.83,.94,1.05,1.84,2.8], [0,-3,-5,8,53,55,51,0]),
    'yaw': ([0,.40,.72,.94,1.84,2.8], [0,-8,-12,14,12,0]),
    'hipY': ([0,.40,.72,.94,1.05,1.84,2.8], [0,-.012,.008,-.095,-.10,-.095,0]),
    'hipZ': ([0,.50,.72,.94,1.84,2.8], [0,.015,.045,.13,.13,0]),
    'stepY': ([0,.35,.70,.91,1.84,2.40,2.8], [0,0,.055,0,0,.025,0]),
    'stepZ': ([0,.35,.70,.94,1.84,2.8], [0,0,.10,.19,.19,0]),
}
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



def arm_fk(r, pose, donor_world, chain, flex, abduct, bend, side):
    upper, fore, hand = chain
    spine = r.names['Spine2']
    world = r.world(pose)
    torso_delta = world[spine,:3,:3] @ donor_world[spine,:3,:3].T
    u = donor_world[fore,:3,3] - donor_world[upper,:3,3]
    f = donor_world[hand,:3,3] - donor_world[fore,:3,3]
    hinge = unit(np.cross(u,f))
    base_bend = math.degrees(math.acos(float(np.clip(unit(u)@unit(f),-1,1))))
    # Flexion cannot reverse the elbow or collapse it beyond 135 degrees.
    actual_bend = float(np.clip(base_bend+bend, 8., 135.))
    bend = actual_bend-base_bend
    shoulder = Rotation.from_euler('x',-flex,degrees=True).as_matrix() @ Rotation.from_euler('z',(-1 if side=='Right' else 1)*abduct,degrees=True).as_matrix()
    upper_rotation = torso_delta @ shoulder @ donor_world[upper,:3,:3]
    fore_rotation = torso_delta @ shoulder @ Rotation.from_rotvec(hinge*np.deg2rad(bend)).as_matrix() @ donor_world[fore,:3,:3]
    r.set_world_rotation(pose,upper,upper_rotation)
    r.set_world_rotation(pose,fore,fore_rotation)
    # Do not touch the hand: its approved local wrist and fingers follow forearm.
    return actual_bend


def write_candidate(body_path, approved_idle_path, output):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite a review clip: {output}')
    g, idle = GLB(body_path), GLB(approved_idle_path)
    if g.json['nodes'] != idle.json['nodes'] or g.json['skins'] != idle.json['skins']:
        raise ValueError('Approved idle must share exact bind skeleton')
    if g.json.get('animations') or len(idle.json.get('animations', [])) != 1:
        raise ValueError('Expected static body and one approved idle clip')
    r = setup_rig(g,idle)
    arms={s:[r.names[s+n] for n in ('Arm','ForeArm','Hand')] for s in ('Right','Left')}
    legs={s:[r.names[s+n] for n in ('UpLeg','Leg','Foot')] for s in ('Right','Left')}
    nodes=[n for c in (*arms.values(),*legs.values()) for n in c]
    curves={k:PchipInterpolator(*v) for k,v in CURVES.items()}
    times=np.unique(np.r_[np.linspace(0,DURATION,SAMPLES),*[v[0] for v in CURVES.values()]])
    poses=[]; metrics=[]
    for t in times:
        donor=sample(idle,.5*math.sin(math.pi*float(t)/DURATION)**2)
        for n in nodes:
            donor.setdefault((n,'rotation'),np.asarray(g.json['nodes'][n].get('rotation',[0,0,0,1]),dtype=float))
        hips=r.names['Hips']
        donor.setdefault((hips,'translation'),np.asarray(g.json['nodes'][hips].get('translation',[0,0,0]),dtype=float))
        pose={k:v.copy() for k,v in donor.items()}
        c={k:float(f(t)) for k,f in curves.items()}
        pose[(hips,'translation')]+=np.array([0,c['hipY'],c['hipZ']])
        for name,p,y in (('Spine',.27,.26),('Spine1',.37,.34),('Spine2',.36,.40),('Neck',-.15,-.25),('Head',-.10,-.15)):
            turn(r,pose,name,(c['pitch']*p,c['yaw']*y,0))
        dw=r.world(donor)
        feet={}; clamps={}; bends={}
        for side in ('Left','Right'):
            shift=np.array([0,c['stepY'],c['stepZ']]) if side=='Right' else np.zeros(3)
            target=dw[legs[side][2],:3,3]+shift
            feet[side]=target
            upper,knee,foot=legs[side]
            hinge=unit(np.cross(dw[knee,:3,3]-dw[upper,:3,3],dw[foot,:3,3]-dw[knee,:3,3]))
            direction=unit(target-r.world(pose)[upper,:3,3])
            pole=unit(np.cross(direction,hinge))
            result=r.limb(pose,legs[side],target,dw[foot,:3,:3],pole)
            clamps[side]=result['reachClampCm']
            low=side.lower()
            bends[side]=arm_fk(r,pose,dw,arms[side],c[low+'Flex'],c[low+'Abduct'],c[low+'Elbow'],side)
        # A single shoulder-flexion correction lands the blade on the floor;
        # elbow remains its authored hinge, wrist/grip remains untouched.
        contact=float(smooth(np.clip((t-.88)/.06,0,1)))*float(smooth(np.clip((2.2-t)/.36,0,1)))
        if contact>0:
            h=arms['Right'][2]
            def tip_height(flex):
                arm_fk(r,pose,dw,arms['Right'],flex,c['rightAbduct'],c['rightElbow'],'Right')
                w0=r.world(pose)
                return float((w0[h,:3,3]+w0[h,:3,:3]@np.array([.0616763,-.00199617,.00555098])+w0[h,:3,:3]@SOCKET_ROTATION[:,1]*(.4096359622825952*2.35))[1])-.025
            landed=brentq(tip_height,0.,90.) if tip_height(0.)*tip_height(90.)<0 else c['rightFlex']
            arm_fk(r,pose,dw,arms['Right'],c['rightFlex']*(1-contact)+landed*contact,c['rightAbduct'],c['rightElbow'],'Right')
        if t==0 or t==DURATION:
            pose={k:v.copy() for k,v in donor.items()}
        w=r.world(pose); hand=arms['Right'][2]
        axis=w[hand,:3,:3]@SOCKET_ROTATION[:,1]
        tip=w[hand,:3,3]+w[hand,:3,:3]@np.array([.0616763,-.00199617,.00555098])+axis*(.4096359622825952*2.35)
        metrics.append({'seconds':float(t),'hand':w[hand,:3,3].tolist(),'freeHand':w[arms['Left'][2],:3,3].tolist(),'head':w[r.names['Head'],:3,3].tolist(),'swordAxis':axis.tolist(),'swordTip':tip.tolist(),'elbowFlexDegrees':bends,'footTargetError':max(np.linalg.norm(w[legs[s][2],:3,3]-feet[s]) for s in feet),'reachClampCm':max(clamps.values())})
        poses.append(pose)
    if any(set(p)!=set(poses[0]) for p in poses): raise ValueError('Track set changes')
    if any(not np.allclose(poses[0][k],poses[-1][k],atol=1e-6) for k in poses[0]): raise ValueError('Loop differs')
    if max(m['footTargetError'] for m in metrics)>.012 or max(m['reachClampCm'] for m in metrics)>2.:
        raise ValueError('Foot target or leg reach failed')
    for side in arms:
        hand=arms[side][2]
        if any(not np.allclose(p[(hand,'rotation')],poses[0][(hand,'rotation')],atol=1e-6) for p in poses):
            raise ValueError('Approved local wrist grip changed')
    result=build(g,poses,times,'LightAttack_BlackKnightReference_v10')
    if result.binary[:len(g.binary)]!=g.binary or any(result.json.get(k)!=g.json.get(k) for k in ('nodes','skins','meshes','materials','textures','images')): raise ValueError('Bind or geometry changed')
    error=max(float(np.abs(result.world_matrices(0,float(t))-r.world(p)).max()) for t,p in zip(times,poses))
    if error>1e-5: raise ValueError('Export mismatch')
    # Report angular speeds on baked local channels, including elbow and wrist.
    speeds={}
    for n in nodes:
        q=Rotation.from_quat([p[(n,'rotation')] for p in poses])
        speeds[g.json['nodes'][n]['name']]=float(np.max((q[:-1].inv()*q[1:]).magnitude()/np.diff(times))*180/math.pi)
    output.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f: f.write(result.bytes())
    return {'bodySourceSha256':hashlib.sha256(body_path.read_bytes()).hexdigest(),'approvedIdleSha256':hashlib.sha256(approved_idle_path.read_bytes()).hexdigest(),'outputSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'durationSeconds':DURATION,'sampleCount':len(times),'maximumExportMatrixError':error,'maximumFootTargetErrorRigUnits':max(m['footTargetError'] for m in metrics),'maximumReachClampCm':max(m['reachClampCm'] for m in metrics),'maximumLocalAngularSpeedDegreesPerSecond':speeds,'startAndEndMatchApprovedIdle':True,'sourceGeometryAndBindDataPreserved':True,'anatomy':'Torso-relative shoulder flexion and abduction; one-axis elbow hinge 8..135 degrees; unchanged local wrist.','nativeUnrealReview':False,'keyMoments':{str(t):min(metrics,key=lambda m:abs(m['seconds']-t)) for t in (0,.3,.6,.72,.8,.85,.91,1.04,1.84,DURATION)}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body',required=True,type=Path)
    parser.add_argument('--approved-idle',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    print(json.dumps(write_candidate(a.body,a.approved_idle,a.output),indent=2))

if __name__=='__main__':main()
