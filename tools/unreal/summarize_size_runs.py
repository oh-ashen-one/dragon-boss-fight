#!/usr/bin/env python3
"""Summarize D3 (dragon size) windowless runs: band numbers and the dragonSize meter.

Usage: summarize_size_runs.py <Evidence/native-...> [more run folders]
Reads every unreal-*/evidence.json under each folder (a -VeyrSeedSweep run holds one per seed) and prints one line
per fight plus a per-folder summary: wins inside 150 s, median fight time, passive death time, and the worst wall
margin, overlap frames, attack reach and arena coverage, sword hits by part and the knocked-down head height.
"""
import json
import statistics
import sys
from pathlib import Path


def load(folder):
    out = []
    for path in sorted(Path(folder).glob('unreal-*/evidence.json')):
        try:
            out.append((path, json.loads(path.read_text())))
        except (OSError, ValueError):
            print('unreadable', path)
    return out


def main(folders):
    for folder in folders:
        rows = load(folder)
        if not rows:
            print(folder, 'no evidence')
            continue
        times, wins, deaths = [], 0, []
        size_rows = []
        for path, d in rows:
            s = d.get('dragonSize') or {}
            size_rows.append(s)
            t = d.get('terminalWallSeconds', -1)
            mode = d.get('mode')
            won = mode == 'victory' and d.get('passed') and d.get('victoryWithin150Seconds') is not None
            if mode == 'victory':
                times.append(t)
                wins += 1 if (d.get('passed') and t <= 150) else 0
            elif mode == 'death':
                deaths.append(t)
            print(f"  {mode} seed {s.get('brainSeed')} scale {s.get('bodyScale')} two-hand {s.get('twoHanded')} "
                  f"passed {d.get('passed')} t {t:.1f} margin {s.get('minWallMarginCm', 0):.0f} ({s.get('minWallMarginWhere')}) "
                  f"overlap {s.get('overlapFrames')}/{s.get('overlapChecks')} reason {str(d.get('reason'))[:60]}")
        print(folder)
        if times:
            print(f"  victory: {wins}/{len(times)} passed within 150 s; median {statistics.median(times):.1f} s; "
                  f"min {min(times):.1f} max {max(times):.1f}")
        if deaths:
            print(f"  passive death: {min(deaths):.2f}-{max(deaths):.2f} s")
        moves = {}
        for s in size_rows:
            for name, m in (s.get('moves') or {}).items():
                agg = moves.setdefault(name, {'inst': 0, 'hits': 0, 'reach': 0, 'cov': 0})
                agg['inst'] += m.get('activeInstances', 0)
                agg['hits'] += m.get('knightHits', 0)
                agg['reach'] = max(agg['reach'], m.get('maxReachCm', 0))
                agg['cov'] = max(agg['cov'], m.get('maxArenaCoveragePct', 0))
        for name, a in moves.items():
            print(f"  move {name}: active {a['inst']} knight hits {a['hits']} max reach {a['reach']:.0f} cm "
                  f"max arena coverage {a['cov']:.1f} %")
        margins = [s.get('minWallMarginCm', 1e9) for s in size_rows if s]
        if margins:
            worst = min(range(len(size_rows)), key=lambda i: size_rows[i].get('minWallMarginCm', 1e9))
            cw = min(range(len(size_rows)), key=lambda i: size_rows[i].get('minCapsuleWallMarginCm', 1e9))
            print(f"  worst hurt-capsule wall margin {size_rows[cw].get('minCapsuleWallMarginCm', 0):.0f} cm: {size_rows[cw].get('minCapsuleWallMarginWhere')}")
            print(f"  worst wall margin {margins[worst]:.0f} cm at {size_rows[worst].get('minWallMarginWhere')} xyz {size_rows[worst].get('minWallMarginAt')}; "
                  f"overlap frames total {sum(s.get('overlapFrames', 0) for s in size_rows)}")
            comps = {}
            for s in size_rows:
                for k, v in (s.get('overlapComponents') or {}).items():
                    comps[k] = comps.get(k, 0) + v
            if comps:
                print('  overlaps:', sorted(comps.items(), key=lambda kv: -kv[1])[:8])
        stand, down = {}, {}
        for s in size_rows:
            for k, v in (s.get('swordHitsStanding') or {}).items():
                stand[k] = stand.get(k, 0) + v
            for k, v in (s.get('swordHitsDown') or {}).items():
                down[k] = down.get(k, 0) + v
        print('  warning containment failures:', sum(d.get('warningContainmentFailures', 0) for _, d in rows))
        print('  sword hits standing:', stand)
        print('  sword hits down:', down)
        heads = [s.get('headDownLowestCm') for s in size_rows if s.get('headDownLowestCm', -1) >= 0]
        if heads:
            print(f"  head lowest when down {min(heads):.0f}-{max(heads):.0f} cm")
        s0 = size_rows[0]
        if s0:
            print(f"  body {s0.get('bodyLengthCm', 0):.0f} long, {s0.get('bodySpanCm', 0):.0f} wide, "
                  f"{s0.get('bodyHeightCm', 0):.0f} tall; head top {s0.get('headStandingTopCm', 0):.0f}; "
                  f"front leg top {s0.get('frontLegTopStandingCm', 0):.0f}; belly clearance {s0.get('bellyClearanceCm', 0):.0f}; "
                  f"chest clearance {s0.get('chestClearanceCm', 0):.0f}")
            for shot in s0.get('introShots') or []:
                print(f"  intro {shot['shot']}: in frame {shot['dragonPointsInFramePct']:.0f} % height "
                      f"{shot['dragonScreenHeightPct']:.0f} % width {shot['dragonScreenWidthPct']:.0f} % "
                      f"top cut {shot['dragonCutByTopEdge']} on centre ray {shot['bodyOnCentreRay']}")


if __name__ == '__main__':
    main(sys.argv[1:])
