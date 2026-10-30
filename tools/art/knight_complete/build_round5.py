"""Knight fix round 5 (2026-10-30), headless Blender driver (no rendering, no window).

blender --background --factory-startup --python build_round5.py -- STAGE [--tag TAG]
python3 build_round5.py --dry                 plain CPython: inputs/outputs and the roll / blink timelines

Targets: critique-round4.md (RollAttack veto + blink toe-off note) and the engine blend proof
(blendproof-footgate-diagnosis.md section 5, items 4-5). Reuses the round-1/3/4 helpers (exec'd). Every output is a NEW
name in Local/FabRigTesting/Exports; export() refuses to overwrite. Only RollAttack and the four blinks change.

Stages
  rollattack  Sourced_RollAttack_v7 from the same sources as v6 (Fab_Roll_v17 + Mixamo_Attack_v17 + animated idle) with
              the round-4 composition up to the strike (roll, 0.60 s join, join velocity ramp with the 15 cm carry, slash,
              damage window unchanged) and round 5:
              (1) footstep plan from the roll landing to the end (r5_core): the rear (Right) foot touches down from the
                  roll on its FINAL idle spot and never moves again; the front (Left) foot plants after the roll, makes
                  one lifted lunge step that lands with the strike (rendered f32) and is locked through the slash, then
                  one lifted step back (rendered f39-50) that moves horizontally only while the ankle is >= ~15 cm up.
                  Plants are full foot matrices (no slide, no toe roll); a smoothed hips drop keeps both targets within
                  99 % of the leg length.
              (2) one recovery from 1.58 s to 2.15 s (rendered f37-50, r4: a 4-frame pop): body blend to the animated
                  idle, right-arm recovery, wrist pitch and the hips settle all share one smoothstep progress.
  blinkfeet   Knight_Blink*_v7c from the round-4 v6c clips: every 120 Hz key's legs re-solved so the feet sit on the
              idle stance (removes the 6-12 cm floor dips the round-4 120 Hz resample left between the 30 Hz authoring
              keys, incl. the blend proof's BlinkLeft 0.38-0.40 s pop), plus a heel lift about the planted toe joint on
              the push frames (toe-off). Hips, spine, arms, sword, crouch depth, tail and first/last frames: unchanged.
"""
import sys, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r4_core as core  # noqa: E402
import r5_core as c5  # noqa: E402

ROOT = HERE.parents[2]
EXP = ROOT / "Local/FabRigTesting/Exports"
KNIGHT = ROOT / "Local/CustomuseAssets/Polish20261025/knight"
OWNER5 = "fable-knight-round5-20261030"
BLINKS = ["Blink%s%s" % (s, g) for s in ("Left", "Right") for g in ("", "TwoHand")]


def outputs(tag=""):
    return {"rollattack": ["Sourced_RollAttack_v7" + tag], "blinkfeet": ["Knight_%s_v7c%s" % (b, tag) for b in BLINKS]}


def inputs():
    return {"rollattack": ["Fab_Roll_v17.glb", "Mixamo_Attack_v17.glb"], "blinkfeet": ["Knight_%s_v6c.glb" % b for b in BLINKS]}


if __name__ == "__main__" and "--dry" in sys.argv:
    try:
        import bpy  # noqa: F401
    except ImportError:
        ok = True
        for st, names in outputs().items():
            for f in inputs()[st]:
                print("INPUT", st, f, "ok" if (EXP / f).exists() else "MISSING"); ok &= (EXP / f).exists()
            for n in names:
                print("OUTPUT", st, n, "EXISTS" if (EXP / (n + ".glb")).exists() else "free")
        rate = core.ROLL_RATE
        print("ROLL recovery %.3f-%.3f s = rendered f%.1f-f%.1f; steps:" % (c5.REC_START, c5.REC_END, c5.REC_START / rate * 30, c5.REC_END / rate * 30))
        for a, b, H, lo, hi in c5.STEPS_LEFT:
            print("  Left step %.3f-%.3f s = f%.1f-f%.1f, lift %.0f cm, horizontal over u %.2f-%.2f" % (a, b, a / rate * 30, b / rate * 30, H, lo, hi))
            print("   ", [(round(u, 2),) + tuple(round(x, 2) for x in c5.step_shape(u, lo, hi, H)) for u in [i / 10 for i in range(11)]])
        print("BLINK toe-off deg at rendered frames:", [(round(t, 3), round(c5.seg(t, c5.TOE_OFF_DEG), 1)) for t in core.rendered_times()])
        sys.exit(0 if ok else 1)

