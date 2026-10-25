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
import tempfile
from audit_bundle import repair_copy

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
# Use a fresh task-owned stage outside Documents/FileProvider. The source tree,
# earlier stages and failed archives remain intact for recovery and diagnosis.
stage_base=Path(tempfile.mkdtemp(prefix='veyr-stage-',dir='/private/tmp'))
(stage_base/'veyr-stage-owner.json').write_text(json.dumps({'project':str(project.parent.resolve()),'receiptDirectory':str(receipt_dir.resolve())})+'\n')
cooker_options = '-nullrhi -NoCrashReports -notraceserver -NoZenAutoLaunch -DDC=(EnginePak=InstalledEnginePak,Local) -LocalDataCachePath="' + str(project.parent/'DerivedDataCache') + '" -SkipZenStore'
command = [str(engine/'Engine/Build/BatchFiles/RunUAT.sh'), 'BuildCookRun', '-project='+str(project), '-noP4', '-platform=Mac', '-clientconfig=Development', '-skipbuild', '-skipbuildeditor', '-cook', '-map=/Game/Maps/VeyrArena', '-stage', '-stagingdirectory='+str(stage_base), '-pak', '-archive', '-archivedirectory='+str(archive), '-unattended', '-utf8output', '-AdditionalCookerOptions='+cooker_options]
with (receipt_dir/'package.log').open('w') as output:
    result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
apps = list(archive.rglob('Veyr.app')) if archive.exists() else []
uat_success = result.returncode == 0 and bool(apps)
repairs = []
if uat_success:
    for app in apps:
        try:
            # Preserve UAT's raw archive for diagnosis. UE's Mac archive can
            # omit Contents/UE even though staging succeeded; never accept the
            # existence of a .app as evidence of a self-contained package.
            repaired = archive / 'Repaired' / app.relative_to(archive)
            repairs.append(repair_copy(app, stage_base/'Mac/Veyr.app',
                                       repaired, project.parent/'Binaries/Mac/Veyr.target', engine, owned_stage_root=stage_base))
        except (OSError, ValueError, KeyError) as error:
            repairs.append({'sourceApp':str(app), 'packagingSucceeded':False, 'error':str(error)})
success = uat_success and bool(repairs) and all(item['packagingSucceeded'] for item in repairs)
receipt = {'packagingSucceeded':success, 'uatSucceeded':uat_success, 'uatExitCode':result.returncode,
           'stagingDirectory':str(stage_base),
           'exitCode':0 if success else result.returncode or 1,
           'originalArchives':[str(x) for x in apps], 'bundleRepairs':repairs,
           'apps':[item['signature']['verifiedRuntimeApp'] for item in repairs if item['packagingSucceeded']],
           'signedArchives':[{'path':item['signature']['signedZip'], 'sha256':item['signature']['archiveSHA256']}
                             for item in repairs if item['packagingSucceeded']],
           'nativePackagedGameplayVerified':False}
(receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt), flush=True)
raise SystemExit(0 if success else 1)
