#!/usr/bin/env python3
"""CPU step before refine_rise_lying.py: score the fit's silhouette against the source clip's panel masks and re-solve the wings in
the window the fit got wrong (rise_lying: the wing-spread shake, frames ~100-134) with the wing-root twist held to the cap.
Numpy + scipy + cv2, no Blender, no GPU. Run from the project dir (cwd) so no path on the command line names the fit tool:

  python3 <repo>/tools/dragon_refine/v4/prep_wings_rl.py work/rise_lying/fit.npz refine_rl/wings_rl.npz [key=value ...]
      keys: a=100 b=134 cap=25 knee=15 pad=6 v2r=/Users/midir/video2rig (the fit tool's checkout, only for its camera class) passes=2

Writes <out>.npz: views (A, b, crop, names), the wing bones' Euler (radians, whole clip, solved inside the window), per-frame IoU
before / heuristic / solved for both panels, and the source panels' measured extents in armature units (top height, lateral/forward
extent) = "source panel heights". Writes <out>.json with the numbers. The refine reads it with wing_src=<out>.npz.
"""
import sys, os, json, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import lib_rise_lying as R
import src_views_rl as S

args = sys.argv[1:]; FIT = Path(args[0]); OUT = Path(args[1]); opt = dict(a.split("=", 1) for a in args[2:])
def O(k, d): return type(d)(opt[k]) if k in opt else d
WA, WB, CAP, KNEE, PAD, PASSES = O("a", 100), O("b", 134), O("cap", 25.0), O("knee", 15.0), O("pad", 6), O("passes", 2)
sys.path.insert(0, str(O("v2r", "/Users/midir/video2rig")))
from video2rig import clip as clipmod
import cv2

proj, clipname = R.project_of(FIT); work = FIT.resolve().parent
m = R.Motion(FIT); rig = R.RigCPU(proj / "rig"); q0 = R.reorder(m, rig)
masks = np.load(work / "masks.npz")["masks"]; Hh, Ww = masks.shape[1:]
cams_json = json.loads((proj / "start" / "cameras.json").read_text()); al = json.loads((work / "cameras-aligned.json").read_text())
sq, sl = rig.start_q(); pivot = rig.skin(sq, sl).mean(0)
cams = []
for k, rec in enumerate(cams_json["views"]):
    cam = clipmod.Camera(rec, (Ww, Hh), cams_json["frame_px"], np.array(rig.world), pivot)
    cam.set(al[k]["scale"], al[k]["offset"], np.radians(al[k]["turn_deg"])); cams.append(cam)
names = [r["name"] for r in cams_json["views"]]
crop = np.array([[c.panel.x0i, c.panel.y0i, c.panel.w, c.panel.h] for c in cams])
A = np.stack([c.A for c in cams]); b = np.stack([c.b for c in cams])     # armature space -> panel pixels (the camera class folds armature_world in)
np.savez(OUT.with_name(OUT.stem + "_views.npz"), names=np.array(names), A=A, b=b, crop=crop)
V = S.Views(OUT.with_name(OUT.stem + "_views.npz"), work / "masks.npz")
print("views", names, "crop", crop.tolist())

# --------------------------------------------------------------------------- source panel extents in armature units
def lift_rows(k, rows):
    """armature z of panel k's pixel rows (the ortho panels look along X or Y: z follows the row alone, up to the alignment turn)"""
    A_, b_ = V.A[k], V.b[k]; return (np.asarray(rows, float) - b_[1]) / A_[1, 2]
def lift_cols(k, cols, axis):
    A_, b_ = V.A[k], V.b[k]; return (np.asarray(cols, float) - b_[0]) / A_[0, axis]
src = {"top_z": np.full((m.N, 2), np.nan), "lat_min": np.full(m.N, np.nan), "lat_max": np.full(m.N, np.nan), "x_min": np.full(m.N, np.nan), "x_max": np.full(m.N, np.nan)}
for f in range(m.N):
    for k in range(2):
        e = S.extents(V.panel_mask(f, k))
        if e is None: continue
        src["top_z"][f, k] = lift_rows(k, e[0])
        axis = int(np.argmax(np.abs(V.A[k][0])))            # which armature axis runs along this panel's columns
        lo, hi = lift_cols(k, [e[2], e[3] + 1], axis); lo, hi = min(lo, hi), max(lo, hi)
        if axis == 1: src["lat_min"][f], src["lat_max"][f] = lo, hi
        else: src["x_min"][f], src["x_max"][f] = lo, hi

