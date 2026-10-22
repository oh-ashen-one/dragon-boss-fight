"""bandpx.py DIR VIEW : silhouette width (px) at several fractions of figure height (blade excluded); prints min/max per band."""
import sys, glob, json
import numpy as np
from PIL import Image
D, V = sys.argv[1], sys.argv[2]; fr = [.14, .18, .22, .26, .30, .34]; W = {f: [] for f in fr}
for fn in sorted(glob.glob(f"{D}/{V}-full-*.png")):
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    grey = (abs(r - g) < 18) & (abs(g - b) < 22) & (r > 80)
    ys, xs = np.nonzero(grey); top, bot = ys.min(), ys.max()
    for f in fr:
        row = int(top + f * (bot - top)); cols = np.nonzero(grey[row - 2:row + 3].any(axis=0))[0]
        W[f].append(int(cols.max() - cols.min() + 1) if len(cols) else 0)
for f in fr: print(V, f, min(W[f]), max(W[f]), W[f])
