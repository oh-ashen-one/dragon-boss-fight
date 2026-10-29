"""Knight fix round 2 (2026-10-29), headless Blender driver. Reuses build_round1 helpers.

The Mixamo Sword and Shield strafes are side-on clips (chest -70..-86 deg). Only the right-moving ones are forward
gaits (knees toward travel): strafe.fbx (walk R) and strafe (4).fbx (run R). Round 2 therefore:
  retarget  sagittal mirrors of those two for the left side, and a mirror of impact (3) for a symmetric front stagger
  bodies    spine counter-twist so the chest faces the boss (mean chest yaw -> 0; pelvis/knees keep the travel);
            staggers rebuilt (front = mean of impact (3) and its mirror); backpedal lean body re-exported. All exports
            now set the scene frame range to the keyed range (round 1 exported frame 1..250).
  fit       idle-root carries; staggers with blade pitch/tip limits; 1H/2H guarded backpedals with a ramped raise;
            1H and 2H blinks from the twisted run bodies
  cycles    loops start at the narrowest stance; blinks start at the phase whose ankle width is closest to the idle's
  rollattack  0.60 s join, sword locked to the right hand (socket = hand x blended grip), lifted recovery step
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
for _k in ("clear", "load", "basis_rows", "scale_rot", "smooth", "head_metrics", "plant_legs", "key_rows", "key_rows_planted", "FAB", "ROOT", "EXP", "KNIGHT", "SRC", "FPS", "ADDITIVE", "LEAN", "BASES"):
    globals()[_k] = _g[_k]
args = sys.argv[sys.argv.index("--") + 1:]
stage, only = args[0], set(args[1:])
OWNER = "fable-knight-round2-20261029"

RETARGET = [
    ("Mixamo_StrafeWalkLeftM_v1", "sword and shield strafe.fbx", False, True, "sagittal mirror of the forward-gait walk strafe right"),
    ("Mixamo_StrafeRunLeftM_v1", "sword and shield strafe (4).fbx", False, True, "sagittal mirror of the forward-gait run strafe right"),
    ("Mixamo_ImpactFrontMirror_v1", "sword and shield impact (3).fbx", False, True, "mirror of the front impact, averaged with it for a straight-back reaction"),
]
TWIST = {  # body name: source retarget
    "Knight_StrafeRightBody_v4": "Mixamo_StrafeRight_v1",
    "Knight_StrafeLeftBody_v4": "Mixamo_StrafeWalkLeftM_v1",
    "Knight_StrafeRunRightBody_v4": "Mixamo_StrafeRunRight_v1",
    "Knight_StrafeRunLeftBody_v4": "Mixamo_StrafeRunLeftM_v1",
}
SPINE = (("Spine", .30), ("Spine1", .35), ("Spine2", .35))


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


def chest_yaw(arm):
    pb = arm.pose.bones
    L = pb["LeftArm"].head - pb["RightArm"].head  # armature space == world (identity object)
    # glTF yaw convention: forward Blender -Y, + toward the knight's left (+X).
    f = Vector((L.y, -L.x, 0))  # shoulder line rotated -90 deg about Z = facing (idle: L=+X -> f=-Y)
    return math.degrees(math.atan2(f.x, -f.y))


if stage == "retarget":
    rg = {"__file__": str(FAB / "retarget.py")}
    exec(compile((FAB / "retarget.py").read_text(), str(FAB / "retarget.py"), "exec"), rg)
    for name, fbx, travel, mirror, why in RETARGET:
        if only and name not in only:
            continue
        bpy.context.scene["session_owner"] = rg["OWNER"]
        rg["run"](SRC / fbx, "mixamo", name, travel, mirror)
        rep = EXP / (name + ".json"); d = json.loads(rep.read_text()); d["classification"] = why; rep.write_text(json.dumps(d, indent=2))
        print("RETARGETED", name, flush=True)

elif stage == "bodies":
    report = {}
    for out, src in TWIST.items():
        if only and out not in only:
            continue
        s = clear()
        arm, body, objs = load(EXP / (src + ".glb"))
        meta = json.loads((EXP / (src + ".json")).read_text())
        n = int(round(meta["duration"] * FPS))
        rows = basis_rows(arm, range(n + 1))
        yaws = []
        for f in range(n + 1):
            s.frame_set(f); bpy.context.view_layer.update(); yaws.append(chest_yaw(arm))
        mu = sum(yaws) / len(yaws)
        arm.animation_data_clear(); arm.animation_data_create(); arm.animation_data.action = bpy.data.actions.new(out)
        pb = arm.pose.bones
        for b in pb:
            b.rotation_mode = "QUATERNION"
        prev = {}
        after = []
        for f, row in enumerate(rows):
            for b in pb:
                if b.name in row:
                    loc, q, sc = row[b.name].decompose(); b.location, b.rotation_quaternion, b.scale = loc, q, sc
            bpy.context.view_layer.update()
            for bn, frac in SPINE:  # counter-twist about vertical, parent before child
                b = pb[bn]; h = b.head.copy()
                b.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(-mu * frac), 4, "Z") @ Matrix.Translation(-h) @ b.matrix
                bpy.context.view_layer.update()
            after.append(chest_yaw(arm))
            for b in pb:
                q = b.rotation_quaternion.copy()
                if b.name in prev:
                    q.make_compatible(prev[b.name])
                prev[b.name] = q.copy(); b.rotation_quaternion = q
                for prop in ("location", "rotation_quaternion", "scale"):
                    b.keyframe_insert(prop, frame=f)
        report[out] = {"source": src, "chestYawBefore": [round(min(yaws), 1), round(max(yaws), 1), round(mu, 1)],
                       "chestYawAfter": [round(min(after), 1), round(max(after), 1), round(sum(after) / len(after), 1)]}
        print("TWIST", out, report[out], flush=True)
        export(arm, body, out, {"fps": FPS, "duration": n / FPS, "source": src, "method": "spine counter-twist (Spine/Spine1/Spine2 30/35/35%) about vertical by the clip's mean chest yaw; legs, pelvis and timing unchanged",
                                "twist": report[out]}, n)
    # Staggers v4 (front = mean of impact (3) and its mirror), frame range fixed.
    IMP = {"Front": ("Mixamo_ImpactFront_v1", "Mixamo_ImpactFrontMirror_v1", 1.0), "Back": ("Mixamo_ImpactBack_v1", None, 1.0),
           "Left": ("Mixamo_ImpactLeft_v1", None, 1.8), "Right": ("Mixamo_ImpactRight_v1", None, 1.8)}
    for grip, base_file in BASES.items():
        for d, (src_name, mirror_name, k) in IMP.items():
            name = "Knight_Stagger%s%sBody_v4" % (d, grip)
            if only and name not in only:
                continue
            s = clear()
            base, base_body, base_objs = load(KNIGHT / base_file)
            s.frame_set(0)
            idle = {b.name: b.matrix_basis.copy() for b in base.pose.bones}
            mw = base.matrix_world
            feet = {sd: (mw @ base.pose.bones[sd + "Foot"].matrix).copy() for sd in ("Left", "Right")}
            meta = json.loads((EXP / (src_name + ".json")).read_text())
            n = int(round(meta["duration"] * FPS))
            imp, _, imp_objs = load(EXP / (src_name + ".glb"))
            rows = basis_rows(imp, range(n + 1))
            for o in imp_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            rows_m = None
            if mirror_name:
                impm, _, impm_objs = load(EXP / (mirror_name + ".glb"))
                rows_m = basis_rows(impm, range(n + 1))
                for o in impm_objs:
                    bpy.data.objects.remove(o, do_unlink=True)
            out = []
            for f in range(n + 1):
                u = f / n
                w = 1.0 - smooth((u - .70) / .30)
                row = {}
                for bn, m in idle.items():
                    if bn in ADDITIVE and bn in rows[f]:
                        l0, q0, _ = rows[0][bn].decompose(); lt, qt, _ = rows[f][bn].decompose()
                        dq = q0.inverted() @ qt; dl = lt - l0
                        if rows_m is not None:
                            m0, p0, _ = rows_m[0][bn].decompose(); mt, pt, _ = rows_m[f][bn].decompose()
                            dqm = p0.inverted() @ pt
                            if dq.dot(dqm) < 0:
                                dqm = -dqm
                            dq = dq.slerp(dqm, .5); dl = (dl + (mt - m0)) * .5
                        dq = scale_rot(dq, k * w)
                        li, qi, si = m.decompose()
                        row[bn] = Matrix.LocRotScale(li + dl * (k * w if bn == "Hips" else 0.0), qi @ dq, si)
                    else:
                        row[bn] = m.copy()
                out.append(row)
            key_rows_planted(base, out, name, feet)
            report[name] = head_metrics(base, n)
            export(base, base_body, name, {"fps": FPS, "duration": n / FPS, "source": src_name, "mirrorAveraged": mirror_name, "base": base_file, "lateralGain": k,
                                           "method": "additive deltas on the approved idle frame 0 (start and end exactly idle); legs planted by analytic two-bone IK",
                                           "headMetricsMetres": report[name]}, n)
    name = "Knight_BackpedalGuardBody_v4"
    if not only or name in only:
        s = clear()
        arm, body, objs = load(KNIGHT / "Backpedal_Blender_loop_v1r3.glb")
        n = int(round(arm.animation_data.action.frame_range[1]))
        rows = basis_rows(arm, range(n + 1))
        pb = arm.pose.bones; mw = arm.matrix_world
        s.frame_set(0)
        fwd = Vector((0, -1, 0)); right = fwd.cross(Vector((0, 0, 1)))
        h0 = (mw @ pb["Head"].head).copy()
        base_q = pb["Spine"].rotation_quaternion.copy() if pb["Spine"].rotation_mode == "QUATERNION" else None
        sign = 1
        for trial in (1, -1):
            pb["Spine"].rotation_mode = "QUATERNION"; q0 = pb["Spine"].rotation_quaternion.copy()
            axis_local = (pb["Spine"].bone.matrix_local.to_3x3().inverted() @ right).normalized()
            pb["Spine"].rotation_quaternion = q0 @ Quaternion(axis_local, math.radians(trial * 10)); bpy.context.view_layer.update()
            if (mw @ pb["Head"].head - h0).dot(fwd) > 0:
                sign = trial
            pb["Spine"].rotation_quaternion = q0; bpy.context.view_layer.update()
        final = []
        for row in rows:
            fr = {}
            for bn, m in row.items():
                if bn in LEAN:
                    axis_local = (pb[bn].bone.matrix_local.to_3x3().inverted() @ right).normalized()
                    loc, q, sc = m.decompose(); fr[bn] = Matrix.LocRotScale(loc, q @ Quaternion(axis_local, math.radians(sign * LEAN[bn])), sc)
                else:
                    fr[bn] = m.copy()
            final.append(fr)
        key_rows(arm, final, name)
        export(arm, body, name, {"fps": FPS, "duration": n / FPS, "source": "Backpedal_Blender_loop_v1r3.glb (approved; read only)", "lean": LEAN}, n)
    (EXP / "round2-bodies-report.json").write_text(json.dumps(report, indent=2))

elif stage == "fit":
    fg = {"__file__": str(FAB / "fit_weapon.py")}
    exec(compile((FAB / "fit_weapon.py").read_text(), str(FAB / "fit_weapon.py"), "exec"), fg)
    bpy.context.scene["session_owner"] = fg["OWNER"]
    refs = {"one": fg["reference"]("IdleOneHand_Blender_v2r4.glb"), "two": fg["reference"]("IdleTwoHand_Blender_v2r4.glb"),
            "guard": fg["reference"]("GuardReadyTwoHand_Blender_v4r4.glb", True)}
    jobs = []  # out, src, grip, mode, kwargs
    for side in ("Left", "Right"):
        for grip in ("", "TwoHand"):
            jobs.append(("Knight_Strafe%s%s_v4" % (side, grip), "Knight_Strafe%sBody_v4" % side, grip, "idle-root", {}))
            jobs.append(("Knight_StrafeRun%s%s_v4" % (side, grip), "Knight_StrafeRun%sBody_v4" % side, grip, "idle-root", {}))
            jobs.append(("Knight_Blink%s%s_v4" % (side, grip), "Knight_StrafeRun%sBody_v4" % side, grip, "idle-root", {}))
    for d, rate in (("Front", 1.1667), ("Back", 1.6111), ("Left", 1.1667), ("Right", 1.1667)):
        for grip in ("", "TwoHand"):
            # 40 game cm per in-game frame at the in-game rate: 40/240 m per (rate) source frames at 30 fps.
            jobs.append(("Knight_Stagger%s%s_v4" % (d, grip), "Knight_Stagger%s%sBody_v4" % (d, grip), grip, "idle-root",
                         {"follow": .45, "pitch_cap": 25.0, "tip_cap": (40.0 / 240.0) / rate}))
    jobs.append(("Knight_BackpedalGuard_v4", "Knight_BackpedalGuardBody_v4", "", "idle", {"carry_raise": (62.0, .10)}))
    jobs.append(("Knight_BackpedalGuardTwoHand_v4", "Knight_BackpedalGuardBody_v4", "TwoHand", "idle", {"carry_raise": (-22.0, .0)}))
    for out, src, grip, mode, kw in jobs:
        if only and out not in only:
            continue
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        bpy.context.scene["session_owner"] = fg["OWNER"]
        kw = dict(kw); cr = kw.pop("carry_raise", (0., 0.))
        fg["fit"]("walk", refs, "v4", "two" if grip else "one", out, src, mode, cr, **kw)
        print("FITTED", out, flush=True)

elif stage == "cycles":
    HZ = 120
    IDLE_ANKLE = None
    s = clear(); a0, _, o0 = load(KNIGHT / "IdleOneHand_Blender_v2r4.glb"); s.frame_set(0)
    d0 = a0.pose.bones["LeftFoot"].head - a0.pose.bones["RightFoot"].head; d0.z = 0; IDLE_ANKLE = d0.length
    names = ["Knight_Strafe%s%s_v4" % (a, b) for a in ("Left", "Right", "RunLeft", "RunRight") for b in ("", "TwoHand")]
    names += ["Knight_Blink%s%s_v4" % (a, b) for a in ("Left", "Right") for b in ("", "TwoHand")]
    rep = {}
    for nm in names:
        out = nm[:-3] + "_v4c"
        if (only and out not in only) or (EXP / (out + ".glb")).exists():
            continue
        s = clear(); s.render.fps = HZ
        arm, body, objs = load(EXP / (nm + ".glb"))
        meta = json.loads((EXP / (nm + ".json")).read_text()); T = meta["duration"]; n = int(round(T * HZ))
        pb = arm.pose.bones
        widths = []
        for i in range(n):
            s.frame_set(i); d = pb["LeftFoot"].head - pb["RightFoot"].head; d.z = 0; widths.append(d.length)
        blink = "Blink" in nm or "Strafe" in nm  # ends at the idle stance width (62 +/- 10 cm)
        i0 = min(range(n), key=lambda i: abs(widths[i] - IDLE_ANKLE)) if blink else min(range(n), key=lambda i: widths[i])
        rows = basis_rows(arm, [((i0 + i) % n) for i in range(n + 1)])
        rows[-1] = rows[0]
        key_rows(arm, rows, out)
        m2 = dict(meta, fps=HZ, bakeSampleRate=HZ, cycleStartShiftSeconds=i0 / HZ, startAnkleMetres=widths[i0], idleAnkleMetres=IDLE_ANKLE, derivedFrom=nm)
        m2.pop("sha256", None)
        export(arm, body, out, m2, n)
        rep[out] = {"shift": i0 / HZ, "ankleCm": round(widths[i0] * 240, 1)}
    print("CYCLES", json.dumps(rep), flush=True)

elif stage == "rollattack":
    name = "Sourced_RollAttack_v4"
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

    def grip_of(p):  # socket in right-hand space
        return p["RightHand"].inverted() @ p["WeaponSocket"]
    T_GRIP = None  # fixed hand-space grip translation (idle) so hand-to-grip distance never changes
    frames, grips, outro_u = [], [], []
    gR, gI = grip_of(R[-1]), grip_of(I)
    T_GRIP = gI.translation.copy()
    for f in range(301 + len(A) - 1):
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
    # Recovery step: the foot that travels furthest across the outro lifts on an arc (peak 0.06 m rig = 14 game cm).
    o0 = next(i for i, u in enumerate(outro_u) if u > 0) - 1
    moves = {sd: (frames[-1][sd + "Foot"].translation - frames[o0][sd + "Foot"].translation).length for sd in ("Left", "Right")}
    step_foot = max(moves, key=moves.get)
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
        if outro_u[f] > 0:
            # Two lifted recovery steps: the far foot steps in the first half while the other stays planted, then the other.
            u = outro_u[f]; other = "Right" if step_foot == "Left" else "Left"; tg = {}
            for sd, a, b, h in ((step_foot, 0.0, .5, .06), (other, .5, 1.0, .05)):
                w = max(0.0, min(1.0, (u - a) / (b - a)))
                m = mixm(frames[o0][sd + "Foot"], frames[-1][sd + "Foot"], smooth(w))
                tg[sd] = Matrix.Translation(Vector((0, 0, h * math.sin(math.pi * w)))) @ m
            plant_legs(arm, tg)
        # Sword locked to the right hand with the blended hand-space grip (hand slip only from the grip blend itself).
        gl, gq, gs = grips[f].decompose()
        pb["WeaponSocket"].matrix = pb["RightHand"].matrix @ Matrix.LocRotScale(T_GRIP, gq, gs); bpy.context.view_layer.update()
        for b in order:
            q = b.rotation_quaternion.copy()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy(); b.rotation_quaternion = q
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)
    export(arm, roll_body, name, {"fps": HZ, "duration": (len(frames) - 1) / HZ, "rollPrefixSeconds": 1.0, "attackComposedDuration": 1.2,
                                  "joinSeconds": JOIN / HZ, "outroSeconds": OUTRO / HZ, "stepFoot": step_foot, "stepLiftMetres": [.06, .05], "steps": "far foot first half, other foot second half",
                                  "sources": ["Fab_Roll_v17", "Mixamo_Attack_v17", "IdleOneHand_Blender_v2r4 (end pose)"], "gripMode": "one-handed",
                                  "method": "armature-space composition; 0.60 s velocity-matched join; 0.42 s outro into the 1H idle with a lifted recovery step (analytic leg IK); WeaponSocket = RightHand x blended hand-space grip every frame"}, len(frames) - 1)
