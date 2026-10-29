"""Knight fix round 3 (2026-10-29), headless Blender driver (no rendering, no window).

blender --background --factory-startup --python build_round3.py -- STAGE [NAMES]
Reuses the round-1/round-2 helpers. Every output is a new name in Local/FabRigTesting/Exports (v5 / v5c); approved
sources and every round-2 file are only read. StrafeLeft(2H) and the eight staggers are never touched.

Stages
  retarget   Mixamo "sword and shield crouch.fbx" onto the knight rig (hips travel kept: it is the squat's sit-back)
  bodies     blinks: 1H/2H idle frame 0 + additive crouch deltas (launch crouch, reversed for the landing) + authored lateral
             push/lean/pelvis yaw, feet planted on the idle stance throughout (root carries the travel only while hidden);
             sprint strafes: Mixamo strafe (4) forward run (and its sagittal mirror) with the pelvis turned to ~45 deg off
             travel, the spine carrying the rest so the chest faces the boss, ankles IK-held on the source foot paths
  fit        weapon fit (idle-root carry) of blinks / sprint strafes, 1H free-arm counter-swing (left_fn), raised guard
             backpedals with the hand at chest height and the blade off the face line (hilt_fn)
  cycles     loop closure (end-to-start residual spread over the cycle) and a cycle start at a slow phase (seam step below
             the in-cycle mean in all three bands, pose space); blinks: first/last frames pinned to the exact idle
  retime     sprint cycles resampled to fewer frames so their stance-foot speed matches the v030p capsule nominal
             (owner rule: never slow the character to fix sliding)
  rollattack round-2 roll + 0.60 s join unchanged; right arm recovers from the slash straight to the carry; recovery steps on
             linear time (lifted, >= 4 frames each), the planted foot locked
"""
import bpy, sys, json, math, hashlib
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion

HERE = Path(__file__).resolve().parent
R1 = HERE / "build_round1.py"
_g = {"__file__": str(R1), "__name__": "r1helpers"}
_src = R1.read_text().split('\nif stage == "retarget":')[0]
_saved = sys.argv
sys.argv = [sys.argv[0], "--", "none"]
exec(compile(_src, str(R1), "exec"), _g)
sys.argv = _saved
for _k in ("clear", "load", "basis_rows", "scale_rot", "smooth", "plant_legs", "key_rows", "FAB", "ROOT", "EXP", "KNIGHT", "SRC", "FPS", "ADDITIVE"):
    globals()[_k] = _g[_k]
args = sys.argv[sys.argv.index("--") + 1:]
stage, only = args[0], set(args[1:])
OWNER = "fable-knight-round3-20261029"
IDLE = {"": "IdleOneHand_Blender_v2r4.glb", "TwoHand": "IdleTwoHand_Blender_v2r4.glb"}
SPINE = (("Spine", .30), ("Spine1", .35), ("Spine2", .35))
HIDDEN = (.207, .391)        # blink hidden window in clip seconds (game 0.18-0.34 s of action time at rate 1.15)
BLINK_T = 0.70               # blink clip length the game expects (v030p)
Z = Vector((0, 0, 1))
FWD = Vector((0, -1, 0))     # knight forward (boss) in Blender armature space; +X = knight's left


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


def yaw_line(arm, a, b):
    """Facing yaw (deg) of the line a-b (left minus right joint): 0 = boss, + toward the knight's left."""
    pb = arm.pose.bones
    L = pb[a].head - pb[b].head
    f = Vector((L.y, -L.x, 0))
    return math.degrees(math.atan2(f.x, -f.y))


def chest_yaw(arm):
    return yaw_line(arm, "LeftArm", "RightArm")


def pelvis_yaw(arm):
    return yaw_line(arm, "LeftUpLeg", "RightUpLeg")


def rot_about(pbone, axis, deg, pivot=None):
    h = (pivot if pivot is not None else pbone.head).copy()
    pbone.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-h) @ pbone.matrix
    bpy.context.view_layer.update()


def key_all(arm, f, prev):
    for b in arm.pose.bones:
        q = b.rotation_quaternion.copy()
        if b.name in prev:
            q.make_compatible(prev[b.name])
        prev[b.name] = q.copy(); b.rotation_quaternion = q
        for prop in ("location", "rotation_quaternion", "scale"):
            b.keyframe_insert(prop, frame=f)


def new_action(arm, name):
    arm.animation_data_clear(); arm.animation_data_create(); arm.animation_data.action = bpy.data.actions.new(name)
    for b in arm.pose.bones:
        b.rotation_mode = "QUATERNION"


