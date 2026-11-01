#!/usr/bin/env python3
"""Anonymous per-move native sequences, sampling every production state interval."""
import argparse
import json
from pathlib import Path
import secrets

from encode_video import read_capture
from prepare_pacing_review import make_sheets


def load(evidence_path):
    e=json.loads(evidence_path.read_text())
    if e.get('mode')!='showcase' or not(e.get('passed') and e.get('finished') and e.get('finalWrite')):
        raise ValueError('Completed passing showcase required')
    path=evidence_path.parent/'native-video/frames.jsonl'
    _,frames,end,tail,_=read_capture(path,world_index=0)
    if not tail:raise ValueError('Capture has no observed end')
    return e,path,frames,end


def prepare(before,after,directory,mapping_path):
    directory=directory.resolve();mapping_path=mapping_path.resolve()
    if directory.exists() or mapping_path.exists() or mapping_path.is_relative_to(directory):
        raise ValueError('Fresh blind directory and external mapping required')
    records=[load(before),load(after)]
    if records[0][0]['sourceId']!=records[1][0]['sourceId']:raise ValueError('Use the same native build')
    names=[[c['segment'] for c in r[0]['showcase']['chapters']] for r in records]
    if names[0]!=names[1] or len(names[0])!=20:raise ValueError('Different or incomplete move sequences')
    secrets.SystemRandom().shuffle(records);directory.mkdir(parents=True)
    manifest={'scope':'Native rendered frame sequences; read left-to-right then top-to-bottom. Each move samples all of its production state intervals. Black tiles are padding. Labels contain no chronology. Sampled evidence cannot establish continuous motion or player feel.','variants':{}}
    mapping={}
    for label,(e,path,frames,end) in zip(['A','B'],records):
        origin=frames[0]['wallSeconds'];moves=[]
        for index,chapter in enumerate(e['showcase']['chapters'],1):
            name=chapter['segment'];start,finish=chapter['startSeconds'],chapter['endSeconds']
            events=[x for x in e['events'] if x.get('event','').startswith('dragon_') and
                    x.get('showcase',{}).get('currentSegment')==name and start-.001<=x['seconds']<=finish+.001]
            transitions=[(max(start,x['seconds']-x.get('stateElapsed',0)),x['dragonState']) for x in events]
            if not transitions or transitions[0][0]>start+.05:transitions.insert(0,(start,name))
            transitions.append((finish,'end'))
            intervals=[(a,b,state) for (a,state),(b,_) in zip(transitions,transitions[1:]) if b-a>.04 and (state!='Idle' or name in ['Idle','Roar'])]
            if not intervals:intervals=[(start,finish,name)]
            count=max(3,16//len(intervals));selected=[];states=[]
            for a,b,state in intervals:
                for j in range(count):
                    target=a+(b-a)*(.03+.94*j/max(1,count-1))
                    frame=min(frames,key=lambda f:abs(f['requestedGameSeconds']-target))
                    selected.append(frame);states.append(state)
            sheets=make_sheets(path.parent,selected,origin,directory,f'{label}-{index:02}-{name}')
            moves.append({'move':name,'sheets':sheets,'tileStates':states})
        manifest['variants'][label]={'durationSeconds':end-origin,'moves':moves}
        mapping[label]=str(path)
    (directory/'sequence.json').write_text(json.dumps(manifest,indent=2)+'\n')
    mapping_path.parent.mkdir(parents=True,exist_ok=True);mapping_path.write_text(json.dumps(mapping,indent=2)+'\n')
    print('Anonymous every-move sequences prepared')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('directory',type=Path);p.add_argument('--mapping',type=Path,required=True)
    a=p.parse_args();prepare(a.before,a.after,a.directory,a.mapping)
