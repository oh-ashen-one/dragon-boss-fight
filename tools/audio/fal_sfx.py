#!/usr/bin/env python3
"""One fal.ai sound-effect job at a time (elevenlabs/sound-effects/v3), logged to the generation ledger.

  set -a; . ~/.config/fal/secrets.env; set +a          # FAL_KEY is only ever read from the environment
  python3 tools/audio/fal_sfx.py make CUE "prompt" SECONDS [--influence 0.5]   # submit, wait, download, log
  python3 tools/audio/fal_sfx.py mark JOB_ID kept|rejected "why"

Downloads go to Local/AudioSources20261118/generated/<job>.mp3 (not committed). The ledger
(docs/audio-20261118/generation-ledger.json) records time, endpoint, prompt, requested seconds, cost, file hash and the
decision. The key is never printed or written. Refuses a job that would take the total over the budget.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = 'elevenlabs/sound-effects/v3'
PRICE_PER_SECOND = 0.002  # read from GET /v1/models/pricing on 2026-11-18
BUDGET = 3.0
ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / 'docs/audio-20261118/generation-ledger.json'
OUT = ROOT / 'Local/AudioSources20261118/generated'


def call(url, body=None, method=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={'Authorization': 'Key ' + os.environ['FAL_KEY'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # the body explains a refusal; the key is never part of it
        sys.exit(f'HTTP {e.code}: ' + e.read()[:400].decode('utf-8', 'replace'))


def load():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {'endpoint': ENDPOINT, 'pricePerSecondUSD': PRICE_PER_SECOND,
                                                                     'budgetUSD': BUDGET, 'jobs': []}


def save(ledger):
    ledger['totalCostUSD'] = round(sum(j['costUSD'] for j in ledger['jobs']), 4)
    LEDGER.write_text(json.dumps(ledger, indent=1) + '\n')


p = argparse.ArgumentParser(description=__doc__)
sub = p.add_subparsers(dest='cmd', required=True)
m = sub.add_parser('make')
m.add_argument('cue')
m.add_argument('prompt')
m.add_argument('seconds', type=float)
m.add_argument('--influence', type=float, default=0.5)
k = sub.add_parser('mark')
k.add_argument('job')
k.add_argument('decision', choices=['kept', 'rejected'])
k.add_argument('why')
a = p.parse_args()
ledger = load()
if a.cmd == 'mark':
    job = next(j for j in ledger['jobs'] if j['job'] == a.job)
    job['decision'], job['why'] = a.decision, a.why
    save(ledger)
    print('marked', a.job, a.decision)
    sys.exit(0)
cost = round(a.seconds * PRICE_PER_SECOND, 4)
spent = sum(j['costUSD'] for j in ledger['jobs'])
if spent + cost > BUDGET:
    sys.exit(f'refused: {spent:.3f} + {cost:.3f} would exceed the {BUDGET} USD budget')
body = {'text': a.prompt, 'duration_seconds': a.seconds, 'prompt_influence': a.influence, 'output_format': 'mp3_44100_128'}
sub_resp = call(f'https://queue.fal.run/{ENDPOINT}', body)
status_url, result_url = sub_resp['status_url'], sub_resp['response_url']
while True:
    st = call(status_url)
    if st.get('status') == 'COMPLETED':
        break
    if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
        sys.exit('job failed: ' + json.dumps(st)[:300])
    time.sleep(2)
audio = call(result_url)['audio']
OUT.mkdir(parents=True, exist_ok=True)
n = len(ledger['jobs']) + 1
job_id = f'g{n:03d}'
target = OUT / f'{job_id}_{a.cue}.mp3'
with urllib.request.urlopen(audio['url'], timeout=120) as r:
    target.write_bytes(r.read())
ledger['jobs'].append({'job': job_id, 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                       'endpoint': ENDPOINT, 'cue': a.cue, 'prompt': a.prompt, 'durationRequestedS': a.seconds,
                       'promptInfluence': a.influence, 'costUSD': cost, 'file': str(target.relative_to(ROOT)),
                       'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'decision': 'pending', 'why': ''})
save(ledger)
print(job_id, target, 'cost', cost, 'total', ledger['totalCostUSD'])
