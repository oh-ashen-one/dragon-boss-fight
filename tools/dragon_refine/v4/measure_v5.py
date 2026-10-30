"""Measure fix round 3 against the round-3 critic's targets (critique-round3.md, "What fix round 3 must do") BEFORE rendering:
CPU raster of the evaluated mesh through the review cameras (raster.py) scored with the critic's definitions (critic.py,
metrics_v5.py), plus bone/vertex-space checks from the same dumps (root steps, feet on the floor, tail tip, wing tips).
python3 measure_v5.py <out.json> v4=<dump dir> v5=<dump dir> [only=move,move] [seg=<critic-seg cache dir>]
Per-frame-change numbers (d, holds, pop thresholds) are raster values times a per-clip critic/raster factor measured on the v4
review renders (the critic's own segmentation of clip_<LABEL>4, `seg=`), so they estimate what the critic reads on a render."""
import sys, os, json, hashlib, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raster as R, critic as C, metrics_v4 as MV, metrics_v5 as M5
OUT = sys.argv[1]
opt = dict(a.split("=", 1) for a in sys.argv[2:])
DIRS = {"v4": opt["v4"], "v5": opt["v5"]}
ONLY = set(opt["only"].split(",")) if "only" in opt else None
SEG = opt.get("seg")
CACHE = os.path.join(opt["v5"], "rcache"); os.makedirs(CACHE, exist_ok=True)
VIEWS = ("front", "left", "threequarter")

def dump_path(act, tag): return os.path.join(DIRS[tag], f"d_{act}.npz")
def frames_of(act, tag, grp, view):
    p = dump_path(act, tag); st = os.stat(p)
    key = hashlib.md5(f"{p}{st.st_mtime_ns}{grp}{view}v5".encode()).hexdigest()[:12]
    cp = os.path.join(CACHE, f"{act}_{grp}_{view}_{key}.npz")
    if os.path.exists(cp):
        z = np.load(cp); sh = tuple(z["shape"])
        m = np.unpackbits(z["m"], axis=-1)[..., :sh[2]].astype(bool); w = np.unpackbits(z["w"], axis=-1)[..., :sh[2]].astype(bool)
        return m, w, z["g"].astype(np.float32)
    d = R.load(p); m, w, g = R.render(d, grp, view)
    m = np.stack([C.clean(x) for x in m]); w = w & m
    np.savez_compressed(cp, m=np.packbits(m, axis=-1), w=np.packbits(w, axis=-1), shape=np.array(m.shape), g=g.astype(np.float16))
    return m, w, g
def seg_get(label, view):
    z = np.load(os.path.join(SEG, f"{label}_{view}.npz")); g = z["g"]; Wd = g.shape[2]
    return np.unpackbits(z["m"], -1)[..., :Wd].astype(bool), np.unpackbits(z["w"], -1)[..., :Wd].astype(bool), g.astype(np.float32)
_K = {}
def factor(label4, act4, grp, view):
    """critic/raster per-frame-change ratio for this clip and view, from the v4 render vs the v4 raster"""
    k = (label4, view)
    if k not in _K:
        try:
            ms, _, gs = seg_get(label4, view); mr, _, gr = frames_of(act4, "v4", grp, view)
            n = min(len(ms), len(mr)); ds, _ = C.steps(gs[:n], ms[:n]); dr, _ = C.steps(gr[:n], mr[:n]); _K[k] = float(np.median(ds) / np.median(dr))
        except Exception as e:
            print("factor fallback", label4, view, repr(e)); _K[k] = 1.0
    return _K[k]
