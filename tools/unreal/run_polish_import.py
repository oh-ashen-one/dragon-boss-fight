#!/usr/bin/env python3
"""Run the hash-locked null-renderer import/activation commandlet for one prepared knight plan.

usage: run_polish_import.py <import-plan-KnightB.json> <report directory under Local/>
No window and no GPU: UnrealEditor-Cmd with -nullrhi. Refuses to reuse a report directory.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path('/Users/Shared/Epic Games/UE_5.8')
plan = Path(sys.argv[1]).resolve(strict=True)
out = Path(sys.argv[2]).resolve()
assert out.is_relative_to((ROOT/'Local').resolve()) and not out.exists(), 'report directory must be new and under Local/'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
job = {'operation': 'import', 'verifyCanonicalSkin': True, 'plan': str(plan), 'planSHA256': sha(plan),
       'reportDirectory': str(out),
       'activeManifestSHA256': sha(ROOT/'Local/CustomuseAssets/Polish20261025/active-plans.json'),
       'runtimeAssetSHA256': sha(ROOT/'Unreal/Veyr/Content/Characters/Customuse/RuntimePolish/DA_Knight.uasset')}
out.mkdir(parents=True)
(out/'job.json').write_text(json.dumps(job, indent=2)+'\n')
project = ROOT/'Unreal/Veyr/Veyr.uproject'
cmd = ['/usr/sbin/taskpolicy', '-b', str(ENGINE/'Engine/Binaries/Mac/UnrealEditor-Cmd'), str(project), '-run=pythonscript',
       '-script='+str(ROOT/'tools/unreal/import_polish_commandlet.py'), '-nullrhi', '-unattended', '-NoCrashReports',
       '-notraceserver', '-NoZenAutoLaunch', '-DDC=(EnginePak=InstalledEnginePak,Local)',
       '-LocalDataCachePath='+str(project.parent/'DerivedDataCache'), '-abslog='+str(out/'engine.log')]
(out/'command.json').write_text(json.dumps(cmd, indent=2)+'\n')
with (out/'launcher.log').open('w') as log:
    code = subprocess.run(cmd, env={**os.environ, 'VEYR_NATIVE_IMPORT_JOB': str(out/'job.json')}, stdin=subprocess.DEVNULL,
                          stdout=log, stderr=subprocess.STDOUT).returncode
result = json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else {}
print('exit', code, 'stage', result.get('stage'), 'success', result.get('success'), result.get('error', ''))
raise SystemExit(0 if result.get('success') else 1)
