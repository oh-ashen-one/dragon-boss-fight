"""land2 pass 2: make the hop's centroid arc ballistic (critic: a_down / a_up 0.8 to 1.25) and knee-high (the clip's own prompt asked
for a knee-high hop; a 0.52 BH apex lands at 16 px/frame, above the critic's 8 px contact-snap limit in the T camera).
Measures the left-view centroid on the T raster, builds one parabola (same acceleration up and down) from the takeoff centroid to
the touchdown centroid with the requested apex height, and writes the world-z body offsets that move the centroid onto it.
python3 land2_corr.py <dump.npz> <out corr.npz> [prev=<corr.npz>] [apex_BH=0.26]"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raster as R, critic as C, metrics_v4 as MV
src, out = sys.argv[1], sys.argv[2]; opt = dict(a.split("=", 1) for a in sys.argv[3:])
BH = C.BH_PX["T"]; HA = float(opt.get("apex_BH", 0.26)) * BH
d = R.load(src); m, _, _ = R.render(d, "T", "left", shaded=False); m = np.stack([C.clean(x) for x in m])
r, h, cy, lo = MV.arc(m, BH)
to, td = r["takeoff"] - 1, r["touchdown"]                  # last ground frame before the launch, first frame back on the floor
y0, y1 = cy[to], cy[td]; ya = min(y0, y1) - HA             # screen y grows downward
T = td - to
a = ((np.sqrt(y0 - ya) + np.sqrt(y1 - ya)) / T) ** 2
t1 = np.sqrt((y0 - ya) / a)                                 # frames from launch to apex
t = np.arange(len(cy), dtype=float); tgt = cy.copy()
w = (t >= to) & (t <= td); tgt[w] = ya + a * (t[w] - to - t1) ** 2
PX_PER_M = (50.0 / 36.0 * 960) / 3.1                         # T camera, dragon at the origin
dz = -(tgt - cy) / PX_PER_M
if "prev" in opt: dz = dz + np.load(opt["prev"])["dz"][: len(dz)]
np.savez(out, dz=dz, target=tgt, measured=cy)
print("LAND2_CORR", out, {"takeoff": to, "touchdown": td, "apex_px": round(float(min(y0, y1) - cy[to:td + 1].min()), 1), "target_apex_px": round(float(HA), 1),
      "a_px_per_f2": round(float(a), 3), "a_ratio_now": round(r.get("a_down_over_a_up", float("nan")), 3), "max_corr_cm": round(float(np.abs(dz).max() * 100), 2)})
