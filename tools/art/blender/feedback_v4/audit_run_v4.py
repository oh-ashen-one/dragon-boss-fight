"""Independent 120 Hz export audit for the Run v4 loop (system python, numpy/scipy).

A COPY of audit_exports.py with a run case added (the shared file has no run job and is
not edited). Generic checks and thresholds are identical to audit_exports.py: duration vs
report, native IK error < .001, limb-length change < .002, held palm drift < .003,
exported joint rotation step < 35 deg. The approved-idle start/end checks do not apply to a
locomotion loop and are replaced by loop checks: first/last world pose identical (< 1e-4),
seam velocity continuity, in-place root (|hips delta| < 1e-4), feet on separate lateral
tracks (minimum LeftFoot.x - RightFoot.x > .10 and knees > .05, glTF X), both feet airborne
at some sample (flight), and torso turn within (1, 20) deg like the other locomotion jobs; for a
loop the turn is measured about the cycle-mean chest orientation (the one-shot jobs measure from
frame 0, which for a loop that starts at a yaw extreme reports the peak-to-peak range instead).
maxTorsoTurnDegrees (from frame 0) is still reported.
Writes only --out (default <out>/run-export-audit.json).
"""
from pathlib import Path
import argparse, importlib.util, json, hashlib, sys
import numpy as np
from scipy.spatial.transform import Rotation
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location("veyr_v4_common", HERE / "common.py"); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--glb"); ap.add_argument("--report"); ap.add_argument("--out")
a = ap.parse_args(); P = cm.params({})
GLB = Path(a.glb) if a.glb else P["export_dir"] / ("RunOneHand_Blender_v" + P["revision"] + ".glb")
REPORT = Path(a.report) if a.report else P["out"] / "run-report.json"
OUT = cm.check_writable(Path(a.out) if a.out else P["out"] / "run-export-audit.json")
spec = importlib.util.spec_from_file_location("eval", cm.REPO / "tools/unreal/normalize_customuse_glb.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
g = m.GLB(GLB); ns = {n.get("name"): i for i, n in enumerate(g.json["nodes"])}; r = json.loads(REPORT.read_text())
dur = max(float(g.accessor(s["input"]).max()) for s in g.json["animations"][0]["samplers"])
first = g.world_matrices(0, 0); last = g.world_matrices(0, dur)
socket = ns["ReviewWeaponSocket"]; contact = np.linalg.solve(first[ns["RightHand"]], first[socket] @ np.array([0, -.075, 0, 1]))
segments = [(ns[s + x], ns[s + y]) for s in ("Left", "Right") for x, y in [("Arm", "ForeArm"), ("ForeArm", "Hand"), ("UpLeg", "Leg"), ("Leg", "Foot")]]
lengths = {k: np.linalg.norm(first[k[0], :3, 3] - first[k[1], :3, 3]) for k in segments}
def rot(w, n):
    x = w[ns[n], :3, :3]; return Rotation.from_matrix(x / np.linalg.norm(x, axis=0))
ts = np.linspace(0, dur, round(dur * 120) + 1); W = [g.world_matrices(0, float(t)) for t in ts]
lengtherr = palm = torso = 0.; footgap = kneegap = 100.; flight = 0; hips = []
groundL = min(w[ns["LeftToeBase"], 1, 3] for w in W); groundR = min(w[ns["RightToeBase"], 1, 3] for w in W)
for w in W:
    assert np.isfinite(w).all()
    for x, y in segments: lengtherr = max(lengtherr, abs(float(np.linalg.norm(w[x, :3, 3] - w[y, :3, 3])) - lengths[x, y]))
    palm = max(palm, float(np.linalg.norm((w[ns["RightHand"]] @ contact - w[socket] @ np.array([0, -.075, 0, 1]))[:3])))
    torso = max(torso, float(np.rad2deg((rot(first, "Spine2").inv() * rot(w, "Spine2")).magnitude())))
    footgap = min(footgap, float(w[ns["LeftFoot"], 0, 3] - w[ns["RightFoot"], 0, 3])); kneegap = min(kneegap, float(w[ns["LeftLeg"], 0, 3] - w[ns["RightLeg"], 0, 3]))
    lifted = lambda s, g0: min(w[ns[s + "ToeBase"], 1, 3], w[ns[s + "Foot"], 1, 3] - (first[ns[s + "Foot"], 1, 3] - first[ns[s + "ToeBase"], 1, 3])) - g0
    if w[ns["LeftToeBase"], 1, 3] - groundL > .01 and w[ns["LeftFoot"], 1, 3] - groundL > .06 and w[ns["RightToeBase"], 1, 3] - groundR > .01 and w[ns["RightFoot"], 1, 3] - groundR > .06: flight += 1
    hips.append(w[ns["Hips"], :3, 3])
meanChest = Rotation.concatenate([rot(w, "Spine2") for w in W[:-1]]).mean()
torsoAmp = max(float(np.rad2deg((meanChest.inv() * rot(w, "Spine2")).magnitude())) for w in W)
jointstep = 0.
for ch in g.json["animations"][0]["channels"]:
    if ch["target"]["path"] == "rotation":
        q = Rotation.from_quat(g.accessor(g.json["animations"][0]["samplers"][ch["sampler"]]["output"])); jointstep = max(jointstep, float(np.rad2deg((q[:-1].inv() * q[1:]).magnitude()).max()))
loopPose = float(np.abs(last[:, :3, 3] - first[:, :3, 3]).max())
v0 = (W[1][:, :3, 3] - W[0][:, :3, 3]); v1 = (W[-1][:, :3, 3] - W[-2][:, :3, 3]); seamVel = float(np.linalg.norm(v0 - v1, axis=1).max())
inner = max(float(np.linalg.norm((W[k + 1][:, :3, 3] - W[k][:, :3, 3]) - (W[k][:, :3, 3] - W[k - 1][:, :3, 3]), axis=1).max()) for k in range(1, len(W) - 1))
root = (last[ns["Hips"], :3, 3] - first[ns["Hips"], :3, 3]).tolist(); hipsArr = np.array(hips)
row = {"job": "run", "glb": str(GLB), "sha256": hashlib.sha256(GLB.read_bytes()).hexdigest(), "reportSHA256": r.get("sha256"), "duration": dur, "nativeIKError": r["nativeIKError"],
       "maxLimbLengthChange": lengtherr, "maxHeldPalmDrift": palm, "maxExportJointStepDegrees": jointstep, "maxTorsoTurnDegrees": torso, "torsoTurnAboutCycleMeanDegrees": torsoAmp,
       "minimumLeftRightFootGap": footgap, "minimumKneeGap": kneegap, "flightSamples120Hz": flight, "rootDelta": root,
       "hipsVerticalRange": float(np.ptp(hipsArr[:, 1])), "loopPoseMaxPositionError": loopPose, "seamVelocityMismatch": seamVel, "maxInCycleSecondDifference": inner,
       "rootMotion": r.get("rootMotion"), "runSpeedUnitsPerSecond": r.get("runSpeedUnitsPerSecond"), "ownerApproved": False}
row["pass"] = bool(abs(dur - r["duration"]) < 1e-5 and r["nativeIKError"] < .001 and lengtherr < .002 and palm < .003 and jointstep < 35
                   and loopPose < 1e-4 and seamVel <= inner and np.linalg.norm(root) < 1e-4 and footgap > .10 and kneegap > .05 and flight > 0 and 1. < torsoAmp < 20.)
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps([row], indent=2) + "\n"); print(json.dumps(row, indent=2)); sys.exit(0 if row["pass"] else 1)