def set_row(arm, row):
    for b in arm.pose.bones:
        if b.name in row:
            loc, q, sc = row[b.name].decompose(); b.location, b.rotation_quaternion, b.scale = loc, q, sc
    bpy.context.view_layer.update()


def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def seg(t, keys):
    """Piecewise smoothstep through (time, value) keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return keys[-1][1]


def knee_hinge(arm, rows):
    """Per leg, the knee hinge normal (thigh x shin) in the thigh's local frame, from the source frame with the most bend."""
    pb = arm.pose.bones; best = {}
    for row in rows:
        set_row(arm, row)
        for sd in ("Left", "Right"):
            H, K, A = pb[sd + "UpLeg"].head, pb[sd + "Leg"].head, pb[sd + "Foot"].head
            n = (K - H).cross(A - K)
            if n.length > best.get(sd, (0, None))[0]:
                best[sd] = (n.length, pb[sd + "UpLeg"].matrix.to_3x3().normalized().inverted() @ n.normalized())
    return {sd: v[1] for sd, v in best.items()}


def plant_legs_pole(arm, targets, poles, reach=.98, hinge=None):
    """Analytic two-bone IK (armature space) with an explicit knee pole: the knee bends toward poles[side] (a direction,
    made perpendicular to hip->ankle), so a near-straight leg cannot flip its knee plane. Reach clamped to `reach`.
    With `hinge` (knee_hinge), the thigh is rolled about its own axis so its knee hinge lies in the new bend plane."""
    pb = arm.pose.bones
    for sd in ("Left", "Right"):
        up, leg, foot = pb[sd + "UpLeg"], pb[sd + "Leg"], pb[sd + "Foot"]
        T = targets[sd].to_translation()
        H, K, A = up.head.copy(), leg.head.copy(), foot.head.copy()
        a, b = (K - H).length, (A - K).length
        d = min(max((T - H).length, 1e-4), (a + b) * reach)
        u = (T - H).normalized()
        v = poles[sd] - u * poles[sd].dot(u)
        if v.length < 1e-5:
            v = (K - H) - u * (K - H).dot(u)
        v.normalize()
        ca = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
        K2 = H + a * (ca * u + math.sqrt(max(0.0, 1 - ca * ca)) * v)
        R1 = (K - H).rotation_difference(K2 - H).to_matrix().to_4x4()
        up.matrix = Matrix.Translation(H) @ R1 @ Matrix.Translation(-H) @ up.matrix
        bpy.context.view_layer.update()
        if hinge is not None:
            ax = (K2 - H).normalized(); want_n = ax.cross(T - K2)
            have_n = up.matrix.to_3x3().normalized() @ hinge[sd]
            pw = want_n - ax * want_n.dot(ax); ph = have_n - ax * have_n.dot(ax)
            if pw.length > 1e-6 and ph.length > 1e-6:
                pw.normalize(); ph.normalize()
                ang = math.atan2(ax.dot(ph.cross(pw)), ph.dot(pw))
                up.matrix = Matrix.Translation(H) @ Matrix.Rotation(ang, 4, ax) @ Matrix.Translation(-H) @ up.matrix
                bpy.context.view_layer.update()
        K, A = leg.head.copy(), foot.head.copy()
        R2 = (A - K).rotation_difference(T - K).to_matrix().to_4x4()
        leg.matrix = Matrix.Translation(K) @ R2 @ Matrix.Translation(-K) @ leg.matrix
        bpy.context.view_layer.update()
        _, rq, rs = targets[sd].decompose()
        foot.matrix = Matrix.LocRotScale(foot.head.copy(), rq, foot.matrix.to_scale())
        bpy.context.view_layer.update()


def needed_drop(arm, targets, reach=.98):
    """Hips drop (rig m) that brings both ankle targets within `reach` of the leg length."""
    pb = arm.pose.bones; need = 0.0
    for sd in ("Left", "Right"):
        H = pb[sd + "UpLeg"].head; T = targets[sd].to_translation()
        L = ((pb[sd + "Leg"].head - H).length + (pb[sd + "Foot"].head - pb[sd + "Leg"].head).length) * reach
        dv = H - T; h2 = dv.x * dv.x + dv.y * dv.y
        if h2 < L * L:
            need = max(need, dv.z - math.sqrt(L * L - h2))
    return max(0.0, need)


