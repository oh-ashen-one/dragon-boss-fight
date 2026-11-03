#!/usr/bin/env python3
"""Combine the initial-world native viewport capture with its game-only master mix."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
manifest=next(a.run.rglob('frames.jsonl'));audio=sorted(a.run.rglob('*.wav'))[0];silent=a.output.with_name(a.output.stem+'-silent.mp4')
subprocess.run([sys.executable,str(ROOT/'tools/unreal/encode_video.py'),str(manifest.resolve()),'--world-index','0','--output',str(silent.resolve())],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(silent),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af','apad','-shortest','-map_metadata','-1','-movflags','+faststart',str(a.output)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name,nb_frames,duration','-of','json',str(a.output)]));assert {'video','audio'}=={x['codec_type'] for x in probe['streams']}
receipt={'sourceRun':a.run.name,'audioSHA256':hashlib.sha256(audio.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'probe':probe,'timing':'Unretimed initial-world capture streams, aligned at replay start; audio capture buffer and pixel-readback latency can differ within frames.','audioScope':'Game master submix only; no microphone or system audio.'}
a.output.with_suffix('.mix.json').write_text(json.dumps(receipt,indent=2)+'\n');silent.unlink();print('Game video/audio mux verified')
