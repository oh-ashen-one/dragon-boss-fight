import sys, importlib.util, numpy as np
from pathlib import Path
REPO = Path("/Users/midir/veyr-review-fable-20261021")
spec = importlib.util.spec_from_file_location("eval", REPO / "tools/unreal/normalize_customuse_glb.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
g = m.GLB(Path(sys.argv[1])); ns = {n.get("name"): i for i, n in enumerate(g.json["nodes"])}
dur = max(float(np.asarray(g.accessor(s["input"])).max()) for s in g.json["animations"][0]["samplers"])
socket = ns["ReviewWeaponSocket"]; cp = np.array([0, -.075, 0, 1]); w0 = g.world_matrices(0, 0.); contact = np.linalg.solve(w0[ns["RightHand"]], w0[socket] @ cp)
rows = []
for t in np.linspace(0, dur, round(dur * 120) + 1):
    w = g.world_matrices(0, float(t)); rows.append((float(np.linalg.norm((w[ns["RightHand"]] @ contact - w[socket] @ cp)[:3])), round(float(t) * 150, 1)))
print(sorted(rows, reverse=True)[:12])