# ------------------------------------------------------------------------------------------------ blink authoring
# Clip-second keys (game time = clip / 1.15). Launch crouch 0-0.15 (>= 3 game frames), push 0.15-0.207, hidden
# 0.207-0.391 (travel), landing contact at 0.391, settle to exact idle by 0.62, idle hold to 0.70.
BLINK_KEYS = {
    "crouchFrame": [(0, 0.0), (.15, 9.0), (.207, 6.0), (.391, 8.5), (.62, 0.0)],     # crouch.fbx source frame (sourced shape)
    "crouchGain": [(0, .60), (.70, .60)],
    "leanDeg": [(0, 0.0), (.15, 5.0), (.207, 15.0), (.391, -9.0), (.62, 0.0)],        # + toward travel (about forward)
    "shiftM": [(0, 0.0), (.15, -.016), (.207, .034), (.391, .022), (.62, 0.0)],       # hips, + toward travel (rig m)
    "pelvisYawDeg": [(0, 0.0), (.15, 8.0), (.207, 18.0), (.391, 10.0), (.62, 0.0)],   # + toward travel; spine counters 85%
    "armLead": [(0, 0.0), (.15, .35), (.207, 1.0), (.391, -.8), (.62, 0.0)],          # free hand toward travel (x0.08 rig m)
}
SPINE_LEAN = (("Hips", .30), ("Spine", .25), ("Spine1", .25), ("Spine2", .20))


def blink_params(t):
    return {k: seg(t, v) for k, v in BLINK_KEYS.items()}


# ------------------------------------------------------------------------------------------------ stages
if stage == "retarget":
    rg = {"__file__": str(FAB / "retarget.py")}
    exec(compile((FAB / "retarget.py").read_text(), str(FAB / "retarget.py"), "exec"), rg)
    rg["render"] = lambda *a, **k: None  # no review render here (GPU slot rule); renders are made by render_review.py
    for name, fbx, travel, mirror, why in [("Mixamo_Crouch_v1", "sword and shield crouch.fbx", True, False,
                                            "stand-to-crouch transition; frames 0-9 base the blink launch crouch and (reversed) the landing")]:
        if not want(name):
            continue
        bpy.context.scene["session_owner"] = rg["OWNER"]
        rg["run"](SRC / fbx, "mixamo", name, travel, mirror)
        rep = EXP / (name + ".json"); d = json.loads(rep.read_text()); d["classification"] = why; rep.write_text(json.dumps(d, indent=2))
        print("RETARGETED", name, flush=True)

