"""Knight completion fix round 1 (2026-10-29), headless Blender driver.

Stages (Blender --background --factory-startup --python build_round1.py -- STAGE [NAMES]):
  retarget  Mixamo strafe (3) as: true mirror (sprint strafe right), blink left (with travel), blink right (mirror, travel)
  bodies    additive staggers on the approved idles (feet IK-planted to the idle stance, start/end exactly idle,
            lateral amplitude x2) and the guarded backpedal body (approved loop legs, forward lean)
  fit       weapon fit with the approved idles' carries (carry_mode='idle'), one- and two-hand
  rollattack  Fab roll -> Mixamo slash with a 0.40 s smootherstep join and a 0.36 s outro into the 1H idle carry
All outputs are new names in Local/FabRigTesting/Exports; approved sources are only read."""
import bpy, sys, json, math, hashlib
from pathlib import Path
from mathutils import Matrix, Vector, Quaternion

HERE = Path(__file__).resolve().parent
FAB = HERE.parent / "blender/fab_rig_testing"
ROOT = HERE.parents[2]
EXP = ROOT / "Local/FabRigTesting/Exports"
KNIGHT = ROOT / "Local/CustomuseAssets/Polish20261025/knight"
SRC = ROOT / "Local/FabRigTesting/Source/Mixamo"
args = sys.argv[sys.argv.index("--") + 1:]
stage, only = args[0], set(args[1:])
FPS = 30

RETARGET = [  # name, fbx, travel, mirror, why
    ("Mixamo_StrafeRunRightMirror_v1", "sword and shield strafe (3).fbx", False, True, "true sagittal mirror of the run strafe left"),
    ("Mixamo_BlinkLeft_v1", "sword and shield strafe (3).fbx", True, False, "run strafe left with travel (blink body)"),
    ("Mixamo_BlinkRight_v1", "sword and shield strafe (3).fbx", True, True, "mirror of the blink left body, with mirrored travel"),
]
IMPACTS = {"Front": ("Mixamo_ImpactFront_v1", 1.0), "Back": ("Mixamo_ImpactBack_v1", 1.0),
           "Left": ("Mixamo_ImpactLeft_v1", 2.0), "Right": ("Mixamo_ImpactRight_v1", 2.0)}
BASES = {"": "IdleOneHand_Blender_v2r4.glb", "TwoHand": "IdleTwoHand_Blender_v2r4.glb"}
ADDITIVE = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "RightShoulder"]
LEAN = {"Spine": 8.5, "Spine1": 7.0, "Spine2": 5.5, "Neck": -8.0, "Head": -5.0}


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
    s = bpy.context.scene
    s.render.fps = FPS
    s.render.fps_base = 1
    return s


def load(path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = set(bpy.context.scene.objects) - before
    arm = next(o for o in new if o.type == "ARMATURE")
    return arm, [o for o in new if o.type == "MESH"], new


def basis_rows(arm, frames):
    s = bpy.context.scene
    rows = []
    for f in frames:
        s.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        rows.append({b.name: b.matrix_basis.copy() for b in arm.pose.bones})
    return rows


def scale_rot(q, k):
    axis, angle = q.to_axis_angle()
    return Quaternion(axis, angle * k)


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def export(arm, body, name, meta):
    s = bpy.context.scene
    for o in s.objects:
        o.select_set(False)
    arm.select_set(True)
    for o in body:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    path = EXP / name
    assert not path.with_suffix(".glb").exists(), name
    bpy.ops.export_scene.gltf(filepath=str(path.with_suffix(".glb")), export_format="GLB", use_selection=True,
                              export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_frame_range=True,
                              export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False)
    s["session_owner"] = "fable-knight-round1-20261029"
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix(".blend")), compress=True)
    meta = dict(meta, name=name, sha256=hashlib.sha256(path.with_suffix(".glb").read_bytes()).hexdigest())
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print("EXPORTED", name, flush=True)


