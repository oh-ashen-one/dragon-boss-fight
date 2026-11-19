#!/usr/bin/env python3
"""E4: why does one knight win faster? Per-fight action counts from two seed sweeps, paired by seed.

  python3 tools/unreal/greystone/fight_compare.py <Evidence/native-victory-A> <Evidence/native-victory-B> [--json out.json]

Reads every unreal-*/evidence.json (one per seed of a -VeyrSeedSweep run). Per fight: fight seconds, attacks started
(light, heavy, combo, rolling, running, leaping), strike windows that connected, sword contacts, hits taken, rolls,
heals, run starts, and the ratios that separate reach (contacts per attack) from pace (attacks per minute).
"""
import argparse
import glob
import json
import statistics

COUNTS = ('lightAttacks', 'heavyAttacks', 'comboAttacks', 'rollAttacks', 'runningAttacks', 'leapingAttacks',
          'successfulStrikeWindows', 'swordContacts', 'headBonusHits', 'hitsTaken', 'dodgedHits', 'rolls', 'blinkDodges',
          'healsCompleted', 'runStarts', 'runStops', 'guardedHits', 'whiffOpenings', 'collapses')


def fights(folder):
    out = {}
    for path in sorted(glob.glob(folder + '/unreal-*/evidence.json')):
        e = json.load(open(path))
        samples = [s for s in e.get('samples', []) if s.get('replayStage') == 'combat'] or e.get('samples', [])
        if not samples:
            continue
        seed = next((s.get('brainSeed') for s in samples if s.get('brainSeed') is not None), None)
        row = {k: max((s.get(k) or 0) for s in samples if isinstance(s.get(k, 0), (int, float))) for k in COUNTS}
        row['fightSeconds'] = e.get('terminalWallSeconds') or e.get('terminalSeconds')
        row['passed'] = e.get('passed')
        attacks = sum(row[k] for k in COUNTS[:6])
        row['attacks'] = attacks
        row['contactsPerAttack'] = round(row['successfulStrikeWindows'] / attacks, 3) if attacks else None
        row['attacksPerMinute'] = round(attacks / row['fightSeconds'] * 60, 2) if row['fightSeconds'] else None
        speeds = [s.get('playerSpeedCmPerSecond') or 0 for s in samples]
        row['movingShare'] = round(sum(1 for v in speeds if v > 50) / len(speeds), 3)
        row['meanSpeedCmPerSecond'] = round(statistics.mean(speeds), 1)
        rig = e.get('knightRig') or {}
        row['greystone'] = bool(rig.get('greystone') or rig.get('active'))
        out[seed] = row
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('a'); ap.add_argument('b'); ap.add_argument('--json')
    a = ap.parse_args()
    A, B = fights(a.a), fights(a.b)
    seeds = [s for s in A if s in B]
    keys = ['fightSeconds', 'attacks', 'successfulStrikeWindows', 'swordContacts', 'contactsPerAttack', 'attacksPerMinute',
            'hitsTaken', 'rolls', 'healsCompleted', 'movingShare', 'meanSpeedCmPerSecond'] + [k for k in COUNTS if k not in
            ('successfulStrikeWindows', 'swordContacts', 'hitsTaken', 'rolls', 'healsCompleted')]
    print(f'{len(seeds)} paired seeds  A={a.a}  B={a.b}')
    print(f'{"field":26s} {"A median":>10s} {"B median":>10s} {"B/A":>7s}')
    summary = {}
    for k in keys:
        va = [A[s][k] for s in seeds if A[s][k] is not None]; vb = [B[s][k] for s in seeds if B[s][k] is not None]
        if not va or not vb:
            continue
        ma, mb = statistics.median(va), statistics.median(vb)
        summary[k] = {'a': ma, 'b': mb, 'sumA': sum(va), 'sumB': sum(vb)}
        print(f'{k:26s} {ma:10.2f} {mb:10.2f} {(mb / ma if ma else float("nan")):7.3f}   sums {sum(va):.1f} / {sum(vb):.1f}')
    if a.json:
        json.dump({'a': a.a, 'b': a.b, 'perSeedA': A, 'perSeedB': B, 'summary': summary}, open(a.json, 'w'), indent=1, default=str)


if __name__ == '__main__':
    main()
