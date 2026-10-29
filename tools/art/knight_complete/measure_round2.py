#!/usr/bin/env python3
"""Round-2 metrics in glTF mesh space (+Z forward/boss, +X knight's left, Y up), game cm = rig m x 240.
yaw convention: 0 toward +Z, + toward the knight's left (+X).
Per clip: chest yaw (shoulder line), pelvis yaw (hip line), knee-bend yaw (knee offset from hip-ankle line),
travel yaw (stance-toe velocity reversed), hips height vs idle, hand-to-socket distance range (hand slip),
sword-tip step per in-game frame and blade pitch (socket +Y), first/last frame vs idle, end ankle width,
planted toe drift. Usage: measure_round2.py OUT.json RATE_JSON GLB..."""
import json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB
CM = 240.0
TIP = np.array([0, 2.35, 0, 1.0])
K = ROOT / "Local/CustomuseAssets/Polish20261025/knight"


def yaw(v):
    return math.degrees(math.atan2(v[0], v[2]))


def facing_from_left(Lv):
    return np.array([-Lv[2], 0, Lv[0]])


def frame(g, w):
    P = lambda n: w[g.names[n]][:3, 3]
    out = {}
    out["chest"] = yaw(facing_from_left(P("LeftArm") - P("RightArm")))
    out["pelvis"] = yaw(facing_from_left(P("LeftUpLeg") - P("RightUpLeg")))
    knees = []
    for s in ("Left", "Right"):
        h, k, a = P(s + "UpLeg"), P(s + "Leg"), P(s + "Foot")
        d = (a - h) / np.linalg.norm(a - h)
        off = (k - h) - d * ((k - h) @ d)
        off[1] = 0
        if np.linalg.norm(off) > 1e-4:
            knees.append(yaw(off))
    out["knees"] = knees
    out["hipsY"] = P("Hips")[1] * CM
    out["head"] = P("Head") * CM
    out["hand"] = float(np.linalg.norm(P("RightHand") - (w[g.names["WeaponSocket"]] @ np.array([0, 0, 0, 1.0]))[:3]) * CM)
    tip = (w[g.names["WeaponSocket"]] @ TIP)[:3]
    out["tip"] = tip * CM
    b = w[g.names["WeaponSocket"]][:3, :3] @ np.array([0, 1.0, 0]); b /= np.linalg.norm(b)
    out["pitch"] = math.degrees(math.asin(max(-1, min(1, b[1]))))
    out["blade"] = b
    out["toes"] = {s: P(s + "ToeBase") * CM for s in ("Left", "Right")}
    out["ankles"] = float(np.linalg.norm((P("LeftFoot") - P("RightFoot"))[[0, 2]]) * CM)
    return out


def angle(a, b):
    return math.degrees(math.acos(max(-1, min(1, float(a @ b)))))


def wrap(a):
    return (a + 180) % 360 - 180


idle = {}
for gname, f in (("one", "IdleOneHand_Blender_v2r4.glb"), ("two", "IdleTwoHand_Blender_v2r4.glb")):
    g = GLB(K / f); idle[gname] = frame(g, g.sample(0)[0])


