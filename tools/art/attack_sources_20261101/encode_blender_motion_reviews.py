#!/usr/bin/env python3
"""Encode complete Blender review views at their sampled 30 fps, unannotated."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'Local/AttackSources20261104/BlenderReviewFramed'
OUT = SOURCE/'movies'
OUT.mkdir(parents=True, exist_ok=True)
titles = {'Mixamo_ForwardRun_v4rigid': 'Two-handed run',
          'FabMixamo_OneHandRun_v2blender': 'One-handed run',
          'Mixamo_SlideAttack_v4blender': 'Running attack'}
figures = []
for name, title in titles.items():
    metadata = SOURCE/(name+'.json')
    if not metadata.exists():
        continue
    data = json.loads(metadata.read_text())
    assert data['reviewFPS'] == 30
    for view in ['front', 'side', 'threequarter']:
        files = [SOURCE/'Evidence'/name/f'{view}_{f:04d}.png' for f in data['frames']]
        assert all(p.is_file() for p in files)
        movie = OUT/f'{name}-{view}.mp4'
        receipt = movie.with_suffix('.json')
        frame_hash = hashlib.sha256(''.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in files).encode()).hexdigest()
        if movie.exists():
            prior = json.loads(receipt.read_text())
            assert prior['frameHashSequenceSHA256'] == frame_hash
            assert prior['movieSHA256'] == hashlib.sha256(movie.read_bytes()).hexdigest()
        else:
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                '-framerate', '30', '-pattern_type', 'glob', '-i', str(files[0].parent/(view+'_*.png')),
                '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-an', '-movflags', '+faststart', str(movie)]
            subprocess.run(command, check=True)
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                'stream=nb_frames,avg_frame_rate:format=duration', '-of', 'json', str(movie)], text=True))
            assert int(probe['streams'][0]['nb_frames']) == len(files)
            assert abs(float(probe['format']['duration'])-len(files)/30) < .001
            receipt.write_text(json.dumps({'frames': len(files), 'fps': 30, 'durationSeconds': len(files)/30,
                'frameHashSequenceSHA256': frame_hash, 'movieSHA256': hashlib.sha256(movie.read_bytes()).hexdigest(),
                'scope': 'Full source sampling at intended speed; includes one endpoint display frame. No native gameplay or quality acceptance.'}, indent=2)+'\n')
        figures.append(f'<figure><figcaption>{title} · {view}</figcaption><video controls playsinline preload="metadata" src="{movie.name}"></video></figure>')
page = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Veyr motion previews</title>
<style>body{margin:0;padding:16px;background:#090a0b;color:#ddd;font:14px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}figure{margin:0}video{width:100%;display:block}figcaption{padding:8px 0}</style>
<p>Blender motion previews · native gameplay review pending</p><main>'''+''.join(figures)+'</main>'
(OUT/'index.html').write_text(page)
print('Verified source review movies', len(figures), flush=True)
