"""Independent glTF playback audit after Blender changes the joint basis."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

def audit(evaluator, clip):
    spec=importlib.util.spec_from_file_location('glb_audit',evaluator)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    g=mod.GLB(clip);names={n.get('name'):i for i,n in enumerate(g.json['nodes'])}
    base=g.world_matrices(0,0);socket_id=names['ReviewWeaponSocket']
    contacts={side:np.linalg.solve(base[names[side+'Hand']],base[socket_id]@np.array([0,y,0,1])) for side,y in [('Right',-.075),('Left',-.255)]}
    palms={s:0. for s in contacts};feet={s:0. for s in contacts};previous={}
    swings={'Left':[(.25,.73),(1.45,1.93),(2.65,3.13)],'Right':[(.85,1.33),(2.05,2.53)]}
    joint_positions=[]
    for t in np.linspace(0,3.5,421):
        w=g.world_matrices(0,float(t));joint_positions.append(w[:,:3,3])
        for side,y in [('Right',-.075),('Left',-.255)]:
            palm=w[names[side+'Hand']]@contacts[side]
            palms[side]=max(palms[side],float(np.linalg.norm((palm-w[socket_id]@np.array([0,y,0,1]))[:3])))
            # Exclude the 60fps export's samples straddling a stance boundary.
            stance=not any(a-.02<t<b+.02 for a,b in swings[side])
            foot=w[names[side+'Foot'],:3,3]
            if stance and previous.get(side,(False,None))[0]:feet[side]=max(feet[side],float(np.linalg.norm(foot-previous[side][1])))
            previous[side]=(stance,foot.copy())
    max_step=0.
    for channel in g.json['animations'][0]['channels']:
        if channel['target']['path']!='rotation':continue
        sampler=g.json['animations'][0]['samplers'][channel['sampler']]
        r=Rotation.from_quat(g.accessor(sampler['output']))
        max_step=max(max_step,float(np.rad2deg((r[:-1].inv()*r[1:]).magnitude()).max()))
    assert max(palms.values())<.001,palms
    assert max(feet.values())<.001,feet
    assert max_step<20,max_step
    return {'sha256':hashlib.sha256(Path(clip).read_bytes()).hexdigest(),'auditHz':120,'maximumPalmDrift':palms,'maximumStanceFootFrameDrift':feet,'maximumLocalJointStepDegreesAt60Hz':max_step,'ownerApproved':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evaluator',required=True);p.add_argument('--clip',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();r=audit(a.evaluator,a.clip);Path(a.report).write_text(json.dumps(r,indent=2));print(json.dumps(r))
