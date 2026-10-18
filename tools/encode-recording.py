#!/usr/bin/env python3
"""Encode native backbuffer recording preserving timestamp pacing. Requires ffmpeg."""
import json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]).resolve()
data=json.loads((root/'frames.json').read_text())
frames=data['frames']
if not frames:raise SystemExit('No recorded frames')
lines=[]
for i,f in enumerate(frames):
    path=root/f['file']
    if not path.is_file():raise SystemExit('Missing recorded frame '+f['file'])
    escaped=str(path).replace("'", "'\\''")
    lines.append("file '"+escaped+"'")
    if i+1<len(frames):lines.append('duration '+str(max(.001,frames[i+1]['seconds']-f['seconds'])))
concat=root/'concat.txt';concat.write_text('\n'.join(lines)+'\n')
out=root/'native-gameplay.mp4'
subprocess.run(['ffmpeg','-n','-f','concat','-safe','0','-i',str(concat),'-fps_mode','vfr','-c:v','libx264','-threads','2','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True)
print(out)
