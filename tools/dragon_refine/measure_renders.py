"""Image measurements on rendered idle clips (system python3 + OpenCV).
Usage: python3 measure_renders.py <label> <video_dir> <out.json>
Reads video/clip_<label>_<cam>.mp4. Metrics per camera:
  flow: Farneback dense flow, p95 magnitude over the dragon mask (dark pixels <60 in either frame, dilated 5 px);
        seam = last -> first frame; ratio = seam / median of consecutive steps.
  mad: mean abs grey difference last->first vs median consecutive step.
  last_second: median flow p95 over the last 24 steps (incl. seam) / clip median.
  feet: template (21x21 at frame 0) tracked with matchTemplate + subpixel peak, max drift px from frame 0.
  tail tip (threequarter + left): extreme dragon-mask pixel on the tail side, speed px/frame.
  wings: dragon-mask topmost row inside the wing column band, last vs first frame px.
"""
import sys, json, math
import numpy as np, cv2

label, vdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
F_PX = 50.0 / 36.0 * 960
TARGET = np.array([0.0, 0.0, 0.24])
CAMS = {"front": np.array([2.30, 0.00, 0.50]), "left": np.array([0.00, 2.30, 0.40]), "threequarter": np.array([1.65, 1.65, 0.80])}
# frame-0 foot points (world, from Blender rest-ish positions at sole height; only used to centre templates)
FEET = {"front+Y": np.array([0.30, 0.11, 0.02]), "front-Y": np.array([0.30, -0.10, 0.02]),
        "hind+Y": np.array([0.09, 0.12, 0.02]), "hind-Y": np.array([0.11, -0.12, 0.02])}
def project(cam, p):
    P = CAMS[cam]; fwd = TARGET - P; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    d = p - P
    return 480 + F_PX * d @ right / (d @ fwd), 270 - F_PX * d @ up / (d @ fwd)

def frames(cam):
    cap = cv2.VideoCapture(f"{vdir}/clip_{label}_{cam}.mp4"); fr = []
    while True:
        ok, im = cap.read()
        if not ok: break
        fr.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    return fr

def flow_p95(a, b):
    fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 21, 5, 7, 1.5, 0)
    mag = np.linalg.norm(fl, axis=2)
    m = cv2.dilate(((a < 60) | (b < 60)).astype(np.uint8), np.ones((11, 11), np.uint8)) > 0
    return float(np.percentile(mag[m], 95))

def subpix(res):
    _, _, _, (x, y) = cv2.minMaxLoc(res)
    def p(c, l, r): d = l - 2 * c + r; return 0.0 if abs(d) < 1e-9 else 0.5 * (l - r) / d
    dx = p(res[y, x], res[y, x - 1], res[y, x + 1]) if 0 < x < res.shape[1] - 1 else 0
    dy = p(res[y, x], res[y - 1, x], res[y + 1, x]) if 0 < y < res.shape[0] - 1 else 0
    return x + dx, y + dy, float(res[y, x])

R = {"label": label}
for cam in CAMS:
    fr = frames(cam); n = len(fr)
    steps = [flow_p95(fr[i], fr[i + 1]) for i in range(n - 1)]
    seam = flow_p95(fr[-1], fr[0]); med = float(np.median(steps))
    mads = [float(np.mean(cv2.absdiff(fr[i], fr[i + 1]))) for i in range(n - 1)]
    r = {"n_frames": n, "flow_p95_median_step_px": round(med, 3), "seam_flow_p95_px": round(seam, 3), "seam_ratio": round(seam / med, 3),
         "seam_mad": round(float(np.mean(cv2.absdiff(fr[-1], fr[0]))), 3), "median_step_mad": round(float(np.median(mads)), 3),
         "last_second_motion_vs_median": round(float(np.median(steps[-23:] + [seam])) / med, 3),
         "first_step_vs_median": round(steps[0] / med, 3),
         "max_step_vs_median": round(max(steps + [seam]) / med, 3),
         "accel_p99_5_px": round(float(np.percentile(np.abs(np.diff(steps + [seam, steps[0]])), 99.5)), 3)}
    # feet
    feet = {}
    for name, p in FEET.items():
        x, y = project(cam, p); x, y = int(round(x)), int(round(y - 8))   # template a bit above the sole
        h = 10; S = 18
        if not (S + h < x < 960 - S - h and S + h < y < 540 - S - h): continue
        tpl = fr[0][y - h:y + h + 1, x - h:x + h + 1]
        if tpl.std() < 8: continue
        tr = []
        for im in fr:
            win = im[y - h - S:y + h + S + 1, x - h - S:x + h + S + 1]
            res = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED)
            tr.append(subpix(res))
        tr = np.array(tr); d = np.linalg.norm(tr[:, :2] - tr[0, :2], axis=1)
        feet[name] = {"px": [x, y], "max_drift_px": round(float(d.max()), 3), "end_drift_px": round(float(d[-1]), 3), "min_score": round(float(tr[:, 2].min()), 3)}
    r["feet"] = feet
    # tail tip extreme (dragon mask), tail side = smaller x on left view, larger x on threequarter/front? (front: tail hidden)
    if cam in ("threequarter", "left"):
        pts = []
        for im in fr:
            m = (im < 60).astype(np.uint8)
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
            ys, xs = np.nonzero(m[:440])          # exclude bottom margin
            i = xs.argmax()                       # tail points to +x in both views
            sel = xs >= xs[i] - 2
            pts.append((xs[sel].mean(), ys[sel].mean()))
        pts = np.array(pts); v = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
        r["tail_tip"] = {"peak_px_per_frame": round(float(v.max()), 3), "median": round(float(np.median(v)), 3),
                         "peak_over_median": round(float(v.max() / max(np.median(v), 1e-6)), 2), "seam_px": round(float(v[-1]), 3),
                         "x_range_px": round(float(np.ptp(pts[:, 0])), 2),
                         "zero_runs_ge2": int(sum(1 for i in range(len(v) - 1) if v[i] < 0.05 and v[i + 1] < 0.05))}
    # wings: topmost dragon pixel per 20-px column band across the silhouette, last vs first
    m0 = fr[0] < 60; m1 = fr[-1] < 60
    def tops(m):
        cols = []
        for x0 in range(0, 960, 20):
            ys = np.nonzero(m[:, x0:x0 + 20].any(1))[0]
            cols.append(ys.min() if len(ys) else np.nan)
        return np.array(cols, float)
    t0, t1 = tops(m0), tops(m1); ok = ~np.isnan(t0) & ~np.isnan(t1)
    r["silhouette_top_last_vs_first_max_px"] = round(float(np.abs(t0[ok] - t1[ok]).max()), 2)
    R[cam] = r
    print(cam, json.dumps(r))
open(out, "w").write(json.dumps(R, indent=1))
