"""ParryRiposte_Blender_v1: key-pose authored two-hand parry (blade-up deflect, wrist snap, hip check), half-beat pause, committed thrust riposte with a lunge; approved two-hand idle at both ends; deep recovery breath.

Execute ONLY in the task-owned Blender (port 9885) via run_nc.py. Authoring layer: per-key body/feet/hilt/left-hand
parameters -> dense Blender control keys (FK torso/head/fingers, world hilt, IK hand/foot targets, poles);
native four-limb IK + bake from rebuild/approved_actions.py. The approved light_two scene supplies only the rig,
the approved two-hand idle start pose, grip relations and the StrongGrip sword; no source motion is reused.
"""
from pathlib import Path
import bpy, math, json, importlib.util
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent
_sp = importlib.util.spec_from_file_location("veyr_nc_clips", HERE / "clips.py"); C = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(C)
core = C.core; REPO = C.REPO; OUT = C.OUT
BASE = REPO / "Local/Blender/approved-rebuild-20261021/light_two_Blender_v1.blend"
JOB = "parry_riposte2"; REVIEW = "ParryRiposte_Blender_v1"


def bdir(az, el):
    az, el = math.radians(az), math.radians(el); return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def azel(v):
    v = v.normalized(); return math.degrees(math.atan2(v.x, -v.y)), math.degrees(math.asin(max(-1, min(1, v.z))))


