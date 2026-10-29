"""Knight fix round 4 (2026-10-29), headless Blender driver (no rendering, no window).

blender --background --factory-startup --python build_round4.py -- STAGE [NAMES]
python3 build_round4.py --dry [STAGE]       plain CPython, no bpy: checks inputs/outputs and prints the key timelines

Reuses the round-1/round-3 helpers (exec'd, as round 3 did with round 1). Every output is a NEW name in
Local/FabRigTesting/Exports (v6 / v6c / v6r); export() refuses to overwrite. Approved sources and every round-2/3 file
are only read. StrafeLeft(2H) and the eight staggers are never touched. StrafeRight(2H) and both backpedals are not
re-authored: their round-3 seams are clean on the lossless render frames (the MP4 wrap excess is an encoder artifact,
see plan-round4.md); they stay the v030q files.

Stages
  bodies     sprint strafes: round-3 method (Mixamo strafe run, hips turned so the pelvis is ~45 deg off the boss, spine
             re-aims the chest) PLUS the swing-plane fix: while a foot is off the ground its ankle target is turned about
             the hip's vertical axis by w*theta (theta = pelvis yaw - travel yaw), so the heel kick and the forward reach
             lie in the pelvis sagittal plane, and the knee pole moves to pelvis-forward. Stance frames (w = 0) keep the
             sourced ankle path (foot lock and stance speed unchanged). A gate refuses to export unless the kicked leg's
             plane is within GATE_PLANE_DEG of the boss and the shin's side/front span ratio is >= GATE_RATIO.
             blinks: round-3 method with the round-4 keys (r4_core.BLINK_KEYS_R4): crouch bottom at 0.115 s, two visible
             push frames, deeper crouch, landing impact compression.
  fit        weapon fit (idle-root carry) of blinks / sprint strafes, 1H free-arm counter-swing (as round 3)
  cycles     sprints: loop closure + slow-phase cycle start (as round 3). blinks: first frame pinned to the exact idle;
             the last 0.20 s blend (smootherstep) into the ANIMATED idle, timed so it reaches idle frame 0 exactly at the
             clip end (no frozen hold; the idle's own motion continues across the switch)
  retime     sprint cycles resampled so the stance-foot speed matches the v030p/v030q capsule nominal (owner rule: never
             slow the character to fix sliding). args OUT=TARGET@SOURCE_SPEED, from `measure_round4.py retime-args`
  rollattack round-3 composition (roll, 0.60 s join, slash, arm recovery, wrist pitch) with: (a) world hips velocity
             re-profiled over JOIN_DECEL_S after the root-prefix end (1.0 s) so the roll's speed ramps down instead of
             stopping in two frames; (b) outro starts at 1.62 s; the hips settle on a Hermite path that reaches its final
             position with zero velocity SETTLE_HOLD_S before the end and the idle target is the animated idle;
             (c) contact cleanup 0.62 s..outro: every detected foot contact is locked in world (armature) space and the
             swings between contacts get a minimum lift; (d) the two lifted recovery steps finish before the settle.
"""
import sys, json, math, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r4_core as core  # noqa: E402

ROOT = HERE.parents[2]
EXP = ROOT / "Local/FabRigTesting/Exports"
KNIGHT = ROOT / "Local/CustomuseAssets/Polish20261025/knight"
PLAN3 = ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030q/import-plan-KnightB.json"
OWNER = "fable-knight-round4-20261029"
IDLE = {"": "IdleOneHand_Blender_v2r4.glb", "TwoHand": "IdleTwoHand_Blender_v2r4.glb"}
SPRINTS = (("Knight_StrafeRunRightBody_v6", "Mixamo_StrafeRunRight_v1"), ("Knight_StrafeRunLeftBody_v6", "Mixamo_StrafeRunLeftM_v1"))
# round-4 tunables live in r4_core (shared with measure_round4.py predictions)
from r4_core import (PEL_MAX, SWING_GAIN, FOOT_K, FOOT_SWING_K, POLE_STANCE, POLE_SWING, GATE_PLANE_DEG, GATE_RATIO,  # noqa: E402
                     GATE_STANCE_CM, JOIN_T, JOIN_DECEL_S, OUTRO_START, SETTLE_HOLD_S, GETUP_T, LIFT_MIN_CM, ROLL_RATE)


def outputs():
    out = {"bodies": [o for o, _ in SPRINTS] + ["Knight_Blink%s%sBody_v6" % (s, g) for s in ("Left", "Right") for g in ("", "TwoHand")]}
    out["fit"] = ["Knight_StrafeRun%s%s_v6" % (s, g) for s in ("Left", "Right") for g in ("", "TwoHand")] + \
                 ["Knight_Blink%s%s_v6" % (s, g) for s in ("Left", "Right") for g in ("", "TwoHand")]
    out["cycles"] = [n + "c" for n in out["fit"]]
    out["retime"] = ["Knight_StrafeRun%s%s_v6r" % (s, g) for s in ("Left", "Right") for g in ("", "TwoHand")]
    out["rollattack"] = ["Sourced_RollAttack_v6"]
    return out


def inputs():
    return {"bodies": [s + ".glb" for _, s in SPRINTS] + ["Mixamo_Crouch_v1.glb"], "fit": [], "cycles": [], "retime": [],
            "rollattack": ["Fab_Roll_v17.glb", "Mixamo_Attack_v17.glb"]}


