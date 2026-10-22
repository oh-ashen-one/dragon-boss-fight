"""Per-clip copy of tools/art/blender/remainder/audit_remainder.py checks (same thresholds, never weaker),
for the fable polish A/B versions. Verification only. Usage:
  python3 audit_polish.py --glb NEW.glb --report NEW-report.json --ref APPROVED.glb --kind walk|loop|oneshot|death|guard_two|strafe [--two] --out OUT.json
Extra informative rows: duration vs approved, approved-vs-new endpoint pose error."""
from pathlib import Path
import argparse, importlib.util, json, sys, hashlib
import numpy as np
from scipy.spatial.transform import Rotation
REPO = Path("/Users/midir/veyr-review-fable-20261021")
spec = importlib.util.spec_from_file_location("glb_eval", REPO/"tools/unreal/normalize_customuse_glb.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ap = argparse.ArgumentParser(); ap.add_argument("--glb"); ap.add_argument("--report"); ap.add_argument("--ref"); ap.add_argument("--kind"); ap.add_argument("--two", action="store_true"); ap.add_argument("--out"); ap.add_argument("--loop", action="store_true")
a = ap.parse_args()
def body_indices(g):
    node = next(n for n in g.json["nodes"] if "mesh" in n and "skin" in n)
    return sum(len(g.accessor(p["indices"])) for p in g.json["meshes"][node["mesh"]]["primitives"])
approved = m.GLB(REPO/"tools/asset-review/.asset-cache/review/IdleOneHand_Blender_v1.glb"); expected = body_indices(approved)
g = m.GLB(Path(a.glb)); ref = m.GLB(Path(a.ref)); report = json.loads(Path(a.report).read_text())
ns = {n.get("name"): i for i, n in enumerate(g.json["nodes"])}; rn = {n.get("name"): i for i, n in enumerate(ref.json["nodes"])}
anim = g.json["animations"][0]; dur = max(float(g.accessor(s["input"]).max()) for s in anim["samplers"])
rdur = max(float(ref.accessor(s["input"]).max()) for s in ref.json["animations"][0]["samplers"])
first = g.world_matrices(0, 0); last = g.world_matrices(0, dur)
joints = [ns[n] for n in ("Hips", "LeftFoot", "RightFoot", "LeftHand", "RightHand", "Head")]
loop = float(np.max(np.abs(first[joints] - last[joints])))
lengths = {}; lerr = 0.; palm = {"Right": 0.}; step = 0.
if a.two: palm["Left"] = 0.
sock = ns["ReviewWeaponSocket"]; contact = {sd: np.linalg.solve(first[ns[sd+"Hand"]], first[sock] @ np.array([0, -.075 if sd == "Right" else -.255, 0, 1])) for sd in palm}
for sd in ("Left", "Right"):
    for x, y in [("Arm", "ForeArm"), ("ForeArm", "Hand"), ("UpLeg", "Leg"), ("Leg", "Foot")]:
        na, nb = ns[sd+x], ns[sd+y]; lengths[na, nb] = np.linalg.norm(first[na, :3, 3] - first[nb, :3, 3])
for t in np.linspace(0, dur, round(dur*120)+1):
    w = g.world_matrices(0, float(t)); assert np.isfinite(w).all()
    for (x, y), L in lengths.items(): lerr = max(lerr, abs(float(np.linalg.norm(w[x, :3, 3] - w[y, :3, 3])) - L))
    if a.kind != "death" or t < dur*.28:
        for sd in palm:
            pt = w[sock] @ np.array([0, -.075 if sd == "Right" else -.255, 0, 1]); palm[sd] = max(palm[sd], float(np.linalg.norm((w[ns[sd+"Hand"]] @ contact[sd] - pt)[:3])))
for ch in anim["channels"]:
    if ch["target"]["path"] == "rotation":
        r = Rotation.from_quat(g.accessor(anim["samplers"][ch["sampler"]]["output"])); step = max(step, float(np.rad2deg((r[:-1].inv()*r[1:]).magnitude()).max()))
rf = ref.world_matrices(0, 0); rl = ref.world_matrices(0, rdur)
names = ("Hips", "LeftFoot", "RightFoot", "LeftHand", "RightHand", "Head")
res = {"glb": a.glb, "sha256": hashlib.sha256(Path(a.glb).read_bytes()).hexdigest(), "approvedRef": a.ref, "approvedRefSHA256": hashlib.sha256(Path(a.ref).read_bytes()).hexdigest(),
       "duration": dur, "approvedDuration": rdur, "durationError": abs(dur - report["duration"]), "loopExpected": bool(a.loop), "loopMatrixError": loop,
       "nativeIKError": report.get("nativeIKError"), "maxLimbLengthChange": lerr, "maxPalmDrift": palm, "maxExportRotationStepDegrees": step,
       "bodyTriangleIndices": body_indices(g), "approvedBodyTriangleIndices": expected,
       "startPoseVsApproved": max(float(np.linalg.norm(first[ns[n], :3, 3] - rf[rn[n], :3, 3])) for n in names),
       "endPoseVsApproved": max(float(np.linalg.norm(last[ns[n], :3, 3] - rl[rn[n], :3, 3])) for n in names), "auditHz": 120, "ownerApproved": False}
res["pass"] = bool(res["durationError"] < 1e-5 and (not a.loop or loop < 1e-4) and (report.get("nativeIKError") or 0) < .001 and lerr < .002 and max(palm.values()) < .003 and step < 40 and res["bodyTriangleIndices"] == expected)
Path(a.out).write_text(json.dumps(res, indent=2) + "\n"); print(json.dumps(res, indent=2)); sys.exit(0 if res["pass"] else 1)
