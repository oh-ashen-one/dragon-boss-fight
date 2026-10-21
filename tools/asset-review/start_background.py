#!/usr/bin/env python3
"""Start/restart this checkout's loopback reviewer without a terminal window."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[2];LOCAL=ROOT/'Local';PID=LOCAL/'review-service.pid';SERVER=ROOT/'tools/asset-review/server.py'
p=argparse.ArgumentParser();p.add_argument('--restart',action='store_true');args=p.parse_args()
def ready():
 try:
  with urllib.request.urlopen('http://127.0.0.1:8775/api/catalog',timeout=1) as response:data=json.load(response)
  return isinstance(data.get('items'),list) and any(x['id']=='knight/KnightRig.glb' for x in data['items'])
 except Exception:return False
if args.restart and PID.exists():
 pid=int(PID.read_text().strip());cmd=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
 if cmd and str(SERVER) not in cmd:raise RuntimeError('Preserving an unrelated PID')
 if cmd:
  os.kill(pid,signal.SIGTERM)
  for _ in range(30):
   if not ready():break
   time.sleep(.1)
if ready():print('Existing private viewer is ready; preserved current process');sys.exit(0)
LOCAL.mkdir(exist_ok=True)
with (LOCAL/'review-service.log').open('ab',buffering=0) as log:
 child=subprocess.Popen([sys.executable,str(SERVER),'--local-only','--port','8775'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'PYTHONUNBUFFERED':'1'})
PID.write_text(str(child.pid)+'\n')
for _ in range(30):
 if ready():print('Detached review server ready:',child.pid);sys.exit(0)
 if child.poll() is not None:break
 time.sleep(.1)
raise RuntimeError('Viewer did not become ready; inspect Local/review-service.log')