def probe():
    C.open_scene(BASE); s = bpy.context.scene; s.frame_set(0); fk = bpy.data.objects["Pose_Control_Rig"]
    h = bpy.data.objects["Hilt_Control"].matrix_world; out = {"hiltPos": list(h.translation), "bladeAzEl": azel(h.to_3x3() @ Vector((0, 0, 1))), "hiltX": list((h.to_3x3() @ Vector((1, 0, 0))).normalized()), "hiltY": list((h.to_3x3() @ Vector((0, 1, 0))).normalized())}
    for n in ("Hips", "Spine2", "Neck", "Head", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand", "RightHand", "LeftUpLeg", "RightUpLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"):
        out[n] = [round(x, 4) for x in (fk.matrix_world @ fk.pose.bones[n].head)]
    for n in ("LeftLeg_Target", "RightLeg_Target", "LeftArm_Pole", "RightArm_Pole", "LeftLeg_Pole", "RightLeg_Pole"):
        out[n] = [round(x, 4) for x in bpy.data.objects[n].matrix_world.translation]
    return out


# ------------------------------------------------------------------ key poses -----------------------
# Units: metres-ish rig units; character faces -Y, +X is its left. Angles in degrees.
# hilt = socket offset from the chest (Spine2 head) in the chest-yaw frame; blade az/el in the chest-yaw frame
# (az 0 = forward, - = toward the right side, el + = up). lw = left hand on hilt (1) / free (0).
IDLE = dict(hips=(0, 0, 0), hyaw=0, hlean=0, hroll=0, cyaw=0, clean=0, hilt=(-.042, -.125, .036), az=-24, el=68, roll=0,
            lw=1, lfree=(.18, -.22, -.05), lf=(0, 0, 0), lfyaw=0, lfp=0, rf=(0, 0, 0), rfyaw=0, rfp=0, rpole=(-.51, -.12, -.08), lpole=(.42, -.20, -.15))
KEYS = [
    (0.00, {}),
    # ---- parry: small dip, lead foot steps in, blade snaps up to catch high-left (contact f6) ----------------------------
    (0.0667, dict(hilt=(-.05, -.14, .01), az=-25, el=62, cyaw=-6, hyaw=-3, hips=(0, .005, -.012), hlean=2)),
    (0.10, dict(lf=(.004, -.01, .02))),
    (0.1333, dict(hilt=(-.03, -.19, .08), az=-2, el=70, cyaw=4, hyaw=2, hips=(.01, -.015, -.018), lf=(.015, -.045, .025), rpole=(-.45, -.12, -.15))),
    (0.1667, dict(lf=(.02, -.06, 0))),
    (0.20, dict(hilt=(0.0, -.22, .12), az=16, el=72, cyaw=10, hyaw=8, hips=(.02, -.03, -.02), hlean=3, rfp=6)),
    (0.2333, "hold"),
    # ---- wrist snap outward + hip check (released at full speed) -------------------------------------------------------
    (0.2667, dict(hilt=(.02, -.22, .11), az=45, el=56, cyaw=24, hyaw=22, hips=(.03, -.035, -.022), hlean=4, rfp=10, rfyaw=6)),
    (0.30, dict(hilt=(.03, -.21, .10), az=58, el=48, cyaw=28, hyaw=24)),
    (0.3333, dict(hilt=(.03, -.20, .09), az=62, el=46, cyaw=27, hyaw=23, hips=(.03, -.033, -.022))),
    # ---- half-beat pause: the blade drifts, weight settles ------------------------------------------------------------
    (0.4333, dict(hilt=(.02, -.20, .085), az=57, el=49, cyaw=24, hyaw=20, hips=(.026, -.03, -.022), rfp=6)),
    (0.50, dict(hilt=(.01, -.20, .08), az=50, el=52, cyaw=20, hyaw=17, hips=(.022, -.028, -.022))),
    # ---- riposte chamber: hands back to the right hip, point forward, weight back ---------------------------------------
    (0.5667, dict(hilt=(-.09, -.17, .02), az=10, el=25, cyaw=-8, hyaw=-4, hips=(.0, 0, -.026), rfp=0, rfyaw=0)),
    (0.6333, dict(hilt=(-.16, -.11, -.05), az=-6, el=4, cyaw=-28, hyaw=-14, hips=(-.02, .03, -.03), hlean=-2, rpole=(-.42, .15, -.25), lpole=(.42, -.10, -.20))),
    # ---- committed thrust: lunge (lead foot lifts f20, plants f22), hips drive, lean; contact f23 ----------------------
    (0.6667, dict(lf=(.022, -.08, .04))),
    (0.70, dict(hilt=(-.09, -.17, -.03), az=-3, el=3, cyaw=-6, hyaw=-2, hips=(-.005, -.05, -.04), hlean=6, lf=(.025, -.14, .03))),
    (0.7333, dict(lf=(.03, -.20, 0), rfp=12, rfyaw=4)),
    (0.7667, dict(hilt=(-.05, -.25, -.01), az=2, el=2, cyaw=12, hyaw=8, hips=(.01, -.13, -.055), hlean=13, rfp=18, rpole=(-.45, -.05, -.20), lpole=(.42, -.20, -.15))),
    (0.80, "hold"),
    (0.8333, dict(hilt=(-.075, -.215, -.004), az=-4, el=12, cyaw=15, hyaw=10, hips=(.014, -.162, -.062), hlean=15)),
    (0.8667, dict(hilt=(-.088, -.20, 0.0), az=-6, el=17, cyaw=12, hyaw=9, hips=(.013, -.152, -.06), hlean=14)),
    (0.90, dict(hilt=(-.097, -.187, .003), az=-8, el=21, cyaw=8, hyaw=6, hips=(.01, -.135, -.052), hlean=12)),
    (0.9333, dict(hilt=(-.10, -.18, .006), az=-10, el=24, cyaw=6, hyaw=5, hips=(.008, -.12, -.046), hlean=11)),
    # ---- recovery: retract, step back to the start position (in place), approved idle --------------------------------
    (1.0333, dict(hilt=(-.10, -.18, 0.0), az=-12, el=30, cyaw=4, hyaw=3, hips=(.005, -.09, -.035), hlean=8, rfp=8)),
    (1.10, dict(lf=(.025, -.17, .03))),
    (1.20, dict(lf=(.012, -.08, .04), hips=(0, -.04, -.015))),
    (1.30, dict(hilt=(-.06, -.14, .03), az=-20, el=55, cyaw=0, hyaw=0, hips=(0, -.005, -.006), hlean=2, lf=(0, 0, 0), rfp=0, rfyaw=0, rpole=(-.51, -.12, -.08), lpole=(.42, -.20, -.15))),
    (1.42, dict(IDLE)),
]
DURATION = 2.0
WRIST_MIN = 0.
TR = {"B": None, "d": None}
ORIENT_TRANSPORT = (9., 9., 9.)  # not needed here (blade never passes the anti-idle direction)
HITSTOPS = [[.20, .2333], [.7667, .80]]  # parry contact and thrust impact: 2 identical sheet frames each, full-speed release
END_IDLE_T = 1.40
BREATH = dict(t0=1.42, t1=2.0, chest=3.5, rise=.024, lift=.012, clav=27.)  # deep post-riposte breath  # one deep post-combo recovery breath; ends exactly on the approved idle


# ------------------------------------------------------------------ evaluation ----------------------
def merged_keys():
    """Per-parameter key lists: a parameter is keyed only where a key sets it (no accidental holds);
    a "hold" freezes every parameter from the previous key time to the hold time (hit-stop)."""
    pk = {n: [(0., v)] for n, v in IDLE.items()}
    for t, k in KEYS[1:]:
        if k == "hold": continue
        te = unwarp(t)
        for n, v in k.items(): pk[n] = [kv for kv in pk[n] if kv[0] < te - 1e-9] + [(te, v)]
    return pk


def unwarp(t):
    """Clip time -> motion time: hit-stop windows freeze the motion clock, which then resumes at full speed."""
    te = t
    for a, b in HITSTOPS:
        if t >= b: te -= (b - a)
        elif t > a: te -= (t - a)
    return te


def _eval(lst, t):
    v0 = lst[0][1]
    if isinstance(v0, (tuple, list, Vector)):
        return tuple(C.pchip([(kt, kv[i]) for kt, kv in lst], t) for i in range(len(v0)))
    return C.pchip(lst, t)


def param(keys, name, t):
    v = _eval(keys[name], t)
    return Vector(v) if isinstance(v, tuple) else v


def wr(fk, name, axis, deg):
    if abs(deg) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy()
    b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(deg), 4, axis) @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()


