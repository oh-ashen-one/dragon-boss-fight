#!/usr/bin/env python3
"""Prepare dedicated CC0 creature-library SFX; no voice TTS or pitch shifting."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('sources',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);records=[]
for cue,number in [('Roar','03'),('DragonGrowl','08'),('DragonPain','10')]:
 source=a.sources/('dragon-roar-'+number+'.wav');target=a.output/(cue+'.pcm')
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-map_metadata','-1','-ar','24000','-ac','1','-c:a','pcm_s16le','-f','s16le',str(target)],check=True)
 records.append({'cue':cue,'sourceURL':'https://sfxmint.com/sounds/dragon-roar-'+number,'license':'CC0-1.0','licenseURL':'https://sfxmint.com/license','sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'pcmSHA256':hashlib.sha256(target.read_bytes()).hexdigest(),'durationSeconds':target.stat().st_size/48000,'processing':'24 kHz mono PCM conversion only; no human TTS, pitch shifting, trimming or effects','sourceKind':'Pre-existing dedicated creature SFX library; provider identifies AI sound generation.'})
a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(records,indent=2)+'\n');print('Prepared three dedicated creature cues')
