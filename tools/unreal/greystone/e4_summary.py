#!/usr/bin/env python3
"""E4 check: summarise scripted-fight evidence folders (Evidence/native-<mode>-*) for the Greystone-vs-KnightB comparison.

Per scenario (each unreal-* folder): mode, seed, grip, pass/reason, terminal (fight) seconds, sword contacts by region,
damage received, player action counts, the knight clips that were shown, and every presentation failure or missing
target/clip log line. With --compare A B the two folder lists are paired by mode/seed/grip and hit counts and fight
lengths are printed side by side.

  python3 tools/unreal/greystone/e4_summary.py Evidence/native-victory-2026... [...] [--json out.json]
"""
import argparse
import collections
import json
import re
from pathlib import Path

PROBLEM = re.compile(r'VEYR_SKELETAL_PRESENTATION_(FAILED|TARGET_MISSING)|MISSING_CLIP|missing clip|Missing clip|'
                     r'not in definition|ResolveClip|Foot IK bone|knightFallback=true|VEYR_GREYSTONE_.*(FAIL|MISS)', re.I)
ACTIONS = ('LightAttack', 'HeavyAttack', 'Roll', 'RollAttack', 'Heal', 'Guard', 'Blink', 'RunningAttack', 'LeapAttack',
           'GripTransition', 'Stagger', 'Knockdown', 'RunStop', 'RunStart', 'Jump', 'ComboAttack')


def scenario(folder, log_lines):
    ev = json.loads((folder / 'evidence.json').read_text())
    latest = ev.get('latest') or {}
    events = collections.Counter(e.get('event', '?') for e in ev.get('events') or [])
    clips = collections.Counter(s.get('knightClip') for s in ev.get('samples') or [] if s.get('knightClip'))
    rig = ev.get('knightRig') or {}
    return {
        'folder': str(folder),
        'mode': ev.get('mode'),
        'seed': latest.get('brainSeed'),
        'twoHanded': bool(ev.get('victoryStartTwoHandedRequested')),
        'greystone': bool(rig.get('greystone')),
        'passed': ev.get('passed'),
        'reason': ev.get('reason'),
        'terminalSeconds': ev.get('terminalSeconds'),
        'swordContacts': {k: events[k] for k in ('head_contact', 'leg_contact', 'body_contact', 'tail_contact', 'wing_contact') if events[k]},
        'swordContactsTotal': sum(v for k, v in events.items() if k.endswith('_contact') and k != 'dodge_contact'),
        'damageReceived': events['damage_received'],
        'dodgeContacts': events['dodge_contact'],
        'actions': {a: events['player_' + a] for a in ACTIONS if events['player_' + a]},
        'bossHealthEnd': latest.get('bossHealth'),
        'playerHealthEnd': latest.get('playerHealth'),
        'clipsShown': dict(clips.most_common()),
        'problemLines': log_lines,
    }


def run(path):
    path = Path(path)
    log = path / 'native.log'
    lines = []
    if log.is_file():
        seen = collections.Counter()
        for line in log.read_text(errors='replace').splitlines():
            if PROBLEM.search(line):
                key = re.sub(r'^\[[^]]*\]\[[^]]*\]', '', line)[:220]
                seen[key] += 1
        lines = [f'{n}x {k}' for k, n in seen.most_common(20)]
    return [scenario(f, lines) for f in sorted(path.glob('unreal-*')) if (f / 'evidence.json').is_file()]


def key(s):
    return (s['mode'], s['seed'], s['twoHanded'])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('runs', nargs='*', type=Path)
    p.add_argument('--compare', nargs=2, metavar=('KNIGHT_LIST', 'GREYSTONE_LIST'),
                   help='two text files, one evidence folder per line')
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    if a.compare:
        sides = [[s for r in Path(f).read_text().split() for s in run(r)] for f in a.compare]
        by = [{key(s): s for s in side} for side in sides]
        rows = []
        for k in sorted(set(by[0]) | set(by[1]), key=str):
            kn, gs = by[0].get(k), by[1].get(k)
            rows.append({'scenario': k, 'knight': kn, 'greystone': gs})
            f = lambda s, n: '-' if not s else s.get(n)
            print(f'{k[0]:9s} seed={k[1]} {"2H" if k[2] else "1H"}  pass {f(kn,"passed")}/{f(gs,"passed")}  '
                  f'fight s {f(kn,"terminalSeconds")}/{f(gs,"terminalSeconds")}  sword hits {f(kn,"swordContactsTotal")}/{f(gs,"swordContactsTotal")}  '
                  f'damage taken {f(kn,"damageReceived")}/{f(gs,"damageReceived")}')
        out = rows
    else:
        out = [s for r in a.runs for s in run(r)]
        for s in out:
            print(json.dumps({k: v for k, v in s.items() if k not in ('folder',)}, default=str)[:1500])
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
