#!/usr/bin/env python3
"""Build a blind A/B pack for one Tier 1 playtest item.

Each side is one or more native evidence runs (Evidence/native-*/unreal-*). The pack gets the same
kinds of native frames from both sides under neutral names (A_*.png / B_*.png), one metrics file
per side with identical keys, and nothing that says which side is new. The key is written beside
the pack, not inside it.
"""
import argparse
import json
from pathlib import Path
import random
import shutil

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--item', required=True)
p.add_argument('--new', action='append', required=True, type=Path, help='evidence run directory (repeatable)')
p.add_argument('--old', action='append', required=True, type=Path)
p.add_argument('--kinds', default='dragon_Windup,dragon_Active,dragon_Recovery,dragon_Idle,dragon_Reposition,leg_contact',
               help='frame event names to include, in order')
p.add_argument('--per-kind', type=int, default=4)
p.add_argument('--video-every', type=float, default=0.0,
               help='also take one native video frame every N seconds between --video-from and --video-to')
p.add_argument('--video-from', type=float, default=0.0)
p.add_argument('--video-to', type=float, default=0.0)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--seed', type=int, default=None)
a = p.parse_args()

rng = random.Random(a.seed)
new_is_a = rng.random() < 0.5
sides = {'A': a.new if new_is_a else a.old, 'B': a.old if new_is_a else a.new}
a.out.mkdir(parents=True, exist_ok=False)
kinds = [k for k in a.kinds.split(',') if k]


def spread(items, count):
    if len(items) <= count:
        return items
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def metrics(run):
    e = json.loads((run / 'evidence.json').read_text())
    s = e.get('samples', [])
    fight = [x for x in s if x.get('encounterEntered')]
    top = lambda key: max([x.get(key, 0) or 0 for x in s] or [0])
    speeds = sorted(x.get('playerSpeedCmPerSecond', 0) or 0 for x in s)
    m = {
        'mode': e.get('mode'), 'passed': e.get('passed'), 'reason': e.get('reason'),
        'fightWallSeconds': e.get('terminalWallSeconds'),
        'bossMaxHealth': (e.get('latest') or {}).get('bossMaxHealth'),
        'playerHitsTaken': top('hitsTaken'), 'playerDodges': top('dodgedHits'), 'playerHeals': top('healsCompleted'),
        'bossAttacksStarted': top('bossAttacksStarted'), 'bossBlowsLanded': top('bossDamageContacts'),
        'bossChainedAttacks': top('chainCount'), 'bossSteps': top('repositionCount'),
        'bossLongestIdleSeconds': round(top('longestBossIdleSeconds'), 2),
        'bossCollapses': top('collapses'),
        'playerTopSpeedCmPerSecond': round(speeds[-1], 0) if speeds else None,
        'samples': len(fight),
    }
    if 'camp' in e:
        m['campZones'] = [{'zone': z['zone'], 'firstHitSeconds': round(z['firstHitSecondsAfterArrival'], 1),
                           'takeoffSeconds': round(z['antiCampFlightSecondsAfterArrival'], 1), 'hits': z['hits']}
                          for z in e['camp']['zones']]
    return m


for label, runs in sides.items():
    out = []
    index = 0
    for run in runs:
        run = run.resolve(strict=True)
        frames = sorted(f for f in run.glob('frame-*.png'))
        for kind in kinds:
            chosen = spread([f for f in frames if f.name.split('-', 2)[2].startswith(kind)], a.per_kind)
            for f in chosen:
                index += 1
                shutil.copyfile(f, a.out / f'{label}_{index:03d}_{kind}.png')
        if a.video_every > 0:
            manifest = run / 'native-video' / 'frames.jsonl'
            if manifest.exists():
                next_time = a.video_from
                for line in manifest.read_text().splitlines():
                    r = json.loads(line)
                    if r.get('type') != 'frame' or r.get('worldIndex', 0) != 0:
                        continue
                    t = r.get('wallSeconds', 0)
                    if t >= next_time and (a.video_to <= 0 or t <= a.video_to):
                        index += 1
                        shutil.copyfile(manifest.parent / r['file'], a.out / f'{label}_{index:03d}_film_{t:06.2f}s.png')
                        next_time = t + a.video_every
        out.append(metrics(run))
    (a.out / f'{label}_metrics.json').write_text(json.dumps(out, indent=1) + '\n')

key = a.out.parent / (a.out.name + '.key.json')
key.write_text(json.dumps({'item': a.item, 'new': 'A' if new_is_a else 'B',
                           'newRuns': [str(r) for r in a.new], 'oldRuns': [str(r) for r in a.old]}, indent=1) + '\n')
print('pack', a.out, 'frames', len(list(a.out.glob('*.png'))), 'key', key)
