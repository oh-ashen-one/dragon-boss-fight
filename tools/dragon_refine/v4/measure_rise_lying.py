#!/usr/bin/env python3
"""CPU measure of the rise-from-lying Action before any render (no Blender, no GPU): the critic's round-3/4 definitions (raster.py + critic.py,
as measure_v5.py) on the dump of the Action (dump_verts.py output, or lib_rise_lying.cpu_dump for a dry run), compared with the same numbers
for the authored rise v5 (A/B reference) and, when given, the silhouette overlap with the source clip's panel masks.
  python3 measure_rise_lying.py <out.json> rl=<dump.npz> [ch=<out.blend.channels.npz>] [idle=<d_idle_v2.npz>] [ref=<d_rise_v5.npz>]
        [raw=<dump of the raw fit>] [start=<first raw frame kept>] [views=<views.npz> masks=<masks.npz>] [hold_s=1.25] [idle_blend=8] [cap=25] [jump=8]
Numbers: pops and per-frame change (G cameras, front / left / three-quarter), the hold (body height onset), feet under the floor and feet
on the floor per frame, wing root twist and the biggest wing Euler step (from ch=), the last frame against the idle pose (vertices + silhouettes),
the largest per-frame change inside the idle blend, silhouette IoU against the source masks over the kept clip (raw fit vs the Action).
Per-frame-change numbers are raster values (factor 1.0: the new clip has no critic render to calibrate against; the v5 reference is measured the same way).
"""
import sys, os, json
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import raster as R, critic as C, metrics_v5 as M5
import lib_rise_lying as RL
OUT = sys.argv[1]; opt = dict(a.split("=", 1) for a in sys.argv[2:])
VIEWS = ("front", "left", "threequarter"); GRP = "G"
def rnd(o):
    if isinstance(o, dict): return {str(k): rnd(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [rnd(v) for v in o]
    if isinstance(o, (bool, np.bool_)): return bool(o)
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, (float, np.floating)): return round(float(o), 3)
    if isinstance(o, np.ndarray): return rnd(o.tolist())
    return o
def frames_of(path):
    d = R.load(path); out = {}
    for v in VIEWS:
        m, w, g = R.render(d, GRP, v); m = np.stack([C.clean(x) for x in m]); out[v] = (m, w & m, g)
    return d, out
def convex_mask(d, f, view):
    P, _ = R.project(d["V"][f], GRP, view); img = np.zeros((R.H, R.W), np.uint8)
    for t in np.round(P * 16).astype(np.int32)[d["tri"]]: cv2.fillConvexPoly(img, t, 1, cv2.LINE_8, 4)
    return img.astype(bool)
FOOTG = {"front+Y": ["bone_9", "tripo::1_Left_Limb_1"], "front-Y": ["bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"],
         "hind+Y": ["tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4"], "hind-Y": ["tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"]}
def feet_z(d): return {k: d["V"][:, np.isin(d["vname"], g), 2].min(1) for k, g in FOOTG.items()}
def clip_numbers(path, label):
    d, fr = frames_of(path); n = len(d["V"]); r = {"frames": n}
    isw = np.char.startswith(d["vname"], "VeyrWing"); foot = np.isin(d["vname"], sum(FOOTG.values(), []))
    com = {}
    for v in VIEWS:
        m, w, g = fr[v]; dch, _ = C.steps(g, m)
        ci = M5.consec_iou(m)
        com[v] = {"pops": M5.pop_scan(dch), "max_step_ratio": M5.max_step_ratio(dch), "consec_iou_min": float(ci.min()), "consec_iou_min_at": int(ci.argmin()),
                  "change_max": float(dch.max()), "change_max_at": int(dch.argmax()), "change_mean": float(dch.mean()), "d": dch}
    r["views"] = {v: {k: val for k, val in c.items() if k != "d"} for v, c in com.items()}
    d_front = com["front"]["d"]; r["_d"] = {v: com[v]["d"] for v in VIEWS}
    low_body = d["V"][:, ~isw & ~foot, 2].min(1); low_all = d["V"][:, :, 2].min(1); fz = feet_z(d)
    r["floor"] = {"body_min_cm": float(low_body.min() * 100), "body_frames_under_-0.3cm": int((low_body < -0.003).sum()), "feet_min_cm": {k: float(v.min() * 100) for k, v in fz.items()},
                  "feet_frames_under_-0.5cm": int(sum(((v < -0.005)).sum() for v in fz.values())), "all_min_cm": float(low_all.min() * 100),
                  "wing_min_cm": float(d["V"][:, isw, 2].min() * 100)}
    cnt = sum((v <= 0.005).astype(int) for v in fz.values()); r["feet_on_floor_series"] = cnt.tolist(); r["feet_on_floor_min_after_frame6"] = int(cnt[6:].min())
    sel = np.where(~isw)[0][::7]; zc = d["V"][:, sel, 2].mean(1); ref = float(np.median(zc[6:14]))
    onset = next((i for i in range(14, n - 3) if np.all(zc[i:i + 3] > ref + 0.004)), n)
    r["hold_frames"] = int(onset); r["hold_s"] = round(onset / 24.0, 2); r["hold_def"] = "first frame the body (wings left out) stays 0.4 cm above its height over frames 6..13 for 3 frames"
    r["top_cm_series_every_6"] = (d["V"][::6, :, 2].max(1) * 100).tolist()
    r["_dump"] = d; r["_fr"] = fr; return r
RL_PATH = opt["rl"]; res = {"_method": "CPU raster of the evaluated mesh (raster.py) with the critic's definitions (critic.py, metrics_v5.py); factor 1.0"}
a = clip_numbers(RL_PATH, "rl"); n = a["frames"]
HOLD_S = float(opt.get("hold_s", 1.25)); IB = int(opt.get("idle_blend", 8)); WB = max(IB, int(opt.get("wing_blend", 16))); EASE = int(opt.get("ease", 6)); CAP = float(opt.get("cap", 25.0)); JUMP = float(opt.get("jump", 8.0))
out = {k: v for k, v in a.items() if not k.startswith("_")}
# ---- the idle blend and the last frame against the idle pose
if "idle" in opt:
    di = R.load(opt["idle"]); dl = a["_dump"]; Xi, Xl = di["V"][0], dl["V"][-1]; dv = np.linalg.norm(Xi - Xl, axis=1)
    sil = {v: float(C.iou(convex_mask(di, 0, v), convex_mask(dl, n - 1, v))) for v in VIEWS}
    out["last_vs_idle"] = {"max_vertex_mm": float(dv.max() * 1000), "mean_vertex_mm": float(dv.mean() * 1000), "silhouette_iou": sil,
                           "bone_head_max_mm": float(np.abs(a["_dump"]["bone_head"][-1] - di["bone_head"][0]).max() * 1000)}
    dd = {v: np.array(a["_d"][v]) for v in VIEWS}
    out["idle_blend_change"] = {v: {"max_in_blend": float(dd[v][-IB:].max()), "max_before_blend": float(dd[v][:-IB].max()), "median_clip": float(np.median(dd[v]))} for v in VIEWS}
# ---- authored rise v5 reference
if "ref" in opt and os.path.exists(opt["ref"]):
    b = clip_numbers(opt["ref"], "ref"); out["ref_rise_v5"] = {k: v for k, v in b.items() if not k.startswith("_")}
    out["ref_rise_v5"]["views"] = {v: {k: val for k, val in c.items()} for v, c in b["views"].items()}
# ---- channels: twist and steps
if "ch" in opt and os.path.exists(opt["ch"]):
    z = np.load(opt["ch"], allow_pickle=True); m = RL.Motion.__new__(RL.Motion); m.bones = [str(x) for x in z["bones"]]; m.q = z["q"]; m.loc = z["loc"]; m.N = len(m.q); m.root = "tripo::Spine_0"
    wb = RL.wing_bones(m); tw = RL.twist_deg(m, wb); jump = RL.euler_jump_deg(m, wb, frames=list(range(EASE + 1, m.N - WB)))
    jb = RL.euler_jump_deg(m, wb, frames=list(range(m.N - WB, m.N)))
    allj = max(float(np.max(RL.qangle_deg(m.q[1:], m.q[:-1]))), 0.0)
    out["channels"] = {"wing_twist_max_deg": dict(list(tw.items())[:4]), "wing_euler_step_max_deg": {"deg": jump[0], "bone": jump[1], "frame": jump[2], "frames": f"{EASE + 1}..{m.N - WB - 1}: after the ease from the collapse end pose, before the wing blend into idle"},
                         "wing_euler_step_in_idle_blend_deg": {"deg": jb[0], "bone": jb[1], "frame": jb[2]}, "any_bone_rotation_step_max_deg": allj}
# ---- silhouettes against the source clip
if "views" in opt and "masks" in opt and "raw" in opt:
    import src_views_rl as S
    Vw = S.Views(opt["views"], opt["masks"]); dr = R.load(opt["raw"]); da = a["_dump"]; st = int(opt.get("start", 0)); ib = IB
    tri = da["tri"]; rows = []
    for f in range(ib, n - WB):                         # skip the ease-in and the idle blend: only the fit's own frames
        raw_f = f + st
        if raw_f >= len(dr["V"]): break
        row = []
        for k in range(Vw.n):
            mk = Vw.panel_mask(raw_f, k)
            row += [S.iou(Vw.fill(dr["V"][raw_f], tri, k), mk), S.iou(Vw.fill(da["V"][f], tri, k), mk)]
        rows.append(row)
    rows = np.array(rows); out["silhouette_vs_source"] = {"frames": [ib + st, ib + st + len(rows) - 1],
        "front": {"raw_fit": float(rows[:, 0].mean()), "action": float(rows[:, 1].mean())}, "side": {"raw_fit": float(rows[:, 2].mean()), "action": float(rows[:, 3].mean())}}
    wlo, whi = int(opt.get("wing_a", 100)) - st - ib, int(opt.get("wing_b", 134)) - st - ib
    whi = min(whi, len(rows) - 1)
    if 0 <= wlo < whi:
        out["silhouette_vs_source"]["wing_window"] = {"front": {"raw_fit": float(rows[wlo:whi + 1, 0].mean()), "action": float(rows[wlo:whi + 1, 1].mean())},
                                                      "side": {"raw_fit": float(rows[wlo:whi + 1, 2].mean()), "action": float(rows[wlo:whi + 1, 3].mean())}}
# ---- verdicts
P = {}
pops = {v: out["views"][v]["pops"] for v in VIEWS}
refpops = {v: out["ref_rise_v5"]["views"][v]["pops"] for v in VIEWS} if "ref_rise_v5" in out else None
P["no_pop_in_any_view(raster, factor 1.0)"] = all(not p for p in pops.values()) if refpops is None else sum(len(p) for p in pops.values()) <= sum(len(p) for p in refpops.values())
P["body_not_under_floor(-0.3cm)"] = out["floor"]["body_frames_under_-0.3cm"] == 0
P["feet_not_under_floor(-0.5cm)"] = out["floor"]["feet_frames_under_-0.5cm"] == 0
P["hold_1.0-1.6s"] = 1.0 <= out["hold_s"] <= 1.6
if "channels" in out:
    P[f"wing_twist<={CAP:g}"] = max(out["channels"]["wing_twist_max_deg"].values()) <= CAP + 0.05
    P[f"wing_step<={JUMP:g}"] = out["channels"]["wing_euler_step_max_deg"]["deg"] <= JUMP + 0.05
if "last_vs_idle" in out: P["last_frame==idle(<=1mm)"] = out["last_vs_idle"]["max_vertex_mm"] <= 1.0
if "silhouette_vs_source" in out and "wing_window" in out["silhouette_vs_source"]:
    ww = out["silhouette_vs_source"]["wing_window"]; P["wing_window_iou_not_worse_than_raw(-0.02)"] = (ww["front"]["action"] + ww["side"]["action"]) / 2 >= (ww["front"]["raw_fit"] + ww["side"]["raw_fit"]) / 2 - 0.02
out["pass"] = P
res.update({"rise_lying": out}); json.dump(rnd(res), open(OUT, "w"), indent=1)
print("MEASURE", json.dumps(rnd(P)))
print("hold_s", out["hold_s"], "| pops", {v: len(p) for v, p in pops.items()}, "| ref pops", None if refpops is None else {v: len(p) for v, p in refpops.items()})
print("floor", rnd(out["floor"]))
for k in ("last_vs_idle", "idle_blend_change", "channels", "silhouette_vs_source"):
    if k in out: print(k, json.dumps(rnd(out[k])))
