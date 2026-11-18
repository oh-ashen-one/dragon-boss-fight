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
p.add_argument('--app', type=Path)
p.add_argument('--engine', type=Path, help='run the editor build as a game instead of a packaged app (quick iteration; not a release check)')
p.add_argument('--run', action='append', required=True,
               help='mode[:flag[,flag...]] e.g. victory, victory:two-handed, camp, showcase:-VeyrLegacyDragon; '
                    '"two-handed" maps to --start-two-handed, "video=N" to --video-fps N, "sound" to --with-sound, '
                    '"headless" to a numbers-only null-renderer run that needs no GPU slot')
p.add_argument('--label', default='suite')
p.add_argument('--parallel', type=int, default=1, help='run this many headless specs at once (headless only)')
p.add_argument('--busy-wait-minutes', type=float, default=40,
               help='how long one run may stay queued while another session holds the GPU')
a = p.parse_args()
assert bool(a.app) != bool(a.engine), 'give exactly one of --app or --engine'
gate = Path.home() / '.cache/gpu-slot/bin/gpu_slot.sh'
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
results = []
crashes = 0
def run_spec(spec, delay=0.0):
    time.sleep(delay)
    mode, _, rest = spec.partition(':')
    flags = [f for f in rest.split(',') if f]
    runtime = ['--app', str(a.app)] if a.app else ['--engine', str(a.engine)]
    cmd = [sys.executable, str(ROOT / 'tools/unreal/run_native.py'), *runtime, '--gpu-slot', str(gate),
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
        elif flag == 'headless':
            cmd.append('--headless')
        elif flag == 'no-profile':
            extra = []
        else:
            extra.append(flag)
    for flag in extra:
        cmd.append('--extra-arg=' + flag)
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # Exit 75 is the shared GPU gate declining to launch while another session holds the GPU
    # (nothing was started). Queue politely: ask again every 20 s for --busy-wait-minutes.
    waits = 0
    while proc.returncode == 75 and time.time() - started < a.busy_wait_minutes * 60:
        waits += 1
        if waits % 10 == 1:
            print(f'    GPU busy with another session; still queued (attempt {waits})', flush=True)
        time.sleep(20)
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # run_native.py prints its own evidence directory; parallel headless runs cannot be told apart by listing.
    new = [line.split(':', 1)[1].strip() for line in proc.stdout.splitlines() if line.startswith('Native run:')]
    record = {'spec': spec, 'headless': 'headless' in flags, 'exit': proc.returncode, 'wallSeconds': round(time.time() - started, 1),
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
            'overrunCount': max([s.get('overrunCount', 0) for s in samples] or [0]),
            'whiffOpenings': max([s.get('whiffOpenings', 0) for s in samples] or [0]),
            'guardPocketFlights': max([s.get('guardPocketFlights', 0) for s in samples] or [0]),
            'exposedCapRises': max([s.get('exposedCapRises', 0) for s in samples] or [0]),
            'courtOverreachCm': max([s.get('bossCourtOverreachCm', -100000) for s in samples] or [-100000]),
            'bossAttacks': max([s.get('bossAttacksStarted', 0) for s in samples] or [0]),
            'bossContacts': max([s.get('bossDamageContacts', 0) for s in samples] or [0]),
            'minPlayerHealth': min([s.get('playerHealth', 100) for s in samples] or [100]),
            'longestBossIdleSeconds': max([s.get('longestBossIdleSeconds', 0) for s in samples] or [0]),
            'warningContainmentFailures': e.get('warningContainmentFailures'),
            'moves': {m['move']: m['started'] for m in latest.get('moveCoverage', [])},
            'meanFrameSeconds': e.get('meanFrameSeconds'), 'wallFrameP95Seconds': e.get('wallFrameP95Seconds'),
            'bodyScale': latest.get('bossBodyScale'), 'pace': latest.get('bossPaceScale'),
            'aggression': latest.get('bossAggression'), 'floorTelegraph': latest.get('floorTelegraph'),
            'evidence': evidence[-1],
        })
        if 'a123' in e:
            # Quality goal A1-A3 proof modes (footclosehits / camerahug / soleheights).
            x = e['a123']
            keys = ('mirroredClips', 'sweepMirroredMaxStretchCm1x', 'sweepLegacyMirroredMaxStretchCm1x', 'liveMirroredFrames',
                    'liveMirroredMaxStretchCm', 'liveMirrorRepairSamples', 'cameraFrames', 'cameraInsideFrames', 'collapseFrames',
                    'collapseInsideFrames', 'pullInEvents', 'maxLiftCm', 'maxCameraJumpCmPerFrame', 'liveGroundFrames',
                    'liveLowestSoleMedianCm', 'liveLowestSoleP90Cm', 'sweepWorstClipMedianFloatCm1x', 'sweepWorstClip',
                    'groundingOffsetCm', 'legacyMirrorToe', 'legacyCameraBoom', 'noDragonGrounding')
            record['a123'] = {k: x[k] for k in keys if k in x}
        if 'framing' in e:
            # Quality goal D1: what the player's camera showed (VeyrFramingMeter). Goal: knight >= .95, limb >= .90.
            x = e['framing']
            keys = ('frames', 'knightFullyInFrameShare', 'lockedKnightFullyInFrameShare', 'headOrChestOnScreenShare',
                    'knightMeanScreenHeightPct', 'cameraInsideBodyFrames', 'strikes', 'strikeLimbVisibleShare',
                    'nearStrikeLimbVisibleShare', 'strikeLimbVisibleByMove', 'goalD1Met', 'giantCamera')
            record['framing'] = {k: (round(x[k], 3) if isinstance(x.get(k), float) else x[k]) for k in keys if k in x}
        if 'framingProof' in e:
            record['framingPhases'] = {name: {'knight': round(p.get('knightFullyInFrameShare', 0), 3),
                                              'headOrChest': round(p.get('headOrChestOnScreenShare', 0), 3),
                                              'knightHeightPct': round(p.get('knightMeanScreenHeightPct', 0), 1),
                                              'limb': p.get('strikeLimbVisibleByMove')}
                                       for name, p in e['framingProof'].get('phases', {}).items()}
            record['framingFlightSeen'] = e['framingProof'].get('flightSeen')
        if 'camp' in e:
            record['camp'] = e['camp']['zones']
        if 'brainReachMap' in e:
            record['brainReachMap'] = e['brainReachMap']
    return record, proc


