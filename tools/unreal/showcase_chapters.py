#!/usr/bin/env python3
"""Map completed rehearsal events to the verified movie's real capture timeline."""
import argparse
import hashlib
import json
import math
from pathlib import Path

LABELS={'Idle':'Idle','Roar':'Roar','Walk':'Walk','TurnLeft':'Turn left','TurnRight':'Turn right',
        'TurnLeftFine':'Small left turn','TurnRightFine':'Small right turn','Fire':'Fire breath','Flight':'Takeoff',
        'Claw0':'Left front claw','Claw1':'Right front claw','Stomp2':'Left rear stomp','Stomp3':'Right rear stomp',
        'Tail':'Tail sweep','Bite':'Bite','Stagger0':'Left front leg break','Stagger1':'Right front leg break',
        'Stagger2':'Left rear leg break','Stagger3':'Right rear leg break','Death':'Death'}


def chapters(evidence_path,encode_path):
    evidence=json.loads(evidence_path.read_text());encode=json.loads(encode_path.read_text())
    if evidence.get('mode')!='showcase' or not(evidence.get('finalWrite') and evidence.get('finished') and evidence.get('passed')):
        raise ValueError('Only a completed, passing every-move rehearsal can produce final chapters')
    rows=evidence['showcase']['chapters']
    if len(rows)!=evidence['showcase']['requiredSegments'] or not all(r['passed'] for r in rows):
        raise ValueError('Incomplete native chapter coverage')
    manifest=evidence_path.parent/'native-video/frames.jsonl'
    if encode['manifestSHA256']!=hashlib.sha256(manifest.read_bytes()).hexdigest() or not encode['timingVerified'] or encode['selectedWorldIndex']!=0:
        raise ValueError('Movie is not the verified world-0 capture')
    if encode['sourceId']!=evidence['sourceId']:raise ValueError('Evidence/movie build mismatch')
    frames=[json.loads(l) for l in manifest.read_text().splitlines()]
    frames=[r for r in frames if r['type']=='frame' and r.get('worldIndex',0)==0]
    if not frames or not all(math.isfinite(f['requestedGameSeconds']) and math.isfinite(f['wallSeconds']) for f in frames):
        raise ValueError('Invalid capture timeline')
    origin=frames[0]['wallSeconds']
    def time(event):
        if not math.isfinite(event['seconds']):raise ValueError('Invalid chapter event time')
        frame=min(frames,key=lambda f:abs(f['requestedGameSeconds']-event['seconds']))
        return max(0.,frame['wallSeconds']-origin)
    result=[];seen=set();flight_parts=set()
    for event in evidence['events']:
        name=event.get('event','')
        if name.startswith('showcase_begin_'):
            key=name.removeprefix('showcase_begin_')
            if key not in LABELS or key in seen:raise ValueError('Unknown or duplicated chapter')
            seen.add(key);result.append({'label':LABELS[key],'seconds':time(event),'segment':key})
        elif event.get('showcase',{}).get('currentSegment')=='Flight':
            label={'dragon_Active':'Hover','showcase_flight_fire_down':'Fire down','dragon_Recovery':'Landing'}.get(name)
            if label:
                flight_parts.add(label);result.append({'label':label,'seconds':time(event),'segment':'Flight'})
    if seen!=set(LABELS):raise ValueError('A required move is absent from the movie event timeline')
    if flight_parts!={'Hover','Fire down','Landing'}:raise ValueError('Flight subphase events are incomplete')
    if not all(a['seconds']<b['seconds'] for a,b in zip(result,result[1:])):raise ValueError('Chapter times are not strictly ordered')
    return {'sourceId':evidence['sourceId'],'videoSHA256':encode['videoSHA256'],
            'durationSeconds':encode['encodedDurationSeconds'],'chapters':result,
            'scope':'Scripted production-animation rehearsal; camera labels remain outside the video'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('encode_receipt',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Refusing overwrite')
    data=chapters(a.evidence,a.encode_receipt);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(data,indent=2)+'\n')
    print('Verified movie chapters',len(data['chapters']))
