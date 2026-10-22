"""COPY of rebuild/audit_set.py for the Elden Ring A/B *_Blender_v2 remasters (per-clip; thresholds unchanged).
Reads <out>/er_v2/<job>_Blender_v1.glb (delivered as <Review>_Blender_v2.glb). Usage: audit_er.py job [job...]"""
import sys,json,importlib.util
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

REPO=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('evaluator',REPO/'tools/unreal/normalize_customuse_glb.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import os
ROOT=REPO/'Local/Blender/feedback-v4-20261021'/os.environ.get('ER_SUB','er_v2')
JOBS=sys.argv[1:]
results=[]
for p in [ROOT/(j+'-report.json') for j in JOBS]:
 report=json.loads(p.read_text());job=report['job'];g=mod.GLB(ROOT/(job+'_Blender_v1.glb'));old=mod.GLB(REPO/'tools/asset-review/.asset-cache/review'/(report['source']+'.glb'))
 names={n.get('name'):i for i,n in enumerate(g.json['nodes'])};oldnames={n.get('name'):i for i,n in enumerate(old.json['nodes'])}
 duration=max(float(g.accessor(s['input']).max()) for s in g.json['animations'][0]['samplers'])
 endpoint=0.;loop=0.;maxstep=0.;palms={'Right':0.,'Left':0.};lengthchange=0.
 first=g.world_matrices(0,0);last=g.world_matrices(0,duration)
 joints=[n for n in names if n in oldnames and n in ('Hips','Spine','Spine1','Spine2','Head','LeftHand','RightHand','LeftFoot','RightFoot')]
 for t in (0,duration):
  a=g.world_matrices(0,t);b=old.world_matrices(0,t)
  endpoint=max(endpoint,max(float(np.linalg.norm(a[names[n],:3,3]-b[oldnames[n],:3,3])) for n in joints))
 loop=max(float(np.max(np.abs(first[names[n]]-last[names[n]]))) for n in joints)
 socket=names['ReviewWeaponSocket']
 contacts={s:np.linalg.solve(first[names[s+'Hand']],first[socket]@np.array([0,y,0,1])) for s,y in [('Right',-.075),('Left',-.255)]}
 bones=[(s+a,s+b) for s in ('Left','Right') for a,b in [('Arm','ForeArm'),('ForeArm','Hand'),('UpLeg','Leg'),('Leg','Foot')]]
 lengths={(a,b):np.linalg.norm(first[names[a],:3,3]-first[names[b],:3,3]) for a,b in bones}
 for t in np.linspace(0,duration,round(duration*120)+1):
  w=g.world_matrices(0,float(t));assert np.isfinite(w).all()
  for a,b in bones:lengthchange=max(lengthchange,abs(float(np.linalg.norm(w[names[a],:3,3]-w[names[b],:3,3]))-lengths[a,b]))
  for s,y in [('Right',-.075),('Left',-.255)]:
   if s=='Left' and job in ('idle_one','overhead'):continue
   palms[s]=max(palms[s],float(np.linalg.norm((w[names[s+'Hand']]@contacts[s]-w[socket]@np.array([0,y,0,1]))[:3])))
 for channel in g.json['animations'][0]['channels']:
  if channel['target']['path']=='rotation':
   sm=g.json['animations'][0]['samplers'][channel['sampler']];r=Rotation.from_quat(g.accessor(sm['output']))
   maxstep=max(maxstep,float(np.rad2deg((r[:-1].inv()*r[1:]).magnitude()).max()))
 row={'job':job,'duration':duration,'durationError':abs(duration-report['duration']),'endpointJointPositionError':endpoint,'loopMatrixError':loop,'maximumLimbLengthChange':lengthchange,'maximumPalmDrift':palms,'maxRotationStepDegrees':maxstep,'nativeIKError':report['nativeIKError'],'samplesHz':120}
 if job in ('idle_one','overhead'):row['leftHandIsFree']=True
 row['pass']=row['durationError']<1e-5 and endpoint<1e-4 and lengthchange<.002 and max(palms.values())<.003 and maxstep<40 and report['nativeIKError']<.001
 results.append(row)
(ROOT/('export-audit-'+'-'.join(JOBS)+'.json')).write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
sys.exit(0 if all(r['pass'] for r in results) else 1)
