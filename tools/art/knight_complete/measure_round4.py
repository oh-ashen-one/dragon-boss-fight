#!/usr/bin/env python3
"""Round-4 metrics on the normalized GLBs the game imports (glTF mesh space: +Z boss, +X knight's left, Y up; game cm =
rig m x 240; frames = 30 fps of game time at the in-game rate). Pure CPython + numpy (+ ffmpeg only to decode review MP4s
that already exist); no Blender, no GPU.

Every round-3 metric (measure_round3.measure) plus:
  pelvisVsBoss (bone transforms, not pixels), per frame of one cycle at 120 Hz:
    hipLineYaw      facing of the LeftUpLeg-RightUpLeg line (what round 3 called "pelvis"; 41-47 deg on the r3 sprints)
    hipsBoneYaw     the Hips bone's rotation relative to the idle Hips, applied to the idle forward
    legPlaneYaw     folded yaw of each leg's hip-knee-ankle plane (0 = the leg swings toward/away from the boss, 90 =
                    frontal plane); mean over the swing frames (swing weight > 0.5) and at the full kick (max knee bend)
    shinSideOverFront  the full-kick shin's horizontal span seen from the side (|boss axis|) over from the front (|x|)
    visualTwist     chest yaw minus the leg plane (what a viewer reads as "legs vs shoulders")
  Round 3 reported 45 deg because it measured the hip-joint LINE; the critic saw the LEGS: the r3 swing paths stayed
  travel-aligned, so the leg plane sat 48-68 deg off the boss and the shin spanned 0.35-0.47x side/front (round 2: ~90).
  Targets (critic): leg plane within ~45-52 deg of the boss, side/front >= 0.6.
  seamLossless    the critic's seam method (shift-compensated MAD on the knight crop, 3 bands + all, per panel) on the
                  lossless render PNGs (Local/knight-review-20261028/{r4,r3}/frames)
  seamPixelsIntra measure_round3.pixels on the all-intra review MP4s (serve-round4/media)
  blinkTail       bone pose steps of the last rendered frames (frozen = < 0.03 cm mean joint step; the idle itself moves
                  0.07-0.15 cm per frame), last-vs-idle-frame-0,
                  and the same from the lossless front PNGs (changed pixels > 8 levels)
  rollWorld       hips (pose + plan root track) world speed per rendered frame (game cm/frame), the join (clip 1.0 s)
                  profile, the last 3 frames, contact runs after the get-up (local floor) with the max world slide inside
                  each run, minimum toe-joint height vs the idle's 3.3 cm
  byteIdentical   protected 30 files vs round3-protected-sha256-before.txt; kept round-3 clips' sha in v030r == v030q

Usage: measure_round4.py OUT.json        measure v030r (round 4) and v030q (round 3) side by side
       measure_round4.py retime-args     stance speed of the authored _v6c sprint cycles (Exports) -> retime stage args
       measure_round4.py predict         CPU predictions of the sprint swing-plane fix and the roll join/settle on the r3 data"""
import json, math, sys, hashlib, glob
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(HERE))
import r4_core as core  # noqa: E402
from normalize_approved import GLB  # noqa: E402
CM = 240.0
BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
PLAN4 = BASE / "knight-v030r/import-plan-KnightB.json"
PLAN3 = BASE / "knight-v030q/import-plan-KnightB.json"
EXP = ROOT / "Local/FabRigTesting/Exports"
REV = ROOT / "Local/knight-review-20261028"
FR4, FR3, MEDIA4 = REV / "r4/frames", REV / "r3/frames", REV / "serve-round4/media"
KEPT_R3 = ["StrafeRight", "StrafeRightTwoHand", "BackpedalGuard", "BackpedalGuardTwoHand"]
IDLE_FILES = {"one": BASE / "knight/IdleOneHand_Blender_v2r4.glb", "two": BASE / "knight/IdleTwoHand_Blender_v2r4.glb"}
LEGJ = ("UpLeg", "Leg", "Foot", "ToeBase")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rate_of(c):
    if c["loop"]:
        n = c["nominal_speed_cm_per_second"]
        cap = 100.0 if c["name"].startswith("Backpedal") else (min(580, n * 1.1) if "Run" in c["name"] else min(240, n * 1.2))
        return cap / n
    return c["gameplay_play_rate"]


