#!/usr/bin/env python3
"""Blind visual sequences for completed sprint trials, including failed fidelity candidates."""
import argparse
import json
from pathlib import Path
import secrets
from encode_video import read_capture
from prepare_pacing_review import make_sheets

def load(path):
    path=path.resolve()
    d=json.loads(path.read_text())
    if d.get('mode')!='blendproof' or not(d.get('finished') and d.get('finalWrite') and d.get('blendProof',{}).get('sprintProof')):
        raise ValueError('Completed sprint rehearsal required')
    rows=d['blendProof']['sequences']
    if len(rows)!=4 or not all(r['completed'] for r in rows):raise ValueError('Four completed sequences required')
    manifest=path.parent/'native-video/frames.jsonl'
    _,frames,end,tail,_=read_capture(manifest,world_index=0)
    if not tail:raise ValueError('Capture end missing')
    trace=[json.loads(l) for l in (path.parent/'blendproof-frames.jsonl').read_text().splitlines()]
    return d,manifest,frames,end,trace

def prepare(before_lab,after_lab,before_game,after_game,out,mapping_path):
    out=out.resolve();mapping_path=mapping_path.resolve()
    if out.exists() or mapping_path.exists() or mapping_path.is_relative_to(out):raise ValueError('Fresh blind folder and external mapping required')
    variants=[{'lab':load(before_lab),'game':load(before_game)}, {'lab':load(after_lab),'game':load(after_game)}]
    if len({record[0]['sourceId'] for variant in variants for record in variant.values()})!=1:raise ValueError('Use one Shipping source for all views')
    secrets.SystemRandom().shuffle(variants);out.mkdir(parents=True)
    packet={'scope':'Sampled native frames in temporal order. Side laboratory and ordinary gameplay camera show the same four input sequences. No chronology is disclosed. Sampling cannot establish continuous motion or human gameplay feel.','variants':{}};mapping={}
    for label,variant in zip(['A','B'],variants):
        items=[];mapping[label]={}
        for view,(data,manifest,frames,end,trace) in variant.items():
            origin=frames[0]['wallSeconds'];mapping[label][view]=str(manifest)
            for row in data['blendProof']['sequences']:
                start,finish=row['gameStartSeconds'],row['gameEndSeconds'];times=[start+(finish-start)*i/15 for i in range(16)]
                seq=[f for f in trace if f['sequence']==row['name']]
                # Add dense samples around each actual clip change; the uniform
                # samples retain the whole action and stable endpoints.
                for a,b in zip(seq,seq[1:]):
                    if a['clip']!=b['clip']:
                        times.extend(max(start,min(finish,b['t']+dt)) for dt in [-.066,0,.033,.066,.133,.233])
                selected=[];seen=set()
                for time in sorted(times):
                    f=min(frames,key=lambda f:abs(f['requestedGameSeconds']-time))
                    if f['file'] not in seen:selected.append(f);seen.add(f['file'])
                sheets=make_sheets(manifest.parent,selected,origin,out,f'{label}-{view}-{row["index"]:02}-{row["name"]}')
                items.append({'view':view,'sequence':row['name'],'sheets':sheets})
        packet['variants'][label]=items
    (out/'sequence.json').write_text(json.dumps(packet,indent=2)+'\n')
    mapping_path.write_text(json.dumps(mapping,indent=2)+'\n');print('Blind sprint packet prepared')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['before_lab','after_lab','before_game','after_game','out']:p.add_argument(key,type=Path)
    p.add_argument('--mapping',type=Path,required=True);a=p.parse_args()
    prepare(a.before_lab,a.after_lab,a.before_game,a.after_game,a.out,a.mapping)