def dry(stage=None):
    ok = True
    for st, names in outputs().items():
        if stage and st != stage:
            continue
        for f in inputs()[st]:
            p = EXP / f
            print("INPUT", st, f, "ok" if p.exists() else "MISSING"); ok &= p.exists()
        for n in names:
            p = EXP / (n + ".glb")
            print("OUTPUT", st, n, "EXISTS (export would refuse)" if p.exists() else "free"); ok &= not p.exists()
    for f in IDLE.values():
        print("INPUT idle", f, "ok" if (KNIGHT / f).exists() else "MISSING"); ok &= (KNIGHT / f).exists()
    if PLAN3.exists():
        c = {x["name"]: x for x in json.loads(PLAN3.read_text())["clips"]}
        r = c["RollAttack"]["gameplay_play_rate"]; print("ROLL_RATE plan", r, "builder", ROLL_RATE, "ok" if abs(r - ROLL_RATE) < 1e-9 else "MISMATCH")
        ok &= abs(r - ROLL_RATE) < 1e-9
        print("ROLL damage windows (unchanged, must end before OUTRO_START %.2f):" % OUTRO_START, c["RollAttack"]["damage_windows"])
        ok &= all(w[1] < OUTRO_START for w in c["RollAttack"]["damage_windows"])
    if stage in (None, "bodies", "cycles"):
        print("BLINK timeline (rendered frames at rate %.2f; hidden %s):" % (core.BLINK_RATE, core.HIDDEN))
        tl = core.blink_timeline()
        for row in tl:
            print("  ", json.dumps(row))
        vis = [r for r in tl if not r["hidden"] and r["clipS"] < core.HIDDEN[0]]
        bottom = max(vis, key=lambda r: r["crouchFrame"])
        push = [r for r in vis if r["clipS"] > bottom["clipS"]]
        print("BLINK launch: crouch bottom at frame %d, visible push frames %d (target >= 2), descent frames %d (target >= 3)"
              % (bottom["frame"], len(push), bottom["frame"]))
        ok &= len(push) >= 2 and bottom["frame"] >= 3
        tail = [r for r in tl if r["clipS"] >= core.BLINK_TAIL[0]]
        print("BLINK tail idle weights (last frames):", [r["tailIdleWeight"] for r in tail])
    steps_end = OUTRO_START + .39; settle = 2.2 - SETTLE_HOLD_S
    print("ROLL outro: steps end %.3f s, hips settle %.3f s, clip end 2.200 s -> steps %s before the settle" % (steps_end, settle, "finish" if steps_end <= settle else "DO NOT finish"))
    ok &= steps_end <= settle
    print("DRY", "OK" if ok else "PROBLEMS")
    return ok


if __name__ == "__main__" and "--dry" in sys.argv:
    try:
        import bpy  # noqa: F401
        IN_BLENDER = True
    except ImportError:
        IN_BLENDER = False
    if not IN_BLENDER:
        rest = [a for a in sys.argv[1:] if a != "--dry"]
        sys.exit(0 if dry(rest[0] if rest else None) else 1)

import bpy  # noqa: E402
from mathutils import Matrix, Vector, Quaternion  # noqa: E402

# round-1 + round-3 helpers (clear, load, basis_rows, scale_rot, smooth, plant_legs, key_rows, FPS, ADDITIVE, set_row,
# rot_about, key_all, new_action, yaw_line, chest_yaw, pelvis_yaw, knee_hinge, plant_legs_pole, needed_drop, SPINE...)
R3 = HERE / "build_round3.py"
_g = {"__file__": str(R3), "__name__": "r3helpers"}
_src = R3.read_text().split('\nif stage == "retarget":')[0]
_saved = sys.argv
sys.argv = [sys.argv[0], "--", "none"]
exec(compile(_src, str(R3), "exec"), _g)
sys.argv = _saved
for _k in ("clear", "load", "basis_rows", "scale_rot", "smooth", "plant_legs", "key_rows", "FAB", "SRC", "FPS", "ADDITIVE",
           "set_row", "rot_about", "key_all", "new_action", "chest_yaw", "pelvis_yaw", "knee_hinge", "plant_legs_pole",
           "needed_drop", "SPINE", "SPINE_LEAN", "Z", "FWD"):
    globals()[_k] = _g[_k]
args = sys.argv[sys.argv.index("--") + 1:]
stage, only = args[0], set(a for a in args[1:] if a != "--force")
FORCE = "--force" in args


def want(name):
    return not only or name in only


def export(arm, body, name, meta, n):
    s = bpy.context.scene
    s.frame_start, s.frame_end = 0, n
    for o in s.objects:
        o.select_set(False)
    arm.select_set(True)
    for o in body:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    path = EXP / name
    assert not path.with_suffix(".glb").exists(), name
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix(".glb")), export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIVE_ACTIONS", export_frame_range=True, export_force_sampling=True,
                              export_optimize_animation_size=False, export_cameras=False, export_lights=False)
    s["session_owner"] = OWNER
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix(".blend")), compress=True)
    meta = dict(meta, name=name, sha256=hashlib.sha256(path.with_suffix(".glb").read_bytes()).hexdigest())
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print("EXPORTED", name, flush=True)


def T3(v):
    return (v[0], v[1], v[2])


def mixm(a, b, u):
    x, q, sc = a.decompose(); y, r, ss = b.decompose()
    if q.dot(r) < 0:
        r = -r
    return Matrix.LocRotScale(x.lerp(y, u), q.slerp(r, u), sc.lerp(ss, u))


def legs_report(arm):
    pb = arm.pose.bones
    return {sd: core.leg_plane(T3(pb[sd + "UpLeg"].head), T3(pb[sd + "Leg"].head), T3(pb[sd + "Foot"].head)) for sd in ("Left", "Right")}