def head_metrics(arm, n):
    """Head displacement relative to frame 0 (armature metres): max forward/lateral, using the idle facing."""
    s = bpy.context.scene
    mw = arm.matrix_world
    pb = arm.pose.bones
    s.frame_set(0)
    toes = (mw @ pb["LeftToeBase"].head + mw @ pb["RightToeBase"].head) / 2
    heels = (mw @ pb["LeftFoot"].head + mw @ pb["RightFoot"].head) / 2
    fwd = toes - heels
    fwd.z = 0
    fwd.normalize()
    right = fwd.cross(Vector((0, 0, 1)))
    h0 = mw @ pb["Head"].head
    best = {"forward": 0, "back": 0, "right": 0, "left": 0, "down": 0}
    feet0 = {sd: (mw @ pb[sd + "Foot"].head).copy() for sd in ("Left", "Right")}
    slide = 0
    for f in range(n + 1):
        s.frame_set(f)
        d = mw @ pb["Head"].head - h0
        best["forward"] = max(best["forward"], d.dot(fwd)); best["back"] = max(best["back"], -d.dot(fwd))
        best["right"] = max(best["right"], d.dot(right)); best["left"] = max(best["left"], -d.dot(right))
        best["down"] = max(best["down"], -d.z)
        for sd in ("Left", "Right"):
            v = mw @ pb[sd + "Foot"].head - feet0[sd]; v.z = 0
            slide = max(slide, v.length)
    best["maxFootSlide"] = slide
    return {k: round(v, 4) for k, v in best.items()}


def leg_ik(arm, targets):
    """Two-bone IK on each leg to fixed foot world matrices (planted stance)."""
    s = bpy.context.scene
    cons = []
    for sd in ("Left", "Right"):
        t = bpy.data.objects.new(sd + "_FootTarget", None)
        s.collection.objects.link(t)
        t.matrix_world = targets[sd]
        knee = arm.pose.bones[sd + "Leg"]
        pole = bpy.data.objects.new(sd + "_KneePole", None)
        s.collection.objects.link(pole)
        pole.location = arm.matrix_world @ knee.head + targets["fwd"] * .6
        # glTF imports have arbitrary bone tails, so the effector is the Foot bone head (the ankle):
        # IK on Foot with use_tail=False and a 3-bone chain (Foot, Leg, UpLeg).
        ik = arm.pose.bones[sd + "Foot"].constraints.new("IK")
        ik.target = t
        ik.pole_target = pole
        ik.chain_count = 3
        ik.use_tail = False
        ik.use_stretch = False
        ik.iterations = 500
        cr = arm.pose.bones[sd + "Foot"].constraints.new("COPY_ROTATION")
        cr.target = t
        cons.append((ik, pole, knee))
    # The IK solver aims the knee chain at the target with use_tail; calibrate pole angle to the idle knee.
    s.frame_set(0)
    for ik, pole, knee in cons:
        want = (arm.matrix_world @ knee.head).copy()
        best = None
        for deg in range(-180, 181, 5):
            ik.pole_angle = math.radians(deg)
            bpy.context.view_layer.update()
            e = (arm.matrix_world @ knee.head - want).length
            if best is None or e < best[0]:
                best = (e, ik.pole_angle)
        ik.pole_angle = best[1]


def bake(arm, n):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.nla.bake(frame_start=0, frame_end=n, step=1, only_selected=False, visual_keying=True, clear_constraints=True,
                     clear_parents=False, use_current_action=False, clean_curves=False, bake_types={"POSE"},
                     channel_types={"LOCATION", "ROTATION", "SCALE"})
    bpy.ops.object.mode_set(mode="OBJECT")


def key_rows(arm, rows, action_name):
    arm.animation_data_clear()
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.new(action_name)
    prev = {}
    for b in arm.pose.bones:
        b.rotation_mode = "QUATERNION"
    for f, row in enumerate(rows):
        for b in arm.pose.bones:
            if b.name not in row:
                continue
            loc, q, sc = row[b.name].decompose()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy()
            b.location, b.rotation_quaternion, b.scale = loc, q, sc
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)


