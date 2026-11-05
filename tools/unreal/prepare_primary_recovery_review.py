#!/usr/bin/env python3
"""Blind native single-tap attacks, their recoveries and the ordinary idle exit."""
import argparse
import json
from pathlib import Path
import secrets

from PIL import Image
from encode_video import read_capture
from prepare_pacing_review import make_sheets

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('before',type=Path);parser.add_argument('after',type=Path)
parser.add_argument('out',type=Path);parser.add_argument('--mapping',type=Path,required=True)
args=parser.parse_args();OUT=args.out.resolve();MAPPING=args.mapping.resolve()
assert not MAPPING.is_relative_to(OUT)
assert not OUT.exists() and not MAPPING.exists()
runs=[args.before.resolve(),args.after.resolve()]
assert all(r.is_relative_to(ROOT/'Evidence') for r in runs)
secrets.SystemRandom().shuffle(runs);OUT.mkdir()
packet={'scope':'Four native ordinary-input single-tap trials:1H side,2H side,2H three-quarter,2H front. '
        'Read each sheet left-to-right,top-to-bottom:4columns and8rows; black is padding. '
        'Every captured frame from attack start through recovery and0.4s of idle is retained. '
        'Compare the weight/readability and continuity of the attack ending, feet and grip; not the environment. '
        'These are ordered samples, not continuous playback or a combat-balance proof.','variants':{}}
mapping={};source_ids=set()
for label,run in zip(['A','B'],runs):
    evidence=next(run.glob('unreal-*/evidence.json'));d=json.loads(evidence.read_text())
    assert d['finished'] and d['finalWrite'] and d['blendProof']['primaryTapProof']
    # A100ms exit can disappear between coarse samples and falsely pass the
    # contact gate. The observed1080p failure is retained as the counterexample.
    assert all(s['maxFrameSeconds']<=.05 for s in d['blendProof']['sequences']), 'Recovery transition is undersampled; recapture before review'
    source_ids.add(d['sourceId'])
    recorded=[json.loads(l) for l in (evidence.parent/'blendproof-frames.jsonl').read_text().splitlines()]
    manifest=evidence.parent/'native-video/frames.jsonl';_,frames,_,tail,_=read_capture(manifest,world_index=0);assert tail
    origin=frames[0]['wallSeconds'];packet['variants'][label]=[]
    for trial in d['blendProof']['sequences']:
        rows=[r for r in recorded if r['seq']==trial['index']]
        active=[r for r in rows if r['phase']=='action'];idle=[r for r in rows if r['phase']=='post_idle']
        assert active and idle
        start=active[0]['t']-.05;end=idle[0]['t']+.4
        selected=[f for f in frames if start<=f['requestedGameSeconds']<=end]
        assert len(selected)>=20
        sheets=make_sheets(manifest.parent,selected,origin,OUT,f'{label}-trial-{trial["index"]}',rows=8)
        # Equal elapsed time after the last attack-state sample, not a
        # different phase midpoint from each variant's recovery duration.
        last_attack=next((r['t'] for r in reversed(active) if r['action'] not in ['Ready','AttackRecovery']),active[-1]['t'])
        detail=min(frames,key=lambda f:abs(f['requestedGameSeconds']-last_attack-.12))
        name=f'{label}-trial-{trial["index"]}-detail.png'
        with Image.open(manifest.parent/detail['file']) as im:im.convert('RGB').save(OUT/name)
        packet['variants'][label].append({'trial':trial['index'],'view':trial['name'],'sheets':sheets,'detail':name})
    mapping[label]=run.name
assert len(source_ids)==1
(OUT/'sequence.json').write_text(json.dumps(packet,indent=2)+'\n');MAPPING.write_text(json.dumps(mapping,indent=2)+'\n')
print('Native recovery packet prepared; image count',len(list(OUT.glob('*.jpg')))+len(list(OUT.glob('*.png'))))
