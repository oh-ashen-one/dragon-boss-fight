#!/usr/bin/env python3
"""Convert selected CC0 recordings into bounded game PCM. Does not download assets.
Acquisition URLs and rights are documented in docs/overhaul-20261026/assets.md.
"""
from pathlib import Path
import subprocess,json,hashlib,array,math
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'Local/Overhaul20261026/audio';OUT=ROOT/'Unreal/Veyr/Content/Audio/Overhaul';OUT.mkdir(parents=True,exist_ok=True)
fire=SRC/'fire/LEGIT Audio_FIRE STAFF - FREE/Wavs'
items={
 'Swing':(SRC/'sword/Katana Swing.wav',.65,1),
 'HeavySwing':(SRC/'sword/Katana Swing.wav',.9,.77),
 'Contact':(SRC/'breaking/bfh1_hit_06.ogg',1.1,.85),
 'Guard':(SRC/'breaking/bfh1_metal_hit_03.ogg',1.2,1),
 'Impact':(SRC/'breaking/bfh1_rock_breaking_01.ogg',2.2,.78),
 'Breath':(SRC/'creatures/breath.ogg',2.1,.72),
 'Fire':(fire/'LEGIT_FIR_Fire_Staff 13-Audio.wav',3.,.78),
 'Roar':(SRC/'creatures/roar_02.ogg',3.5,.65),
 'Roll':(SRC/'footsteps/footsteps/step_cloth3.ogg',.7,.8),
 'Blink':(fire/'LEGIT_FIR_Fire_Staff 6-Audio.wav',.65,1.25),
 'Footstep':(SRC/'footsteps/footsteps/step_metal.ogg',.5,1),
 'Wing':(fire/'LEGIT_FIR_Fire_Staff 1-Audio.wav',1.25,.60),
 'Break':(SRC/'breaking/bfh1_rock_falling_04.ogg',3.,.85),
 'Music':(SRC/'music.wav',None,1),
 'Ambience':(SRC/'ambience.ogg',None,1),
}
report=[]
for name,(source,limit,pitch) in items.items():
 cmd=['ffmpeg','-v','error','-i',str(source),'-vn','-ac','1','-ar','24000','-f','s16le','-']
 raw=subprocess.check_output(cmd);samples=array.array('h');samples.frombytes(raw)
 if limit:
  # Pick one actual recorded event rather than retaining a multi-event recording.
  count=min(len(samples),int(limit*24000*pitch));step=1200
  starts=range(0,max(1,len(samples)-count+1),step)
  best=max(starts,key=lambda start:sum(float(x)*x for x in samples[start:start+count]))
  samples=samples[best:best+count]
  # Short equal-power fades remove cut clicks; peak normalization keeps headroom.
  peak=max(abs(x) for x in samples) or 1;gain=24500/peak
  for i in range(len(samples)):
   fade=min(1.,i/240,(len(samples)-1-i)/720)
   samples[i]=int(samples[i]*gain*max(0.,fade))
 else:best=0
 raw=samples.tobytes()
 if pitch!=1:
  raw=subprocess.check_output(['ffmpeg','-v','error','-f','s16le','-ar','24000','-ac','1','-i','pipe:0','-af',f'asetrate={24000*pitch},aresample=24000','-f','s16le','-'],input=raw)
 path=OUT/(name+'.pcm');path.write_bytes(raw)
 report.append({'cue':name,'source':str(source.relative_to(ROOT)),'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'pcmSHA256':hashlib.sha256(raw).hexdigest(),'sampleRate':24000,'channels':1,'durationSeconds':len(raw)/48000,'sourceStartSeconds':best/24000,'pitchRatio':pitch})
(ROOT/'Local/Overhaul20261026/audio/prepared.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'cues':len(report),'totalPCMBytes':sum((OUT/(x['cue']+'.pcm')).stat().st_size for x in report)}))
