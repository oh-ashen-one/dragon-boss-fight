#!/usr/bin/env python3
"""Where the hit sound starts against the white flash, on the game's own clock and on the film's.

    ~/.cache/earshot/venv/bin/python tools/audio/hit_timing.py <film.mp4> <frames.jsonl> <VeyrTap-N-cues.json> [--lag S]

1. game clock: each weapon event in the tap carries the world time (gameT) at which the cue was requested; each captured frame carries requestedGameSeconds. The flash
   is the largest mean-luma jump within +-0.4 s of the event; cue minus flash, in game seconds and in frames, needs no audio at all.
2. film: the audio onset (largest 10 ms level jump within +-0.4 s of the aligned event) against the same flash frame's film time: this is what a viewer sees, and includes the
   capture's audio latency.
"""
import argparse, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('frames'); ap.add_argument('cues'); ap.add_argument('--lag', type=float)
a = ap.parse_args()
fr = [json.loads(l) for l in open(a.frames) if l.strip()]
fr = [f for f in fr if f.get('type') == 'frame' and f.get('worldIndex', 0) == 0]
gt_all = np.array([f['requestedGameSeconds'] for f in fr]); wall_all = np.array([f['wallSeconds'] for f in fr])
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', a.film, '-vf', 'scale=64:36,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
fl = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 36 * 64).astype(float).mean(1); dl = np.diff(fl, prepend=fl[0])
pts = np.array([float(v.strip(',')) for v in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts_time', '-of', 'csv=p=0', a.film], capture_output=True, text=True).stdout.split() if v.strip(',') not in ('', 'N/A')])
# the encoder may drop frames: map each film frame to the manifest frame whose capture wall time is nearest to its film time (film time = wall time minus the first frame's)
n = min(len(dl), len(pts)); dl, pts = dl[:n], pts[:n]
gt = np.array([gt_all[int(np.clip(np.searchsorted(wall_all - wall_all[0], t), 0, len(gt_all) - 1))] for t in pts])
fps = (n - 1) / (gt[-1] - gt[0])
d = json.loads(Path(a.cues).read_text())
ev = [e for e in d['events'] if e['kind'] in ('weaponLight', 'weaponHeavy', 'weaponHead')]
out = {}
for e in ev:
    i0 = int(np.searchsorted(gt, e['gameT'] - .4)); i1 = int(np.searchsorted(gt, e['gameT'] + .4))
    if i1 - i0 < 3: continue
    j = i0 + int(np.argmax(dl[i0:i1]))
    if dl[j] < 3: continue
    out.setdefault(e['kind'], []).append((e['gameT'] - gt[j], j, pts[j], e['t']))
print(f'{n} frames, {fps:.1f} fps on the game clock')
print(f"{'kind':12} {'n':>3} {'cue minus flash, game clock (median ms, p10..p90)':>52}   frames")
allv = []
for k, v in out.items():
    x = np.array([q[0] for q in v]) * 1000; allv += list(x)
    print(f'{k:12} {len(v):3} {np.median(x):+8.0f} ({np.percentile(x,10):+.0f}..{np.percentile(x,90):+.0f})   {np.median(x)*fps/1000:+.1f}')
if allv: print(f'all weapon hits: median {np.median(allv):+.0f} ms = {np.median(allv)*fps/1000:+.1f} frames (negative = the cue is requested before the flash frame was captured)')
# film side
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.film, '-vn', '-ac', '1', '-ar', '48000', '/tmp/ht.wav'], check=True)
w = wave.open('/tmp/ht.wav'); sr = w.getframerate(); r = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
lag = a.lag
if lag is None:
    tw = wave.open(str(Path(a.cues).with_name(Path(a.cues).name.replace('-cues.json', '-mix.wav')))); tx = np.frombuffer(tw.readframes(tw.getnframes()), dtype=np.int16).reshape(-1, 2).astype(float).mean(1) / 32768
    env = lambda x, s, h=.05: 10 * np.log10((x[:(len(x) // int(s * h)) * int(s * h)].reshape(-1, int(s * h)) ** 2).mean(1) + 1e-10)
    e1 = np.maximum(np.diff(env(r, sr)), 0); e2 = np.maximum(np.diff(env(tx, tw.getframerate())), 0); best = (-1, 0)
    for l in range(-600, 600):
        p, q = (e1[l:], e2) if l >= 0 else (e1, e2[-l:]); m = min(len(p), len(q))
        if m < 400: continue
        c = np.corrcoef(p[:m], q[:m])[0, 1]
        if c > best[0]: best = (c, l)
    lag = best[1] * .05
res = []
for k, v in out.items():
    for dg, j, tpts, tt in v:
        i0 = max(int((tpts - .35) * sr), 480); seg = r[i0:i0 + int(.7 * sr)]
        if len(seg) < 4800: continue
        e = 10 * np.log10((seg[:len(seg) // 480 * 480].reshape(-1, 480) ** 2).mean(1) + 1e-10)
        jj = int(np.argmax(np.diff(e)) + 1); res.append((i0 / sr + jj * .01 - tpts) * 1000)
if res: print(f'film audio onset minus flash frame (picture), same events: median {np.median(res):+.0f} ms (p10 {np.percentile(res,10):+.0f}, p90 {np.percentile(res,90):+.0f}) = {np.median(res)*fps/1000:+.1f} frames, n={len(res)}')
