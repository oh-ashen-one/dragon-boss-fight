#!/usr/bin/env python3
"""Collect CC0 candidate recordings from Freesound's public search for a list of game cues.

For each cue in the plan (cue name -> queries, duration range, how many to keep) this reads the public
search results filtered to Creative Commons 0, most downloaded first, and downloads the public high-quality
preview of the top matches. No account or key is used. Every candidate is written to a ledger
with its sound page, author, title, license and file hash. Nothing is chosen here: prepare_recorded_set.py
picks and cuts the files that go into the game.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.parse

AGENT = 'Mozilla/5.0 (Macintosh) game-sound-research'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('plan', type=Path, help='JSON: {cue: {"queries": [...], "min": s, "max": s, "keep": n, "perQuery": n}}')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--only', help='comma-separated cue names')
a = p.parse_args()
plan = json.loads(a.plan.read_text())
a.out.mkdir(parents=True, exist_ok=True)
ledger_path = a.out / 'candidates.json'
ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}


def fetch(url, target=None):
    cmd = ['curl', '-sS', '-L', '--max-time', '60', '-A', AGENT, url]
    if target:
        cmd += ['-o', str(target)]
    out = subprocess.run(cmd, capture_output=True, check=True)
    return out.stdout.decode('utf-8', 'replace')


def attr(block, name):
    m = re.search(name + r'="([^"]*)"', block)
    return html.unescape(m.group(1)) if m else ''


for cue, spec in plan.items():
    if a.only and cue not in a.only.split(','):
        continue
    found = {c['id']: c for c in ledger.get(cue, [])}
    for query in spec['queries']:
        if len(found) >= spec['keep']:
            break
        duration = f'duration:[{spec["min"]} TO {spec["max"]}]'
        url = ('https://freesound.org/search/?q=' + urllib.parse.quote_plus(query) +
               '&f=' + urllib.parse.quote_plus('license:"Creative Commons 0" ' + duration) +
               '&s=' + urllib.parse.quote_plus('Downloads (most first)'))
        page = fetch(url)
        time.sleep(1.0)
        taken = 0
        per_query = spec.get('perQuery', 5)
        # One player block per result: the div that carries data-sound-id also carries the title,
        # the duration and the preview address.
        for block in re.findall(r'<div[^>]*class="[^"]*bw-player[^"]*"[^>]*>', page):
            sound_id = attr(block, 'data-sound-id')
            mp3 = attr(block, 'data-mp3')
            if not sound_id or not mp3 or sound_id in found:
                continue
            seconds = float(attr(block, 'data-duration') or 0)
            if not (spec['min'] <= seconds <= spec['max']):
                continue
            title = attr(block, 'data-title')
            downloads = int(attr(block, 'data-num-downloads') or 0)
            target = a.out / cue / f'{sound_id}.mp3'
            target.parent.mkdir(exist_ok=True)
            fetch(mp3.replace('-lq.mp3', '-hq.mp3'), target)
            if target.stat().st_size < 2000:
                target.unlink()
                continue
            found[sound_id] = {
                'id': sound_id, 'cue': cue, 'query': query, 'title': title, 'seconds': seconds, 'downloads': downloads,
                'author': attr(block, 'data-username'),
                'page': f'https://freesound.org/s/{sound_id}/', 'license': 'CC0-1.0',
                'licenseBasis': 'Freesound search filter license:"Creative Commons 0"',
                'file': str(target.relative_to(a.out)), 'preview': mp3.replace('-lq.mp3', '-hq.mp3'),
                'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            }
            time.sleep(0.4)
            taken += 1
            if len(found) >= spec['keep'] or taken >= per_query:
                break
    ledger[cue] = list(found.values())
    ledger_path.write_text(json.dumps(ledger, indent=1) + '\n')
    print(cue, len(found), 'candidates:', '; '.join(c['title'][:38] for c in found.values()), flush=True)
