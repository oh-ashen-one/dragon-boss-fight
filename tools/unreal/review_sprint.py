#!/usr/bin/env python3
"""Bare paired films with external lab/game-camera selectors."""
import argparse
from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import review_video

p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--port',type=int,default=8808);a=p.parse_args()
routes={};sources=set()
for kind in ['before-lab','after-lab','before-game','after-game']:
    path=a.directory/(kind+'.mp4');receipt=json.loads(path.with_suffix('.encode.json').read_text())
    if not path.is_file() or not receipt['timingVerified'] or receipt['failedFrames']:
        raise ValueError('Missing or unverified movie')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['videoSHA256']:raise ValueError('Movie receipt mismatch')
    sources.add(receipt['sourceId'])
    routes['/'+kind+'.mp4']=path.resolve()
if len(sources)!=1:raise ValueError('All views must use the same Shipping source')
review_video.PAGE=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Veyr - Sprint comparison</title>
<style>body{margin:0;background:#090b0e;color:#d8d9dc;font:14px system-ui}nav{display:flex;gap:12px;justify-content:center;margin:24px}button{background:#20262e;color:inherit;border:1px solid #58616e;padding:8px 16px;border-radius:4px;cursor:pointer}button[aria-pressed=true]{background:#414e60}main{max-width:1440px;margin:24px auto;padding:16px;display:grid;gap:24px}figure{margin:0}figcaption{margin-bottom:8px;letter-spacing:.15em;font-size:12px}video{width:100%;background:#000}@media(min-width:1100px){main{grid-template-columns:1fr 1fr}}</style>
<nav><button data-view="lab" aria-pressed="true">Side view</button><button data-view="game" aria-pressed="false">Gameplay camera</button></nav><main>
<figure><figcaption>BEFORE</figcaption><video id="before" controls playsinline preload="metadata" src="/before-lab.mp4"></video></figure>
<figure><figcaption>AFTER</figcaption><video id="after" controls playsinline preload="metadata" src="/after-lab.mp4"></video></figure></main>
<script>for(const button of document.querySelectorAll('button'))button.onclick=()=>{for(const b of document.querySelectorAll('button'))b.setAttribute('aria-pressed',String(b===button));for(const id of ['before','after']){const v=document.getElementById(id);v.pause();v.src='/'+id+'-'+button.dataset.view+'.mp4';v.load();}};</script>'''
server=ThreadingHTTPServer(('localhost',a.port),review_video.Handler);server.routes=routes
print('Sprint comparison ready',flush=True);server.serve_forever()