def B(w, g, n):
    """Joint n of world matrices w in Blender armature axes (rig metres)."""
    return core.to_blender(tuple(float(x) for x in w[g.names[n]][:3, 3]))


def gyaw(v):
    """glTF-space yaw (deg): 0 = boss (+Z), + toward the knight's left (+X)."""
    return math.degrees(math.atan2(v[0], v[2]))


_IDLE_HIPS = {}


def idle_hips_rot(grip):
    if grip not in _IDLE_HIPS:
        g = GLB(IDLE_FILES[grip]); w = g.sample(0)[0]; _IDLE_HIPS[grip] = np.array(w[g.names["Hips"]][:3, :3], float)
    return _IDLE_HIPS[grip]


# ------------------------------------------------------------------------------------------------ pelvis vs boss
def pelvis_vs_boss(path, grip, hz=120):
    g = GLB(path); T = g.duration(); n = max(8, int(round(T * hz))); ts = [i * T / n for i in range(n)]
    R0 = idle_hips_rot(grip); f0 = R0.T @ np.array([0, 0, 1.0])
    hip, bone, chest, J = [], [], [], {s: {j: [] for j in LEGJ} for s in ("Left", "Right")}
    for t in ts:
        w = g.sample(float(t))[0]
        hip.append(core.facing_of_line(B(w, g, "LeftUpLeg"), B(w, g, "RightUpLeg")))
        chest.append(core.facing_of_line(B(w, g, "LeftArm"), B(w, g, "RightArm")))
        R = np.array(w[g.names["Hips"]][:3, :3], float); bone.append(gyaw(R @ f0))
        for s in J:
            for j in LEGJ:
                J[s][j].append(B(w, g, s + j))
    out = {"frames120": n, "hipLineYaw": [round(min(hip), 1), round(max(hip), 1), round(float(np.mean(hip)), 1)],
           "hipsBoneYaw": [round(min(bone), 1), round(max(bone), 1), round(float(np.mean(bone)), 1)],
           "chestYawMean": round(float(np.mean(chest)), 1), "legs": {}}
    planes_sw = []
    for s in J:
        rows = [core.leg_plane(J[s]["UpLeg"][i], J[s]["Leg"][i], J[s]["Foot"][i]) for i in range(n)]
        w = core.swing_weights([p[2] for p in J[s]["Foot"]], [p[2] for p in J[s]["ToeBase"]])
        sw = [r["planeYaw"] for r, x in zip(rows, w) if x > .5 and not math.isnan(r["planeYaw"])]
        k = core.full_kick(rows)
        out["legs"][s] = {"swingPlaneYawMeanAbs": round(float(np.mean(np.abs(sw))), 1) if sw else None,
                          "swingPlaneYawRange": [round(min(sw), 1), round(max(sw), 1)] if sw else None, "swingFrames": len(sw), "fullKick": k}
        planes_sw += sw
    lp = float(np.mean(np.abs(planes_sw))) if planes_sw else float("nan")
    out["legPlaneOffBossDeg"] = round(lp, 1)
    out["visualTwistDeg"] = round(abs(abs(out["chestYawMean"]) - lp), 1)
    ratios = [out["legs"][s]["fullKick"]["sideOverFront"] for s in out["legs"]]
    planes_k = [abs(out["legs"][s]["fullKick"]["planeYaw"]) for s in out["legs"]]
    out["targets"] = {"legPlaneWithin52": lp <= 52.0 and max(planes_k) <= 52.0, "sideOverFrontAtLeast0.6": min(ratios) >= .6,
                      "hipLineWithin45": abs(out["hipLineYaw"][2]) <= 45.5}
    return out


# ------------------------------------------------------------------------------------------------ critic seam (lossless)
def _load_png(folder, views):
    from PIL import Image
    n = len(glob.glob(str(folder / (views[0] + "_*.png")))); A = []
    for i in range(n):
        A.append(np.concatenate([np.asarray(Image.open(folder / ("%s_%04d.png" % (v, i))).convert("RGB")).astype(np.float32) for v in views], 1))
    return A


