"""Compare native sampled local bone transforms and morph curves to exact GLB input."""
from pathlib import Path
import argparse,json,re
import numpy as np
from scipy.spatial.transform import Rotation
from normalize_approved import GLB,UE

def run(root,plan_dir=None,label=""):
 plan_dir=plan_dir or root/"Local/CustomuseAssets/Integration20261025b"
 suffix=("-"+label) if label else ""
 conversion=np.eye(4);conversion[:3,:3]=UE
 rows=[];coverage_errors=[]
 for character in ['KnightB','DragonV3B']:
  plan=json.loads((plan_dir/('import-plan-'+character+'.json')).read_text());version=plan['version'];clips={c['name']:c for c in plan['clips']};proof=json.loads((root/'Local/CustomuseImports'/('native-pose-proof-'+character+'-'+version+'.json')).read_text());cache={};metrics={}
  expected_clips=set(clips);observed_clips={f['clip'] for f in proof['samples']}
  if observed_clips!=expected_clips:coverage_errors.append({'character':character,'missingClips':sorted(expected_clips-observed_clips),'unexpectedClips':sorted(observed_clips-expected_clips)})
  for frame in proof['samples']:
   name=frame['clip'];c=clips[name];path=c['file']
   if path not in cache:cache[path]=GLB(path)
   g=cache[path];world,weights=g.sample(frame['sequenceSeconds']);mapping={re.sub('[^a-zA-Z0-9_]','_',n):i for n,i in g.names.items()};row=metrics.setdefault(name,{'clip':name,'maxPositionErrorCm':0.,'maxRotationErrorDegrees':0.,'maxScaleError':0.,'maxMorphWeightError':0.,'samples':0})
   expected_bones={re.sub('[^a-zA-Z0-9_]','_',n) for n in g.skin_names()}
   if set(frame['pose'])!=expected_bones:coverage_errors.append({'character':character,'clip':name,'missingBones':sorted(expected_bones-set(frame['pose'])),'unexpectedBones':sorted(set(frame['pose'])-expected_bones)})
   for bone,value in frame['pose'].items():
    i=mapping[bone];parent=g.parents.get(i);local=world[i] if parent is None else np.linalg.inv(world[parent])@world[i];expected=conversion@local@conversion;expected[:3,3]*=100
    actual_scale=np.array(value['scale']);actual_rotation=Rotation.from_quat(value['rotation']).as_matrix();expected_scale=np.linalg.norm(expected[:3,:3],axis=0)
    row['maxPositionErrorCm']=max(row['maxPositionErrorCm'],float(np.linalg.norm(np.array(value['translation'])-expected[:3,3])))
    if expected_scale.min()>1e-7:
     expected_rotation=expected[:3,:3]/expected_scale;angle=Rotation.from_matrix(actual_rotation.T@expected_rotation).magnitude()*180/np.pi
     row['maxRotationErrorDegrees']=max(row['maxRotationErrorDegrees'],float(angle))
    row['maxScaleError']=max(row['maxScaleError'],float(abs(actual_scale-expected_scale).max()))
   body_i,body=g.body();mesh=g.g['meshes'][body['mesh']];names=mesh.get('extras',{}).get('targetNames',[]);values=weights.get(body_i,mesh.get('weights',[0]*len(names)))
   for index,(n,v) in enumerate(zip(names,values)):
    target=mesh['primitives'][0].get('targets',[])[index]
    nonzero_shape=bool(np.max(np.abs(g.accessor(target['POSITION'])))>1e-12)
    if n not in frame['morphCurves']:
     if nonzero_shape or abs(float(v))>.000001:coverage_errors.append({'character':character,'clip':name,'missingMorph':n})
    else:row['maxMorphWeightError']=max(row['maxMorphWeightError'],abs(float(v)-frame['morphCurves'][n]))
   row['samples']+=1
  for row in metrics.values():
   if row['samples']!=6:coverage_errors.append({'character':character,'clip':row['clip'],'sampleCount':row['samples'],'expectedSamples':6})
  for row in metrics.values():row['character']=character;row['pass']=row['maxPositionErrorCm']<.15 and row['maxRotationErrorDegrees']<.5 and row['maxScaleError']<.001 and row['maxMorphWeightError']<.005;rows.append(row)
 out=root/'Local/CustomuseImports'/('native-source-fidelity'+suffix+'.json');out.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({'clips':len(rows),'passed':sum(x['pass'] for x in rows),'failed':[x for x in rows if not x['pass']]},indent=2))
 (root/'Local/CustomuseImports'/('native-source-coverage'+suffix+'.json')).write_text(json.dumps({'clips':len(rows),'samples':sum(x['samples'] for x in rows),'coverageErrors':coverage_errors,'passed':not coverage_errors},indent=2)+'\n')
 return not coverage_errors and all(x['pass'] for x in rows)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);p.add_argument('--plans',type=Path);p.add_argument('--label',default='');a=p.parse_args();raise SystemExit(0 if run(a.root.resolve(),a.plans.resolve() if a.plans else None,a.label) else 1)
