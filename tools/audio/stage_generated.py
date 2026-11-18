#!/usr/bin/env python3
"""Write Local/AudioSources20261118/generated/candidates.json from the generation ledger (jobs not rejected), in the
format prepare_recorded_set.py reads, so generated takes go through the same cut, check and level steps.
Titles are neutral on purpose ("fal job g001"): the creature-cue title filter must not see the prompt text.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
ledger = json.loads((root / 'docs/audio-20261118/generation-ledger.json').read_text())
src = root / 'Local/AudioSources20261118/generated'
out = {}
for j in ledger['jobs']:
    if j['decision'] == 'rejected':
        continue
    out.setdefault(j['cue'], []).append({
        'id': j['job'], 'cue': j['cue'], 'title': 'fal job ' + j['job'], 'author': 'fal.ai ' + j['endpoint'],
        'page': 'fal:' + j['endpoint'] + '#' + j['job'], 'license': 'generated (fal.ai)', 'sha256': j['sha256'],
        'file': Path(j['file']).name, 'generated': True, 'endpoint': j['endpoint'], 'prompt': j['prompt'], 'job': j['job']})
(src / 'candidates.json').write_text(json.dumps(out, indent=1) + '\n')
print({k: len(v) for k, v in out.items()})
