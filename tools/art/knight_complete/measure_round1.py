#!/usr/bin/env python3
"""Round-1 checks on exported GLBs (glTF mesh space, +Z forward, +X = knight's left, Y up; 240 game cm per metre).
- carry: WeaponSocket blade axis (+Y) angle at first/last frame vs the approved idle's frame 0 (per grip)
- stance: horizontal ankle distance at first/last frame vs the idle
- strafe/blink travel axis: stance-foot direction angle from lateral, front-view projection
- sword tip per-frame displacement at 30 fps in-game rate (joins)"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(ROOT / "tools/art/knight_complete"))
from normalize_approved import GLB
from measure_locomotion import measure
CM = 240.0
K = ROOT / "Local/CustomuseAssets/Polish20261025/knight"
E = ROOT / "Local/FabRigTesting/Exports"
TIP = np.array([0, 1.0, 0, 1.0])


def pose(g, t):
    w, _ = g.sample(float(t))
    return w


def blade(g, w):
    m = w[g.names["WeaponSocket"]]
    v = m[:3, :3] @ np.array([0, 1.0, 0])
    return v / np.linalg.norm(v)


def ankles(g, w):
    l, r = w[g.names["LeftFoot"]][:3, 3], w[g.names["RightFoot"]][:3, 3]
    return float(np.linalg.norm((l - r)[[0, 2]]))


def ang(a, b):
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


idle = {"one": GLB(K / "IdleOneHand_Blender_v2r4.glb"), "two": GLB(K / "IdleTwoHand_Blender_v2r4.glb")}
canon = {k: (blade(g, pose(g, 0)), ankles(g, pose(g, 0))) for k, g in idle.items()}
rows = {"canonical": {k: {"bladeAxis": [round(float(x), 3) for x in v[0]], "ankleDistanceCm": round(v[1] * CM, 1)} for k, v in canon.items()}, "clips": {}}
names = sorted(p.stem for p in E.glob("Knight_*_v3*.glb") if "Body" not in p.stem) + ["Sourced_RollAttack_v3", "Sourced_RollAttack_v2"]
extra = {"GripToTwoHand_Blender_polish_v2": ("two", K), "GripToOneHand_Blender_polish_v2": ("one", K), "Mixamo_WalkTwoHand_v17": ("two", E), "Mixamo_Walk_v17": ("one", E)}
for n in names + list(extra):
    src = extra[n][1] if n in extra else E
    g = GLB(src / (n + ".glb"))
    grip = extra[n][0] if n in extra else ("two" if "TwoHand" in n else "one")
    T = g.duration()
    w0, w1 = pose(g, 0), pose(g, T)
    b, a = canon[grip]
    r = {"grip": grip, "duration": round(T, 3),
         "startCarryDeg": round(ang(blade(g, w0), b), 1), "endCarryDeg": round(ang(blade(g, w1), b), 1),
         "startAnkleCm": round(ankles(g, w0) * CM, 1), "endAnkleCm": round(ankles(g, w1) * CM, 1)}
    if "Strafe" in n or "Blink" in n or "Backpedal" in n:
        m = measure(src / (n + ".glb"))
        dx, dz = m["bodyDirectionMeshXZ"]
        r["travelAxisOffLateralDeg"] = round(float(np.degrees(np.arctan2(abs(dz), abs(dx)))), 1)
        r["travelSide"] = "left" if dx > 0 else "right"
        r["stanceMedianCmS"] = round(m["rawStanceSpeedMedian"] * CM, 1)
    if "RollAttack" in n:
        rate = 1 / .78
        ts = np.arange(0, T, rate / 30.0)
        tips = [(w[g.names["WeaponSocket"]] @ TIP)[:3] for w in (pose(g, t) for t in ts)]
        steps = np.linalg.norm(np.diff(np.array(tips), axis=0), axis=1) * CM
        k = int(np.argmax(steps))
        r["maxTipStepCmPerFrame30"] = round(float(steps.max()), 1)
        r["maxTipStepAtFrame"] = k
        r["medianTipStepCm"] = round(float(np.median(steps)), 1)
        r["tipStepsAroundJoinCm"] = [round(float(x), 1) for x in steps[20:34]]
    rows["clips"][n] = r
    print(n, r, flush=True)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Local/knight-review-20261028/data/round1-checks.json"
out.write_text(json.dumps(rows, indent=1) + "\n")
