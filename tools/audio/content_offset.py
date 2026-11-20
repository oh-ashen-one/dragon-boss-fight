#!/usr/bin/env python3
"""Film audio offset from content, for a run captured with a tap (-VeyrAudioTap): the master recording drops time while the game stalls,
so the clock-based offset in mux_film.py can be off by tenths of a second.

    ~/.cache/earshot/venv/bin/python tools/audio/content_offset.py <Evidence/native-*/unreal-*> <VeyrTap-1-cues.json> [--seconds 30]

Chain: master time <- tap time (local lag map, tap mix against the master), tap time -> game time (the tap's events), game time -> video
time (the frame manifest's requestedGameSeconds -> wallSeconds, plus the median capture delay is already in wallSeconds). Prints the
median (master time - video time) over the first --seconds of the fight: pass it to mux_film.py --offset.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent)); import offline_mix as om

ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('cues'); ap.add_argument('--seconds', type=float, default=30.0); a = ap.parse_args()
run = Path(a.run); d = json.loads(Path(a.cues).read_text())
wav = sorted((run.parent / 'master-audio').glob('*.wav'))[0]
x = om.rdwav(wav)[0]; t = om.rdwav(Path(a.cues).with_name(Path(a.cues).name.replace('-cues.json', '-mix.wav')))[0]
lag, lm = om.lag_map(x, t)
fr = [json.loads(l) for l in (run / 'native-video/frames.jsonl').read_text().splitlines() if l.strip()]
fr = [f for f in fr if f.get('type') == 'frame' and f.get('worldIndex', 0) == 0 and 'requestedGameSeconds' in f]
g = np.array([f['requestedGameSeconds'] for f in fr]); v = np.array([f['wallSeconds'] for f in fr])
ev = [e for e in d['events'] if 'gameT' in e]; ev.sort(key=lambda e: e['t'])
t0 = ev[0]['t']; offs = []
for e in ev:
    if e['t'] - t0 > a.seconds: break
    vt = float(np.interp(e['gameT'], g, v)); offs.append(e['t'] + lag(e['t']) - vt)
print(f'{len(offs)} events in the first {a.seconds:.0f} s: master minus video time median {np.median(offs):+.3f} s (p10 {np.percentile(offs,10):+.3f}, p90 {np.percentile(offs,90):+.3f})')
print(f'{np.median(offs):.4f}')
