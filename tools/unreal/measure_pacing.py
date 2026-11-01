#!/usr/bin/env python3
"""Report active-clock damage gaps from native victory events; never infer visual quality."""
import argparse
import json
import math
from pathlib import Path


def measure(evidence):
    if evidence.get('mode') != 'victory' or not evidence.get('finalWrite'):
        raise ValueError('A completed native victory attempt is required')
    hits, contacts = [], 0
    initial_health = None
    for event in evidence['events']:
        if event.get('replayStage') not in ('combat', 'terminal'):
            continue
        count = event.get('swordContacts', 0)
        if initial_health is None:initial_health = event['bossMaxHealth']
        if count > contacts:
            if count != contacts + 1:
                raise ValueError('Missing damage event; cannot invent per-hit timing')
            t=event['encounterWallSeconds']
            if not math.isfinite(t) or (hits and t < hits[-1]['activeSeconds']):
                raise ValueError('Invalid encounter clock')
            hits.append({'activeSeconds':t, 'damage':event['lastSwordDamage'],
                         'remainingHP':event['bossHealth'], 'region':event['lastHitRegion'],
                         'dragonState':event['dragonState']})
            contacts = count
    terminal = evidence.get('terminalWallSeconds', -1)
    end = terminal if terminal > 0 else max((e['encounterWallSeconds'] for e in evidence['events']
            if e.get('replayStage')=='combat'), default=0)
    points=[0]+[h['activeSeconds'] for h in hits]+[end]
    gaps=[{'start':a,'end':b,'seconds':b-a} for a,b in zip(points,points[1:]) if b>=a]
    # Use observed HP loss, capped at the remaining health on the killing hit.
    prior=initial_health
    for h in hits:h['observedHealthLoss']=prior-h['remainingHP'];prior=h['remainingHP']
    burst=max((sum(h['observedHealthLoss'] for h in hits if start['activeSeconds']<=h['activeSeconds']<=start['activeSeconds']+4.)
               for start in hits), default=0)
    return {'sourceId':evidence['sourceId'],'initialHP':initial_health,'victoryPassed':evidence['passed'],
            'terminalActiveSeconds':terminal,'firstHitActiveSeconds':hits[0]['activeSeconds'] if hits else None,
            'longestNoDamageGap':max(gaps,key=lambda x:x['seconds']) if gaps else None,
            'damageGapsOver20Seconds':[g for g in gaps if g['seconds']>20],
            'largestFourSecondHealthLossFraction':burst/initial_health if initial_health else None,
            'hits':hits,'scope':'Native event timing; not a visual, difficulty or human-feel quality gate'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();report=measure(json.loads(a.evidence.read_text()));text=json.dumps(report,indent=2)+'\n'
    if a.output:
        if a.output.exists():raise ValueError('Refusing overwrite')
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
    else:print(text)
