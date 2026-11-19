#!/usr/bin/env python3
"""Onset density and spectrum of a mix (film or wav): where its hits, stomps and roars are and how they sound.

    ~/.cache/earshot/venv/bin/python tools/audio/onset_profile.py <media> [--from S --to S] [--min-rise 12] [--label name]

Onset = the broadband level of a 33 ms window rises at least --min-rise dB above the median of the 15 windows before it (events at least 0.25 s apart).
Reported: onsets per minute, the distribution of the rise (median, p90), and for the strongest 20 onsets the per-band rise
(<200 Hz, 200 Hz-2 kHz, 2-8 kHz) and the spectral centroid of the 150 ms after the onset; an octave-band level profile (dB re the mix's loudest band)
averaged over those onsets, so two mixes can be laid side by side.
"""
import argparse, subprocess, tempfile, wave, json
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('media'); ap.add_argument('--from', dest='t0', type=float, default=0); ap.add_argument('--to', dest='t1', type=float, default=1e9)
ap.add_argument('--min-rise', type=float, default=12.0); ap.add_argument('--label', default=''); ap.add_argument('--json')
a = ap.parse_args()
p = Path(a.media)
if p.suffix.lower() != '.wav':
    t = Path(tempfile.mkdtemp()) / 'a.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.media, '-vn', '-ac', '1', '-ar', '48000', str(t)], check=True); p = t
w = wave.open(str(p)); sr = w.getframerate(); ch = w.getnchannels()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, ch).astype(float).mean(1) / 32768
i0, i1 = int(a.t0 * sr), min(len(x), int(min(a.t1, 1e8) * sr)); x = x[i0:i1]; base = i0 / sr
N = int(.033 * sr); n = len(x) // N
lv = 10 * np.log10((x[:n * N].reshape(n, N) ** 2).mean(1) + 1e-12)
ons = []; last = -1
for k in range(16, n):
    r = lv[k] - np.median(lv[k - 15:k])
    if r >= a.min_rise and (last < 0 or (k - last) * N / sr >= .25):
        ons.append((k, r)); last = k
secs = n * N / sr
print(f"{a.label or a.media}: {secs:.0f} s, {len(ons)} onsets >= {a.min_rise} dB ({len(ons)/secs*60:.1f}/min)")
if not ons: raise SystemExit
rs = np.array([r for _, r in ons]); print(f'  rise median {np.median(rs):.1f} dB, p90 {np.percentile(rs,90):.1f}, max {rs.max():.1f}')
BANDS = ((20, 200), (200, 2000), (2000, 8000)); OCT = [(31, 63), (63, 125), (125, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 8000), (8000, 16000)]
def spec(seg):
    s = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 8192)) ** 2; f = np.fft.rfftfreq(8192, 1 / sr); return s, f
def bl(seg):
    s, f = spec(seg); return np.array([10 * np.log10(s[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in BANDS])
top = sorted(ons, key=lambda o: -o[1])[:20]
br, cen, oct_ = [], [], []
for k, r in top:
    i = k * N
    if i - 16 * N < 0 or i + int(.15 * sr) > len(x): continue
    br.append(bl(x[i:i + N]) - np.median([bl(x[i - j * N:i - (j - 1) * N]) for j in range(1, 16)], axis=0))
    s, f = spec(x[i:i + int(.15 * sr)]); cen.append((f * s).sum() / s.sum())
    oct_.append([10 * np.log10(s[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in OCT])
br = np.array(br); oct_ = np.mean(oct_, axis=0)
print(f'  strongest 20: band rise median <200 {np.median(br[:,0]):+.0f}, 200-2k {np.median(br[:,1]):+.0f}, 2-8k {np.median(br[:,2]):+.0f} dB; share >=25 dB in all bands {np.mean(np.all(br>=25,axis=1))*100:.0f}%; centroid {np.median(cen):.0f} Hz')
print('  octave profile of onsets (dB re peak octave): ' + ' '.join(f'{lo}:{v-oct_.max():+.0f}' for (lo, _), v in zip(OCT, oct_)))
if a.json: Path(a.json).write_text(json.dumps({'onsPerMin': len(ons)/secs*60, 'riseMedian': float(np.median(rs)), 'riseP90': float(np.percentile(rs, 90)), 'bandRiseMedian': np.median(br, axis=0).tolist(), 'centroid': float(np.median(cen)), 'octave': (oct_-oct_.max()).tolist()}))
