#!/usr/bin/env python3
"""Build and package the native Mac app without launching a renderer.

Uses an existing installed Unreal engine. Receipts and build products stay local.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--engine', required=True, type=Path)
a = p.parse_args()
if (ROOT / 'Local/ENGINE_LAUNCH_HOLD.json').exists():
    p.error('Engine launches are held after two crashes; obtain owner approval before clearing the task-local hold.')
engine = a.engine.resolve()
project = ROOT / 'Unreal/Veyr/Veyr.uproject'
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive = ROOT / 'Builds' / ('Unreal-Mac-' + stamp)
receipt_dir = ROOT / 'Local' / ('package-' + stamp)
receipt_dir.mkdir(parents=True, mode=0o700)
print('Archive:', archive, 'Log:', receipt_dir/'package.log', flush=True)
# Embed and verify the exact source identity in the native target first.
build = subprocess.run([sys.executable, str(ROOT/'tools/unreal/build.py'), '--engine', str(engine), '--target', 'Veyr'], cwd=ROOT)
if build.returncode:
    raise SystemExit(build.returncode)
cooker_options = '-nullrhi -NoCrashReports -notraceserver -NoZenAutoLaunch -DDC=(EnginePak=InstalledEnginePak,Local) -LocalDataCachePath="' + str(project.parent/'DerivedDataCache') + '" -SkipZenStore'
command = [str(engine/'Engine/Build/BatchFiles/RunUAT.sh'), 'BuildCookRun', '-project='+str(project), '-noP4', '-platform=Mac', '-clientconfig=Development', '-skipbuild', '-skipbuildeditor', '-cook', '-map=/Game/Maps/VeyrArena', '-stage', '-pak', '-archive', '-archivedirectory='+str(archive), '-unattended', '-utf8output', '-AdditionalCookerOptions='+cooker_options]
with (receipt_dir/'package.log').open('w') as output:
    result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
apps = list(archive.rglob('Veyr.app')) if archive.exists() else []
success = result.returncode == 0 and bool(apps)
receipt = {'packagingSucceeded':success, 'exitCode':result.returncode, 'apps':[str(x) for x in apps], 'nativePackagedGameplayVerified':False}
(receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt), flush=True)
raise SystemExit(0 if success else 1)
