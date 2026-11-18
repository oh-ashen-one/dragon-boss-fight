#!/usr/bin/env python3
"""Pick, cut, check and level the game's recorded sound set from the Freesound CC0 candidates.

Run with the Earshot environment's Python (CPU-local audio models; nothing is uploaded):
  ~/.cache/earshot/venv/bin/python tools/audio/prepare_recorded_set.py Local/AudioSources20261118 \
      --output Unreal/Veyr/Content/Audio/Recorded20261118 --receipt docs/audio-20261118/recorded-set.json

Per cue:
  1. candidates whose sound does not match the cue's description are dropped (Earshot rank, a content check only);
  2. the best-matching moments inside each remaining file are cut out (Earshot find);
  3. every cut is measured by our own checks: head silence is trimmed, then it is rejected if it is cut off at the
     tail, clipped, mostly silence, noisy, too short, or if its peak sits in the wrong place for the cue type;
  4. cuts are re-ranked; creature cues also drop cuts that sound like a human voice; the best cuts are taken from
     as many different recordings as possible;
  5. variants of one cue are levelled to the same event RMS (within 1.5 dB); the target is the level of the sound the
     game plays today for that cue where there is one, so the wiring volumes stay valid.
Output is 24 kHz mono 16-bit PCM named <Cue>_<n>.pcm (what AVeyrAudio reads) plus a receipt with provenance,
measurements and per-cue levels. A model match is a content check, not a listening approval.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks, resample_poly

import earshot

RATE = 24000
OLD_DIRS = ['Overhaul', 'Polish20261102', 'DragonLibrary20261103']

# name: (description, shape, variants, longest cut s, tail after event s, peak ceiling dBFS, extras)
#   shape 'hit'   : attack first; the peak must sit in the first half of the cut
#         'swell' : whoosh / breath / growl; the peak must sit between 8 % and 85 %
#         'any'   : crashes, rubble, booms: no rule about where the peak is
#         'loop'  : steady texture, made loopable with a cross-fade
#   extras: voice=True drops human-sounding cuts; old=<name of the sound the game plays today>
CUES = {
    'Swing':           ('a sword swinging fast through the air, a short whoosh', 'swell', 6, 0.60, 0.30, -3, {'old': 'Swing', 'min': 0.20}),
    'HeavySwing':      ('a heavy weapon swung through the air, a deep whoosh', 'swell', 5, 0.90, 0.50, -3, {'old': 'HeavySwing', 'min': 0.40}),
    'Contact':         ('a sword blade cutting into flesh, a wet slash impact', 'hit', 6, 0.70, 0.40, -2, {'old': 'Contact', 'peakBy': 0.10, 'attackMs': 60}),
    'Guard':           ('two metal swords clashing, a metal clang', 'hit', 5, 0.80, 0.55, -3, {'old': 'Guard', 'peakBy': 0.08, 'attackMs': 40}),
    'ArmorHit':        ('a heavy blow hitting metal armor, a metal thud', 'hit', 5, 0.80, 0.50, -2, {'peakBy': 0.10, 'attackMs': 60}),
    'Impact':          ('a very heavy object slamming into the ground, a deep thud', 'hit', 5, 1.80, 1.30, -1, {'old': 'Impact', 'pulses': 2, 'longTail': True, 'min': 0.6, 'peakBy': 0.15, 'attackMs': 70, 'alsoFrom': ['Exposed', 'Break', 'DragonStep']}),
    'DragonStep':      ('the footstep of a giant creature, a deep heavy thud', 'hit', 6, 0.80, 0.60, -1, {'pulses': 1, 'peakBy': 0.15, 'attackMs': 70, 'min': 0.3, 'longTail': True, 'pitch': 0.7, 'alsoFrom': ['Impact', 'Exposed', 'Footstep', 'Break'], 'distinctFrom': ['Impact', 'Exposed']}),
    'DragonSwing':     ('a big heavy whoosh of something large swinging through the air', 'swell', 5, 1.30, 0.80, -3, {'min': 0.45, 'pitch': 0.8}),
    'Bite':            ('a sharp bite, jaws snapping shut with a crunch', 'hit', 4, 0.80, 0.50, -2, {'peakBy': 0.20, 'attackMs': 80, 'pitch': 0.85}),
    'Breath':          ('fire igniting with a whoosh, a burst of flame', 'swell', 4, 1.60, 1.20, -3, {'old': 'Breath'}),
    'Fire':            ('a roaring stream of fire, a flamethrower', 'loop', 3, 3.20, 0.0, -3, {'old': 'Fire'}),
    'Wing':            ('one flap of very large wings', 'swell', 5, 0.90, 0.60, -3, {'old': 'Wing', 'pulses': 3, 'pitch': 0.85}),
    'Roll':            ('cloth and armor rustling as a person moves quickly', 'swell', 5, 0.60, 0.40, -6, {'old': 'Roll'}),
    'Footstep':        ('a single footstep of a boot on stone', 'hit', 10, 0.40, 0.28, -6, {'old': 'Footstep', 'peakBy': 0.07, 'attackMs': 30}),
    'Blink':           ('a short magical whoosh, air rushing', 'swell', 4, 0.90, 0.60, -6, {'old': 'Blink'}),
    'Break':           ('stone breaking and crumbling, rubble falling', 'any', 5, 1.50, 1.10, -3, {'old': 'Break', 'min': 0.5, 'longTail': True}),
    'Debris':          ('small stones and rubble falling and scattering on a stone floor', 'any', 5, 1.20, 0.90, -4, {'min': 0.4, 'longTail': True, 'distinctFrom': ['Break']}),
    'Exposed':         ('a heavy body falling and hitting the ground with a thud', 'hit', 4, 2.00, 1.50, -1, {'old': 'Exposed', 'pulses': 2, 'alsoFrom': ['Impact', 'Death', 'Break'], 'longTail': True, 'min': 0.7, 'peakBy': 0.25, 'attackMs': 80}),
    'Death':           ('a person in armor falling to the ground', 'hit', 4, 1.60, 1.20, -2, {'old': 'Death', 'pulses': 2, 'longTail': True, 'min': 0.5, 'peakBy': 0.30, 'attackMs': 90}),
    'Heal':            ('a person drinking and swallowing a liquid, gulping', 'swell', 3, 1.60, 1.10, -4, {'old': 'Heal', 'pulses': 4}),
    'Victory':         ('a deep drum hit or low brass blast, a cinematic boom', 'any', 3, 5.00, 4.00, -2, {'old': 'Victory', 'min': 1.0, 'tailDb': -10}),
    'DragonBreathIn':  ('a large animal slowly inhaling, a deep breath in through the nose', 'swell', 4, 2.80, 1.00, -5, {'voice': True, 'pulses': 1, 'min': 0.8}),
    'DragonBreathOut': ('a large animal slowly exhaling, a deep heavy breath out', 'swell', 4, 2.80, 1.00, -5, {'voice': True, 'pulses': 1, 'min': 0.45, 'alsoFrom': ['DragonBreathIn', 'DragonSnort']}),
    'DragonGrowlLow':  ('a low growl of a large predator, a deep rumbling animal growl', 'swell', 4, 3.00, 0.90, -3, {'voice': True}),
    'DragonSnort':     ('a large animal snorting, a short heavy snort', 'swell', 4, 1.20, 0.50, -3, {'voice': True}),
}
REJECT = 'a beep, a chime, a ding, a synthesizer tone, a video game jingle'
VOICE = 'a human voice speaking, shouting or screaming'

# ---------------------------------------------------------------- measuring


def db(x):
    return 20 * math.log10(max(float(x), 1e-9))


def decode(path):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map_metadata', '-1', '-ac', '1', '-ar', str(RATE),
                          '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype='<f4').astype(np.float64)


def envelope(x, ms=10):
    n = max(1, int(RATE * ms / 1000))
    return np.sqrt(np.convolve(x * x, np.ones(n) / n, mode='same'))


def active_rms_db(x):
    """RMS over the event: samples where the 10 ms envelope is within 25 dB of the loudest part."""
    env = envelope(x)
    mask = env > env.max() * 10 ** (-25 / 20)
    return db(math.sqrt(float(np.mean(x[mask] ** 2)))) if mask.any() else -120.0


def trim_head(x, shape):
    env = envelope(x, 5)
    # the cut belongs to the loudest event: start after the last quiet stretch before its peak
    peak = int(np.argmax(env))
    quiet = np.nonzero(env[:peak] < env.max() * 10 ** (-30 / 20))[0]
    if len(quiet):
        x, env = x[quiet[-1]:], env[quiet[-1]:]
    floor = env.max() * 10 ** ((-34 if shape == 'hit' else -30) / 20)
    first = int(np.argmax(env > floor))
    keep = max(0, first - int(0.006 * RATE))
    return x[keep:]


def trim_tail(x, floor_db=-30):
    """End the cut where the sound has died away after its peak (a second event after a gap is not ours)."""
    env = envelope(x, 8)
    peak = int(np.argmax(env))
    quiet = np.nonzero(env[peak:] < env.max() * 10 ** (floor_db / 20))[0]
    if len(quiet) == 0:
        return x
    return x[:peak + int(quiet[0]) + int(0.012 * RATE)]


def fade(x, head=0.003, tail=0.05):
    x = x.copy()
    h, t = max(1, int(head * RATE)), min(len(x) // 2, max(1, int(tail * RATE)))
    x[:h] *= np.linspace(0, 1, h)
    x[-t:] *= np.cos(np.linspace(0, math.pi / 2, t)) ** 2
    return x


def check(raw, shape, seconds_min, peak_by=0.10, attack_ms=40, max_pulses=2, lead_check=False, tail_limit=-20):
    """Return (ok, metrics, reason). raw is the cut before the tail fade, trimmed at the head."""
    n = len(raw)
    if n < seconds_min * RATE:
        return False, {}, 'too short'
    peak = float(np.max(np.abs(raw)))
    if peak < 1e-4:
        return False, {}, 'silent'
    env = envelope(raw)
    peak_at = int(np.argmax(env)) / RATE
    frac = peak_at / (n / RATE)
    frames = envelope(raw, 20)[::int(0.02 * RATE)]
    floor_db = db(np.percentile(frames, 15) / env.max())
    loud_share = float(np.mean(frames > env.max() * 10 ** (-30 / 20)))
    tail_db = db(math.sqrt(float(np.mean(raw[-int(0.04 * RATE):] ** 2))) / env.max())
    hot = (np.abs(raw) >= 0.985).astype(np.int8)
    # clipping = flat-topped runs (three or more hot samples in a row), not one lossy-decode overshoot
    clipped = int(np.sum((hot[:-2] & hot[1:-1] & hot[2:]) > 0)) if len(hot) > 3 else 0
    head_db = db(math.sqrt(float(np.mean(raw[:int(0.01 * RATE)] ** 2))) / env.max())
    fast = envelope(raw, 3)
    first = int(np.argmax(fast > fast.max() * 0.12))
    attack = (int(np.argmax(fast)) - first) / RATE * 1000
    spec = np.abs(np.fft.rfft(raw * np.hanning(len(raw)))) ** 2
    freqs = np.fft.rfftfreq(len(raw), 1 / RATE)
    audible = float(spec[freqs >= 130].sum() / max(spec.sum(), 1e-12))
    slow = envelope(raw, 50)
    pulses = len(find_peaks(slow, prominence=slow.max() * 0.25, distance=int(0.12 * RATE))[0])
    rms_all = active_rms_db(raw)
    crest = db(peak) - rms_all
    m = {'crestDb': round(crest, 1), 'pulses': pulses, 'attackMs': round(attack), 'above130HzShare': round(audible, 2), 'peakAtS': round(peak_at, 3), 'peakFrac': round(frac, 2), 'noiseFloorDb': round(floor_db, 1),
         'loudShare': round(loud_share, 2), 'tailDb': round(tail_db, 1), 'clippedSamples': clipped}
    if clipped > 40:
        return False, m, 'clipped in the source'
    if shape == 'hit' and (frac > 0.50 or peak_at > peak_by or attack > attack_ms):
        return False, m, 'attack not at the start'
    if shape == 'hit' and crest < 6.5:
        return False, m, 'flat, compressed or clipped body'
    lead_n = int(min(0.25, 0.4 * peak_at) * RATE)
    lead_db = db(math.sqrt(float(np.mean(raw[:lead_n] ** 2))) / env.max()) if lead_n > 0.05 * RATE else -99
    m['leadInDb'] = round(lead_db, 1)
    if lead_check and peak_at > 0.35 and lead_db > -26:
        return False, m, 'long noisy lead-in'
    if shape in ('swell', 'hit') and pulses > max_pulses:
        return False, m, 'several events in one cut'
    if audible < 0.10:
        return False, m, 'too low to hear on small speakers'
    if shape == 'swell' and not (0.08 <= frac <= 0.85):
        return False, m, 'peak at the edge'
    if shape != 'loop' and tail_db > tail_limit:
        return False, m, 'cut off at the tail'
    if shape != 'loop' and floor_db > -22 and shape == 'hit':
        return False, m, 'noisy: floor %.0f dB' % floor_db
    if shape == 'hit' and loud_share < 0.04 and n / RATE > 0.5:
        return False, m, 'mostly silence'
    if shape == 'loop' and floor_db < -30:
        return False, m, 'not steady'
    return True, m, ''


def make_loop(x, xfade=0.35):
    n = int(xfade * RATE)
    if len(x) < 4 * n:
        return x
    a = np.sin(np.linspace(0, math.pi / 2, n)) ** 1.0
    head, tail = x[:n], x[-n:]
    mixed = head * a + tail * np.sqrt(1 - a ** 2)  # equal-power
    return np.concatenate([mixed, x[n:-n]])


def soft_limit(x, knee=0.80):
    knee = min(knee, 0.97)
    y = x.copy()
    over = np.abs(y) > knee
    y[over] = np.sign(y[over]) * (knee + (1 - knee) * np.tanh((np.abs(y[over]) - knee) / (1 - knee)))
    return y


def old_level(root, name, code_tones=None):
    folders = [root / d for d in OLD_DIRS] + ([code_tones] if code_tones else [])
    for folder in folders:
        f = folder / (name + '.pcm')
        if f.exists() and f.stat().st_size > 400:
            x = np.frombuffer(f.read_bytes(), dtype='<i2').astype(np.float64) / 32768
            return active_rms_db(x), db(np.max(np.abs(x)))
    return None


# ---------------------------------------------------------------- main
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('sources', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--receipt', type=Path, required=True)
p.add_argument('--plan', type=Path, default=Path(__file__).with_name('recorded_set_plan.json'),
               help='plan file; its per-cue "exclude" lists the Freesound ids rejected after looking at the cuts')
p.add_argument('--only', help='comma-separated cue names')
p.add_argument('--audio-root', type=Path, default=None, help='Content/Audio folder holding the old sets (levels)')
a = p.parse_args()
audio_root = a.audio_root or a.output.parent
ledger = json.loads((a.sources / 'candidates.json').read_text())
plan = json.loads(a.plan.read_text())
a.output.mkdir(parents=True, exist_ok=True)
a.receipt.parent.mkdir(parents=True, exist_ok=True)
receipt = json.loads(a.receipt.read_text()) if a.receipt.exists() else {}
work = Path(tempfile.mkdtemp(prefix='veyr-audio-cuts-'))
# (Freesound page, start s) of every cut already given to a cue: no recording moment is used twice anywhere
rerun = set(a.only.split(',')) if a.only else set(CUES)
taken = [(v['page'], v['sourceStart']) for cue_name, info in receipt.items() if cue_name not in rerun for v in info['variants']]


def used(page, start):
    return any(page == p_ and abs(start - s_) < 0.35 for p_, s_ in taken)


def good(v):
    return v in ('strong', 'plausible')


for cue, (text, shape, variants, longest, tail, ceiling_db, extra) in CUES.items():
    if a.only and cue not in a.only.split(','):
        continue
    excluded = {str(i) for i in plan.get(cue, {}).get('exclude', [])}
    pool = list(ledger.get(cue, []))
    for other in extra.get('alsoFrom', []):  # sounds fetched for a related cue can serve this one too
        pool += ledger.get(other, [])
    for other in extra.get('distinctFrom', []):  # do not reuse a recording another cue already took
        excluded |= {v['page'].rstrip('/').rsplit('/', 1)[1] for v in receipt.get(other, {}).get('variants', [])}
    records = {c['file']: c for c in pool if c['id'] not in excluded}
    if extra.get('voice'):  # creature cues: a title that names a person is a human recording
        human = ('sigh', 'male', 'female', ' man', 'woman', 'human', 'person', 'gasp', 'scream', 'inhaler', 'candle', 'asthma',
                 'kid', 'child', 'girl', 'boy', 'voice', 'cough', 'yawn')
        records = {f: c for f, c in records.items() if not any(w in (' ' + c['title'].lower()) for w in human)}
    files = [str(a.sources / f) for f in records if (a.sources / f).exists()]
    if not files:
        print(cue, 'has no candidates', flush=True)
        continue
    ranked = earshot.rank(files, text)['results']
    kept = [r for r in ranked if good(r['verdict']) and not r.get('near_silent')]
    # Second chance for weak-ranked files: the model is a content check, our checks decide quality.
    rejected = {'multi': 0, 'tooShort': 0, 'cutOff': 0, 'clipped': 0, 'noisy': 0, 'silence': 0, 'edge': 0, 'attack': 0, 'other': 0}
    cuts = []
    min_len = extra.get('min', 0.08 if cue in ('Footstep', 'Bite', 'DragonSnort') else 0.15)
    for r in kept:
        source = Path(r['path'])
        samples = decode(source)
        total = len(samples) / RATE
        found = earshot.find(str(source), text, top=8, kind='texture' if shape == 'loop' else 'event',
                             win=longest if shape == 'loop' else None)
        segs = sorted((s for s in found['segments'] if good(s['verdict'])), key=lambda s: s['start'])
        starts = [s['start'] for s in sorted(found['segments'], key=lambda s: s['start'])]
        for seg in segs:
            begin = max(0.0, seg['start'] - 0.015)
            later = [t for t in starts if t > seg['start'] + 0.08]
            limit = min(total, (later[0] - 0.02) if later and shape == 'hit' and not extra.get('longTail') else total)
            piece, m, why, ok = None, {}, 'too short', False
            # a longer tail is tried when the first cut ends while the sound is still ringing
            for mult in ((1.0,) if shape == 'loop' else (1.0, 1.7, 2.6)):
                length = min(longest * (1 if mult == 1.0 else 1.5), max(seg['end'] + tail * mult, seg['start'] + 0.12) - begin,
                             limit - begin)
                piece = samples[int(begin * RATE):int((begin + length) * RATE)]
                if len(piece) < min_len * RATE:
                    why, ok = 'too short', False
                    continue
                piece = piece - float(np.mean(piece))
                if shape != 'loop':
                    piece = trim_tail(trim_head(piece, shape), -40 if extra.get('longTail') else -30)
                ok, m, why = check(piece, shape, min_len, extra.get('peakBy', 0.10), extra.get('attackMs', 40), extra.get('pulses', 3 if shape == 'hit' else 2),
                                lead_check=shape == 'hit' or bool(extra.get('voice')), tail_limit=extra.get('tailDb', -20))
                if ok or why not in ('cut off at the tail', 'too short'):
                    break
            if not ok:
                key = {'too short': 'tooShort', 'cut off at the tail': 'cutOff', 'clipped in the source': 'clipped',
                       'mostly silence': 'silence', 'peak at the edge': 'edge',
                       'attack not at the start': 'attack'}.get(why, 'noisy' if why.startswith('noisy') else 'other')
                rejected[key] += 1
                continue
            if shape == 'loop':
                piece = make_loop(piece)
                piece = fade(piece, 0.0, 0.0001)
            else:
                piece = fade(piece, 0.003, min(0.35 * len(piece) / RATE, 0.12 if shape == 'hit' else 0.25))
            target = work / f'{cue}-{source.stem}-{int(seg["start"] * 1000):06d}.wav'
            sf.write(target, piece, RATE, subtype='FLOAT')
            cuts.append({'wav': target, 'source': source, 'start': round(begin, 3), 'data': piece, 'metrics': m})
    if not cuts:
        print(cue, 'no usable cut;', len(kept), 'of', len(files), 'files matched; rejected', rejected, flush=True)
        receipt[cue] = {'description': text, 'candidates': len(files), 'matching': len(kept), 'variants': [],
                        'rejectedCuts': rejected}
        a.receipt.write_text(json.dumps(receipt, indent=1) + '\n')
        continue
    by_path = {str(c['wav']): c for c in cuts}
    again = earshot.rank(list(by_path), text)['results']
    beeps = {r['path']: r['z'] for r in earshot.rank(list(by_path), REJECT)['results']}
    voices = {r['path']: r['z'] for r in earshot.rank(list(by_path), VOICE)['results']} if extra.get('voice') else {}
    chosen, per_source = [], {}
    for limit in (1, 2, 3, 6):  # first one cut per recording, then more, so variants differ
        for r in again:
            c = by_path[r['path']]
            if c in chosen or not good(r['verdict']) or beeps.get(r['path'], -9) > r['z'] - 0.5:
                continue
            if voices and voices.get(r['path'], -9) > r['z'] - 0.5:
                continue
            if per_source.get(c['source'], 0) >= limit or len(chosen) >= variants:
                continue
            page = records[str(c['source'].relative_to(a.sources))]['page']
            if used(page, c['start']):
                continue
            c.update(z=round(r['z'], 2), verdict=r['verdict'], beepZ=round(beeps.get(r['path'], 0), 2),
                     voiceZ=round(voices.get(r['path'], 0), 2) if voices else None)
            chosen.append(c)
            taken.append((page, c['start']))
            per_source[c['source']] = per_source.get(c['source'], 0) + 1
    # ---- levelling: same event RMS for every variant, peaks under the ceiling
    pitch = extra.get('pitch', 1.0)  # a big creature: the recording is played slower (lower and longer), never generated
    for c in chosen:
        if pitch != 1.0:
            c['data'] = resample_poly(c['data'], 100, int(round(100 * pitch)))
        x = c['data']
        c['rmsDb'], c['peakDb'] = active_rms_db(x), db(np.max(np.abs(x)))
        c['crest'] = c['peakDb'] - c['rmsDb']
    old = old_level(audio_root, extra['old'], a.sources / '_code_tones') if extra.get('old') else None
    feasible = float(np.median([ceiling_db - c['crest'] for c in chosen])) if chosen else -20.0
    target_rms = feasible  # peak-limited level shared by all variants; the old level is only reported
    for c in chosen:
        gain = target_rms - c['rmsDb']
        y = soft_limit(c['data'] * 10 ** (gain / 20), 10 ** (ceiling_db / 20))
        c['final'] = y
        c['finalRmsDb'], c['finalPeakDb'] = active_rms_db(y), db(np.max(np.abs(y)))
    spread = max(c['finalRmsDb'] for c in chosen) - min(c['finalRmsDb'] for c in chosen) if chosen else 0
    for old_file in a.output.glob(cue + '_*.pcm'):
        old_file.unlink()
    out = []
    for index, c in enumerate(chosen, 1):
        pcm = np.clip(np.round(c['final'] * 32767), -32768, 32767).astype('<i2')
        target = a.output / f'{cue}_{index}.pcm'
        target.write_bytes(pcm.tobytes())
        origin = records[str(c['source'].relative_to(a.sources))]
        out.append({'file': target.name, 'seconds': round(len(pcm) / RATE, 3), 'sourceStart': c['start'],
                    'match': c['verdict'], 'matchZ': c['z'], 'beepZ': c['beepZ'], 'voiceZ': c['voiceZ'],
                    'rmsDb': round(c['finalRmsDb'], 1), 'peakDb': round(c['finalPeakDb'], 1),
                    'checks': c['metrics'], 'title': origin['title'], 'author': origin['author'],
                    'page': origin['page'], 'license': origin['license'], 'sourceSHA256': origin['sha256'],
                    'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    receipt[cue] = {'description': text, 'shape': shape, 'loop': shape == 'loop', 'candidates': len(files),
                    'matching': len(kept), 'cutsPassingChecks': len(cuts), 'rejectedCuts': rejected,
                    'levelRmsDb': round(target_rms, 1), 'levelSpreadDb': round(spread, 2),
                    'ceilingDb': ceiling_db, 'pitchFactor': pitch, 'oldGameLevelRmsDb': round(old[0], 1) if old else None,
                    'volumeToMatchOldLevel': round(10 ** ((old[0] - target_rms) / 20), 2) if old else None,
                    'variants': out}
    a.receipt.write_text(json.dumps(receipt, indent=1) + '\n')
    print(cue, f'{len(out)}/{variants} variants, {len({o["page"] for o in out})} recordings, spread {spread:.2f} dB, '
          f'rms {target_rms:.1f} dB (old {round(old[0], 1) if old else "-"}); {len(kept)}/{len(files)} files matched, '
          f'{len(cuts)} cuts passed; rejected {rejected}', flush=True)
