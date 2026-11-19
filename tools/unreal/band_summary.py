#!/usr/bin/env python3
"""Quality goal band: wins/medians per grip and passive death times from suite records (Local/playtest-suite-*.json).

  band_summary.py <suite.json> [...]
Band (owner): every win within 150 s in both grips; medians within 15 % of 88 s (one-hand) and 73.5 s (two-hand);
passive player dead under 12 s.
"""
import json
import statistics
import sys

rows = []
for f in sys.argv[1:]:
    try:
        rows += json.load(open(f))
    except ValueError:  # a running suite's log: one JSON record per line
        rows += [json.loads(l[l.index('{'):]) for l in open(f) if l.lstrip().startswith('{"spec"')]
groups = {'one-hand': [], 'two-hand': [], 'passive': []}
for r in rows:
    spec = r.get('spec', '')
    seed = next((x.split('=')[1] for x in spec.split(',') if 'BrainSeed' in x), '0')
    t = r.get('terminalWallSeconds')
    if spec.startswith('death'):
        groups['passive'].append((seed, t, r.get('passed')))
    elif spec.startswith('victory'):
        groups['two-hand' if 'two-handed' in spec else 'one-hand'].append((seed, t, r.get('passed'), r.get('hitsTaken'), r.get('healsCompleted')))
target = {'one-hand': 88.0, 'two-hand': 73.5}
for g in ('one-hand', 'two-hand'):
    v = [x[1] for x in groups[g] if x[2] and x[1] is not None]
    if not v:
        continue
    med = statistics.median(v)
    print('%s: %d runs, %d wins, min %.1f median %.1f max %.1f, over 150 s: %s, median %+.1f %% of %.1f (band +-15 %%: %s)' % (
        g, len(groups[g]), len(v), min(v), med, max(v), [x[0] for x in groups[g] if x[1] and x[1] > 150 or not x[2]],
        100 * (med / target[g] - 1), target[g], 'OK' if abs(med / target[g] - 1) <= .15 else 'OUT'))
    print('   ', sorted((int(x[0]), round(x[1] or -1, 1)) for x in groups[g]))
p = [x[1] for x in groups['passive'] if x[1] is not None]
if p:
    print('passive: %s, max %.2f s (%s)' % ([round(x, 2) for x in p], max(p), 'OK' if max(p) < 12 else 'OVER 12 s'))
