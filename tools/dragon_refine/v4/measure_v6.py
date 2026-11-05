"""Measure fix round 4 against the round-4 critic's targets (docs/dragon-critique-round4-20261030.md) BEFORE rendering:
CPU raster of the evaluated mesh through the review cameras (raster.py), scored with the round-4 critic's definitions
(metrics_v6.py) plus the round-3 checks the v5 clips already passed (measure_v5's m_* functions), so a regression shows.
python3 measure_v6.py <out.json> v4=<dump dir> v5=<dump dir> v6=<dump dir> [only=move,move] [seg=<critic-seg cache dir>]
Per-frame-change numbers (d) are raster values times the per-clip critic/raster factor from the v4 render (measure_v5),
i.e. in the round-3 critic's units; the round-4 critic's d scale is ~2.5x that (critique-round4, "How to read the numbers").
Calibration of the proxies on v4/v5 raster vs the round-4 critic's render readings (2026-10-30):
  roar halves about the frame-0 centre: v5 raster L 1.075 / R 1.157 (gap 0.082) vs critic L 1.03 / R 1.11 (gap 0.085);
  v4 raster gap 0.012 vs critic 0.017; span hold raster 1.098-1.132 vs critic 1.06-1.09 -> critic ~ raster - 0.04.
  bite upper-left zone (frame-0 centroid quadrant, 3/4): v4 raster 0.27/0.39/0.54 at 50/56/62 vs critic 0.27/0.37/0.52;
  v5 raster 0.61/0.74/0.80 vs critic 0.54/0.67/0.73 -> critic ~ raster - 0.07 (conservative).
  collapse front end height: v5 raster 0.531 vs critic 0.53 -> critic ~ raster.
  roar tremor dominant period (front d, hold, band 2-20 f): v4 raster 2.7 vs critic 3.7 (buzz); v5 raster 5.1 vs critic 9.6
  (irregular, accepted) -> pass = raster period >= 4.5 f."""
import sys, os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
OUT = sys.argv[1]
opt = dict(a.split("=", 1) for a in sys.argv[2:])
# reuse measure_v5's raster cache / factor / round-3 checks without running its main block
_src = open(os.path.join(HERE, "measure_v5.py")).read(); _cut = _src.find("\nRES = json.load")
_argv = sys.argv; sys.argv = [os.path.join(HERE, "measure_v5.py"), "/dev/null", f"v4={opt['v4']}", f"v5={opt['v5']}"] + ([f"seg={opt['seg']}"] if "seg" in opt else [])
G5 = {"__file__": os.path.join(HERE, "measure_v5.py"), "__name__": "measure_v5_lib"}; exec(compile(_src[:_cut], "measure_v5", "exec"), G5); sys.argv = _argv
G5["DIRS"]["v6"] = opt["v6"]
import critic as C, metrics_v5 as M5, metrics_v6 as M6
fo, common, rnd, stance, h0 = G5["frames_of"], G5["common"], G5["rnd"], G5["stance"], G5["h0"]
ONLY = set(opt["only"].split(",")) if "only" in opt else None
VIEWS = ("front", "left", "threequarter")
CRITIC_OFF = {"roar_span": -0.04, "bite_zone": -0.07, "collapse_h": 0.0}

def d_of(act, tag, grp, view, label4, act4):
    m, _, g = fo(act, tag, grp, view); d, _ = C.steps(g, m); return d * G5["factor"](label4, act4, grp, view), m
def m_airland(tag):
    act = f"air_land_{tag}"; grp = "K"; r = {}
    df, mf = d_of(act, tag, grp, "front", "clip_AL4", "air_land_v4")
    r["front_area_change_max_90_120"], r["front_area_change_step"] = M6.area_change(mf, 90, 120)
    r["front_d_94_114"] = df[94:115].round(2).tolist()
    sr = {}
    for v in VIEWS:
        d, _ = d_of(act, tag, grp, v, "clip_AL4", "air_land_v4"); sr[v] = {"pops": M5.pop_scan(d), "max_step_ratio_90_120": M5.max_step_ratio(d[90:120])}
    r["step_rule"] = sr
    r["front_hold_d_106_114_min"] = float(df[105:114].min())          # step i = frame i -> i+1
    r["v5_checks"] = G5["m_airland"](act, tag)
    r["pass"] = {"front_area_change<=12%/f": r["front_area_change_max_90_120"] <= 0.12,
                 "no_step>2.2x_neighbours": all(not sr[v]["pops"] and sr[v]["max_step_ratio_90_120"]["ratio"] <= 2.2 for v in VIEWS),
                 "front_hold_d>=0.4(r3 units)": r["front_hold_d_106_114_min"] >= 0.4,
                 "v5_checks_still_pass": all(r["v5_checks"]["pass"].values())}
    return r
