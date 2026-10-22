"""shoulderpx.py DIR VIEW : silhouette width (px) at the shoulder band (bodyTop + 18% of figure height), ignoring blade pixels."""
import sys, glob, json
import numpy as np
from PIL import Image
D, V = sys.argv[1], sys.argv[2]; out = []
for fn in sorted(glob.glob(f"{D}/{V}-full-*.png")):
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grey = (abs(r - g) < 18) & (abs(g - b) < 22) & (r > 80)
    ys, xs = np.nonzero(grey); top, bot = ys.min(), ys.max(); row = int(top + .18 * (bot - top))
    band = grey[row - 2:row + 3]; cols = np.nonzero(band.any(axis=0))[0]
    out.append({"f": int(fn.rsplit("-", 1)[1][:4]), "row": row, "width": int(cols.max() - cols.min() + 1) if len(cols) else 0})
print(json.dumps(out))