# ------------------------------------------------------------------------------------------------ stages
if stage == "bodies":
    report = {}
    # ---- blinks (round-3 construction, round-4 keys)
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):
        for grip, base_file in IDLE.items():
            name = "Knight_Blink%s%sBody_v6" % (side, grip)
            if not want(name):
                continue
            s = clear()
            n = int(round(core.BLINK_T * FPS))
            times = [i / FPS for i in range(n + 1)]
            P = [core.blink_params(t) for t in times]
            cr, _, cr_objs = load(EXP / "Mixamo_Crouch_v1.glb")
            crow = basis_rows(cr, [p["crouchFrame"] for p in P]); c0 = basis_rows(cr, [0])[0]
            for o in cr_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            base, base_body, _ = load(KNIGHT / base_file); s.frame_set(0)
            idle = {b.name: b.matrix_basis.copy() for b in base.pose.bones}
            feet = {sd: base.pose.bones[sd + "Foot"].matrix.copy() for sd in ("Left", "Right")}
            hips_idle = base.pose.bones["Hips"].head.copy()
            new_action(base, name); pb = base.pose.bones; prev = {}; log = []
            for f, (t, p) in enumerate(zip(times, P)):
                k = p["crouchGain"]; row = {}
                for bn, m in idle.items():
                    if bn in ADDITIVE and bn in crow[f]:
                        l0, q0, _ = c0[bn].decompose(); lt, qt, _ = crow[f][bn].decompose()
                        li, qi, si = m.decompose()
                        row[bn] = Matrix.LocRotScale(li + (lt - l0) * (k if bn == "Hips" else 0.0), qi @ scale_rot(q0.inverted() @ qt, k), si)
                    else:
                        row[bn] = m.copy()
                set_row(base, row)
                hp = pb["Hips"]
                hp.matrix = Matrix.Translation(Vector((sgn * p["shiftM"], 0, 0))) @ hp.matrix; bpy.context.view_layer.update()
                for bn, frac in SPINE_LEAN:
                    rot_about(pb[bn], Vector((0, 1, 0)), sgn * p["leanDeg"] * frac)
                rot_about(pb["Head"], Vector((0, 1, 0)), -sgn * p["leanDeg"] * .30)
                rot_about(hp, Z, sgn * p["pelvisYawDeg"])
                for bn, frac in SPINE:
                    rot_about(pb[bn], Z, -sgn * p["pelvisYawDeg"] * .85 * frac)
                plant_legs(base, feet)
                key_all(base, f, prev)
                log.append({"t": round(t, 4), "hipsDropCm": round((pb["Hips"].head.z - hips_idle.z) * 240, 1), "chest": round(chest_yaw(base), 1),
                            "pelvis": round(pelvis_yaw(base), 1), "ankleErrCm": round(max((pb[sd + "Foot"].head - feet[sd].translation).length for sd in feet) * 240, 2)})
            report[name] = log
            export(base, base_body, name, {"fps": FPS, "duration": n / FPS, "base": base_file, "travelSign": sgn, "keys": core.BLINK_KEYS_R4,
                                           "sources": {"Mixamo_Crouch_v1": "sword and shield crouch.fbx frames 0-9, additive (hips, spine, neck, head, clavicles) x0.75; forward for the launch, partly reversed for the landing"},
                                           "authored": "round 4 keys: crouch bottom 0.115 s (two visible push frames), lateral hip shift, lean, pelvis yaw (spine counter 85%), landing impact compression; feet planted on the idle stance (analytic IK)",
                                           "hiddenWindowClipSeconds": core.HIDDEN, "frames": log}, n)
    # ---- sprint strafes: round-3 hip turn + round-4 swing-plane fix
    for out, src in SPRINTS:
        if not want(out):
            continue
        s = clear(); arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text()); n = int(round(meta["duration"] * FPS))
        rows = basis_rows(arm, range(n + 1)); pb = arm.pose.bones
        new_action(arm, out)
        Ps, Cs, feet, az, tz, fp = [], [], [], {"Left": [], "Right": []}, {"Left": [], "Right": []}, {"Left": [], "Right": []}
        for row in rows:
            set_row(arm, row); Ps.append(pelvis_yaw(arm)); Cs.append(chest_yaw(arm))
            feet.append({sd: pb[sd + "Foot"].matrix.copy() for sd in ("Left", "Right")})
            for sd in ("Left", "Right"):
                az[sd].append(pb[sd + "Foot"].head.z); tz[sd].append(pb[sd + "ToeBase"].head.z); fp[sd].append(T3(pb[sd + "Foot"].head))
        Pm, Cm = sum(Ps) / len(Ps), sum(Cs) / len(Cs); sgn = 1.0 if Pm > 0 else -1.0
        best = None
        for pel in [PEL_MAX - .5 * i for i in range(21)]:
            for alpha in (.5, .4, .3, .2):
                for ch in [i * .5 for i in range(37)]:
                    chest = [sgn * ch + alpha * (c - Cm) for c in Cs]
                    pelv = [p - Pm + sgn * pel for p in Ps]
                    tw = max(abs(a - b) for a, b in zip(pelv, chest)); cmax = max(abs(c) for c in chest)
                    if tw <= 44.0 and cmax <= 18.0:
                        score = (pel, alpha, -tw)
                        if best is None or score > best[0]:
                            best = (score, pel, alpha, ch, tw, cmax)
        assert best, "no pelvis/chest split meets the caps"
        _, pel, alpha, ch, tw_pred, cmax_pred = best
        d1 = sgn * pel - Pm
        travel = core.travel_yaw({sd: fp[sd][:n] for sd in fp}, FPS) or sgn * 90.0
        theta = (sgn * pel - travel) * SWING_GAIN
        W = {sd: core.swing_weights(az[sd][:n], tz[sd][:n]) for sd in az}
        for sd in W:
            W[sd].append(W[sd][0])
        REACH = .98
        HINGE = knee_hinge(arm, rows)

        def posed(f):
            """Source frame f, hips turned, chest re-aimed; ankle targets (swing offsets turned into the pelvis plane) and poles."""
            set_row(arm, rows[f])
            hp = pb["Hips"]; rot_about(hp, Z, d1)
            want_c = sgn * ch + alpha * (Cs[f] - Cm)
            for _ in range(3):
                d2 = want_c - chest_yaw(arm)
                for bn, frac in SPINE:
                    rot_about(pb[bn], Z, d2 * frac)
            L = pb["LeftUpLeg"].head - pb["RightUpLeg"].head
            pf = Vector((L.y, -L.x, 0)).normalized()
            tg, poles = {}, {}
            for sd in ("Left", "Right"):
                w = W[sd][f]; m = feet[f][sd]; H = pb[sd + "UpLeg"].head
                T2 = Vector(core.rot_vertical(T3(m.to_translation()), T3(H), theta * w))
                qf = Quaternion(Z, math.radians(d1 * FOOT_K + theta * w * FOOT_SWING_K))
                tg[sd] = Matrix.LocRotScale(T2, qf @ m.to_quaternion(), Vector((1, 1, 1)))
                K, A = pb[sd + "Leg"].head, pb[sd + "Foot"].head
                dd = (A - H).normalized(); off = (K - H) - dd * (K - H).dot(dd)
                src_dir = (off + pf * .05).normalized()
                k = POLE_STANCE + (POLE_SWING - POLE_STANCE) * w
                poles[sd] = src_dir * (1 - k) + pf * k
            return tg, poles
        # pass 1: hips drop each frame needs to keep both legs at <= 98% reach (turning about the hip's vertical keeps the
        # hip-ankle distance, so this equals round 3's drop); dilate +-3 frames (cyclic), equal for both steps, smooth
        need, P1 = [], []
        for f in range(n + 1):
            tg, po = posed(f); need.append(needed_drop(arm, tg, REACH)); P1.append(po)
        PS = [{sd: sum((P1[(i + k) % n][sd] * wk for k, wk in ((-2, 1), (-1, 2), (0, 3), (1, 2), (2, 1))), Vector()) / 9 for sd in ("Left", "Right")} for i in range(n)]
        PS.append(PS[0])
        cyc = need[:n]
        h2 = n / 2.0
        cyc = [max(cyc[i], cyc[int(math.floor(i + h2)) % n] * (1 - (h2 % 1)) + cyc[int(math.ceil(i + h2)) % n] * (h2 % 1),
                   cyc[int(math.floor(i - h2)) % n] * (h2 % 1) + cyc[int(math.ceil(i - h2)) % n] * (1 - (h2 % 1))) for i in range(n)]
        dil = [max(cyc[(i + k) % n] for k in range(-3, 4)) for i in range(n)]
        for _ in range(2):
            dil = [(dil[(i - 1) % n] + 2 * dil[i] + dil[(i + 1) % n]) / 4 for i in range(n)]
        dil = [max(x, y) for x, y in zip(dil, cyc)]
        drops = dil + [dil[0]]
        prev = {}; log = []; legs = {"Left": [], "Right": []}
        for f in range(n + 1):
            tg, _ = posed(f); poles = PS[f]
            hp = pb["Hips"]; hp.matrix = Matrix.Translation(Vector((0, 0, -drops[f]))) @ hp.matrix; bpy.context.view_layer.update()
            plant_legs_pole(arm, tg, poles, REACH, HINGE)
            err = {sd: (pb[sd + "Foot"].head - tg[sd].to_translation()).length for sd in tg}
            lr = legs_report(arm)
            for sd in lr:
                legs[sd].append(lr[sd])
            key_all(arm, f, prev)
            log.append({"f": f, "pelvis": round(pelvis_yaw(arm), 1), "chest": round(chest_yaw(arm), 1), "ankleErrCm": {sd: round(e * 240, 2) for sd, e in err.items()},
                        "swingW": {sd: round(W[sd][f], 3) for sd in W}, "hipsDropCm": round(drops[f] * 240, 2),
                        "legPlaneYaw": {sd: round(lr[sd]["planeYaw"], 1) for sd in lr}, "kneeBendDeg": {sd: round(lr[sd]["kneeBend"], 1) for sd in lr}})
        kicks = {sd: core.full_kick(legs[sd][:n]) for sd in legs}
        stance_err = max(row["ankleErrCm"][sd] for row in log for sd in ("Left", "Right") if row["swingW"][sd] < .02)
        gate = all(abs(k["planeYaw"]) <= GATE_PLANE_DEG and k["sideOverFront"] >= GATE_RATIO for k in kicks.values()) and stance_err <= GATE_STANCE_CM
        report[out] = {"source": src, "sourcePelvisMean": round(Pm, 1), "sourceChestMean": round(Cm, 1), "pelvisYawFromBossDeg": pel,
                       "travelYaw": round(travel, 1), "swingThetaDeg": round(theta, 1), "chestTarget": sgn * ch, "chestSwingKept": alpha,
                       "predictedTwistMax": round(tw_pred, 1), "fullKick": kicks, "stanceAnkleErrMaxCm": stance_err, "gate": gate, "frames": log}
        print("RUNBODY", out, {k: v for k, v in report[out].items() if k != "frames"}, flush=True)
        if not gate and not FORCE:
            rp = EXP / "round4-bodies-report.json"; old = json.loads(rp.read_text()) if rp.exists() else {}
            rp.write_text(json.dumps(dict(old, **{out + "#GATE_FAIL": report[out]}), indent=1))
            raise SystemExit("GATE_FAIL %s: kicked-leg plane / shin ratio / stance error outside the round-4 gate (see round4-bodies-report.json); --force to export anyway" % out)
        export(arm, body, out, {"fps": FPS, "duration": n / FPS, "source": src, "method":
                                "round 3 hip turn (pelvis %.1f deg off the boss, spine 30/35/35%% re-aims the chest to %.1f deg + %.0f%% of the source "
                                "shoulder swing) + round 4 swing plane: off-ground ankle targets turned about the hip's vertical axis by w x %.1f deg "
                                "(pelvis minus travel yaw, w = swing weight from ankle/toe clearance) so the heel kick and reach lie in the pelvis plane; "
                                "knee pole %.0f%%..%.0f%% pelvis-forward (stance..swing); stance frames keep the sourced ankle path; feet turned %.1fx the hip turn "
                                "(+%.1fx the swing turn in the air); smoothed hips drop at 98%% reach; timing unchanged"
                                % (pel, sgn * ch, alpha * 100, theta, POLE_STANCE * 100, POLE_SWING * 100, FOOT_K, FOOT_SWING_K),
                                "twist": {k: v for k, v in report[out].items() if k != "frames"}}, n)
    rp = EXP / "round4-bodies-report.json"
    old = json.loads(rp.read_text()) if rp.exists() else {}
    rp.write_text(json.dumps(dict(old, **report), indent=1))

