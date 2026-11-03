#!/usr/bin/env python3
"""Convert the owner-selected score without retiming or changing its arrangement."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
a.output.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(a.input),'-map','0:a:0','-vn','-map_metadata','-1','-ar','48000','-ac','2','-c:a','pcm_s16le','-f','s16le',str(a.output)],check=True)
d={'sourceName':a.input.name,'sourceSHA256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'sampleRate':48000,'channels':2,'format':'signed 16-bit little-endian PCM','durationSeconds':a.output.stat().st_size/(48000*2*2),'processing':'Decode/resample only; no trim, tempo, gain, loop crossfade or arrangement changes. Source metadata and cover image omitted.','provenance':'Owner supplied soundtrack and explicitly selected it for Veyr. Raw/distributable music is not published in the public source repository.'}
a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
