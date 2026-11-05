#!/usr/bin/env python3
"""Build a neutral, dense camera packet from two completed native captures.

No gameplay pixels are retouched. Sheets resize whole frames; detail PNGs retain
native resolution. Private mapping and quantitative results stay outside packet.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert not args.packet.exists() and not args.receipt.exists()
    runs = []
    for side, directory in [('before', args.before), ('after', args.after)]:
        evidence = next(directory.glob('unreal-*/evidence.json'))
        data = json.loads(evidence.read_text())
        assert data['finished'] and data['passed'] and data['victoryWithin150Seconds']
        manifest = evidence.parent/'native-video/frames.jsonl'
        frames = [r for r in map(json.loads, manifest.read_text().splitlines())
                  if r['type'] == 'frame' and r['worldIndex'] == 0]
        samples = [s for s in data['samples'] if s['worldTimeSeconds'] > s['seconds']-.2]
        runs.append(dict(side=side, evidence=evidence, data=data, manifest=manifest, frames=frames, samples=samples))
    assert runs[0]['data']['sourceId'] == runs[1]['data']['sourceId']
    random.SystemRandom().shuffle(runs)
    args.packet.mkdir(parents=True)
    receipt = {'scope': 'Native still-sequence camera comparison; not continuous video, audio, manual input or performance acceptance',
               'sourceId': runs[0]['data']['sourceId'], 'mapping': {}, 'variants': {}, 'images': []}
    image_names = []
    for label, run in zip('AB', runs):
        receipt['mapping'][label] = run['side']
        frames, samples, data = run['frames'], run['samples'], run['data']
        # Fixed identical time window with context at both ends; every captured
        # frame is included, including unlocked/manual-look replay behavior.
        selected = [r for r in frames if 20 <= r['requestedGameSeconds'] <= 30]
        assert selected
        selected_manifest = []
        def sheet(rows, name, columns=6):
            width, height = 320, 198
            canvas = Image.new('RGB', (columns*width, ((len(rows)+columns-1)//columns)*height), '#111111')
            draw = ImageDraw.Draw(canvas)
            for i, row in enumerate(rows):
                with Image.open(run['manifest'].parent/row['file']) as img:
                    canvas.paste(img.convert('RGB').resize((320,180), Image.Resampling.LANCZOS), ((i%columns)*width,(i//columns)*height))
                draw.text(((i%columns)*width+4,(i//columns)*height+181), f"{label} | {row['requestedGameSeconds']:.3f}s", fill='white')
            canvas.save(args.packet/name, quality=93)
            image_names.append(name)
        for offset in range(0,len(selected),36):
            sheet(selected[offset:offset+36], f'{label}-sequence-{offset//36+1:02d}.jpg')
            selected_manifest.extend({k:r[k] for k in ['file','requestedGameSeconds','wallSeconds']} for r in selected[offset:offset+36])
        # Equally selected whole-fight context, plus unresized flight details.
        times=[1,3,5.2,5.7,6.2,7,10,15,18,31,35,40,45,50,55,60,65,70,74,75,76,77,78,80]
        sheet([min(frames,key=lambda r:abs(r['requestedGameSeconds']-t)) for t in times],f'{label}-context.jpg')
        for index, t in enumerate([21.5,23.5,27]):
            row=min(frames,key=lambda r:abs(r['requestedGameSeconds']-t))
            name=f'{label}-detail-{index+1}.png'
            with Image.open(run['manifest'].parent/row['file']) as img:
                img.convert('RGB').save(args.packet/name)
            image_names.append(name)
        stats={}
        for state in ['Windup','Active','Recovery']:
            ss=[s for s in samples if s['lockedOn'] and s['dragonMove']=='FlyAway' and s['dragonState']==state]
            stats[state]={'samples':len(ss),'headVisible':sum(s['camera']['bossHeadWithinViewport'] for s in ss),
                          'feetVisible':sum(0<=s['camera']['feetViewportY']<=1 for s in ss),
                          'fitFound':sum(s['camera']['threatCameraFitFound'] for s in ss)}
        receipt['variants'][label]={'run':str(run['evidence']), 'passed':data['passed'],
            'victoryGameSeconds':data['terminalSeconds'],'victoryWallSeconds':data['terminalWallSeconds'],
            'flightLockedSamples':stats,'sequenceFrames':selected_manifest,
            'manifestSHA256':hashlib.sha256(run['manifest'].read_bytes()).hexdigest()}
    assert len(image_names)<=32
    brief='''Review two anonymous versions of the same native boss fight. Judge camera quality, not which implementation you think is newer. All images are real gameplay frames. Sequence sheets contain EVERY captured frame from game time 20-30 seconds, chronologically left-to-right/top-to-bottom, approximately 30 captured frames per second. Context sheets contain fixed time samples from the full fight including healing and death. Detail images retain full native resolution at approximately 21.5, 23.5 and 27 seconds. Runs use the same build, gameplay policy, resolution and capture settings with a camera option varied; natural simulation timing differs slightly.

Inspect each listed image ONCE, then give the verdict. You cannot play continuous video here. Do not claim to have watched video or verified continuous smoothness, audio, collision, manual control, performance or input latency. Judge visible boss head/mouth/attack tells, player/weapon/feet, ground hazards, scale, composition and changes across the dense sequence. A wider view is not automatically better: assess loss of weight, detail and player readability. Identify common failures and regressions. State A, B, or TIE, whether the winner is visibly better, and whether this visual evidence supports further integration or rejects both. Be candid about remaining gaps. A first tie stops this candidate, so do not break a tie arbitrarily. No metrics or implementation notes are provided.

Read every image below exactly once, then return a concise structured review with winner, visiblyBetter, visibleImprovements, visibleRegressions, remainingRequirements and scopeLimitations.
'''
    (args.packet/'brief.txt').write_text(brief+'\n'+'\n'.join(str((args.packet/n).resolve()) for n in image_names)+'\n')
    receipt['images']=[{'name':n,'sha256':hashlib.sha256((args.packet/n).read_bytes()).hexdigest()} for n in image_names]
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'imageCount':len(image_names),'packet':str(args.packet),'mapping':receipt['mapping']}))


if __name__ == '__main__':
    main()
