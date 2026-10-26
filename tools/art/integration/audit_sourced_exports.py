#!/usr/bin/env python3
"""Audit the actual GLB sampler used by runtime, independent of DCC reimport."""
import json,math
from pathlib import Path
import numpy as np
from normalize_approved import GLB
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'Local/FabRigTesting'
FILES=['Mixamo_Walk_v17','Mixamo_WalkTwoHand_v17','Fab_RunOneHand_v18','Fab_Run_v17','Mixamo_Attack_v17','Fab_Roll_v17']
BONES=['VeyrRoot','Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder','LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase','RightUpLeg','RightLeg','RightFoot','RightToeBase']
def audit(name):
 p=OUT/'Exports'/(name+'.glb');row=json.loads(p.with_suffix('.json').read_text());clip=GLB(p)
 raw_name='Mixamo_Walk_v1' if 'Walk' in name else 'Fab_Run_v1' if 'Run' in name else name.rsplit('_v',1)[0]+'_v1';raw=GLB(OUT/'Exports'/(raw_name+'.glb'));source_fps=row.get('sourceFPS',row['fps']);body=0
 for time in np.linspace(0,clip.duration(),round(clip.duration()*source_fps)+1):
  a,_=clip.sample(time);b,_=raw.sample(time);body=max(body,max(float(np.max(np.abs(a[clip.names[n]]-b[raw.names[n]]))) for n in BONES))
 held=['Right','Left'] if row['gripMode']=='two-handed' else ['Right'];initial={};drift={s:0. for s in held};previous=None;angle=0
 for time in np.linspace(0,clip.duration(),round(clip.duration()*row['fps']*2)+1):
  pose,_=clip.sample(time);h=pose[clip.names['WeaponSocket']]
  for side in held:
   rel=np.linalg.inv(h)@pose[clip.names[side+'Hand']]
   if side not in initial:initial[side]=rel.copy()
   drift[side]=max(drift[side],float(np.linalg.norm(h[:3,:3]@(rel[:3,3]-initial[side][:3,3]))))
 assert body<1e-4,(name,body)
 assert max(drift.values())<.002,(name,drift)
 return {'name':name,'sha256':clip.sha,'duration':clip.duration(),'bakeFPS':row['fps'],'sourceFPS':source_fps,'sourceBodyKeyframeMaxMatrixDelta':body,'maxPalmDriftSceneUnits':drift,'actualGLBSampler':True}
if __name__=='__main__':
 rows=[]
 for name in FILES:
  result=audit(name);rows.append(result);print(json.dumps(result),flush=True)
 (OUT/'Evidence/final-export-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
