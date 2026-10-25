#!/usr/bin/env python3
"""Read-only localhost reviewer for the final eight October25 polish candidates.

Explicit route allowlist only: no directory listing, arbitrary paths or SSH.
This server is independent of the older reviewer on8775.
"""
import argparse,hashlib,json,mimetypes,struct
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'Local/Blender/polish-20261025';CACHE=ROOT/'Local/polish-review-20261025'
VENDOR=['build/three.module.js','build/three.core.js','examples/jsm/loaders/GLTFLoader.js','examples/jsm/controls/OrbitControls.js','examples/jsm/utils/BufferGeometryUtils.js','examples/jsm/utils/SkeletonUtils.js']
ALIASES={'FlightWindup':['polish/Dragon_Takeoff_Blender_polish_v1.glb','polish/Dragon_Takeoff_Blender_polish_v2.glb'],'FlightRecovery':['polish/Dragon_Land_Blender_polish_v1.glb','polish/Dragon_Land_Blender_polish_v2.glb','polish/Dragon_Land_Blender_polish_v3.glb']}
TITLES={'FlightHoverAlternate':'Dragon · Hover','FlightWindup':'Dragon · Takeoff','FlightRecovery':'Dragon · Landing','RunTwoHand':'Knight · Two-hand run','GripToTwoHand':'Knight · One hand → two hands','GripToOneHand':'Knight · Two hands → one hand','Roll':'Knight · Roll','RollAttack':'Knight · Roll into attack'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def header(path):
 with path.open('rb') as stream:
  first=stream.read(20)
  if len(first)!=20 or first[:4]!=b'glTF':raise ValueError('Invalid GLB '+path.name)
  count,kind=struct.unpack_from('<II',first,12)
  if kind!=0x4e4f534a:raise ValueError('Missing GLB JSON')
  return json.loads(stream.read(count))

def inventory():
 manifest=json.loads((SOURCE/'manifest.json').read_text());items=[];assets={}
 for row in manifest['clips']:
  path=Path(row['file']).resolve()
  if not path.is_relative_to(SOURCE.resolve()) or path.suffix!='.glb':raise ValueError('Candidate outside the known authoring directory')
  digest=sha(path)
  if digest!=row['sha256']:raise ValueError('Candidate hash changed: '+path.name)
  doc=header(path);group='dragon' if path.name.startswith('Dragon_') else 'knight';identifier='polish/'+path.name
  if group=='knight' and not any(n.get('name') in ('ReviewWeaponSocket','WeaponSocket') for n in doc['nodes']):raise ValueError('Knight candidate lacks authored weapon socket')
  assets['/api/asset/'+identifier]=path
  items.append({'id':identifier,'aliases':ALIASES.get(row['key'],[]),'file':path.name,'group':group,'title':TITLES.get(row['key'],row['key']),'key':row['key'],'duration':row['duration'],'loop':row['loop'],'candidate':True,'ownerApproved':bool(row.get('ownerApproved',False)),'sha256':digest,'bytes':path.stat().st_size,'animationNames':[a.get('name','Animation') for a in doc.get('animations',[])],'morphTargets':sum(len(p.get('targets',[])) for m in doc.get('meshes',[]) for p in m['primitives']),'weaponId':'props/'+row['weapon_file'] if row.get('weapon_file') else None})
 if len(items)!=8:raise ValueError('Expected the final eight candidates, not an incomplete manifest')
 sword=CACHE/'BoatGreatsword_OneHand_v4.glb'
 if sha(sword)!='bfb0bd2d6580882236e499833d28564712e08ff9323d76d3c55715d0ee558ab4':raise ValueError('Intact approved sword cache hash changed')
 assets['/api/asset/props/'+sword.name]=sword
 static={'/':HERE/'polish-index.html','/polish-index.html':HERE/'polish-index.html','/polish-viewer.js':HERE/'polish-viewer.js','/style.css':HERE/'style.css'}
 static.update({'/node_modules/three/'+rel:CACHE/'vendor/three'/rel for rel in VENDOR})
 for path in static.values():
  if not path.is_file():raise FileNotFoundError(path)
 return {'build':'October 25 polish candidates','nativeAcceptance':'pending','items':items},assets,static

class Handler(BaseHTTPRequestHandler):
 def do_HEAD(self):self.respond(False)
 def do_GET(self):self.respond(True)
 def respond(self,body):
  route=unquote(urlsplit(self.path).path)
  if route=='/api/catalog':
   data=json.dumps(self.server.catalog).encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
   if body:self.wfile.write(data)
   return
  path=self.server.allowed.get(route)
  if path is None:self.send_error(404,'Unknown review asset');return
  mime='model/gltf-binary' if path.suffix=='.glb' else 'text/javascript; charset=utf-8' if path.suffix=='.js' else mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Cache-Control','private, max-age=3600' if path.suffix=='.glb' else 'no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
  if body:
   try:
    with path.open('rb') as stream:
     while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
   except (BrokenPipeError,ConnectionResetError):pass

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8776);p.add_argument('--check',action='store_true');a=p.parse_args();catalog,assets,static=inventory()
 if a.check:print(json.dumps({'candidates':len(catalog['items']),'dragon':sum(i['group']=='dragon' for i in catalog['items']),'knight':sum(i['group']=='knight' for i in catalog['items']),'routes':len(assets)+len(static)+1,'filesVerified':True}));raise SystemExit(0)
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.catalog=catalog;server.allowed={**assets,**static};print(f'Veyr polish reviewer http://127.0.0.1:{a.port}/ — {len(catalog["items"])} candidates',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
