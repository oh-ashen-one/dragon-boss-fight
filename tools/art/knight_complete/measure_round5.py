#!/usr/bin/env python3
"""Round-5 metrics (2026-10-30): the round-4 critic's RollAttack acceptance spec in bone space, plus the round-4 checks.

Pure CPython + numpy, no Blender, no GPU. Works on the normalized GLB the game imports (glTF mesh space + the plan's root
track = world) or on a raw Blender export (armature space == world for the roll, see build_round4.py). Rendered frames are
the review's: clip t_k = k * rate / 30 (k = 0 .. end), rate 1.282, so critic frame k is exactly rendered frame k.

Critic spec (critique-round4.md, "Biggest gap"), rt-RollAttack:
  feet41_50   side view frames 41-50: no foot moves more than 2 px (~2.9 game cm) horizontally while its sole is within
              8 px (~11.7 cm) of the ground. Measured per foot on the heel (ankle) and toe points: a point is "near the
              ground" when its height above its idle standing height is < 11.7 cm; per rendered frame its horizontal world
              step (full horizontal, not only the side-view axis), and the cumulative drift over each near-ground run.
              FAIL if any per-frame step or run drift > 2.9 cm.
  recovery    per rendered frame the mean world joint distance (all skin joints) to the final pose, from its maximum after
              the strike end (damage window end 1.576 clip s): start = 5 % of the way to the final pose, end = 95 %.
              PASS if end - start >= 8 frames AND no 4 consecutive frames cover more than half of the distance ("snap";
              r4: 0.67). restFrame2cm = first frame within 2 cm (reported).
  sword       blade centroid (BoatGreatsword blade points on WeaponSocket) projected in the review's 3/4 view (ortho,
              360 px over 2.1 rig m, the critic's scale): max px per frame after frame 41. PASS if <= 25 px.
              The side-view value is reported too.
  frontHeel   the lunge front-foot heel drift over frames 31-37 (critic: ~14 cm in r4, ~34 cm in r3) - reported.

Blinks (round-5 foot pass): minimum heel/toe clearance vs the idle heights on visible frames (>= -1 cm), stance slip
from the idle foot spots, push-frame heel/toe heights (toe-off), and every non-leg joint + the blade unchanged vs the
round-4 v6c file (< 0.05 cm).

Usage: measure_round5.py blink GLB [REF_GLB]
       measure_round5.py roll GLB [--plan PLAN.json]   one roll candidate (raw export, or normalized + plan root track)
       measure_round5.py OUT.json                       v030s vs v030r side by side + byte-identical checks (writes OUT)"""
import json, math, sys, hashlib, glob
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(HERE))
import r4_core as core  # noqa: E402
from normalize_approved import GLB  # noqa: E402
CM = 240.0
PX = 360 / 2.1                       # critic px per rig m (review renders: 360 px, ortho 2.1 rig m)
BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
PLAN5 = BASE / "knight-v030s/import-plan-KnightB.json"
PLAN4 = BASE / "knight-v030r/import-plan-KnightB.json"
PLAN3 = BASE / "knight-v030q/import-plan-KnightB.json"
IDLE1 = BASE / "knight/IdleOneHand_Blender_v2r4.glb"
DAMAGE_END = 1.576
NEAR_CM, STEP_CM, SWORD_PX = 8 / PX * CM, 2 / PX * CM, 25.0


def _sword_pts():
    import measure_round3 as m3
    return m3.SWORD


def B(w, g, n):
    return core.to_blender(tuple(float(x) for x in w[g.names[n]][:3, 3]))


_IDLE = {}


def idle_ref():
    """Idle standing heights (rig m) of the ankle and toe joints, and the review's canonical forward (Blender axes)."""
    if not _IDLE:
        g = GLB(IDLE1); w = g.sample(0)[0]
        _IDLE["h"] = {s: {"heel": B(w, g, s + "Foot")[2], "toe": B(w, g, s + "ToeBase")[2]} for s in ("Left", "Right")}
        toes = np.mean([B(w, g, s + "ToeBase") for s in ("Left", "Right")], 0); heels = np.mean([B(w, g, s + "Foot") for s in ("Left", "Right")], 0)
        f = toes - heels; f[2] = 0; _IDLE["fwd"] = f / np.linalg.norm(f)
    return _IDLE