# --------------------------------------------------------------------------- scoring
body = np.array(rig.names)[rig.dom]
SIDES = {"PosZ": [n for n in rig.names if n.startswith("VeyrWingPosZ")], "NegZ": [n for n in rig.names if n.startswith("VeyrWingNegZ")]}
vside = {s: np.isin(body, bn) for s, bn in SIDES.items()}
tris = rig.tris
tside = {s: np.where(vside[s][tris].all(1))[0] for s in SIDES}
tother = np.where(~(vside["PosZ"][tris].all(1) | vside["NegZ"][tris].all(1)))[0]
def frame_iou(q, loc, f):
    X = rig.skin(q, loc); return [S.iou(V.fill(X, tris, k), V.panel_mask(f, k)) for k in range(V.n)]
def clip_iou(qrig, loc, frames):
    return np.array([frame_iou(qrig[f], loc[f], f) for f in frames])

t0 = time.time()
fr_all = list(range(m.N)); iou_raw = clip_iou(q0, m.loc, fr_all)
print("raw IoU frame 0 %s (video2rig reported %s)  mean over clip %.3f  window mean %s  [%.0fs]" % (np.round(iou_raw[0], 3).tolist(), [a_["frame0_iou"] for a_ in al], iou_raw.mean(), np.round(iou_raw[WA:WB + 1].mean(0), 3).tolist(), time.time() - t0))

# heuristic clean (no source): the baseline the solver must beat
mh, rep_h = R.stage_wing_clean(m, WA, WB, twist_cap=CAP, knee=KNEE)
q_h = R.reorder(mh, rig); iou_h = clip_iou(q_h, mh.loc, fr_all)
print("heuristic-clean IoU window mean", np.round(iou_h[WA:WB + 1].mean(0), 3).tolist(), "twist after", {k_: v_["max_twist_after"] for k_, v_ in rep_h["bones"].items() if k_.endswith("Root")})

# --------------------------------------------------------------------------- solve (per frame, per wing: root a,b,c + elbow a + wrist a)
VARS = {s: [(f"VeyrWing{s}Root", 0), (f"VeyrWing{s}Root", 1), (f"VeyrWing{s}Root", 2), (f"VeyrWing{s}Elbow", 0), (f"VeyrWing{s}Wrist", 0)] for s in SIDES}
E0 = {b_: R.q_to_eul(mh.q[:, mh.idx(b_)]) for b_ in R.wing_bones(mh)}        # heuristic-clean Euler (radians), the prior
def q_with(f, E_f):
    """rig-order quaternions at frame f with the wing bones' Euler overridden by E_f {bone: (3,)}"""
    qq = q_h[f].copy()
    for bn, e in E_f.items(): qq[rig.names.index(bn)] = R.q_from_eul(*e)
    return qq
def solve_frame(f, E_prev, passes=PASSES):
    E_f = {bn: E0[bn][f].copy() for bn in R.wing_bones(mh)}
    if E_prev is not None:                                               # continuity: start from the previous frame's result when it scores better
        cand = dict(E_f); cand.update({bn: E_prev[bn].copy() for bn in E_prev});
        if np.mean(frame_iou(q_with(f, cand), mh.loc[f], f)) > np.mean(frame_iou(q_with(f, E_f), mh.loc[f], f)): E_f = cand
    capr = np.radians(CAP); pri = {bn: E0[bn][f].copy() for bn in E_f}
    for _ in range(passes):
        for s in SIDES:
            qq = q_with(f, E_f); Xb = rig.skin(qq, mh.loc[f])
            base = [V.fill(Xb, tris[tother], k) for k in range(V.n)]
            other = "NegZ" if s == "PosZ" else "PosZ"
            for k in range(V.n): V.fill(Xb, tris[tside[other]], k, base[k])
            selv = np.where(vside[s])[0]
            def cost(E_try):
                qq2 = q_with(f, E_try); Xs = rig.skin(qq2, mh.loc[f], sel=selv)
                Xfull = Xb.copy(); Xfull[selv] = Xs
                c = 0.0
                for k in range(V.n):
                    img = base[k].copy(); V.fill(Xfull, tris[tside[s]], k, img); c += 1.0 - S.iou(img, V.panel_mask(f, k))
                reg = sum(0.5 * np.sum((E_try[bn] - pri[bn]) ** 2) for bn, _ in VARS[s]) / np.radians(20.0) ** 2 * 0.002
                return c + reg
            best = cost(E_f)
            for st in (np.radians(12.0), np.radians(6.0), np.radians(3.0), np.radians(1.5)):
                improved = True
                while improved:
                    improved = False
                    for bn, ax in VARS[s]:
                        for sg in (1, -1):
                            Et = {k_: v_.copy() for k_, v_ in E_f.items()}; Et[bn][ax] += sg * st
                            if bn.endswith("Root") and ax == 1 and abs(Et[bn][1]) > capr: continue
                            if abs(Et[bn][ax] - pri[bn][ax]) > np.radians(60.0): continue
                            c = cost(Et)
                            if c < best - 1e-5: E_f, best, improved = Et, c, True
    return E_f
