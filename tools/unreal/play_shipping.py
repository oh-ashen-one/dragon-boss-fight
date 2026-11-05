#!/usr/bin/env python3
"""macOS launcher for a verified Shipping app; never starts the editor."""
import argparse,json,subprocess,datetime
from pathlib import Path
from owned_launch_budget import wait_for_budget
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--app',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
app=a.app or Path(json.loads((ROOT/'Local/LatestShipping.json').read_text())['app'])
assert app.name=='Veyr-Mac-Shipping.app' and app.is_dir(),'Verified Shipping app missing'
result=subprocess.run(['codesign','--verify','--deep','--strict',str(app)],capture_output=True);assert result.returncode==0,'Shipping signature check failed'
if a.check:print('Shipping app and signature verified');raise SystemExit(0)
gate=Path.home()/'.cache/gpu-slot/bin/gpu_slot.sh';assert gate.is_file(),'Shared GPU guard missing'
if (ROOT/'Local/ENGINE_LAUNCH_HOLD.json').exists():raise SystemExit('Task engine-launch hold is active')
wait_for_budget(ROOT)
receipt=ROOT/'Local'/('play-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-gpu.json')
raise SystemExit(subprocess.call([str(gate),'capture','--label','veyr-owner-play','--timeout','180','--json',str(receipt),'--','open','-g','-W','-n',str(app),'--args','/Game/Maps/VeyrArena','-windowed','-ResX=1280','-ResY=720','-ExecCmds=t.MaxFPS 60','-NoCrashReports','-notraceserver','-VeyrCanonicalKnightSkin','-VeyrStableWeaponPresentation','-VeyrWalkEntryBlend','-VeyrReadableAutoLock']))
