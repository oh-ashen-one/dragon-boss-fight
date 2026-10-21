#!/usr/bin/env python3
"""Check exported walk stance locks, endpoint recovery, grip and joint continuity."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from author_knight_actions import sample
from author_knight_twohand_strong_review import GRIP, SOCKET, SCALE
from inspect_weapon_topology import GLB


def audit(body,idle,clip):
    g,baseg,source=GLB(clip),GLB(idle),GLB(body)
    names={n.get('name'):i for i,n in enumerate(g.json['nodes'])}
    base=baseg.world_matrices(0,0);n=len(base)
    start=g.world_matrices(0,0)[:n];end=g.world_matrices(0,3.5)[:n]
    for node in range(n):
        ancestor=node
        while ancestor in g.parents and ancestor != names['Hips']:
            ancestor=g.parents[ancestor]
        if ancestor == names['Hips']: end[node,:3,3]-=[0,0,.72]
    assert np.max(abs(start-base))<1e-6 and np.max(abs(end-base))<1e-6
    assert source.binary==g.binary[:len(source.binary)]
    rh=names['RightHand'];center=base[rh,:3,3]+base[rh,:3,:3]@GRIP
    axis=base[rh,:3,:3]@SOCKET[:,1]
    offsets={}
    for side,z in [('Right',0),('Left',-.18*SCALE)]:
        h=base[names[side+'Hand']];offsets[side]=np.linalg.solve(h[:3,:3],center+axis*z-h[:3,3])
    swings={'Left':[(.25,.73),(1.45,1.93),(2.65,3.13)],'Right':[(.85,1.33),(2.05,2.53)]}
    errors={s:0. for s in swings};palms={s:0. for s in swings};previous={};rotations={}
    min_knee=180.;max_knee=0.
    for t in np.linspace(0,3.5,421):
        w=g.world_matrices(0,float(t));p=sample(g,float(t));socket=w[names['ReviewWeaponSocket']]
        for side,z in [('Right',-.075),('Left',-.255)]:
            h=w[names[side+'Hand']];palm=h[:3,3]+h[:3,:3]@offsets[side]
            palms[side]=max(palms[side],float(np.linalg.norm(palm-(socket@np.array([0,z,0,1]))[:3])))
            stance=not any(a-1e-6<t<b+1e-6 for a,b in swings[side])
            foot=w[names[side+'Foot'],:3,3]
            if stance and previous.get(side,(False,None))[0]:
                errors[side]=max(errors[side],float(np.linalg.norm(foot-previous[side][1])))
            previous[side]=(stance,foot.copy())
            u=w[names[side+'Leg'],:3,3]-w[names[side+'UpLeg'],:3,3]
            v=foot-w[names[side+'Leg'],:3,3]
            bend=float(np.rad2deg(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))
            min_knee=min(min_knee,bend);max_knee=max(max_knee,bend)
        for (node,path),q in p.items():
            if path=='rotation':rotations.setdefault(node,[]).append(q)
    max_step=0.
    for qs in rotations.values():
        r=Rotation.from_quat(qs);max_step=max(max_step,float(np.rad2deg((r[:-1].inv()*r[1:]).magnitude()).max()))
    assert max(errors.values())<.001,errors
    assert max(palms.values())<.001,palms
    assert max_step<20,max_step
    return {'sha256':hashlib.sha256(Path(clip).read_bytes()).hexdigest(),'auditHz':120,
      'startPoseError':float(np.max(abs(start-base))),'endPoseErrorAfterRootTravel':float(np.max(abs(end-base))),
      'maximumStanceFootDriftPerFrame':errors,'maximumPalmDrift':palms,'kneeFlexionDegrees':[min_knee,max_knee],
      'maximumLocalJointStepDegrees':max_step,'sourceGeometryPreserved':True,'ownerApproved':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('body','idle','clip','report'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();report=audit(a.body,a.idle,a.clip)
    with a.report.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))
