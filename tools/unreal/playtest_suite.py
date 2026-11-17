#!/usr/bin/env python3
"""Run a list of native replays on one packaged app, one at a time, with the owner's play profile.

Each run goes through run_native.py (shared GPU slot, 60 fps cap, background window). Prints one
summary line per run and writes Local/playtest-suite-<stamp>.json. Never relaunches a failed run.
"""
import argparse
import datetime
import glob
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PLAY_PROFILE = ['-VeyrCanonicalKnightSkin', '-VeyrStableWeaponPresentation', '-VeyrWalkEntryBlend', '-VeyrReadableAutoLock']

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--run', action='append', required=True,
               help='mode[:flag[,flag...]] e.g. victory, victory:two-handed, camp, showcase:-VeyrLegacyDragon; '
                    '"two-handed" maps to --start-two-handed, "video=N" to --video-fps N, "sound" to --with-sound')
p.add_argument('--label', default='suite')
a = p.parse_args()
gate = Path.home() / '.cache/gpu-slot/bin/gpu_slot.sh'
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
results = []
crashes = 0
for spec in a.run:
    mode, _, rest = spec.partition(':')
    flags = [f for f in rest.split(',') if f]
    cmd = [sys.executable, str(ROOT / 'tools/unreal/run_native.py'), '--app', str(a.app), '--gpu-slot', str(gate),
           '--mode', mode, '--slot-wait-seconds', '900']
    extra = list(PLAY_PROFILE)
    for flag in flags:
        if flag == 'two-handed':
            cmd.append('--start-two-handed')
        elif flag == 'sound':
            cmd.append('--with-sound')
        elif flag.startswith('video='):
            cmd += ['--video-fps', flag.split('=', 1)[1]]
        elif flag.startswith('audio='):
            cmd += ['--audio-capture-seconds', flag.split('=', 1)[1]]
        elif flag == 'no-profile':
            extra = []
        else:
            extra.append(flag)
    for flag in extra:
        cmd.append('--extra-arg=' + flag)
    before = set(glob.glob(str(ROOT / 'Evidence' / ('native-' + mode + '-*'))))
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # Exit 75 is the shared GPU gate declining to launch while another session holds the GPU
    # (nothing was started). Queue politely: wait and ask again, up to 40 minutes.
    waits = 0
    while proc.returncode == 75 and waits < 20:
        waits += 1
        print(f'    GPU busy with another session; waiting 120 s (attempt {waits})', flush=True)
        time.sleep(120)
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    new = sorted(set(glob.glob(str(ROOT / 'Evidence' / ('native-' + mode + '-*')))) - before)
    record = {'spec': spec, 'exit': proc.returncode, 'wallSeconds': round(time.time() - started, 1),
              'run': new[-1] if new else None, 'tail': proc.stdout.strip().splitlines()[-1:] }
    evidence = glob.glob(new[-1] + '/unreal-*/evidence.json') if new else []
    if evidence:
        e = json.loads(Path(evidence[-1]).read_text())
        latest = e.get('latest', {})
        samples = e.get('samples', [])
        record.update({
            'passed': e.get('passed'), 'reason': e.get('reason'),
            'terminalWallSeconds': e.get('terminalWallSeconds'), 'durationSeconds': e.get('durationSeconds'),
            'bossMaxHealth': latest.get('bossMaxHealth'), 'bossHealth': latest.get('bossHealth'),
            'hitsTaken': max([s.get('hitsTaken', 0) for s in samples] or [0]),
            'dodgedHits': max([s.get('dodgedHits', 0) for s in samples] or [0]),
            'healsCompleted': max([s.get('healsCompleted', 0) for s in samples] or [0]),
            'collapses': max([s.get('collapses', 0) for s in samples] or [0]),
            'chainCount': max([s.get('chainCount', 0) for s in samples] or [0]),
            'antiCampFlights': max([s.get('antiCampFlights', 0) for s in samples] or [0]),
            'repositionCount': max([s.get('repositionCount', 0) for s in samples] or [0]),
            'trampleCount': max([s.get('trampleCount', 0) for s in samples] or [0]),
            'longestBossIdleSeconds': max([s.get('longestBossIdleSeconds', 0) for s in samples] or [0]),
            'warningContainmentFailures': e.get('warningContainmentFailures'),
            'moves': {m['move']: m['started'] for m in latest.get('moveCoverage', [])},
            'meanFrameSeconds': e.get('meanFrameSeconds'), 'wallFrameP95Seconds': e.get('wallFrameP95Seconds'),
            'bodyScale': latest.get('bossBodyScale'), 'pace': latest.get('bossPaceScale'),
            'aggression': latest.get('bossAggression'), 'floorTelegraph': latest.get('floorTelegraph'),
            'evidence': evidence[-1],
        })
        if 'camp' in e:
            record['camp'] = e['camp']['zones']
        if 'brainReachMap' in e:
            record['brainReachMap'] = e['brainReachMap']
    results.append(record)
    print(json.dumps({k: v for k, v in record.items() if k not in ('camp', 'tail', 'brainReachMap')}), flush=True)
    for line in record.get('brainReachMap', []):
        print('    MAP', line, flush=True)
    if 'camp' in record:
        for zone in record['camp']:
            print('   ', json.dumps(zone), flush=True)
    if proc.returncode not in (0, 1) or not evidence:
        crashes += 1
        print('    stderr:', proc.stderr.strip()[-600:], flush=True)
        if crashes >= 2:
            print('Two launches failed without evidence: stopping (never auto-relaunch).', flush=True)
            break
out = ROOT / 'Local' / f'playtest-suite-{a.label}-{stamp}.json'
out.write_text(json.dumps(results, indent=1) + '\n')
print('Suite record:', out)
