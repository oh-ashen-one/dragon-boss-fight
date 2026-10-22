#!/usr/bin/env python3
"""Client: run a newclips Blender-side script function in the task-owned Blender (veyr_rpc owner guard).

  python3 tools/art/blender/newclips/run_nc.py SCRIPT "CALL"   (env VEYR_BLENDER_PORT / VEYR_BLENDER_OWNER required)
"""
import datetime, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
script = (HERE / sys.argv[1]).resolve(); call = sys.argv[2]
assert script.parent == HERE and script.is_file() and script.name != "run_nc.py", script
code = ("import json\n" f"_f={str(script)!r}\n" "_g={'__file__':_f,'__name__':'veyr_nc'}\n"
        "exec(compile(open(_f).read(),_f,'exec'),_g)\n" f"_r=eval({call!r},_g)\n" "print('NC_RESULT '+json.dumps(_r,default=str))\n")
out = REPO / "Local/Blender/newclips-20261021/rpc"; out.mkdir(parents=True, exist_ok=True)
f = out / (datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f") + "-" + script.stem + ".py"); f.write_text(code)
assert os.environ.get("VEYR_BLENDER_PORT") and os.environ.get("VEYR_BLENDER_OWNER")
sys.exit(subprocess.run([sys.executable, str(REPO / "tools/art/blender/veyr_rpc.py"), str(f)]).returncode)
