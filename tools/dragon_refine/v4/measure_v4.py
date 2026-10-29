"""Measure fix round 2 against the critic's ranked targets (critique-round2.md) on the CPU raster of the v3 and v4 Actions.
python3 measure_v4.py <dump_dir> <out.json> [only=move,move] [calib=calibration.json]
Dumps: d_<action>.npz from dump_verts.py. Cameras: G ground, T tall, K extra tall (render_clip_v3.py constants).
Per-frame-change numbers (holds) are raster values times the clip's own critic/raster ratio measured on its v3 render (calibrate.py),
so they estimate what the critic's script will read on the review render; every other number is geometric (pixels / body heights)."""
import sys, os, json, hashlib, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raster as R, critic as C, metrics_v4 as MV
DD, OUT = sys.argv[1], sys.argv[2]
opt = dict(a.split("=", 1) for a in sys.argv[3:])
ONLY = set(opt["only"].split(",")) if "only" in opt else None
CAL = json.load(open(opt.get("calib", os.path.join(DD, "calibration.json"))))
CACHE = os.path.join(DD, "rcache"); os.makedirs(CACHE, exist_ok=True)

def frames_of(act, grp, view):
    p = os.path.join(DD, f"d_{act}.npz"); st = os.stat(p)
    key = hashlib.md5(f"{p}{st.st_mtime_ns}{grp}{view}v2".encode()).hexdigest()[:12]
    cp = os.path.join(CACHE, f"{act}_{grp}_{view}_{key}.npz")
    if os.path.exists(cp):
        z = np.load(cp); sh = tuple(z["shape"])
        m = np.unpackbits(z["m"], axis=-1)[..., :sh[2]].astype(bool); w = np.unpackbits(z["w"], axis=-1)[..., :sh[2]].astype(bool)
        return m, w, z["g"].astype(np.float32)
    d = R.load(p); m, w, g = R.render(d, grp, view)
    m = np.stack([C.clean(x) for x in m]); w = w & m
    np.savez_compressed(cp, m=np.packbits(m, axis=-1), w=np.packbits(w, axis=-1), shape=np.array(m.shape), g=g.astype(np.float16))
    return m, w, g
def both(act, grp):
    return {v: frames_of(act, grp, v) for v in ("front", "left")}
def calib(clip_v3, view):
    c = CAL[clip_v3][view]; return c["step_median_critic"] / c["step_median_raster"]
