"""bandcx.py DIR VIEW : silhouette centre x (px, blade excluded) of chest / pelvis bands per frame."""
import sys, glob
import numpy as np
from PIL import Image
D, V = sys.argv[1], sys.argv[2]; rows = {}
for fn in sorted(glob.glob(f"{D}/{V}-full-*.png")):
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grey = (abs(r - g) < 18) & (abs(g - b) < 22) & (r > 80)
    ys, xs = np.nonzero(grey); top, bot = ys.min(), ys.max(); H = bot - top
    for nm, (f0, f1) in {"chest": (.20, .32), "waist": (.36, .44), "pelvis": (.46, .54)}.items():
        sel = grey[int(top + f0 * H):int(top + f1 * H)]; yy, xx = np.nonzero(sel)
        rows.setdefault(nm, []).append(round(float((xx.min() + xx.max()) / 2), 1))
for k, v in rows.items(): print(k, v)