import bpy  # noqa: E402
from mathutils import Matrix, Vector, Quaternion  # noqa: E402

# round-1/3/4 helpers: exec build_round4.py up to its stage dispatch
R4 = HERE / "build_round4.py"
_g = {"__file__": str(R4), "__name__": "r4helpers"}
_src = R4.read_text().split("\n# ------------------------------------------------------------------------------------------------ stages\n")[0]
_saved = sys.argv
sys.argv = [sys.argv[0], "--", "none"]
exec(compile(_src, str(R4), "exec"), _g)
sys.argv = _saved
_g["OWNER"] = OWNER5
for _k in ("clear", "load", "basis_rows", "scale_rot", "plant_legs", "key_rows", "FPS", "set_row", "Z", "export", "mixm", "T3", "IDLE"):
    globals()[_k] = _g[_k]
args = sys.argv[sys.argv.index("--") + 1:]
stage = args[0]
TAG = args[args.index("--tag") + 1] if "--tag" in args else ""


def smooth(x):
    return core.smooth(x)


def _blade_pts():
    import struct
    raw = (ROOT / "Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb").read_bytes()
    n = struct.unpack_from("<I", raw, 12)[0]; doc = json.loads(raw[20:20 + n]); blob = raw[28 + n:]
    a = doc["accessors"][doc["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]; v = doc["bufferViews"][a["bufferView"]]
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    pts = [struct.unpack_from("<3f", blob, off + 12 * i) for i in range(a["count"])]
    return [p_ for p_ in pts if p_[1] > .55][::6]


BLADE_PTS = _blade_pts()


# ================================================================================================ roll attack
if stage == "rollattack":
    name = "Sourced_RollAttack_v7" + TAG
    assert not (EXP / (name + ".glb")).exists(), name
    from r4_core import JOIN_T, JOIN_DECEL_S, ROLL_RATE  # noqa: E402
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
    o_start = int(round(c5.REC_START * HZ)); F_SET = int(round(c5.REC_END * HZ))
    IT = {}
    for f in range(o_start, NF):  # as r4: the recovery blends toward the ANIMATED idle, reaching idle frame 0 at the clip end
        tau = core.idle_tail_time(f / HZ, T_END, ROLL_RATE, idle_T)
        s.frame_set(int(math.floor(tau * FPS)), subframe=tau * FPS - math.floor(tau * FPS))
        IT[f] = {b.name: b.matrix.copy() for b in idl.pose.bones}
    s.frame_set(0)
    I = {b.name: b.matrix.copy() for b in idl.pose.bones}
    IT[NF - 1] = I
    for o in list(att_objs) + list(idl_objs):
        bpy.data.objects.remove(o, do_unlink=True)
    off = R[-1]["Hips"].translation - A[0]["Hips"].translation; off.z = 0
    JOIN = int(.60 * HZ)

    def grip_of(p):
        return p["RightHand"].inverted() @ p["WeaponSocket"]
    frames, grips = [], []
    gR, gI = grip_of(R[-1]), grip_of(I)
    T_GRIP = gI.translation.copy()
    for f in range(NF):  # round-2/3/4 composition; R5: one smoothstep recovery 1.58-2.15 s toward the animated idle
        if f <= 300:
            frames.append(R[f]); grips.append(grip_of(R[f])); continue
        j = f - 300
        a = {n: Matrix.Translation(off) @ m for n, m in A[j].items()}
        g = grip_of(A[j])
        if j <= JOIN:
            u = core.smoother(j / JOIN)
            ext = {}
            for n in a:
                if n in R[-1]:
                    l1, q1, s1 = R[-2][n].decompose(); l2, q2, s2 = R[-1][n].decompose()
                    steps = min(j, 12) * (1 - u)
                    ext[n] = Matrix.LocRotScale(l2 + (l2 - l1) * steps, q2 @ scale_rot(q1.inverted() @ q2, steps), s2)
            a = {n: mixm(ext[n], m, u) if n in ext else m for n, m in a.items()}
            g = mixm(gR, g, u)
        if f >= o_start:
            uo = c5.progress(f / HZ)
            hip_off = a["Hips"].translation - I["Hips"].translation; hip_off.z = 0
            tgt = {n: Matrix.Translation(hip_off) @ m for n, m in IT[f].items()}
            a = {n: mixm(m, tgt[n], uo) if n in tgt and n != "VeyrRoot" else m for n, m in a.items()}
            g = mixm(g, gI, uo)
        frames.append(a); grips.append(g)
    # ---- right arm recovers from the slash to the carry (r3 method) on the shared progress; wrist keeps the blade pitch monotonic
    ARM = ["RightShoulder", "RightArm", "RightForeArm", "RightHand"]
    PARENT = {"RightShoulder": "Spine2", "RightArm": "RightShoulder", "RightForeArm": "RightArm", "RightHand": "RightForeArm"}
    REC0 = o_start

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
        w = c5.progress(f / HZ)
        p = dict(frames[f]); old = frames[f]
        for bn in ARM:
            p[bn] = p[PARENT[bn]] @ mixm(L0[bn], LI[bn], w)
        for bn in HAND_KIDS:
            p[bn] = p[PALL[bn]] @ (old[PALL[bn]].inverted() @ old[bn])
        frames[f] = p; grips[f] = mixm(G0, gI, w)

    def blade_of(f):
        gl, gq, gs = grips[f].decompose(); so = frames[f]["RightHand"] @ Matrix.LocRotScale(T_GRIP, gq, gs)
        return (so.to_3x3() @ Vector((0, 1, 0))).normalized()
    # R5: the blade DIRECTION follows a great-circle sweep from its post-strike direction to the carry on the shared
    # progress (r4 corrected only the pitch, so the blade swung across the body in ~4 frames); the hand turns about the
    # wrist by the remaining difference (logged: max wrist correction)
    b0, bE = blade_of(REC0), blade_of(NF - 1)
    ax0 = b0.cross(bE); th0 = math.atan2(ax0.length, b0.dot(bE))
    ax0 = ax0.normalized() if ax0.length > 1e-9 else Vector((0, 0, 1))
    WRIST = []
    for f in range(REC0, NF):
        tgt = (Matrix.Rotation(th0 * c5.progress(f / HZ), 3, ax0) @ b0).normalized(); cur = blade_of(f)
        q = cur.rotation_difference(tgt)
        ang = math.degrees(q.angle)
        if ang > 1e-3:
            hm = frames[f]["RightHand"]; h = hm.translation.copy(); old = dict(frames[f]); p = dict(frames[f])
            p["RightHand"] = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ hm
            for bn in HAND_KIDS:
                p[bn] = p[PALL[bn]] @ (old[PALL[bn]].inverted() @ old[bn])
            frames[f] = p
        WRIST.append(round(ang, 2))
    p0, pE = math.degrees(math.asin(max(-1, min(1, b0.z)))), math.degrees(math.asin(max(-1, min(1, bE.z))))
    print("BLADE_SWEEP_DEG", round(math.degrees(th0), 1), flush=True)
    print("WRIST_CORRECTION_DEG", min(WRIST), max(WRIST), "blade pitch", round(p0, 1), "->", round(pE, 1), flush=True)
    # ---- world hips path: r4 join ramp + carry, then a Hermite settle over the shared recovery window, then rest
    HXY = [(frames[f]["Hips"].translation.x, frames[f]["Hips"].translation.y, 0.0) for f in range(NF)]
    J0 = int(round(JOIN_T * HZ)); J1 = J0 + int(round(JOIN_DECEL_S * HZ))
    newj, delta = core.reprofile_velocity(HXY, J0, J1)
    corr = [(0.0, 0.0, 0.0)] * NF
    for k, f in enumerate(range(J0, J1 + 1)):
        corr[f] = core.sub(newj[k], HXY[f])
    for f in range(J1 + 1, o_start + 1):
        corr[f] = delta
    pa = core.add(HXY[o_start], corr[o_start]); pb_ = core.add(HXY[o_start - 1], corr[o_start - 1])
    v0 = core.sub(pa, pb_); NS = F_SET - o_start
    for k, f in enumerate(range(o_start, F_SET + 1)):   # R5: smoothstep path on the shared progress + the incoming velocity decaying to 0
        x = k / NS; pt = core.add(core.add(pa, core.mul(core.sub(HXY[NF - 1], pa), c5.progress(f / HZ))), core.mul(v0, k * (1 - x) ** 2))
        corr[f] = core.sub(pt, HXY[f])
    for f in range(F_SET + 1, NF):
        corr[f] = core.sub(HXY[NF - 1], HXY[f])
    for f in range(NF):
        c = corr[f]
        if abs(c[0]) + abs(c[1]) > 1e-9:
            M = Matrix.Translation(Vector((c[0], c[1], 0.0)))
            frames[f] = {bn: M @ m for bn, m in frames[f].items()}
    print("ROLL_PATH join delta cm", [round(x * 240, 1) for x in delta[:2]], "settle frames", F_SET - o_start, "rest frames", NF - 1 - F_SET, flush=True)
    # ---- R5: retime the recovery by arc length. The composed recovery (body blend, arm, blade sweep, hips) starts slowly
    # and bunches its motion in the middle; resample the poses so (blade centroid path + 2 x mean joint path) advances on
    # the shared progress profile (uniform plateau speed), keeping the first and last recovery poses.
    import bisect
    BLADE_C = Vector((0.0, float(sum(p_[1] for p_ in BLADE_PTS) / len(BLADE_PTS)), 0.0))

    def blade_c(fr, gr):
        gl, gq, gs = gr.decompose(); return (fr["RightHand"] @ Matrix.LocRotScale(T_GRIP, gq, gs)) @ BLADE_C
    C = [blade_c(frames[f], grips[f]) for f in range(o_start, NF)]
    JN = [bn for bn in frames[NF - 1] if bn not in ("VeyrRoot", "WeaponSocket")]
    S = [0.0]
    for k in range(1, len(C)):   # metric: blade centroid step + 2 x mean joint step (so neither the blade nor the body bunches)
        fa, fb = frames[o_start + k - 1], frames[o_start + k]
        mj = sum((fb[bn].translation - fa[bn].translation).length for bn in JN) / len(JN)
        S.append(S[-1] + (C[k] - C[k - 1]).length + 2.0 * mj)
    Stot = S[-1]; src_f = []
    old_frames = {f: frames[f] for f in range(o_start, NF)}; old_grips = {f: grips[f] for f in range(o_start, NF)}
    for f in range(o_start, NF):
        pr = c5.progress(f / HZ)
        if pr >= 1.0 or f == NF - 1:
            src_f.append(float(f)); continue
        tgt = Stot * pr; j = min(max(bisect.bisect_right(S, tgt) - 1, 0), len(S) - 2)
        u = (tgt - S[j]) / max(S[j + 1] - S[j], 1e-12); sf = o_start + j + u
        src_f.append(sf)
        a, b_ = int(math.floor(sf)), min(int(math.floor(sf)) + 1, NF - 1); w = sf - a
        fa, fb = old_frames[a], old_frames[b_]
        frames[f] = {bn: mixm(fa[bn], fb[bn], w) if bn in fb else fa[bn] for bn in fa}
        grips[f] = mixm(old_grips[a], old_grips[b_], w)
    print("ROLL_RETIME path metric cm", round(Stot * 240, 1), "source frame at rendered steps", [round((x - o_start) / HZ, 3) for x in src_f[::13]], flush=True)
    # ---- footstep plan (world = armature space)
    IDLE_H = {sd: (I[sd + "Foot"].translation.z, I[sd + "ToeBase"].translation.z) for sd in ("Left", "Right")}

    def foot_at(t, sd):
        return frames[min(NF - 1, int(round(t * HZ)))][sd + "Foot"].copy()

    def grounded(m, sd, f):
        """Foot matrix m moved vertically so its lower point (ankle or toe joint vs their idle heights) is on the floor."""
        toe = frames[f][sd + "ToeBase"].translation - frames[f][sd + "Foot"].translation
        toe = m.to_3x3().normalized() @ (frames[f][sd + "Foot"].to_3x3().normalized().inverted() @ toe)
        a = m.translation.z - IDLE_H[sd][0]; b = m.translation.z + toe.z - IDLE_H[sd][1]
        return Matrix.Translation(Vector((0, 0, -min(a, b)))) @ m
    final = {sd: frames[NF - 1][sd + "Foot"].copy() for sd in ("Left", "Right")}
    FL0 = grounded(foot_at(c5.LEFT_L0_REF, "Left"), "Left", int(round(c5.LEFT_L0_REF * HZ)))
    FL1 = grounded(foot_at(c5.LEFT_L1_REF, "Left"), "Left", int(round(c5.LEFT_L1_REF * HZ)))
    PLAN = {"Right": {"lead": c5.RIGHT_LEAD, "plants": [final["Right"]], "steps": []},
            "Left": {"lead": c5.LEFT_LEAD, "plants": [FL0, FL1, final["Left"]], "steps": list(c5.STEPS_LEFT)}}

    def blend(ma, mb, h, lift):
        la, qa, _ = ma.decompose(); lb, qb, _ = mb.decompose()
        if qa.dot(qb) < 0:
            qb = -qb
        return Matrix.LocRotScale(la.lerp(lb, h) + Vector((0, 0, lift)), qa.slerp(qb, h), Vector((1, 1, 1)))
    targets = {}
    for sd, P in PLAN.items():
        t0, t1 = P["lead"]
        for f in range(int(round(t0 * HZ)), NF):
            t = f / HZ
            if t < t1:   # in-air lead: the source path, offset (smoothstep) so it touches down on the first plant
                w = smooth((t - t0) / (t1 - t0)); src = frames[f][sd + "Foot"]; at1 = frames[int(round(t1 * HZ))][sd + "Foot"]
                d = P["plants"][0].translation - at1.translation
                m = blend(src, Matrix.LocRotScale(src.translation + d, P["plants"][0].to_quaternion(), Vector((1, 1, 1))), w, 0.0)
            else:
                k = sum(1 for a, *_ in P["steps"] if t >= a)            # plants passed
                m = P["plants"][k]
                for i, (a, b, H, lo, hi) in enumerate(P["steps"]):
                    if a <= t < b:
                        h, z = c5.step_shape((t - a) / (b - a), lo, hi, H)
                        m = blend(P["plants"][i], P["plants"][i + 1], h, z / 240.0)
            targets.setdefault(f, {})[sd] = m
    for f in targets:   # a foot without a plan yet keeps its own pose
        for sd in ("Left", "Right"):
            targets[f].setdefault(sd, frames[f][sd + "Foot"].copy())
    # ---- hips drop so both targets are reachable (smoothed), applied to every bone
    LEN = {sd: ((I[sd + "Leg"].translation - I[sd + "UpLeg"].translation).length + (I[sd + "Foot"].translation - I[sd + "Leg"].translation).length) * c5.REACH for sd in ("Left", "Right")}
    need = [0.0] * NF; unreachable = []
    for f, tg in targets.items():
        for sd in ("Left", "Right"):
            dv = frames[f][sd + "UpLeg"].translation - tg[sd].translation; h2 = dv.x * dv.x + dv.y * dv.y
            if h2 < LEN[sd] ** 2:
                need[f] = max(need[f], dv.z - math.sqrt(LEN[sd] ** 2 - h2))
            else:
                unreachable.append(round(f / HZ, 3))
    W = int(round(c5.DROP_SMOOTH_S * HZ))
    dil = [max(need[max(0, f - W):f + W + 1]) for f in range(NF)]
    for _ in range(3):
        dil = [sum(dil[max(0, f - W):f + W + 1]) / len(dil[max(0, f - W):f + W + 1]) for f in range(NF)]
    drop = [max(a, b) for a, b in zip(dil, need)]
    for f in range(NF):
        if drop[f] > 1e-7:
            M = Matrix.Translation(Vector((0, 0, -drop[f])))
            frames[f] = {bn: M @ m for bn, m in frames[f].items()}
    print("ROLL_HIPS_DROP max cm", round(max(drop) * 240, 2), "at clip s", round(drop.index(max(drop)) / HZ, 3), "last", round(drop[-1] * 240, 3), "horizontally unreachable clip s", unreachable[:20], len(unreachable), flush=True)
    # ---- toes never below the idle toe-joint height (r4)
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
    TOE_REL = {sd: I[sd + "Foot"].inverted() @ I[sd + "ToeBase"] for sd in ("Left", "Right")}
    prev = {}; err_max = 0.0
    pb = arm.pose.bones
    for f, pose in enumerate(frames):
        for b in order:
            if b.name in pose and b.name != "WeaponSocket":
                b.matrix = pose[b.name]; bpy.context.view_layer.update()
        if f in targets:
            plant_legs(arm, targets[f])
            for sd in ("Left", "Right"):   # toes keep the idle foot-to-toe relation (no sourced toe flex sliding the toe joint)
                t0, t1 = PLAN[sd]["lead"]; w = smooth((f / HZ - t0) / (t1 - t0))
                if w > 0:
                    tb = pb[sd + "ToeBase"]; want = pb[sd + "Foot"].matrix @ TOE_REL[sd]
                    tb.matrix = mixm(tb.matrix.copy(), want, w); bpy.context.view_layer.update()
            for sd in ("Left", "Right"):
                err_max = max(err_max, (pb[sd + "Foot"].head - targets[f][sd].to_translation()).length * 240)
        gl, gq, gs = grips[f].decompose()
        pb["WeaponSocket"].matrix = pb["RightHand"].matrix @ Matrix.LocRotScale(T_GRIP, gq, gs); bpy.context.view_layer.update()
        for b in order:
            q = b.rotation_quaternion.copy()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy(); b.rotation_quaternion = q
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)
    print("ROLL_TARGET_ERR_MAX_CM", round(err_max, 2), flush=True)
    export(arm, roll_body, name, {"fps": HZ, "duration": (NF - 1) / HZ, "rollPrefixSeconds": 1.0, "attackComposedDuration": 1.2,
                                  "joinSeconds": JOIN / HZ, "joinDecel": {"clipSeconds": [J0 / HZ, J1 / HZ], "attackOffsetCm": [round(x * 240, 2) for x in delta[:2]]},
                                  "recoveryClipSeconds": [c5.REC_START, c5.REC_END], "restSeconds": (NF - 1 - F_SET) / HZ,
                                  "footPlan": {"Right": {"lead": c5.RIGHT_LEAD, "plant": "final idle spot from %.3f s to the end" % c5.RIGHT_LEAD[1]},
                                               "Left": {"lead": c5.LEFT_LEAD, "plantRefs": [c5.LEFT_L0_REF, c5.LEFT_L1_REF, "final"], "steps": c5.STEPS_LEFT}},
                                  "hipsDropMaxCm": round(max(drop) * 240, 2), "targetErrMaxCm": round(err_max, 2), "toeFloorFramesFixed": toe_fixed,
                                  "bladeSweepDeg": round(math.degrees(th0), 1), "wristCorrectionDeg": [min(WRIST), max(WRIST)],
                                  "sources": ["Fab_Roll_v17", "Mixamo_Attack_v17", "IdleOneHand_Blender_v2r4 (animated end)"], "gripMode": "one-handed",
                                  "method": "r4 composition to the strike (roll, join ramp + carry, slash); R5: footstep plan (rear foot lands on its final spot "
                                            "and stays; front foot: plant, lifted lunge step landing with the strike, locked through the slash, lifted step back "
                                            "moving only while lifted), one smoothstep recovery %.2f-%.2f s shared by body blend, arm, blade direction (great-circle sweep) and hips settle"
                                            % (c5.REC_START, c5.REC_END)}, NF - 1)

# ================================================================================================ blinks: feet only
elif stage == "blinkfeet":
    HZ = 120
    for b in BLINKS:
        src, out = "Knight_%s_v6c" % b, "Knight_%s_v7c%s" % (b, TAG)
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        s = clear(); s.render.fps = HZ
        grip = "TwoHand" if "TwoHand" in b else ""
        ia, _, io = load(KNIGHT / IDLE[grip]); s.frame_set(0)
        feet = {sd: ia.pose.bones[sd + "Foot"].matrix.copy() for sd in ("Left", "Right")}
        toes = {sd: ia.pose.bones[sd + "ToeBase"].matrix.copy() for sd in ("Left", "Right")}
        for o in io:
            bpy.data.objects.remove(o, do_unlink=True)
        meta = json.loads((EXP / (src + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
        arm, body, objs = load(EXP / (src + ".glb"))
        rows = basis_rows(arm, range(n + 1)); pb = arm.pose.bones
        trail = "Right" if "Left" in b else "Left"   # pushing (trailing) foot is opposite the travel side
        arm.animation_data_clear(); arm.animation_data_create(); arm.animation_data.action = bpy.data.actions.new(out)
        for bb in pb:
            bb.rotation_mode = "QUATERNION"
        prev = {}; log = []
        for i, row in enumerate(rows):
            t = i / HZ
            set_row(arm, row)
            if 0 < i < n:   # first / last keys are the exact idle already
                tg, toe_world = {}, {}
                ang = c5.seg(t, c5.TOE_OFF_DEG)
                for sd in ("Left", "Right"):
                    a = math.radians(ang * (1.0 if sd == trail else c5.TOE_OFF_LEAD))
                    piv = toes[sd].translation
                    lat = (toes[sd].translation - feet[sd].translation).cross(Z)
                    R = Matrix.Translation(piv) @ Matrix.Rotation(a, 4, lat.normalized()) @ Matrix.Translation(-piv) if a > 1e-6 else Matrix.Identity(4)
                    m = R @ feet[sd]
                    if (m.translation - feet[sd].translation).z < 0:   # rotation sign: the heel must go UP
                        R = Matrix.Translation(piv) @ Matrix.Rotation(-a, 4, lat.normalized()) @ Matrix.Translation(-piv); m = R @ feet[sd]
                    tg[sd] = m
                plant_legs(arm, tg)
                for sd in ("Left", "Right"):   # toes stay flat on the floor (toe joint is the pivot)
                    tb = pb[sd + "ToeBase"]
                    tb.matrix = Matrix.LocRotScale(tb.head.copy(), toes[sd].to_quaternion(), tb.matrix.to_scale()); bpy.context.view_layer.update()
                log.append({"t": round(t, 4), "toeOffDeg": round(ang, 1),
                            "ankleErrCm": round(max((pb[sd + "Foot"].head - tg[sd].to_translation()).length for sd in tg) * 240, 2),
                            "heelLiftCm": {sd: round((pb[sd + "Foot"].head.z - feet[sd].translation.z) * 240, 1) for sd in tg}})
            for bb in pb:
                q = bb.rotation_quaternion.copy()
                if bb.name in prev:
                    q.make_compatible(prev[bb.name])
                prev[bb.name] = q.copy(); bb.rotation_quaternion = q
                for prop in ("location", "rotation_quaternion", "scale"):
                    bb.keyframe_insert(prop, frame=i)
        m2 = dict(meta, derivedFrom=src, round5={"feet": "every 120 Hz key re-planted on the idle stance (analytic IK, legs only)",
                                                 "toeOffDeg": c5.TOE_OFF_DEG, "trailingFoot": trail, "leadingFootScale": c5.TOE_OFF_LEAD,
                                                 "maxAnkleErrCm": max(r["ankleErrCm"] for r in log), "frames": log})
        m2.pop("sha256", None)
        export(arm, body, out, m2, n)
        print("BLINKFEET", out, "maxAnkleErrCm", max(r["ankleErrCm"] for r in log), "maxHeelLiftCm",
              {sd: max(r["heelLiftCm"][sd] for r in log) for sd in ("Left", "Right")}, flush=True)
else:
    raise SystemExit("unknown stage %r (rollattack | blinkfeet)" % stage)
