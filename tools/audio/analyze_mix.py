#!/usr/bin/env python3
"""Loudness and onset analysis of a game mix, with the blind critic's method.

    ~/.cache/earshot/venv/bin/python tools/audio/analyze_mix.py <mix.wav|film.mp4> [--events cues.json] [--offset S] [--from S --to S]

Whole mix: integrated LUFS, loudness range, sample and true peak (ffmpeg ebur128).
Per event (from the tap's `events` list, or the DragonStep/Contact/Footstep items when absent): the onset rise in three bands
(below 200 Hz, 200 Hz to 2 kHz, 2 to 8 kHz) = band level of the 33 ms window starting at the event minus the median band level
of the 15 windows before it; grouped by event kind with the share of events that rise 25 dB or more in all three bands.
Consecutive same-kind events: spectral correlation (log-magnitude spectra of the 150 ms after the event), the number of pairs
at or above 0.8. --offset shifts event times (tap time to file time).
"""
import argparse, json, re, statistics, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('media')
ap.add_argument('--events')
ap.add_argument('--offset', type=float, default=0.0)
ap.add_argument('--from', dest='t0', type=float, default=0.0)
ap.add_argument('--to', dest='t1', type=float, default=1e9)
ap.add_argument('--json', help='write the result here')
a = ap.parse_args()

tmp = tempfile.mkdtemp()
wav = Path(a.media)
if wav.suffix.lower() != '.wav':
    wav = Path(tmp) / 'a.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.media, '-vn', '-ac', '2', '-ar', '48000', str(wav)], check=True)
import wave
w = wave.open(str(wav)); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, w.getnchannels()).astype(float) / 32768
m = x.mean(1)

# loudness
r = subprocess.run(['ffmpeg', '-nostats', '-i', str(wav), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
txt = r.stderr.split('Summary:')[-1]
def grab(pat):
    mm = re.search(pat, txt)
    return float(mm.group(1)) if mm else None
res = {'lufs': grab(r'I:\s+(-?[\d.]+) LUFS'), 'lra': grab(r'LRA:\s+(-?[\d.]+) LU'), 'truePeakDb': grab(r'Peak:\s+(-?[\d.]+) dBFS'),
       'samplePeakDb': float(20 * np.log10(max(np.abs(x).max(), 1e-6))), 'seconds': len(m) / sr}
print(f"{a.media}: {res['seconds']:.1f} s, integrated {res['lufs']} LUFS, LRA {res['lra']} LU, true peak {res['truePeakDb']} dBFS, sample peak {res['samplePeakDb']:.1f} dBFS")

BANDS = ((20, 200), (200, 2000), (2000, 8000))
def bands(seg):
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    return np.array([10 * np.log10(sp[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in BANDS])
N = int(.033 * sr)
def rise(t):
    i = int(t * sr)
    if i < 16 * N or i + N > len(m):
        return None
    on = bands(m[i:i + N])
    pre = np.median([bands(m[i - k * N:i - (k - 1) * N]) for k in range(1, 16)], axis=0)
    return on - pre
def spec(t):
    i = int(t * sr); seg = m[i:i + int(.15 * sr)]
    if len(seg) < int(.1 * sr):
        return None
    s = np.log10(np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 2048)) ** 2 + 1e-12)
    return s - s.mean()

events = []
if a.events:
    d = json.loads(Path(a.events).read_text())
    if d.get('events'):
        events = [(e['kind'], e['t'] + a.offset) for e in d['events']]
    else:
        kind = {'Contact': 'weaponContact', 'DragonStep': 'dragonStep', 'Footstep': 'knightStep', 'Exposed': 'bodyFall', 'Fire': 'fire', 'ArmorHit': 'hurt'}
        events = [(kind[i['cue']], i['t'] + a.offset) for i in d['items'] if i['cue'] in kind]
events = [(k, t) for k, t in sorted(events, key=lambda e: e[1]) if a.t0 <= t <= a.t1]
byk = {}
for k, t in events:
    rr = rise(t)
    if rr is not None:
        byk.setdefault(k, []).append((t, rr))
print(f"{'event kind':16} {'n':>4} {'<200Hz':>7} {'200-2k':>7} {'2-8k':>7}  {'>=25 dB all bands':>18}")
res['events'] = {}
for k, v in sorted(byk.items()):
    arr = np.array([r_ for _, r_ in v])
    med = np.median(arr, axis=0); good = float(np.mean(np.all(arr >= 25, axis=1)))
    print(f'{k:16} {len(v):4} {med[0]:+7.1f} {med[1]:+7.1f} {med[2]:+7.1f}  {good*100:17.0f}%')
    res['events'][k] = {'n': len(v), 'medianRiseDb': med.round(1).tolist(), 'shareAll25': round(good, 2)}
    # spectral correlation of consecutive events of this kind
    sp = [(t, spec(t)) for t, _ in v]
    sp = [(t, s) for t, s in sp if s is not None]
    cors = [float(np.corrcoef(s1, s2)[0, 1]) for (t1, s1), (t2, s2) in zip(sp, sp[1:]) if t2 - t1 < 3.0]
    if cors:
        print(f"{'':16}      consecutive spectral correlation: median {statistics.median(cors):.2f}, {sum(c >= .8 for c in cors)}/{len(cors)} pairs >= 0.8")
        res['events'][k]['specCorrMedian'] = round(statistics.median(cors), 2)
        res['events'][k]['pairsAt08'] = [sum(c >= .8 for c in cors), len(cors)]
if a.json:
    Path(a.json).write_text(json.dumps(res, indent=1))
