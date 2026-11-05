"""Bob shape from the visible wing motion: the critic couples wing-tip (top silhouette row) velocity with body acceleration,
so the body's vertical velocity is made proportional to the wing-tip height (cy'' ~ top'  =>  cy' ~ top - mean  =>  z ~ integral).
The top row is folded over the beat phase (u = t / P) from a no-bob render of the hover and integrated as a periodic signal.
python3 bob_table.py <nobob dump.npz> <out table.npz> [P=26] [grid=1]"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raster as R, critic as C, metrics_v4 as MV
src, out = sys.argv[1], sys.argv[2]; opt = dict(a.split("=", 1) for a in sys.argv[3:]); P = float(opt.get("P", 26))
d = R.load(src); m, w, _ = R.render(d, "K", "front"); m = np.stack([C.clean(x) for x in m]); w = w & m
top = np.array([C.topmost(x) for x in m], float); N = len(top)
n = 64; u = (np.arange(N) / P) % 1.0
bins = np.floor(u * n).astype(int); prof = np.array([top[bins == k].mean() if (bins == k).any() else np.nan for k in range(n)])
ok = ~np.isnan(prof); uu = (np.arange(n) + 0.5) / n; prof = np.interp(uu, uu[ok], prof[ok], period=1.0)
prof = np.convolve(np.r_[prof[-2:], prof, prof[:2]], np.ones(5) / 5, "valid")      # light cyclic smoothing
x = prof - prof.mean()                         # px, down positive: wing up => negative
# body up-velocity proportional to wing-tip DOWNWARD velocity -> body screen-y velocity = -k (top - mean)?  No: the critic wants
# accel ~ wing velocity: cy'' = -k top'  =>  cy' = -k (top - mean)  =>  cy = -k * I(top - mean).  World z is up = -cy.
z = np.cumsum(x) / n; z -= z.mean()
# remove drift so the integral is periodic (x has zero mean so it is already), normalise to unit peak-to-peak
z /= np.ptp(z)
np.savez(out, U=uu, Z=z, top_profile=prof)
print("table", out, "top p2p px", round(float(np.ptp(prof)), 1), "z argmax u", round(float(uu[np.argmax(z)]), 3), "argmin u", round(float(uu[np.argmin(z)]), 3))
if opt.get("grid"):
    V0 = d["V"].copy()
    for amp in (0.04, 0.05, 0.06):
        for lead in (-0.15, -0.1, -0.05, 0.0, 0.05, 0.1):
            zz = amp * np.interp(np.mod(np.arange(N) / P + lead, 1), uu, z, period=1)
            d["V"] = V0 + np.stack([np.zeros(N), np.zeros(N), zz], 1)[:, None, :].astype(np.float32)
            mf, wf, _ = R.render(d, "K", "front"); mf = np.stack([C.clean(q) for q in mf]); b = MV.beat(mf, wf & mf, 158.0, P=P)
            print("amp", amp, "lead", lead, "corr0-4 %.2f@%d best %.2f@%d bob %.3f" % (b["corr_lag0to4"], b["corr_lag0to4_best_lag"], b["corr_best"], b["corr_best_lag"], b["body_bob_p2p_BH"]), flush=True)