CORR_FILE = OUT / JOB / "collision-correction.json"
CORR = {}


def load_corr():
    CORR.clear()
    if CORR_FILE.exists(): CORR.update({int(k): v for k, v in json.loads(CORR_FILE.read_text()).items()})


def solve_collisions(scan="contact-scan", gain=1.3, margin=.006, sigma=3.0):
    """One relaxation step: from the last contact scan, add a smoothed correction per frame.
    Handle/pommel contacts (sword-local z < -.05) -> rotate the sword about the right palm so the touching point moves
    along the push normal; blade contacts -> translate the sword (and both hands) along the push normal."""
    rows = {int(k): v for k, v in json.loads((OUT / JOB / (scan + ".json")).read_text()).items()}; nfr = max(rows) + 1
    inc = {f: (Vector(), Vector()) for f in range(nfr)}
    for f, r in rows.items():
        if r["n"] <= 3: continue
        d = (r["depth"] + margin) * gain; p = -Vector(r["push"]); blade = Vector(r["blade"])  # vertex inside: move the sword surface along -normal
        inc[f] = (Vector(), p * min(d, .02))  # translation only (rotations about the palm proved unstable)
    load_corr(); out = {}
    for f in range(nfr):
        wsum = 0.; rv = Vector(); tr = Vector()
        for g in range(max(0, f - 9), min(nfr, f + 10)):
            w = math.exp(-((g - f) / sigma) ** 2); wsum += w; rv += inc[g][0] * w; tr += inc[g][1] * w
        rv /= wsum; tr /= wsum
        o_rv, o_tr = (Vector(CORR[f][0]), Vector(CORR[f][1])) if f in CORR else (Vector(), Vector())
        n_rv, n_tr = o_rv + rv * 2.2, o_tr + tr * 2.2  # gaussian spreading dilutes a single-frame push; re-scale
        if n_rv.length > 1e-7 or n_tr.length > 1e-7: out[f] = [list(n_rv), list(n_tr)]
    # exact approved idle at both ends; corrections frozen through each hit-stop (the hold stays a true freeze)
    for f in list(out):
        w = C.smooth01(f / 15.) * C.smooth01((nfr - 1 - f) / 15.)
        out[f] = [list(Vector(out[f][0]) * w), list(Vector(out[f][1]) * w)]
    for t0, t1 in HITSTOPS:
        f0, f1 = round(t0 * 150), round(t1 * 150); v = out.get(f0, [[0, 0, 0], [0, 0, 0]])
        for f in range(f0, f1 + 1): out[f] = v
    C.writable(CORR_FILE).write_text(json.dumps(out)); load_corr()
    return {"frames": len(out), "maxRotDeg": max((math.degrees(Vector(v[0]).length) for v in out.values()), default=0), "maxTrans": max((Vector(v[1]).length for v in out.values()), default=0)}


