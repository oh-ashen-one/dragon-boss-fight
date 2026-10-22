"""RollAttack_Blender_v1: the owner-praised RollBoat roll copied EXACTLY (0-0.78 s, all body tracks), then a key-pose authored rising one-hand slash out of the roll into the approved one-hand idle, deep recovery breath.

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
BASE = REPO / "Local/Blender/approved-rebuild-20261021/idle_one_Blender_v1.blend"  # approved one-hand idle scene
ROLL = OUT / "roll_source/RollBoat.glb"  # owner-praised roll (sha 49b944d0...), copied exactly for 0-0.78 s
ROLL_END_F = 117; ROLL_BLEND_F = 18  # roll frames 0..117 exact; blend into the authored slash over 18 frames
JOB = "roll_attack"; REVIEW = "RollAttack_Blender_v1"


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
    # 0-0.78 s: the roll is copied exactly after the bake. These two keys are the roll's own last poses read back in
    # authoring space (pose_params at f108/f117), so the authored motion leaves the roll with the roll's own velocity.
    (0.72, dict(hips=(.019, .068, .016), lf=(-.192, .105, .032), rf=(-.049, -.002, .083), lfyaw=19.2, rfyaw=74.6, lfp=12.3, rfp=5.9, cyaw=33.6, hyaw=34.6, hlean=4,
                hilt=(-.393, .039, -.074), az=-121.8, el=62.1, lfree=(.057, -.051, -.131), rpole=(-.45, .30, -.05))),
    (0.78, dict(hips=(.019, .068, .021), lf=(-.162, .198, .028), rf=(-.055, .092, .071), lfyaw=26.6, rfyaw=86.8, lfp=13.8, rfp=8.5, cyaw=35.6, hyaw=36.2, hlean=4,
                hilt=(-.38, .067, -.107), az=-105, el=70, lfree=(.056, -.038, -.118), rpole=(-.45, .30, -.05))),
    # ---- landing out of the roll: right foot plants, knees absorb, the blade starts dropping behind the right side ------
    (0.85, dict(rf=(-.06, .11, 0), rfyaw=62, rfp=0, lf=(-.16, .21, 0), lfyaw=24, lfp=5, hips=(.015, .07, -.035), hlean=6, cyaw=25, hyaw=28,
                  hilt=(-.30, .09, -.12), az=-114, el=48, lfree=(.09, -.08, -.12))),
    # ---- coil into the low-right load (rising-slash chamber), left foot lifts for the step-in -----------------------------
    (0.9333, dict(rfyaw=52, lf=(-.12, .12, .045), lfyaw=16, lfp=0, hips=(.01, .05, -.065), hlean=9, cyaw=-8, hyaw=10,
                hilt=(-.26, .10, -.09), az=-142, el=8, lfree=(.20, -.13, -.05), rpole=(-.40, .35, -.10))),
    (1.0, dict(lf=(-.07, .0, .05), lfyaw=10, hips=(.005, .03, -.07), hlean=10, cyaw=-30, hyaw=0, hilt=(-.25, .12, -.08), az=-145, el=-8, rpole=(-.42, .30, -.12), lfree=(.23, -.14, -.03))),
    # ---- step-in plants, rising one-hand slash low-right -> high-left; impact mid-swing with the weight on the lead foot ---
    (1.0333, dict(lf=(-.03, -.10, 0), lfyaw=4, hips=(.01, -.02, -.06), hlean=8, cyaw=-12, hyaw=4, hilt=(-.17, -.15, -.11), az=-80, el=-20, rpole=(-.50, .10, -.15))),
    (1.1, dict(hilt=(-.01, -.24, .03), az=20, el=32, cyaw=15, hyaw=8, hips=(.02, -.07, -.05), hlean=6, lfree=(.25, .04, -.06), rfp=12, rfyaw=34, rpole=(-.45, -.10, -.12))),
    (1.1333, "hold"),
    (1.1667, dict(hilt=(-.005, -.24, .08), az=42, el=44, cyaw=32, hyaw=16, hips=(.025, -.07, -.04), lfree=(.24, .10, -.04))),
    (1.2, dict(hilt=(.01, -.20, .13), az=64, el=57, cyaw=42, hyaw=20, hips=(.025, -.065, -.035))),
    (1.2333, dict(hilt=(.015, -.19, .155), az=75, el=63, cyaw=46, hyaw=22)),
    (1.3, dict(hilt=(.01, -.18, .16), az=80, el=66, cyaw=46, hyaw=22, hips=(.02, -.06, -.03), rfp=6)),
    # ---- recovery: blade comes down on the right; right foot steps up, left foot steps back into the idle stance ---------
    (1.3667, dict(rf=(-.06, .11, 0), rfp=0)),
    (1.4333, dict(hilt=(-.16, -.18, .04), az=-10, el=40, cyaw=8, hyaw=4, hips=(.01, -.03, -.025), hlean=3, rf=(-.03, .05, .04), rfyaw=14, lfree=(.20, -.05, -.10), rpole=(-.51, -.12, -.08))),
    (1.5, dict(rf=(0, 0, 0), rfyaw=0, lf=(-.03, -.10, 0), lfyaw=4)),
    (1.5667, dict(lf=(-.015, -.05, .035), lfyaw=2, hips=(.005, -.01, -.012))),
    (1.6, dict(hilt=(-.19, -.13, -.12), az=0, el=10, cyaw=2, hyaw=1, hlean=1)),
    (1.6333, dict(lf=(0, 0, 0), lfyaw=0)),
    (1.7333, dict(IDLE)),
]
DURATION = 2.2
WRIST_MIN = 0.
TR = {"B": None, "d": None}
ORIENT_TRANSPORT = (0.78, 1.0333, 1.10)  # parallel-transported blade frame: the chamber passes near the anti-idle direction
HITSTOPS = [[33 / 30, 34 / 30]]
END_IDLE_T = 1.72
BREATH = dict(t0=1.7333, t1=2.2, chest=3.5, rise=.024, lift=.012, clav=27.)  # one deep post-combo recovery breath; ends exactly on the approved idle


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
    free_fingers = {}
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
    IDLE["lfree"] = tuple(LT0.translation - (fk.matrix_world @ fk.pose.bones["Spine2"].head)); IDLE["lw"] = 0.
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


def roll_overwrite():
    """Replace the baked deform keys of frames 0..ROLL_END_F with the RollBoat action (exact), blend the next
    ROLL_BLEND_F frames from the roll's last pose into the authored slash; the sword socket follows the right hand
    with the approved one-hand grip throughout the roll."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]
    s.frame_set(ROLL_END_F + ROLL_BLEND_F + 2); bpy.context.view_layer.update()
    s.frame_set(0); off = None
    # grip offset from the authored (baked) frame just after the blend window: hand -> socket
    f_ref = ROLL_END_F + ROLL_BLEND_F + 1; s.frame_set(f_ref); bpy.context.view_layer.update()
    off = (rig.matrix_world @ rig.pose.bones["RightHand"].matrix).inverted() @ sock.matrix_world
    baked = {}
    for f in range(ROLL_END_F + 1, ROLL_END_F + ROLL_BLEND_F + 1):
        s.frame_set(f); bpy.context.view_layer.update(); baked[f] = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.import_scene.gltf(filepath=str(ROLL))
    added = set(bpy.data.objects) - before; src = next(o for o in added if o.type == "ARMATURE")
    roll = {}
    for f in range(ROLL_END_F + 1):
        s.frame_set(f); bpy.context.view_layer.update(); roll[f] = {b.name: b.matrix_basis.copy() for b in src.pose.bones}
    for o in added: bpy.data.objects.remove(o, do_unlink=True)
    prev = {}
    for f in range(ROLL_END_F + ROLL_BLEND_F + 1):
        if f <= ROLL_END_F: pose = roll[f]
        else:
            w = C.smooth01((f - ROLL_END_F) / (ROLL_BLEND_F + 1)); pose = {n: C._mblend(roll[ROLL_END_F][n], baked[f][n], w) for n in roll[ROLL_END_F]}
        for b in rig.pose.bones: b.matrix_basis = pose[b.name]
        bpy.context.view_layer.update()
        for b in rig.pose.bones: core.key(b, f, prev)
        if f <= ROLL_END_F + ROLL_BLEND_F: sock.matrix_world = (rig.matrix_world @ rig.pose.bones["RightHand"].matrix) @ off; core.key(sock, f, prev)
    for o in (rig, sock):
        for fc in core.curves(o.animation_data.action):
            for k in fc.keyframe_points: k.interpolation = "LINEAR"
    s["roll_source"] = str(ROLL); s["roll_frames"] = json.dumps([0, ROLL_END_F]); s["roll_blend_frames"] = ROLL_BLEND_F
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True); return {"rollFrames": ROLL_END_F + 1, "blend": ROLL_BLEND_F}


