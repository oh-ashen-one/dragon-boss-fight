#!/usr/bin/env python3
"""Run one native input replay through the existing shared GPU slot protocol."""
import argparse
import datetime
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--engine', type=Path, required=True)
p.add_argument('--gpu-slot', type=Path, required=True)
p.add_argument('--mode', choices=['core','death','victory','leg0','leg1','leg2','leg3','controls','avoidance'], required=True)
p.add_argument('--width', type=int, default=1280)
p.add_argument('--height', type=int, default=720)
a = p.parse_args()
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
run = ROOT / 'Evidence' / ('native-' + a.mode + '-' + stamp)
run.mkdir(parents=True)
project = ROOT / 'Unreal/Veyr/Veyr.uproject'
engine = a.engine / 'Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor'
cmd = [str(a.gpu_slot), 'capture', '--label', 'veyr-' + a.mode, '--timeout', '180', '--json', str(run/'gpu.json'), '--', str(engine), str(project), '/Game/Maps/VeyrArena', '-game', '-RenderOffScreen', '-unattended', '-NoCrashReports', '-NoSound', '-notraceserver', '-NoZenAutoLaunch', '-DDC=(EnginePak=InstalledEnginePak,Local)', '-LocalDataCachePath='+str(project.parent/'DerivedDataCache'), '-ResX='+str(a.width), '-ResY='+str(a.height), '-ForceRes', '-ExecCmds=t.MaxFPS 60,r.ScreenPercentage 100', '-VeyrReplay='+a.mode, '-VeyrEvidence='+str(run), '-VeyrReplayQuit', '-abslog='+str(run/'native.log')]
print('Native run:', run, flush=True)
with (run/'launcher.log').open('w') as output:
    result = subprocess.run(cmd, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
print('Process exit:', result.returncode, 'Evidence:', run, flush=True)
raise SystemExit(result.returncode)