elif stage == "fit":
    fg = {"__file__": str(FAB / "fit_weapon.py")}
    exec(compile((FAB / "fit_weapon.py").read_text(), str(FAB / "fit_weapon.py"), "exec"), fg)
    bpy.context.scene["session_owner"] = fg["OWNER"]
    refs = {"one": fg["reference"]("IdleOneHand_Blender_v2r4.glb"), "two": fg["reference"]("IdleTwoHand_Blender_v2r4.glb"),
            "guard": fg["reference"]("GuardReadyTwoHand_Blender_v4r4.glb", True)}

    def run_swing(sgn, amp=.075):  # round 3, unchanged
        travel = Vector((sgn, 0, 0)); cache = {}

        def fn(f, N, source, ch, hand):
            if "s" not in cache:
                d = [((source[i]["RightFoot"].translation - source[i]["LeftFoot"].translation).dot(travel)) for i in range(N + 1)]
                lo, hi = min(d), max(d); mid = (lo + hi) / 2; half = max(1e-6, (hi - lo) / 2)
                cache["s"] = [(x - mid) / half for x in d]
            sw = cache["s"][f]
            out = hand.copy(); out.translation += travel * amp * sw + Vector((0, 0, .022 * sw * sw)) + FWD * (.015 * abs(sw))
            return out
        return fn

    def blink_swing(sgn, amp=.08):  # round 3 shape on the round-4 armLead key
        travel = Vector((sgn, 0, 0))

        def fn(f, N, source, ch, hand):
            t = f / N * core.BLINK_T; a = core.seg(t, core.BLINK_KEYS_R4["armLead"])
            out = hand.copy(); out.translation += travel * amp * a + Vector((0, 0, .05 * abs(a))) + FWD * (.03 * abs(a))
            return out
        return fn
    jobs = []
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):
        for grip in ("", "TwoHand"):
            kw = {} if grip else {"left_fn": run_swing(sgn)}
            jobs.append(("Knight_StrafeRun%s%s_v6" % (side, grip), "Knight_StrafeRun%sBody_v6" % side, grip, "idle-root", kw))
            kw = {"follow": .45} if grip else {"follow": .45, "left_fn": blink_swing(sgn)}
            jobs.append(("Knight_Blink%s%s_v6" % (side, grip), "Knight_Blink%s%sBody_v6" % (side, grip), grip, "idle-root", kw))
    for out, src, grip, mode, kw in jobs:
        if not want(out):
            continue
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        bpy.context.scene["session_owner"] = fg["OWNER"]
        fg["fit"]("walk", refs, "v6", "two" if grip else "one", out, src, mode, (0., 0.), **kw)
        d = json.loads((EXP / (out + ".json")).read_text()); d["round4"] = {k: (v if not callable(v) else v.__qualname__) for k, v in kw.items()}
        (EXP / (out + ".json")).write_text(json.dumps(d, indent=2))
        print("FITTED", out, flush=True)

