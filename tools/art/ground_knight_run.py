#!/usr/bin/env python3
"""Bounded Run grounding: exact rotation keys and horizontal pose preserved.

Extracts only approved source2.6..3.2s into one full-file loop. A periodic,
nonnegative majorant corrects whole-foot surface penetration through root Y.
Existing rotational seam is measured, never silently reauthored. Native runtime
wrap blending owns that residual. No geometry, weights, rest, engine or paid ops.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from inspect_weapon_topology import GLB, ASSETS, primitive
from author_knight_actions import append


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ground_run(source,output):
    if output.exists() or output.with_suffix('.run-grounding.json').exists():raise ValueError('Fresh output required')
    raw=source.read_bytes();g=GLB(raw);clip=g.json['animations'][0];roots=[i for i,n in enumerate(g.json['nodes']) if n.get('name')=='Hips']
    if len(roots)!=1:raise ValueError('One Hips root required')
    root=roots[0];root_channels=[c for c in clip['channels'] if c['target']['node']==root and c['target']['path']=='translation']
    if len(root_channels)!=1:raise ValueError('Expected one root translation track')
    s=clip['samplers'][root_channels[0]['sampler']];original_times=g.accessor(s['input']).reshape(-1).copy();first=int(np.argmin(abs(original_times-2.6)));last=int(np.argmin(abs(original_times-3.2)));start=float(original_times[first]);end=float(original_times[last]);duration=end-start
    if abs(start-2.6)>1e-5 or abs(end-3.2)>1e-5:raise ValueError('Requested trim does not land on exact source keys')
    _,p,_,_=primitive(g);J=g.accessor(p['attributes']['JOINTS_0']);W=g.accessor(p['attributes']['WEIGHTS_0']);feet=np.flatnonzero((np.isin(J,[46,47,50,51])*W).sum(1)>=.5)
    if len(feet)<500:raise ValueError('Whole-foot selection unexpectedly small')
    factor=244/np.ptp(g.skinned_positions()[:,1]);samples=np.linspace(0,duration,round(duration*120)+1);source_world=[g.world_matrices(0,float(t+start)) for t in samples];source_y=np.array([w[root,1,3] for w in source_world]);source_sole=np.array([g.skinned_positions(0,float(t+start))[feet,1].min() for t in samples]);phase=samples/duration;periodic_drift=-(source_y[-1]-source_y[0])*(phase*phase*(3-2*phase));margin=.5/factor;need=np.maximum(0,margin-source_sole-periodic_drift)
    # Dilation then positive-weight smoothing majorizes every required lift sample.
    # Every dilated neighbor in the smoothing window contains the center sample.
    periodic=need[:-1].copy();periodic[0]=max(periodic[0],need[-1]);radius=3;dilated=np.maximum.reduce([np.roll(periodic,k) for k in range(-radius,radius+1)]);weights=np.array([1,2,3,4,3,2,1],float)/16;smoothed=sum(weight*np.roll(dilated,k) for weight,k in zip(weights,range(-radius,radius+1)));lift=np.r_[smoothed,smoothed[0]];delta=periodic_drift+lift
    if np.any(lift+1e-12<need):raise ValueError('Grounding envelope does not majorize required lift')
    parent=g.parents.get(root);parent_world=g.world_matrices()[parent] if parent is not None else np.eye(4)
    if parent is not None and any(c['target']['node']==parent for c in clip['channels']):raise ValueError('Animated root parent unsupported')
    values=g.accessor(s['output']).copy();local=np.column_stack([np.interp(samples+start,original_times,values[:,axis]) for axis in range(3)]);local+=delta[:,None]*(np.linalg.inv(parent_world[:3,:3])@np.array([0.,1.,0.]))
    d=GLB(g.bytes());anim={'name':'Veyr_Run_Grounded','samplers':[],'channels':[]};rotation_proof=[]
    for c in clip['channels']:
        sampler=clip['samplers'][c['sampler']];key=c['target'];times=g.accessor(sampler['input']).reshape(-1).copy();data=g.accessor(sampler['output']).copy();i=int(np.argmin(abs(times-start)));j=int(np.argmin(abs(times-end)))
        if abs(float(times[i])-start)>1e-5 or abs(float(times[j])-end)>1e-5:raise ValueError('Track trim keys differ')
        if key['node']==root and key['path']=='translation':new_times=samples;new_data=local
        else:
            new_times=times[i:j+1]-np.float32(start);new_data=data[i:j+1].copy()
            if key['path']=='rotation':rotation_proof.append({'node':int(key['node']),'firstOriginalKey':i,'lastOriginalKey':j,'outputValuesSHA256':hashlib.sha256(new_data.tobytes()).hexdigest()})
        ti=append(d,np.asarray(new_times)[:,None],'SCALAR');oi=append(d,new_data,'VEC4' if key['path']=='rotation' else 'VEC3');si=len(anim['samplers']);anim['samplers'].append({'input':ti,'output':oi,'interpolation':sampler.get('interpolation','LINEAR')});anim['channels'].append({'sampler':si,'target':copy.deepcopy(key)})
    d.json['animations']=[anim];derived=GLB(d.bytes())
    if bytes(derived.binary[:len(g.binary)])!=bytes(g.binary) or not np.array_equal(g.skinned_positions(),derived.skinned_positions()):raise ValueError('Geometry/skin/rest changed')
    # Dense validation covers quaternion-interpolated extrema between source keys.
    checks=[];max_rotation=0.;max_horizontal=0.;minimum=float('inf')
    for time in np.linspace(0,duration,round(duration*480)+1):
        oldW=g.world_matrices(0,float(time+start));newW=derived.world_matrices(0,float(time));old=g.skinned_positions(0,float(time+start));new=derived.skinned_positions(0,float(time));rotation_error=float(np.abs(oldW[:,:3,:3]-newW[:,:3,:3]).max());horizontal=float(np.abs(old[:,[0,2]]-new[:,[0,2]]).max());sole=float(new[feet,1].min()*factor);minimum=min(minimum,sole);max_rotation=max(max_rotation,rotation_error);max_horizontal=max(max_horizontal,horizontal)
        if rotation_error>2e-6 or horizontal>2e-6 or not np.all(np.isfinite(new)):raise ValueError('Nonvertical pose data changed')
        checks.append({'seconds':float(time),'wholeSoleMinYcm':sole,'worldRootYcm':float(newW[root,1,3]*factor)})
    if minimum<-.05:raise ValueError('Dense sole penetration remains')
    begin=derived.world_matrices(0,0);finish=derived.world_matrices(0,duration);oldbegin=g.world_matrices(0,start);oldfinish=g.world_matrices(0,end);endpoint=float(np.linalg.norm(begin[:,:3,3]-finish[:,:3,3],axis=1).max()*factor);rootgap=float(abs(begin[root,1,3]-finish[root,1,3])*factor)
    if rootgap>.001:raise ValueError('Root vertical loop seam remains')
    # Recheck copied quaternion outputs bit-for-bit against the original trimmed keys.
    for c in anim['channels']:
        if c['target']['path']!='rotation':continue
        row=next(r for r in rotation_proof if r['node']==c['target']['node']);actual=derived.accessor(anim['samplers'][c['sampler']]['output'])
        if hashlib.sha256(actual.tobytes()).hexdigest()!=row['outputValuesSHA256']:raise ValueError('Rotation values changed')
    payload=derived.bytes();report={'status':'ROOT_Y_ONLY_RUN_GROUNDING_CPU_VERIFIED_NATIVE_PENDING','source':source.name,'sourceSHA256':sha(source),'output':output.name,'outputSHA256':hashlib.sha256(payload).hexdigest(),'sourceWindowSeconds':[start,end],'durationSeconds':duration,'trimPolicy':'Full output0..duration; source rotation keys copied exactly. Runtime0.12s wrap blend handles existing rotational seam.','wholeFootVertexCount':len(feet),'wholeFootSelection':'All actual skinned mesh vertices with majority combined Foot/Toe influence, including both full heel/toe surfaces; no joint-point or single-vertex proxy.','sourceWholeSoleMinCm':float(source_sole.min()*factor),'finalWholeSoleMinimumCm':minimum,'rootYCorrectionRangeCm':[float(delta.min()*factor),float(delta.max()*factor)],'nonnegativeLiftRangeCm':[float(lift.min()*factor),float(lift.max()*factor)],'sourceRootYEndpointDriftCm':float((source_y[-1]-source_y[0])*factor),'finalRootYEndpointGapCm':rootgap,'remainingAllJointEndpointGapCm':endpoint,'originalAllJointEndpointGapCm':float(np.linalg.norm(oldbegin[:,:3,3]-oldfinish[:,:3,3],axis=1).max()*factor),'rotationValuesBitwisePreserved':True,'rotationMatrixMaxDifference':max_rotation,'worldHorizontalSkinMaxDifferenceCm':max_horizontal*factor,'geometryWeightsRestSafeHoldPreserved':True,'nominalSurfaceSpeedCmS':822.809855272621,'nominalSpeedPolicy':'Unchanged horizontal sole paths and exact rotations; vertical contact eligibility can shift, so native speed remains provisional.','samples':checks,'rotationProof':rotation_proof,'nativeAccepted':False}
    if sha(source)!=report['sourceSHA256']:raise ValueError('Source changed')
    output.write_bytes(payload);output.with_suffix('.run-grounding.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['durationSeconds','sourceWholeSoleMinCm','finalWholeSoleMinimumCm','rootYCorrectionRangeCm','finalRootYEndpointGapCm','remainingAllJointEndpointGapCm','rotationValuesBitwisePreserved','worldHorizontalSkinMaxDifferenceCm']},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.source.resolve().is_relative_to(ASSETS.resolve()) or a.output.resolve().parent!=ASSETS.resolve():raise ValueError('Private task assets only')
    ground_run(a.source,a.output)


if __name__=='__main__':main()
