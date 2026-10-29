#!/usr/bin/env python3
"""Hand-to-grip slip during in-game pose transitions (frozen source pose, local-space linear blend, as
UVeyrSingleNodeInstance). OLD: sword at the blended WeaponSocket (root child). NEW (round 2): sword = right hand x
hand-space grip lerped between the source and target clips' own grips. Slip = range of the hand-to-socket distance
across the blend minus the endpoint range. Game cm. Usage: measure_handslip.py OUT.json"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/knight_complete")); sys.path.insert(0, str(ROOT / "tools/art/integration"))
from measure_runstop import locals_at, compose, blend
from normalize_approved import GLB
CM = 240.0
K = ROOT / "Local/CustomuseAssets/Polish20261025/idle-joins/knight"
S = ROOT / "Local/CustomuseAssets/Sourced20261025b/knight"
N2 = ROOT / "Local/CustomuseAssets/Knight20261029r2/knight"
PAIRS = [  # label, source file, source time ('end' or seconds), target file, blend seconds (round 2 engine values)
    ("idle -> strafe left (lock-on enter)", K / "IdleOneHand_Blender_v2r4.glb", 0.0, N2 / "Knight_StrafeLeft_v4c.glb", .30),
    ("strafe right -> idle (lock-on exit)", N2 / "Knight_StrafeRight_v4c.glb", .5, K / "IdleOneHand_Blender_v2r4.glb", .30),
    ("walk -> sprint strafe right", S / "Mixamo_Walk_v17.glb", .4, N2 / "Knight_StrafeRunRight_v4c.glb", .30),
    ("strafe left -> stagger left", N2 / "Knight_StrafeLeft_v4c.glb", .6, N2 / "Knight_StaggerLeft_v4.glb", .10),
    ("idle 2H -> blink right 2H", K / "IdleTwoHand_Blender_v2r4.glb", 0.0, N2 / "Knight_BlinkRightTwoHand_v4c.glb", .10),
    ("blink left end -> idle", N2 / "Knight_BlinkLeft_v4c.glb", "end", K / "IdleOneHand_Blender_v2r4.glb", .10),
    ("roll attack end -> idle", N2 / "Sourced_RollAttack_v4.glb", "end", K / "IdleOneHand_Blender_v2r4.glb", .10),
    ("fab run -> RunStop", S / "Fab_RunOneHand_v18.glb", .28, K / "RunStop_Blender_v1r2.glb", .30),
    ("idle -> light attack (approved pair)", K / "IdleOneHand_Blender_v2r4.glb", 0.0, S / "Mixamo_Attack_v17.glb", .10),
    ("light attack end -> idle (approved pair)", S / "Mixamo_Attack_v17.glb", "end", K / "IdleOneHand_Blender_v2r4.glb", .10),
]


def hand_sock(W):
    h = W["RightHand"]; s = W["WeaponSocket"]
    return h, s


def grip(h, s):
    return np.linalg.inv(h) @ s


rows = {}
for label, fa, ta, fb, B in PAIRS:
    A, Bg = GLB(fa), GLB(fb)
    names = [n for n in Bg.skin_names() if n in A.names]
    t0 = A.duration() if ta == "end" else ta
    la, wa = locals_at(A, t0, names)
    WA = compose(A, la, names, wa); hA, sA = hand_sock(WA); gA = grip(hA, sA)
    old, new = [], []
    for t in np.arange(0, B + 1e-9, 1 / 120):
        lb, wb = locals_at(Bg, min(t, Bg.duration()), names)
        WB = compose(Bg, lb, names, wb); hB, sB = hand_sock(WB); gB = grip(hB, sB)
        a = min(1.0, t / B)
        W = compose(Bg, blend(la, lb, a), names, wb)
        h, s = hand_sock(W)
        old.append(float(np.linalg.norm(s[:3, 3] - h[:3, 3])) * CM)
        gt = gA[:3, 3] * (1 - a) + gB[:3, 3] * a
        new.append(float(np.linalg.norm(h[:3, :3] @ gt)) * CM)
    ends = (float(np.linalg.norm(gA[:3, 3])) * CM, float(np.linalg.norm(gB[:3, 3])) * CM)
    lo, hi = min(ends), max(ends)
    dev = lambda v: max(0.0, max(v) - hi, lo - min(v))
    rows[label] = {"blendSeconds": B, "endpointHandToGripCm": [round(x, 1) for x in ends], "oldExtraSlipCm": round(dev(old), 1), "newExtraSlipCm": round(dev(new), 1),
                   "oldRangeCm": [round(min(old), 1), round(max(old), 1)], "newRangeCm": [round(min(new), 1), round(max(new), 1)]}
    print(label, rows[label], flush=True)
Path(sys.argv[1]).write_text(json.dumps(rows, indent=1) + "\n")
