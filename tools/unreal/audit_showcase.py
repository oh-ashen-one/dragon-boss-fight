#!/usr/bin/env python3
"""Audit every-move coverage and its separation from actual combat victory."""
import argparse
import json
from pathlib import Path

from showcase_chapters import LABELS


def audit(evidence):
    if evidence.get('mode')!='showcase' or not all(evidence.get(k) for k in ['finished','finalWrite','passed']):
        raise ValueError('Showcase did not finish successfully')
    data=evidence['showcase'];rows=data['chapters']
    if len(rows)!=20 or {r['segment'] for r in rows}!=set(LABELS) or not all(r['passed'] for r in rows):
        raise ValueError('Required move coverage is incomplete')
    if evidence.get('terminalWallSeconds',-1)>=0:raise ValueError('Rehearsal incorrectly produced a victory timing')
    samples=evidence['samples']
    if not samples or any(s['playerHealth']!=100 or s['bossHealth']!=s['bossMaxHealth'] or s['swordContacts']!=0 or s['encounterWallSeconds']!=0 for s in samples):
        raise ValueError('Rehearsal changed combat resources or encounter clock')
    flight=next(r for r in rows if r['segment']=='Flight')
    if flight['flightFireDownFrames']<2:raise ValueError('Fire-down phase not observed')
    starts=[e for e in evidence['events'] if e.get('event')=='showcase_begin_Roar']
    ends=[e for e in evidence['events'] if e.get('event')=='showcase_end_Roar']
    if len(starts)!=1 or len(ends)!=1:raise ValueError('Roar event boundaries missing')
    shake=ends[0]['fightFeel']['shakeEvents']-starts[0]['fightFeel']['shakeEvents']
    return {'sourceId':evidence['sourceId'],'mode':'showcase','passed':True,
            'requiredSegments':20,'completedSegments':len(rows),'playerCameraBaseline':data['playerCameraBaseline'],
            'combatResourcesUnchanged':True,'noVictoryTiming':True,
            'fireDownFrames':flight['flightFireDownFrames'],'roarShakeEvents':shake,
            'roarShakeDegrees':ends[0]['fightFeel']['lastShakeDegrees'],
            'roarShakeDistanceCm':ends[0]['fightFeel']['lastShakeDistanceCm'],
            'durationGameSeconds':evidence['durationSeconds'],'chapters':rows,
            'scope':'Native fidelity/coverage audit only; rendered visibility/quality needs independent review'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Refusing overwrite')
    r=audit(json.loads(a.evidence.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print('Every-move coverage audit passed; visual review still required')