def author():
    C.open_scene(BASE); s = bpy.context.scene; s.frame_set(0); bpy.context.view_layer.update()
    fk = bpy.data.objects["Pose_Control_Rig"]; hilt = bpy.data.objects["Hilt_Control"]; objs = {n: bpy.data.objects[n] for n in C.CTRL}
    idle_basis = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    H0 = hilt.matrix_world.copy(); RT0 = objs["RightArm_Target"].matrix_world.copy(); LT0 = objs["LeftArm_Target"].matrix_world.copy()
    grip_rel = RT0.inverted() @ H0; left_rel = H0.inverted() @ LT0; dir0 = (H0.to_3x3() @ Vector((0, 0, 1))).normalized(); rot0 = H0.to_3x3().normalized()
    feet0 = {sd: objs[sd + "Leg_Target"].matrix_world.copy() for sd in ("Left", "Right")}; legpole0 = {sd: objs[sd + "Leg_Pole"].matrix_world.translation.copy() for sd in ("Left", "Right")}
    ball0 = {sd: (fk.matrix_world @ fk.pose.bones[sd + "ToeBase"].head).copy() for sd in ("Left", "Right")}
    lhand_rot0 = LT0.to_3x3().normalized()
    free = C._load("heavy")["f"][105]["fk"]; free_fingers = {n: C._M(v) for n, v in free.items() if n.startswith("LeftHand") and n != "LeftHand"}
    # rebuild the control layer
    old = s.get("rebuild_job"); coll = bpy.data.collections["AUTHORING_" + old]; coll.name = "AUTHORING_" + JOB
    s["rebuild_job"] = JOB; s["duration"] = DURATION; fps = 150; s.render.fps = fps; s.render.fps_base = 1; s.frame_start = 0; s.frame_end = round(DURATION * fps)
    for m in list(s.timeline_markers): s.timeline_markers.remove(m)
    for o in [fk, *objs.values()]:
        mw = o.matrix_world.copy(); o.animation_data_clear(); o.constraints.clear(); o.parent = None; o.matrix_world = mw
    for o in list(coll.objects):
        if o.name.endswith("_Follow"): bpy.data.objects.remove(o, do_unlink=True)
    leg_len = {sd: (fk.pose.bones[sd + "Leg"].head - fk.pose.bones[sd + "UpLeg"].head).length + (fk.pose.bones[sd + "Foot"].head - fk.pose.bones[sd + "Leg"].head).length for sd in ("Left", "Right")}
    arm_len = {sd: ((fk.pose.bones[sd + "ForeArm"].head - fk.pose.bones[sd + "Arm"].head).length, (fk.pose.bones[sd + "Hand"].head - fk.pose.bones[sd + "ForeArm"].head).length) for sd in ("Left", "Right")}
    ch0 = fk.pose.bones["Spine2"].head.copy() if False else None
    s.frame_set(0)
    IDLE["hilt"] = tuple(H0.translation - (fk.matrix_world @ fk.pose.bones["Spine2"].head)); IDLE["az"], IDLE["el"] = azel(dir0)
    for i, (t, k) in enumerate(KEYS):
        if isinstance(k, dict) and t >= END_IDLE_T: KEYS[i] = (t, dict(IDLE))
    reach_log = []
    TR["B"] = None; TR["d"] = None
    load_corr(); keys = merged_keys(); prev = {}; hips_rest = fk.data.bones["Hips"].matrix_local.to_3x3().inverted()
    for fr in range(s.frame_end + 1):
        t = fr / fps; P = {n: param(keys, n, unwarp(t)) for n in IDLE}
        for b in fk.pose.bones: b.matrix_basis = idle_basis[b.name]
        breath0 = math.sin(math.pi * (t - BREATH["t0"]) / (BREATH["t1"] - BREATH["t0"])) ** 2 if BREATH["t0"] < t < BREATH["t1"] else 0.
        fk.pose.bones["Hips"].location += hips_rest @ (Vector(P["hips"]) + Vector((0, 0, BREATH.get("lift", 0.) * breath0))); bpy.context.view_layer.update()
        wr(fk, "Hips", "X", P["hlean"])
        breath = 0.
        if BREATH["t0"] < t < BREATH["t1"]: breath = math.sin(math.pi * (t - BREATH["t0"]) / (BREATH["t1"] - BREATH["t0"])) ** 2
        for n, l in (("Spine", .4), ("Spine1", .35), ("Spine2", .25)): wr(fk, n, "X", P["clean"] * l + (BREATH["chest"] * breath if n == "Spine2" else 0))
        wr(fk, "Neck", "X", -.35 * (P["hlean"] + P["clean"])); wr(fk, "Head", "X", -.45 * (P["hlean"] + P["clean"]) - .5 * BREATH["chest"] * breath)
        U = (fk.pose.bones["Neck"].head - fk.pose.bones["Hips"].head).normalized()
        wr(fk, "Hips", U, P["hyaw"]); tw = P["cyaw"] - P["hyaw"]
        for n, sh in (("Spine", .35), ("Spine1", .35), ("Spine2", .30)): wr(fk, n, U, sh * tw)
        UN = (fk.pose.bones["Head"].head - fk.pose.bones["Neck"].head).normalized(); wr(fk, "Neck", UN, -.4 * P["cyaw"]); wr(fk, "Head", UN, -.45 * P["cyaw"])
        wr(fk, "Hips", "Y", P["hroll"])
        for _ in range(4):  # leg reach: lower the pelvis rather than over-extend a planted leg
            worst = 0.
            for sd in ("Left", "Right"):
                ank = feet0[sd].translation + Vector(P["lf"] if sd == "Left" else P["rf"])
                worst = max(worst, (ank - fk.pose.bones[sd + "UpLeg"].head).length - leg_len[sd] * .99)
            if worst <= 0: break
            hb = fk.pose.bones["Hips"]; m = hb.matrix.copy(); m.translation.z -= worst * 1.2; hb.matrix = m; bpy.context.view_layer.update()
        for n, sg in (("LeftShoulder", -1), ("RightShoulder", 1)): wr(fk, n, "Y", sg * BREATH.get("clav", 1.5) * breath)  # shoulders lift with the breath
        # left-hand fingers: grip shape <-> relaxed free shape
        for sd, pitch in (("Left", P["lfp"]), ("Right", P["rfp"])):
            if abs(pitch) > 1e-6:
                tb = fk.pose.bones[sd + "ToeBase"]; m = tb.matrix.copy(); ax = (fk.pose.bones[sd + "Foot"].matrix.to_3x3() @ (feet0[sd].to_3x3().inverted() @ Vector((1, 0, 0)))).normalized()
                tb.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(-pitch), 4, ax) @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()
        lw = max(0., min(1., P["lw"]))
        for n, m in free_fingers.items(): fk.pose.bones[n].matrix_basis = C._mblend(m, idle_basis[n], lw)
        bpy.context.view_layer.update()
        for b in fk.pose.bones: core.key(b, fr, prev)
        chest = fk.pose.bones["Spine2"].head.copy(); Rc = Matrix.Rotation(math.radians(P["cyaw"]), 3, "Z")
        d = Rc @ bdir(P["az"], P["el"])
        # wrist sanity: the handle below the gripping hand must not point back along that forearm (pommel into the arm).
        hp = chest + Rc @ Vector(P["hilt"]); fixes = [("Right", Rc @ Vector(P["rpole"]), 1. - lw)]  # one-hand phases only
        for sd, pole_rel, wgt in fixes:
            S = fk.pose.bones[sd + "Arm"].head; l1 = arm_len[sd][0]; l2 = arm_len[sd][1]; Hh = hp + d * (-.075 * .4096 if sd == "Right" else -.255 * .4096)
            dv = Hh - S; dist = min(dv.length, l1 + l2 - 1e-4); u = dv.normalized(); a_ = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist); h_ = math.sqrt(max(0., l1 * l1 - a_ * a_))
            Pp = chest + pole_rel; wv = (Pp - S) - u * (Pp - S).dot(u)
            if wv.length < 1e-6: continue
            E = S + u * a_ + wv.normalized() * h_; fdir = (E - Hh).normalized(); pom = -d; ang = math.degrees(pom.angle(fdir))
            need = WRIST_MIN - ang
            if need > 0:
                ax = fdir.cross(pom)
                if ax.length > 1e-6: d = -(Matrix.Rotation(math.radians(need * wgt), 3, ax.normalized()) @ pom)
        Rd = dir0.rotation_difference(d).to_matrix() @ rot0
        a0, a1, a2 = ORIENT_TRANSPORT  # heavy wind-up only: the idle-referenced frame flips as the blade passes the anti-idle direction
        if t < a0 or t > a2: Bt = Rd; TR["B"] = None
        else:
            TR["B"] = Rd.copy() if TR["B"] is None else TR["d"].rotation_difference(d).to_matrix() @ TR["B"]
            wb = C.smooth01((t - a1) / (a2 - a1)); Bt = TR["B"] if wb <= 0 else C._mblend(TR["B"].to_4x4(), Rd.to_4x4(), wb).to_3x3()
        TR["d"] = d.copy()
        R = Matrix.Rotation(math.radians(P["roll"]), 3, d) @ Bt
        H = Matrix.Translation(chest + Rc @ Vector(P["hilt"]) + Vector((0, 0, BREATH["rise"] * breath))) @ R.to_4x4() @ Matrix.Diagonal(H0.to_scale().to_4d())
        if fr in CORR:  # collision correction field (rotation about the right palm + translation), solved from the baked mesh
            rv, tr = Vector(CORR[fr][0]), Vector(CORR[fr][1]); palm = H @ Vector((0, 0, -.075))
            if rv.length > 1e-7: H = Matrix.Translation(palm) @ Matrix.Rotation(rv.length, 4, rv.normalized()) @ Matrix.Translation(-palm) @ H
            H = Matrix.Translation(tr) @ H
        for sd, wgt in (("Right", 1.), ("Left", lw)):
            if wgt < .5: continue
            Sh = fk.pose.bones[sd + "Arm"].head; tgt = (H @ grip_rel.inverted()).translation if sd == "Right" else (H @ left_rel).translation
            L = (arm_len[sd][0] + arm_len[sd][1]) * .955; dv = tgt - Sh
            if dv.length > L:
                H = Matrix.Translation(-dv.normalized() * (dv.length - L)) @ H; reach_log.append((fr, sd, round(dv.length / L, 3)))
        hilt.matrix_world = H; core.key(hilt, fr, prev)
        objs["RightArm_Target"].matrix_world = H @ grip_rel.inverted(); core.key(objs["RightArm_Target"], fr, prev)
        Lg = H @ left_rel; Lf = Matrix.LocRotScale(chest + Rc @ Vector(P["lfree"]), (Rc @ lhand_rot0).to_quaternion(), Lg.to_scale())
        LT = C._mblend(Lf, Lg, lw); Sh = fk.pose.bones["LeftArm"].head; dv = LT.translation - Sh; L = (arm_len["Left"][0] + arm_len["Left"][1]) * .975
        if dv.length > L: LT = Matrix.Translation(-dv.normalized() * (dv.length - L)) @ LT; reach_log.append((fr, "LeftFree", round(dv.length / L, 3)))
        objs["LeftArm_Target"].matrix_world = LT; core.key(objs["LeftArm_Target"], fr, prev)
        objs["RightArm_Pole"].location = chest + Rc @ Vector(P["rpole"]); objs["LeftArm_Pole"].location = chest + Rc @ Vector(P["lpole"])
        for sd, off, yaw, pitch in (("Left", P["lf"], P["lfyaw"], P["lfp"]), ("Right", P["rf"], P["rfyaw"], P["rfp"])):
            m0 = feet0[sd]; off = Vector(off); piv = ball0[sd] + off
            m = Matrix.Translation(off) @ Matrix.Translation(m0.translation) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Translation(-m0.translation) @ m0
            m = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(pitch), 4, "X") @ Matrix.Translation(-piv) @ m
            objs[sd + "Leg_Target"].matrix_world = m; core.key(objs[sd + "Leg_Target"], fr, prev)
            objs[sd + "Leg_Pole"].location = legpole0[sd] + off + Vector((0, 0, 0))
        for n in ("RightArm_Pole", "LeftArm_Pole", "LeftLeg_Pole", "RightLeg_Pole"): objs[n].keyframe_insert("location", frame=fr)
    for o in [fk, *objs.values()]:
        for fc in core.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    for t, k in KEYS: s.timeline_markers.new(f"key {t:.3f}", frame=round(t * fps))
    s["review_name"] = REVIEW; s["two_hand"] = True; s["hit_stops"] = json.dumps(HITSTOPS)
    s["nc_segments"] = json.dumps([{"authored": "key poses", "keys": [k[0] for k in KEYS]}])
    tx = bpy.data.texts.get("newclips_combo2.py") or bpy.data.texts.new("newclips_combo2.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s["reach_clamps"] = json.dumps(reach_log); core.at(0); return {"frames": s.frame_end, "reachClamps": len(reach_log), "worst": sorted(reach_log, key=lambda x: -x[2])[:5]}


def freeze_holds():
    """Copy the baked pose of each hit-stop's first frame over the whole window (deform rig + weapon socket)."""
    s = bpy.context.scene; fps = s.render.fps; n = 0
    for name in ("Knight_Deform", "ReviewWeaponSocket"):
        o = bpy.data.objects[name]
        for fc in core.curves(o.animation_data.action):
            pts = {round(k.co.x): k for k in fc.keyframe_points}
            for a, b in HITSTOPS:
                f0, f1 = math.ceil(a * fps - 1e-6), math.floor(b * fps + 1e-6)
                if f0 not in pts: continue
                v = pts[f0].co.y
                for f in range(f0 + 1, f1 + 1):
                    if f in pts: pts[f].co.y = v; pts[f].handle_left.y = v; pts[f].handle_right.y = v; n += 1
            fc.update()
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True); return {"frozenKeys": n}