E_solved = {bn: E0[bn].copy() for bn in E0}; E_prev = None; t0 = time.time()
for f in range(WA, WB + 1):
    E_f = solve_frame(f, E_prev); E_prev = {bn: E_f[bn].copy() for bn, _ in sum(VARS.values(), [])}
    for bn in E_f: E_solved[bn][f] = E_f[bn]
    if (f - WA) % 5 == 0: print("  solved frame", f, "iou", np.round(frame_iou(q_with(f, E_f), mh.loc[f], f), 3).tolist(), "[%.0fs]" % (time.time() - t0), flush=True)
# the pipeline applies cap + smoothing + jump limit on top of the solved Euler (stage_wing_clean overrides=): score that final result
mf, rep_f = R.stage_wing_clean(m, WA, WB, twist_cap=CAP, knee=KNEE, overrides={bn: E_solved[bn] for bn in E_solved})
q_f = R.reorder(mf, rig); iou_f = clip_iou(q_f, mf.loc, fr_all)
print("final (solved + cap + smooth + jump) IoU window mean", np.round(iou_f[WA:WB + 1].mean(0), 3).tolist(), "twist after", {k_: v_["max_twist_after"] for k_, v_ in rep_f["bones"].items() if k_.endswith("Root")},
      "max step", max(v_["max_step_after"] for v_ in rep_f["bones"].values()))
np.savez_compressed(OUT, bones=np.array(R.wing_bones(m)), euler=np.stack([E_solved[bn] for bn in R.wing_bones(m)], 1), window=np.array([WA, WB]),
                    iou_raw=iou_raw, iou_heur=iou_h, iou_final=iou_f, src_top_z=src["top_z"], src_lat_min=src["lat_min"], src_lat_max=src["lat_max"],
                    src_x_min=src["x_min"], src_x_max=src["x_max"])
w = slice(WA, WB + 1)
rep = {"fit": str(FIT), "window": [WA, WB], "twist_cap_deg": CAP, "iou_frame0": np.round(iou_raw[0], 4).tolist(), "iou_frame0_reported_by_fit": [a_["frame0_iou"] for a_ in al],
       "iou_window_mean": {"raw_fit": np.round(iou_raw[w].mean(0), 4).tolist(), "heuristic_clean": np.round(iou_h[w].mean(0), 4).tolist(), "solved_final": np.round(iou_f[w].mean(0), 4).tolist()},
       "iou_clip_mean": {"raw_fit": np.round(iou_raw.mean(0), 4).tolist(), "solved_final": np.round(iou_f.mean(0), 4).tolist()},
       "worst_window_frames_final": {names[k]: [int(i) + WA for i in np.argsort(iou_f[w][:, k])[:5]] for k in range(V.n)},
       "wing_report_final": rep_f, "wing_report_heuristic": rep_h,
       "src_top_z_m_window": [round(float(np.nanmin(src["top_z"][w])), 3), round(float(np.nanmax(src["top_z"][w])), 3)]}
OUT.with_suffix(".json").write_text(json.dumps(rep, indent=1, default=float)); print("WROTE", OUT, OUT.with_suffix(".json"))
