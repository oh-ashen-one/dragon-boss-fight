#!/usr/bin/env python3
"""Acquire the selected CC0 support assets from Poly Haven's documented public API/CDN.

No authentication, purchases, HTML scraping or executable content. Existing bytes
must match the cached manifest. Raw assets stay private under Local.
"""
import argparse,hashlib,json,struct,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'Local/Fortress20261103/PolyHaven';AGENT='VeyrAssetPreparation/2026-11-03'
def acquire(asset):
 root=BASE/asset;root.mkdir(parents=True,exist_ok=True);manifest=root/'files.json'
 if not manifest.exists():
  with urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/'+asset,headers={'User-Agent':AGENT}),timeout=30) as r:data=r.read(2*1024*1024)
  json.loads(data);manifest.write_bytes(data)
 data=json.loads(manifest.read_text())
 if asset=='coastal_cliff_01':
  model=data['gltf']['4k']['gltf'];items={'coastal_cliff_01_4k.gltf':{k:v for k,v in model.items() if k!='include'},**model['include']}
 else:items={data[k]['2k']['jpg']['url'].rsplit('/',1)[1]:data[k]['2k']['jpg'] for k in (['Diffuse','arm'] if asset=='rust_coarse_01' else ['Diffuse','nor_dx','Rough'])}
 def fetch(item):
  rel,info=item;path=(root/rel).resolve();url=urlsplit(info['url']);assert path.is_relative_to(root.resolve()) and url.scheme=='https' and url.hostname=='dl.polyhaven.org' and not url.username and not url.password and info['size']<200*1024*1024
  if not path.exists():
   path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.part');req=urllib.request.Request(info['url'],headers={'User-Agent':AGENT})
   with urllib.request.urlopen(req,timeout=60) as response,tmp.open('xb') as stream:
    count=0
    while chunk:=response.read(1024*1024):
     count+=len(chunk)
     if count>info['size']:raise RuntimeError('Declared download size exceeded')
     stream.write(chunk)
   assert tmp.stat().st_size==info['size'] and hashlib.md5(tmp.read_bytes()).hexdigest()==info['md5'];tmp.rename(path)
  content=path.read_bytes();assert len(content)==info['size'] and hashlib.md5(content).hexdigest()==info['md5']
  return {'file':rel,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'url':info['url']}
 with ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(fetch,items.items()))
 (root/'acquisition.json').write_text(json.dumps({'asset':asset,'license':'CC0','licenseURL':'https://polyhaven.com/license','sourceURL':'https://polyhaven.com/a/'+asset,'priceUSD':0,'files':files},indent=2)+'\n')
 if asset=='coastal_cliff_01':pack(root)
 print(asset,'verified',sum(f['bytes'] for f in files),'bytes')
def pack(root):
 source=root/'coastal_cliff_01_4k.gltf';doc=json.loads(source.read_text());assert len(doc['buffers'])==1
 binary=bytearray((root/doc['buffers'][0]['uri']).read_bytes());geometry_sha=hashlib.sha256(binary).hexdigest();doc['buffers']=[{'byteLength':len(binary)}]
 for im in doc.get('images',[]):
  p=(root/im.pop('uri')).resolve();assert p.is_relative_to(root.resolve());data=p.read_bytes();binary.extend(b'\0'*(-len(binary)%4));offset=len(binary);binary.extend(data);im['bufferView']=len(doc['bufferViews']);im['mimeType']='image/jpeg';doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
 doc['buffers'][0]['byteLength']=len(binary);text=json.dumps(doc,separators=(',',':')).encode();text+=b' '*(-len(text)%4);binary.extend(b'\0'*(-len(binary)%4));payload=struct.pack('<III',0x46546c67,2,12+8+len(text)+8+len(binary))+struct.pack('<II',len(text),0x4e4f534a)+text+struct.pack('<II',len(binary),0x004e4942)+binary
 out=root/'CoastalCliff_packed.glb'
 if out.exists():assert out.read_bytes()==payload,'Preserve a different packed source'
 else:out.write_bytes(payload)
 (root/'packing.json').write_text(json.dumps({'inputJSONSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'originalGeometryBufferSHA256':geometry_sha,'packedSHA256':hashlib.sha256(payload).hexdigest(),'geometryBufferBytesPreserved':True,'textureBytesPreserved':True},indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('asset',choices=['coastal_cliff_01','slate_floor_02','rust_coarse_01']);a=p.parse_args();acquire(a.asset)
