#!/usr/bin/env python3
"""Prepare a neutral dense native movement comparison, with private mapping."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
from PIL import Image,ImageDraw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--packet',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();assert not a.packet.exists() and not a.receipt.exists();a.packet.mkdir(parents=True)
    runs=[]
    for side,directory in [('before',a.before),('after',a.after)]:
        evidence=next(directory.glob('unreal-*/evidence.json'));data=json.loads(evidence.read_text())
        assert data['finished'] and data['finalWrite'] and data['blendProof']['runStartProof']
        manifest=evidence.parent/'native-video/frames.jsonl';frames=[r for r in map(json.loads,manifest.read_text().splitlines()) if r['type']=='frame' and r['worldIndex']==0]
        motion=[json.loads(s) for s in (evidence.parent/'blendproof-frames.jsonl').read_text().splitlines()]
        offset=statistics.median(s['worldTimeSeconds']-s['seconds'] for s in data['samples'])
        runs.append({'side':side,'evidence':evidence,'data':data,'manifest':manifest,'frames':frames,'motion':motion,'offset':offset})
    assert runs[0]['data']['sourceId']==runs[1]['data']['sourceId']
    random.SystemRandom().shuffle(runs);receipt={'mapping':{},'variants':{},'images':[]};images=[]
    for label,run in zip('AB',runs):
        receipt['mapping'][label]=run['side'];sequences=run['data']['blendProof']['sequences'];first=sequences[0];origin=first['gameStartSeconds']
        selected=[r for r in run['frames'] if origin+run['offset']<=r['requestedGameSeconds']<=first['gameEndSeconds']+run['offset']]
        def sheet(rows,name):
            canvas=Image.new('RGB',(1920,((len(rows)+5)//6)*198),'#111');draw=ImageDraw.Draw(canvas)
            for i,row in enumerate(rows):
                x,y=(i%6)*320,(i//6)*198
                with Image.open(run['manifest'].parent/row['file']) as im:canvas.paste(im.convert('RGB').resize((320,180),Image.Resampling.LANCZOS),(x,y))
                draw.text((x+4,y+181),f"{label} | {row['requestedGameSeconds']-run['offset']-origin:.3f}s",fill='white')
            canvas.save(a.packet/name,quality=94);images.append(name)
        for offset in range(0,len(selected),36):sheet(selected[offset:offset+36],f'{label}-sequence-{offset//36+1:02d}.jpg')
        context=[]
        for seq in sequences[1:]:
            for i in range(12):
                t=seq['gameStartSeconds']+(seq['gameEndSeconds']-seq['gameStartSeconds'])*i/11+run['offset']
                context.append(min(run['frames'],key=lambda r:abs(r['requestedGameSeconds']-t)))
        sheet(context,f'{label}-controls.jpg')
        motion=[r for r in run['motion'] if r['sequence']==first['name']]
        stop=next(r['t'] for r in motion if r['action']=='RunStop')
        for i,t in enumerate([stop-.15,stop+.05,stop+.2,stop+.7]):
            frame=min(run['frames'],key=lambda r:abs(r['requestedGameSeconds']-(t+run['offset'])))
            name=f'{label}-detail-{i+1}.png'
            with Image.open(run['manifest'].parent/frame['file']) as im:im.convert('RGB').save(a.packet/name)
            images.append(name)
        receipt['variants'][label]={'run':str(run['evidence']),'sourceId':run['data']['sourceId'],'complete':True,'passed':run['data']['passed'],
            'firstSequenceNativeFrames':len(selected),'gameRange':[origin,first['gameEndSeconds']],'gameTimeOffset':run['offset'],
            'manifestSHA256':hashlib.sha256(run['manifest'].read_bytes()).hexdigest()}
    assert len(images)<=32
    brief='''Judge two anonymous native movement tests for visible motion quality. They use the same packaged game, camera, input sequence and capture settings with one movement option varied. Neither version is represented as accepted. Do not infer which is newer and do not assume a longer or shorter stopping motion is better.

The numbered sequence sheets include EVERY captured frame of the complete first two-handed trial: idle, sourced start, sustained sprint, release/stop and return to idle. Read chronologically left-to-right/top-to-bottom. Timestamps are elapsed from that trial start. Native capture is approximately30frames/s; screenshots preserve the actual rendered frames. The controls sheet sparsely samples three other trials in order: early release, attack cancellation during start, and an unchanged one-handed control. Their absolute phases/durations can differ slightly between runs. Detail1 is just before release, detail2 just after release, detail3 early stop, detail4 later stop; each retains native resolution.

Read every listed image once. Judge full-body weight, stride, foot sliding/ground contact, heading changes, run-to-stop join, deceleration length, return to idle, weapon carry/grips/clearance and visible regressions. Do not reward merely matching poses if movement looks worse. State A, B or TIE and whether the winner is visibly better. A first tie stops this candidate; do not manufacture a preference. Give specific improvements, regressions, common failures and whether the winner is shippable or only worth further refinement. You see dense still sequences, not continuous video: do not claim video playback, input-latency, audio, collision, performance or full-combat validation. Do not use other directories, implementation history or metrics.
'''
    (a.packet/'brief.txt').write_text(brief+'\n'+'\n'.join(str((a.packet/n).resolve()) for n in images)+'\n')
    receipt['images']=[{'name':name,'sha256':hashlib.sha256((a.packet/name).read_bytes()).hexdigest()} for name in images]
    a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'images':len(images),'mapping':receipt['mapping'],'sequenceFrames':{k:v['firstSequenceNativeFrames'] for k,v in receipt['variants'].items()}}))

if __name__=='__main__':main()
