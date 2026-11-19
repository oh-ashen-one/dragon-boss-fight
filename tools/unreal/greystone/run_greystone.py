#!/usr/bin/env python3
"""Run one Greystone editor-Python step in an owned, unattended PythonScriptCommandlet.

usage: run_greystone.py <step> [--set key=value ...] [--project /path/to/Unreal/Veyr]
steps: load-all, skin, rigs, native, retarget, definition, motion-db, features   (NullRHI: no window, no GPU)
       skin-sheet                                                  (renders: shared GPU slot, never while STREAMING)

Rules kept (BUILDER_RULES): the machine-wide engine lock (tools/unreal/engine_lock.py) is held for exactly the
commandlet's life, the owned launch-rate budget, Local/ENGINE_LAUNCH_HOLD.json stops everything, the started PID is
recorded and only that PID is ever signalled (the lock forwards signals to it). Evidence goes to a new Local/greystone/<step>-<UTC> directory.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import greystone_common as g

STEPS = {
    'load-all': ('load_all.py', False),
    'rigs': ('make_rigs.py', False),
    'native': ('measure_native.py', False),
    'skin': ('novaborn_gold.py', False),
    'retarget': ('retarget_clips.py', False),
    'definition': ('build_definition.py', False),
    'motion-db': ('make_motion_databases.py', False),
    'features': ('bake_motion_features.py', False),
    'skin-sheet': ('skin_sheet.py', True),
}
ENGINE = Path('/Users/Shared/Epic Games/UE_5.8')

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('step', choices=sorted(STEPS))
p.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='job option (JSON value or string)')
p.add_argument('--project', type=Path, default=g.PROJECT)
p.add_argument('--slot-wait-seconds', type=int, default=1800)
a = p.parse_args()

project = a.project.resolve()
root = project.parents[1]
assert (project / 'Veyr.uproject').is_file()
if (root / 'Local/ENGINE_LAUNCH_HOLD.json').exists():
    sys.exit('Task engine-launch hold is active')
script, rendered = STEPS[a.step]
streaming = Path.home() / '.cache/gpu-slot/STREAMING'
if rendered and streaming.exists():
    sys.exit('STREAMING flag present: no rendered launch (the skin sheet waits for the stream window to end)')

options = {}
for item in a.set:
    key, _, value = item.partition('=')
    try:
        options[key] = json.loads(value)
    except json.JSONDecodeError:
        options[key] = value

stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out = root / 'Local/greystone' / f'{a.step}-{stamp}'
out.mkdir(parents=True, exist_ok=False)
job = {'step': a.step, 'reportDirectory': str(out), 'options': options, 'project': str(project)}
(out / 'job.json').write_text(json.dumps(job, indent=2) + '\n')


if rendered:  # the ten-per-hour budget counts rendered launches only
    from owned_launch_budget import wait_for_budget
    wait_for_budget(root)

cmd = ['/usr/sbin/taskpolicy', '-b', str(ENGINE / 'Engine/Binaries/Mac/UnrealEditor-Cmd'), str(project / 'Veyr.uproject'),
       '-run=pythonscript', '-script=' + str(HERE / script), '-unattended', '-NoCrashReports', '-notraceserver',
       '-NoZenAutoLaunch', '-NoSound', '-DDC=(EnginePak=InstalledEnginePak,Local)',
       '-LocalDataCachePath=' + str(project / 'DerivedDataCache'), '-abslog=' + str(out / 'engine.log')]
if rendered:
    gate = Path.home() / '.cache/gpu-slot/bin/gpu_slot.sh'
    assert gate.is_file(), 'Shared GPU guard missing'
    cmd = [str(gate), 'capture', '--label', 'veyr-greystone-' + a.step, '--timeout', str(a.slot_wait_seconds),
           '--json', str(out / 'gpu.json'), '--', *cmd, '-AllowCommandletRendering', '-ExecCmds=t.MaxFPS 30']
else:
    cmd.append('-nullrhi')
(out / 'command.json').write_text(json.dumps(cmd, indent=2) + '\n')
print('Greystone step', a.step, '->', out, flush=True)
from engine_lock import engine_lock
# Machine-wide engine lock (BUILDER_RULES 2026-11-19) for exactly the commandlet's life; the lock forwards SIGTERM/SIGINT
# to the child only and records its pid so an orphan is noticed.
with engine_lock('E trial: ' + a.step, tree=root) as lock:
    started = time.time()
    with (out / 'launcher.log').open('w') as log:
        env = {**os.environ, 'VEYR_GREYSTONE_JOB': str(out / 'job.json'), 'VEYR_GREYSTONE_PROJECT': str(project)}
        result_proc = lock.run(cmd, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    code = result_proc.returncode
    lock.exit_code = code
    try:  # read-only: the lock recorded our child's pid in its holder file while we still hold it
        from engine_lock import lock_dir
        holder = json.loads((lock_dir() / 'holder.json').read_text())
    except (OSError, ValueError):
        holder = {}
    (out / 'pid.json').write_text(json.dumps({'pid': holder.get('child_pid'), 'driverPid': os.getpid(), 'args0': cmd[0],
                                              'minutes': round((time.time() - started) / 60, 1)}) + '\n')
result = json.loads((out / 'result.json').read_text()) if (out / 'result.json').exists() else {}
print('exit', code, 'success', result.get('success'), result.get('error', ''), flush=True)
sys.exit(0 if result.get('success') else 1)