def build():
    r = author(); b = C.bake_job(JOB, "key-pose authored (light_two rig/idle only)"); fz = freeze_holds(); return {**r, **b, **fz}


def track(step=6):
    s = bpy.context.scene; sock = bpy.data.objects["ReviewWeaponSocket"]; rig = bpy.data.objects["Knight_Deform"]; out = []; keys = merged_keys()
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); m = sock.matrix_world; a, e = azel(m.to_3x3() @ Vector((0, 0, 1))); t = fr / s.render.fps
        out.append((round(t, 2), round(a), round(e), round(param(keys, "az", t) + param(keys, "cyaw", t)), round(param(keys, "el", t)), [round(x, 2) for x in m.translation], round((rig.matrix_world @ rig.pose.bones["Head"].head).z, 3)))
    return out


def sheet_metrics(px_per_unit=500 / 2.2, fps=30):
    """What the critic reads off the 30 fps sheets: blade tip speed (px/frame), front-view blade angle,
    head height (px vs frame 0), left/right foot lift, freeze frames."""
    s = bpy.context.scene; sock = bpy.data.objects["ReviewWeaponSocket"]; rig = bpy.data.objects["Knight_Deform"]
    sw = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); zmax = max(v.co.z for v in sw.data.vertices)
    n = round(s["duration"] * fps) + 1; rows = []; prev = None
    for i in range(n):
        t = min(s["duration"], i / fps); ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        m = sock.matrix_world; tip = m @ Vector((0, 0, zmax)); d = m.to_3x3() @ Vector((0, 0, 1))
        head = (rig.matrix_world @ rig.pose.bones["Head"].head)
        r = {"f": i, "t": round(t, 3), "tipSpeedPx": round((tip - prev).length * px_per_unit, 1) if prev is not None else 0., "frontAngle": round(math.degrees(math.atan2(d.z, d.x)) % 180, 1),
             "headPx": round(head.z * px_per_unit, 1), "lfZ": round((rig.matrix_world @ rig.pose.bones["LeftFoot"].head).z, 3), "rfZ": round((rig.matrix_world @ rig.pose.bones["RightFoot"].head).z, 3)}
        prev = tip.copy(); rows.append(r)
    h0 = rows[0]["headPx"]
    for r in rows: r["headDropPx"] = round(h0 - r["headPx"], 1)
    return rows


