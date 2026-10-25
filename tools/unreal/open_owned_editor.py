#!/usr/bin/env python3
"""Open one Veyr editor through the shared two-renderer coordinator.

Uses the previously approved native loopback MCP port. Never restarts a crashed
editor, changes foreign processes, opens terminals or clears an engine hold.
Close the owned editor normally to release its slot. Logs remain private Local.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine', type=Path, required=True)
parser.add_argument('--gpu-slot', type=Path, required=True)
parser.add_argument('--video-fps',type=int,choices=range(1,16))
parser.add_argument('--replay-start-two-handed',action='store_true',help='Victory QA requests the ordinary authored grip transition before combat')
parser.add_argument('--slot-wait-seconds', type=int, default=1800)
a = parser.parse_args()
if not 30 <= a.slot_wait_seconds <= 3600:
    parser.error('Slot wait must be 30..3600 seconds')
if (ROOT/'Local/ENGINE_LAUNCH_HOLD.json').exists():
    parser.error('An explicit task-local launch hold is present; inspect its reason')
project = ROOT/'Unreal/Veyr/Veyr.uproject'
engine = a.engine/'Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor'
if not project.is_file() or not engine.is_file() or not a.gpu_slot.is_file():
    parser.error('Project, editor executable or slot coordinator is missing')
try:
    with socket.create_connection(('127.0.0.1',18773),timeout=1):
        parser.error('Native MCP port is occupied; inspect and reuse its owned editor instead of launching a duplicate')
except (ConnectionRefusedError,TimeoutError):
    pass
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
run = ROOT/'Local'/('owned-editor-'+stamp)
run.mkdir(mode=0o700,parents=True,exist_ok=False)
command = [str(a.gpu_slot),'capture','--label','veyr-customuse-editor','--timeout',str(a.slot_wait_seconds),
           '--json',str(run/'gpu.json'),'--','/usr/bin/open','-W','-n','--env','UE4_FORCE_MALLOC_ANSI=1',
           str(engine.parents[2]),'--args',str(project),'-ModelContextProtocolStartServer',
           '-ModelContextProtocolPort=18773','-notraceserver','-NoZenAutoLaunch','-NoCrashReports',
           '-asyncstaticmeshcompilation=0','-asyncskinnedassetcompilation=0',
           '-DDC=(EnginePak=InstalledEnginePak,Local)','-LocalDataCachePath='+str(project.parent/'DerivedDataCache'),
           '-windowed','-ResX=1280','-ResY=720','-nosplash','-abslog='+str(run/'editor.log')]
if a.video_fps:command.append('-VeyrVideoFPS='+str(a.video_fps))
if a.replay_start_two_handed:command.append('-VeyrReplayStartTwoHanded')
(run/'launch.json').write_text(json.dumps({'command':command,'autoRestart':False,'rendererLimit':2},indent=2)+'\n')
environment=os.environ.copy();environment['GPU_SLOT_CAPTURE_SLOTS']='2'
print('Owned editor run:',run,flush=True)
with (run/'launcher.log').open('w') as output:
    result=subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
print('Owned editor exited:',result.returncode,flush=True)
raise SystemExit(result.returncode)