def plant_legs(arm, targets):
    """Analytic two-bone IK in armature space (the armature object is at identity): keeps each ankle
    (Foot head) on its idle world position and the foot at its idle rotation, preserving the knee plane."""
    pb = arm.pose.bones
    for sd in ("Left", "Right"):
        up, leg, foot = pb[sd + "UpLeg"], pb[sd + "Leg"], pb[sd + "Foot"]
        T = targets[sd].to_translation()
        H, K, A = up.head.copy(), leg.head.copy(), foot.head.copy()
        a, b = (K - H).length, (A - K).length
        d = min(max((T - H).length, 1e-4), (a + b) * .9995)
        u = (T - H).normalized()
        n = (K - H).cross(A - H)
        if n.length < 1e-6:
            n = u.cross(Vector((0, 0, 1)))
        n.normalize()
        v = n.cross(u).normalized()
        if v.dot(K - H) < 0:
            v = -v
        ca = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d)))
        K2 = H + a * (ca * u + math.sqrt(max(0.0, 1 - ca * ca)) * v)
        R1 = (K - H).rotation_difference(K2 - H).to_matrix().to_4x4()
        up.matrix = Matrix.Translation(H) @ R1 @ Matrix.Translation(-H) @ up.matrix
        bpy.context.view_layer.update()
        K, A = leg.head.copy(), foot.head.copy()
        R2 = (A - K).rotation_difference(T - K).to_matrix().to_4x4()
        leg.matrix = Matrix.Translation(K) @ R2 @ Matrix.Translation(-K) @ leg.matrix
        bpy.context.view_layer.update()
        _, rq, rs = targets[sd].decompose()
        foot.matrix = Matrix.LocRotScale(foot.head.copy(), rq, foot.matrix.to_scale())
        bpy.context.view_layer.update()


def key_rows_planted(arm, rows, action_name, targets):
    arm.animation_data_clear()
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.new(action_name)
    prev = {}
    for b in arm.pose.bones:
        b.rotation_mode = "QUATERNION"
    for f, row in enumerate(rows):
        for b in arm.pose.bones:
            if b.name in row:
                loc, q, sc = row[b.name].decompose()
                b.location, b.rotation_quaternion, b.scale = loc, q, sc
        bpy.context.view_layer.update()
        plant_legs(arm, targets)
        for b in arm.pose.bones:
            q = b.rotation_quaternion.copy()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy()
            b.rotation_quaternion = q
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)


if stage == "retarget":
    g = {"__file__": str(FAB / "retarget.py")}
    exec(compile((FAB / "retarget.py").read_text(), str(FAB / "retarget.py"), "exec"), g)
    for name, fbx, travel, mirror, why in RETARGET:
        if only and name not in only:
            continue
        bpy.context.scene["session_owner"] = g["OWNER"]
        g["run"](SRC / fbx, "mixamo", name, travel, mirror)
        rep = EXP / (name + ".json")
        d = json.loads(rep.read_text())
        d["classification"] = why
        rep.write_text(json.dumps(d, indent=2))
        print("RETARGETED", name, flush=True)

