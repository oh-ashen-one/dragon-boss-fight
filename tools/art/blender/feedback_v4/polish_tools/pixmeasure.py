"""pixmeasure.py DIR VIEW : per-frame pixel metrics of <VIEW>-full-NNNN.png renders.
blade angle (deg, PCA of orange mask) and its per-frame delta, blade lowest/top row, body top row (helmet),
lowest silhouette row, changed-pixel count vs previous frame, silhouette width at shoulder band."""
import sys, glob, json, math
import numpy as np
from PIL import Image
D, V = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(f"{D}/{V}-full-*.png")); prev = None; out = []; pang = None
for fn in fs:
    a = np.asarray(Image.open(fn).convert("RGB")).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    orange = (r > 90) & (r > g * 1.35) & (r > b * 1.8)
    bg = (abs(r - g) < 12) & (abs(g - b) < 14) & (r < 75)
    grey = (~orange) & (abs(r - g) < 18) & (abs(g - b) < 22) & (r > 80)
    sil = ~bg
    row = {"f": int(fn.rsplit("-", 1)[1][:4])}
    ys, xs = np.nonzero(orange)
    if len(xs) > 20:
        cx, cy = xs.mean(), ys.mean(); C = np.cov(np.vstack([xs - cx, ys - cy])); w, v = np.linalg.eigh(C); ax = v[:, np.argmax(w)]
        ang = math.degrees(math.atan2(-ax[1], ax[0])) % 180
        row.update(bladeAngle=round(ang, 1), bladeLowRow=int(ys.max()), bladeTopRow=int(ys.min()), bladeCx=round(cx, 1), bladeCy=round(cy, 1))
        if pang is not None:
            d = (ang - pang + 90) % 180 - 90; row["bladeDelta"] = round(d, 1)
        pang = ang
    gy, gx = np.nonzero(grey)
    if len(gy): row.update(bodyTopRow=int(gy.min()), bodyBottomRow=int(gy.max()))
    sy, sx = np.nonzero(sil)
    if len(sy): row["silBottomRow"] = int(sy.max())
    if prev is not None: row["changedPx"] = int((np.abs(a - prev).max(axis=2) > 12).sum())
    prev = a; out.append(row)
print(json.dumps(out))
