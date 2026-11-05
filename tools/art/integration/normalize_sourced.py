#!/usr/bin/env python3
"""Canonicalize already-rigged sourced exports without altering their motion.

The fitted files already contain VeyrRoot/WeaponSocket/CupSocket. Preserve those
curves, remap palettes by name, and factor only explicit planar actor travel.
"""
import copy,json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from normalize_approved import GLB,Writer,decompose,UE,digest,mesh_variant
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/import-plan-KnightB.json'
OUT=ROOT/'Local/CustomuseAssets/Sourced20261025'

def normalize_file(path,canonical,out,fps,root_prefix=None,root_vertical=False,root_linear=False,root_turn=False,root_linear_prefix=None):
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
 first_world,_=src.sample(0.);last_world,_=src.sample(duration)
 prefix_world=None
 if root_linear_prefix is not None:
  assert root_prefix is not None and root_prefix>=duration-1e-6 and 0<root_linear_prefix<=duration and not root_linear and not root_turn
  prefix_world,_=src.sample(float(root_linear_prefix))
 turn_angles=np.zeros(len(times))
 if root_turn:
  assert root_prefix is not None and root_prefix>=duration-1e-6 and not root_linear and not root_vertical
  initial_rotation=first_world[src.names['Hips']][:3,:3]
  angles=[]
  for t in times:
   world,_=src.sample(float(t));relative=world[src.names['Hips']][:3,:3]@np.linalg.inv(initial_rotation)
   q=Rotation.from_matrix(relative).as_quat()
   angles.append(2*math.atan2(q[1],q[3]))
  # Keep crossings of180degrees continuous. A wrapped rotvec would turn a
  # sourced188degree pivot into a356degree jump between adjacent root keys.
  turn_angles=np.unwrap(angles)
 vertical_base=max(first_world[src.names['Hips']][1,3],last_world[src.names['Hips']][1,3])
 for sample_index,t in enumerate(times):
  world,_=src.sample(float(t));hips=world[src.names['Hips']][:3,3]
  if initial is None:initial=hips.copy()
  actor=np.eye(4)
  if root_prefix is not None:
   if t<=root_prefix+1e-6 or last_actor is None:
    actor[:3,3]=(last_world[src.names['Hips']][:3,3]-first_world[src.names['Hips']][:3,3])*(t/duration) if root_linear else hips-initial
    if root_linear_prefix is not None and t<=root_linear_prefix+1e-6:
     actor[:3,3]=(prefix_world[src.names['Hips']][:3,3]-first_world[src.names['Hips']][:3,3])*(t/root_linear_prefix)
    if root_turn:
     actor[:3,:3]=Rotation.from_rotvec([0,turn_angles[sample_index],0]).as_matrix()
     actor[:3,3]=hips-actor[:3,:3]@initial
    actor[1,3]=max(0.,hips[1]-vertical_base) if root_vertical else 0;last_actor=actor.copy()
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
 return {'file':str(out),'sha256':sha,'sourceFile':str(Path(path).resolve()),'sourceSHA256':src.sha,'duration':duration,'rootSampleRate':count/duration,'rootTranslationSamplesCm':[(UE@a[:3,3]*100).tolist() for a in actors],'rootYawSamplesDegrees':(-np.degrees(turn_angles)).tolist() if root_turn else [],'bRootMotionRemoved':root_prefix is not None,'rootMode':'linear_shared_prefix_then_authored_profile' if root_linear_prefix is not None else 'authored_planar_turn' if root_turn else 'linear_cycle_travel' if root_linear else 'authored_planar_profile' if root_prefix is not None else 'in_place','linearRootPrefixSeconds':root_linear_prefix,'mesh_variant':'knight_'+mesh_variant(check)[:16],'canonicalReconstructionMaxMatrixError':worst}

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args();plan=json.loads(BASE.read_text());canonical=GLB(plan['rig']['file']);art=json.loads(a.manifest.read_text());a.out.mkdir(parents=True,exist_ok=True)
 assert not (a.out/'sourced-manifest.json').exists(),'Choose a fresh output folder'
 rows=[]
 for clip in art['clips']:
  row=normalize_file(clip['file'],canonical,a.out/'knight'/Path(clip['file']).name,clip['fps'],clip.get('root_prefix_seconds'));row.update(clip);row['file']=str(a.out/'knight'/Path(clip['file']).name);row['sha256']=digest(Path(row['file']).read_bytes());rows.append(row);print('NORMALIZED',clip['key'],row['canonicalReconstructionMaxMatrixError'],flush=True)
 (a.out/'sourced-manifest.json').write_text(json.dumps({'canonicalRig':plan['rig'],'clips':rows,'sourceManifest':str(a.manifest.resolve())},indent=2)+'\n')