elif stage == "bodies":
    report = {}
    for grip, base_file in BASES.items():
        for d, (src_name, k) in IMPACTS.items():
            name = "Knight_Stagger%s%sBody_v3" % (d, grip)
            if only and name not in only:
                continue
            s = clear()
            base, base_body, base_objs = load(KNIGHT / base_file)
            s.frame_set(0)
            idle = {b.name: b.matrix_basis.copy() for b in base.pose.bones}
            mw = base.matrix_world
            feet = {sd: (mw @ base.pose.bones[sd + "Foot"].matrix).copy() for sd in ("Left", "Right")}
            toes = (mw @ base.pose.bones["LeftToeBase"].head + mw @ base.pose.bones["RightToeBase"].head) / 2
            heels = (mw @ base.pose.bones["LeftFoot"].head + mw @ base.pose.bones["RightFoot"].head) / 2
            fwd = toes - heels; fwd.z = 0; fwd.normalize()
            imp, imp_body, imp_objs = load(EXP / (src_name + ".glb"))
            meta = json.loads((EXP / (src_name + ".json")).read_text())
            n = int(round(meta["duration"] * FPS))
            rows = basis_rows(imp, range(n + 1))
            for o in imp_objs:
                bpy.data.objects.remove(o, do_unlink=True)
            out = []
            for f in range(n + 1):
                u = f / n
                w = 1.0 - smooth((u - .70) / .30)  # full reaction, then settle exactly into the idle pose
                row = {}
                for bn, m in idle.items():
                    if bn in ADDITIVE and bn in rows[f]:
                        l0, q0, _ = rows[0][bn].decompose()
                        lt, qt, _ = rows[f][bn].decompose()
                        dq = scale_rot(q0.inverted() @ qt, k * w)
                        li, qi, si = m.decompose()
                        loc = li + (lt - l0) * (k * w if bn == "Hips" else 0.0)
                        row[bn] = Matrix.LocRotScale(loc, qi @ dq, si)
                    else:
                        row[bn] = m.copy()
                out.append(row)
            key_rows_planted(base, out, name, feet)
            report[name] = head_metrics(base, n)
            export(base, base_body, name, {"fps": FPS, "duration": n / FPS, "source": src_name, "base": base_file, "lateralGain": k,
                                           "method": "additive impact deltas (hips, spine, neck, head, clavicles) on the approved idle frame 0; legs planted to the idle feet by analytic two-bone IK; envelope fades to the exact idle pose over the last 30%",
                                           "headMetricsMetres": report[name]})
    for grip in ("",):
        name = "Knight_BackpedalGuardBody_v3"
        if only and name not in only:
            continue
        s = clear()
        arm, body, objs = load(KNIGHT / "Backpedal_Blender_loop_v1r3.glb")
        dur = arm.animation_data.action.frame_range[1] / FPS
        n = int(round(dur * FPS))
        rows = basis_rows(arm, range(n + 1))
        out = []
        for row in rows:
            new = {}
            for bn, m in row.items():
                if bn in LEAN:
                    loc, q, sc = m.decompose()
                    new[bn] = (bn, loc, q, sc)
                else:
                    new[bn] = m
            out.append(new)
        # Apply the lean as a rotation about the knight's right axis in armature space, parent before child.
        mw = arm.matrix_world
        s.frame_set(0)
        pb = arm.pose.bones
        toes = (mw @ pb["LeftToeBase"].head + mw @ pb["RightToeBase"].head) / 2
        heels = (mw @ pb["LeftFoot"].head + mw @ pb["RightFoot"].head) / 2
        fwd = toes - heels; fwd.z = 0; fwd.normalize()
        right = fwd.cross(Vector((0, 0, 1)))
        h0 = (mw @ pb["Head"].head).copy()
        pb["Spine"].rotation_mode = "QUATERNION"
        sign = 1
        for trial in (1, -1):  # pick the sign that moves the head forward
            base_q = pb["Spine"].rotation_quaternion.copy()
            axis_local = (pb["Spine"].matrix.to_3x3().inverted() @ (mw.to_3x3().inverted() @ right)).normalized()
            pb["Spine"].rotation_quaternion = base_q @ Quaternion(axis_local, math.radians(trial * 10))
            bpy.context.view_layer.update()
            if (mw @ pb["Head"].head - h0).dot(fwd) > 0:
                sign = trial
            pb["Spine"].rotation_quaternion = base_q
            bpy.context.view_layer.update()
        final = []
        for f, row in enumerate(rows):
            s.frame_set(f)
            fr = {}
            for bn, m in row.items():
                if bn in LEAN:
                    b = pb[bn]
                    axis_local = (b.bone.matrix_local.to_3x3().inverted() @ (mw.to_3x3().inverted() @ right)).normalized()
                    loc, q, sc = m.decompose()
                    fr[bn] = Matrix.LocRotScale(loc, q @ Quaternion(axis_local, math.radians(sign * LEAN[bn])), sc)
                else:
                    fr[bn] = m.copy()
            final.append(fr)
        def head_ahead(n_):
            vals = []
            for f in range(n_ + 1):
                s.frame_set(f)
                vals.append((mw @ pb["Head"].head - mw @ pb["Hips"].head).dot(fwd))
            return sum(vals) / len(vals)
        before = head_ahead(n)
        key_rows(arm, final, name)
        after = head_ahead(n)
        print("LEAN head ahead of hips (m): before %.4f after %.4f delta %.4f" % (before, after, after - before), flush=True)
        export(arm, body, name, {"fps": FPS, "duration": n / FPS, "source": "Backpedal_Blender_loop_v1r3.glb (approved; read only)",
                                 "method": "constant forward lean on Spine/Spine1/Spine2 (+8.5/+7/+5.5 deg) with Neck/Head counter (-8/-5) about the knight's right axis; legs and timing untouched",
                                 "headAheadOfHipsMetres": {"before": before, "after": after, "delta": after - before}})
    (EXP / "round1-bodies-report.json").write_text(json.dumps(report, indent=2))

