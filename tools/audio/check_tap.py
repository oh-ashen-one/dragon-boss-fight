#!/usr/bin/env python3
"""Per-cue checks on a software-mix tap (VeyrAudition-cues.json from -VeyrAudioAudition, or VeyrTap-cues.json from a replay).

Game side: add `-VeyrAudioTap=<absolute dir>` (and `-VeyrAudioAudition` for the every-cue pass) to a run, headless is fine
(`playtest_suite.py --run <mode>:headless,-VeyrAudioTap=/abs/dir`). No window, no audio device.

    python3 tools/audio/check_tap.py <dir-or-json> [--expect-variants staged/Recorded20261118 [staged/Generated20261118]] [--earshot]

Checks per cue: fires; every loaded variant plays (audition); expected variant count loaded; no variant twice in a row in the random
phase; not clipped (item peak under -2 dBFS, master peak under -1 dBFS, no clipped samples); audible over the music bed at its live gain (median of the cue's events, in its own window).
--earshot adds `earshot realness` on the mix wav (real recording vs synthesized). Exit status 1 if any check fails.
"""
import argparse, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

QUIET = {'Footstep', 'DragonBreathIn', 'DragonBreathOut', 'DragonSnort', 'Roll', 'Blink', 'Debris'}
FIXED = {'Roar', 'DragonGrowl', 'DragonPain', 'PlayerPain'}   # single fixed files, no variants


def expected_variants(folders):
    n = Counter()
    for f in folders:
        for p in Path(f).glob('*.pcm'):
            m = re.match(r'(.+?)_g?\d+\.pcm$', p.name)
            if m:
                n[m.group(1)] += 1
    return {k: min(v, 16) for k, v in n.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--expect-variants', nargs='*', default=[])
    ap.add_argument('--earshot', action='store_true')
    ap.add_argument('--quiet-floor', type=float, default=0.0, help='dB above the music bed for quiet cues')
    ap.add_argument('--floor', type=float, default=3.0, help='dB above the music bed for the others')
    a = ap.parse_args()
    p = Path(a.path)
    if p.is_dir():
        p = next((p / n for n in ('VeyrAudition-cues.json', 'VeyrTap-cues.json') if (p / n).exists()), p)
    d = json.loads(p.read_text())
    audition = d.get('audition')
    want = expected_variants(a.expect_variants) if a.expect_variants else {}
    fails = []
    print(f"{p.name}: {d['seconds']:.1f} s, master peak {d['masterPeakDb']:.1f} dBFS, clipped {d['clippedSamples']}, "
          f"effects {d['effectsRmsDbOverActive']:.1f} dB, beds {d['bedsRmsDbOverAll']:.1f} dB, newSet={d['newSet']}")
    if not d['newSet']:
        fails.append('newSet is false: the previous sounds were played')
    if d['masterPeakDb'] > -1.0 or d['clippedSamples']:
        fails.append(f"master peak {d['masterPeakDb']:.1f} dBFS / {d['clippedSamples']} clipped samples")
    gap = d['effectsRmsDbOverActive'] - d['bedsRmsDbOverAll']
    print(f'effects over music bed: {gap:+.1f} dB (target +4 .. +14)')
    if not 4 <= gap <= 14:
        fails.append(f'effects vs music {gap:+.1f} dB outside +4..+14')
    items = d['items']
    print(f"{'cue':16} {'events':>6} {'loaded':>6} {'used':>4} {'b2b':>3} {'peak':>6} {'med>music':>9}  result")
    for cue, c in sorted(d['cues'].items()):
        bad = []
        loaded = c['variantsLoaded']
        if want.get(cue) is not None and cue not in FIXED and loaded != want[cue]:
            bad.append(f'loaded {loaded} != expected {want[cue]}')
        if audition and cue not in FIXED and c['variantsUsed'] != loaded:
            bad.append(f"used {c['variantsUsed']}/{loaded} variants")
        if loaded > 1 and c['backToBackRepeats']:
            bad.append(f"{c['backToBackRepeats']} back-to-back repeats")
        if c['maxPeakDb'] > -2.0:
            bad.append(f"peak {c['maxPeakDb']:.1f} dBFS")
        floor = 0.0 if cue in FIXED else (a.quiet_floor if cue in QUIET else a.floor)  # fixed vocals keep their approved levels
        import statistics
        vals = [i['aboveMusicDb'] for i in items if i['cue'] == cue and i['musicRmsDb'] > -100]
        m = statistics.median(vals) if vals else None  # median per cue: one quiet variant or a far pitched-down take is not the cue
        if m is not None and m < floor:
            bad.append(f'only {m:+.1f} dB over the music (need {floor:+.0f})')
        print(f"{cue:16} {c['events']:6} {loaded:6} {c['variantsUsed']:4} {c['backToBackRepeats']:3} {c['maxPeakDb']:6.1f} "
              f"{m if m is not None else float('nan'):9.1f}  {'OK' if not bad else '; '.join(bad)}")
        fails += [f'{cue}: {b}' for b in bad]
    if audition:
        for cue in sorted(set(want) - set(d['cues'])):
            fails.append(f'{cue}: files exist but the cue never fired (not loaded?)')
    if a.earshot:
        wav = p.with_name(p.name.replace('-cues.json', '-mix.wav'))
        e = Path.home() / '.cache/earshot/venv/bin/earshot'
        r = subprocess.run([str(e), 'realness', str(wav)], capture_output=True, text=True)
        print(r.stdout[-1500:] or r.stderr[-500:])
    print('FAIL' if fails else 'PASS')
    for f in fails:
        print('  -', f)
    return 1 if fails else 0


sys.exit(main())
