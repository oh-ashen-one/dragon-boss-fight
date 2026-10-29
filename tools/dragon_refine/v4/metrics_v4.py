"""Round-2 targets measured with the critic's definitions (critique-round2.md, Method and Ranked fix list) on masks/gray frames.
Inputs come either from raster.render (CPU stand-in of the review renders) or from segmented renders; same functions.
Each function returns a dict of numbers plus pass flags against the critic's numeric targets."""
import numpy as np
import critic as C

def series(m, w=None):
    lo = np.array([C.lowest(x) for x in m], float); top = np.array([C.topmost(x) for x in m], float)
    cy = np.array([C.centroid(x)[1] for x in m]); sp = np.array([C.fspan(x)[0] for x in m], float)
    out = {"lowest": lo, "top": top, "cy": cy, "fspan": sp}
    if w is not None:
        body = m & ~w
        out["body_cy"] = np.array([C.centroid(x)[1] for x in body])
    return out

def beat(mf, wf, BH, window=None, P=24):
    """item 2 on the front view: wing-tip (top row) peak-to-peak, period, body bob, coupling, span drift"""
    a, b = window or (0, len(mf))
    s = series(mf[a:b], wf[a:b])
    wt, cy, sp = s["top"], s["body_cy"], s["fspan"]
    vw = np.diff(wt); ab = np.diff(cy, 2)
    lc = C.lag_corr(vw, ab)
    best = max(lc, key=lambda k: abs(lc[k]))
    best04 = max((k for k in lc if 0 <= k <= 4), key=lambda k: abs(lc[k]))
    k = int(round(P))
    if len(sp) > k:
        avg = np.convolve(sp, np.ones(k) / k, mode="valid")          # per-beat mean span (in-cycle beat removed)
        drift = float((avg.max() - avg.min()) / avg.mean())
    else: drift = float("nan")
    r = {"window": [a, b], "wingtip_p2p_px": float(np.ptp(wt)), "wingtip_p2p_BH": float(np.ptp(wt) / BH), "period_frames": C.per(wt),
         "body_bob_p2p_px": float(np.ptp(cy)), "body_bob_p2p_BH": float(np.ptp(cy) / BH), "body_period_frames": C.per(cy),
         "corr_best_lag": int(best), "corr_best": lc[best], "corr_lag0to4_best_lag": int(best04), "corr_lag0to4": lc[best04],
         "span_drift_beat_avg": drift, "span_raw_range_frac": float(np.ptp(sp) / sp.mean()),
         "span_first_last_frac": float((sp[-1] - sp[0]) / sp.mean())}
    r["pass"] = {"wingtip_p2p>=0.5BH": r["wingtip_p2p_BH"] >= 0.5, "period_18_30": 18 <= r["period_frames"] <= 30,
                 "bob>=0.06BH": r["body_bob_p2p_BH"] >= 0.06, "corr>=0.6_lag0to4": abs(r["corr_lag0to4"]) >= 0.6, "span_drift<=5%": drift <= 0.05}
    return r

def loop(g_f, m_f, g_l, m_l, mf, P=24):
    """item 3: seam (last vs first, in own median steps), span change in the last 8 frames, saw both views"""
    out = {}
    for v, g, m in (("front", g_f, m_f), ("left", g_l, m_l)):
        d, box = C.steps(g, m)
        out[v] = {"seam_steps": C.framediff(g[-1], g[0], box) / float(np.median(d)), "saw": C.saw(d), "median_step": float(np.median(d))}
    sp = np.array([C.fspan(x)[0] for x in mf], float)
    out["span_last8_raw_frac"] = float(np.ptp(sp[-8:]) / sp.mean())
    out["span_last8_vs_one_beat_earlier_frac"] = float(np.abs(sp[-8:] - sp[-8 - P:-P]).max() / sp.mean())
    out["pass"] = {"seam<=1.2": max(out["front"]["seam_steps"], out["left"]["seam_steps"]) <= 1.2,
                   "span_last8<=3%_raw": out["span_last8_raw_frac"] <= 0.03,
                   "span_last8<=3%_beat_matched": out["span_last8_vs_one_beat_earlier_frac"] <= 0.03,
                   "saw<=0.07_both": max(out["front"]["saw"], out["left"]["saw"]) <= 0.07}
    return out

def hold_change(g, m, a, b, scale=1.0):
    d, box = C.steps(g, m)
    return float(np.mean(d[a:b]) * scale), d

def foot_jumps(lo, frames):
    """largest single-frame change of the lowest row around the listed frames (+-6)"""
    out = {}
    for f in frames:
        a, b = max(1, f - 6), min(len(lo) - 1, f + 7)
        out[int(f)] = float(np.abs(np.diff(lo[a - 1:b])).max())
    return out

def arc(m, BH):
    """critic arc: lowest row (feet) and centroid; parabolas fitted to ascent and descent of the centroid separately"""
    s = series(m); lo, cy = s["lowest"], s["cy"]
    fl = lo[0]; h = fl - lo
    air = np.where(h > 3)[0]
    if len(air) == 0: return {"airborne": False}
    to = int(air[0]); ap = int(np.argmax(h)); after = np.where(h[ap:] <= 2)[0]; td = int(ap + after[0]) if len(after) else None
    r = {"takeoff": to, "apex": ap, "touchdown": td, "apex_h_px": float(h[ap]), "apex_h_BH": float(h[ap] / BH)}
    if td:
        capex = int(to + np.argmin(cy[to:td + 1]))
        up = np.arange(to, capex + 1); dn = np.arange(capex, td + 1)
        au = C.parab_a(up, cy[up]); ad = C.parab_a(dn, cy[dn])
        r.update({"centroid_apex": capex, "a_up": au, "a_down": ad, "a_down_over_a_up": ad / au if au else float("nan"),
                  "rise_frames": int(capex - to), "fall_frames": int(td - capex)})
    return r, h, cy, lo
