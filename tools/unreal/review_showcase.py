#!/usr/bin/env python3
"""Bare before/after movies with chapter buttons outside the frames."""
import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path

import review_video

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('before',type=Path);p.add_argument('after',type=Path)
p.add_argument('--before-chapters',type=Path,required=True);p.add_argument('--after-chapters',type=Path,required=True)
p.add_argument('--port',type=int,default=8806)
a=p.parse_args()
data={}
for name in ['before','after']:
    video=getattr(a,name).resolve();meta=json.loads(getattr(a,name+'_chapters').read_text())
    if hashlib.sha256(video.read_bytes()).hexdigest()!=meta['videoSHA256']:raise ValueError('Chapter/video mismatch')
    data[name]=meta['chapters']
payload=json.dumps(data).replace('<','\\u003c')
review_video.PAGE=('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Veyr — Dragon moves</title><style>body{margin:0;background:#090b0e;color:#d8d9dc;font:14px system-ui}
main{max-width:1440px;margin:24px auto;display:grid;gap:24px;padding:16px}figure{margin:0}figcaption{margin-bottom:8px;letter-spacing:.15em;font-size:12px}
video{width:100%;background:#000}.chapters{display:flex;flex-wrap:wrap;gap:6px}button{border:1px solid #454950;background:#171b21;color:inherit;border-radius:4px;padding:6px 9px;cursor:pointer}
button:hover,button.active{background:#343d49}p{min-height:1.4em}@media(min-width:1100px){main{grid-template-columns:1fr 1fr}}</style>
<main><figure><figcaption>BEFORE</figcaption><video id="before" controls playsinline preload="metadata" src="/before.mp4"></video><p></p><div class="chapters"></div></figure>
<figure><figcaption>AFTER</figcaption><video id="after" controls playsinline preload="metadata" src="/after.mp4"></video><p></p><div class="chapters"></div></figure></main>
<script>const chapters='''+payload+''';for(const id of ['before','after']){const video=document.getElementById(id),figure=video.parentElement,label=figure.querySelector('p'),buttons=[];
for(const chapter of chapters[id]){const b=document.createElement('button');b.textContent=chapter.label;b.onclick=()=>{video.currentTime=chapter.seconds;video.play().catch(()=>{});};figure.querySelector('.chapters').append(b);buttons.push(b);}
let active=-2;video.addEventListener('timeupdate',()=>{let index=-1;chapters[id].forEach((c,i)=>{if(c.seconds<=video.currentTime)index=i;});if(index!==active){active=index;label.textContent=index<0?'':chapters[id][index].label;buttons.forEach((b,i)=>b.classList.toggle('active',i===index));}});}</script>''').encode()
server=ThreadingHTTPServer(('localhost',a.port),review_video.Handler)
server.routes={'/before.mp4':a.before.resolve(),'/after.mp4':a.after.resolve()}
print('Veyr chapter review ready',flush=True)
server.serve_forever()