def m_roar(tag, hold=(45, 86)):
    act = f"roar_{tag}"; grp = "G"; a, b = hold; r = {}
    mf = fo(act, tag, grp, "front")[0]; L, R, S = M6.halves_f0(mf)
    gap = np.abs(L - R)[a:b] / np.maximum(L, R)[a:b]
    r.update({"hold_L_R_mean": [float(L[a:b].mean()), float(R[a:b].mean())], "hold_gap_rel_mean": float(gap.mean()), "hold_gap_rel_max": float(gap.max()),
              "span_hold_raster": [float(S[a:b].min()), float(S[a:b].mean()), float(S[a:b].max())],
              "span_hold_critic_est": [float(S[a:b].min() + CRITIC_OFF["roar_span"]), float(S[a:b].mean() + CRITIC_OFF["roar_span"]), float(S[a:b].max() + CRITIC_OFF["roar_span"])]})
    df, _ = d_of(act, tag, grp, "front", "clip_RS4", "roar_v4"); r["tremor_dominant_period_frames"] = M6.dominant_period(df[a:b])
    r["v5_checks"] = G5["m_roar"](act, tag)
    sm = r["span_hold_critic_est"][1]
    r["pass"] = {"halves_within_5%(mean)": r["hold_gap_rel_mean"] <= 0.05, "span_hold_1.10-1.12(critic est, mean)": 1.10 <= sm <= 1.12,
                 "tremor_not_buzz(raster period>=4.5f)": r["tremor_dominant_period_frames"] >= 4.5, "height>=1.25": r["v5_checks"]["pass"]["height>=1.25"]}
    return r
def m_collapse(tag):
    act = f"collapse_{tag}"; grp = "G"; r = {}
    end = {}
    for v in ("front", "left", "threequarter"):
        m = fo(act, tag, grp, v)[0]; end[v] = float((C.lowest(m[-1]) - C.topmost(m[-1])) / h0(grp, v))
    r["end_height_ratio"] = end
    br = {}
    for v, lab in (("front", "clip_CO4"), ("left", "clip_CO4"), ("threequarter", "clip_CO4")):
        d, _ = d_of(act, tag, grp, v, lab, "collapse_v4"); br[v] = {"min": float(d[-35:].min()), "mean": float(d[-35:].mean())}
    r["breath_last35_d"] = br
    rp = os.path.join(G5["DIRS"]["v5"], "d_rise_v5.npz")
    if os.path.exists(rp):
        r["seam_iou_vs_rise_v5_frame0"] = {v: float(C.iou(fo(act, tag, grp, v)[0][-1], fo("rise_v5", "v5", grp, v)[0][0])) for v in VIEWS}
    r["v5_checks"] = G5["m_collapse"](act, tag)
    r["pass"] = {"front_height<=0.50": end["front"] + CRITIC_OFF["collapse_h"] <= 0.50, "breath_min_d>=v4_level": None,
                 "leftmost_3q>=200": r["v5_checks"]["pass"].get("leftmost_3q>=200(raster, v4 render offset +17)")}
    return r
def m_bite(tag):
    act = f"bite_{tag}"; grp = "G"; r = {}
    m3 = fo(act, tag, grp, "threequarter")[0]; z, zone = M6.zone_area(m3)
    r["zone"] = list(map(int, zone)); r["zone_area"] = {str(f): float(z[f]) for f in (44, 47, 50, 56, 62)}
    r["zone_area_44_50_min"] = float(z[44:51].min()); r["zone_area_44_50_min_critic_est"] = float(z[44:51].min() + CRITIC_OFF["bite_zone"])
    r["v5_checks"] = G5["m_bite"](act, tag)
    r["pass"] = {"near_wing>=0.7_44-50(critic est)": r["zone_area_44_50_min_critic_est"] >= 0.7, "v5_checks_still_pass": all(r["v5_checks"]["pass"].values())}
    return r
JOBS = {"air_land": m_airland, "roar": m_roar, "collapse": m_collapse, "bite": m_bite}
RES = json.load(open(OUT)) if os.path.exists(OUT) else {}
for k, fn in JOBS.items():
    if ONLY is not None and k not in ONLY: continue
    RES.setdefault(k, {})
    for tag in ("v4", "v5", "v6"):
        if not os.path.exists(os.path.join(G5["DIRS"][tag], f"d_{k}_{tag}.npz")): continue
        try: RES[k][tag] = rnd(fn(tag))
        except Exception as e:
            import traceback; traceback.print_exc(); RES[k][tag] = {"error": repr(e)}
        print(k, tag, json.dumps(RES[k][tag].get("pass", RES[k][tag].get("error", ""))), flush=True)
    if k == "collapse" and "v6" in RES[k] and "v4" in RES[k] and "breath_last35_d" in RES[k]["v6"]:
        ok = all(RES[k]["v6"]["breath_last35_d"][v]["min"] >= RES[k]["v4"]["breath_last35_d"][v]["min"] for v in VIEWS)
        RES[k]["v6"]["pass"]["breath_min_d>=v4_level"] = ok
RES["_method"] = __doc__
json.dump(RES, open(OUT, "w"), indent=1)