def _crop_box(A, p):
    U = np.zeros((360, 360), bool)
    for a in A:
        pan = a[:, p * 360:(p + 1) * 360]; L = pan.mean(2); hz = int(np.argmax(L[:, 3] < 70))
        U[:hz] |= np.abs(pan[:hz] - pan[2, 3]).sum(2) > 24
    ys, xs = np.nonzero(U); x0, x1 = np.percentile(xs, [1, 99]).astype(int)
    return ys.min(), x0, x1


def _best(a, b, R=6):
    bv, bs = 1e9, (0, 0); H, W = a.shape[:2]
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            v = np.abs(a[R + dy:H - R + dy, R + dx:W - R + dx] - b[R:H - R, R:W - R]).mean()
            if v < bv:
                bv, bs = v, (dx, dy)
    return bs


def _bandd(a, b, s, R=6, bands=((0, .4), (.4, .65), (.65, 1), (0, 1))):
    dx, dy = s; H, W = a.shape[:2]; D = np.abs(a[R + dy:H - R + dy, R + dx:W - R + dx] - b[R:H - R, R:W - R]).mean(2); h = D.shape[0]
    return [float(D[int(f0 * h):int(f1 * h)].mean()) for f0, f1 in bands]


def seam_lossless(folder):
    """Critic's method (round-3 critique): per panel, knight crop (union silhouette + margins, to 95 px below the
    horizon), each consecutive step shift-compensated (+-6 px), bands head/chest (0-40%), hips/sword (40-65%), legs
    (65-100%), all; seam = last->first step; reported as seam/mean (and legs seam, mean, max)."""
    views = ["front", "side", "threequarter"]
    if not (folder / "front_0000.png").exists():
        return None
    A = _load_png(folder, views); res = {}
    for p, v in enumerate(views):
        y0, x0, x1 = _crop_box(A, p); L0 = A[0][:, p * 360:(p + 1) * 360].mean(2); hz = int(np.argmax(L0[:, 3] < 70))
        y1 = min(359, hz + 95); x0 = max(0, x0 - 40); x1 = min(360, x1 + 40); y0 = max(0, y0 - 8)
        C = [a[y0:y1, p * 360 + x0:p * 360 + x1] for a in A]; n = len(C)
        S = np.array([_bandd(C[i], C[i + 1], _best(C[i].mean(2), C[i + 1].mean(2))) for i in range(n - 1)])
        sm = _bandd(C[-1], C[0], _best(C[-1].mean(2), C[0].mean(2)))
        res[v] = {"allSeamOverMean": round(sm[3] / S[:, 3].mean(), 2), "legsSeamOverMean": round(sm[2] / S[:, 2].mean(), 2),
                  "legs": [round(sm[2], 2), round(float(S[:, 2].mean()), 2), round(float(S[:, 2].max()), 2)],
                  "headChestSeamOverMean": round(sm[0] / S[:, 0].mean(), 2), "hipsSwordSeamOverMean": round(sm[1] / S[:, 1].mean(), 2)}
    res["worstAllSeamOverMean"] = max(res[v]["allSeamOverMean"] for v in views)
    return res


# ------------------------------------------------------------------------------------------------ blink tail
def blink_tail(c, m3, idle_png):
    g = GLB(c["file"]); T = g.duration(); rate = rate_of(c); ts = m3.times(T, rate, False)
    F = [m3.frame(g, g.sample(float(t))[0]) for t in ts]
    st = [m3.pose_dist(F[i + 1], F[i])[1] for i in range(len(F) - 1)]
    frozen = 0
    for x in reversed(st):
        if x >= .03:   # the idle's own motion is 0.07-0.15 cm mean joint step per frame; r3's frozen tail is 0.00
            break
        frozen += 1
    I = m3.IDLE["two" if "TwoHand" in c["name"] else "one"]
    common = [n for n in I["P"] if n in F[-1]["P"]]
    out = {"meanJointStepCmLast5": [round(x, 3) for x in st[-5:]], "frozenTrailingSteps": frozen,
           "lastVsIdleFrame0Cm": dict(zip(("max", "mean"), (round(x, 2) for x in m3.pose_dist(F[-1], I, common))))}
    return out