def rnd(o):
    if isinstance(o, dict): return {str(k): rnd(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [rnd(v) for v in o]
    if isinstance(o, (bool, np.bool_)): return bool(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (float, np.floating)): return round(float(o), 3)
    return o
_ST = {}
def stance(grp):
    if grp not in _ST: _ST[grp] = {v: frames_of("idle_v2", grp, v)[0][0] for v in ("front", "left")}
    return _ST[grp]
def stance_iou(F, grp, idx):
    S = stance(grp); return {v: C.iou(F[v][0][idx], S[v]) for v in ("front", "left")}

RES = json.load(open(OUT)) if os.path.exists(OUT) else {}
def want(k): return ONLY is None or k in ONLY

# ---------------- 1 + 2 + 5: takeoff ----------------
def m_takeoff(act, grp):
    F = both(act, grp); BH = C.BH_PX[grp]
    ml = F["left"][0]; mf, wf = F["front"][0], F["front"][1]
    sl = MV.series(ml); sf = MV.series(mf, wf)
    lo = sl["lowest"]; floor = lo[0]; h = floor - lo
    L = int(np.argmax(h > 2))
    cy = sl["cy"]
    crouch = float((cy[:L + 1].max() - cy[0]) / BH)
    sp = sf["fspan"]
    span_before = float((sp[L] - sp[max(0, L - 6)]) / sp[max(0, L - 6)])
    span_before_max = float(sp[max(0, L - 6):L + 1].max() / sp[max(0, L - 6):L + 1].min() - 1)
    peak, end = float(h.max()), float(h[-1])
    last = cy[-24:]
    jumps = {v: float(np.abs(np.diff(F[v][0].any(2).shape and MV.series(F[v][0])["lowest"][max(0, L - 6):L + 8])).max()) for v in ("front", "left")}
    r = {"liftoff_frame_left": L, "crouch_BH": crouch, "span_change_6f_before_liftoff": span_before, "span_change_6f_before_liftoff_maxmin": span_before_max,
         "peak_over_end_height": peak / end if end > 0 else float("inf"), "peak_h_BH": peak / BH, "end_h_BH": end / BH,
         "centroid_change_last24_BH": float(np.ptp(last) / BH),
         "centroid_mean_change_last24_vs_previous24_BH": float(abs(cy[-24:].mean() - cy[-48:-24].mean()) / BH),
         "foot_jump_px_around_liftoff": jumps, "start_stance_iou": stance_iou(F, grp, 0)}
    r["beat_airborne"] = MV.beat(mf, wf, BH, (min(len(mf) - 40, L + 10), len(mf)))
    r["pass"] = {"feet_down_until>=36": L >= 36, "crouch>=0.08BH": crouch >= 0.08, "span+30%_before_liftoff": span_before >= 0.30,
                 "peak/end<=1.2": r["peak_over_end_height"] <= 1.2, "centroid_last24<=0.1BH": r["centroid_change_last24_BH"] <= 0.1,
                 "foot_jump<=8px": max(jumps.values()) <= 8}
    return r
# ---------------- 2 + 3: hover ----------------
def m_hover(act, grp):
    F = both(act, grp); BH = C.BH_PX[grp]
    b = MV.beat(F["front"][0], F["front"][1], BH, P=26)
    l = MV.loop(F["front"][2], F["front"][0], F["left"][2], F["left"][0], F["front"][0], P=26)
    return {"beat": b, "loop": l}
def m_fire(act, grp, v3cal):
    F = both(act, grp); BH = C.BH_PX[grp]
    b = MV.beat(F["front"][0], F["front"][1], BH, P=27)
    hold = {}
    for v in ("front", "left"):
        d, _ = C.steps(F[v][2], F[v][0]); k = calib(*v3cal[v]) if isinstance(v3cal[v], tuple) else v3cal[v]
        hold[v] = {"raster": float(d[80:152].mean()), "factor": k, "est_critic": float(d[80:152].mean() * k)}
    sawv = {v: C.saw(C.steps(F[v][2], F[v][0])[0]) for v in ("front", "left")}
    return {"beat": b, "hold_80_152_change": hold, "saw": sawv, "pass": {"hold>=1.0_both": min(x["est_critic"] for x in hold.values()) >= 1.0}}
# ---------------- 2 + 5 + 6: air land ----------------
def m_airland(act, grp):
    F = both(act, grp); BH = C.BH_PX[grp]
    ml, mf, wf = F["left"][0], F["front"][0], F["front"][1]
    sl = MV.series(ml); sf = MV.series(mf, wf)
    lo = sl["lowest"]; floor = lo[-1]; h = floor - lo
    air = np.where(h > 2)[0]; Cf = int(air[-1] + 1)
    cy = sl["cy"]; v = np.diff(cy)
    va = float(np.mean(v[Cf - 15:Cf - 11])); vb = float(np.mean(v[Cf - 3:Cf]))
    sp = sf["fspan"]
    span_win = float(sp[Cf - 12:Cf + 1].max() / sp[Cf - 12] - 1)
    comp = float((cy[Cf:Cf + 5].max() - cy[Cf]) / BH)
    jumps = {vv: float(np.abs(np.diff(MV.series(F[vv][0])["lowest"][Cf - 6:Cf + 7])).max()) for vv in ("front", "left")}
    fs = abs(lo[Cf] - lo[Cf - 1]); bs = abs(cy[Cf] - cy[Cf - 1])
    r = {"contact_frame": Cf, "descent_px_per_frame_at_C-12": va, "descent_px_per_frame_at_contact": vb, "descent_speed_drop": 1 - vb / va if va else float("nan"),
         "span_gain_12f_before_contact": span_win, "impact_compression_BH": comp, "end_stance_iou": stance_iou(F, grp, -1),
         "foot_jump_px_around_contact": jumps, "foot_over_body_speed_at_contact": fs / bs if bs else float("inf")}
    r["beat_airborne"] = MV.beat(mf, wf, BH, (0, Cf - 12), P=26)
    r["pass"] = {"descent_drop>=40%": r["descent_speed_drop"] >= 0.40, "span+30%": span_win >= 0.30, "compression>=0.08BH": comp >= 0.08,
                 "end_iou>=0.97": min(r["end_stance_iou"].values()) >= 0.97, "foot_jump<=8px": max(jumps.values()) <= 8,
                 "foot/body<=1.2": r["foot_over_body_speed_at_contact"] <= 1.2}
    return r
# ---------------- 4 + 8: roar ----------------
def m_roar(act, grp, cal, hold=(43, 86)):
    F = both(act, grp); BH = C.BH_PX[grp]
    mf, wf, gf = F["front"]; ml = F["left"][0]
    _, wi, _ = frames_of("idle_v2", grp, "front")
    cx = 480
    sp0 = C.span(wi[0]); l0 = cx - sp0[1]; r0 = sp0[2] - cx
    lw = np.array([cx - C.span(x)[1] for x in wf]) / l0; rw = np.array([C.span(x)[2] - cx for x in wf]) / r0
    sp = np.array([C.span(x)[0] for x in wf]) / sp0[0]
    pk = int(np.argmax(sp)); a, b = hold
    def rise_frames(x, i0, i1):
        lo_, hi_ = x[i0], x[i1]
        if hi_ <= lo_: return 0
        f10 = i0 + int(np.argmax(x[i0:i1 + 1] >= lo_ + 0.1 * (hi_ - lo_))); f90 = i0 + int(np.argmax(x[i0:i1 + 1] >= lo_ + 0.9 * (hi_ - lo_)))
        return f90 - f10
    open_f = rise_frames(sp, 0, pk)
    close_f = rise_frames(sp[::-1], 0, len(sp) - 1 - pk)
    d, _ = C.steps(gf, mf); k = calib(cal, "front")
    sn = np.array([C.snout_left(x) for x in ml]); hw = np.arange(a + 3, b - 3)
    trem_sn = float(np.hypot(C.hp(sn[:, 0])[hw], C.hp(sn[:, 1])[hw]).std())
    top = np.array([C.topmost(x) for x in mf], float); trem_top = float(C.hp(top)[hw].std())
    lext = np.array([C.span(x)[1] for x in wf], float); rext = np.array([C.span(x)[2] for x in wf], float)
    trem_w = [float(C.hp(lext)[hw].std()), float(C.hp(rext)[hw].std())]
    r = {"span_peak_over_idle": float(sp.max()), "peak_frame": pk, "left_wing_peak": float(lw.max()), "right_wing_peak": float(rw.max()),
         "left_wing_hold_min": float(lw[a:b].min()), "right_wing_hold_min": float(rw[a:b].min()),
         "wing_asymmetry_at_peak": float(abs(lw[pk] - rw[pk]) / max(lw[pk], rw[pk])), "open_frames_10_90": open_f, "close_frames_10_90": close_f,
         "hold_change": {"raster": float(d[a:b].mean()), "factor": k, "est_critic": float(d[a:b].mean() * k)},
         "snout_tremor_px": trem_sn, "head_top_tremor_px": trem_top, "wingtip_tremor_px": trem_w,
         "start_stance_iou": stance_iou(F, grp, 0), "end_stance_iou": stance_iou(F, grp, -1)}
    r["pass"] = {"both_wings>=1.22": min(lw[pk], rw[pk]) >= 1.22, "wings_within_5%": r["wing_asymmetry_at_peak"] <= 0.05,
                 "open>=8": open_f >= 8, "close>=10": close_f >= 10, "hold_change>=1.2": r["hold_change"]["est_critic"] >= 1.2,
                 "snout_tremor_1.5-3px": 1.5 <= trem_sn <= 3.0, "wingtip_tremor_1.5-3px": all(1.5 <= x <= 3.0 for x in trem_w)}
    return r
def m_collapse(act, grp, cal, win=(114, 145)):
    F = both(act, grp); r = {}
    for v in ("front", "left"):
        d, _ = C.steps(F[v][2], F[v][0]); k = calib(cal, v)
        r[v] = {"raster": float(d[win[0]:win[1] - 1].mean()), "factor": k, "est_critic": float(d[win[0]:win[1] - 1].mean() * k)}
    return {"lying_change": r, "pass": {"lying_change>=0.4_front": r["front"]["est_critic"] >= 0.4}}
def m_bite(act, grp):
    F = both(act, grp); ml = F["left"][0]
    sn = np.array([C.snout_left(x) for x in ml]); x = sn[:, 0]
    reach = (x[0] - x) / C.PX_PER_CM_G
    pk = int(np.argmax(reach)); near = np.abs(x - x[pk]) <= 3
    run, best = 0, 0
    for i in range(len(near)):
        run = run + 1 if near[i] else 0; best = max(best, run)
    r = {"reach_cm": float(reach.max()), "peak_frame": pk, "full_reach_freeze_frames": best, "start_stance_iou": stance_iou(F, grp, 0), "end_stance_iou": stance_iou(F, grp, -1)}
    r["pass"] = {"reach>=12cm": r["reach_cm"] >= 12, "freeze<=10": best <= 10}
    return r
def m_land2(act, grp):
    F = both(act, grp); BH = C.BH_PX[grp]
    a = MV.arc(F["left"][0], BH)
    if isinstance(a, dict): return a
    r, h, cy, lo = a
    jumps = {}
    for v in ("front", "left"):
        lov = MV.series(F[v][0])["lowest"]
        jumps[v] = {"takeoff": float(np.abs(np.diff(lov[r["takeoff"] - 6:r["takeoff"] + 7])).max()), "touchdown": float(np.abs(np.diff(lov[r["touchdown"] - 6:r["touchdown"] + 7])).max())}
    td = r["touchdown"]; fs = abs(lo[td] - lo[td - 1]); bs = abs(cy[td] - cy[td - 1])
    r.update({"foot_jumps_px": jumps, "foot_over_body_speed_at_touchdown": fs / bs if bs else float("inf"),
              "start_stance_iou_vs_frame0": None, "end_vs_start_iou": {v: C.iou(F[v][0][0], F[v][0][-1]) for v in ("front", "left")}})
    r["pass"] = {"a_ratio_0.8-1.25": 0.8 <= r["a_down_over_a_up"] <= 1.25, "foot_jump<=8px": max(max(j.values()) for j in jumps.values()) <= 8,
                 "foot/body<=1.2": r["foot_over_body_speed_at_touchdown"] <= 1.2}
    return r
def m_rise(act, grp):
    F = both(act, grp); out = {}
    for c in ("collapse_v3", "collapse_v4"):
        if os.path.exists(os.path.join(DD, f"d_{c}.npz")):
            G = both(c, grp); out[f"iou_frame0_vs_{c}_end"] = {v: C.iou(F[v][0][0], G[v][0][-1]) for v in ("front", "left")}
    out["end_stance_iou"] = stance_iou(F, grp, -1)
    # the shipped chain is collapse_v4 -> rise_v4 (collapse_v4 adds breathing, so its end differs from collapse_v3's)
    out["pass"] = {"iou>=0.95_vs_collapse_v4_end": min(out.get("iou_frame0_vs_collapse_v4_end", {"x": 0}).values()) >= 0.95}
    return out

JOBS = {
    "takeoff3": [("v3", lambda: m_takeoff("takeoff3_v3", "K")), ("v4", lambda: m_takeoff("takeoff3_v4", "K"))],
    "air_hover": [("v3", lambda: m_hover("air_hover_v3", "T")), ("v4", lambda: m_hover("air_hover_v4", "K"))],
    "air_fire_down": [("v3", lambda: m_fire("air_fire_down_v3", "T", {"front": ("air_air_fire_down_FD1", "front"), "left": ("air_air_fire_down_FD1", "left")})),
                      ("v4", lambda: m_fire("air_fire_down_v4", "K", {"front": ("air_takeoff3_TK1", "front"), "left": ("air_takeoff3_TK1", "left")}))],
    "air_land": [("v3", lambda: m_airland("air_land_v3", "T")), ("v4", lambda: m_airland("air_land_v4", "K"))],
    "roar": [("v3", lambda: m_roar("roar_sd_v3", "G", "after_roar_r1")), ("v4", lambda: m_roar("roar_v4", "G", "after_roar_r1", hold=(44, 84)))],
    "collapse": [("v3", lambda: m_collapse("collapse_v3", "G", "after_collapse_r1")), ("v4", lambda: m_collapse("collapse_v4", "G", "after_collapse_r1"))],
    "bite": [("v3", lambda: m_bite("bite_v3", "G")), ("v4", lambda: m_bite("bite_v4", "G"))],
    "land2": [("v3", lambda: m_land2("land2_v3", "T")), ("v4", lambda: m_land2("land2_v4", "T"))],
    "rise": [("v3", lambda: m_rise("rise_v3", "G")), ("v4", lambda: m_rise("rise_v4", "G"))],
}
for k, jobs in JOBS.items():
    if not want(k): continue
    RES.setdefault(k, {})
    for tag, fn in jobs:
        try: RES[k][tag] = rnd(fn())
        except Exception as e: RES[k][tag] = {"error": repr(e)}
        print(k, tag, json.dumps(RES[k][tag].get("pass", RES[k][tag].get("error", ""))), flush=True)
    json.dump(RES, open(OUT, "w"), indent=1)
RES["_method"] = ("CPU raster of the evaluated mesh through the review cameras (raster.py), critic definitions (critic.py, metrics_v4.py). "
                  "v4 airborne clips on the K camera (the T frame clips the upstroke); hold changes are estimates: raster x the clip's v3 critic/raster ratio.")
json.dump(RES, open(OUT, "w"), indent=1)
