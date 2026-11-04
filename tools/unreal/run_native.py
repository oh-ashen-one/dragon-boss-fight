#!/usr/bin/env python3
"""Run one native input replay through the existing shared GPU slot protocol."""
import argparse
import datetime
import json
import hashlib
import os
import plistlib
from pathlib import Path
import subprocess
import time
import re

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
runtime = p.add_mutually_exclusive_group(required=True)
runtime.add_argument('--engine', type=Path)
runtime.add_argument('--app', type=Path, help='Test the actual cooked Mac app')
p.add_argument('--gpu-slot', type=Path, required=True)
p.add_argument('--mode', choices=['core','death','victory','leg0','leg1','leg2','leg3','controls','avoidance','healing','guard','stance','integration','collision','lockon','blendproof','showcase','environment','intro'], required=True)
p.add_argument('--next-mode',choices=['environment','showcase','healing','death'],help='One additional scenario in a fresh world, using the same owned renderer process')
p.add_argument('--slot-wait-seconds', type=int, default=180, help='Bounded shared-slot queue wait, 30 to 3600 seconds; does not extend test duration')
p.add_argument('--wait-for-stream-end',action='store_true',help='Keep this single owned request waiting while the shared streaming flag exists; still acquire the normal GPU gate afterward')
p.add_argument('--wait-for-capacity',action='store_true',help='Wait without a slot until shared status shows spare capacity; the normal GPU gate still makes the launch decision')
p.add_argument('--video-fps', type=int, choices=range(1,61), help='Optional native capture cadence; adds measurable overhead')
p.add_argument('--launch-services',action='store_true',help='Use the normal macOS app launch path; success still requires native final evidence')
p.add_argument('--performance',action='store_true',help='Exclusive GPU lease; no screenshots/video, sparse diagnostics; audio remains enabled')
p.add_argument('--with-sound',action='store_true',help='Enable the game audio device without recording; intro proof requires this or audio capture')
p.add_argument('--audio-capture-seconds',type=int,choices=range(1,121),help='Record only the game master submix; enables sound and is incompatible with performance mode')
p.add_argument('--start-two-handed', action='store_true', help='Core/victory QA uses the ordinary authored grip input before combat')
p.add_argument('--extra-arg', action='append', default=[], help='Extra game command-line flag (repeatable), e.g. -VeyrNoWeaponGripLock for the blendproof before-run')
p.add_argument('--no-proof-floor', action='store_true', help='blendproof only: do not apply the 25 cm checker (-VeyrProofFloor)')
p.add_argument('--width', type=int, default=1280)
p.add_argument('--height', type=int, default=720)
a = p.parse_args()
if a.mode=='intro' and not(a.with_sound or a.audio_capture_seconds):p.error('Intro proof requires --with-sound or --audio-capture-seconds; NoSound playback counters are not valid audio evidence')
if not 30 <= a.slot_wait_seconds <= 3600:
    p.error('--slot-wait-seconds must be between 30 and 3600')
