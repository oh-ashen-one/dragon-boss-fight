#!/usr/bin/env python3
"""Read-only source diagnostics for pivots versus whole-foot translation.

Keeps the existing native60cm/s gate unchanged. A low bone-marker speed is not
the same thing as a grounded material contact; report both without accepting art.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from normalize_customuse_glb import GLB

ROOT=Path(__file__).resolve().parents[2]
scale=json.loads((ROOT/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
rows=[]
for path in sorted((ROOT/'Local/AttackSources20261104/SourcedTurnContacts').glob('*.glb')):
    g=GLB(path);nodes={n.get('name'):i for i,n in enumerate(g.json['nodes'])}
    mesh=g.json['nodes'][g.mesh_node()];skin=g.json['skins'][mesh['skin']]
    joints=[g.json['nodes'][i]['name'] for i in skin['joints']]
    bind=g.skinned_positions()*scale
    bind_bones=g.world_matrices()
    masks=[]
    for side in ['Left','Right']:
        # Autorigged heels can also carry lower-leg weights. Include that
        # influence, but restrict the region below the ankle in bind space.
        ids=[joints.index(side+'Leg'),joints.index(side+'Foot'),joints.index(side+'ToeBase')];parts=[]
        for primitive in g.json['meshes'][mesh['mesh']]['primitives']:
            a=primitive['attributes'];ji=g.accessor(a['JOINTS_0']);weights=g.accessor(a['WEIGHTS_0'])
            parts.append(np.where(np.isin(ji,ids),weights,0).sum(1)>.75)
        ankle_height=bind_bones[nodes[side+'Foot']][1,3]*scale
        foot=np.concatenate(parts)&(bind[:,1]<=ankle_height+1.);minimum=float(bind[foot,1].min())
        masks.append(np.flatnonzero(foot&(bind[:,1]<minimum+1.)))
    end=max(float(g.accessor(s['input']).max()) for s in g.json['animations'][0]['samplers'])
    times=np.linspace(0,end,round(end*120)+1)
    markers=[];soles=[[],[]]
    for t in times:
        world=g.world_matrices(0,float(t))
        markers.append([world[nodes[n]][:3,3]*scale for n in ['LeftToeBase','LeftFoot','RightToeBase','RightFoot']])
        vertices=g.skinned_positions(0,float(t))*scale
        for side in range(2):soles[side].append(vertices[masks[side]])
    markers=np.asarray(markers);soles=[np.asarray(s) for s in soles]
    low=np.quantile(markers[:,:,1],.1,axis=0)+2.5
    result=[]
    for side in range(2):
        ids=[2*side,2*side+1];planted=(markers[:,ids,1]<=low[ids]).all(1);windows=[]
        for end_index in range(4,len(times)):
            start=end_index-4
            if not planted[start:end_index+1].all():continue
            dt=times[end_index]-times[start]
            bone_delta=np.diff(markers[start:end_index+1][:,ids][:,:,[0,2]],axis=0)
            marker_speed=float(np.linalg.norm(bone_delta,axis=2).max(axis=1).sum()/dt)
            patch=soles[side][start:end_index+1]
            near_ground=(np.abs(patch[:,:,1])<=1.).all(0)
            vertex_speed=np.linalg.norm(np.diff(patch[:,:,[0,2]],axis=0),axis=2).sum(0)/dt
            candidates=np.flatnonzero(near_ground)
            support=float(vertex_speed[candidates].min()) if len(candidates) else None
            windows.append({'endSeconds':float(times[end_index]),'boneMarkerSpeedCmS':marker_speed,
                            'minimumGroundedSoleVertexSpeedCmS':support,'groundedSoleVertices':len(candidates)})
        result.append({'side':['left','right'][side],'soleVertexCount':len(masks[side]),
                       'minimumBindSoleHeightCm':float(bind[masks[side],1].min()),
                       'minimumSoleHeightCm':float(soles[side][:,:,1].min()),
                       'worstBoneMarkerWindow':max(windows,key=lambda w:w['boneMarkerSpeedCmS']) if windows else None})
    rows.append({'name':path.stem,'sourceSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'feet':result})
(ROOT/'docs/master-goal-20261103/turn-support-point-diagnostics-v2.json').write_text(json.dumps({
    'sourceOnly':True,'nativeGateChanged':False,'accepted':False,
    'scope':'Actual skinned sole vertices: combined same-side shin/foot/toe weight>0.75, below bind ankle, in the lowest1cm bind band; within1cm of native floor0 throughout a1/30s window. Includes heel skin weighted to the shin. Diagnostic only; source gaps/penetration remain failures.',
    'clips':rows},indent=2)+'\n')
print('Source sole support-point diagnostics saved')
