#!/usr/bin/env python3
"""Read-only CPU measurements of sourced locomotion; no source or acceptance edits."""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB
sources=[ROOT/'Local/AttackSources20261103/ForwardRun/Exports/Mixamo_ForwardRun_v1.glb']+[ROOT/'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports'/('Mixamo_'+n+'_v1.glb') for n in ['RunStopOneHand','RunStopTwoHand']]
parser=argparse.ArgumentParser();parser.add_argument('--contacts',action='store_true');args=parser.parse_args()
if args.contacts:sources=[ROOT/'Local/AttackSources20261103/LocomotionContacts'/(p.stem.replace('_v1','_v2contacts')+'.glb') for p in sources]
rows=[]
for p in sources:
 g=GLB(p);names={n.get('name'):i for i,n in enumerate(g.json['nodes'])};node=g.json['nodes'][g.mesh_node()];skin=g.json['skins'][node['skin']];parts=g.json['meshes'][node['mesh']]['primitives'];indices=[]
 for side in ['Left','Right']:
  joint_ids=[i for i,n in enumerate(skin['joints']) if g.json['nodes'][n].get('name') in [side+'Foot',side+'ToeBase']];mask=[]
  for part in parts:
   j=g.accessor(part['attributes']['JOINTS_0']);w=g.accessor(part['attributes']['WEIGHTS_0']);mask.extend(((np.isin(j,joint_ids)*w).sum(axis=1)>.75).tolist())
  indices.append(np.flatnonzero(mask));assert len(indices[-1])>20
 factor=244/np.ptp(g.skinned_positions()[:,1]);clip=g.json['animations'][0];end=max(float(g.accessor(s['input'])[-1,0]) for s in clip['samplers']);times=np.linspace(0,end,round(end*60)+1)
 W=np.array([g.world_matrices(0,float(t)) for t in times]);points=W[:,:,:3,3]*factor
 soles=np.array([[g.skinned_positions(0,float(t))[ix,1].min()*factor for ix in indices] for t in times]);floor=float(soles.min());net=points[-1,names['Hips']]-points[0,names['Hips']];net[1]=0
 feet=[]
 for i,side in enumerate(['Left','Right']):
  q=points[:,names[side+'Foot']];vel=np.linalg.norm(np.diff(q[:,[0,2]],axis=0),axis=1)/np.diff(times);mask=(soles[:-1,i]<floor+2.5)&(soles[1:,i]<floor+2.5);v=vel[mask]
  toe=points[:,names[side+'ToeBase']];low=(q[:,1]<=np.percentile(q[:,1],10)+2.5)&(toe[:,1]<=np.percentile(toe[:,1],10)+2.5)
  step=np.maximum(np.linalg.norm(np.diff(q[:,[0,2]],axis=0),axis=1),np.linalg.norm(np.diff(toe[:,[0,2]],axis=0),axis=1));windows=[float((step[k-1]+step[k])/(times[k+1]-times[k-1])) for k in range(1,len(step)) if low[k-1:k+2].all()]
  feet.append({'side':side,'sourceOnlyLowFootWindowMaxCmS':max(windows) if windows else None,'nearFloorSamples':int(mask.sum()),'ankleHorizontalSpeedP95CmS':float(np.percentile(v,95)) if len(v) else None,'soleRangeCm':[float(soles[:,i].min()-floor),float(soles[:,i].max()-floor)]})
 loop_nodes=[names[s+n] for s in ['Left','Right'] for n in ['Foot','ToeBase','Hand']];gaps=np.linalg.norm(points[-1,loop_nodes]-points[0,loop_nodes]-net,axis=1)
 rows.append({'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'durationSeconds':end,'heightScaleCm':float(factor),'planarHipTravelCm':net.tolist(),'feet':feet,'endpointGapAfterPlanarTravelCm':{'max':float(gaps.max()),'mean':float(gaps.mean())},'scope':'Source-only diagnostic; ankle speed includes legitimate pivots. Native foot gates and visible transitions remain required.'})
out=ROOT/'docs/master-goal-20261103'/('locomotion-contact-metrics.json' if args.contacts else 'locomotion-source-metrics.json');out.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
