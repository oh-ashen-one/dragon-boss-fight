"""headpx.py DIR VIEW : helmet-top point per frame (top 6 rows of the grey body mask) and its per-frame displacement (px)."""
import sys, glob, json, math
import numpy as np
from PIL import Image
D, V = sys.argv[1], sys.argv[2]; out = []; prev = None
for fn in sorted(glob.glob(f"{D}/{V}-full-*.png")):
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grey = (abs(r - g) < 18) & (abs(g - b) < 22) & (r > 80) & ~((r > 90) & (r > g * 1.35))
    ys, xs = np.nonzero(grey); top = ys.min(); sel = ys <= top + 6; p = (float(xs[sel].mean()), float(ys[sel].mean()))
    d = math.hypot(p[0] - prev[0], p[1] - prev[1]) if prev else 0.; prev = p
    out.append({"f": int(fn.rsplit("-", 1)[1][:4]), "x": round(p[0], 1), "y": round(p[1], 1), "d": round(d, 1)})
print(json.dumps(out))
