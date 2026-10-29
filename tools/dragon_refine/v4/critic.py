"""The blind critic's round-2 metric definitions (Local/dragon-review-20261029/critique-round2.md, Method), ported to work on
arrays so the same code measures (a) the CPU raster of an Action (raster.py) and (b) segmented review renders.
All image metrics are in pixels of the 960x540 review frame; BH = standing body height in that camera's left view."""
import numpy as np, cv2
BH_PX = {"G": 315.0, "T": 227.0, "K": 158.0}          # critic's standing heights (G front 315; T, K left)
PX_PER_CM_G = 6.0
def clean(m):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if n <= 2: return m
    big = 1 + np.argmax(st[1:, 4]); keep = lab == big
    dil = cv2.dilate(keep.astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool)
    return np.isin(lab, np.unique(lab[dil & (lab > 0)]))
def iou(a, b):
    u = (a | b).sum(); return float((a & b).sum() / u) if u else 1.0
def steps(g, m):
    U = m.any(0); ys, xs = np.where(U); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    G = g[:, y0:y1, x0:x1].astype(np.float32)
    return np.abs(np.diff(G, axis=0)).mean((1, 2)), (y0, y1, x0, x1)
def framediff(a, b, box):
    y0, y1, x0, x1 = box; return float(np.abs(a[y0:y1, x0:x1].astype(np.float32) - b[y0:y1, x0:x1]).mean())
def saw(d):
    d = np.asarray(d, float)
    sm = np.convolve(np.pad(d, 4, mode="edge"), np.ones(5) / 5, "same")[4:-4]
    r = d - sm; idx = np.where(sm > 0.3)[0]
    if len(idx) < 12: return 0.0
    ph = np.array([r[idx[idx % 4 == k]].mean() for k in range(4)])
    return float((ph.max() - ph.min()) / sm[idx].mean())
def span(wm):
    cols = np.where(wm.sum(0) >= 3)[0]
    return (int(cols.max() - cols.min()), int(cols.min()), int(cols.max())) if len(cols) >= 2 else (0, 0, 0)
def fspan(m, ymax=540):
    cols = np.where(m[:ymax].sum(0) >= 2)[0]
    return (int(cols.max() - cols.min()), int(cols.min()), int(cols.max())) if len(cols) else (0, 0, 0)
def lowest(m):
    r = np.where(m.any(1))[0]; return int(r.max()) if len(r) else -1
def topmost(m):
    r = np.where(m.any(1))[0]; return int(r.min()) if len(r) else -1
def centroid(m):
    ys, xs = np.where(m); return (float(xs.mean()), float(ys.mean())) if len(xs) else (np.nan, np.nan)
def per(x):
    x = np.asarray(x, float) - np.mean(x); t = np.arange(len(x)); x = x - np.polyval(np.polyfit(t, x, 1), t)
    P = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; f = np.fft.rfftfreq(len(x)); k = 1 + np.argmax(P[1:])
    return float(1 / f[k]) if f[k] > 0 else float("inf")
def hp(x, k=7):
    x = np.asarray(x, float); s = np.convolve(np.pad(x, k // 2, mode="edge"), np.ones(k) / k, "valid"); return x - s
def lag_corr(vw, ab, lags=range(-6, 7)):
    out = {}
    for l in lags:
        a = vw[6 + l:len(ab) - 6 + l]; b = ab[6:len(ab) - 6]
        out[l] = float(np.corrcoef(a, b)[0, 1])
    return out
def snout_left(m):
    cols = np.where(m.any(0))[0]; c0 = cols.min(); rows = np.where(m[:, c0:c0 + 6].any(1))[0]; return float(c0), float(rows.mean())
def parab_a(t, y):
    return float(np.polyfit(t, y, 2)[0]) if len(t) >= 4 else float("nan")