def rnd(o):
    if isinstance(o, dict): return {str(k): rnd(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [rnd(v) for v in o]
    if isinstance(o, (bool, np.bool_)): return bool(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (float, np.floating)): return round(float(o), 3)
    if isinstance(o, np.ndarray): return rnd(o.tolist())
    return o
_ST = {}
def stance(grp):
    if grp not in _ST:
        _ST[grp] = {v: frames_of("idle_v2", "v4", grp, v)[0][0] for v in VIEWS}
    return _ST[grp]
def h0(grp, view): s = stance(grp)[view]; return float(C.lowest(s) - C.topmost(s))
def common(act, tag, grp, label4, act4):
    """pops / consecutive IoU / saw for every view, d scaled to the critic's units"""
    out = {}
    for v in VIEWS:
        m, w, g = frames_of(act, tag, grp, v); d, _ = C.steps(g, m); k = factor(label4, act4, grp, v); dc = d * k
        ci = M5.consec_iou(m)
        out[v] = {"pops": M5.pop_scan(dc), "max_step_ratio": M5.max_step_ratio(dc), "consec_iou_min": float(ci.min()), "consec_iou_min_at": int(ci.argmin()),
                  "saw": C.saw(dc), "factor": k}
    return out
def ends(act, tag, grp):
    S = stance(grp); r = {}
    for v in ("front", "left"):
        m = frames_of(act, tag, grp, v)[0]; r[v] = [C.iou(m[0], S[v]), C.iou(m[-1], S[v])]
    return r
def iou_dip(act, tag, grp, v, n=None):
    """largest consecutive-IoU dip: (1 - IoU) of a step over the median of its +-3 neighbours (raster IoU runs lower than the
    critic's segmentation on this spiky mesh, so the pop test is relative)"""
    e = 1 - M5.consec_iou(frames_of(act, tag, grp, v)[0][:n])
    rr = [e[i] / max(1e-4, float(np.median(np.r_[e[max(0, i - 3):i], e[i + 1:i + 4]]))) for i in range(len(e))]
    k = int(np.argmax(rr)); return {"ratio": float(rr[k]), "step": k, "iou": float(1 - e[k]), "iou_min": float(1 - e.max())}
def load3d(act, tag):
    d = R.load(dump_path(act, tag)); return d
FOOTG = {"front+Y": ["bone_9", "tripo::1_Left_Limb_1"], "front-Y": ["bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"],
         "hind+Y": ["tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4"], "hind-Y": ["tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"]}
def feet_z(d): return {k: d["V"][:, np.isin(d["vname"], g), 2].min(1) for k, g in FOOTG.items()}
def bone_track(d, name, tail=False): return R.bone(d, name, tail)
def step_ratio3(x, k=3, lo=1e-4):
    s = np.linalg.norm(np.diff(x, axis=0), axis=1); best = (0.0, -1)
    for i in range(len(s)):
        nb = np.r_[s[max(0, i - k):i], s[i + 1:i + 1 + k]]; best = max(best, (float(s[i] / max(float(np.median(nb)), lo)), i))
    return {"ratio": best[0], "step": best[1], "max_step_cm": float(s.max() * 100)}

# ---------------- per move ----------------
def m_collapse(act, tag):
    grp = "G"; r = {}
    mf = frames_of(act, tag, grp, "front")[0]; ml = frames_of(act, tag, grp, "left")[0]; m3, w3, _ = frames_of(act, tag, grp, "threequarter")
    r["end_height_ratio"] = {"front": float(M5.height_ratio(mf[-1:], h0(grp, "front"))[0]), "left": float(M5.height_ratio(ml[-1:], h0(grp, "left"))[0])}
    r["leftmost_3q_end_px"] = int(M5.leftmost(m3[-1:])[0])
    hr = M5.height_ratio(mf, h0(grp, "front")); f90 = int(np.argmax(hr < hr[0] - 0.9 * (hr[0] - hr[-1]))); f10 = int(np.argmax(hr < hr[0] - 0.1 * (hr[0] - hr[-1])))
    r["fall_frames_height_10_90"] = [f10, f90, f90 - f10]
    cm = common(act, tag, grp, "clip_CO4", "collapse_v4")
    n = len(mf); a = n - 31
    lying = {}
    for v in VIEWS:
        m, _, g = frames_of(act, tag, grp, v); d, _ = C.steps(g, m); lying[v] = float(d[a:].mean() * cm[v]["factor"])
    r["lying_breath_change_last30"] = lying
    d = load3d(act, tag); V = d["V"][-1]; isw = np.char.startswith(d["vname"], "VeyrWing")
    r["end_3d_cm"] = {"top": float(V[:, 2].max() * 100), "back_top_nonwing": float(V[~isw, 2].max() * 100), "wing_top": float(V[isw, 2].max() * 100),
                      "wing_min": float(V[isw, 2].min() * 100), "wing_x_max": float(V[isw, 0].max() * 100), "snout_x": float(V[~isw, 0].max() * 100),
                      "feet_low": {k: float(v[-1] * 100) for k, v in feet_z(d).items()}}
    tail = d["V"][-1][np.char.startswith(d["vname"], "tripo::Tail"), 2]
    r["tail_end_z_cm"] = [float(tail.min() * 100), float(tail.max() * 100)]
    r["common"] = cm
    r["pass"] = {"front_height<=0.50(critic est = raster x 0.953, CO4 render 0.689 / raster 0.723)": r["end_height_ratio"]["front"] * 0.953 <= 0.50, "leftmost_3q>=200(raster, v4 render offset +17)": r["leftmost_3q_end_px"] + 17 >= 200,
                 "wings_below_back": r["end_3d_cm"]["wing_top"] <= r["end_3d_cm"]["back_top_nonwing"] + 1.0, "breathing>=0.4": min(lying.values()) >= 0.4,
                 "fall>=24f": r["fall_frames_height_10_90"][2] >= 24}
    return r
def m_rise(act, tag, collapse_act):
    grp = "G"; r = {}
    cd = {v: frames_of(collapse_act, tag, grp, v)[0][-1] for v in VIEWS}
    r["iou_frame0_vs_collapse_end"] = {v: C.iou(frames_of(act, tag, grp, v)[0][0], cd[v]) for v in VIEWS}
    cm = common(act, tag, grp, "clip_RI4", "rise_v4"); r["common"] = cm
    dd = {}
    for v in ("front", "left"):
        m, _, g = frames_of(act, tag, grp, v); d, _ = C.steps(g, m); dd[v] = (d[:8] * cm[v]["factor"]).tolist()
    r["d_frames_0_7"] = dd
    d = load3d(act, tag); fz = feet_z(d); n = len(d["V"])
    G = int(opt.get("getup", 50)) if tag == "v5" else 44
    cnt = sum((fz[k] <= 0.005).astype(int) for k in fz)
    isw = np.char.startswith(d["vname"], "VeyrWing"); foot = np.isin(d["vname"], sum(FOOTG.values(), []))
    body_low = d["V"][:, ~isw & ~foot, 2].min(1); low_all = d["V"][:, :, 2].min(1); wing_low = d["V"][:, isw, 2].min(1)
    r["getup_frames"] = G
    r["feet_on_floor_min_0_G"] = int(cnt[:G + 1].min()); r["feet_on_floor_series"] = cnt[:G + 10].tolist()
    r["lowest_vertex_max_cm_0_G"] = float(low_all[:G + 1].max() * 100)
    r["wing_min_z_cm_0_G"] = float(wing_low[:G + 1].min() * 100)
    lf = frames_of(act, tag, grp, "left")[0]; fl = C.lowest(stance(grp)["left"])
    lo = np.array([C.lowest(x) for x in lf]); r["left_lowest_row_minus_floor_max_px_0_G"] = int((fl - lo[:G + 1]).max())
    r["end_stance_iou"] = ends(act, tag, grp)
    # consecutive-IoU dip over frames 0..G+10 (the critic's pop sat at the handover): raster IoU runs lower than the critic's
    # segmentation on this spiky mesh, so the test is relative: (1 - IoU) of a step over the median of its +-3 neighbours
    def iou_dip(v):
        e = 1 - M5.consec_iou(frames_of(act, tag, grp, v)[0][:G + 11])
        rr = [e[i] / max(1e-4, float(np.median(np.r_[e[max(0, i - 3):i], e[i + 1:i + 4]]))) for i in range(len(e))]
        k = int(np.argmax(rr)); return {"ratio": float(rr[k]), "step": k, "iou": float(1 - e[k]), "iou_min": float(1 - e.max())}
    r["consec_iou_dip_0_G10"] = {v: iou_dip(v) for v in VIEWS}
    r["pass"] = {"no_pop": all(not cm[v]["pops"] for v in VIEWS), "no_iou_dip(<=2.2x neighbours, 0..G+10)": max(x["ratio"] for x in r["consec_iou_dip_0_G10"].values()) <= 2.2,
                 ">=2_feet_on_floor": r["feet_on_floor_min_0_G"] >= 2, "no_float(lowest<=0.5cm)": r["lowest_vertex_max_cm_0_G"] <= 0.5,
                 "breath_d>=0.3_frames0-7": min(min(x) for x in dd.values()) >= 0.3, "start=collapse_end(IoU>=0.98)": min(r["iou_frame0_vs_collapse_end"].values()) >= 0.98}
    return r
def m_airland(act, tag):
    grp = "K"; BH = C.BH_PX[grp]; r = {}
    ml, _, gl = frames_of(act, tag, grp, "left"); mf, wf, _ = frames_of(act, tag, grp, "front")
    sl = MV.series(ml); sf = MV.series(mf, wf)
    lo = sl["lowest"]; floor = lo[-1]; h = floor - lo
    air = np.where(h > 2)[0]; Cf = int(air[-1] + 1); r["contact_frame"] = Cf
    cy = sl["cy"]; v = np.diff(cy)
    va = float(np.mean(v[Cf - 12:Cf - 9])); vb = float(np.mean(v[Cf - 3:Cf]))
    r["descent_px_per_frame"] = {"C-12..C-9": va, "C-3..C": vb}; r["descent_speed_drop"] = 1 - vb / va if va > 0 else float("nan")
    sp = sf["fspan"]; r["span_gain_12f_before_contact"] = float(sp[Cf - 12:Cf + 1].max() / sp[Cf - 12] - 1)
    top = sl["top"]; st_top = C.topmost(stance(grp)["left"])
    drop = (top - st_top) / BH
    win = drop[Cf:Cf + 30]; held = int(np.max(np.convolve((win >= 0.3).astype(int), np.ones(8, int), "valid"))) if len(win) >= 8 else 0
    r["top_drop_BH_max_within_6f"] = float(drop[Cf:Cf + 7].max()); r["top_drop_BH_series_C..C+30"] = drop[Cf:Cf + 31].round(3).tolist()
    r["top_drop>=0.3_held_frames"] = int(np.sum(win >= 0.3)); r["held_8_consecutive"] = held == 8
    cm = common(act, tag, grp, "clip_AL4", "air_land_v4"); r["common"] = cm
    endd = {}
    for vv in VIEWS:
        m, _, g = frames_of(act, tag, grp, vv); d, _ = C.steps(g, m); endd[vv] = float(d[118:].mean() * cm[vv]["factor"])
    r["end_hold_change_118_144"] = endd
    d = load3d(act, tag)
    r["root_step_3d"] = step_ratio3(bone_track(d, "tripo::Spine_0"))
    tt = bone_track(d, "tripo::Tail_2", tail=True); pz = tt[Cf:Cf + 30, 2]; py = tt[Cf:Cf + 30, 1]
    r["tail_tip_after_contact_cm"] = {"z_p2p": float(np.ptp(pz) * 100), "y_p2p": float(np.ptp(py) * 100), "z_min": float(pz.min() * 100)}
    r["end_stance_iou"] = ends(act, tag, grp)
    r["consec_iou_dip"] = {vv: iou_dip(act, tag, grp, vv) for vv in VIEWS}
    r["pass"] = {"no_pop": all(not cm[vv]["pops"] for vv in VIEWS), "no_iou_dip(<=2.2x neighbours)": max(x["ratio"] for x in r["consec_iou_dip"].values()) <= 2.2,
                 "span+30%": r["span_gain_12f_before_contact"] >= 0.30, "descent_drop>=40%": r["descent_speed_drop"] >= 0.40,
                 "top_drop>=0.3BH_within_6f": r["top_drop_BH_max_within_6f"] >= 0.3, "held>=8f": held == 8,
                 "end_breath_d>=0.4": min(endd.values()) >= 0.4, "end_iou>=0.97": min(min(x) for x in [r["end_stance_iou"][vv][1:] for vv in ("front", "left")]) >= 0.97}
    return r
def m_roar(act, tag, hold=(45, 86)):
    grp = "G"; r = {}
    mf, wf, gf = frames_of(act, tag, grp, "front")
    sp, Ls, Rs = M5.roar_halves(mf, stance(grp)["front"])
    pk = int(np.argmax(sp)); a, b = hold
    hr = M5.height_ratio(mf, h0(grp, "front"))
    r.update({"peak_span": float(sp[pk]), "peak_frame": pk, "L_R_at_peak": [float(Ls[pk]), float(Rs[pk])], "hold_mean_L_R": [float(Ls[a:b].mean()), float(Rs[a:b].mean())],
              "hold_gap_mean": float(np.abs(Ls[a:b] - Rs[a:b]).mean()), "hold_gap_max": float(np.abs(Ls[a:b] - Rs[a:b]).max()),
              "hold_gap_rel_max": float((np.abs(Ls[a:b] - Rs[a:b]) / np.maximum(Ls[a:b], Rs[a:b])).max()),
              "height_ratio_max": float(hr.max()), "height_ratio_hold_min": float(hr[a:b].min())})
    cm = common(act, tag, grp, "clip_RS4", "roar_v4"); r["common"] = cm
    ml, _, gl = frames_of(act, tag, grp, "left"); dl, _ = C.steps(gl, ml); r["saw_left_40_90"] = C.saw(dl[40:90] * cm["left"]["factor"])
    df, _ = C.steps(gf, mf); r["hold_change_front"] = float(df[a:b].mean() * cm["front"]["factor"])
    lext = np.array([C.fspan(x, 330)[1] for x in mf], float); rext = np.array([C.fspan(x, 330)[2] for x in mf], float)
    hw = np.arange(a + 3, b - 3); r["wingtip_hp_std_px"] = [float(C.hp(lext)[hw].std()), float(C.hp(rext)[hw].std())]
    r["start_end_stance_iou"] = ends(act, tag, grp)
    r["pass"] = {"peak_span_1.10-1.15": 1.10 <= r["peak_span"] <= 1.15, "height>=1.25": r["height_ratio_hold_min"] >= 1.25,
                 "halves_within_5%": r["hold_gap_rel_max"] <= 0.05, "saw_left<0.15": r["saw_left_40_90"] < 0.15,
                 "wingtip_hp_1.5-3px": all(1.5 <= x <= 3.0 for x in r["wingtip_hp_std_px"]), "hold_change>=1.2": r["hold_change_front"] >= 1.2}
    return r
def m_bite(act, tag):
    grp = "G"; r = {}
    ml = frames_of(act, tag, grp, "left")[0]
    sn = np.array([C.snout_left(x) for x in ml]); x = sn[:, 0]; reach = (x[0] - x) / C.PX_PER_CM_G
    pk = int(np.argmax(reach)); near = np.abs(x - x[pk]) <= 3; run = best = 0
    for i in range(len(near)): run = run + 1 if near[i] else 0; best = max(best, run)
    r.update({"reach_cm": float(reach.max()), "peak_frame": pk, "full_reach_freeze_frames": best})
    m3, w3, _ = frames_of(act, tag, grp, "threequarter"); wa = w3.sum((1, 2)) / max(1, w3[0].sum())
    r["wing_area_3q_44_62_min"] = float(wa[44:63].min())
    cm = common(act, tag, grp, "clip_BI4", "bite_v4"); r["common"] = cm
    r["end_stance_iou"] = ends(act, tag, grp)
    r["pass"] = {"reach>=12cm": r["reach_cm"] >= 12, "freeze<=10": best <= 10, "no_step>2.2x": all(cm[v]["max_step_ratio"]["ratio"] <= 2.2 for v in VIEWS),
                 "wing_3q>=0.7": r["wing_area_3q_44_62_min"] >= 0.7}
    return r
def m_land2(act, tag):
    grp = "T"; BH = C.BH_PX[grp]
    ml = frames_of(act, tag, grp, "left")[0]
    a = MV.arc(ml, BH)
    if isinstance(a, dict): return a
    r, h, cy, lo = a
    jumps = {}
    for v in ("front", "left"):
        lov = MV.series(frames_of(act, tag, grp, v)[0])["lowest"]
        jumps[v] = {"takeoff": float(np.abs(np.diff(lov[r["takeoff"] - 6:r["takeoff"] + 7])).max()), "touchdown": float(np.abs(np.diff(lov[r["touchdown"] - 6:r["touchdown"] + 7])).max())}
    d = load3d(act, tag); fz = feet_z(d); mx = {k: float(np.abs(np.diff(v[r["takeoff"] - 6:r["takeoff"] + 7])).max() * 100) for k, v in fz.items()}
    r.update({"foot_jumps_px": jumps, "foot_vertical_step_max_cm_around_takeoff": mx, "end_vs_start_iou": {v: C.iou(frames_of(act, tag, grp, v)[0][0], frames_of(act, tag, grp, v)[0][-1]) for v in ("front", "left")}})
    r["common"] = common(act, tag, grp, "clip_LA4", "land2_v4")
    r["pass"] = {"hop_0.45-0.55BH(render est = raster x 0.42/0.383)": 0.45 <= r["apex_h_BH"] * 0.42 / 0.383 <= 0.55, "a_ratio_0.8-1.25": 0.8 <= r["a_down_over_a_up"] <= 1.25,
                 "foot_jump<=8px": max(max(j.values()) for j in jumps.values()) <= 8}
    return r
def m_hover(act, tag):
    grp = "K"; BH = C.BH_PX[grp]; r = {}
    mf, wf, gf = frames_of(act, tag, grp, "front"); ml, wl, gl = frames_of(act, tag, grp, "left")
    n = len(mf) if tag == "v5" else len(mf) - 1                          # v5 is exported 0..129; v4 had frame 130 = frame 0
    mf, wf, gf, ml, gl = mf[:n], wf[:n], gf[:n], ml[:n], gl[:n]
    r["beat"] = MV.beat(mf, wf, BH, P=26)
    sd = {}
    for v, g, m in (("front", gf, mf), ("left", gl, ml)):
        d, box = C.steps(g, m); sd[v] = {"seam_129_to_0_steps": C.framediff(g[-1], g[0], box) / float(np.median(d)), "saw": C.saw(d)}
    r["loop"] = sd; r["frames"] = n
    d = load3d(act, tag); V = d["V"][:n]; vn = d["vname"]; bi = d["bones"]
    sh = {s: R.bone(d, f"VeyrWing{s}Root")[:n] for s in ("PosZ", "NegZ")}
    pf_sh = {s: R.project(sh[s], grp, "front")[0][:, 1] for s in sh}
    below = []
    for s in ("PosZ", "NegZ"):
        wv = V[:, np.char.startswith(vn, "VeyrWing" + s)]; P_ = R.project(wv.reshape(-1, 3), grp, "front")[0].reshape(n, -1, 2)
        below.append(float(((P_[:, :, 1].max(1) - pf_sh[s]) / BH).max()))
    r["downstroke_tip_below_shoulder_BH"] = below
    tt = R.project(R.bone(d, "tripo::Tail_2", tail=True)[:n], grp, "left")[0]
    r["tail_tip_p2p_BH"] = float(np.ptp(tt[:, 1]) / BH); r["tail_tip_p2p_x_BH"] = float(np.ptp(tt[:, 0]) / BH)
    r["pass"] = {"downstroke>=0.15BH_below_shoulder": min(below) >= 0.15, "tail_tip_p2p>=0.15BH": r["tail_tip_p2p_BH"] >= 0.15,
                 "seam<=1.2": max(x["seam_129_to_0_steps"] for x in sd.values()) <= 1.2}
    return r
def m_fire(act, tag):
    grp = "K"; BH = C.BH_PX[grp]; r = {}
    mf, wf, gf = frames_of(act, tag, grp, "front")
    r["beat"] = MV.beat(mf, wf, BH, P=27)
    wt = np.array([C.topmost(y) if y.any() else C.topmost(x) for x, y in zip(mf, wf)], float)
    r["wingtop_p2p_33_66_BH"] = float(np.ptp(wt[33:67]) / BH)
    ml, wl, _ = frames_of(act, tag, grp, "left"); wtl = np.array([C.topmost(y) if y.any() else C.topmost(x) for x, y in zip(ml, wl)], float)
    r["wingtop_p2p_33_66_BH_left"] = float(np.ptp(wtl[33:67]) / BH)
    cm = common(act, tag, grp, "clip_FD4", "air_fire_down_v4"); r["common"] = cm
    hold = {}
    for v in ("front", "left"):
        m, _, g = frames_of(act, tag, grp, v); d, _ = C.steps(g, m); hold[v] = float(d[80:152].mean() * cm[v]["factor"])
    r["hold_80_152_change"] = hold
    r["pass"] = {"wingtop_p2p_33_66>=0.3BH": r["wingtop_p2p_33_66_BH"] >= 0.3, "hold>=1.0": min(hold.values()) >= 1.0}
    return r
def m_takeoff(act, tag):
    grp = "K"; BH = C.BH_PX[grp]
    mf, wf, _ = frames_of(act, tag, grp, "front"); ml = frames_of(act, tag, grp, "left")[0]
    sl = MV.series(ml); lo = sl["lowest"]; h = lo[0] - lo; L_ = int(np.argmax(h > 2))
    r = {"liftoff_frame": L_, "peak_over_end": float(h.max() / h[-1]) if h[-1] > 0 else None, "beat_airborne": MV.beat(mf, wf, BH, (L_ + 10, len(mf)))}
    r["common"] = common(act, tag, grp, "clip_TK4", "takeoff3_v4")
    return r

JOBS = {
    "collapse": lambda tag: m_collapse(f"collapse_{tag}", tag),
    "rise": lambda tag: m_rise(f"rise_{tag}", tag, f"collapse_{tag}"),
    "air_land": lambda tag: m_airland(f"air_land_{tag}", tag),
    "roar": lambda tag: m_roar(f"roar_{tag}", tag),
    "bite": lambda tag: m_bite(f"bite_{tag}", tag),
    "land2": lambda tag: m_land2(f"land2_{tag}", tag),
    "air_hover": lambda tag: m_hover(f"air_hover_{tag}", tag),
    "air_fire_down": lambda tag: m_fire(f"air_fire_down_{tag}", tag),
    "takeoff3": lambda tag: m_takeoff(f"takeoff3_{tag}", tag),
}
RES = json.load(open(OUT)) if os.path.exists(OUT) else {}
for k, fn in JOBS.items():
    if ONLY is not None and k not in ONLY: continue
    RES.setdefault(k, {})
    for tag in ("v4", "v5"):
        act = f"{k}_{tag}" if k != "air_land" else f"air_land_{tag}"
        try:
            if not os.path.exists(dump_path({"rise": f"rise_{tag}"}.get(k, f"{k}_{tag}"), tag)): continue
            RES[k][tag] = rnd(fn(tag))
        except Exception as e:
            import traceback; traceback.print_exc(); RES[k][tag] = {"error": repr(e)}
        print(k, tag, json.dumps(RES[k][tag].get("pass", RES[k][tag].get("error", ""))), flush=True)
    json.dump(RES, open(OUT, "w"), indent=1)
RES["_method"] = ("CPU raster of the evaluated mesh through the review cameras (raster.py) with the round-3 critic's definitions (critic.py, metrics_v5.py); "
                  "per-frame-change numbers scaled by each clip's critic/raster ratio measured on its v4 review render; 3D checks from the same dumps.")
json.dump(RES, open(OUT, "w"), indent=1)
