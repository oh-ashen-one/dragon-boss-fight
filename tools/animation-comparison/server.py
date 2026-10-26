#!/usr/bin/env python3
"""Loopback-only before/after reviewer; explicit allowlist, private assets stay local."""
import hashlib,json,mimetypes,struct,argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
from catalog import ROOT,BASE,NEW,ROWS
HERE=Path(__file__).parent;CACHE=ROOT/'Local/polish-review-20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def duration(p):
 b=p.read_bytes();n=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+n]);return max(d['accessors'][s['input']]['max'][0] for a in d['animations'] for s in a['samplers'])
def inventory():
 routes={};rows=[]
 for r in ROWS:
  row=dict(r)
  for side,folder in [('before',BASE),('after',NEW),('raw',NEW)]:
   p=(BASE if side=='after' and r.get('retainOriginal') else folder)/r[side];url='/assets/'+side+'/'+p.name;routes[url]=p;row[side+'URL']=url;row[side+'SHA256']=sha(p);row[side+'Duration']=duration(p)
  rows.append(row)
 routes.update({'/':HERE/'index.html','/viewer.js':HERE/'viewer.js','/style.css':HERE/'style.css','/assets/sword.glb':CACHE/'BoatGreatsword_OneHand_v4.glb','/assets/guard-sword.glb':ROOT/'Local/CustomuseAssets/Polish20261025/props/BoatGreatsword_Grip_v6.glb'})
 for name in ['build/three.module.js','build/three.core.js','examples/jsm/loaders/GLTFLoader.js','examples/jsm/controls/OrbitControls.js','examples/jsm/utils/BufferGeometryUtils.js','examples/jsm/utils/SkeletonUtils.js']:
  routes['/vendor/three/'+name]=CACHE/'vendor/three'/name
 for p in routes.values():assert p.is_file(),p
 return rows,routes
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):self.respond(True)
 def do_HEAD(self):self.respond(False)
 def respond(self,body):
  route=unquote(urlsplit(self.path).path)
  if route=='/api/catalog':data=json.dumps(self.server.rows).encode();mime='application/json'
  elif route in self.server.routes:
   p=self.server.routes[route];data=p.read_bytes();mime='model/gltf-binary' if p.suffix=='.glb' else mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',len(data));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
  if body:
   try:self.wfile.write(data)
   except (BrokenPipeError,ConnectionResetError):pass
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8777);p.add_argument('--check',action='store_true');a=p.parse_args();rows,routes=inventory()
 if a.check:print(json.dumps({'pairs':len(rows),'files':len(routes),'allFilesVerified':True}));raise SystemExit()
 s=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);s.rows=rows;s.routes=routes;print('Comparison ready at http://127.0.0.1:'+str(a.port),flush=True);s.serve_forever()