def report(record, proc):
    global crashes
    results.append(record)
    print(json.dumps({k: v for k, v in record.items() if k not in ('camp', 'tail', 'brainReachMap', 'framing', 'framingPhases')}), flush=True)
    if 'framing' in record:
        print('    FRAMING', json.dumps(record['framing']), flush=True)
    for name, phase in record.get('framingPhases', {}).items():
        print('    PHASE', name, json.dumps(phase), flush=True)
    for line in record.get('brainReachMap', []):
        print('    MAP', line, flush=True)
    if 'camp' in record:
        for zone in record['camp']:
            print('   ', json.dumps(zone), flush=True)
    if proc.returncode not in (0, 1) or not record.get('evidence'):
        crashes += 1
        print('    stderr:', proc.stderr.strip()[-600:], flush=True)


if a.parallel > 1:
    # Only renderer-less runs may overlap: they use no GPU and take no slot.
    assert all('headless' in spec.partition(':')[2].split(',') for spec in a.run), '--parallel is for headless runs only'
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(a.parallel) as pool:
        for record, proc in pool.map(lambda item: run_spec(item[1], 2.5 * (item[0] % a.parallel)), enumerate(a.run)):
            report(record, proc)
else:
    for spec in a.run:
        report(*run_spec(spec))
        if crashes >= 2:
            print('Two launches failed without evidence: stopping (never auto-relaunch).', flush=True)
            break
out = ROOT / 'Local' / f'playtest-suite-{a.label}-{stamp}.json'
out.write_text(json.dumps(results, indent=1) + '\n')
print('Suite record:', out)
