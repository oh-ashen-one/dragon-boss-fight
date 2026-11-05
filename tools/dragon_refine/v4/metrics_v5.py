"""Round-3 targets (Local/dragon-review-20261029/critique-round3.md, "What fix round 3 must do") with the round-3 critic's
definitions, on masks / gray frames: works on the CPU raster (raster.py) and on segmented review renders alike.
Pixel numbers are in the 960x540 review frame; BH = standing height in px of that camera (critic.BH_PX)."""
import numpy as np
import critic as C

def pop_scan(d, thr=2.0, ratio=2.2, k=3):
    """critic pop rule: step i (frame i -> i+1) is a pop when d[i] > thr and d[i] > ratio x median of the +-k neighbouring steps"""
    d = np.asarray(d, float); out = []
    for i in range(len(d)):
        nb = np.r_[d[max(0, i - k):i], d[i + 1:i + 1 + k]]
        if len(nb) and d[i] > thr and d[i] > ratio * np.median(nb): out.append((i, round(float(d[i]), 2), round(float(np.median(nb)), 2)))
    return out
def max_step_ratio(d, k=3, lo=0.3):
    """largest d[i] / median(+-k neighbours), over steps whose neighbourhood moves (median > lo)"""
    d = np.asarray(d, float); best = (0.0, -1)
    for i in range(len(d)):
        nb = np.r_[d[max(0, i - k):i], d[i + 1:i + 1 + k]]; md = float(np.median(nb)) if len(nb) else 0
        if md > lo: best = max(best, (float(d[i] / md), i))
    return {"ratio": round(best[0], 2), "step": best[1]}
def consec_iou(m):
    return np.array([C.iou(m[i], m[i + 1]) for i in range(len(m) - 1)])
def height_ratio(m, h0):
    """critic: silhouette bounding-box height (lowest row - top row) over the standing stance's (h0 px)"""
    return np.array([(C.lowest(x) - C.topmost(x)) / h0 for x in m])
def leftmost(m):
    return np.array([np.where(x.any(0))[0].min() if x.any() else -1 for x in m])
def roar_halves(mf, m_idle0):
    """critique-round3 roar.py: front span over the rows above 330 (G front), halves about the body centre (median column of rows 330-440)"""
    def body_cx(m):
        ys, xs = np.where(m[330:440]); return float(np.median(xs))
    cx0 = body_cx(m_idle0); s0 = C.fspan(m_idle0, 330); L0 = cx0 - s0[1]; R0 = s0[2] - cx0
    sp, Ls, Rs = [], [], []
    for x in mf:
        s = C.fspan(x, 330); cx = body_cx(x); sp.append(s[0] / s0[0]); Ls.append((cx - s[1]) / L0); Rs.append((s[2] - cx) / R0)
    return np.array(sp), np.array(Ls), np.array(Rs)
def contacts(m, floor_row, lo=6, hi=3, minw=3):
    """critic contact.py: contact segments (x ranges, >= minw px) in the band floor_row-lo .. floor_row+hi"""
    out = []
    for x in m:
        cols = np.where(x[floor_row - lo:floor_row + hi].any(0))[0]; segs = []
        if len(cols):
            s = p = cols[0]
            for c in cols[1:]:
                if c > p + 4: segs.append((s, p)); s = c
                p = c
            segs.append((s, p))
        out.append([sg for sg in segs if sg[1] - sg[0] >= minw])
    return out
