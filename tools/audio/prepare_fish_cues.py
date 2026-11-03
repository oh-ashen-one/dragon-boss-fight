#!/usr/bin/env python3
"""Prepare bounded PCM cues from the reviewed Fish vocal take and pain take."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('sources',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
# Natural silence between the roar and growl measured at 2.465–3.792 seconds.
clips=[('Roar','DragonRoar.wav',0.,2.50),('DragonGrowl','DragonRoar.wav',3.77,3.36),('PlayerPain','PlayerPain.wav',0.,.53)]
rows=[]
for cue,name,start,duration in clips:
 source=a.sources/name;target=a.output/(cue+'.pcm')
 filters=f'atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={max(0,duration-.04)}:d=0.04,alimiter=limit=0.8:level=false'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-vn','-map_metadata','-1','-af',filters,'-ar','24000','-ac','1','-c:a','pcm_s16le','-f','s16le',str(target)],check=True)
 rows.append({'cue':cue,'sourceName':name,'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(target.read_bytes()).hexdigest(),'trimStartSeconds':start,'trimDurationSeconds':duration,'sampleRate':24000,'channels':1,'processing':'Natural silence split, 8ms/40ms edge fades, peak limiter; no pitch shifting.','qualityScope':'ASR identified a roar/groan in source; technical checks do not replace owner listening.'})
a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(rows,indent=2)+'\n');print('Prepared',len(rows),'cues')
