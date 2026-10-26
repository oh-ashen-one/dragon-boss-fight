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

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
runtime = p.add_mutually_exclusive_group(required=True)
runtime.add_argument('--engine', type=Path)
runtime.add_argument('--app', type=Path, help='Test the actual cooked Mac app')
p.add_argument('--gpu-slot', type=Path, required=True)
p.add_argument('--mode', choices=['core','death','victory','leg0','leg1','leg2','leg3','controls','avoidance','healing','guard','stance','integration','collision'], required=True)
p.add_argument('--slot-wait-seconds', type=int, default=180, help='Bounded shared-slot queue wait, 30 to 3600 seconds; does not extend test duration')
p.add_argument('--video-fps', type=int, choices=range(1,16), help='Optional native capture cadence; adds measurable overhead')
p.add_argument('--performance',action='store_true',help='Exclusive GPU lease; no screenshots/video, sparse diagnostics; audio remains enabled')
p.add_argument('--start-two-handed', action='store_true', help='Victory QA uses the ordinary authored grip input before combat')
p.add_argument('--width', type=int, default=1280)
p.add_argument('--height', type=int, default=720)
a = p.parse_args()
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
    launch = [str(executable), '/Game/Maps/VeyrArena']
else:
    executable = a.engine / 'Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor'
    launch = [str(executable), str(project), '/Game/Maps/VeyrArena', '-game']
if not executable.is_file():
    p.error('Runtime executable is missing')
(run/'launch.json').write_text(json.dumps({'runtimeKind':'packaged-app' if a.app else 'editor-game', 'executableSHA256':hashlib.sha256(executable.read_bytes()).hexdigest(), 'resolution':[a.width,a.height], 'screenPercentage':100, 'fpsCap':60, 'silent':not a.performance,'performanceMode':a.performance},indent=2)+'\n')
cmd = [str(a.gpu_slot), 'perf' if a.performance else 'capture', '--label', 'veyr-' + a.mode, '--timeout', str(a.slot_wait_seconds), '--json', str(run/'gpu.json'), '--', *launch, '-RenderOffScreen', '-unattended', '-NoCrashReports', '-NoSound', '-notraceserver', '-NoZenAutoLaunch', '-DDC=(EnginePak=InstalledEnginePak,Local)', '-LocalDataCachePath='+str(project.parent/'DerivedDataCache'), '-ResX='+str(a.width), '-ResY='+str(a.height), '-ForceRes', '-ExecCmds=t.MaxFPS 60,r.ScreenPercentage 100', '-VeyrReplay='+a.mode, '-VeyrEvidence='+str(run), '-VeyrReplayQuit', '-abslog='+str(run/'native.log')]
if a.performance:
    if a.video_fps:p.error('Performance and video capture are mutually exclusive')
    cmd.remove('-NoSound');cmd.append('-VeyrPerformance')
if a.video_fps:
    cmd.append('-VeyrVideoFPS='+str(a.video_fps))
if a.start_two_handed:
    if a.mode!='victory':p.error('--start-two-handed applies only to victory validation')
    cmd.append('-VeyrReplayStartTwoHanded')
print('Native run:', run, flush=True)
with (run/'launcher.log').open('w') as output:
    environment = os.environ.copy()
    environment['GPU_SLOT_CAPTURE_SLOTS'] = '2'
    # Direct executable launches do not receive Info.plist LSEnvironment from
    # LaunchServices. Honor only this explicit app-owned allocator setting.
    if a.app and info.get('LSEnvironment',{}).get('UE4_FORCE_MALLOC_ANSI')=='1':
        environment['UE4_FORCE_MALLOC_ANSI']='1'
    result = subprocess.run(cmd, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
print('Process exit:', result.returncode, 'Evidence:', run, flush=True)
if result.returncode:
    raise SystemExit(result.returncode)
results = list(run.glob('unreal-*/evidence.json'))
if len(results) != 1:
    raise SystemExit('Expected one completed native evidence file')
evidence = json.loads(results[0].read_text())
print('Scenario:', evidence.get('passed'), evidence.get('reason'), flush=True)
raise SystemExit(0 if evidence.get('finalWrite') and evidence.get('finished') and evidence.get('passed') else 1)
