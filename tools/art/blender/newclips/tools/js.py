import sys, importlib.util, numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation
REPO = Path("/Users/midir/veyr-review-fable-20261021")
spec = importlib.util.spec_from_file_location("eval", REPO / "tools/unreal/normalize_customuse_glb.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
g = m.GLB(Path(sys.argv[1])); A = g.json["animations"][0]; out = []
for ch in A["channels"]:
    if ch["target"]["path"] == "rotation":
        s = A["samplers"][ch["sampler"]]; q = Rotation.from_quat(g.accessor(s["output"])); tt = np.asarray(g.accessor(s["input"])).ravel()
        st = np.rad2deg((q[:-1].inv() * q[1:]).magnitude()); i = int(st.argmax())
        if st[i] > 20: out.append((round(float(st[i]), 1), g.json["nodes"][ch["target"]["node"]].get("name"), round(float(tt[i]) * 150), [round(float(x)) for x in st[max(0, i - 3):i + 4]]))
for o in sorted(out, reverse=True)[:15]: print(o)