elif stage == "cycles":
    HZ = 120
    s = clear(); a0, _, o0 = load(KNIGHT / IDLE[""]); s.frame_set(0)
    d0 = a0.pose.bones["LeftFoot"].head - a0.pose.bones["RightFoot"].head; d0.z = 0; IDLE_ANKLE = d0.length
    for o in o0:
        bpy.data.objects.remove(o, do_unlink=True)
    BANDS = {"headChest": ["Head", "Neck", "Spine2", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm"],
             "hipsSword": ["Hips", "Spine", "LeftUpLeg", "RightUpLeg", "LeftHand", "RightHand", "LeftForeArm", "RightForeArm", "#tip", "#base"],
             "legsFeet": ["LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"]}
    LOOPS = [("Knight_StrafeRun%s%s_v6" % (sd, g), "Knight_StrafeRun%s%s_v6c" % (sd, g), 1.1) for sd in ("Left", "Right") for g in ("", "TwoHand")]
    rep = {}

    def pose_points(arm):
        pb = arm.pose.bones; P = {b.name: b.head.copy() for b in pb}
        so = pb["WeaponSocket"].matrix
        P["#tip"] = so @ Vector((0, 2.35, 0)); P["#base"] = so @ Vector((0, .6, 0))
        return P

    for src, out, rate in LOOPS:  # round-3 algorithm, unchanged
        if not want(out) or (EXP / (out + ".glb")).exists():
            continue
        s = clear(); s.render.fps = HZ
        arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
        rows = basis_rows(arm, range(n + 1))
        resid = {}; closed = []
        for i, row in enumerate(rows):
            u = i / n; r = {}
            for bn, m in row.items():
                l0, q0, s0 = rows[0][bn].decompose(); ln, qn, sn = rows[n][bn].decompose(); li, qi, si = m.decompose()
                if i == 0:
                    resid[bn] = ((ln - l0).length, math.degrees(2 * math.acos(min(1.0, abs(qn.dot(q0))))))
                dq = qn.inverted() @ q0
                if dq.w < 0:
                    dq = -dq
                r[bn] = Matrix.LocRotScale(li + (l0 - ln) * u, qi @ scale_rot(dq, u), si + (s0 - sn) * u)
            closed.append(r)
        arm.animation_data_clear()
        pts, widths = [], []
        for r in closed[:n]:
            set_row(arm, r); P = pose_points(arm); pts.append(P)
            d = P["LeftFoot"] - P["RightFoot"]; d.z = 0; widths.append(d.length)
        nr = max(8, int(round(T / rate * 30))); stride = n / nr

        def band_step(a, b, band):
            return sum((pts[b % n][j] - pts[a % n][j]).length for j in BANDS[band]) / len(BANDS[band])
        steps = {bd: [band_step(int(round(i - stride)), i, bd) for i in range(n)] for bd in BANDS}
        mean = {bd: sum(v) / n for bd, v in steps.items()}
        cand = [(max(steps[bd][i] / mean[bd] for bd in BANDS), abs(widths[i] - IDLE_ANKLE), i) for i in range(n)]
        good = [c for c in cand if c[0] <= .80] or [c for c in cand if c[0] <= .92]
        pick = min(good, key=lambda c: (c[1], c[0])) if good else min(cand)
        i0 = pick[2]
        key_rows(arm, [closed[(i0 + i) % n] for i in range(n + 1)], out)
        m2 = dict(meta, fps=HZ, bakeSampleRate=HZ, derivedFrom=src, cycleStartShiftSeconds=i0 / HZ, startAnkleMetres=widths[i0], idleAnkleMetres=IDLE_ANKLE,
                  closureResidualMax={"locCm": round(max(v[0] for v in resid.values()) * 240, 3), "rotDeg": round(max(v[1] for v in resid.values()), 3)},
                  seamChoice={"renderFramesPerCycle": nr, "stepRatioToMeanMaxBand": round(pick[0], 3), "bandMeansCm": {k: round(v * 240, 2) for k, v in mean.items()}},
                  method="round-3 loop closure + slow-phase cycle start")
        m2.pop("sha256", None)
        export(arm, body, out, m2, n)
        rep[out] = {"shift": i0 / HZ, "ratio": round(pick[0], 3), "ankleCm": round(widths[i0] * 240, 1), "closure": m2["closureResidualMax"]}
        print("CYCLE", out, rep[out], flush=True)
    # blinks: first frame = exact idle frame 0 (fading out by 0.05 s); last 0.20 s blend into the animated idle, which
    # reaches its frame 0 exactly at the clip end (round 3 held the static idle from 0.62 s: three identical frames)
    for side in ("Left", "Right"):
        for grip in ("", "TwoHand"):
            src, out = "Knight_Blink%s%s_v6" % (side, grip), "Knight_Blink%s%s_v6c" % (side, grip)
            if not want(out) or (EXP / (out + ".glb")).exists():
                continue
            s = clear(); s.render.fps = HZ
            meta = json.loads((EXP / (src + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
            ia, _, io = load(KNIGHT / IDLE[grip]); s.frame_set(0)
            idle0 = {b.name: b.matrix_basis.copy() for b in ia.pose.bones}
            idle_T = ia.animation_data.action.frame_range[1] / HZ
            tail_t = [i / HZ for i in range(n + 1) if i / HZ >= core.BLINK_TAIL[0]]
            taus = [core.idle_tail_time(t, T, core.BLINK_RATE, idle_T) for t in tail_t]
            tail_rows = dict(zip([round(t * HZ) for t in tail_t], basis_rows(ia, [tau * HZ for tau in taus])))
            for o in io:
                bpy.data.objects.remove(o, do_unlink=True)
            arm, body, objs = load(EXP / (src + ".glb"))
            rows = basis_rows(arm, range(n + 1))
            out_rows = []
            for i, row in enumerate(rows):
                t = i / HZ
                if i == n:
                    out_rows.append({bn: idle0.get(bn, m) for bn, m in row.items()}); continue
                if t < .05:
                    w = 1.0 - core.smooth(t / .05)
                    out_rows.append({bn: mixm(m, idle0[bn], w) if bn in idle0 else m for bn, m in row.items()}); continue
                w = core.smoother((t - core.BLINK_TAIL[0]) / (core.BLINK_TAIL[1] - core.BLINK_TAIL[0])) if t >= core.BLINK_TAIL[0] else 0.0
                tr = tail_rows.get(i, idle0)
                out_rows.append({bn: mixm(m, tr[bn], w) if (w > 0 and bn in tr) else m for bn, m in row.items()})
            key_rows(arm, out_rows, out)
            m2 = dict(meta, fps=HZ, derivedFrom=src, idleTail={"clipSeconds": core.BLINK_TAIL, "idleSeconds": idle_T, "idleRate": 1.0, "blinkRate": core.BLINK_RATE,
                      "note": "smootherstep blend into the animated idle, timed to reach idle frame 0 exactly at the clip end"},
                      idlePinned="exact idle frame 0 at t=0 (fading out by 0.05 s) and at the last frame")
            m2.pop("sha256", None)
            export(arm, body, out, m2, n)
    print("CYCLES", json.dumps(rep), flush=True)

elif stage == "retime":
    HZ = 120
    for spec in sorted(only):
        out, rest = spec.split("="); tgt, have = map(float, rest.split("@")); src = out.replace("_v6r", "_v6c")
        assert out.endswith("_v6r"), spec
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        s = clear(); s.render.fps = HZ
        arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text()); n = int(round(meta["duration"] * HZ))
        m = max(8, int(round(n * have / tgt)))
        rows = basis_rows(arm, [i * n / m for i in range(m + 1)])
        key_rows(arm, rows, out)
        m2 = dict(meta, fps=HZ, duration=m / HZ, derivedFrom=src, retime={"sourceFrames": n, "frames": m, "sourceStanceSpeedCmS": have,
                  "targetNominalCmS": tgt, "predictedStanceSpeedCmS": round(have * n / m, 2),
                  "why": "owner rule: never slow the character to fix sliding; capsule speed kept, clip retimed to match it"})
        m2.pop("sha256", None)
        export(arm, body, out, m2, m)
        print("RETIMED", out, n, "->", m, "frames", round(have * n / m, 2), "cm/s vs", tgt, flush=True)

elif stage == "rollattack":
    name = "Sourced_RollAttack_v6"
    assert not (EXP / (name + ".glb")).exists(), name
    s = clear()
    HZ = 300
    roll, roll_body, roll_objs = load(EXP / "Fab_Roll_v17.glb")
    att, att_body, att_objs = load(EXP / "Mixamo_Attack_v17.glb")
    idl, idl_body, idl_objs = load(KNIGHT / "IdleOneHand_Blender_v2r4.glb")
    rmeta = json.loads((EXP / "Fab_Roll_v17.json").read_text()); ameta = json.loads((EXP / "Mixamo_Attack_v17.json").read_text())

    def arm_rows(arm, src_dur, out_dur):
        cnt = int(round(out_dur * HZ)); rows = []
        for i in range(cnt + 1):
            f = i / cnt * src_dur * FPS
            s.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
            rows.append({b.name: b.matrix.copy() for b in arm.pose.bones})
        return rows
    R = arm_rows(roll, rmeta["duration"], 1.0)
    A = arm_rows(att, ameta["duration"], 1.2)
    NF = 301 + len(A) - 1; T_END = (NF - 1) / HZ
    idle_T = idl.animation_data.action.frame_range[1] / FPS
    o_start = int(round(OUTRO_START * HZ))
    IT = {}
    for f in range(o_start, NF):  # R4: the outro blends toward the ANIMATED idle, reaching idle frame 0 at the clip end
        tau = core.idle_tail_time(f / HZ, T_END, ROLL_RATE, idle_T)
        s.frame_set(int(math.floor(tau * FPS)), subframe=tau * FPS - math.floor(tau * FPS))
        IT[f] = {b.name: b.matrix.copy() for b in idl.pose.bones}
    s.frame_set(0)
    I = {b.name: b.matrix.copy() for b in idl.pose.bones}
    IT[NF - 1] = I
    for o in list(att_objs) + list(idl_objs):
        bpy.data.objects.remove(o, do_unlink=True)
    off = R[-1]["Hips"].translation - A[0]["Hips"].translation; off.z = 0
    JOIN, OUTRO = int(.60 * HZ), NF - 1 - o_start

    def smoother(x):
        return core.smoother(x)

    def grip_of(p):
        return p["RightHand"].inverted() @ p["WeaponSocket"]
    frames, grips, outro_u = [], [], []
    gR, gI = grip_of(R[-1]), grip_of(I)
    T_GRIP = gI.translation.copy()
    for f in range(NF):  # round-2/3 composition; R4: longer outro, animated idle target
        if f <= 300:
            frames.append(R[f]); grips.append(grip_of(R[f])); outro_u.append(0.0); continue
        j = f - 300
        a = {n: Matrix.Translation(off) @ m for n, m in A[j].items()}
        g = grip_of(A[j])
        if j <= JOIN:
            u = smoother(j / JOIN)
            ext = {}
            for n in a:
                if n in R[-1]:
                    l1, q1, s1 = R[-2][n].decompose(); l2, q2, s2 = R[-1][n].decompose()
                    steps = min(j, 12) * (1 - u)
                    ext[n] = Matrix.LocRotScale(l2 + (l2 - l1) * steps, q2 @ scale_rot(q1.inverted() @ q2, steps), s2)
            a = {n: mixm(ext[n], m, u) if n in ext else m for n, m in a.items()}
            g = mixm(gR, g, u)
        uo = 0.0
        if f >= o_start:
            uo = smoother((f - o_start) / OUTRO)
            hip_off = a["Hips"].translation - I["Hips"].translation; hip_off.z = 0
            tgt = {n: Matrix.Translation(hip_off) @ m for n, m in IT[f].items()}
            a = {n: mixm(m, tgt[n], uo) if n in tgt and n != "VeyrRoot" else m for n, m in a.items()}
            g = mixm(g, gI, uo)
        frames.append(a); grips.append(g); outro_u.append(uo)
    # ---- round 3 (unchanged): right arm recovers from the slash straight to the carry; wrist keeps the blade pitch monotonic
    ARM = ["RightShoulder", "RightArm", "RightForeArm", "RightHand"]
    PARENT = {"RightShoulder": "Spine2", "RightArm": "RightShoulder", "RightForeArm": "RightArm", "RightHand": "RightForeArm"}
    REC0, REC1 = int(round(1.60 * HZ)), int(round(2.10 * HZ))

    def local(p, bn):
        return p[PARENT[bn]].inverted() @ p[bn]
    L0 = {bn: local(frames[REC0], bn) for bn in ARM}; G0 = grips[REC0]
    LI = {bn: local(I, bn) for bn in ARM}
    PALL = {b.name: b.parent.name for b in roll.pose.bones if b.parent}
    HAND_KIDS = []

    def kids(n):
        for c, par in PALL.items():
            if par == n:
                HAND_KIDS.append(c); kids(c)
    kids("RightHand")
    for f in range(REC0, NF):
        w = smoother((f - REC0) / (REC1 - REC0))
        p = dict(frames[f]); old = frames[f]
        for bn in ARM:
            p[bn] = p[PARENT[bn]] @ mixm(L0[bn], LI[bn], w)
        for bn in HAND_KIDS:
            p[bn] = p[PALL[bn]] @ (old[PALL[bn]].inverted() @ old[bn])
        frames[f] = p; grips[f] = mixm(G0, gI, w)

    def pitch_of(f):
        gl, gq, gs = grips[f].decompose(); so = frames[f]["RightHand"] @ Matrix.LocRotScale(T_GRIP, gq, gs)
        b = (so.to_3x3() @ Vector((0, 1, 0))).normalized(); return math.degrees(math.asin(max(-1.0, min(1.0, b.z)))), b
    p0, pE = pitch_of(REC0)[0], pitch_of(NF - 1)[0]
    WRIST = []
    for f in range(REC0, NF):
        cur, b = pitch_of(f); tgt = p0 + (pE - p0) * smoother((f - REC0) / (NF - 1 - REC0)); dl = tgt - cur
        ax = b.cross(Z)
        if ax.length > 1e-6 and abs(dl) > 1e-4:
            hm = frames[f]["RightHand"]; h = hm.translation.copy(); old = dict(frames[f]); p = dict(frames[f])
            p["RightHand"] = Matrix.Translation(h) @ Matrix.Rotation(math.radians(dl), 4, ax.normalized()) @ Matrix.Translation(-h) @ hm
            for bn in HAND_KIDS:
                p[bn] = p[PALL[bn]] @ (old[PALL[bn]].inverted() @ old[bn])
            frames[f] = p
        WRIST.append(round(dl, 2))
    print("WRIST_PITCH_CORRECTION_DEG", min(WRIST), max(WRIST), "pitch", round(p0, 1), "->", round(pE, 1), flush=True)
    # ---- R4 (a)+(b): world hips path. Armature space == game world here: normalize_sourced extracts the root as the hips'
    # planar path up to 1.0 s and holds it after, so game world motion = this hips path at every time.
    orig_feet = [{sd: frames[f][sd + "Foot"].translation.copy() for sd in ("Left", "Right")} for f in range(NF)]
    orig_toe_z = [{sd: frames[f][sd + "ToeBase"].translation.z for sd in ("Left", "Right")} for f in range(NF)]
    HXY = [(frames[f]["Hips"].translation.x, frames[f]["Hips"].translation.y, 0.0) for f in range(NF)]
    J0 = int(round(JOIN_T * HZ)); J1 = J0 + int(round(JOIN_DECEL_S * HZ))
    newj, delta = core.reprofile_velocity(HXY, J0, J1)
    corr = [(0.0, 0.0, 0.0)] * NF
    for k, f in enumerate(range(J0, J1 + 1)):
        corr[f] = core.sub(newj[k], HXY[f])
    for f in range(J1 + 1, o_start + 1):
        corr[f] = delta
    F_SET = NF - 1 - int(round(SETTLE_HOLD_S * HZ))
    pa = core.add(HXY[o_start], corr[o_start]); pb_ = core.add(HXY[o_start - 1], corr[o_start - 1])
    settle = core.settle_path(pa, core.sub(pa, pb_), HXY[NF - 1], F_SET - o_start)
    for k, f in enumerate(range(o_start, F_SET + 1)):
        corr[f] = core.sub(settle[k], HXY[f])
    for f in range(F_SET + 1, NF):
        corr[f] = core.sub(HXY[NF - 1], HXY[f])
    for f in range(NF):
        c = corr[f]
        if abs(c[0]) + abs(c[1]) > 1e-9:
            M = Matrix.Translation(Vector((c[0], c[1], 0.0)))
            frames[f] = {bn: M @ m for bn, m in frames[f].items()}
    print("ROLL_PATH join delta cm", [round(x * 240, 1) for x in delta[:2]], "settle frames", F_SET - o_start, "hold frames", NF - 1 - F_SET, flush=True)
    # ---- R4 (c): contact cleanup from the get-up to the outro start, world (armature) space
    G0f = int(round(GETUP_T * HZ))
    floor_toe = {sd: I[sd + "ToeBase"].translation.z for sd in ("Left", "Right")}
    targets = {}   # f -> {sd: Matrix}
    contact_log, in_contact = {}, {}
    for sd in ("Left", "Right"):
        seg_o = [T3(orig_feet[f][sd]) for f in range(G0f, o_start + 1)]
        tz = [orig_toe_z[f][sd] for f in range(G0f, o_start + 1)]
        runs = core.contact_runs(seg_o, tz, None, HZ)
        cur = [T3(frames[f][sd + "Foot"].translation) for f in range(G0f, o_start + 1)]
        tg = core.contact_targets(cur, runs, LIFT_MIN_CM / 240.0, lock_z=False)
        contact_log[sd] = [(round((a + G0f) / HZ, 3), round((b + G0f) / HZ, 3)) for a, b in runs]
        for k, f in enumerate(range(G0f, o_start + 1)):
            # horizontal lock only: the sourced heel lift / toe roll (ankle height and foot rotation) are kept
            targets.setdefault(f, {})[sd] = Matrix.LocRotScale(Vector(tg[k]), frames[f][sd + "Foot"].to_quaternion(), Vector((1, 1, 1)))
        in_contact[sd] = set(G0f + k for a, b in runs for k in range(a, b + 1))
    print("ROLL_CONTACTS clip s", json.dumps(contact_log), flush=True)
    # toes never below the idle toe-joint height: the slash source plants its feet ~3 cm lower than the roll / idle
    LOCAL_TOE = {sd: I[sd + "Foot"].to_3x3().inverted() @ (I[sd + "ToeBase"].translation - I[sd + "Foot"].translation) for sd in ("Left", "Right")}
    TOE_FLOOR = core.TOE_FLOOR_CM / 240.0
    toe_fixed = {"Left": 0, "Right": 0}

    def toe_up(m, sd):
        loc, q, sc = m.decompose(); v = q.to_matrix() @ LOCAL_TOE[sd]; L = v.length
        if loc.z + v.z >= TOE_FLOOR or L < 1e-6 or (TOE_FLOOR - loc.z) / L >= 1.0:
            return m
        ax = v.cross(Z)
        if ax.length < 1e-6:
            return m
        ang = math.asin(max(-1.0, (TOE_FLOOR - loc.z) / L)) - math.asin(max(-1.0, min(1.0, v.z / L)))
        toe_fixed[sd] += 1
        return Matrix.LocRotScale(loc, (Matrix.Rotation(ang, 3, ax.normalized()) @ q.to_matrix()).to_quaternion(), sc)
    # ---- R4 (d): two lifted recovery steps (round 3 shape) from the cleaned feet at the outro start, done before the settle
    plant0 = {sd: targets[o_start][sd].copy() for sd in ("Left", "Right")}
    plant1 = {sd: frames[-1][sd + "Foot"].copy() for sd in ("Left", "Right")}
    moves = {sd: (plant1[sd].translation - plant0[sd].translation).length for sd in ("Left", "Right")}
    step_foot = max(moves, key=moves.get); other = "Right" if step_foot == "Left" else "Left"
    STEPS = ((step_foot, o_start, o_start + int(round(.19 * HZ)), .06), (other, o_start + int(round(.20 * HZ)), o_start + int(round(.39 * HZ)), .05))
    assert STEPS[-1][2] <= F_SET, "recovery steps must finish before the hips settle"
    for f in range(o_start + 1, NF):
        tg = {}
        for sd, a, b_, h in STEPS:
            w = max(0.0, min(1.0, (f - a) / (b_ - a)))
            m = mixm(plant0[sd], plant1[sd], smooth(w))
            tg[sd] = Matrix.Translation(Vector((0, 0, h * math.sin(math.pi * w)))) @ m
        targets[f] = tg
    for f in targets:
        targets[f] = {sd: toe_up(m, sd) for sd, m in targets[f].items()}
    print("ROLL_TOE_FLOOR frames pitched up", toe_fixed, flush=True)
    # ---- key it
    arm = roll
    arm.animation_data_clear(); arm.animation_data_create(); arm.animation_data.action = bpy.data.actions.new(name)
    s.render.fps = HZ
    order = []

    def walk_(b):
        order.append(b)
        for c in b.children:
            walk_(c)
    for b in arm.pose.bones:
        b.rotation_mode = "QUATERNION"
        if b.parent is None:
            walk_(b)
    prev = {}; contact_err = 0.0
    pb = arm.pose.bones
    for f, pose in enumerate(frames):
        for b in order:
            if b.name in pose and b.name != "WeaponSocket":
                b.matrix = pose[b.name]; bpy.context.view_layer.update()
        if f in targets:
            plant_legs(arm, targets[f])
            for sd in ("Left", "Right"):
                if f in in_contact.get(sd, ()):
                    e = (pb[sd + "Foot"].head - targets[f][sd].to_translation()).length * 240
                    contact_err = max(contact_err, e)
        gl, gq, gs = grips[f].decompose()
        pb["WeaponSocket"].matrix = pb["RightHand"].matrix @ Matrix.LocRotScale(T_GRIP, gq, gs); bpy.context.view_layer.update()
        for b in order:
            q = b.rotation_quaternion.copy()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy(); b.rotation_quaternion = q
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)
    export(arm, roll_body, name, {"fps": HZ, "duration": (NF - 1) / HZ, "rollPrefixSeconds": 1.0, "attackComposedDuration": 1.2,
                                  "joinSeconds": JOIN / HZ, "outroStartSeconds": o_start / HZ, "outroSeconds": OUTRO / HZ, "stepFoot": step_foot,
                                  "steps": [{"foot": sd, "clipSeconds": [round(a / HZ, 3), round(b_ / HZ, 3)], "liftRigM": h} for sd, a, b_, h in STEPS],
                                  "joinDecel": {"clipSeconds": [J0 / HZ, J1 / HZ], "attackOffsetCm": [round(x * 240, 2) for x in delta[:2]]},
                                  "hipsSettle": {"clipSeconds": [o_start / HZ, F_SET / HZ], "holdSeconds": (NF - 1 - F_SET) / HZ},
                                  "contactsClipSeconds": contact_log, "contactAnkleErrMaxCm": round(contact_err, 2), "liftMinCm": LIFT_MIN_CM, "toeFloorCm": core.TOE_FLOOR_CM, "toeFloorFramesFixed": toe_fixed,
                                  "armRecoveryClipSeconds": [REC0 / HZ, REC1 / HZ], "wristPitchCorrectionDeg": [min(WRIST), max(WRIST)],
                                  "sources": ["Fab_Roll_v17", "Mixamo_Attack_v17", "IdleOneHand_Blender_v2r4 (animated end)"], "gripMode": "one-handed",
                                  "method": "round-3 composition up to the arm recovery; R4: world hips velocity ramped over %.2f s after the 1.0 s root-prefix end "
                                            "(attack carried by the resulting offset), outro from %.2f s toward the animated idle, hips settle (Hermite) to rest %.2f s "
                                            "before the end, every foot contact 0.62 s..outro locked in world space with >= %.0f cm swing lift, two lifted recovery steps"
                                            % (JOIN_DECEL_S, OUTRO_START, SETTLE_HOLD_S, LIFT_MIN_CM)}, NF - 1)

else:
    raise SystemExit("unknown stage %r (bodies | fit | cycles | retime | rollattack)" % stage)