if (ROOT / 'Local/ENGINE_LAUNCH_HOLD.json').exists():
    p.error('Engine launches are held after two crashes; obtain owner approval before clearing the task-local hold.')
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
run = ROOT / 'Evidence' / ('native-' + a.mode + '-' + stamp)
run.mkdir(parents=True)
project = ROOT / 'Unreal/Veyr/Veyr.uproject'
if a.app:
    app = a.app.resolve()
    info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    name = info['CFBundleExecutable']
    if Path(name).name != name:
        p.error('Invalid executable name in app bundle')
    executable = app/'Contents/MacOS'/name
    from audit_bundle import audit_bundle
    preflight = audit_bundle(app)
    preflight['cookedPayloadPresent'] = (app/'Contents/UE').is_dir()
    signature = subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True)
    preflight['signatureVerified'] = signature.returncode == 0
    (run/'bundle-preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
    if not (preflight['staticDependencyAuditPassed'] and preflight['cookedPayloadPresent'] and preflight['signatureVerified']):
        p.error('Packaged app failed dependency, payload or signature preflight; no game was launched')
    launch = ['/usr/bin/open','-g','-W','-n',str(app),'--args','/Game/Maps/VeyrArena'] if a.launch_services else [str(executable), '/Game/Maps/VeyrArena']
else:
    executable = a.engine / 'Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor'
    launch = [str(executable), str(project), '/Game/Maps/VeyrArena', '-game']
if not executable.is_file():
    p.error('Runtime executable is missing')
(run/'launch.json').write_text(json.dumps({'runtimeKind':'packaged-app' if a.app else 'editor-game', 'executableSHA256':hashlib.sha256(executable.read_bytes()).hexdigest(), 'resolution':[a.width,a.height], 'screenPercentage':100, 'fpsCap':60, 'silent':not(a.performance or a.audio_capture_seconds or a.with_sound),'performanceMode':a.performance,'masterAudioCaptureSeconds':a.audio_capture_seconds},indent=2)+'\n')
cmd = [str(a.gpu_slot), 'perf' if a.performance else 'capture', '--label', 'veyr-' + a.mode, '--timeout', str(a.slot_wait_seconds), '--json', str(run/'gpu.json'), '--', *launch, '-windowed', '-unattended', '-NoCrashReports', '-NoSound', '-notraceserver', '-NoZenAutoLaunch', '-DDC=(EnginePak=InstalledEnginePak,Local)', '-LocalDataCachePath='+str(project.parent/'DerivedDataCache'), '-ResX='+str(a.width), '-ResY='+str(a.height), '-ForceRes', '-ExecCmds=t.MaxFPS 60,r.ScreenPercentage 100', '-VeyrReplay='+a.mode, '-VeyrEvidence='+str(run), '-VeyrReplayQuit', '-abslog='+str(run/'native.log')]
if a.performance:
    if a.video_fps or a.audio_capture_seconds:p.error('Performance and media capture are mutually exclusive')
    cmd.remove('-NoSound');cmd.extend(['-VeyrPerformance','-ini:Engine:[Audio]:UnfocusedVolumeMultiplier=1.0'])
if a.audio_capture_seconds:
    cmd.remove('-NoSound')
    audio_dir=run/'master-audio';audio_dir.mkdir()
    cmd.extend(['-ini:Engine:[Audio]:UnfocusedVolumeMultiplier=1.0','-VeyrAudioCapture='+str(audio_dir),'-VeyrAudioCaptureSeconds='+str(a.audio_capture_seconds)])
if a.with_sound and '-NoSound' in cmd:cmd.remove('-NoSound')
if a.video_fps:
    cmd.append('-VeyrVideoFPS='+str(a.video_fps))
if a.next_mode:
    if a.next_mode==a.mode:p.error('Use distinct modes for a two-scenario run')
    if a.performance or a.audio_capture_seconds:p.error('Performance/audio measurements require a single scenario')
    cmd.append('-VeyrReplayNext='+a.next_mode)
if a.mode=='blendproof' and not a.no_proof_floor:
    cmd.append('-VeyrProofFloor')
for extra in a.extra_arg:
    if not extra.startswith('-Veyr') or ' ' in extra:p.error('--extra-arg accepts only a single -Veyr* flag')
    cmd.append(extra)
if a.start_two_handed:
    if a.mode not in ('core','victory'):p.error('--start-two-handed applies only to core/victory validation')
    cmd.append('-VeyrReplayStartTwoHanded')
print('Native run:', run, flush=True)
if a.wait_for_capacity:
    print('Waiting outside the GPU lease for spare capacity; no renderer launched',flush=True)
    calm_since=None
    while True:
        status=subprocess.run([str(a.gpu_slot),'status'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
        utilization=re.search(r'GPU Device Utilization now:\s*([0-9.]+)\s*%',status.stdout)
        slots=re.search(r'Capture slots:\s*(\d+)/(\d+)',status.stdout)
        watchdog=re.search(r'Watchdog cap:\s*(\d+)',status.stdout)
        capacity=min(int(slots[2]),int(watchdog[1])) if slots and watchdog else 0
        available=bool(status.returncode==0 and utilization and slots and
            re.search(r'PAUSED:\s*no',status.stdout) and re.search(r'Perf lock:\s*free',status.stdout) and
            not (Path.home()/'.cache/gpu-slot/STREAMING').exists() and int(slots[1])<capacity and float(utilization[1])<75.)
        now=time.monotonic()
        calm_since=(now if calm_since is None else calm_since) if available else None
        (run/'queue-state.json').write_text(json.dumps({'pid':os.getpid(),'state':'waiting_capacity','rendererLaunched':False,
            'checkedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'capacityObserved':available})+'\n')
        if calm_since is not None and now-calm_since>=20.:break
        time.sleep(10.)
    (run/'queue-state.json').write_text(json.dumps({'pid':os.getpid(),'state':'requesting_normal_gate','rendererLaunched':False})+'\n')
    print('Spare capacity observed; requesting the ordinary launch-budget and GPU gates',flush=True)
if a.wait_for_stream_end:
    streaming=Path.home()/'.cache/gpu-slot/STREAMING'
    if streaming.exists():print('Waiting for the shared streaming guard to clear; no renderer launched',flush=True)
    while streaming.exists():time.sleep(30.)
if a.wait_for_stream_end or a.wait_for_capacity:
    # An unattended wait must not turn an earlier preflight into permission to
    # launch a changed binary. GPU headroom/cap checks still happen below.
    if not executable.is_file() or hashlib.sha256(executable.read_bytes()).hexdigest()!=json.loads((run/'launch.json').read_text())['executableSHA256']:
        raise SystemExit('Runtime changed during the guarded wait; preserve evidence and revalidate')
from owned_launch_budget import wait_for_budget
wait_for_budget(ROOT)
with (run/'launcher.log').open('w') as output:
    environment = os.environ.copy()
    # Direct executable launches do not receive Info.plist LSEnvironment from
    # LaunchServices. Honor only this explicit app-owned allocator setting.
    if a.app and info.get('LSEnvironment',{}).get('UE4_FORCE_MALLOC_ANSI')=='1':
        environment['UE4_FORCE_MALLOC_ANSI']='1'
    result = subprocess.run(cmd, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
print('Process exit:', result.returncode, 'Evidence:', run, flush=True)
if result.returncode:
    raise SystemExit(result.returncode)
results = list(run.glob('unreal-*/evidence.json'))
expected=[a.mode]+([a.next_mode] if a.next_mode else [])
if len(results) != len(expected):raise SystemExit('Expected one completed evidence file per requested scenario')
evidence=[json.loads(p.read_text()) for p in results]
if sorted(d.get('mode','') for d in evidence)!=sorted(expected):raise SystemExit('Recorded scenarios differ from the requested run')
if len({d.get('sourceId') for d in evidence})!=1:raise SystemExit('Source identity changed during the run')
for d in evidence:print('Scenario:',d.get('mode'),d.get('passed'),d.get('reason'),flush=True)
raise SystemExit(0 if all(d.get('finalWrite') and d.get('finished') and d.get('passed') for d in evidence) else 1)
