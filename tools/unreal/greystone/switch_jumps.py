#!/usr/bin/env python3
"""Clip-switch jump check for a blendproof run (no engine).

For every clip switch (the proof's transition serial changes) it takes the switch frame and the next three, and
reports the largest one-frame pop of each toe, ankle and the weapon hand relative to the capsule: how far the frame's
step differs from the steps on both sides (the smaller difference), so travel, fast smooth motion and the velocity
kink where a linear cross-fade starts do not count. The E3 rule (coordinator 2026-11-19): no one-frame jump over 5 cm at a clip switch, and cross-fades happen.

usage: switch_jumps.py <Evidence/native-blendproof-*> [--limit-cm 5]
"""
import argparse
import glob
import json
import math
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('run', type=Path)
p.add_argument('--limit-cm', type=float, default=5.0)
a = p.parse_args()
frames_file = glob.glob(str(a.run / 'unreal-*' / 'blendproof-frames.jsonl'))
if not frames_file:
    raise SystemExit('no blendproof-frames.jsonl under ' + str(a.run))
rows = [json.loads(line) for line in open(frames_file[0])]


def rel(x, key):
    v, c = x.get(key), x['capsule']
    return None if not v or v == [0, 0, 0] else (v[0] - c[0], v[1] - c[1], v[2] - c[2])


points = ('toeL', 'toeR', 'ankleL', 'ankleR', 'hand')
report = {'limitCm': a.limit_cm, 'sequences': {}}
worst_all = 0.0
for seq in sorted({x['seq'] for x in rows}):
    r = [x for x in rows if x['seq'] == seq]
    switches = []
    for i in range(1, len(r)):
        if r[i]['transition'] != r[i - 1]['transition']:
            worst, where = 0.0, ''
            for j in range(max(i, 2), min(i + 4, len(r) - 1)):
                for k in points:
                    q = [rel(r[n], k) for n in (j - 2, j - 1, j, j + 1)]
                    if all(q):
                        # pop = this frame's step differs from the steps on BOTH sides (min of the two differences):
                        # fast smooth motion and the velocity kink where a linear cross-fade starts do not count
                        step = [tuple(q[m + 1][c] - q[m][c] for c in range(3)) for m in range(3)]
                        d = min(math.dist(step[1], step[0]), math.dist(step[1], step[2]))
                        if d > worst:
                            worst, where = d, f'{k} t={r[j]["t"]:.3f}'
            blended = any(r[j]['blending'] for j in range(i, min(i + 30, len(r))))
            switches.append({'t': round(r[i]['t'], 3), 'from': r[i]['blendFrom'], 'to': r[i]['clip'],
                             'crossFaded': blended, 'maxOneFrameJumpCm': round(worst, 2), 'at': where})
            worst_all = max(worst_all, worst)
    report['sequences'][r[0]['sequence']] = {
        'switches': switches,
        'blendingFrames': sum(1 for x in r if x['blending']),
        'frames': len(r)}
report['worstJumpCm'] = round(worst_all, 2)
report['pass'] = worst_all <= a.limit_cm and all(
    s['crossFaded'] for q in report['sequences'].values() for s in q['switches'] if s['from'] != s['to'])
out = a.run / 'switch-jumps.json'
out.write_text(json.dumps(report, indent=1) + '\n')
for name, q in report['sequences'].items():
    print(name, 'blendingFrames', q['blendingFrames'])
    for s in q['switches']:
        print(f"  t={s['t']:.2f} {s['from']} -> {s['to']} crossFaded={s['crossFaded']} jump={s['maxOneFrameJumpCm']} cm ({s['at']})")
print('worst', report['worstJumpCm'], 'cm; pass', report['pass'], '->', out)