elif stage == "fit":
    g = {"__file__": str(FAB / "fit_weapon.py")}
    exec(compile((FAB / "fit_weapon.py").read_text(), str(FAB / "fit_weapon.py"), "exec"), g)
    bpy.context.scene["session_owner"] = g["OWNER"]
    refs = {"one": g["reference"]("IdleOneHand_Blender_v2r4.glb"), "two": g["reference"]("IdleTwoHand_Blender_v2r4.glb"),
            "guard": g["reference"]("GuardReadyTwoHand_Blender_v4r4.glb", True)}
    jobs = []
    for side, src in (("Left", "Mixamo_StrafeLeft_v1"), ("Right", "Mixamo_StrafeRight_v1")):
        for grip in ("", "TwoHand"):
            jobs.append(("Knight_Strafe%s%s_v3" % (side, grip), src, grip, (0., 0.), "idle-root"))
    for side, src in (("Left", "Mixamo_StrafeRunLeft_v1"), ("Right", "Mixamo_StrafeRunRightMirror_v1")):
        for grip in ("", "TwoHand"):
            jobs.append(("Knight_StrafeRun%s%s_v3" % (side, grip), src, grip, (0., 0.), "idle-root"))
    for d in IMPACTS:
        for grip in ("", "TwoHand"):
            jobs.append(("Knight_Stagger%s%s_v3" % (d, grip), "Knight_Stagger%s%sBody_v3" % (d, grip), grip, (0., 0.), "idle"))
    for grip in ("", "TwoHand"):
        jobs.append(("Knight_BackpedalGuard%s_v3" % grip, "Knight_BackpedalGuardBody_v3", grip, (27., .06), "idle"))
    for side in ("Left", "Right"):
        jobs.append(("Knight_Blink%s_v3" % side, "Mixamo_Blink%s_v1" % side, "", (0., 0.), "idle-root"))
    for out, src, grip, raise_, mode in jobs:
        if only and out not in only:
            continue
        if (EXP / (out + ".glb")).exists():
            print("SKIP", out); continue
        bpy.context.scene["session_owner"] = g["OWNER"]
        g["fit"]("walk", refs, "v3", "two" if grip else "one", out, src, mode, raise_)
        print("FITTED", out, flush=True)

