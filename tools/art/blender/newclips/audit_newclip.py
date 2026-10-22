"""Independent 120 Hz audit of a new clip's exported GLB (system python, numpy/scipy).

A copy of feedback_v4/audit_exports.py adapted per clip (shared file untouched). Generic checks and thresholds
are identical: duration vs report (1e-5), native IK error < .001, limb-length change < .002, held-palm drift < .003,
exported joint rotation step < 35 deg. Clip-specific: the right palm is checked for the whole clip; the left palm only
inside --two-hand windows; start/end pose vs an approved idle (--start-ref/--end-ref, < 1e-4 like the v4 idle checks);
hit-stop windows (--hit-stops) must hold the hilt nearly still (reported speed). Writes only --out.
"""
from pathlib import Path
import argparse, importlib.util, json, hashlib, sys
import numpy as np
from scipy.spatial.transform import Rotation
REPO = Path(__file__).resolve().parents[4]
ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--glb", required=True); ap.add_argument("--report", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--two-hand", default="", help="t0:t1,t0:t1 seconds with both palms on the hilt")
ap.add_argument("--start-ref", default=""); ap.add_argument("--end-ref", default=""); ap.add_argument("--hit-stops", default="")
a = ap.parse_args()
OUT = Path(a.out).resolve(); assert "newclips-20261021" in str(OUT), "writes only into the newclips folder"
spec = importlib.util.spec_from_file_location("eval", REPO / "tools/unreal/normalize_customuse_glb.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
win = lambda txt: [tuple(map(float, w.split(":"))) for w in txt.split(",") if w]
g = m.GLB(Path(a.glb)); ns = {n.get("name"): i for i, n in enumerate(g.json["nodes"])}; r = json.loads(Path(a.report).read_text())
dur = max(float(g.accessor(s["input"]).max()) for s in g.json["animations"][0]["samplers"]); first = g.world_matrices(0, 0); last = g.world_matrices(0, dur)
socket = ns["ReviewWeaponSocket"]; cp = {"Right": np.array([0, -.075, 0, 1]), "Left": np.array([0, -.255, 0, 1])}
two = win(a.two_hand); t_ref = two[0][0] if two else 0.
w0 = g.world_matrices(0, t_ref); contact = {sd: np.linalg.solve(w0[ns[sd + "Hand"]], w0[socket] @ cp[sd]) for sd in ("Left", "Right")}
segments = [(ns[s + x], ns[s + y]) for s in ("Left", "Right") for x, y in [("Arm", "ForeArm"), ("ForeArm", "Hand"), ("UpLeg", "Leg"), ("Leg", "Foot")]]
lengths = {k: np.linalg.norm(first[k[0], :3, 3] - first[k[1], :3, 3]) for k in segments}
lengtherr = 0.; palm = {"Right": 0., "Left": 0.}; ts = np.linspace(0, dur, round(dur * 120) + 1); hilt_pos = []
for t in ts:
    w = g.world_matrices(0, float(t)); assert np.isfinite(w).all()
    for x, y in segments: lengtherr = max(lengtherr, abs(float(np.linalg.norm(w[x, :3, 3] - w[y, :3, 3])) - lengths[x, y]))
    for sd in ("Right", "Left"):
        if sd == "Right" or any(t0 <= t <= t1 for t0, t1 in two):
            palm[sd] = max(palm[sd], float(np.linalg.norm((w[ns[sd + "Hand"]] @ contact[sd] - w[socket] @ cp[sd])[:3])))
    hilt_pos.append(w[socket, :3, 3])
jointstep = 0.
for ch in g.json["animations"][0]["channels"]:
    if ch["target"]["path"] == "rotation":
        q = Rotation.from_quat(g.accessor(g.json["animations"][0]["samplers"][ch["sampler"]]["output"])); jointstep = max(jointstep, float(np.rad2deg((q[:-1].inv() * q[1:]).magnitude()).max()))
checked = ["Hips", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]
def ref_err(path, w):
    if not path: return None
    ref = m.GLB(Path(path)); rn = {n.get("name"): i for i, n in enumerate(ref.json["nodes"])}; rw = ref.world_matrices(0, 0)
    return max(float(np.linalg.norm(w[ns[n], :3, 3] - rw[rn[n], :3, 3])) for n in checked)
hp = np.array(hilt_pos); speed = np.linalg.norm(np.diff(hp, axis=0), axis=1) * 120
hs = []
for t0, t1 in win(a.hit_stops):
    i0, i1 = int(np.ceil(t0 * 120)) + 1, int(np.floor(t1 * 120)) - 1
    before = float(speed[max(0, i0 - 12):i0 - 2].max()) if i0 > 3 else None
    hs.append({"window": [t0, t1], "maxHiltSpeedInHold": float(speed[i0:i1].max()) if i1 > i0 else None, "peakSpeedJustBefore": before})
row = {"glb": a.glb, "sha256": hashlib.sha256(Path(a.glb).read_bytes()).hexdigest(), "reportSHA256": r.get("sha256"), "duration": dur, "nativeIKError": r.get("nativeIKError"),
       "maxLimbLengthChange": lengtherr, "maxRightPalmDrift": palm["Right"], "maxLeftPalmDriftTwoHand": palm["Left"] if two else None, "twoHandWindows": two,
       "maxExportJointStepDegrees": jointstep, "startPoseErrorVsRef": ref_err(a.start_ref, first), "endPoseErrorVsRef": ref_err(a.end_ref, last), "hitStops": hs, "ownerApproved": False}
ok = abs(dur - r["duration"]) < 1e-5 and r["nativeIKError"] < .001 and lengtherr < .002 and palm["Right"] < .003 and (not two or palm["Left"] < .003) and jointstep < 35
for k in ("startPoseErrorVsRef", "endPoseErrorVsRef"):
    if row[k] is not None: ok &= row[k] < 1e-4
row["pass"] = bool(ok)
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(row, indent=2) + "\n"); print(json.dumps(row, indent=2)); sys.exit(0 if ok else 1)
