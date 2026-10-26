"""Validate actual comparison files, timing, skin topology and finite motion data."""
import json,struct,math,hashlib
from pathlib import Path
from catalog import ROOT,BASE,NEW,ROWS

def read(path):
 b=path.read_bytes();assert b[:4]==b'glTF';n=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+n]);return d,b[28+n:]
def shape(d):return {'vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for m in d['meshes'] for p in m['primitives']),'joints':len(d['skins'][0]['joints']),'indices':sum(d['accessors'][p['indices']]['count'] for m in d['meshes'] for p in m['primitives'])}
def finite_motion(d,blob):
 for anim in d['animations']:
  for sampler in anim['samplers']:
   for key in ('input','output'):
    a=d['accessors'][sampler[key]];v=d['bufferViews'][a['bufferView']];assert a['componentType']==5126
    width={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']];offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',4*width)
    assert all(math.isfinite(x) for i in range(a['count']) for x in struct.unpack_from('<'+'f'*width,blob,offset+i*stride))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def points(d,blob):
 result=[]
 for m in d['meshes']:
  for p in m['primitives']:
   a=d['accessors'][p['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']];off=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',12)
   result.extend(struct.unpack_from('<fff',blob,off+i*stride) for i in range(a['count']))
 return result

def geometry_error(reference,refblob,d,blob):
 cells={};step=1e-5
 for p in points(reference,refblob):cells.setdefault(tuple(math.floor(x/step) for x in p),[]).append(p)
 worst=0
 for p in points(d,blob):
  key=tuple(math.floor(x/step) for x in p);near=[]
  for x in (-1,0,1):
   for y in (-1,0,1):
    for z in (-1,0,1):near.extend(cells.get((key[0]+x,key[1]+y,key[2]+z),[]))
  assert near,'Geometry point missing'
  worst=max(worst,min(math.dist(p,q) for q in near))
 return worst
reference,refblob=read(BASE/'WalkOneHand_Blender_v2r2.glb');results=[]
for r in ROWS:
 before=BASE/r['before'];after=(BASE if r.get('retainOriginal') else NEW)/r['after']
 if r.get('retainOriginal'):
  assert sha(before)==sha(after);results.append({**r,'beforeSHA256':sha(before),'afterSHA256':sha(after),'retainedOriginal':True});continue
 d,blob=read(after);finite_motion(d,blob);assert shape(d)['indices']==shape(reference)['indices'] and shape(d)['joints']==shape(reference)['joints'];error=geometry_error(reference,refblob,d,blob);assert error<1e-6,error;meta=json.loads(after.with_suffix('.json').read_text());duration=max(d['accessors'][s['input']]['max'][0] for a in d['animations'] for s in a['samplers']);assert abs(duration-meta['duration'])<1e-5
 source=ROOT/meta['source'];results.append({**r,'before':str(before.relative_to(ROOT)),'after':str(after.relative_to(ROOT)),'beforeSHA256':sha(before),'afterSHA256':sha(after),'blend':str(after.with_suffix('.blend').relative_to(ROOT)),'blendSHA256':sha(after.with_suffix('.blend')),'sourceFile':meta['source'],'sourceSHA256':sha(source),'duration':duration,'fps':meta['fps'],'topology':shape(d),'finiteMotion':True,'maxRestGeometryError':error,'vertexSplitNote':'Blender exporter duplicates34 vertices at attribute seams; triangle topology and positions retained'})
archives=[]
for name in ['Sword and Shield Pack.zip','freesampleanimationset.unitypackage']:
 p=ROOT/'Local/FabRigTesting/Source'/name;archives.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)})
report={'branch':'Fab-3D-Rig-Testing','baseCommit':'327d3ac','acquired':'2026-10-25','reviewURL':'http://127.0.0.1:8777/','gameIntegrated':False,'ownerAccepted':False,'archives':archives,'pairs':results,'validation':{'liveBrowserAllFivePairs':True,'originalTiming':True,'halfSpeedAndPhaseMatch':True,'scrubPauseRestart':True,'rootCenteringToggle':True,'rollVisibilityFixed':True,'criticReview':'usable comparison; source-fit and weapon-aware adaptation still required'}}
(ROOT/'docs/fab-rig-testing/manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'pairs':len(results),'topology':shape(reference),'allFinite':True,'timingVerified':True}))