def measure(path, rate=1.0, grip=None, root_samples=None, root_rate=120.0, travel=None):
    g = GLB(path); T = g.duration(); grip = grip or ("two" if "TwoHand" in Path(path).stem else "one")
    ts = np.arange(0, T + 1e-9, rate / 30.0)
    F = [frame(g, g.sample(float(t))[0]) for t in ts]
    I = idle[grip]
    r = {"file": Path(path).name, "duration": round(T, 3), "rate": rate, "frames30": len(F)}
    r["chestYaw"] = [round(min(f["chest"] for f in F), 1), round(max(f["chest"] for f in F), 1), round(float(np.mean([f["chest"] for f in F])), 1)]
    r["pelvisYawMean"] = round(float(np.mean([f["pelvis"] for f in F])), 1)
    kn = [k for f in F for k in f["knees"]]
    r["kneeYaw"] = [round(min(kn), 1), round(max(kn), 1)] if kn else None
    r["hipsVsIdleCm"] = [round(min(f["hipsY"] for f in F) - I["hipsY"], 1), round(max(f["hipsY"] for f in F) - I["hipsY"], 1)]
    hs = [f["hand"] for f in F]
    r["handToSocketCm"] = [round(min(hs), 1), round(max(hs), 1)]; r["handSlipCm"] = round(max(hs) - min(hs), 1)
    steps = [float(np.linalg.norm(F[i + 1]["tip"] - F[i]["tip"])) for i in range(len(F) - 1)]
    r["tipStepMaxCmPerFrame"] = round(max(steps), 1) if steps else 0
    r["bladePitch"] = [round(min(f["pitch"] for f in F), 1), round(max(f["pitch"] for f in F), 1)]
    r["idleBladePitch"] = round(I["pitch"], 1)
    r["tipHeightMaxCm"] = round(max(f["tip"][1] for f in F), 1)
    r["carryDegFirstLast"] = [round(angle(F[0]["blade"], I["blade"]), 1), round(angle(F[-1]["blade"], I["blade"]), 1)]
    r["tipOffsetFirstLastCm"] = [round(float(np.linalg.norm(F[0]["tip"] - I["tip"])), 1), round(float(np.linalg.norm(F[-1]["tip"] - I["tip"])), 1)]
    r["anklesFirstLastCm"] = [round(F[0]["ankles"], 1), round(F[-1]["ankles"], 1)]
    hd = [f["head"] - F[0]["head"] for f in F]
    pk = max(hd, key=lambda v: np.linalg.norm(v))
    r["headPeakCm"] = {"total": round(float(np.linalg.norm(pk)), 1), "back(-Z)": round(-pk[2], 1), "left(+X)": round(pk[0], 1), "down": round(-pk[1], 1)}
    # planted toe drift and travel yaw (body-relative stance velocity reversed); root samples add actor motion
    root = None
    if root_samples is not None:
        rs = np.array(root_samples)  # UE mesh-local cm: x=glTF x, y=glTF z, z=glTF y (x100 rig)
        def root_at(t):
            u = min(len(rs) - 1, t * root_rate); i = int(u); j = min(i + 1, len(rs) - 1); a = u - i
            p = rs[i] * (1 - a) + rs[j] * a
            return np.array([p[0], p[2], p[1]]) / 100.0 * CM
        root = root_at
    vel, drift = [], []
    for s in ("Left", "Right"):
        ys = [f["toes"][s][1] for f in F]; floor = min(ys)
        seg = []
        for i, f in enumerate(F):
            planted = f["toes"][s][1] - floor < 2.0  # within 2 game cm
            p = f["toes"][s] + (root(ts[i]) if root else 0)
            if planted:
                seg.append(p)
            elif seg:
                if len(seg) > 1: drift.append(float(np.linalg.norm((seg[-1] - seg[0])[[0, 2]])))
                seg = []
            if planted and i + 1 < len(F) and F[i + 1]["toes"][s][1] - floor < 4.0:
                q = F[i + 1]["toes"][s]
                vel.append((q - f["toes"][s])[[0, 2]])
        if len(seg) > 1: drift.append(float(np.linalg.norm((seg[-1] - seg[0])[[0, 2]])))
    if vel:
        v = -np.mean(vel, axis=0)
        r["travelYaw"] = round(math.degrees(math.atan2(v[0], v[1])), 1) if travel is None else travel
        sp = [float(np.linalg.norm(x)) * 30 / 1.0 for x in vel]
        r["stanceToeSpeedCmS"] = round(float(np.median(sp)), 1)
    r["plantedDriftMaxCm"] = round(max(drift), 1) if drift else None
    if r.get("kneeYaw") and "travelYaw" in r and r["stanceToeSpeedCmS"] > 20:
        t = r["travelYaw"]
        r["kneeVsTravelDeg"] = round(max(abs(wrap(k - t)) for k in kn), 1)
        r["chestVsBossDeg"] = round(max(abs(f["chest"]) for f in F), 1)
    return r


if __name__ == "__main__":
    out = Path(sys.argv[1]); spec = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 and sys.argv[2].endswith(".json") else {}
    files = sys.argv[3:] if spec else sys.argv[2:]
    rows = {}
    for f in files:
        s = spec.get(Path(f).stem, {})
        rows[Path(f).stem] = measure(f, s.get("rate", 1.0), s.get("grip"), s.get("root"), s.get("rootRate", 120.0))
        print(Path(f).stem, json.dumps(rows[Path(f).stem]), flush=True)
    out.write_text(json.dumps({"idle": {k: {"hipsY": v["hipsY"], "pitch": v["pitch"], "ankles": v["ankles"]} for k, v in idle.items()}, "clips": rows}, indent=1) + "\n")
