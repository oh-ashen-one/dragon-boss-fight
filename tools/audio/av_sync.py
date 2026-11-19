#!/usr/bin/env python3
"""Offset of the game's sound to the picture for each tap event, from a film (video + master audio) and the tap's cue list.

    ~/.cache/earshot/venv/bin/python tools/audio/av_sync.py <film.mp4> <VeyrTap-N-cues.json> [--kinds weaponLight,weaponHeavy,weaponHead,dragonStomp,dragonLanding,knightStep,fireIgnition]
                                                          [--tap-to-film S] [--from S --to S]

1. tap time -> film time: if --tap-to-film is not given it is found by cross-correlating the tap mix's onset envelope with the film audio's.
2. per event: audio onset = largest 10 ms rise of the broadband level within +-200 ms of the (aligned) event time; picture onset = largest
   frame-to-frame rise of mean luma within +-200 ms; offset = audio minus picture, in ms and in frames.
Also prints, per kind, the onset rise per band measured in the REAL film audio (same method as analyze_mix.py).
"""
import argparse, json, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('film'); ap.add_argument('cues')
ap.add_argument('--kinds', default='weaponLight,weaponHeavy,weaponHead,dragonStomp,dragonLanding,knightStep,fireIgnition,hurt')
ap.add_argument('--tap-to-film', type=float)
ap.add_argument('--from', dest='t0', type=float, default=0); ap.add_argument('--to', dest='t1', type=float, default=1e9)
a = ap.parse_args()
tmp = Path(tempfile.mkdtemp())
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.film, '-vn', '-ac', '1', '-ar', '48000', str(tmp / 'a.wav')], check=True)
w = wave.open(str(tmp / 'a.wav')); sr = w.getframerate()
real = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
# luma per frame
pr = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', a.film], capture_output=True, text=True)
num, den = pr.stdout.strip().split('/'); fps = float(num) / float(den)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', a.film, '-vf', 'scale=64:36,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 36 * 64).astype(float)
luma = frames.mean(1); dluma = np.diff(luma, prepend=luma[0])
d = json.loads(Path(a.cues).read_text())
events = [(e['kind'], e['t']) for e in d['events']]

def env(x, hop=480):
    n = len(x) // hop
    return np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
# tap -> film alignment
off = a.tap_to_film
if off is None:
    tw = wave.open(str(Path(a.cues).with_name(Path(a.cues).name.replace('-cues.json', '-mix.wav'))))
    tx = np.frombuffer(tw.readframes(tw.getnframes()), dtype=np.int16).reshape(-1, 2).astype(float).mean(1) / 32768
    e1 = np.diff(np.log(env(real) + 1e-6)); e2 = np.diff(np.log(env(tx) + 1e-6))
    best = (-1, 0)
    for lag in range(-3000, 6000):  # 10 ms steps: tap time + lag*0.01 = film time
        if lag >= 0: a1, b1 = e1[lag:], e2
        else: a1, b1 = e1, e2[-lag:]
        n = min(len(a1), len(b1))
        if n < 500: continue
        c = np.corrcoef(a1[:n], b1[:n])[0, 1]
        if c > best[0]: best = (c, lag)
    off = best[1] * 0.01
    print(f'tap -> film time offset {off:.2f} s (envelope correlation {best[0]:.2f})')
BANDS = ((20, 200), (200, 2000), (2000, 8000)); N = int(.033 * sr)
def bands(seg):
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; f = np.fft.rfftfreq(len(seg), 1 / sr)
    return np.array([10 * np.log10(sp[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in BANDS])
def rise(t):
    i = int(t * sr)
    if i < 16 * N or i + N > len(real): return None
    return bands(real[i:i + N]) - np.median([bands(real[i - k * N:i - (k - 1) * N]) for k in range(1, 16)], axis=0)
print(f"{'kind':14} {'n':>4} {'<200':>6} {'200-2k':>7} {'2-8k':>6} {'all>=25':>8} {'audio-picture ms (median, p10..p90)':>38}")
for kind in a.kinds.split(','):
    ev = [t + off for k, t in events if k == kind and a.t0 <= t + off <= a.t1]
    rr, offs = [], []
    for t in ev:
        r_ = rise(t)
        if r_ is None: continue
        # audio onset: biggest 10 ms energy jump in +-0.2 s
        i0 = max(int((t - .2) * sr), 480); seg = real[i0:i0 + int(.4 * sr)]
        e = env(seg, 480)
        if len(e) < 4: continue
        j = int(np.argmax(np.diff(np.log(e))) + 1); ta = (i0 + j * 480) / sr
        f0 = max(int((t - .2) * fps), 1); f1 = min(int((t + .2) * fps) + 1, len(dluma))
        if f1 - f0 < 2: continue
        jf = f0 + int(np.argmax(dluma[f0:f1])); tp = jf / fps
        if dluma[jf] < 3: continue  # no visible flash
        rr.append(r_); offs.append((ta - tp) * 1000)
    if not rr: print(f'{kind:14} {len(ev):4}  (no usable events)'); continue
    arr = np.array(rr); med = np.median(arr, axis=0); o = np.array(offs)
    print(f'{kind:14} {len(rr):4} {med[0]:+6.1f} {med[1]:+7.1f} {med[2]:+6.1f} {np.mean(np.all(arr>=25,axis=1))*100:7.0f}% {np.median(o):+10.0f} ({np.percentile(o,10):+.0f}..{np.percentile(o,90):+.0f})  = {np.median(o)*fps/1000:+.1f} frames')
