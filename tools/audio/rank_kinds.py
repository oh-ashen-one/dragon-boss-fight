#!/usr/bin/env python3
"""Per-kind loudness ranking in the REAL film audio (the blind critic's table), from the tap's events.

    ~/.cache/earshot/venv/bin/python tools/audio/rank_kinds.py <film.mp4|wav> <VeyrTap-N-cues.json> [--lag S]

Aligns the tap time to the film audio by onset-envelope correlation (or --lag), then for each event kind prints n, median full-band peak (dBFS, 0.25 s after
the event), median 2-8 kHz peak, median rise over the previous 0.5 s, sorted loudest first, and the span top to bottom, slam minus walking step, landing minus slam.
"""
import argparse, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt

ap = argparse.ArgumentParser(); ap.add_argument('media'); ap.add_argument('cues'); ap.add_argument('--lag', type=float)
a = ap.parse_args()
p = Path(a.media)
if p.suffix.lower() != '.wav':
    p2 = Path(tempfile.mkdtemp()) / 'a.wav'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.media, '-vn', '-ac', '2', '-ar', '48000', str(p2)], check=True); p = p2
def rd(q):
    w = wave.open(str(q)); sr = w.getframerate(); return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, w.getnchannels()).astype(float) / 32768, sr
r, sr = rd(p); d = json.loads(Path(a.cues).read_text())
lag = a.lag
if lag is None:
    t, st = rd(Path(a.cues).with_name(Path(a.cues).name.replace('-cues.json', '-mix.wav')))
    def env(x, s, h=.05):
        n = int(s * h); k = len(x) // n; return 10 * np.log10((x.mean(1)[:k * n].reshape(k, n) ** 2).mean(1) + 1e-10)
    dr = np.maximum(np.diff(env(r, sr)), 0); dt = np.maximum(np.diff(env(t, st)), 0); best = (-1, 0)
    for l in range(-600, 600):
        x, y = (dr[l:], dt) if l >= 0 else (dr, dt[-l:]); n = min(len(x), len(y))
        if n < 400: continue
        c = np.corrcoef(x[:n], y[:n])[0, 1]
        if c > best[0]: best = (c, l)
    lag = best[1] * .05; print(f'alignment correlation {best[0]:.2f}, lag {lag:+.2f} s')
sos = butter(4, [2000, 8000], btype='band', fs=sr, output='sos'); hi = sosfilt(sos, r.mean(1))
mono = r.mean(1)
pk = lambda x, i0, n: 20 * np.log10(np.abs(x[i0:i0 + n]).max() + 1e-9)
rows = {}
for e in d['events']:
    i = int((e['t'] + lag) * sr)
    if i < sr or i + int(.3 * sr) > len(mono): continue
    n = int(.25 * sr)
    full = pk(mono, i, n); high = pk(hi, i, n)
    pre = 10 * np.log10((mono[i - int(.5 * sr):i] ** 2).mean() + 1e-12); on = 10 * np.log10((mono[i:i + int(.033 * sr)] ** 2).mean() + 1e-12)
    rows.setdefault(e['kind'], []).append((full, high, on - pre))
print(f"{'kind':16} {'n':>4} {'peak dBFS':>10} {'2-8k peak':>10} {'rise dB':>8}")
med = {}
for k, v in sorted(rows.items(), key=lambda kv: -np.median([x[0] for x in kv[1]])):
    v = np.array(v); med[k] = np.median(v[:, 0]); print(f'{k:16} {len(v):4} {np.median(v[:,0]):10.1f} {np.median(v[:,1]):10.1f} {np.median(v[:,2]):8.1f}')
if med:
    print(f'span loudest to quietest kind: {max(med.values())-min(med.values()):.1f} dB')
    if 'dragonStomp' in med and 'dragonFootfall' in med: print(f"slam/stomp minus walking step: {med['dragonStomp']-med['dragonFootfall']:+.1f} dB")
    if 'dragonLanding' in med and 'dragonStomp' in med: print(f"landing minus slam/stomp: {med['dragonLanding']-med['dragonStomp']:+.1f} dB")
