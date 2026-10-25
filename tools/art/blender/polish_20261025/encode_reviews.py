import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Blender/polish-20261025/fullspeed'
for p in sorted(OUT.glob('*/timing.json')):
 r=json.loads(p.read_text())
 for view in r['views']:
  out=p.parent/(view+'.mp4')
  if out.exists():continue
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-framerate',str(r['playbackFPS']),'-i',str(p.parent/(view+'_%04d.png')),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True)
 print(r['name'],r['duration'])