elif stage == "bodies":
    report = {}
    # ---- blinks
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):
        for grip, base_file in IDLE.items():
            name = "Knight_Blink%s%sBody_v5" % (side, grip)
            if not want(name):
                continue
            s = clear()
            n = int(round(BLINK_T * FPS))
            times = [i / FPS for i in range(n + 1)]
            P = [blink_params(t) for t in times]
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
                for bn, frac in SPINE_LEAN:  # lean toward travel about the forward axis (+Y rotation tilts up toward +X)
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
            export(base, base_body, name, {"fps": FPS, "duration": n / FPS, "base": base_file, "travelSign": sgn, "keys": BLINK_KEYS,
                                           "sources": {"Mixamo_Crouch_v1": "sword and shield crouch.fbx frames 0-9, additive (hips, spine, neck, head, clavicles) x0.60; forward for the launch, reversed for the landing"},
                                           "authored": "lateral hip shift, lean, pelvis yaw (spine counter 85%), timing around the game's hidden window; feet planted on the idle stance (analytic IK)",
                                           "hiddenWindowClipSeconds": HIDDEN, "frames": log}, n)
    # ---- sprint strafes
    for out, src in (("Knight_StrafeRunRightBody_v5", "Mixamo_StrafeRunRight_v1"), ("Knight_StrafeRunLeftBody_v5", "Mixamo_StrafeRunLeftM_v1")):
        if not want(out):
            continue
        s = clear(); arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text()); n = int(round(meta["duration"] * FPS))
        rows = basis_rows(arm, range(n + 1)); pb = arm.pose.bones
        new_action(arm, out)
        Ps, Cs, feet = [], [], []
        for row in rows:
            set_row(arm, row); Ps.append(pelvis_yaw(arm)); Cs.append(chest_yaw(arm))
            feet.append({sd: pb[sd + "Foot"].matrix.copy() for sd in ("Left", "Right")})
        Pm, Cm = sum(Ps) / len(Ps), sum(Cs) / len(Cs); sgn = 1.0 if Pm > 0 else -1.0
        best = None
        for pel in [45 - .5 * i for i in range(21)]:
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
        FOOT_K = .5
        REACH = .98
        HINGE = knee_hinge(arm, rows)

        def posed(f):
            """Source frame f with the hips turned and the chest re-aimed; returns ankle targets and knee poles."""
            set_row(arm, rows[f])
            hp = pb["Hips"]; rot_about(hp, Z, d1)
            want_c = sgn * ch + alpha * (Cs[f] - Cm)
            for _ in range(3):
                d2 = want_c - chest_yaw(arm)
                for bn, frac in SPINE:
                    rot_about(pb[bn], Z, d2 * frac)
            L = pb["LeftUpLeg"].head - pb["RightUpLeg"].head
            pf = Vector((L.y, -L.x, 0)).normalized()       # pelvis forward
            tg, poles = {}, {}
            for sd in ("Left", "Right"):
                m = feet[f][sd]; qf = Quaternion(Z, math.radians(d1 * FOOT_K))
                tg[sd] = Matrix.LocRotScale(m.to_translation(), qf @ m.to_quaternion(), Vector((1, 1, 1)))
                # knee pole = the sourced knee offset (turned with the hips) plus 5 cm of pelvis-forward, so a bent source
                # knee keeps its own direction and a near-straight one falls back smoothly to pelvis-forward
                H, K, A = pb[sd + "UpLeg"].head, pb[sd + "Leg"].head, pb[sd + "Foot"].head
                dd = (A - H).normalized(); off = (K - H) - dd * (K - H).dot(dd)
                poles[sd] = off + pf * .05
            return tg, poles
        # pass 1: hips drop each frame needs to keep both legs at <= 98% reach; dilate +-3 frames (cyclic) and smooth
        need, P1 = [], []
        for f in range(n + 1):
            tg, po = posed(f); need.append(needed_drop(arm, tg, REACH)); P1.append(po)
        # poles smoothed over +-2 frames (cyclic)
        PS = [{sd: sum((P1[(i + k) % n][sd] * wk for k, wk in ((-2, 1), (-1, 2), (0, 3), (1, 2), (2, 1))), Vector()) / 9 for sd in ("Left", "Right")} for i in range(n)]
        PS.append(PS[0])
        cyc = need[:n]
        h2 = n / 2.0  # one step = half a cycle: both steps get the same hips path (no once-per-cycle limp)
        cyc = [max(cyc[i], cyc[int(math.floor(i + h2)) % n] * (1 - (h2 % 1)) + cyc[int(math.ceil(i + h2)) % n] * (h2 % 1),
                   cyc[int(math.floor(i - h2)) % n] * (h2 % 1) + cyc[int(math.ceil(i - h2)) % n] * (1 - (h2 % 1))) for i in range(n)]
        dil = [max(cyc[(i + k) % n] for k in range(-3, 4)) for i in range(n)]
        for _ in range(2):
            dil = [(dil[(i - 1) % n] + 2 * dil[i] + dil[(i + 1) % n]) / 4 for i in range(n)]
        dil = [max(x, y) for x, y in zip(dil, cyc)]
        drops = dil + [dil[0]]
        prev = {}; log = []
        for f in range(n + 1):
            tg, _ = posed(f); poles = PS[f]
            hp = pb["Hips"]; hp.matrix = Matrix.Translation(Vector((0, 0, -drops[f]))) @ hp.matrix; bpy.context.view_layer.update()
            plant_legs_pole(arm, tg, poles, REACH, HINGE)
            err = max((pb[sd + "Foot"].head - tg[sd].to_translation()).length for sd in tg); drop = drops[f]
            kn = []
            for sd in ("Left", "Right"):
                Hh, Kk, Aa = pb[sd + "UpLeg"].head, pb[sd + "Leg"].head, pb[sd + "Foot"].head
                kn.append(round(math.degrees((Kk - Hh).angle(Aa - Kk)), 1))
            key_all(arm, f, prev)
            log.append({"f": f, "pelvis": round(pelvis_yaw(arm), 1), "chest": round(chest_yaw(arm), 1), "ankleErrCm": round(err * 240, 2),
                        "hipsDropCm": round(drop * 240, 2), "kneeBendDeg": kn})
        report[out] = {"source": src, "sourcePelvisMean": round(Pm, 1), "sourceChestMean": round(Cm, 1), "pelvisYawFromBossDeg": pel, "pelvisOffTravelDeg": 90 - pel,
                       "chestTarget": sgn * ch, "chestSwingKept": alpha, "predictedTwistMax": round(tw_pred, 1), "predictedChestMax": round(cmax_pred, 1), "frames": log}
        print("RUNBODY", out, {k: v for k, v in report[out].items() if k != "frames"}, flush=True)
        export(arm, body, out, {"fps": FPS, "duration": n / FPS, "source": src, "method":
                                "whole body turned about the hips to put the pelvis %.1f deg off the boss (about 45 deg off travel); spine (30/35/35%%) "
                                "brings the chest to %.1f deg + %.0f%% of the source shoulder swing; ankles IK-held on the source foot paths, feet turned "
                                "half the hip turn, knees posed toward the sourced knee direction turned with the hips, + 5 cm pelvis-forward (explicit smoothed IK pole, 98%% reach, smoothed hips drop); timing unchanged" % (pel, sgn * ch, alpha * 100), "twist": {k: v for k, v in report[out].items() if k != "frames"}}, n)
    rp = EXP / "round3-bodies-report.json"
    old = json.loads(rp.read_text()) if rp.exists() else {}
    rp.write_text(json.dumps(dict(old, **report), indent=1))

