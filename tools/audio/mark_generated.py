#!/usr/bin/env python3
"""Close the generation ledger: every job is 'kept' if its take went into the generated set (generated-set.json),
otherwise 'rejected' with the reason the checks gave (from the receipt's rejectedExamples). Manual decisions stay."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
lp = root / 'docs/audio-20261118/generation-ledger.json'
ledger = json.loads(lp.read_text())
receipt = json.loads((root / 'docs/audio-20261118/generated-set.json').read_text())
used = {v['job']: (cue, v['file']) for cue, info in receipt.items() for v in info['variants']}
why = {}
for cue, info in receipt.items():
    for e in info.get('rejectedExamples', []):
        why.setdefault(e['source'].split('_')[0], e['why'] + ' (above 130 Hz share %.2f, peak at %.2f s)' % (e['above130HzShare'], e['peakAtS']))
for j in ledger['jobs']:
    if j['decision'] == 'rejected' and j['why']:
        continue
    if j['job'] in used:
        j['decision'], j['why'] = 'kept', 'staged as ' + used[j['job']][1]
    else:
        j['decision'], j['why'] = 'rejected', why.get(j['job'], 'not selected: the set already had better takes of this cue')
lp.write_text(json.dumps(ledger, indent=1) + '\n')
print({d: sum(j['decision'] == d for j in ledger['jobs']) for d in ('kept', 'rejected', 'pending')}, ledger['totalCostUSD'])
