#!/usr/bin/env python3
"""E5 motion-proof metrics for a blendproof run with -VeyrGreystoneMotionProof (no engine).

Per sequence:
  - foot slide: the proof's own VEYR_GATE numbers (planted toe/ankle speed over 1/30 s; gate 60 cm/s), split into
    steady and inside-blend;
  - pose jump at every shown-clip change: the largest one-frame pop of toes, ankles and weapon hand relative to the
    capsule (the frame's step against the steps on both sides, smaller difference; same rule as switch_jumps.py),
    at the change frame and the 3 after it;
  - response: input on (action phase start) -> first matched switch (VEYR_MOTION_SWITCH) and -> capsule at 100 cm/s;
    input off (post-idle start) -> first switch and -> capsule under 30 cm/s;
  - the clips shown, in order.

usage: motion_proof.py <Evidence/native-blendproof-*> [--json out.json]
"""
import argparse
import glob
import json
import math
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('run', type=Path)
p.add_argument('--json', type=Path)
a = p.parse_args()
frames = [json.loads(line) for line in open(glob.glob(str(a.run / 'unreal-*' / 'blendproof-frames.jsonl'))[0])]
log = (a.run / 'native.log').read_text(errors='replace')
switch_t = [float(m.group(1)) for m in re.finditer(r'VEYR_MOTION_SWITCH t=([0-9.]+)', log)]
gates = {int(m.group(1)): m.group(0) for m in re.finditer(r'VEYR_GATE blendproof seq=(\d+) [^\n]*', log)}
POINTS = ('toeL', 'toeR', 'ankleL', 'ankleR', 'hand')


def rel(x, key):
    v, c = x.get(key), x['capsule']
    return None if not v or v == [0, 0, 0] else tuple(v[i] - c[i] for i in range(3))


def pop(r, i, key):
    def step(j):
        A, B = rel(r[j - 1], key), rel(r[j], key)
        return None if A is None or B is None else tuple(B[k] - A[k] for k in range(3))
    if i < 2 or i + 1 >= len(r):
        return 0.0
    s0, s1, s2 = step(i - 1), step(i), step(i + 1)
    if None in (s0, s1, s2):
        return 0.0
    d = lambda u, v: math.sqrt(sum((u[k] - v[k]) ** 2 for k in range(3)))
    return min(d(s1, s0), d(s1, s2))


def first(ts, after):
    later = [t for t in ts if t >= after]
    return round(later[0] - after, 3) if later else None


report = {}
for seq in sorted({x['seq'] for x in frames}):
    r = [x for x in frames if x['seq'] == seq]
    name = r[0].get('sequence')
    on = next((x['t'] for x in r if x['phase'] == 'action'), None)
    off = next((x['t'] for x in r if x['phase'] == 'post_idle'), None)
    speed_on = next((x['t'] for x in r if on is not None and x['t'] >= on and x['speedCmPerSecond'] >= 100), None)
    speed_off = next((x['t'] for x in r if off is not None and x['t'] >= off and x['speedCmPerSecond'] < 30), None)
    changes, clips = [], []
    for i, x in enumerate(r):
        if not clips or clips[-1] != x['clip']:
            clips.append(x['clip'])
        if i and x['clip'] != r[i - 1]['clip']:
            worst, where = 0.0, ''
            for j in range(i, min(i + 4, len(r))):
                for k in POINTS:
                    v = pop(r, j, k)
                    if v > worst:
                        worst, where = v, k
            changes.append({'t': round(x['t'], 3), 'from': r[i - 1]['clip'], 'to': x['clip'], 'popCm': round(worst, 2), 'at': where})
    g = gates.get(seq, '')
    num = lambda key: float(m.group(1)) if (m := re.search(key + r'=([0-9.]+)', g)) else None
    report[name] = {
        'gate': 'PASS' if ' PASS ' in g else 'FAIL' if g else 'missing',
        'footSlideMaxCmPerSecond': num('footSlideMaxCmPerSecond'),
        'footSlideSteadyCmPerSecond': num('footSlideSteadyCmPerSecond'),
        'footSlideTransitionCmPerSecond': num('footSlideTransitionCmPerSecond'),
        'clipChanges': changes,
        'worstPopCm': max([c['popCm'] for c in changes], default=0.0),
        'responseInputOnToSwitchS': first(switch_t, on) if on is not None else None,
        'responseInputOnToMovingS': round(speed_on - on, 3) if speed_on and on is not None else None,
        'responseInputOffToSwitchS': first(switch_t, off) if off is not None else None,
        'responseInputOffToStoppedS': round(speed_off - off, 3) if speed_off and off is not None else None,
        'clipsShown': clips,
    }
    s = report[name]
    print(f"{name}: {s['gate']} slide max/steady/blend {s['footSlideMaxCmPerSecond']}/{s['footSlideSteadyCmPerSecond']}/"
          f"{s['footSlideTransitionCmPerSecond']} cm/s; worst pop {s['worstPopCm']} cm over {len(changes)} changes; "
          f"on->switch {s['responseInputOnToSwitchS']} s, on->moving {s['responseInputOnToMovingS']} s, "
          f"off->switch {s['responseInputOffToSwitchS']} s, off->stopped {s['responseInputOffToStoppedS']} s; clips {' > '.join(clips)}")
print(f'switches logged: {len(switch_t)}')
if a.json:
    a.json.write_text(json.dumps(report, indent=1) + '\n')