def build():
    r = author(); b = C.bake_job(JOB, "RollBoat (exact) + key-pose authored rising slash"); ro = roll_overwrite(); fz = freeze_holds(); return {**r, **b, **ro, **fz}


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


def roll_exactness():
    """Max difference between the baked deform pose and the RollBoat source for frames 0..ROLL_END_F (world bone heads + rotations)."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.import_scene.gltf(filepath=str(ROLL))
    added = set(bpy.data.objects) - before; src = next(o for o in added if o.type == "ARMATURE")
    pos = 0.; rot = 0.
    for f in range(0, ROLL_END_F + 1):
        s.frame_set(f); bpy.context.view_layer.update()
        for b in rig.pose.bones:
            a = rig.matrix_world @ b.matrix; c = src.matrix_world @ src.pose.bones[b.name].matrix
            pos = max(pos, (a.translation - c.translation).length); rot = max(rot, math.degrees(a.to_quaternion().rotation_difference(c.to_quaternion()).angle))
    for o in added: bpy.data.objects.remove(o, do_unlink=True)
    return {"framesChecked": ROLL_END_F + 1, "maxBonePosDiff": pos, "maxBoneRotDiffDeg": rot}


def pose_params(fr, ref=None):
    """Authoring-space readout of the baked pose at frame fr vs the final (approved idle) frame: hips/feet deltas,
    chest/hips yaw, socket offset from the chest in the chest-yaw frame and blade az/el in that frame."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]; ref = s.frame_end if ref is None else ref
    def rd(f):
        s.frame_set(f); bpy.context.view_layer.update(); W = lambda b: (rig.matrix_world @ rig.pose.bones[b].matrix)
        yaw = lambda b: math.degrees(math.atan2(*(lambda v: (v.x, -v.y))((W(b).to_3x3() @ Vector((0, 0, 1))).normalized()))) if False else None
        def across(l, r):
            a = W(l).translation - W(r).translation; return math.degrees(math.atan2(a.y, a.x))
        return {"hips": W("Hips").translation.copy(), "lf": W("LeftFoot").translation.copy(), "rf": W("RightFoot").translation.copy(), "chest": W("Spine2").translation.copy(),
                "cyaw": across("LeftArm", "RightArm"), "hyaw": across("LeftUpLeg", "RightUpLeg"), "sock": sock.matrix_world.copy(),
                "lt": W("LeftToeBase").translation.copy(), "rt": W("RightToeBase").translation.copy(),
                "lh": W("LeftHand").translation.copy(), "relb": W("RightForeArm").translation.copy(), "lelb": W("LeftForeArm").translation.copy()}
    fy = lambda q, sd: math.degrees(math.atan2(*(lambda v: (v.y, v.x))(q[sd + "t"] - q[sd + "f"])))
    fp = lambda q, sd: math.degrees(math.atan2((q[sd + "t"] - q[sd + "f"]).z, (q[sd + "t"] - q[sd + "f"]).xy.length))
    a = rd(fr); b = rd(ref); cy = a["cyaw"] - b["cyaw"]; Rc = Matrix.Rotation(math.radians(cy), 3, "Z")
    d = a["sock"].to_3x3() @ Vector((0, 0, 1)); hl = Rc.inverted() @ (a["sock"].translation - a["chest"]); az, el = azel(Rc.inverted() @ d)
    r3 = lambda v: [round(x, 3) for x in v]
    return {"f": fr, "hips": r3(a["hips"] - b["hips"]), "lf": r3(a["lf"] - b["lf"]), "rf": r3(a["rf"] - b["rf"]), "cyaw": round(cy, 1), "hyaw": round(a["hyaw"] - b["hyaw"], 1),
            "hilt": r3(hl), "az": round(az, 1), "el": round(el, 1), "lfree": r3(Rc.inverted() @ (a["lh"] - a["chest"])),
            "lfyaw": round(fy(a, "l") - fy(b, "l"), 1), "rfyaw": round(fy(a, "r") - fy(b, "r"), 1), "lfp": round(fp(a, "l") - fp(b, "l"), 1), "rfp": round(fp(a, "r") - fp(b, "r"), 1),
            "ltoeZ": round(a["lt"].z - b["lt"].z, 3), "rtoeZ": round(a["rt"].z - b["rt"].z, 3),
            "relb": r3(Rc.inverted() @ (a["relb"] - a["chest"])), "lelb": r3(Rc.inverted() @ (a["lelb"] - a["chest"]))}


