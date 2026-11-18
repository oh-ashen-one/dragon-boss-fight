#!/usr/bin/env python3
"""Pick and cut the game's recorded sound set from the Freesound candidates.

Run with the Earshot environment's Python (CPU-local audio models; nothing is uploaded):
  ~/.cache/earshot/venv/bin/python tools/audio/prepare_recorded_set.py Local/AudioSources20261118 \
      --output Unreal/Veyr/Content/Audio/Recorded20261118 --receipt docs/audio-20261118/recorded-set.json

Per cue: candidates whose sound does not match the cue's description are dropped (a download titled
"sword swing" can be a chime); the best-matching moments inside each remaining file are cut out; the cuts
are ranked again and the best few, from as many different recordings as possible, become the cue's
variants. Output is 24 kHz mono 16-bit PCM named <Cue>_<n>.pcm, which is what AVeyrAudio reads.
A model match is a content check, not a listening approval: the owner's ear decides.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import earshot

RATE = 24000
# description, event|texture, variants, longest cut (s), tail kept after the event (s), peak level
CUES = {
    'Swing':       ('a sword swinging fast through the air, a short whoosh', 'event', 5, 0.60, 0.35, 0.70),
    'HeavySwing':  ('a heavy weapon swung through the air, a deep whoosh', 'event', 4, 0.90, 0.55, 0.75),
    'Contact':     ('a sword blade cutting into flesh, a wet slash impact', 'event', 5, 0.70, 0.45, 0.80),
    'Guard':       ('two metal swords clashing, a metal clang', 'event', 4, 0.80, 0.60, 0.70),
    'ArmorHit':    ('a heavy blow hitting metal armor, a metal thud', 'event', 4, 0.80, 0.55, 0.80),
    'Impact':      ('a very heavy object slamming into the ground, a deep thud', 'event', 4, 1.80, 1.40, 0.90),
    'DragonStep':  ('the footstep of a giant creature, a deep heavy thud', 'event', 5, 1.10, 0.85, 0.85),
    'DragonSwing': ('a huge object moving fast through the air, a big deep whoosh', 'event', 4, 1.30, 0.90, 0.80),
    'Bite':        ('a large animal biting, jaws snapping shut', 'event', 3, 0.80, 0.55, 0.80),
    'Breath':      ('fire igniting with a whoosh, a burst of flame', 'event', 3, 1.60, 1.30, 0.75),
    'Fire':        ('a roaring stream of fire, a flamethrower', 'texture', 3, 3.00, 0.0, 0.75),
    'Wing':        ('one flap of very large wings', 'event', 4, 0.90, 0.65, 0.75),
    'Roll':        ('cloth and armor rustling as a person moves quickly', 'event', 4, 0.60, 0.45, 0.55),
    'Footstep':    ('a single footstep of a boot on stone', 'event', 8, 0.40, 0.30, 0.60),
    'Blink':       ('a short magical whoosh, air rushing', 'event', 3, 0.90, 0.70, 0.60),
    'Break':       ('stone breaking and crumbling, rubble falling', 'event', 4, 1.50, 1.20, 0.80),
    'Exposed':     ('a huge heavy body falling to the ground with a crash', 'event', 3, 2.00, 1.60, 0.90),
    'Death':       ('a person in armor falling to the ground', 'event', 3, 1.60, 1.30, 0.75),
    'Heal':        ('a person drinking and swallowing a liquid, gulping', 'event', 2, 1.60, 1.20, 0.60),
    'Victory':     ('a deep cinematic orchestral hit with low brass', 'event', 2, 5.00, 4.50, 0.75),
}
REJECT = 'a beep, a chime, a ding, a synthesizer tone, a video game jingle'

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('sources', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--receipt', type=Path, required=True)
p.add_argument('--only', help='comma-separated cue names')
a = p.parse_args()
ledger = json.loads((a.sources / 'candidates.json').read_text())
a.output.mkdir(parents=True, exist_ok=True)
a.receipt.parent.mkdir(parents=True, exist_ok=True)
receipt = json.loads(a.receipt.read_text()) if a.receipt.exists() else {}
work = Path(tempfile.mkdtemp(prefix='veyr-audio-cuts-'))


def good(verdict):
    return verdict in ('strong', 'plausible')


def cut(source, start, length, target, tail_fade):
    fade = max(0.03, min(tail_fade, length * 0.5))
    chain = f'afade=t=in:d=0.004,afade=t=out:st={max(0.0, length - fade):.3f}:d={fade:.3f}'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{start:.3f}', '-t', f'{length:.3f}', '-i', str(source),
                    '-map_metadata', '-1', '-ac', '1', '-ar', str(RATE), '-af', chain, str(target)], check=True)


for cue, (text, kind, variants, longest, tail, peak) in CUES.items():
    if a.only and cue not in a.only.split(','):
        continue
    records = {c['file']: c for c in ledger.get(cue, [])}
    files = [str(a.sources / f) for f in records if (a.sources / f).exists()]
    if not files:
        print(cue, 'has no candidates', flush=True)
        continue
    kept = [r for r in earshot.rank(files, text)['results'] if good(r['verdict'])]
    cuts = []
    for ranked in kept:
        source = Path(ranked['path'])
        found = earshot.find(str(source), text, top=4, kind=kind, win=longest if kind == 'texture' else None)
        segments = sorted((s for s in found['segments'] if good(s['verdict'])), key=lambda s: s['start'])
        starts = [s['start'] for s in sorted(found['segments'], key=lambda s: s['start'])]
        for seg in segments:
            begin = max(0.0, seg['start'] - 0.012)
            later = [t for t in starts if t > seg['start'] + 0.08]
            limit = min(found['duration'], (later[0] - 0.02) if later and kind == 'event' else found['duration'])
            length = min(longest, max(seg['end'] + tail, seg['start'] + 0.12) - begin, limit - begin)
            if length < 0.10:
                continue
            target = work / f'{cue}-{source.stem}-{int(seg["start"] * 1000):06d}.wav'
            cut(source, begin, length, target, 0.35 * length)
            cuts.append({'wav': target, 'source': source, 'start': round(begin, 3), 'seconds': round(length, 3)})
    if not cuts:
        print(cue, 'no usable cut; kept', len(kept), 'of', len(files), 'files', flush=True)
        continue
    by_path = {str(c['wav']): c for c in cuts}
    again = earshot.rank(list(by_path), text)['results']
    beeps = {r['path']: r['z'] for r in earshot.rank(list(by_path), REJECT)['results']}
    chosen, per_source = [], {}
    for limit in (1, 2, 4):  # first one cut per recording, then a second, so variants differ
        for r in again:
            c = by_path[r['path']]
            if c in chosen or not good(r['verdict']) or beeps.get(r['path'], 0) > r['z']:
                continue
            if per_source.get(c['source'], 0) >= limit or len(chosen) >= variants:
                continue
            c.update(z=round(r['z'], 2), verdict=r['verdict'], beepZ=round(beeps.get(r['path'], 0), 2))
            chosen.append(c)
            per_source[c['source']] = per_source.get(c['source'], 0) + 1
    for old in a.output.glob(cue + '_*.pcm'):
        old.unlink()
    out = []
    for index, c in enumerate(chosen, 1):
        probe = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(c['wav']), '-af', 'volumedetect', '-f', 'null', '-'],
                               capture_output=True, text=True).stderr
        max_db = float(probe.split('max_volume:')[1].split('dB')[0])
        gain = 20 * __import__('math').log10(peak) - max_db
        target = a.output / f'{cue}_{index}.pcm'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(c['wav']), '-af', f'volume={gain:.2f}dB', '-ac', '1',
                        '-ar', str(RATE), '-c:a', 'pcm_s16le', '-f', 's16le', str(target)], check=True)
        origin = records[str(c['source'].relative_to(a.sources))]
        out.append({'file': target.name, 'seconds': c['seconds'], 'sourceStart': c['start'], 'match': c['verdict'],
                    'matchZ': c['z'], 'beepZ': c['beepZ'], 'title': origin['title'], 'author': origin['author'],
                    'page': origin['page'], 'license': origin['license'], 'sourceSHA256': origin['sha256'],
                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    receipt[cue] = {'description': text, 'candidates': len(files), 'matching': len(kept), 'variants': out}
    a.receipt.write_text(json.dumps(receipt, indent=1) + '\n')
    print(cue, f'{len(out)}/{variants} variants from {len({o["page"] for o in out})} recordings '
          f'({len(kept)} of {len(files)} candidates matched):', '; '.join(o['title'][:28] for o in out), flush=True)