elif stage == "rollattack":
    name = "Sourced_RollAttack_v3"
    s = clear()
    HZ = 300
    roll, roll_body, roll_objs = load(EXP / "Fab_Roll_v17.glb")
    att, att_body, att_objs = load(EXP / "Mixamo_Attack_v17.glb")
    idl, idl_body, idl_objs = load(KNIGHT / "IdleOneHand_Blender_v2r4.glb")
    rmeta = json.loads((EXP / "Fab_Roll_v17.json").read_text())
    ameta = json.loads((EXP / "Mixamo_Attack_v17.json").read_text())

    def arm_rows(arm, src_dur, out_dur):
        cnt = int(round(out_dur * HZ))
        rows, hips = [], []
        for i in range(cnt + 1):
            f = i / cnt * src_dur * FPS
            s.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
            rows.append({b.name: b.matrix.copy() for b in arm.pose.bones})
        return rows

    R = arm_rows(roll, rmeta["duration"], 1.0)            # 301 armature-space poses, roll prefix unchanged
    A = arm_rows(att, ameta["duration"], 1.2)             # slash retimed to 1.2 s (as v2)
    s.frame_set(0)
    I = {b.name: b.matrix.copy() for b in idl.pose.bones}
    for o in list(att_objs) + list(idl_objs):
        bpy.data.objects.remove(o, do_unlink=True)
    # Align the slash start onto the roll end horizontally (travel continuity), as v2 did via VeyrRoot.
    off = R[-1]["Hips"].translation - A[0]["Hips"].translation
    off.z = 0
    JOIN, OUTRO = int(.40 * HZ), int(.36 * HZ)

    def mixm(a, b, u):
        x, q, sc = a.decompose(); y, r, ss = b.decompose()
        if q.dot(r) < 0:
            r = -r
        return Matrix.LocRotScale(x.lerp(y, u), q.slerp(r, u), sc.lerp(ss, u))

    def smoother(x):
        x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)
    frames = []
    for f in range(301 + len(A) - 1):
        if f <= 300:
            frames.append(R[f]); continue
        j = f - 300
        a = {n: Matrix.Translation(off) @ m for n, m in A[j].items()}
        # Velocity-matched join: the roll keeps evolving with its last-frame velocity, faded out with smootherstep.
        if j <= JOIN:
            u = smoother(j / JOIN)
            ext = {}
            for n in a:
                if n in R[-1]:
                    l1, q1, s1 = R[-2][n].decompose(); l2, q2, s2 = R[-1][n].decompose()
                    dq = q1.inverted() @ q2
                    steps = min(j, 12) * (1 - u)
                    ext[n] = Matrix.LocRotScale(l2 + (l2 - l1) * steps, q2 @ scale_rot(dq, steps), s2)
            a = {n: mixm(ext[n], m, u) if n in ext else m for n, m in a.items()}
        end = len(A) - 1
        if j >= end - OUTRO:
            u = smoother((j - (end - OUTRO)) / OUTRO)
            hip_off = a["Hips"].translation - I["Hips"].translation
            hip_off.z = 0
            tgt = {n: Matrix.Translation(hip_off) @ m for n, m in I.items()}
            a = {n: mixm(m, tgt[n], u) if n in tgt and n != "VeyrRoot" else m for n, m in a.items()}
        frames.append(a)
    # Write armature-space poses onto the roll armature (parent before child).
    arm = roll
    arm.animation_data_clear(); arm.animation_data_create(); arm.animation_data.action = bpy.data.actions.new(name)
    s.render.fps = HZ
    order = []
    def walk(b):
        order.append(b)
        for c in b.children:
            walk(c)
    for b in arm.pose.bones:
        b.rotation_mode = "QUATERNION"
        if b.parent is None:
            walk(b)
    prev = {}
    for f, pose in enumerate(frames):
        for b in order:
            if b.name in pose:
                b.matrix = pose[b.name]
                bpy.context.view_layer.update()
        for b in order:
            q = b.rotation_quaternion.copy()
            if b.name in prev:
                q.make_compatible(prev[b.name])
            prev[b.name] = q.copy(); b.rotation_quaternion = q
            for prop in ("location", "rotation_quaternion", "scale"):
                b.keyframe_insert(prop, frame=f)
    s.frame_start, s.frame_end = 0, len(frames) - 1
    export(arm, roll_body, name, {"fps": HZ, "duration": (len(frames) - 1) / HZ, "rollPrefixSeconds": 1.0, "attackComposedDuration": 1.2,
                                  "joinSeconds": JOIN / HZ, "outroSeconds": OUTRO / HZ, "sources": ["Fab_Roll_v17", "Mixamo_Attack_v17", "IdleOneHand_Blender_v2r4 (end pose)"],
                                  "gripMode": "one-handed", "method": "armature-space composition; roll unchanged; join = roll extrapolated with its end velocity, smootherstep-blended into the slash over 0.40 s; final 0.36 s blends into the approved 1H idle frame 0 (VeyrRoot kept)"})

elif stage == "rotateloops":
    # Start each authored loop at its narrowest stance (ankles closest), so the first/last frame matches the idle stance width.
    HZ = 120
    loops = ["Knight_Strafe%s%s_v3" % (s_, g_) for s_ in ("Left", "Right", "RunLeft", "RunRight") for g_ in ("", "TwoHand")] + ["Knight_BackpedalGuard_v3", "Knight_BackpedalGuardTwoHand_v3"]
    rep = {}
    for nm in loops:
        out = nm[:-3] + "_v3c"
        if (only and out not in only) or (EXP / (out + ".glb")).exists():
            continue
        s = clear(); s.render.fps = HZ
        arm, body, objs = load(EXP / (nm + ".glb"))
        meta = json.loads((EXP / (nm + ".json")).read_text())
        T = meta["duration"]; n = int(round(T * HZ))
        pb = arm.pose.bones; mw = arm.matrix_world
        best = None
        for i in range(n):
            s.frame_set(i)
            d = (mw @ pb["LeftFoot"].head - mw @ pb["RightFoot"].head); d.z = 0
            if best is None or d.length < best[0]:
                best = (d.length, i)
        i0 = best[1]
        rows = basis_rows(arm, [((i0 + i) % n) for i in range(n + 1)])
        rows[-1] = rows[0]
        key_rows(arm, rows, out)
        s.frame_start, s.frame_end = 0, n
        meta2 = dict(meta, fps=HZ, bakeSampleRate=HZ, cycleStartShiftSeconds=i0 / HZ, minAnkleDistanceMetres=best[0], derivedFrom=nm)
        meta2.pop("sha256", None)
        export(arm, body, out, meta2)
        rep[out] = {"shiftSeconds": i0 / HZ, "ankleDistanceCm": round(best[0] * 240, 1)}
    print("ROTATED", json.dumps(rep), flush=True)
