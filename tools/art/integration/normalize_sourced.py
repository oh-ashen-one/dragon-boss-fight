#!/usr/bin/env python3
"""Canonicalize already-rigged sourced exports without altering their motion.

The fitted files already contain VeyrRoot/WeaponSocket/CupSocket. Preserve those
curves, remap palettes by name, and factor only explicit planar actor travel.
"""
import copy,json,math
from pathlib import Path
import numpy as np
from normalize_approved import GLB,Writer,decompose,UE,digest,mesh_variant
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/import-plan-KnightB.json'
OUT=ROOT/'Local/CustomuseAssets/Sourced20261025'

def normalize_file(path,canonical,out,fps,root_prefix=None):
 src=GLB(path);names=canonical.skin_names();assert set(src.skin_names())==set(names)
 writer=Writer(src.g,src.binary);g=writer.g;body_index,body=src.body();_,cb=canonical.body()
 g['nodes']=copy.deepcopy(canonical.g['nodes']);g['scenes']=copy.deepcopy(canonical.g['scenes']);g['scene']=canonical.g.get('scene',0)
 out_body=next(i for i,n in enumerate(g['nodes']) if 'mesh' in n and 'skin' in n)
 preserved=copy.deepcopy(body);preserved['name']=g['nodes'][out_body]['name'];preserved.pop('children',None);g['nodes'][out_body]=preserved
 # The body is stored in the same canonical bind coordinates in every fit.
 assert np.allclose(src.sample(None)[0][body_index],np.eye(4),atol=1e-5)
 ids={n['name']:i for i,n in enumerate(g['nodes'])};skin=copy.deepcopy(canonical.g['skins'][0]);skin['inverseBindMatrices']=writer.add(canonical.accessor(skin['inverseBindMatrices']),'MAT4');g['skins']=[skin]
 palette=np.array([names.index(n) for n in src.skin_names()],dtype=np.uint16)
 for primitive in g['meshes'][body['mesh']]['primitives']:
  for attr,acc in list(primitive['attributes'].items()):
   if attr.startswith('JOINTS_'):primitive['attributes'][attr]=writer.add(palette[src.accessor(acc).astype(np.uint16)],'VEC4',5123)
 duration=src.duration();count=round(duration*fps);times=np.linspace(0,duration,count+1);poses=[];actors=[];initial=None;last_actor=None
 for t in times:
  world,_=src.sample(float(t));hips=world[src.names['Hips']][:3,3]
  if initial is None:initial=hips.copy()
  actor=np.eye(4)
  if root_prefix is not None:
   if t<=root_prefix+1e-6 or last_actor is None:actor[:3,3]=hips-initial;actor[1,3]=0;last_actor=actor.copy()
   else:actor=last_actor.copy()
  actors.append(actor);counter=np.linalg.inv(actor);poses.append({n:counter@world[src.names[n]] for n in names})
 animation={'name':Path(path).stem,'samplers':[],'channels':[]};time_accessor=writer.add(times,'SCALAR',bounds=True)
 parents=canonical.parents
 for name in names:
  index=ids[name];parent=parents.get(canonical.names[name]);parent_name=canonical.g['nodes'][parent].get('name') if parent is not None else None
  local=[np.linalg.inv(frame[parent_name])@frame[name] if parent_name in frame else frame[name] for frame in poses]
  parts=[decompose(m) for m in local];q=np.array([x[1] for x in parts])
  for i in range(1,len(q)):
   if q[i]@q[i-1]<0:q[i]*=-1
  for field,values,typ in [('translation',[x[0] for x in parts],'VEC3'),('rotation',q,'VEC4'),('scale',[x[2] for x in parts],'VEC3')]:
   sampler=len(animation['samplers']);animation['samplers'].append({'input':time_accessor,'output':writer.add(values,typ),'interpolation':'LINEAR'});animation['channels'].append({'sampler':sampler,'target':{'node':index,'path':field}})
 g['animations']=[animation];sha=writer.write(out);check=GLB(out);worst=0
 for i in sorted(set([0,len(times)//4,len(times)//2,3*len(times)//4,len(times)-1])):
  actual,_=check.sample(float(times[i]));raw,_=src.sample(float(times[i]));worst=max(worst,max(float(np.max(np.abs(actors[i]@actual[check.names[n]]-raw[src.names[n]]))) for n in names))
 assert worst<3e-5,(path,worst)
 return {'file':str(out),'sha256':sha,'sourceFile':str(Path(path).resolve()),'sourceSHA256':src.sha,'duration':duration,'rootSampleRate':count/duration,'rootTranslationSamplesCm':[(UE@a[:3,3]*100).tolist() for a in actors],'rootYawSamplesDegrees':[],'bRootMotionRemoved':root_prefix is not None,'rootMode':'authored_planar_profile' if root_prefix is not None else 'in_place','mesh_variant':'knight_'+mesh_variant(check)[:16],'canonicalReconstructionMaxMatrixError':worst}

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();plan=json.loads(BASE.read_text());canonical=GLB(plan['rig']['file']);art=json.loads(a.manifest.read_text());a.out.mkdir(parents=True,exist_ok=True)
 assert not (a.out/'sourced-manifest.json').exists(),'Choose a fresh output folder'
 rows=[]
 for clip in art['clips']:
  row=normalize_file(clip['file'],canonical,a.out/'knight'/Path(clip['file']).name,clip['fps'],clip.get('root_prefix_seconds'));row.update(clip);row['file']=str(a.out/'knight'/Path(clip['file']).name);row['sha256']=digest(Path(row['file']).read_bytes());rows.append(row);print('NORMALIZED',clip['key'],row['canonicalReconstructionMaxMatrixError'],flush=True)
 (a.out/'sourced-manifest.json').write_text(json.dumps({'canonicalRig':plan['rig'],'clips':rows,'sourceManifest':str(a.manifest.resolve())},indent=2)+'\n')
