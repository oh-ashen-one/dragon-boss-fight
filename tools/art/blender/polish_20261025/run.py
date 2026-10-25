"""Dispatch authored Blender scripts through the owned MCP, with stored commands."""
import os,sys,subprocess,datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];OUT=ROOT/'Local/Blender/polish-20261025';OUT.mkdir(parents=True,exist_ok=True)
f=(HERE/sys.argv[1]).resolve();assert f.parent==HERE
code=f"__file__={str(f)!r}\nexec(compile(open(__file__).read(),__file__,'exec'),globals())\n"+'\n'.join(sys.argv[2:])
p=OUT/'session'/('cmd-'+datetime.datetime.now().strftime('%H%M%S%f')+'.py');p.write_text(code)
env=dict(os.environ,VEYR_BLENDER_OWNER='codex-veyr-polish-20261025',VEYR_BLENDER_PORT='9891')
r=subprocess.run([sys.executable,str(ROOT/'tools/art/blender/veyr_rpc.py'),str(p)],env=env,capture_output=True,text=True)
(OUT/'session'/(p.stem+'.log')).write_text(r.stdout+r.stderr)
print((r.stdout+r.stderr)[-2200:])
sys.exit(r.returncode)
