#!/usr/bin/env python3
"""Check sustained captured audio and real runtime cue counters, not just Play calls."""
import argparse,json,subprocess
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
evidence=next(a.run.glob('unreal-*/evidence.json'));d=json.loads(evidence.read_text());wav=sorted(a.run.rglob('*.wav'))[0]
x=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(wav),'-ar','12000','-ac','1','-f','f32le','-']),dtype='<f4')
end=min(len(x)/12000,d['terminalSeconds'] if d.get('terminalSeconds',-1)>0 else d['durationSeconds']);windows=[]
for t in range(0,max(0,int(end)-5),5):
 block=x[t*12000:(t+5)*12000];windows.append({'start':t,'rms':float(np.sqrt(np.mean(block*block))),'peak':float(np.max(np.abs(block)))})
samples=d['samples'];r={'run':a.run.name,'sourceId':d['sourceId'],'gameplayPassed':d['passed'],'victorySeconds':d.get('terminalSeconds'),'mixDuration':len(x)/12000,'windows':windows,'sustainedAudioPassed':bool(windows) and all(w['rms']>1e-5 for w in windows),'clippedSamples':int((np.abs(x)>=1).sum()),'maximumMusicStartsPerWorld':max(s.get('musicStarts',0) for s in samples),'maximumDragonVocalCues':max(s.get('dragonVocalCues',0) for s in samples),'maximumPlayerPainCues':max(s.get('playerPainCues',0) for s in samples),'ownerScoreLoaded':all(s.get('ownerScoreLoaded') for s in samples),'scope':'Technical output continuity and runtime behavior; not subjective listening approval.'}
r['passed']=r['gameplayPassed'] and r['sustainedAudioPassed'] and r['clippedSamples']==0 and r['maximumMusicStartsPerWorld']==1
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='windows'}));raise SystemExit(0 if r['passed'] else 1)