def view_axes(view):
    fwd = idle_ref()["fwd"]; right = np.array([fwd[1], -fwd[0], 0.0])
    off = {"side": right * 3 + [0, 0, .4], "threequarter": fwd * 3 + right * 2 + [0, 0, .5], "front": fwd * 3 + [0, 0, .4]}[view]
    look = -off / np.linalg.norm(off); x = np.cross(look, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(x, look)
    return x, y


def roll_frames(path, rate, root=None):
    """Per rendered frame: world joints (Blender axes, rig m), blade centroid. root = (samplesCm, Hz) or None (raw export)."""
    g = GLB(path); T = g.duration(); S = _sword_pts()
    n = int(T / rate * 30 + 1e-6)
    ts = [k * rate / 30 for k in range(n + 1)]
    if ts[-1] < T - 1e-6:
        ts.append(T)
    rs = np.array(root[0], float) if root else None
    out = []
    for t in ts:
        w = g.sample(float(t))[0]
        r = np.zeros(3)
        if root:
            u = min(len(rs) - 1, t * root[1]); i = int(u); j = min(i + 1, len(rs) - 1); v = rs[i] * (1 - (u - i)) + rs[j] * (u - i)
            r = np.array([v[0] / 100.0, -v[1] / 100.0, 0.0])
        J = {n_: np.array(B(w, g, n_)) + r for n_ in g.skin_names()}
        so = w[g.names["WeaponSocket"]]; bl = (so @ S.T).T[:, :3].mean(0)
        J["#blade"] = np.array(core.to_blender(tuple(bl))) + r
        out.append({"t": t, "J": J})
    return out


def roll_gates(F, rate):
    ref = idle_ref(); res = {"frames": len(F)}
    # --- feet, frames 41-50 (and the whole tail for information)
    feet = {}
    worst_step, worst_run = 0.0, 0.0
    for s in ("Left", "Right"):
        rows = []
        for pt, jn in (("heel", s + "Foot"), ("toe", s + "ToeBase")):
            h0 = ref["h"][s][pt]
            P = [f["J"][jn] for f in F]
            near = [(p[2] - h0) * CM < NEAR_CM for p in P]
            steps = [float(np.hypot(*(P[k][:2] - P[k - 1][:2]))) * CM for k in range(1, len(P))]
            win = range(41, min(51, len(P)))
            bad = [(k, round(steps[k - 1], 2)) for k in win if near[k] and near[k - 1] and steps[k - 1] > STEP_CM]
            mx = max([steps[k - 1] for k in win if near[k] and near[k - 1]], default=0.0)
            # cumulative drift over near-ground runs touching the window
            runs, k = [], 0
            while k < len(P):
                if near[k]:
                    j = k
                    while j + 1 < len(P) and near[j + 1]:
                        j += 1
                    if j >= 41 and k <= 50:
                        a, b = max(k, 40), min(j, 50)
                        d = max(float(np.hypot(*(P[i][:2] - P[a][:2]))) for i in range(a, b + 1)) * CM
                        runs.append({"frames": [k, j], "maxDriftInWindowCm": round(d, 2)})
                    k = j + 1
                else:
                    k += 1
            worst_step = max(worst_step, mx); worst_run = max([worst_run] + [r["maxDriftInWindowCm"] for r in runs])
            rows.append({"point": pt, "maxNearGroundStepCm41_50": round(mx, 2), "badSteps": bad, "nearRuns": runs,
                         "clearanceCm41_50": [round((P[k][2] - h0) * CM, 1) for k in win],
                         "stepCm41_50": [round(steps[k - 1], 1) for k in win]})
        feet[s] = rows
    # whole get-up..end (rendered f15-end, informational): per foot point, frames where it moved > 2.9 cm while near the
    # ground, with (frame, step cm, clearance cm); covers the blend proof's "feet slide in the sourced slash" finding
    allw = {}
    for s in ("Left", "Right"):
        for pt, jn in (("heel", s + "Foot"), ("toe", s + "ToeBase")):
            h0 = ref["h"][s][pt]; P = [f["J"][jn] for f in F]
            allw[s + "." + pt] = [(k, round(float(np.hypot(*(P[k][:2] - P[k - 1][:2]))) * CM, 1), round((P[k][2] - h0) * CM, 1))
                                  for k in range(16, len(P)) if min(P[k][2], P[k - 1][2]) - h0 < NEAR_CM / CM
                                  and float(np.hypot(*(P[k][:2] - P[k - 1][:2]))) * CM > STEP_CM]
    res["feetGetupToEnd"] = {"nearGroundStepsOver2.9cm": allw, "count": sum(len(v) for v in allw.values())}
    res["feet41_50"] = {"perFoot": feet, "maxNearGroundStepCm": round(worst_step, 2), "maxNearGroundRunDriftCm": round(worst_run, 2),
                        "limitCm": round(STEP_CM, 2), "pass": worst_step <= STEP_CM and worst_run <= STEP_CM}
    # --- front heel during the slash, frames 31-37 (lunge foot = the one further toward the boss at frame 34)
    fwd = ref["fwd"]
    k34 = min(34, len(F) - 1)
    front = max(("Left", "Right"), key=lambda s: float(F[k34]["J"][s + "Foot"][:2] @ fwd[:2]))
    hp = [F[k]["J"][front + "Foot"] for k in range(31, min(38, len(F)))]
    res["frontHeel31_37"] = {"foot": front, "driftCm": round(max(float(np.hypot(*(p[:2] - hp[0][:2]))) for p in hp) * CM, 2),
                             "clearanceCm": [round((p[2] - ref["h"][front]["heel"]) * CM, 1) for p in hp]}
    # --- recovery duration
    names = [n for n in F[-1]["J"] if not n.startswith("#")]
    err = [float(np.mean([np.linalg.norm(f["J"][n] - F[-1]["J"][n]) for n in names])) * CM for f in F]
    k0 = int(math.ceil(DAMAGE_END / rate * 30 - 1e-6))
    kp = max(range(k0, len(F)), key=lambda k: err[k]); peak = err[kp]
    start = next(k for k in range(kp, len(F)) if err[k] < .95 * peak)          # 5 % of the way to the idle
    end = next((k for k in range(start, len(F)) if err[k] < .05 * peak), len(F) - 1)   # 95 %
    rest = next((k for k in range(start, len(F)) if err[k] < 2.0), len(F) - 1)
    snap = max(((err[k] - err[k + 4]) / max(peak - err[-1], 1e-6) for k in range(kp, len(F) - 4)), default=0.0)
    res["recovery"] = {"strikeEndFrame": k0, "peakFrame": kp, "startFrame": start, "endFrame": end, "frames": end - start,
                       "restFrame2cm": rest, "snap4FrameShare": round(snap, 2), "meanJointErrCm": [round(e, 1) for e in err[k0 - 1:]],
                       "rule": "frames from 5 % to 95 % of the post-strike mean joint distance to the final pose >= 8 and no 4 frames cover more than half of it",
                       "pass": end - start >= 8 and snap <= .5}
    # --- sword centroid px per frame
    sw = {}
    for v in ("threequarter", "side"):
        x, y = view_axes(v)
        pp = [np.array([f["J"]["#blade"] @ x, f["J"]["#blade"] @ y]) * PX for f in F]
        st = [float(np.linalg.norm(pp[k] - pp[k - 1])) for k in range(1, len(pp))]
        sw[v] = {"pxPerFrame": [round(s_, 1) for s_ in st], "maxAfter41": round(max(st[41:]), 1) if len(st) > 41 else None,
                 "maxStrike": round(max(st[29:37]), 1)}
    res["sword"] = dict(sw, limitPx=SWORD_PX, **{"pass": sw["threequarter"]["maxAfter41"] <= SWORD_PX})
    res["pass"] = res["feet41_50"]["pass"] and res["recovery"]["pass"] and res["sword"]["pass"]
    return res


def blink_gates(path, ref_path=None, hz=120):
    """Blink foot pass (round 5): floor contact and toe-off in bone space (mesh space, the blink's root track is lateral
    and removed). Visible frames only (hidden window 0.207-0.391 clip s excluded). ref_path (round-4 v6c): every non-leg
    joint and the blade must be unchanged."""
    import measure_round3 as m3
    ref = idle_ref()["h"]; g = GLB(path); T = g.duration(); n = int(round(T * hz)); S = m3.SWORD
    gi = GLB(IDLE1 if "TwoHand" not in Path(path).name else BASE / "knight/IdleTwoHand_Blender_v2r4.glb"); wi = gi.sample(0)[0]
    idle_xy = {s + p: np.array(B(wi, gi, s + j)[:2]) for s in ("Left", "Right") for p, j in (("heel", "Foot"), ("toe", "ToeBase"))}
    gr = GLB(ref_path) if ref_path else None
    LEGS = {s + j for s in ("Left", "Right") for j in ("UpLeg", "Leg", "Foot", "ToeBase", "Toe_End", "ToeEnd")}
    out = {"minClearanceCm": {}, "maxStanceSlipCm": {}, "frames": n + 1}
    mins, slips, push, diff = {}, {}, {}, 0.0
    for i in range(n + 1):
        t = i * T / n; w = g.sample(t)[0]
        vis = not (core.HIDDEN[0] <= t < core.HIDDEN[1])
        for s in ("Left", "Right"):
            for p, j in (("heel", "Foot"), ("toe", "ToeBase")):
                q = B(w, g, s + j); k = s + "." + p
                if vis:
                    mins[k] = min(mins.get(k, 1e9), (q[2] - ref[s][p]) * CM)
                    if p == "toe" or q[2] - ref[s][p] < 1.0 / CM:
                        slips[k] = max(slips.get(k, 0.0), float(np.linalg.norm(np.array(q[:2]) - idle_xy[s + p])) * CM)
                if .14 <= t <= .207:
                    push.setdefault(k, []).append(round((q[2] - ref[s][p]) * CM, 1))
        if gr is not None:
            wr = gr.sample(t)[0]
            for nm in g.skin_names():
                if nm in LEGS or nm.startswith(("Left", "Right")) and any(x in nm for x in ("UpLeg", "Leg", "Foot", "Toe")):
                    continue
                diff = max(diff, float(np.linalg.norm(w[g.names[nm]][:3, 3] - wr[gr.names[nm]][:3, 3])) * CM)
            so, sr = w[g.names["WeaponSocket"]], wr[gr.names["WeaponSocket"]]
            diff = max(diff, float(np.abs((so @ S.T) - (sr @ S.T)).max()) * CM)
    out["minClearanceCm"] = {k: round(v, 2) for k, v in mins.items()}
    out["maxStanceSlipCm"] = {k: round(v, 2) for k, v in slips.items()}
    out["pushHeightsCm_0.14_0.207"] = {k: (min(v), max(v)) for k, v in push.items()}
    if gr is not None:
        out["nonLegJointsAndBladeMaxDiffVsRefCm"] = round(diff, 3)
    out["pass"] = min(mins.values()) >= -1.0 and (gr is None or diff < .05)
    return out


def summary(r):
    return {"feet41_50": {k: r["feet41_50"][k] for k in ("maxNearGroundStepCm", "maxNearGroundRunDriftCm", "limitCm", "pass")},
            "recovery": {k: r["recovery"][k] for k in ("startFrame", "endFrame", "frames", "snap4FrameShare", "pass")},
            "sword3q": {"maxAfter41Px": r["sword"]["threequarter"]["maxAfter41"], "strikePeakPx": r["sword"]["threequarter"]["maxStrike"], "pass": r["sword"]["pass"]},
            "swordSideMaxAfter41Px": r["sword"]["side"]["maxAfter41"], "frontHeel31_37Cm": r["frontHeel31_37"]["driftCm"], "PASS": r["pass"]}


def plan_clip(plan, name):
    return next(c for c in json.loads(Path(plan).read_text())["clips"] if c["name"] == name)


def measure_plan_roll(plan):
    c = plan_clip(plan, "RollAttack")
    return roll_gates(roll_frames(c["file"], c["gameplay_play_rate"], (c["root_translation_samples_cm"], c["root_sample_rate"])), c["gameplay_play_rate"])


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(out):
    import measure_round4 as m4
    import measure_round3 as m3
    P5 = {c["name"]: c for c in json.loads(PLAN5.read_text())["clips"]}
    P4 = {c["name"]: c for c in json.loads(PLAN4.read_text())["clips"]}
    m4.FR4, m4.FR3 = ROOT / "Local/knight-review-20261028/r5/frames", ROOT / "Local/knight-review-20261028/r4/frames"
    rows = {}
    for name in P5:
        rows[name] = {}
        for lab, P in (("r5", P5), ("r4", P4)):
            cc = P[name]; r = m3.measure(cc, lab)
            if name == "RollAttack":
                r["rollWorld"] = m4.roll_world(cc)
                r["rollGatesR5"] = roll_gates(roll_frames(cc["file"], cc["gameplay_play_rate"], (cc["root_translation_samples_cm"], cc["root_sample_rate"])),
                                              cc["gameplay_play_rate"])
            if name.startswith("Blink"):
                r["blinkTail"] = m4.blink_tail(cc, m3, None)
                r["blinkFeetR5"] = blink_gates(cc["file"], P4[name]["file"] if lab == "r5" else None)
            rows[name][lab] = r
        print(name, json.dumps({lab: summary(rows[name][lab]["rollGatesR5"]) if name == "RollAttack" else
                                {k: rows[name][lab]["blinkFeetR5"][k] for k in ("minClearanceCm", "pushHeightsCm_0.14_0.207", "pass")} for lab in rows[name]}), flush=True)
    # inherited clips: every v030r clip not re-authored in v030s must be byte-identical (plan sha == file sha == v030r)
    inh = {}
    for name, c in P4.items():
        if name in P5:
            continue
        inh[name] = {"v030r": c["sha256"], "fileNow": sha(c["file"]) if Path(c["file"]).exists() else None}
        inh[name]["identical"] = inh[name]["v030r"] == inh[name]["fileNow"]
    ident = {}
    before = ROOT / "docs/knight-complete-20261028/data/round3-protected-sha256-before.txt"
    for line in before.read_text().splitlines():
        h, p = line.split(None, 1); now = sha(ROOT / p) if (ROOT / p).exists() else None
        ident[p] = {"before": h, "after": now, "identical": h == now}
    # v030q kept clips (StrafeRight(2H), backpedals): files unchanged since round 3
    kept = {}
    for c in json.loads(PLAN3.read_text())["clips"]:
        if c["name"] in m4.KEPT_R3:
            kept[c["name"]] = {"v030q": c["sha256"], "fileNow": sha(c["file"]), "identical": c["sha256"] == sha(c["file"])}
    doc = {"definitions": __doc__, "clips": rows, "inheritedFromV030r": inh, "keptRound3": kept, "byteIdentical": ident,
           "byteIdenticalAll": all(v["identical"] for v in ident.values()),
           "inheritedFromV030rIdenticalAll": all(v["identical"] for v in inh.values()),
           "keptRound3IdenticalAll": all(v["identical"] for v in kept.values())}
    Path(out).write_text(json.dumps(doc, indent=1, default=float) + "\n")
    print("WROTE", out, "byteIdenticalAll", doc["byteIdenticalAll"], "inheritedFromV030rIdenticalAll", doc["inheritedFromV030rIdenticalAll"],
          "keptRound3IdenticalAll", doc["keptRound3IdenticalAll"])


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "blink":
        r = blink_gates(a[1], a[2] if len(a) > 2 else None)
        print("BLINK_GATES", Path(a[1]).name, json.dumps(r)); sys.exit(0 if r["pass"] else 2)
    if a[0] == "roll":
        if "--plan" in a:
            r = measure_plan_roll(a[a.index("--plan") + 1])
        else:
            r = roll_gates(roll_frames(a[1], core.ROLL_RATE, None), core.ROLL_RATE)
        if "--full" in a:
            print(json.dumps(r, indent=1))
        print("ROLL_GATES", json.dumps(summary(r)))
        sys.exit(0 if r["pass"] else 2)
    main(a[0])
