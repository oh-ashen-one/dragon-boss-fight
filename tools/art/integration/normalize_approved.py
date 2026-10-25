#!/usr/bin/env python3
"""Structural GLB integration adapter. No motion is authored here.

Preserve source bone channels; remap canonical skins and morph variants by name.
A nondeforming VeyrRoot carries inverse extracted motion, reconstructible exactly
by the emitted actor trajectory. Approved input files are never modified.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,struct
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
DT={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
WD={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
UE=np.array([[1,0,0],[0,0,1],[0,1,0]],dtype=float)

def digest(data):return hashlib.sha256(data).hexdigest()
def trs(n):
 if 'matrix' in n:return np.array(n['matrix'],float).reshape(4,4).T
 a=np.eye(4);a[:3,:3]=Rotation.from_quat(n.get('rotation',[0,0,0,1])).as_matrix()@np.diag(n.get('scale',[1,1,1]));a[:3,3]=n.get('translation',[0,0,0]);return a

def decompose(m):
 scales=np.linalg.norm(m[:3,:3],axis=0);rotation=m[:3,:3]/np.maximum(scales,1e-15)
 return m[:3,3],Rotation.from_matrix(rotation).as_quat(),scales

class GLB:
 def __init__(self,p):
  self.path=Path(p);raw=self.path.read_bytes();self.sha=digest(raw);n=struct.unpack_from('<I',raw,12)[0];self.g=json.loads(raw[20:20+n]);self.binary=bytearray(raw[28+n:]);self.parents={ch:i for i,x in enumerate(self.g['nodes']) for ch in x.get('children',[])};self.names={x.get('name'):i for i,x in enumerate(self.g['nodes'])};self.cache={}
 def accessor(self,i):
  if i in self.cache:return self.cache[i].copy()
  a=self.g['accessors'][i];dtype=np.dtype(DT[a['componentType']]);w=WD[a['type']];out=np.zeros((a['count'],w),dtype=dtype)
  if 'bufferView'in a:
   v=self.g['bufferViews'][a['bufferView']];off=v.get('byteOffset',0)+a.get('byteOffset',0);out=np.ndarray(out.shape,dtype=dtype,buffer=self.binary,offset=off,strides=(v.get('byteStride',w*dtype.itemsize),dtype.itemsize)).copy()
  if 'sparse'in a:
   s=a['sparse'];ind=s['indices'];v=self.g['bufferViews'][ind['bufferView']];ids=np.frombuffer(self.binary,dtype=DT[ind['componentType']],count=s['count'],offset=v.get('byteOffset',0)+ind.get('byteOffset',0));vv=s['values'];v=self.g['bufferViews'][vv['bufferView']];values=np.frombuffer(self.binary,dtype=dtype,count=s['count']*w,offset=v.get('byteOffset',0)+vv.get('byteOffset',0)).reshape(-1,w);out[ids]=values
  if a.get('normalized'):
   info=np.iinfo(dtype);out=np.maximum(out.astype(float)/info.max,-1)
  self.cache[i]=out;return out.copy()
 def sample(self,t):
  nodes=copy.deepcopy(self.g['nodes']);weights={}
  if self.g.get('animations') and t is not None:
   a=self.g['animations'][0]
   for c in a['channels']:
    sm=a['samplers'][c['sampler']];times=self.accessor(sm['input']).ravel();vals=self.accessor(sm['output']);path=c['target']['path'];ix=c['target']['node']
    if path=='weights':vals=vals.reshape(len(times),-1)
    k=max(0,min(len(times)-1,int(np.searchsorted(times,t,side='right'))-1));v=vals[k]
    if k+1<len(times) and t>times[k] and sm.get('interpolation','LINEAR')!='STEP':
     alpha=float((t-times[k])/(times[k+1]-times[k]));alpha=min(1,max(0,alpha))
     v=Slerp([0,1],Rotation.from_quat(vals[k:k+2]))([alpha]).as_quat()[0] if path=='rotation' else vals[k]*(1-alpha)+vals[k+1]*alpha
    if path=='weights':weights[ix]=v
    else:nodes[ix][path]=v.tolist();nodes[ix].pop('matrix',None)
  out={}
  def world(i):
   if i not in out:out[i]=(world(self.parents[i]) if i in self.parents else np.eye(4))@trs(nodes[i])
   return out[i]
  return np.array([world(i) for i in range(len(nodes))]),weights
 def duration(self):
  return max(float(self.accessor(s['input']).max()) for a in self.g.get('animations',[]) for s in a['samplers']) if self.g.get('animations') else 0.
 def skin_names(self):return [self.g['nodes'][n]['name'] for n in self.g['skins'][0]['joints']]
 def body(self):return next((i,n) for i,n in enumerate(self.g['nodes']) if 'mesh'in n and 'skin'in n)

class Writer:
 def __init__(self,g=None,binary=None):
  self.g=copy.deepcopy(g) if g else {'asset':{'version':'2.0','generator':'Veyr structural integration adapter'},'buffers':[{'byteLength':0}],'bufferViews':[],'accessors':[]};self.binary=bytearray(binary or b'')
 def add(self,data,typ='VEC3',component=5126,bounds=False):
  a=np.asarray(data,dtype=DT[component]).reshape(-1,WD[typ]);self.binary.extend(b'\0'*(-len(self.binary)%4));off=len(self.binary);raw=a.tobytes();self.binary.extend(raw);v=len(self.g['bufferViews']);self.g['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(raw)});acc={'bufferView':v,'componentType':component,'count':len(a),'type':typ}
  if bounds and len(a):acc.update(min=a.min(0).tolist(),max=a.max(0).tolist())
  i=len(self.g['accessors']);self.g['accessors'].append(acc);return i
 def write(self,path):
  self.binary.extend(b'\0'*(-len(self.binary)%4));self.g['buffers']=[{'byteLength':len(self.binary)}];j=json.dumps(self.g,separators=(',',':')).encode();j+=b' '*(-len(j)%4);raw=struct.pack('<III',0x46546c67,2,28+len(j)+len(self.binary))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(self.binary),0x004e4942)+self.binary;Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(raw);return digest(raw)

def morph_info(src):
 _,node=src.body();mesh=src.g['meshes'][node['mesh']];p=mesh['primitives'][0];names=mesh.get('extras',{}).get('targetNames',[]);out=[]
 for i,target in enumerate(p.get('targets',[])):
  arrays={k:src.accessor(v).astype('<f4') for k,v in target.items()};h=digest(b''.join(k.encode()+arrays[k].tobytes() for k in sorted(arrays)));out.append({'key':(names[i] if i<len(names) else 'Morph'+str(i),h),'arrays':arrays})
 return out

def canonical_body(src,kind,union,body_source=None):
 body_source=body_source or src
 w=Writer(body_source.g,body_source.binary);g=w.g;_,body=body_source.body();mesh=copy.deepcopy(g['meshes'][body['mesh']]);p=mesh['primitives'][0];skin=src.g['skins'][0];old_names=src.skin_names();ids={n:i+1 for i,n in enumerate(old_names)};nodes=[{'name':'VeyrRoot','children':[]}]
 for name in old_names:
  n=copy.deepcopy(src.g['nodes'][src.names[name]]);n.pop('children',None);n.pop('extras',None);nodes.append(n)
 for name in old_names:
  old=src.names[name];parent=src.parents.get(old)
  while parent is not None and src.g['nodes'][parent].get('name') not in ids:parent=src.parents.get(parent)
  pi=ids[src.g['nodes'][parent]['name']] if parent is not None else 0;nodes[pi].setdefault('children',[]).append(ids[name])
 source_ibm=body_source.accessor(body_source.g['skins'][0]['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1);ibm_by_name=dict(zip(body_source.skin_names(),source_ibm))
 ibm=[np.eye(4)]+[ibm_by_name[n] for n in old_names];joints=list(range(len(nodes)))
 if kind=='knight':
  socket=copy.deepcopy(src.g['nodes'][src.names['ReviewWeaponSocket']]);socket.pop('extras',None);socket['name']='WeaponSocket';wi=len(nodes);nodes.append(socket);nodes[0]['children'].append(wi);ids['WeaponSocket']=wi;joints.append(wi);ibm.append(np.linalg.inv(trs(socket)))
  ci=len(nodes);cup={'name':'CupSocket','rotation':[math.sqrt(.5),0,0,math.sqrt(.5)]};nodes.append(cup);nodes[ids['LeftHand']].setdefault('children',[]).append(ci);ids['CupSocket']=ci;joints.append(ci)
  rest,_=src.sample(None);ibm.append(np.linalg.inv(rest[src.names['LeftHand']]@trs(cup)))
 source_names=body_source.skin_names();palette=np.array([ids[n] for n in source_names],dtype=np.uint16)
 for attr,acc in list(p['attributes'].items()):
  if attr.startswith('JOINTS_'):p['attributes'][attr]=w.add(palette[body_source.accessor(acc).astype(np.uint16)],'VEC4',5123)
 if union:
  count=body_source.g['accessors'][p['attributes']['POSITION']]['count']
  p['targets']=[{semantic:w.add(a if len(a)==count else np.zeros((count,3),np.float32),'VEC3',bounds=True) for semantic,a in entry['arrays'].items()} for entry in union];mesh['extras']={'targetNames':[entry['name'] for entry in union]};mesh['weights']=[0.]*len(union)
 else:p.pop('targets',None);mesh.pop('weights',None);mesh.pop('extras',None)
 bi=len(nodes);nodes.append({'name':'Body','mesh':0,'skin':0});nodes[0]['children'].append(bi);g['nodes']=nodes;g['meshes']=[mesh];g['skins']=[{'name':kind.title()+'CanonicalSkin','joints':joints,'skeleton':0,'inverseBindMatrices':w.add(np.array(ibm).transpose(0,2,1).reshape(-1,16),'MAT4')}];g['scenes']=[{'name':'VeyrIntegration','nodes':[0]}];g['scene']=0;g.pop('animations',None)
 offset=None
 if kind=='knight':
  poses,_=src.sample(0);offset=np.linalg.inv(poses[src.names['RightHand']])@poses[src.names['ReviewWeaponSocket']]
 return w,ids,bi,offset

def actor_motion(src,name,times,kind):
 root_name='Hips' if kind=='knight' else 'tripo::Root';root=src.names[root_name];matrices=[src.sample(float(t))[0][root] for t in times];initial=matrices[0][:3,3].copy();translations=np.array([m[:3,3]-initial for m in matrices]);mode='none';yaw=np.zeros(len(times))
 if kind=='knight' and any(x in name for x in ('Backpedal','Strafe','WalkTwoHand','GuardBreak','RollAttack')):mode='planar'
 if kind=='knight' and ('WalkTwoHand' in name or 'Backpedal_Blender_loop' in name):mode='none'
 if kind=='dragon' and any(x in name for x in ('FlyHover','Takeoff','Land')):mode='none'
 if kind=='dragon' and 'Turn' in name:mode='turn'
 if mode not in ('planar','full','turn'):translations[:]=0
 if mode in ('planar','turn'):translations[:,1]=0
 if mode=='turn':
  rot0=matrices[0][:3,:3];angles=[]
  for matrix in matrices:
   rel=matrix[:3,:3]@np.linalg.inv(rot0);angles.append(math.atan2(rel[0,2],rel[2,2]))
  yaw=np.unwrap(angles)
  if np.max(np.abs(yaw))<1e-5 and np.max(np.abs(translations))<1e-5:mode='none';yaw[:]=0;translations[:]=0
 motion=[]
 for v,a in zip(translations,yaw):
  mat=np.eye(4);mat[:3,:3]=Rotation.from_rotvec([0,a,0]).as_matrix();mat[:3,3]=v;motion.append(mat)
 return np.array(motion),mode

def normalize(src,canonical,kind,union,out):
 if Path(out).resolve()==src.path.resolve():raise ValueError('Never overwrite an approved input')
 base,ids,body_index,legacy_grip=canonical;w=Writer(base.g,base.binary);g=w.g;animation={'name':out.stem,'channels':[],'samplers':[]};union_keys={u['key']:i for i,u in enumerate(union)};source_morphs=morph_info(src);_,source_body=src.body();source_body_i=src.body()[0]
 for c in src.g['animations'][0]['channels']:
  node=src.g['nodes'][c['target']['node']];name=node.get('name');path=c['target']['path'];sm=src.g['animations'][0]['samplers'][c['sampler']];times=src.accessor(sm['input']);values=src.accessor(sm['output']);target=None
  if name in ids:target=ids[name]
  elif name=='ReviewWeaponSocket' and kind=='knight':target=ids['WeaponSocket']
  elif name=='DrinkingCup' and kind=='knight':target=ids['CupSocket']
  elif c['target']['node']==source_body_i and path=='weights':
   target=body_index;old=values.reshape(len(times),-1);new=np.zeros((len(times),len(union)),np.float32)
   for i,info in enumerate(source_morphs):new[:,union_keys[info['key']]]=old[:,i]
   values=new.reshape(-1,1)
  if target is None:continue
  typ='SCALAR' if path=='weights' else 'VEC4' if path=='rotation' else 'VEC3';si=len(animation['samplers']);animation['samplers'].append({'input':w.add(times,'SCALAR',bounds=True),'output':w.add(values,typ),'interpolation':sm.get('interpolation','LINEAR')});animation['channels'].append({'sampler':si,'target':{'node':target,'path':path}})
 # Copy source static bone locals (legacy bone ordering differs, named basis agrees).
 for name,ix in ids.items():
  sn=src.g['nodes'][src.names[name]] if name in src.names else None
  if sn:
   for k in ('translation','rotation','scale','matrix'):
    g['nodes'][ix].pop(k,None)
    if k in sn:g['nodes'][ix][k]=copy.deepcopy(sn[k])
 if union:
  source_mesh=src.g['meshes'][source_body['mesh']];weights=source_body.get('weights',source_mesh.get('weights',[0.]*len(source_morphs)));default=[0.]*len(union)
  for i,info in enumerate(source_morphs):default[union_keys[info['key']]]=weights[i]
  g['meshes'][0]['weights']=default
 duration=src.duration();samples=max(1,math.ceil(duration*60));times=np.linspace(0,duration,samples+1);motion,mode=actor_motion(src,out.stem,times,kind)
 inv=np.linalg.inv(motion);tr=np.array([decompose(x)[0] for x in inv]);qs=np.array([decompose(x)[1] for x in inv]);sc=np.ones_like(tr)
 def channel(node,path,values,typ):
  i=len(animation['samplers']);animation['samplers'].append({'input':w.add(times,'SCALAR',bounds=True),'output':w.add(values,typ),'interpolation':'LINEAR'});animation['channels'].append({'sampler':i,'target':{'node':node,'path':path}})
 channel(0,'translation',tr,'VEC3');channel(0,'rotation',qs,'VEC4')
 if kind=='knight':
  if 'DrinkingCup' in src.names:
   cup=src.g['nodes'][src.names['DrinkingCup']]
   for prop,typ,default in [('translation','VEC3',[0,0,0]),('rotation','VEC4',[0,0,0,1])]:
    if not any(c['target']=={'node':ids['CupSocket'],'path':prop} for c in animation['channels']):channel(ids['CupSocket'],prop,[cup.get(prop,default)]*len(times),typ)
  else:channel(ids['CupSocket'],'scale',np.full((len(times),3),1e-5),'VEC3')
 if kind=='knight' and 'ReviewWeaponSocket' not in src.names:
  offset=legacy_grip
  vals=[decompose(src.sample(float(t))[0][src.names['RightHand']]@offset) for t in times]
  channel(ids['WeaponSocket'],'translation',[v[0] for v in vals],'VEC3');channel(ids['WeaponSocket'],'rotation',[v[1] for v in vals],'VEC4');channel(ids['WeaponSocket'],'scale',[v[2] for v in vals],'VEC3')
 g['animations']=[animation];sha=w.write(out)
 # Verify named bone and helper world transforms reconstructed from actor motion.
 check=GLB(out);errors={'bones':0.,'weapon':0.,'cup':0.,'morph':0.}
 for i in sorted(set([0,len(times)//5,len(times)//3,len(times)//2,3*len(times)//4,len(times)-1])):
  t=float(times[i]);sw,sweights=src.sample(t);nw,nweights=check.sample(t);matrix=motion[i]
  for name in src.skin_names():errors['bones']=max(errors['bones'],float(abs(matrix@nw[ids[name]]-sw[src.names[name]]).max()))
  for old,new,metric in [('ReviewWeaponSocket','WeaponSocket','weapon'),('DrinkingCup','CupSocket','cup')]:
   if old in src.names:errors[metric]=max(errors[metric],float(abs(matrix@nw[ids[new]]-sw[src.names[old]]).max()))
  if source_morphs:
   oldweights=sweights.get(source_body_i,src.g['meshes'][source_body['mesh']].get('weights',[0.]*len(source_morphs)));newweights=nweights.get(body_index,g['meshes'][0]['weights']);oldsum=np.zeros_like(source_morphs[0]['arrays']['POSITION']);newsum=np.zeros_like(oldsum)
   for j,entry in enumerate(source_morphs):oldsum+=entry['arrays']['POSITION']*oldweights[j]
   for j,entry in enumerate(union):newsum+=entry['arrays']['POSITION']*newweights[j]
   errors['morph']=max(errors['morph'],float(abs(oldsum-newsum).max()))
 if max(errors.values())>2e-4:raise RuntimeError(('Reconstruction error',out.name,errors))
 local_ue=np.array([UE@mat[:3,3]*100 for mat in motion]);yaw_ue=[float(-Rotation.from_matrix(mat[:3,:3]).as_rotvec()[1]*180/math.pi) for mat in motion]
 return {'file':str(out),'sha256':sha,'sourceFile':str(src.path),'sourceSHA256':src.sha,'duration':duration,'sourceJointCount':len(src.skin_names()),'canonicalJointCount':len(g['skins'][0]['joints']),'rootMode':mode,'bRootMotionRemoved':mode!='none','rootSampleRate':samples/duration if duration else 60,'rootTranslationSamplesCm':local_ue.tolist(),'rootYawSamplesDegrees':yaw_ue if mode=='turn' else [],'reconstructionMaxError':errors,'legacy':False}

def static_copy(src,mesh_index,out):
 if Path(out).resolve()==src.path.resolve():raise ValueError('Never overwrite an approved input')
 # Keep only the chosen mesh scene. Unreferenced binary bytes are harmless; no armature/animations leak into import.
 w=Writer(src.g,src.binary);mesh=copy.deepcopy(src.g['meshes'][mesh_index]);w.g['meshes']=[mesh];w.g['nodes']=[{'name':out.stem,'mesh':0}];w.g['scenes']=[{'nodes':[0]}];w.g['scene']=0
 for k in ('skins','animations'):w.g.pop(k,None)
 return {'file':str(out),'sha256':w.write(out),'sourceSHA256':src.sha}

def mesh_variant(src):
 """Hash decoded geometry/skin/material payloads, independent of accessor indices."""
 _,node=src.body();mesh=src.g['meshes'][node['mesh']];parts=[]
 for primitive in mesh['primitives']:
  for semantic,index in sorted(primitive['attributes'].items()):parts.extend([semantic.encode(),src.accessor(index).tobytes()])
  if 'indices' in primitive:parts.append(src.accessor(primitive['indices']).tobytes())
  for target in primitive.get('targets',[]):
   for semantic,index in sorted(target.items()):parts.extend([semantic.encode(),src.accessor(index).tobytes()])
 # Only referenced materials/textures count; the heal file's unused cup material
 # must not create a different body variant.
 used=sorted({p.get('material',0) for p in mesh['primitives']});mats=[copy.deepcopy(src.g['materials'][i]) for i in used]
 def material_payload(value,parent=''):
  if isinstance(value,list):return [material_payload(x,parent) for x in value]
  if not isinstance(value,dict):return value
  result={k:material_payload(v,k) for k,v in value.items() if k!='name'}
  if parent.lower().endswith('texture') and 'index' in value:
   texture=src.g['textures'][value['index']];image=src.g['images'][texture['source']];view=src.g['bufferViews'][image['bufferView']];off=view.get('byteOffset',0);result['index']=digest(bytes(src.binary[off:off+view['byteLength']]));result['sampler']=src.g.get('samplers',[])[texture['sampler']] if 'sampler'in texture else None
  return result
 parts.append(json.dumps(material_payload(mats),sort_keys=True,separators=(',',':')).encode())
 parts.append(src.accessor(src.g['skins'][0]['inverseBindMatrices']).tobytes())
 return digest(b''.join(parts))

def run(args):
 source=Path(args.source).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True);cache=source/'tools/asset-review/.asset-cache/review';catalog=json.loads((source/'tools/asset-review/remainder-catalog.json').read_text())['clips'];rows=[r for r in catalog if not r.get('ownerApproved') or r['file']=='Heal_Blender_v4.glb'];srcs={r['file']:GLB(cache/r['file']) for r in rows};dragons=[s for n,s in srcs.items() if n.startswith('Dragon')];union=[];seen=set()
 for s in dragons:
  for info in morph_info(s):
   if info['key'] in seen:continue
   seen.add(info['key']);union.append({**info,'name':info['key'][0]+'_'+info['key'][1][:10]})
 knight=GLB(cache/'IdleOneHand_Blender_v2r4.glb');dragon=GLB(cache/'Dragon_Idle_Blender_v1r3.glb');bases={'knight':canonical_body(knight,'knight',[]),'dragon':canonical_body(dragon,'dragon',union)};result={'version':1,'sourcePolicy':'Approved inputs and per-clip body geometry, skin and materials preserved; canonical named joint hierarchy only; no new animation authored','canonicalSources':{'knight':{'file':str(knight.path),'sha256':knight.sha},'dragon':{'file':str(dragon.path),'sha256':dragon.sha}},'morphUnion':[{'name':u['name'],'sourceName':u['key'][0],'deltaHash':u['key'][1]} for u in union],'clips':[],'props':{}}
 for row in rows:
  src=srcs[row['file']];kind='dragon' if row['file'].startswith('Dragon') else 'knight';report=normalize(src,canonical_body(knight if kind=='knight' else dragon,kind,union if kind=='dragon' else [],src),kind,union if kind=='dragon' else [],out/kind/row['file']);report.update(kind=kind,job=row['job'],loop=row.get('previewLoop',False),swordFile=row.get('swordFile'));result['clips'].append(report);print('NORMALIZED',row['file'],report['reconstructionMaxError'],flush=True)
 for kind,folder in [('knight','ImportSet015'),('dragon','ImportSetDragon007')]:
  legacy=Path(args.legacy)/folder
  for p in sorted(legacy.glob('*.glb')):
   if p.name.endswith('Rig.glb') or (kind=='knight' and p.name!='Roll.glb'):continue
   src=GLB(p);report=normalize(src,canonical_body(knight if kind=='knight' else dragon,kind,union if kind=='dragon' else [],src),kind,union if kind=='dragon' else [],out/kind/('Legacy_'+p.name));report.update(kind=kind,job=p.stem,legacy=True,loop=p.stem in ('Idle','Walk','Exposed'));result['clips'].append(report);print('LEGACY',p.name,report['reconstructionMaxError'],flush=True)
 for name in ('BoatGreatsword_OneHand_v4.glb','BoatGreatsword_Grip_v6.glb','BoatGreatsword_StrongGrip_v1.glb'):result['props'][name]=static_copy(GLB(cache/name),0,out/'props'/name)
 heal=GLB(cache/'Heal_Blender_v4.glb');ci=heal.names['DrinkingCup'];result['props']['DrinkingCup.glb']=static_copy(heal,heal.g['nodes'][ci]['mesh'],out/'props'/'DrinkingCup.glb')
 variants={}
 for clip in result['clips']:
  key=clip['kind']+'_'+mesh_variant(GLB(clip['file']))[:16];clip['mesh_variant']=key
  variants.setdefault(key,{'file':clip['file'],'sha256':clip['sha256'],'kind':clip['kind'],'sourceSHA256':clip['sourceSHA256']})
 result['mesh_variants']=variants
 (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print('MANIFEST',out/'manifest.json',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);run(p.parse_args())
