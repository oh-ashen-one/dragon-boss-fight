#!/usr/bin/env python3
"""Fight-tap checks (B2, B3) on VeyrTap-cues.json from `-VeyrAudioTap=<dir>` during a scripted fight.

    python3 tools/audio/check_fight.py <dir-or-json>

Reports: cue counts; dragon footfalls (contacts -> DragonStep cue: same-frame latency in frames, and the step time against
the sole-clearance minimum in the per-frame trace); knight footsteps against the foot-bone height minima; breathing cadence;
hit layers (ArmorHit with PlayerPain within 0.1 s); timed move sounds (DragonSwing / Bite / BreathIn per move).
Frame = median dt of the trace.
"""
import json, statistics, sys
from collections import Counter
from pathlib import Path

p = Path(sys.argv[1])
if p.is_dir():
    # one file set per world session (a replay may restart the world); take the longest unless a file is named
    sets = sorted(p.glob('VeyrTap-*-cues.json'), key=lambda f: json.loads(f.read_text())['seconds'])
    p = sets[-1] if sets else p / 'VeyrTap-cues.json'
d = json.loads(p.read_text())
items, contacts, tr = d['items'], d.get('contacts', []), d.get('trace', {})
t = tr.get('t', [])
dt = statistics.median(tr['dt']) if tr.get('dt') else 1 / 60
print(f"{p}: {d['seconds']:.1f} s, frame {dt*1000:.1f} ms, newSet={d['newSet']}, master peak {d['masterPeakDb']:.1f} dBFS, clipped {d['clippedSamples']}")
cnt = Counter(i['cue'] for i in items)
print('cue counts:', dict(sorted(cnt.items())))
for cue, c in sorted(d['cues'].items()):
    print(f"  {cue:16} {c['events']:4} events, {c['variantsUsed']}/{c['variantsLoaded']} variants, b2b {c['backToBackRepeats']}, peak {c['maxPeakDb']:.1f} dBFS, over music {c.get('minAboveMusicDb', float('nan')):+.1f} dB")


def plateau(name, when, win, tol):
    """first time within +-win of `when` that the series is within tol cm of its lowest value there (foot has arrived)"""
    idx = [i for i, x in enumerate(t) if abs(x - when) <= win and tr[name][i] is not None and tr[name][i] > -50]
    if not idx:
        return None
    m = min(tr[name][i] for i in idx)
    for i in idx:
        if tr[name][i] <= m + tol:
            return t[i]


def stats(name, offs):
    if not offs:
        print(f'{name}: none'); return
    fr = sorted(o / dt for o in offs)
    print(f"{name}: n={len(fr)} frames after arrival: p10 {fr[len(fr)//10]:+.1f}, median {statistics.median(fr):+.1f}, p90 {fr[9*len(fr)//10]:+.1f}, max abs {max(abs(x) for x in fr):.1f}")


# dragon footfalls
foot = [c for c in contacts if c['part'] == 0]
lat, off = [], []
miss = Counter()
for c in foot:
    lat.append(c['handledGameTime'] - c['gameTime'])
    steps = [items[k] for k in range(c['itemFrom'], c['itemTo']) if items[k]['cue'] == 'DragonStep']
    if not steps:
        miss[c['class']] += 1
    elif c['leg'] >= 0 and tr.get(f"foot{c['leg']}"):
        m = plateau(f"foot{c['leg']}", steps[0]['t'], .35, .5)
        if m is not None:
            off.append(steps[0]['t'] - m)
print(f"dragon foot contacts {len(foot)}: without a DragonStep cue {sum(miss.values())} by class {dict(miss)} (class 3 = landing, one cue per landing)")
stats('  contact -> cue handled, game-time lag', lat)
stats('  DragonStep cue vs sole clearance reaching its floor level (+-0.35 s window, 0.5 cm)', off)
print('  contacts by class (0 foot 1 stomp 2 body 3 landing):', dict(Counter(c['class'] for c in contacts)))

# knight steps
ks = [i for i in items if i['cue'] == 'Footstep']
offs = []
for s in ks:
    cands = [m for m in (plateau('kneeL', s['t'], .2, .75), plateau('kneeR', s['t'], .2, .75)) if m is not None]
    if cands:
        offs.append(s['t'] - min(cands, key=lambda m: abs(m - s['t'])))
print(f'knight steps {len(ks)}')
stats('  step vs foot bone reaching its floor level (+-0.2 s window, 0.75 cm)', offs)
if len(ks) > 2:
    gaps = [b['t'] - a['t'] for a, b in zip(ks, ks[1:]) if b['t'] - a['t'] < 1.5]
    print(f"  step spacing median {statistics.median(gaps):.2f} s" if gaps else '')

# breathing
br = [i for i in items if i['cue'] in ('DragonBreathIn', 'DragonBreathOut')]
alt = sum(1 for a, b in zip(br, br[1:]) if a['cue'] != b['cue'])
cyc = [b['t'] - a['t'] for a, b in zip(br, br[1:]) if a['cue'] == b['cue']]
print(f"breaths {len(br)}, alternating pairs {alt}/{max(len(br)-1,0)}, cycle (in to next in) median {statistics.median(cyc):.1f} s" if cyc else f'breaths {len(br)}')

# hit layers
am = [i for i in items if i['cue'] == 'ArmorHit']
pn = [i for i in items if i['cue'] == 'PlayerPain']
paired = sum(1 for a in am if any(0 <= p_['t'] - a['t'] < .1 for p_ in pn))
print(f'hit layers: ArmorHit {len(am)}, PlayerPain {len(pn)}, ArmorHit with a PlayerPain within 0.1 s {paired}')

# timed dragon sounds per clip (label "<clip>@<p|t><value>": phase or clip seconds when it fired)
tim = {}
for i in items:
    if i.get('label'):
        clip, at = i['label'].split('@')
        tim.setdefault(clip, []).append((i['cue'], float(at[1:]), at[0]))
print('timed dragon sounds fired, by clip (cue@position):')
for clip, ev in sorted(tim.items()):
    print(f"  {clip:16} {len(ev):3}  " + ', '.join(sorted({f"{c}@{a:.2f}" for c, a, _ in ev}))[:150])
sj = Path(__file__).resolve().parents[2] / 'Data/dragon/sounds.json'
if sj.exists():
    want = set(json.loads(sj.read_text())['clips'])
    seen = {c.rstrip('0123456789') if c not in want else c for c in tim}
    print('clips in sounds.json never heard in this tap:', ', '.join(sorted(want - seen)) or 'none')