def reach_dbg(frames):
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; out = []; keys = merged_keys()
    for fr in frames:
        s.frame_set(fr); bpy.context.view_layer.update(); t = fr / 150.; cy = param(keys, "cyaw", unwarp(t)); Ri = Matrix.Rotation(math.radians(-cy), 3, "Z")
        ch = fk.matrix_world @ fk.pose.bones["Spine2"].head; sh = fk.matrix_world @ fk.pose.bones["RightArm"].head
        tg = bpy.data.objects["RightArm_Target"].matrix_world.translation; hl = bpy.data.objects["Hilt_Control"].matrix_world.translation
        r3 = lambda v: [round(x, 3) for x in v]
        out.append({"f": fr, "cyaw": round(cy, 1), "sh": r3(Ri @ (sh - ch)), "tgt": r3(Ri @ (tg - ch)), "hilt": r3(Ri @ (hl - ch)), "dist": round((tg - sh).length, 3)})
    return out


def wrist_dbg(frames):
    """Angle between the pommel direction (-blade) and the forearm (hand->elbow); small = handle along the forearm."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]; out = []
    for fr in frames:
        s.frame_set(fr); bpy.context.view_layer.update(); W = lambda b: rig.matrix_world @ rig.pose.bones[b].head
        pom = -(sock.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized(); fa = (W("RightForeArm") - W("RightHand")).normalized(); ua = (W("RightArm") - W("RightForeArm")).normalized()
        out.append((fr, round(math.degrees(pom.angle(fa))), round(180 - math.degrees(fa.angle(-ua)))))
    return out
