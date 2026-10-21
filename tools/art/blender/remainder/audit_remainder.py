"""Independent GLB checks; verification only, no animation authoring."""
from pathlib import Path
import importlib.util,json,sys,hashlib
import numpy as np
from scipy.spatial.transform import Rotation
REPO=Path(__file__).resolve().parents[4];ROOT=REPO/'Local/Blender/remainder-20261021'
spec=importlib.util.spec_from_file_location('glb_eval',REPO/'tools/unreal/normalize_customuse_glb.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
meta=json.loads((REPO/'tools/asset-review/remainder-catalog.json').read_text())['clips'];results=[]
approved=m.GLB(REPO/'tools/asset-review/.asset-cache/review/IdleOneHand_Blender_v1.glb')
def body_indices(g):
 node=next(n for n in g.json['nodes'] if 'mesh' in n and 'skin' in n)
 return sum(len(g.accessor(p['indices'])) for p in g.json['meshes'][node['mesh']]['primitives'])
expected_indices=body_indices(approved)
for item in meta:
 job=item['job'];report=json.loads((ROOT/(job+'-report.json')).read_text());p=ROOT/(job+'_Blender_v1.glb');g=m.GLB(p)
 ns={n.get('name'):i for i,n in enumerate(g.json['nodes'])};animation=g.json['animations'][0]
 duration=max(float(g.accessor(s['input']).max()) for s in animation['samplers']);first=g.world_matrices(0,0);last=g.world_matrices(0,duration)
 joints=[ns[n] for n in ('Hips','LeftFoot','RightFoot','LeftHand','RightHand','Head')]
 loop=float(np.max(np.abs(first[joints]-last[joints])))
 lengths={};length_error=0.;palm={'Right':0.};foot={'Left':0.,'Right':0.};step=0.
 if job in ('guard_two','walk_two'):palm['Left']=0.
 socket=ns['ReviewWeaponSocket'];contact={side:np.linalg.solve(first[ns[side+'Hand']],first[socket]@np.array([0,-.075 if side=='Right' else -.255,0,1])) for side in palm}
 for side in ('Left','Right'):
  for a,b in [('Arm','ForeArm'),('ForeArm','Hand'),('UpLeg','Leg'),('Leg','Foot')]:
   na,nb=ns[side+a],ns[side+b];lengths[na,nb]=np.linalg.norm(first[na,:3,3]-first[nb,:3,3])
 for t in np.linspace(0,duration,round(duration*120)+1):
  w=g.world_matrices(0,float(t));assert np.isfinite(w).all()
  for (a,b),length in lengths.items():length_error=max(length_error,abs(float(np.linalg.norm(w[a,:3,3]-w[b,:3,3]))-length))
  if job!='death' or t<duration*.28:
   for side in palm:
    point=w[socket]@np.array([0,-.075 if side=='Right' else -.255,0,1]);palm[side]=max(palm[side],float(np.linalg.norm((w[ns[side+'Hand']]@contact[side]-point)[:3])))
  if job in ('guard','guard_two'):
   for side in foot:foot[side]=max(foot[side],float(np.linalg.norm(w[ns[side+'Foot'],:3,3]-first[ns[side+'Foot'],:3,3])))
 for c in animation['channels']:
  if c['target']['path']=='rotation':
   a=g.accessor(animation['samplers'][c['sampler']]['output']);r=Rotation.from_quat(a);step=max(step,float(np.rad2deg((r[:-1].inv()*r[1:]).magnitude()).max()))
 result={'job':job,'file':item['file'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'duration':duration,'durationError':abs(duration-report['duration']),'closedLoopExpected':item['previewLoop'],'loopMatrixError':loop,'nativeIKError':report['nativeIKError'],'maxLimbLengthChange':length_error,'maxPalmDrift':palm,'guardFootDrift':foot if job in ('guard','guard_two') else None,'maxExportRotationStepDegrees':step,'bodyTriangleIndices':body_indices(g),'approvedBodyTriangleIndices':expected_indices,'ownerApproved':False,'auditHz':120}
 result['pass']=result['durationError']<1e-5 and (job in ('death','walk_two') or loop<1e-4) and report['nativeIKError']<.001 and length_error<.002 and max(palm.values())<.003 and step<40 and result['bodyTriangleIndices']==expected_indices and max(foot.values())<.001
 results.append(result)
(ROOT/'export-audit.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));sys.exit(0 if all(r['pass'] for r in results) else 1)
