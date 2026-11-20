#!/usr/bin/env python3
"""Difficulty-band summary for windowless runs (seed sweeps or single runs).

Usage: band_summary.py [--per-seed] <Evidence/native-...> [more run folders]
Reads every unreal-*/evidence.json under the folders. Victory fights are grouped by grip (one-hand / two-hand),
death runs are the passive check. Prints wins inside 150 s, median, range per grip and the passive death range,
against the owner's band: one-hand median 88 s +-15 %, two-hand 73.5 s +-15 %, passive death under 12 s.
"""
import json
import statistics
import sys
from pathlib import Path

BAND = {'one-hand': 88.0, 'two-hand': 73.5}


def fights(folders):
    for folder in folders:
        for path in sorted(Path(folder).glob('unreal-*/evidence.json')):
            try:
                d = json.loads(path.read_text())
            except (OSError, ValueError):
                print('unreadable', path)
                continue
            combat = [s for s in d.get('samples', []) if s.get('replayStage') == 'combat'] or d.get('samples', [])
            yield {
                'mode': d.get('mode'),
                'grip': 'two-hand' if d.get('victoryStartTwoHandedRequested') else 'one-hand',
                'seed': next((s.get('brainSeed') for s in combat if s.get('brainSeed') is not None), None),
                'passed': bool(d.get('passed')),
                'seconds': d.get('terminalWallSeconds', -1),
                'hitsTaken': max([s.get('hitsTaken', 0) for s in combat] or [0]),
                'hitsDealt': max([s.get('swordContacts', 0) for s in combat] or [0]),
                'fastSim': 'fixed' if d.get('meanFrameSeconds') and abs(d['meanFrameSeconds'] - 1 / 60) < 1e-4 else 'wall',
                'reason': d.get('reason', ''),
                'falls': int(d.get('fallRecoveries', 0) or 0) + int(d.get('dragonFallRecoveries', 0) or 0),
                'path': str(path.parent),
            }


def main(argv):
    per_seed = '--per-seed' in argv
    rows = list(fights([a for a in argv if a != '--per-seed']))
    if per_seed:
        for r in rows:
            print(f"{r['mode']:8} {r['grip']:8} seed {r['seed']!s:>9} passed {r['passed']!s:5} t {r['seconds']:7.2f} s "
                  f"hits taken {r['hitsTaken']:2} dealt {r['hitsDealt']:3}  {'FALL RECOVERIES ' + str(r['falls']) + '  ' if r['falls'] else ''}{r['reason'][:70]}")
    for grip, target in BAND.items():
        v = [r for r in rows if r['mode'] == 'victory' and r['grip'] == grip]
        if not v:
            continue
        # A loss has no fight time (-1 s); it never enters the median. Medians are over wins only.
        won = [r for r in v if r['passed'] and r['seconds'] >= 0]
        lost = [r for r in v if r not in won]
        times = [r['seconds'] for r in won]
        inside = sum(1 for t in times if t <= 150)
        if times:
            med = statistics.median(times)
            print(f"{grip}: wins {len(won)} of {len(v)} ({inside} inside 150 s), median over wins {med:.1f} s "
                  f"({100 * (med / target - 1):+.0f} % against {target} s, band +-15 %: "
                  f"{'in' if abs(med / target - 1) <= .15 else 'OUT'}), range {min(times):.1f}-{max(times):.1f} s")
        else:
            print(f"{grip}: wins 0 of {len(v)}")
        for r in lost:
            print(f"{grip}: loss seed {r['seed']}: {r['reason'][:80]}")
    falls = [r for r in rows if r['falls']]
    if falls:
        print(f"FAIL: {len(falls)} run(s) needed a fall recovery (a hole in the court): " + ', '.join(f"seed {r['seed']}" for r in falls))
    deaths = [r['seconds'] for r in rows if r['mode'] == 'death']
    if deaths:
        print(f"passive: death in {min(deaths):.2f}-{max(deaths):.2f} s over {len(deaths)} runs "
              f"({'in' if max(deaths) < 12 else 'OUT'}: under 12 s)")


if __name__ == '__main__':
    main(sys.argv[1:])
