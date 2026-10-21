#!/usr/bin/env python3
"""Run a feedback_v4 Blender script function in the task-owned Blender via veyr_rpc.py.

  python3 tools/art/blender/feedback_v4/run.py [--owner O] [--port N] [--scene-in DIR]
      [--out DIR] [--export-dir DIR] [--revision R] [--allow-overwrite] SCRIPT CALL

SCRIPT is revise.py, render.py or contact_audit.py (in this folder). CALL is a Python
expression evaluated in that script's namespace, e.g. "open_job('guard_two')".
The generated command sets __file__ to the script's real path and passes the
parameters as VEYR_V4_PARAMS; scripts re-tag session_owner after opening any .blend
so veyr_rpc.py's owner guard keeps passing. veyr_rpc.py's own owner guard runs first.
Generated command files are kept under <out>/rpc/ for the record.
"""
import argparse, datetime, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--owner'); ap.add_argument('--port')
ap.add_argument('--scene-in'); ap.add_argument('--out'); ap.add_argument('--export-dir')
ap.add_argument('--revision'); ap.add_argument('--allow-overwrite', action='store_true')
ap.add_argument('script'); ap.add_argument('call')
a = ap.parse_args()
sys.path.insert(0, str(HERE))
import common  # noqa: E402  (plain helper, no bpy at import)
script = (HERE / a.script).resolve()
if script.parent != HERE or not script.is_file() or script.name in ('run.py', 'common.py', 'audit_exports.py'):
    ap.error('SCRIPT must be a Blender-side script in feedback_v4')
overrides = {'owner': a.owner, 'scene_in': a.scene_in, 'out': a.out, 'export_dir': a.export_dir,
             'revision': a.revision, 'allow_overwrite': True if a.allow_overwrite else None}
p = common.params(overrides)  # validates paths client-side too
params = {k: v for k, v in overrides.items() if v is not None}
params.setdefault('owner', p['owner'])
code = (
    "import json\n"
    f"_f={str(script)!r}\n"
    f"_g={{'__file__':_f,'__name__':'veyr_v4_'+{script.stem!r},'VEYR_V4_PARAMS':json.loads({json.dumps(params)!r})}}\n"
    "exec(compile(open(_f).read(),_f,'exec'),_g)\n"
    f"_r=eval({a.call!r},_g)\n"
    "print('V4_RESULT '+json.dumps(_r,default=str))\n")
rpc_dir = p['out'] / 'rpc'; rpc_dir.mkdir(parents=True, exist_ok=True)
cmd_file = rpc_dir / (datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f') + '-' + script.stem + '.py')
cmd_file.write_text(code)
env = dict(os.environ, VEYR_BLENDER_OWNER=p['owner'])
if a.port: env['VEYR_BLENDER_PORT'] = a.port
if not env.get('VEYR_BLENDER_PORT'): ap.error('pass --port or set VEYR_BLENDER_PORT (never rely on the 9881 default)')
sys.exit(subprocess.run([sys.executable, str(REPO / 'tools/art/blender/veyr_rpc.py'), str(cmd_file)], env=env).returncode)
