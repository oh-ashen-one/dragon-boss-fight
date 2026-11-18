#!/usr/bin/env python3
"""Run one Greystone editor-Python step in an owned, unattended PythonScriptCommandlet.

usage: run_greystone.py <step> [--set key=value ...] [--project /path/to/Unreal/Veyr]
steps: load-all, rigs, retarget, definition, motion-db, features   (NullRHI: no window, no GPU)
       skin-sheet                                                  (renders: shared GPU slot, never while STREAMING)

Rules kept (BUILDER_RULES): one engine process at a time (waits until no UnrealEditor / Veyr game is running), the
owned launch-rate budget, Local/ENGINE_LAUNCH_HOLD.json stops everything, the started PID is recorded and only that
PID is ever signalled. Evidence goes to a new Local/greystone/<step>-<UTC> directory.
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


def engine_processes():
    rows = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout.splitlines()
    hits = []
    for row in rows:
        pid, _, command = row.strip().partition(' ')
        if ('UnrealEditor' in command or 'Veyr-Mac' in command or '/Veyr.app/' in command) and 'run_greystone.py' not in command:
            hits.append((int(pid), command[:160]))
    return hits


announced = False
while engine_processes():
    if not announced:
        print('Waiting: another engine/game process is running (one at a time):', engine_processes()[:3], flush=True)
        announced = True
    time.sleep(30)
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
with (out / 'launcher.log').open('w') as log:
    process = subprocess.Popen(cmd, cwd=root, env={**os.environ, 'VEYR_GREYSTONE_JOB': str(out / 'job.json'), 'VEYR_GREYSTONE_PROJECT': str(project)},
                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    (out / 'pid.json').write_text(json.dumps({'pid': process.pid, 'command': cmd[0]}) + '\n')
    try:
        code = process.wait()
    except KeyboardInterrupt:
        # Signal only the PID we started; give it 60 s to exit before anything stronger.
        process.send_signal(signal.SIGTERM)
        try:
            code = process.wait(60)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait()
result = json.loads((out / 'result.json').read_text()) if (out / 'result.json').exists() else {}
print('exit', code, 'success', result.get('success'), result.get('error', ''), flush=True)
sys.exit(0 if result.get('success') else 1)