elif stage == "fit":
    fg = {"__file__": str(FAB / "fit_weapon.py")}
    exec(compile((FAB / "fit_weapon.py").read_text(), str(FAB / "fit_weapon.py"), "exec"), fg)
    bpy.context.scene["session_owner"] = fg["OWNER"]
    refs = {"one": fg["reference"]("IdleOneHand_Blender_v2r4.glb"), "two": fg["reference"]("IdleTwoHand_Blender_v2r4.glb"),
            "guard": fg["reference"]("GuardReadyTwoHand_Blender_v4r4.glb", True)}

    def chest_frame(ch, ref):
        fr = (ch.to_quaternion() @ ref["ch"].to_quaternion().inverted()) @ FWD; fr.z = 0; fr.normalize()
        return fr, Vector((fr.y, -fr.x, 0))  # knight's right = fr x up

    def run_swing(sgn, amp=.075):
        travel = Vector((sgn, 0, 0))
        cache = {}

        def fn(f, N, source, ch, hand):
            if "s" not in cache:
                d = [((source[i]["RightFoot"].translation - source[i]["LeftFoot"].translation).dot(travel)) for i in range(N + 1)]
                lo, hi = min(d), max(d); mid = (lo + hi) / 2; half = max(1e-6, (hi - lo) / 2)
                cache["s"] = [(x - mid) / half for x in d]
            sw = cache["s"][f]  # +1 when the right foot leads toward travel: the left arm swings toward travel
            out = hand.copy(); out.translation += travel * amp * sw + Vector((0, 0, .022 * sw * sw)) + FWD * (.015 * abs(sw))
            return out
        return fn

    def blink_swing(sgn, amp=.08):
        travel = Vector((sgn, 0, 0))

        def fn(f, N, source, ch, hand):
            t = f / N * BLINK_T; a = seg(t, BLINK_KEYS["armLead"])
            out = hand.copy(); out.translation += travel * amp * a + Vector((0, 0, .05 * abs(a))) + FWD * (.03 * abs(a))
            return out
        return fn

    def guard_hilt(two):
        # Hand at chest height in front of the right pectoral; blade up, out to the knight's right and forward, so the
        # flat never crosses the helmet seen from the boss (front view).
        hand_off = (.20, .08, -.05) if two else (.17, .09, -.03)       # forward, right, up from Spine2 head (rig m)
        aim = (.40, .50, .77) if two else (.40, .45, .80)              # forward, right, up blade direction

        def fn(f, N, src, H, ref, grip, hscale):
            ch = src["Spine2"]; fr, rt = chest_frame(ch, ref)
            hand = ch.translation + fr * hand_off[0] + rt * hand_off[1] + Z * hand_off[2]
            d = (fr * aim[0] + rt * aim[1] + Z * aim[2]).normalized()
            q0 = ref["h"].to_quaternion(); b0 = q0 @ Vector((0, 1, 0))
            q = b0.rotation_difference(d) @ q0
            Hn = Matrix.LocRotScale(hand, q, hscale); Hn.translation -= Hn.to_3x3() @ grip["Right"].translation
            return Hn
        return fn

    jobs = []  # out, src, grip, mode, kwargs
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):
        for grip in ("", "TwoHand"):
            kw = {} if grip else {"left_fn": run_swing(sgn)}
            jobs.append(("Knight_StrafeRun%s%s_v5" % (side, grip), "Knight_StrafeRun%sBody_v5" % side, grip, "idle-root", kw))
            kw = {"follow": .45} if grip else {"follow": .45, "left_fn": blink_swing(sgn)}
            jobs.append(("Knight_Blink%s%s_v5" % (side, grip), "Knight_Blink%s%sBody_v5" % (side, grip), grip, "idle-root", kw))
    jobs.append(("Knight_BackpedalGuard_v5", "Knight_BackpedalGuardBody_v4", "", "idle", {"hilt_fn": guard_hilt(False)}))
    jobs.append(("Knight_BackpedalGuardTwoHand_v5", "Knight_BackpedalGuardBody_v4", "TwoHand", "idle", {"hilt_fn": guard_hilt(True)}))
    for out, src, grip, mode, kw in jobs:
        if not want(out):
            continue
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        bpy.context.scene["session_owner"] = fg["OWNER"]
        fg["fit"]("walk", refs, "v5", "two" if grip else "one", out, src, mode, (0., 0.), **kw)
        d = json.loads((EXP / (out + ".json")).read_text()); d["round3"] = {k: (v if not callable(v) else v.__qualname__) for k, v in kw.items()}
        (EXP / (out + ".json")).write_text(json.dumps(d, indent=2))
        print("FITTED", out, flush=True)

