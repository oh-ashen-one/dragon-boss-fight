"""Check baked GLB loop closure and retention of non-limb tracks."""
from pathlib import Path
import json,struct,math
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Blender/dangle-20261025'
def tracks(path):
 data=path.read_bytes();size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);blob=data[28+size:]
 def acc(i):
  a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']];width={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']];assert a['componentType']==5126
  start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',width*4)
  return [struct.unpack_from('<'+'f'*width,blob,start+j*stride) for j in range(a['count'])]
 result={}
 for a in doc['animations']:
  for c in a['channels']:
   s=a['samplers'][c['sampler']];result[(doc['nodes'][c['target']['node']].get('name'),c['target']['path'])]=(acc(s['input']),acc(s['output']))
 return doc,result
old,base=tracks(ROOT/'Local/Blender/polish-20261025/Dragon_FlyHover_Blender_polish_v1.glb');doc,new=tracks(OUT/'Dragon_FlyHover_Blender_dangle_v2.glb')
unchanged=[];changed=[];loop=[]
for key,(times,values) in new.items():
 if key in base:
  other=base[key][1];d=max(abs(x-y) for a,b in zip(values,other) for x,y in zip(a,b));(unchanged if d<1e-5 else changed).append((key,d))
 if key[1]!='weights':loop.append((key,max(abs(x-y) for x,y in zip(values[0],values[-1]))))
# bone_7 is the left shoulder; bone_9/14 are the source palm helpers.
assert all('Limb' in k[0] or k[0] in ('bone_7','bone_9','bone_14') for k,d in changed),changed
assert max(d for k,d in loop)<1e-5,sorted(loop,key=lambda x:-x[1])[:4]
r={'tracks':len(new),'unchangedTracks':len(unchanged),'changedTracks':[{'node':k[0],'path':k[1],'maxDelta':d} for k,d in changed],'nonLimbTracksPreserved':True,'maxLoopEndpointDelta':max(d for k,d in loop),'skins':len(doc['skins']),'jointCount':len(doc['skins'][0]['joints']),'duration':max(t[0] for ts,vs in new.values() for t in ts),'ownerApproved':False,'nativeIntegrated':False}
(OUT/'export-audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