def png_steps(folder, idle_folder=None):
    from PIL import Image
    if not (folder / "front_0000.png").exists():
        return None
    n = len(glob.glob(str(folder / "front_*.png")))
    fr = lambda d, i: np.asarray(Image.open(d / ("front_%04d.png" % i)).convert("L")).astype(np.float32)
    steps = [int((np.abs(fr(folder, i + 1) - fr(folder, i)) > 8).sum()) for i in range(n - 1)]
    out = {"changedPxPerStep": steps, "frozenTrailingSteps": next((k for k, x in enumerate(reversed(steps)) if x >= 50), len(steps))}
    if idle_folder and (idle_folder / "front_0000.png").exists():
        out["lastToIdleFrame0ChangedPx"] = int((np.abs(fr(idle_folder, 0) - fr(folder, n - 1)) > 8).sum())
        ni = len(glob.glob(str(idle_folder / "front_*.png")))
        out["idleOwnStepsChangedPx"] = [int((np.abs(fr(idle_folder, i + 1) - fr(idle_folder, i)) > 8).sum()) for i in range(min(ni - 1, 6))]
    return out


# ------------------------------------------------------------------------------------------------ roll attack in world space
def roll_world(c, hz=120):
    g = GLB(c["file"]); T = g.duration(); rate = rate_of(c)
    rs = np.array(c["root_translation_samples_cm"], float); rr = c["root_sample_rate"]

    def root(t):  # plan samples are mesh cm (x = knight's left, y = boss); -> Blender axes, rig m
        u = min(len(rs) - 1, t * rr); i = int(u); j = min(i + 1, len(rs) - 1); v = rs[i] * (1 - (u - i)) + rs[j] * (u - i)
        return (v[0] / 100.0, -v[1] / 100.0, 0.0)

    def world(t):
        w = g.sample(float(t))[0]; r = root(t)
        return {n: core.add(B(w, g, n), r) for n in ("Hips", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")}
    rt = [min(T, i * rate / 30.0) for i in range(int(T / rate * 30) + 1)]
    if rt[-1] < T - 1e-6:
        rt.append(T)
    W = [world(t) for t in rt]
    sp = [round(math.hypot(*core.sub(b["Hips"], a["Hips"])[:2]) * CM, 2) for a, b in zip(W, W[1:])]
    j = int(core.JOIN_T / rate * 30)
    out = {"rate": round(rate, 4), "renderedFrames": len(W), "hipsWorldSpeedCmPerFrame": sp,
           "join": {"frame": j, "speeds": sp[max(0, j - 2):j + 5]}, "last3": sp[-3:]}
    jw = sp[max(0, j - 2):j + 6]
    out["join"]["maxSpeedDropPerFrame"] = round(max((a - b for a, b in zip(jw, jw[1:])), default=0.0), 2)  # r3: 9.4 (13.7 -> 4.3)
    # contacts after the get-up at 120 Hz in world space (local floor), slide per rendered frame inside each run
    g0 = int(core.GETUP_T * hz); nT = int(T * hz); fps_r = 30.0 / rate
    Wh = [world(i / hz) for i in range(g0, nT + 1)]
    out["contacts"] = {}
    for s in ("Left", "Right"):
        pts = [x[s + "Foot"] for x in Wh]; tz = [x[s + "ToeBase"][2] for x in Wh]
        runs = core.contact_runs(pts, tz, None, hz)
        rows = []
        for a, b in runs:
            sl = max((math.hypot(*core.sub(pts[k + 1], pts[k])[:2]) for k in range(a, b)), default=0.0) * CM * hz / fps_r
            rows.append({"clipS": [round((a + g0) / hz, 3), round((b + g0) / hz, 3)], "maxSlideCmPerRenderedFrame": round(sl, 2),
                         "drift": round(math.hypot(*core.sub(pts[b], pts[a])[:2]) * CM, 2)})
        out["contacts"][s] = {"runs": rows, "minToeHeightCm": round(min(tz) * CM, 2)}
    out["targets"] = {"last3Below1cm": max(out["last3"]) < 1.0, "joinRampDropBelow6cm": out["join"]["maxSpeedDropPerFrame"] < 6.0,
                      "contactSlideBelow1cm": all(r["maxSlideCmPerRenderedFrame"] < 1.0 for s in out["contacts"].values() for r in s["runs"]),
                      "toesAtLeastIdle": all(s["minToeHeightCm"] >= core.TOE_FLOOR_CM - .3 for s in out["contacts"].values())}
    return out


# ------------------------------------------------------------------------------------------------ modes
def retime_args():
    sys.path.insert(0, str(HERE)); from measure_locomotion import measure as stance  # noqa: E402
    P3 = {c["name"]: c for c in json.loads(PLAN3.read_text())["clips"]}; args = []
    for side in ("Left", "Right"):
        for grip in ("", "TwoHand"):
            key = "StrafeRun%s%s" % (side, grip); src = EXP / ("Knight_%s_v6c.glb" % key)
            if not src.exists():
                raise SystemExit("missing %s (run build_round4 cycles first)" % src)
            have = stance(src)["rawStanceSpeedMedian"] * CM
            args.append("Knight_%s_v6r=%s@%.2f" % (key, P3[key]["nominal_speed_cm_per_second"], have))
    print(" ".join(args))


def predict():
    """CPU predictions on the round-3 data (no Blender): sprint swing-plane fix (r4_core math, v030q _v5r clips) and the
    roll join ramp + settle (v030q RollAttack + its root track)."""
    P3 = {c["name"]: c for c in json.loads(PLAN3.read_text())["clips"]}
    for key in ("StrafeRunLeft", "StrafeRunRight", "StrafeRunLeftTwoHand", "StrafeRunRightTwoHand"):
        g = GLB(P3[key]["file"]); T = g.duration(); n = int(round(T * 120)); J = {s: {j: [] for j in LEGJ} for s in ("Left", "Right")}; hip = []
        for i in range(n):
            w = g.sample(i * T / n)[0]
            hip.append(core.facing_of_line(B(w, g, "LeftUpLeg"), B(w, g, "RightUpLeg")))
            for s in J:
                for jn in LEGJ:
                    J[s][jn].append(B(w, g, s + jn))
        pm = float(np.mean(hip)); sgn = 1.0 if pm > 0 else -1.0
        travel = core.travel_yaw({s: J[s]["Foot"] for s in J}, 120) or sgn * 90
        theta = (pm - travel) * core.SWING_GAIN; res = {}
        for s in J:
            H, K, A, Tq = (J[s][x] for x in LEGJ)
            w = core.swing_weights([p[2] for p in A], [p[2] for p in Tq])
            a = float(np.mean([core.norm(core.sub(K[i], H[i])) for i in range(n)])); b = float(np.mean([core.norm(core.sub(A[i], K[i])) for i in range(n)]))
            rows, shift = [], 0.0
            for i in range(n):
                A2 = core.rot_vertical(A[i], H[i], theta * w[i]); r = math.radians(hip[i])
                pf = (math.sin(r), -math.cos(r), 0.0)  # pelvis forward (yaw convention: 0 = -Y boss, + = +X left)
                src = core.unit(core.sub(K[i], H[i])); k = core.POLE_STANCE + (core.POLE_SWING - core.POLE_STANCE) * w[i]
                K2 = core.two_bone_knee(H[i], A2, a, b, core.add(core.mul(src, 1 - k), core.mul(pf, k)))
                rows.append(core.leg_plane(H[i], K2, A2))
                if w[i] < .02:
                    shift = max(shift, core.norm(core.sub(A2, A[i])) * CM)
            res[s] = {"fullKick": core.full_kick(rows), "stanceShiftMaxCm": round(shift, 2)}
        print("PREDICT sprint", key, "hipLine %.1f travel %.1f theta %.1f" % (pm, travel, theta), json.dumps(res), flush=True)
    c = P3["RollAttack"]; r = roll_world(c)
    print("R3 roll measured: join", r["join"], "last3", r["last3"], json.dumps(r["contacts"]), flush=True)
    predict_roll(c)


def predict_roll(c, hz=300):
    """The rollattack stage's hips correction (reprofile over JOIN_DECEL_S, carry, Hermite settle, hold) and contact
    targets, applied to the r3 world hips/feet paths: predicted world speed per rendered frame and contact slide."""
    g = GLB(c["file"]); T = g.duration(); NF = int(round(T * hz)) + 1
    rs = np.array(c["root_translation_samples_cm"], float); rr = c["root_sample_rate"]

    def root(t):
        u = min(len(rs) - 1, t * rr); i = int(u); j = min(i + 1, len(rs) - 1); v = rs[i] * (1 - (u - i)) + rs[j] * (u - i)
        return (v[0] / 100.0, -v[1] / 100.0, 0.0)
    HXY, F, TZ = [], {"Left": [], "Right": []}, {"Left": [], "Right": []}
    for f in range(NF):
        t = f / hz; w = g.sample(t)[0]; r = root(t); h = core.add(B(w, g, "Hips"), r); HXY.append((h[0], h[1], 0.0))
        for s in F:
            F[s].append(core.add(B(w, g, s + "Foot"), r)); TZ[s].append(B(w, g, s + "ToeBase")[2])
    J0 = int(round(core.JOIN_T * hz)); J1 = J0 + int(round(core.JOIN_DECEL_S * hz)); o = int(round(core.OUTRO_START * hz))
    FS = NF - 1 - int(round(core.SETTLE_HOLD_S * hz))
    newj, delta = core.reprofile_velocity(HXY, J0, J1); corr = [(0.0, 0.0, 0.0)] * NF
    for k, f in enumerate(range(J0, J1 + 1)):
        corr[f] = core.sub(newj[k], HXY[f])
    for f in range(J1 + 1, o + 1):
        corr[f] = delta
    pa, pb = core.add(HXY[o], corr[o]), core.add(HXY[o - 1], corr[o - 1])
    st = core.settle_path(pa, core.sub(pa, pb), HXY[NF - 1], FS - o)
    for k, f in enumerate(range(o, FS + 1)):
        corr[f] = core.sub(st[k], HXY[f])
    for f in range(FS + 1, NF):
        corr[f] = core.sub(HXY[NF - 1], HXY[f])
    rate = rate_of(c); fr = [min(NF - 1, int(round(i / 30 * rate * hz))) for i in range(int(T / rate * 30) + 2)]
    vel = lambda P: [round(math.hypot(*core.sub(P[b], P[a])[:2]) * CM, 1) for a, b in zip(fr, fr[1:])]
    v0, v1 = vel(HXY), vel([core.add(HXY[f], corr[f]) for f in range(NF)])
    j = int(core.JOIN_T / rate * 30)
    print("PREDICT roll join offset carried to the outro (game cm):", [round(float(x) * CM, 1) for x in delta[:2]])
    print("PREDICT roll world hips speed per rendered frame r3 -> r4: join", list(zip(v0[j - 1:j + 5], v1[j - 1:j + 5])), "last 4", list(zip(v0[-4:], v1[-4:])))
    G0 = int(round(core.GETUP_T * hz)); fps_r = 30.0 / rate
    for s in F:
        seg = [F[s][f] for f in range(G0, o + 1)]; tz = [TZ[s][f] for f in range(G0, o + 1)]
        runs = core.contact_runs(seg, tz, None, hz)
        tg = core.contact_targets([core.add(F[s][f], corr[f]) for f in range(G0, o + 1)], runs, core.LIFT_MIN_CM / CM, lock_z=False)
        rows = []
        for a, b in runs:
            sl = lambda P: max(math.hypot(*core.sub(P[k + 1], P[k])[:2]) for k in range(a, b)) * CM * hz / fps_r
            rows.append({"clipS": [round((a + G0) / hz, 3), round((b + G0) / hz, 3)], "slideR3": round(sl(seg), 2), "slideR4": round(sl(tg), 2)})
        print("PREDICT roll contacts", s, "toe min %.1f cm (idle %.1f)" % (min(tz) * CM, core.TOE_FLOOR_CM), json.dumps(rows), flush=True)


def main(out):
    import measure_round3 as m3
    P4 = {c["name"]: c for c in json.loads(PLAN4.read_text())["clips"]}; P3 = {c["name"]: c for c in json.loads(PLAN3.read_text())["clips"]}
    rows = {}
    for name, c in P4.items():
        if name not in P3:
            continue
        rows[name] = {}
        for lab, P, fr in (("r4", P4, FR4), ("r3", P3, FR3)):
            cc = P[name]; r = m3.measure(cc, lab); grip = "two" if "TwoHand" in name else "one"
            if name.startswith("StrafeRun") or name.startswith("Strafe") or name.startswith("Backpedal"):
                r["pelvisVsBoss"] = pelvis_vs_boss(cc["file"], grip)
            if cc["loop"]:
                r["seamLossless"] = seam_lossless(fr / ("%s-%s" % (lab, name)))
                px = m3.pixels(MEDIA4 / ("%s-%s.mp4" % (lab, name)))
                if px:
                    r["seamPixelsIntra"] = px
            if name.startswith("Blink"):
                r["blinkTail"] = blink_tail(cc, m3, None)
                r["blinkTailPng"] = png_steps(fr / ("%s-%s" % (lab, name)), FR3 / ("r3-Idle%s" % ("TwoHand" if grip == "two" else "")))
            if name == "RollAttack":
                r["rollWorld"] = roll_world(cc)
            rows[name][lab] = r
        print(name, json.dumps({lab: {k: v for k, v in rows[name][lab].items() if k in ("pelvisVsBoss", "seamLossless", "blinkTail", "rollWorld")} for lab in rows[name]})[:600], flush=True)
    kept = {}
    for name in KEPT_R3:
        a, b = P4.get(name), P3[name]
        kept[name] = {"v030r": a and a["sha256"], "v030q": b["sha256"], "fileNow": sha(b["file"]) if Path(b["file"]).exists() else None}
        kept[name]["identical"] = bool(a) and a["sha256"] == b["sha256"] == kept[name]["fileNow"]
        r = m3.measure(b, "r3 (kept)"); r["pelvisVsBoss"] = pelvis_vs_boss(b["file"], "two" if "TwoHand" in name else "one")
        r["seamLossless"] = seam_lossless(FR3 / ("r3-" + name)); px = m3.pixels(MEDIA4 / ("r3-%s.mp4" % name))
        if px:
            r["seamPixelsIntra"] = px
        kept[name]["metrics"] = r
    prot = {}
    for name in ("StrafeLeft", "StrafeLeftTwoHand"):
        prot[name] = {"seamLossless": seam_lossless(FR3 / ("r3-" + name))}
        px = m3.pixels(MEDIA4 / ("r3-%s.mp4" % name))
        if px:
            prot[name]["seamPixelsIntra"] = px
    ident = {}
    before = ROOT / "docs/knight-complete-20261028/data/round3-protected-sha256-before.txt"
    for line in before.read_text().splitlines():
        h, p = line.split(None, 1); now = sha(ROOT / p) if (ROOT / p).exists() else None
        ident[p] = {"before": h, "after": now, "identical": h == now}
    Path(out).write_text(json.dumps({"definitions": __doc__, "clips": rows, "keptRound3": kept, "protectedReference": prot,
                                     "byteIdentical": ident, "byteIdenticalAll": all(v["identical"] for v in ident.values()),
                                     "keptRound3IdenticalAll": all(v["identical"] for v in kept.values())}, indent=1, default=float) + "\n")
    print("WROTE", out, "byteIdenticalAll", all(v["identical"] for v in ident.values()), "keptRound3IdenticalAll", all(v["identical"] for v in kept.values()))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "retime-args":
        retime_args()
    elif sys.argv[1] == "predict":
        predict()
    else:
        main(sys.argv[1])