def dbg_frames(a, b):
    s = bpy.context.scene; sock = bpy.data.objects["ReviewWeaponSocket"]; out = []
    load_corr()
    for fr in range(a, b + 1):
        s.frame_set(fr); m = sock.matrix_world; az, el = azel(m.to_3x3() @ Vector((0, 0, 1)))
        c = CORR.get(fr); out.append((fr, round(az, 1), round(el, 1), [round(x, 3) for x in m.translation], [round(x, 3) for x in c[1]] if c else None))
    return out



def body_metrics(px_per_unit=500 / 2.2, fps=30):
    """Per sheet frame: hips height (px vs frame 0), left/right foot ground positions (px), shoulder (clavicle) height
    and chest top height (px vs frame 0), so footwork, sink-after-hit and breathing can be read numerically."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000 and not o.get("review_prop"))
    chest_ids = C._groups(body, ("Spine2", "LeftShoulder", "RightShoulder"))
    sw = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); zmax = max(v.co.z for v in sw.data.vertices)
    n = round(s["duration"] * fps) + 1; rows = []
    for i in range(n):
        t = min(s["duration"], i / fps); ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        W = lambda b: rig.matrix_world @ rig.pose.bones[b].head
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); top = max((ev.matrix_world @ me.vertices[j].co).z for j in chest_ids); ev.to_mesh_clear()
        rows.append({"f": i, "hipsZ": W("Hips").z, "lfY": W("LeftFoot").y, "lfX": W("LeftFoot").x, "lfZ": W("LeftFoot").z, "rfY": W("RightFoot").y, "rfX": W("RightFoot").x, "rfZ": W("RightFoot").z,
                     "shoulderZ": (W("LeftArm").z + W("RightArm").z) / 2, "chestTopZ": top, "tip": list(sock.matrix_world @ Vector((0, 0, zmax)))})
    r0 = rows[0]
    out = [{"f": r["f"], "hipsPx": round((r["hipsZ"] - r0["hipsZ"]) * px_per_unit, 1), "lfPx": [round((r["lfX"] - r0["lfX"]) * px_per_unit, 1), round((r["lfY"] - r0["lfY"]) * px_per_unit, 1), round((r["lfZ"] - r0["lfZ"]) * px_per_unit, 1)],
            "rfPx": [round((r["rfX"] - r0["rfX"]) * px_per_unit, 1), round((r["rfY"] - r0["rfY"]) * px_per_unit, 1), round((r["rfZ"] - r0["rfZ"]) * px_per_unit, 1)],
            "shoulderPx": round((r["shoulderZ"] - r0["shoulderZ"]) * px_per_unit, 2), "chestTopPx": round((r["chestTopZ"] - r0["chestTopZ"]) * px_per_unit, 2),
            "tipDriftPx": round((Vector(r["tip"]) - Vector(r0["tip"])).length * px_per_unit, 2)} for r in rows]
    return out