elif stage == "cycles":
    HZ = 120
    s = clear(); a0, _, o0 = load(KNIGHT / IDLE[""]); s.frame_set(0)
    d0 = a0.pose.bones["LeftFoot"].head - a0.pose.bones["RightFoot"].head; d0.z = 0; IDLE_ANKLE = d0.length
    BANDS = {"headChest": ["Head", "Neck", "Spine2", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm"],
             "hipsSword": ["Hips", "Spine", "LeftUpLeg", "RightUpLeg", "LeftHand", "RightHand", "LeftForeArm", "RightForeArm", "#tip", "#base"],
             "legsFeet": ["LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"]}
    LOOPS = [("Knight_StrafeRight_v4", "Knight_StrafeRight_v5c", 1.2), ("Knight_StrafeRightTwoHand_v4", "Knight_StrafeRightTwoHand_v5c", 1.2)]
    for side in ("Left", "Right"):
        for grip in ("", "TwoHand"):
            LOOPS.append(("Knight_StrafeRun%s%s_v5" % (side, grip), "Knight_StrafeRun%s%s_v5c" % (side, grip), 1.1))
    LOOPS += [("Knight_BackpedalGuard_v5", "Knight_BackpedalGuard_v5c", 1.668), ("Knight_BackpedalGuardTwoHand_v5", "Knight_BackpedalGuardTwoHand_v5c", 1.668)]
    rep = {}

    def pose_points(arm):
        pb = arm.pose.bones; P = {}
        for b in pb:
            P[b.name] = b.head.copy()
        so = pb["WeaponSocket"].matrix
        P["#tip"] = so @ Vector((0, 2.35, 0)); P["#base"] = so @ Vector((0, .6, 0))
        return P

    for src, out, rate in LOOPS:
        if not want(out) or (EXP / (out + ".glb")).exists():
            continue
        s = clear(); s.render.fps = HZ
        arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
        rows = basis_rows(arm, range(n + 1))
        # 1. closure: spread the end-to-start residual linearly over the cycle (frame n becomes frame 0 exactly)
        resid = {}
        closed = []
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
        # 2. pose-space speeds per 120 Hz step (rig m), and ankle widths
        arm.animation_data_clear()
        pts, widths = [], []
        for r in closed[:n]:
            set_row(arm, r); P = pose_points(arm); pts.append(P)
            d = P["LeftFoot"] - P["RightFoot"]; d.z = 0; widths.append(d.length)
        nr = max(8, int(round(T / rate * 30)))  # rendered frames per cycle at the in-game rate (even phase sampling)
        stride = n / nr

        def band_step(a, b, band):
            return sum((pts[b % n][j] - pts[a % n][j]).length for j in BANDS[band]) / len(BANDS[band])
        # step of one rendered frame ending at phase i (from i - stride), averaged over the cycle
        steps = {bd: [band_step(int(round(i - stride)), i, bd) for i in range(n)] for bd in BANDS}
        mean = {bd: sum(v) / n for bd, v in steps.items()}
        cand = []
        for i in range(n):
            ratio = max(steps[bd][i] / mean[bd] for bd in BANDS)
            cand.append((ratio, abs(widths[i] - IDLE_ANKLE), i))
        good = [c for c in cand if c[0] <= .80] or [c for c in cand if c[0] <= .92]
        pick = min(good, key=lambda c: (c[1], c[0])) if good else min(cand)
        i0 = pick[2]
        rot = [closed[(i0 + i) % n] for i in range(n + 1)]
        key_rows(arm, rot, out)
        m2 = dict(meta, fps=HZ, bakeSampleRate=HZ, derivedFrom=src, cycleStartShiftSeconds=i0 / HZ, startAnkleMetres=widths[i0], idleAnkleMetres=IDLE_ANKLE,
                  closureResidualMax={"locCm": round(max(v[0] for v in resid.values()) * 240, 3), "rotDeg": round(max(v[1] for v in resid.values()), 3)},
                  seamChoice={"renderFramesPerCycle": nr, "stepRatioToMeanMaxBand": round(pick[0], 3), "bandMeansCm": {k: round(v * 240, 2) for k, v in mean.items()}},
                  method="loop closure (end-to-start residual spread linearly) then cycle start at the phase whose one-render-frame step is <= 0.80 (else <= 0.92) of the in-cycle mean in every band, nearest the idle ankle width; else the lowest ratio")
        m2.pop("sha256", None)
        export(arm, body, out, m2, n)
        rep[out] = {"shift": i0 / HZ, "ratio": round(pick[0], 3), "ankleCm": round(widths[i0] * 240, 1), "closure": m2["closureResidualMax"]}
        print("CYCLE", out, rep[out], flush=True)
    # blinks: pin the first and last frames to the exact idle (fit IK leaves sub-cm arm differences), keep the rest
    for side in ("Left", "Right"):
        for grip in ("", "TwoHand"):
            src, out = "Knight_Blink%s%s_v5" % (side, grip), "Knight_Blink%s%s_v5c" % (side, grip)
            if not want(out) or (EXP / (out + ".glb")).exists():
                continue
            s = clear(); s.render.fps = HZ
            ia, _, io = load(KNIGHT / IDLE[grip]); s.frame_set(0)
            idle = {b.name: b.matrix_basis.copy() for b in ia.pose.bones}
            for o in io:
                bpy.data.objects.remove(o, do_unlink=True)
            arm, body, objs = load(EXP / (src + ".glb"))
            meta = json.loads((EXP / (src + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
            rows = basis_rows(arm, range(n + 1))

            def mixm(a, b, u):
                x, q, sc = a.decompose(); y, r, ss = b.decompose()
                if q.dot(r) < 0:
                    r = -r
                return Matrix.LocRotScale(x.lerp(y, u), q.slerp(r, u), sc.lerp(ss, u))
            out_rows = []
            for i, row in enumerate(rows):
                t = i / HZ
                w = 1.0 - ease(t / .05) if t < .05 else (ease((t - .58) / .04) if t >= .58 else 0.0)  # weight of the exact idle
                out_rows.append({bn: mixm(m, idle[bn], w) if bn in idle else m for bn, m in row.items()})
            key_rows(arm, out_rows, out)
            m2 = dict(meta, fps=HZ, derivedFrom=src, idlePinned="exact idle frame 0 at t=0 (fading out by 0.05 s) and from 0.62 s (fading in over 0.58-0.62 s)")
            m2.pop("sha256", None)
            export(arm, body, out, m2, n)
    print("CYCLES", json.dumps(rep), flush=True)

elif stage == "retime":
    # Owner rule "never slow the character to fix sliding": the lock-on sprint capsule speed stays at v030p
    # (nominal 453.4 L / 456.9 R). The sprint cycles are resampled (same poses, same phase order, fewer 120 Hz frames)
    # so the clip's own stance-foot speed matches that nominal. args: OUT=TARGET@SOURCE_SPEED (cm/s; source speed =
    # measure_locomotion rawStanceSpeedMedian x 240 of the _v5c file).
    HZ = 120
    for spec in sorted(only):
        out, rest = spec.split("="); tgt, have = map(float, rest.split("@")); src = out.replace("_v5r", "_v5c")
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
                  "why": "owner rule: never slow the character to fix sliding; v030p sprint capsule speed kept, clip retimed to match it"})
        m2.pop("sha256", None)
        export(arm, body, out, m2, m)
        print("RETIMED", out, n, "->", m, "frames", round(have * n / m, 2), "cm/s vs", tgt, flush=True)

elif stage == "rollattack":
    name = "Sourced_RollAttack_v5"
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
    s.frame_set(0)
    I = {b.name: b.matrix.copy() for b in idl.pose.bones}
    for o in list(att_objs) + list(idl_objs):
        bpy.data.objects.remove(o, do_unlink=True)
    off = R[-1]["Hips"].translation - A[0]["Hips"].translation; off.z = 0
    JOIN, OUTRO = int(.60 * HZ), int(.42 * HZ)

    def mixm(a, b, u):
        x, q, sc = a.decompose(); y, r, ss = b.decompose()
        if q.dot(r) < 0:
            r = -r
        return Matrix.LocRotScale(x.lerp(y, u), q.slerp(r, u), sc.lerp(ss, u))

    def smoother(x):
        x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)

    def grip_of(p):
        return p["RightHand"].inverted() @ p["WeaponSocket"]
    frames, grips, outro_u = [], [], []
    gR, gI = grip_of(R[-1]), grip_of(I)
    T_GRIP = gI.translation.copy()
    for f in range(301 + len(A) - 1):  # identical to round 2 (roll, join, outro body blend)
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
        end = len(A) - 1; uo = 0.0
        if j >= end - OUTRO:
            uo = smoother((j - (end - OUTRO)) / OUTRO)
            hip_off = a["Hips"].translation - I["Hips"].translation; hip_off.z = 0
            tgt = {n: Matrix.Translation(hip_off) @ m for n, m in I.items()}
            a = {n: mixm(m, tgt[n], uo) if n in tgt and n != "VeyrRoot" else m for n, m in a.items()}
            g = mixm(g, gI, uo)
        frames.append(a); grips.append(g); outro_u.append(uo)
    NF = len(frames)
    # ---- round 3: right arm recovers from the slash straight to the carry (after the damage window, 1.36-1.576 s)
    ARM = ["RightShoulder", "RightArm", "RightForeArm", "RightHand"]
    PARENT = {"RightShoulder": "Spine2", "RightArm": "RightShoulder", "RightForeArm": "RightArm", "RightHand": "RightForeArm"}
    REC0, REC1 = int(round(1.60 * HZ)), int(round(2.10 * HZ))

    def local(p, bn):
        return p[PARENT[bn]].inverted() @ p[bn]
    L0 = {bn: local(frames[REC0], bn) for bn in ARM}; G0 = grips[REC0]
    LI = {bn: local(I, bn) for bn in ARM}
    PALL = {b.name: b.parent.name for b in roll.pose.bones if b.parent}
    HAND_KIDS = []  # RightHand descendants (fingers), parent before child

    def kids(n):
        for c, par in PALL.items():
            if par == n:
                HAND_KIDS.append(c); kids(c)
    kids("RightHand")
    for f in range(REC0, NF):
        w = smoother((f - REC0) / (REC1 - REC0))
        p = dict(frames[f]); old = frames[f]
        for bn in ARM:  # parent before child
            p[bn] = p[PARENT[bn]] @ mixm(L0[bn], LI[bn], w)
        for bn in HAND_KIDS:  # fingers keep their locals on the moved hand
            p[bn] = p[PALL[bn]] @ (old[PALL[bn]].inverted() @ old[bn])
        frames[f] = p; grips[f] = mixm(G0, gI, w)
    # blade pitch goes monotonically from the follow-through to the carry: a wrist correction about the horizontal axis
    # (blade x up) removes the dip the local-space arm slerp produces mid-recovery; zero at both ends by construction
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
    # ---- round 3: recovery steps on linear time; the other foot is locked in place while one steps
    o0 = next(i for i, u in enumerate(outro_u) if u > 0) - 1
    moves = {sd: (frames[-1][sd + "Foot"].translation - frames[o0][sd + "Foot"].translation).length for sd in ("Left", "Right")}
    step_foot = max(moves, key=moves.get); other = "Right" if step_foot == "Left" else "Left"
    STEPS = ((step_foot, o0, o0 + int(round(.19 * HZ)), .06), (other, o0 + int(round(.20 * HZ)), o0 + int(round(.39 * HZ)), .05))
    plant0 = {sd: frames[o0][sd + "Foot"].copy() for sd in ("Left", "Right")}
    plant1 = {sd: frames[-1][sd + "Foot"].copy() for sd in ("Left", "Right")}
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
    prev = {}
    pb = arm.pose.bones
    for f, pose in enumerate(frames):
        for b in order:
            if b.name in pose and b.name != "WeaponSocket":
                b.matrix = pose[b.name]; bpy.context.view_layer.update()
        if f > o0:
            tg = {}
            for sd, a, b_, h in STEPS:
                w = max(0.0, min(1.0, (f - a) / (b_ - a)))
                m = mixm(plant0[sd], plant1[sd], smooth(w))
                tg[sd] = Matrix.Translation(Vector((0, 0, h * math.sin(math.pi * w)))) @ m
            plant_legs(arm, tg)
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
                                  "joinSeconds": JOIN / HZ, "outroSeconds": OUTRO / HZ, "stepFoot": step_foot,
                                  "steps": [{"foot": sd, "clipSeconds": [round(a / HZ, 3), round(b_ / HZ, 3)], "liftRigM": h} for sd, a, b_, h in STEPS],
                                  "armRecoveryClipSeconds": [REC0 / HZ, REC1 / HZ], "wristPitchCorrectionDeg": [min(WRIST), max(WRIST)],
                                  "sources": ["Fab_Roll_v17", "Mixamo_Attack_v17", "IdleOneHand_Blender_v2r4 (end pose)"], "gripMode": "one-handed",
                                  "method": "round-2 composition unchanged up to 1.60 s (roll, 0.60 s join, slash and damage window); right arm chain and "
                                            "grip slerp from their 1.60 s locals to the idle carry over 1.60-2.10 s (no second wind-up), wrist corrected so the blade pitch rises monotonically to the carry; two sequential "
                                            "lifted recovery steps on linear time, the other foot locked while one steps; WeaponSocket = RightHand x grip"}, NF - 1)
