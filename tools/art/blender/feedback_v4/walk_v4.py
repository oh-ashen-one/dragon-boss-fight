"""Two-hand ready walk v5 (WalkTwoHand_Blender_v5): seamless in-place LOOP. Execute ONLY in the
owned Blender MCP session (owner fable-veyr-knight-walk-20261021, port 9886) via run.py.
"""
from pathlib import Path
import bpy, importlib.util, math, json, hashlib, shutil
from mathutils import Vector, Matrix, Quaternion
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location("veyr_v4_common", HERE / "common.py"); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get("VEYR_V4_PARAMS"))
_fs = importlib.util.spec_from_file_location("feedback2", cm.REPO / "tools/art/blender/feedback/feedback_actions.py"); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OUT = P["out"]; c.OWNER = P["owner"]
REPO = cm.REPO
IDLE2 = REPO / "Local/Blender/approved-rebuild-20261021/idle_two_Blender_v1.blend"
REM = REPO / "Local/Blender/remainder-20261021/walk_two_Blender_v1.blend"


def info(path):
    cm.open_tagged(Path(path), P["owner"]); s = bpy.context.scene
    out = {"file": str(path), "job": s.get("rebuild_job"), "fps": s.render.fps, "fpsbase": s.render.fps_base, "frames": [s.frame_start, s.frame_end], "duration": s.get("duration"), "keys": {k: (str(v)[:120]) for k, v in s.items() if k not in ("session_owner",)}}
    out["objects"] = [(o.name, o.type, o.parent.name if o.parent else None, [round(x, 4) for x in o.matrix_world.translation], [cn.type for cn in o.constraints], bool(o.animation_data and o.animation_data.action)) for o in s.objects]
    rig = bpy.data.objects["Knight_Deform"]; out["rigWorld"] = [list(r) for r in rig.matrix_world]
    body = [o for o in s.objects if o.type == "MESH" and o.get("export_body")]
    out["bodies"] = [(o.name, len(o.data.vertices), len(o.data.polygons)) for o in body]
    for fr in sorted(set([0, s.frame_end // 4, s.frame_end // 2, s.frame_end])):
        s.frame_set(fr)
        out["f%d" % fr] = {n: [round(x, 4) for x in (rig.matrix_world @ rig.pose.bones[n].head)] for n in ("Hips", "Spine2", "Head", "LeftUpLeg", "RightUpLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase", "LeftHand", "RightHand")}
        out["f%d" % fr]["socket"] = [round(x, 4) for x in bpy.data.objects["ReviewWeaponSocket"].matrix_world.translation]
    out["bones"] = [b.name for b in rig.pose.bones][:80]
    return out


def _body():
    s = bpy.context.scene
    return next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and not o.get("review_prop") and len(o.data.vertices) > 1000)


def foot_ids(body, sides=("Left", "Right"), groups=("Foot", "ToeBase"), thr=.5):
    gid = {g.index: g.name for g in body.vertex_groups}
    return {sd: [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, "") in tuple(sd + g for g in groups)) > thr] for sd in sides}


def feet_geom(path=None):
    if path: cm.open_tagged(Path(path), P["owner"])
    s = bpy.context.scene; c.at(0); body = _body(); rig = bpy.data.objects["Knight_Deform"]; fk = bpy.data.objects["Pose_Control_Rig"]
    ids = foot_ids(body); ids2 = foot_ids(body, groups=("Leg", "Foot", "ToeBase"))
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
    out = {"groups": sorted(g.name for g in body.vertex_groups)[:80]}
    for sd in ("Left", "Right"):
        pts = [mw @ me.vertices[i].co for i in ids[sd]]
        fm = rig.matrix_world @ rig.pose.bones[sd + "Foot"].matrix; inv = fm.inverted()
        loc = [inv @ p for p in pts]
        z0 = min(p.z for p in pts)
        low = [p for p in pts if p.z < z0 + .006]
        out[sd] = {"n": len(pts), "minZ": z0, "x": [min(p.x for p in pts), max(p.x for p in pts)], "y": [min(p.y for p in pts), max(p.y for p in pts)], "zmax": max(p.z for p in pts),
                   "lowN": len(low), "lowX": [min(p.x for p in low), max(p.x for p in low)], "lowY": [min(p.y for p in low), max(p.y for p in low)],
                   "toeZ": min(p.z for p in pts if p.y < min(q.y for q in pts) + .03), "heelZ": min(p.z for p in pts if p.y > max(q.y for q in pts) - .03),
                   "ankle": list(fm.translation), "toeJoint": list(rig.matrix_world @ rig.pose.bones[sd + "ToeBase"].head), "toeTail": list(rig.matrix_world @ rig.pose.bones[sd + "ToeBase"].tail),
                   "footAxisY": list(fm.to_3x3().col[1].normalized()), "footAxisX": list(fm.to_3x3().col[0].normalized()), "footAxisZ": list(fm.to_3x3().col[2].normalized()),
                   "lowerLegN": len(ids2[sd]), "lowerLegX": [min((mw @ me.vertices[i].co).x for i in ids2[sd]), max((mw @ me.vertices[i].co).x for i in ids2[sd])]}
    for sd in ("Left", "Right"):
        a, k, e = [fk.pose.bones[sd + n].head for n in ("UpLeg", "Leg", "Foot")]
        out[sd]["thigh"] = (k - a).length; out[sd]["shin"] = (e - k).length; out[sd]["reach"] = (e - a).length
    ev.to_mesh_clear()
    return out


# =============================================================== walk v5 authoring ====
JOB = "walk_two"
REV = "v5r2"           # v5 = owner candidate (backed up as *.v5.*); v5r2 = critic polish round, separate export
REVIEW = "WalkTwoHand_Blender_" + REV
OUTR = P["out"] if REV == "v5" else P["out"] / ("walk_" + REV)
c.OUT = OUTR
DUR = 2.4            # two gait cycles: breath period = clip length, seamless loop
T = 1.2              # gait cycle (2 steps) -> 1.667 steps/s
KEY_FRAMES = 2       # authored key every 2 frames at 150 Hz
TUNE = dict(
    step=.25,                    # step length (rig units); stride = 2*step
    foot_x=.068,                 # |x| of sole centre (feet under hips: hip joints are +-.062)
    toe_out=6.,                  # degrees
    ahead=-.012,                  # in-place y of flat sole centre at mid-stance (forward is -Y)
    stance=.60, heel_end=.09, heel_rise=.30, heel_exp=1.5, rise_exp=1.6,
    hs_pitch=-17., to_pitch=32., lift=.032, lift_skew=.8,
    hip_z=.537, bob=.0075, bob_lag=.0, leg_comp=.0035, sway=.013, surge=.003,
    yaw=7., roll=2.6, tilt=2., tilt_osc=.8,
    lean=(10., 3., 2.), counter=(-.45, -.45, -.55), counter_lag=.035,
    breath=(1.0, 1.4, 3.5), hunch=3., arm_pole_off=(0., -.20, .08),
    hilt_k=(.65, .8, .85), hilt_off=(-.03, 0., .006), hilt_roll=-9., hilt_rot_follow=.45, hilt_lag=.06, tip_float=1.6, tip_lag=.09, hilt_breath=.006,
    head_keep=(.3, .38), head_yaw_keep=.9,
)
G = {}


def _u(t): return (t / T) % 1.0
def smooth01(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)
def bobn(t): return math.cos(4 * math.pi * (_u(t) - .30))          # +1 mid-stance (high), -1 double support
def pelvis_yaw(t): return TUNE["yaw"] * math.cos(2 * math.pi * _u(t))      # + : right hip forward (right heel strike u=0)
def pelvis_roll(t): return TUNE["roll"] * math.cos(2 * math.pi * (_u(t) - .28))  # + : left (swing) hip drops in right stance
def breath(t): return math.sin(2 * math.pi * t / DUR)


def pelvis_pos(t):
    T_ = TUNE; u = _u(t)
    return Vector((-T_["sway"] * math.cos(2 * math.pi * (u - .30)), -T_["surge"] * math.sin(4 * math.pi * (u - .30)), T_["hip_z"] + T_["bob"] * bobn(t - T_["bob_lag"]) + T_["leg_comp"] * math.cos(2 * math.pi * (u - .80))))  # longer left leg: slightly higher pelvis in left stance


def _rz(deg): return Matrix.Rotation(math.radians(deg), 4, "Z")
def _rx(deg): return Matrix.Rotation(math.radians(deg), 4, "X")


def sole_frames():
    """From the approved two-hand idle (frame 0): per-foot flat sole frame S0 and pivots."""
    s = bpy.context.scene; c.at(0); body = _body(); fk = bpy.data.objects["Pose_Control_Rig"]
    ids = foot_ids(body); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
    out = {}
    for sd in ("Left", "Right"):
        pts = [mw @ me.vertices[i].co for i in ids[sd]]
        fm = fk.pose.bones[sd + "Foot"].matrix.copy(); tm = fk.pose.bones[sd + "ToeBase"].matrix.copy()
        n = Vector((0, 0, 1))
        for _ in range(4):
            d0 = min(p.dot(n) for p in pts); band = [p for p in pts if p.dot(n) < d0 + .006]
            # least-squares plane z = a x + b y + c on band
            sx = sum(p.x for p in band); sy = sum(p.y for p in band); sz = sum(p.z for p in band); k = len(band)
            sxx = sum(p.x * p.x for p in band); syy = sum(p.y * p.y for p in band); sxy = sum(p.x * p.y for p in band); sxz = sum(p.x * p.z for p in band); syz = sum(p.y * p.z for p in band)
            A = Matrix(((sxx, sxy, sx), (sxy, syy, sy), (sx, sy, k))); rhs = Vector((sxz, syz, sz))
            a, b, _c = A.inverted() @ rhs; n = Vector((-a, -b, 1)).normalized()
        Rc = n.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
        P1 = [Rc @ p for p in pts]; zb = min(p.z for p in P1); sole = [p for p in P1 if p.z < zb + .015]
        best = None
        for k in range(-160, 161):  # min-width footprint heading, 0.25 deg steps
            a = math.radians(k * .25); ca, sa = math.cos(a), math.sin(a); xs = [ca * p.x - sa * p.y for p in sole]; w = max(xs) - min(xs)
            if best is None or w < best[0]: best = (w, a)
        ang = best[1]
        Rh = Matrix.Rotation(ang, 4, "Z")  # rotates the footprint so its length runs along Y (toes -Y)
        P2 = [Rh @ Rc @ p for p in pts]
        cen = Vector(((min(p.x for p in P2) + max(p.x for p in P2)) / 2, (min(p.y for p in P2) + max(p.y for p in P2)) / 2, min(p.z for p in P2)))
        S0 = Matrix.Translation(-cen) @ Rh @ Rc @ fm
        Ps = [Matrix.Translation(-cen) @ q for q in P2]
        tj = Matrix.Translation(-cen) @ Rh @ Rc @ tm.translation
        rot = _rx(TUNE["hs_pitch"]); low = min(Ps, key=lambda q: (rot @ q).z)
        roll = _heel_roll_table(Ps)
        out[sd] = {"roll": roll, "S0": S0, "rel_toe": fm.inverted() @ tm, "ball": Vector((0, tj.y, tj.z)), "heel": Vector((0, low.y, low.z)),
                   "len": max(q.y for q in Ps) - min(q.y for q in Ps), "width": max(q.x for q in Ps) - min(q.x for q in Ps), "tilt": math.degrees(n.angle(Vector((0, 0, 1)))), "heading": math.degrees(ang)}
    ev.to_mesh_clear(); G.update(out)
    return {sd: {k: (list(v) if isinstance(v, Vector) else v) for k, v in out[sd].items() if k not in ("S0", "rel_toe")} for sd in out}


def _heel_roll_table(Ps, steps=80):
    """Rolling (no-slip) heel rocker in the sole frame: translation c(theta) for theta in [hs_pitch, 0].
    Integrates small rotations about the current ground-contact vertex, starting flat."""
    th1 = TUNE["hs_pitch"]; d = th1 / steps; M = Matrix.Identity(4); tab = [(0., Vector((0, 0, 0)))]
    pts = [q.copy() for q in Ps]
    for k in range(steps):
        R = Matrix.Rotation(math.radians(d), 4, "X")
        piv = min(pts, key=lambda q: (Matrix.Translation(q) @ R @ Matrix.Translation(-q) @ q).z if False else (R @ q).z - q.z * 0 )
        piv = min(pts, key=lambda q: (R @ q).z)  # vertex that becomes lowest
        piv = Vector((0, piv.y, piv.z))
        step = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv)
        # keep the support exactly at z=0
        M = step @ M; pts = [step @ q for q in pts]; dz = min(q.z for q in pts)
        M = Matrix.Translation((0, 0, -dz)) @ M; pts = [q - Vector((0, 0, dz)) for q in pts]
        tab.append((d * (k + 1), M.translation.copy()))
    return tab


def _roll_offset(sd, th):
    tab = G[sd]["roll"]
    if th >= 0: return Vector((0, 0, 0))
    x = th / tab[-1][0] * (len(tab) - 1); i = min(int(x), len(tab) - 2); f_ = x - i
    return tab[i][1].lerp(tab[i + 1][1], f_)


def _stance_state(sd, ph, anchor):
    """ph in [0, stance): world(in-place) sole-centre C and pitch, from heel/flat/ball pivots."""
    T_ = TUNE; g = G[sd]; yaw = _rz(g["yaw"]).to_3x3()
    if ph < T_["heel_end"]:
        x = ph / T_["heel_end"]; th = T_["hs_pitch"] * (1 - x) ** T_["heel_exp"]
        return anchor + yaw @ _roll_offset(sd, th), th, 0.
    if ph < T_["heel_rise"]:
        return anchor.copy(), 0., 0.
    x = (ph - T_["heel_rise"]) / (T_["stance"] - T_["heel_rise"]); th = T_["to_pitch"] * x ** T_["rise_exp"]
    R = yaw @ _rx(th).to_3x3(); return anchor + yaw @ g["ball"] - R @ g["ball"], th, th


def _anchor(sd, ph):
    """In-place flat sole-centre anchor: planted point slides back at walking speed during stance."""
    T_ = TUNE; v = 2 * T_["step"] / T; x = T_["foot_x"] * (1 if sd == "Left" else -1)
    mid = T_["stance"] / 2; return Vector((x, T_["ahead"] + v * (ph - mid) * T, 0.))


def foot_state(sd, t):
    T_ = TUNE; off = 0. if sd == "Right" else .5; ph = (t / T - off) % 1.0; st = T_["stance"]
    if ph < st:
        C, th, toe = _stance_state(sd, ph, _anchor(sd, ph)); return C, th, toe, 0.
    # swing: cubic Hermite between toe-off and next heel-strike states (C1), plus a lift bump.
    e = 1e-4
    C0, th0, _ = _stance_state(sd, st - e, _anchor(sd, st - e)); Cm, thm, _ = _stance_state(sd, st - 2 * e, _anchor(sd, st - 2 * e))
    C1, th1, _ = _stance_state(sd, 0., _anchor(sd, 0.)); Cp, thp, _ = _stance_state(sd, e, _anchor(sd, e))
    D = 1. - st; m0 = (C0 - Cm) / e * D; m1 = (Cp - C1) / e * D; n0 = (th0 - thm) / e * D; n1 = (thp - th1) / e * D
    s = (ph - st) / D; h00 = 2 * s ** 3 - 3 * s ** 2 + 1; h10 = s ** 3 - 2 * s ** 2 + s; h01 = -2 * s ** 3 + 3 * s ** 2; h11 = s ** 3 - s ** 2
    C = C0 * h00 + m0 * h10 + C1 * h01 + m1 * h11; th = th0 * h00 + n0 * h10 + th1 * h01 + n1 * h11
    C.z += T_["lift"] * math.sin(math.pi * s ** T_["lift_skew"]) ** 2
    toe = T_["to_pitch"] * (1 - smooth01(s / .3))
    return C, th, toe, s


def foot_matrix(sd, t):
    C, th, toe, s = foot_state(sd, t); g = G[sd]
    return Matrix.Translation(C) @ _rz(g["yaw"]) @ _rx(th) @ g["S0"], toe


def wr(fk, name, axis, degrees):
    if abs(degrees) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy()
    b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(degrees), 4, axis) @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def pose_body(fk, base, t):
    T_ = TUNE
    for b in fk.pose.bones: b.matrix_basis = base[b.name]
    hips = fk.pose.bones["Hips"]; d = pelvis_pos(t) - Vector((0, 0, G["hips0"].z)); d.x += 0 - G["hips0"].x; d.y += 0 - G["hips0"].y
    hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ d; bpy.context.view_layer.update()
    py, pr = pelvis_yaw(t), pelvis_roll(t); pt = T_["tilt"] + T_["tilt_osc"] * -bobn(t)
    wr(fk, "Hips", "Z", py); wr(fk, "Hips", "Y", pr); wr(fk, "Hips", "X", pt)
    lag = T_["counter_lag"]; br = breath(t)
    # Spine: forward lean, shoulders counter-rotate against the pelvis (lagged), level the chest roll.
    for i, n in enumerate(("Spine", "Spine1", "Spine2")):
        wr(fk, n, "X", T_["lean"][i] - (pt * .35 if i == 0 else 0) - (T_["breath"][i] * br if i else 0))
        wr(fk, n, "Z", T_["counter"][i] * pelvis_yaw(t - lag * (i + 1)))
        wr(fk, n, "Y", -pelvis_roll(t - lag * (i + 1)) * (.45, .35, .3)[i])
    # Hunched, breathing shoulders (clavicles forward + slight rise on the inhale).
    wr(fk, "LeftShoulder", "Z", -T_["hunch"]); wr(fk, "RightShoulder", "Z", T_["hunch"])
    wr(fk, "LeftShoulder", "Y", -T_["breath"][2] * br); wr(fk, "RightShoulder", "Y", T_["breath"][2] * br)
    # Head stays level and aimed forward: cancel most of the chest yaw/roll and the added lean.
    chest_yaw = py + sum(T_["counter"][i] * pelvis_yaw(t - lag * (i + 1)) for i in range(3))
    lean = sum(T_["lean"]) + pt * .65
    kn, kh = T_["head_keep"]
    wr(fk, "Neck", "X", -kn * lean); wr(fk, "Head", "X", -kh * lean + .6 * bobn(t - .12))
    wr(fk, "Neck", "Z", -.4 * T_["head_yaw_keep"] * chest_yaw); wr(fk, "Head", "Z", -.6 * T_["head_yaw_keep"] * chest_yaw)
    wr(fk, "Head", "Y", -.5 * pr * .2)


def setup():
    """Open the approved two-hand idle (read only), re-tag, convert into the walk_two v5 authoring scene. Never saves."""
    cm.open_tagged(IDLE2, P["owner"]); s = bpy.context.scene
    assert s["rebuild_job"] == "idle_two"
    coll = bpy.data.collections["AUTHORING_idle_two"]; coll.name = "AUTHORING_" + JOB
    fk = bpy.data.objects["Pose_Control_Rig"]; c.at(0)
    G["base"] = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    G["hips0"] = fk.pose.bones["Hips"].matrix.translation.copy()
    G["chest0"] = fk.pose.bones["Spine2"].matrix.copy()
    G["hilt0"] = bpy.data.objects["Hilt_Control"].matrix_world.copy()
    G["armpole0"] = {sd: bpy.data.objects[sd + "Arm_Pole"].matrix_world.translation.copy() for sd in ("Left", "Right")}
    G["armtarget_local"] = {sd: bpy.data.objects[sd + "Arm_Target"].matrix_basis.copy() for sd in ("Left", "Right")}
    geo = sole_frames()
    G["Left"]["yaw"] = TUNE["toe_out"]; G["Right"]["yaw"] = -TUNE["toe_out"]
    s["rebuild_job"] = JOB; s["duration"] = DUR; s["review_name"] = REVIEW; s["loop_expected"] = True
    s["source_action"] = "approved IdleTwoHand_Blender_v1 frame-0 pose (FK, hilt, grips)"; s["v5_started_from"] = str(IDLE2)
    c.JOBS[JOB] = ("IdleTwoHand_Blender_v1", DUR, [i * T / 4 for i in range(int(round(DUR / T * 4)) + 1)], True)
    return {"geo": geo, "hips0": list(G["hips0"]), "hilt0": list(G["hilt0"].translation)}


def author():
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"] and s.get("rebuild_job") == JOB, "setup() first"
    if "Left" not in G or "S0" not in G.get("Left", {}): raise RuntimeError("setup() first in this exec")
    fps = 150; s.render.fps = fps; s.render.fps_base = 1; s.frame_start = 0; s.frame_end = round(DUR * fps)
    fk = bpy.data.objects["Pose_Control_Rig"]; hilt = bpy.data.objects["Hilt_Control"]
    legs = {sd: (bpy.data.objects[sd + "Leg_Target"], bpy.data.objects[sd + "Leg_Pole"]) for sd in ("Left", "Right")}
    armp = {sd: bpy.data.objects[sd + "Arm_Pole"] for sd in ("Left", "Right")}
    fk.animation_data_clear(); hilt.animation_data_clear()
    for o in (*[x for p in legs.values() for x in p], *armp.values()): f.reset_animation(o)
    for sd in ("Left", "Right"):
        tg = bpy.data.objects[sd + "Arm_Target"]; tg.animation_data_clear(); tg.matrix_basis = G["armtarget_local"][sd]
    s.timeline_markers.clear()
    for k in range(int(round(DUR / T * 2))):
        s.timeline_markers.new(("R" if k % 2 == 0 else "L") + " heel strike", frame=round(k * T / 2 * fps))
    n = round(DUR * fps / KEY_FRAMES); prev = {}; chest = []; reach = {"Left": 0., "Right": 0.}; prof = {}
    Lleg = {sd: (fk.pose.bones[sd + "Leg"].head - fk.pose.bones[sd + "UpLeg"].head).length + (fk.pose.bones[sd + "Foot"].head - fk.pose.bones[sd + "Leg"].head).length for sd in legs}
    for i in range(n + 1):
        t = i * KEY_FRAMES / fps; fr = i * KEY_FRAMES
        pose_body(fk, G["base"], t)
        for sd, (tg, pl) in legs.items():
            M, toe = foot_matrix(sd, t)
            # toes stay flat on the ground while the heel rises (counter-rotate ToeBase about the ball)
            J = (M @ G[sd]["rel_toe"]).translation; ax = (_rz(G[sd]["yaw"]).to_3x3() @ Vector((1, 0, 0)))
            toe_w = Matrix.Translation(J) @ Matrix.Rotation(math.radians(-toe), 4, ax) @ Matrix.Translation(-J) @ M @ G[sd]["rel_toe"]
            fk.pose.bones[sd + "ToeBase"].matrix = fk.pose.bones[sd + "Foot"].matrix @ (M.inverted() @ toe_w); bpy.context.view_layer.update()
            tg.matrix_basis = M; c.key(tg, fr, prev)
            hip = fk.pose.bones[sd + "UpLeg"].head.copy(); ank = M.translation
            rr = (ank - hip).length / Lleg[sd]; reach[sd] = max(reach[sd], rr); prof.setdefault(sd, []).append(round(rr, 3))
            out = Vector((1 if sd == "Left" else -1, 0, 0))
            pl.location = (hip + ank) * .5 + _rz(G[sd]["yaw"]).to_3x3() @ Vector((0, -.35, 0)) + out * .02; pl.keyframe_insert("location", frame=fr)
        for b in fk.pose.bones: c.key(b, fr, prev)
        chest.append(fk.pose.bones["Spine2"].matrix.copy())
    # Hilt and arm poles: follow the chest with lag/float so the blade is stable but alive.
    T_ = TUNE; inv0 = G["chest0"].inverted(); N = n
    def chest_at(i, lag_s):
        j = (i - round(lag_s * fps / KEY_FRAMES)) % N; return chest[j]
    for i in range(n + 1):
        t = i * KEY_FRAMES / fps; fr = i * KEY_FRAMES
        rigid = chest_at(i, T_["hilt_lag"]) @ inv0 @ G["hilt0"]; h0 = G["hilt0"]
        k = T_["hilt_k"]; dp = rigid.translation - h0.translation
        pos = h0.translation + Vector((dp.x * k[0], dp.y * k[1], dp.z * k[2])) + Vector((0, 0, T_["hilt_breath"] * breath(t - .1)))
        q = h0.to_quaternion().slerp(rigid.to_quaternion(), T_["hilt_rot_follow"])
        tip = T_["tip_float"] * -bobn(t - T_["tip_lag"])
        pos += Vector(T_["hilt_off"]); roll = Matrix.Rotation(math.radians(T_["hilt_roll"]), 4, "Y")  # blade tipped to his right, clear of the face
        m = Matrix.Translation(pos) @ roll @ _rx(tip) @ q.to_matrix().to_4x4() @ Matrix.Diagonal(h0.to_scale().to_4d())  # keep the approved socket scale
        hilt.matrix_basis = m; c.key(hilt, fr, prev)
        for sd, pl in armp.items():
            pl.location = chest_at(i, 0) @ inv0 @ (G["armpole0"][sd] + Vector(T_["arm_pole_off"])); pl.keyframe_insert("location", frame=fr)  # elbows forward of the breastplate
    objs = [fk, hilt, *armp.values(), *[x for p in legs.values() for x in p]]
    for o in objs:
        c.smooth(o)
        for fc in c.curves(o.animation_data.action):
            if not any(m.type == "CYCLES" for m in fc.modifiers): fc.modifiers.new("CYCLES")
            fc.update()
    tx = bpy.data.texts.get("feedback_v4_walk_v5.py") or bpy.data.texts.new("feedback_v4_walk_v5.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s["walk_v5_tune"] = json.dumps(TUNE); s["root_motion"] = "in place (loop); forward speed %.4f rig units/s" % (2 * TUNE["step"] / T)
    c.at(0)
    return {"keys": n + 1, "maxLegReach": reach, "reachProfile": {k: v[::3][:31] for k, v in prof.items()}, "legLen": Lleg, "speed": 2 * TUNE["step"] / T}


def _strap():
    sp = importlib.util.spec_from_file_location("veyr_v4_strap", HERE / "strap_v4.py"); m = importlib.util.module_from_spec(sp); m.VEYR_V4_PARAMS = globals().get("VEYR_V4_PARAMS"); sp.loader.exec_module(m)
    s = bpy.context.scene; return m.apply_body(auto_frames=list(range(0, s.frame_end + 1, 10)))


def bake_export():
    """Strap-fix weights, native bake, save OUT/walk_two_Blender_v1.blend, export, deliver v5 copy."""
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"] and s.get("rebuild_job") == JOB
    cm.check_writable(c.OUT); c.OUT.mkdir(parents=True, exist_ok=True); fix = _strap()
    c.bake()
    glb = c.OUT / (JOB + "_Blender_v1.glb"); rp = c.OUT / (JOB + "-report.json"); r = json.loads(rp.read_text())
    r.update(reviewName=REVIEW, loopExpected=True, previewLoop=True, duration=DUR, gaitCycle=T, stepsPerSecond=2 / T, ownerApproved=False,
             startedFrom=str(IDLE2), rootMotion=s["root_motion"], strapFix=fix, strapFixWeightsSHA256=s.get("strap_fix_v4"), tune=TUNE,
             authoring="Blender FK body curves + world foot targets with heel/flat/ball pivots + chest-following hilt; native IK; baked")
    rp.write_text(json.dumps(r, indent=2) + "\n")
    name = REVIEW + ".glb"; assert name not in cm.approved_names(); dest = P["export_dir"] / name
    P["export_dir"].mkdir(parents=True, exist_ok=True); shutil.copyfile(glb, dest)
    return {"blend": bpy.data.filepath, "glb": str(dest), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "nativeIKError": r["nativeIKError"], "endpoint": r["endpointMatrixDelta"], "strap": fix}


def build():
    a = setup(); b = author(); e = bake_export(); return {"setup": a, "author": b, "export": e}


def measure(path=None, t0=0., t1=None, step=1, translate=0.):
    """Per-frame evaluated-mesh metrics on the baked deform rig. translate: in-place speed to add back for slip."""
    if path: cm.open_tagged(Path(path), P["owner"])
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; body = _body(); fps = s.render.fps
    ids = foot_ids(body); legids = foot_ids(body, groups=("Leg", "Foot", "ToeBase"))
    from mathutils.kdtree import KDTree
    t1 = s["duration"] if t1 is None else t1; rows = []
    for fr in range(round(t0 * fps), round(t1 * fps) + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        P_ = {sd: [mw @ me.vertices[i].co for i in ids[sd]] for sd in ids}; Q = {sd: [mw @ me.vertices[i].co for i in legids[sd]] for sd in legids}
        row = {"t": fr / fps}
        for sd in ("Left", "Right"):
            pts = P_[sd]; z0 = min(p.z for p in pts); row[sd + "MinZ"] = z0
            row[sd + "X"] = (min(p.x for p in pts) + max(p.x for p in pts)) / 2; row[sd + "Y"] = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
            row[sd + "Low"] = {i: (p.x, p.y - translate * fr / fps) for i, p in zip(ids[sd], pts) if p.z < .0015}
            a, k, e = [(rig.matrix_world @ rig.pose.bones[sd + n_].head) for n_ in ("UpLeg", "Leg", "Foot")]
            row[sd + "Knee"] = 180 - math.degrees((a - k).angle(e - k))
        kd = KDTree(len(P_["Right"]))
        for i, p in enumerate(P_["Right"]): kd.insert(p, i)
        kd.balance(); row["footGap"] = min(kd.find(p)[2] for p in P_["Left"])
        kd2 = KDTree(len(Q["Right"]))
        for i, p in enumerate(Q["Right"]): kd2.insert(p, i)
        kd2.balance(); row["legGap"] = min(kd2.find(p)[2] for p in Q["Left"])
        row["hipsZ"] = (rig.matrix_world @ rig.pose.bones["Hips"].head).z; row["hipW"] = ((rig.matrix_world @ rig.pose.bones["LeftUpLeg"].head) - (rig.matrix_world @ rig.pose.bones["RightUpLeg"].head)).x
        ev.to_mesh_clear(); rows.append(row)
    lat = [r["LeftX"] - r["RightX"] for r in rows]; ground = [min(r["LeftMinZ"], r["RightMinZ"]) for r in rows]
    slip = {}
    for sd in ("Left", "Right"):
        mx = 0.
        for a, b in zip(rows, rows[1:]):
            common = set(a[sd + "Low"]) & set(b[sd + "Low"])  # same vertices touching the ground in both frames
            if len(common) >= 15:
                v_ = sum(math.hypot(a[sd + "Low"][i][0] - b[sd + "Low"][i][0], a[sd + "Low"][i][1] - b[sd + "Low"][i][1]) for i in common) / len(common)
                if v_ > mx: mx = v_; worst = (round(a["t"], 4), len(common))
        slip[sd] = mx; slip[sd + "At"] = worst if mx > 0 else None
    summ = {"frames": len(rows), "lateralFootCentre": [min(lat), sum(lat) / len(lat), max(lat)], "hipJointWidth": [min(r["hipW"] for r in rows), max(r["hipW"] for r in rows)],
            "minFootMeshGap": min(r["footGap"] for r in rows), "minLowerLegMeshGap": min(r["legGap"] for r in rows),
            "groundContactLowestPerFrame": [min(ground), max(ground)], "LeftMinZ": [min(r["LeftMinZ"] for r in rows), max(r["LeftMinZ"] for r in rows)], "RightMinZ": [min(r["RightMinZ"] for r in rows), max(r["RightMinZ"] for r in rows)],
            "plantedContactSlipPerFrame": slip, "kneeFlex": {sd: [min(r[sd + "Knee"] for r in rows), max(r[sd + "Knee"] for r in rows)] for sd in ("Left", "Right")},
            "hipsZ": [min(r["hipsZ"] for r in rows), max(r["hipsZ"] for r in rows)],
            "framesNoFootOnGround": sum(1 for g in ground if g > .002)}
    summ["series"] = [{k: round(v, 4) for k, v in r.items() if isinstance(v, float)} for r in rows[::max(1, 15 // step)]]
    return summ


def loop_check():
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]; E = s.frame_end
    def snap(fr):
        s.frame_set(fr); return {b.name: (rig.matrix_world @ b.matrix).copy() for b in rig.pose.bones} | {"socket": sock.matrix_world.copy()}
    a0, a1, b0, b1 = snap(0), snap(1), snap(E - 1), snap(E)
    pos = max((a0[n].translation - b1[n].translation).length for n in a0); mat = max(max(abs(a0[n][i][j] - b1[n][i][j]) for i in range(4) for j in range(4)) for n in a0)
    vel = max(((a1[n].translation - a0[n].translation) - (b1[n].translation - b0[n].translation)).length * s.render.fps for n in a0)
    return {"seamPositionError": pos, "seamMatrixError": mat, "seamVelocityJump_unitsPerS": vel}


def _ground(s):
    V = [(-1.5, -1.5, -.0006), (1.5, -1.5, -.0006), (1.5, 1.5, -.0006), (-1.5, 1.5, -.0006)]; F = [(0, 1, 2, 3)]; w = .0018
    for k in range(-15, 16):
        a = k * .1; b = len(V); V += [(a - w, -1.5, 0), (a + w, -1.5, 0), (a + w, 1.5, 0), (a - w, 1.5, 0)]; F.append((b, b + 1, b + 2, b + 3))
        b = len(V); V += [(-1.5, a - w, 0), (1.5, a - w, 0), (1.5, a + w, 0), (-1.5, a + w, 0)]; F.append((b, b + 1, b + 2, b + 3))
    me = bpy.data.meshes.new("TMP_Ground"); me.from_pydata(V, [], F); me.update(); o = bpy.data.objects.new("TMP_Ground", me); s.collection.objects.link(o)
    o.color = (.2, .22, .2, 1); return o


def render(label, path=None, t0=0., t1=T, fps_out=30, follow=False, res=480, views=("front", "side", "threequarter"), ortho=1.22, cz=.5, hide_small=False, cy=-.03, cx=0.):
    src = Path(path) if path else c.OUT / (JOB + "_Blender_v1.blend"); cm.open_tagged(src, P["owner"])
    s = bpy.context.scene; cam = s.camera; r = bpy.data.objects["Knight_Deform"]
    folder = cm.check_writable(P["out"] / "renders" / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = "OBJECT"
    for o in s.objects:
        if o.get("export_body"): o.color = (.53, .55, .6, 1)
        if o.get("review_attachment"): o.color = (.25, .16, .07, 1)
    gr = _ground(s)
    if hide_small:
        for o in s.objects:
            if o.type == "MESH" and len(o.data.vertices) < 100 and o.name.startswith("Icosphere"): o.hide_render = True
    V = {"front": (0, -4, .5), "side": (4, 0, .5), "threequarter": (2.8, -4, 1.)}
    times = [t0 + i / fps_out for i in range(round((t1 - t0) * fps_out))]; n = 0
    for view in views:
        for i, t in enumerate(times):
            ff = t * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
            center = Vector((cx, cy, cz))
            if follow: h = r.matrix_world @ r.pose.bones["Hips"].head; center.x, center.y = h.x, h.y; gr.location = (h.x, h.y, 0)
            d = Vector(V[view]).normalized(); cam.location = center + d * 5; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cam.data.ortho_scale = ortho
            s.render.filepath = str(folder / f"{view}-{i:04d}.png"); bpy.ops.render.render(write_still=True); n += 1
    return {"folder": str(folder), "frames": n, "times": [times[0], times[-1]], "source": str(src)}


def probe(path=None, times=(0, .3, .6, .9)):
    if path: cm.open_tagged(Path(path), P["owner"])
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; so = bpy.data.objects["ReviewWeaponSocket"]; out = {}
    for t in times:
        s.frame_set(round(t * s.render.fps)); w = lambda n: [round(x, 4) for x in (rig.matrix_world @ rig.pose.bones[n].head)]
        m = so.matrix_world; out[t] = {n: w(n) for n in ("Hips", "Spine2", "Neck", "Head", "LeftArm", "RightArm", "LeftHand", "RightHand")}
        out[t]["socket"] = [round(x, 4) for x in m.translation]; out[t]["socketY"] = [round(x, 3) for x in m.to_3x3().col[1].normalized()]; out[t]["socketZ"] = [round(x, 3) for x in m.to_3x3().col[2].normalized()]; out[t]["socketX"] = [round(x, 3) for x in m.to_3x3().col[0].normalized()]
    return out


def grip_check(frames=(0, 90, 180, 270), path=None):
    """Compare hand fit on Grip_v6 (scene sword) vs StrongGrip_v1 at the same socket. Never saves."""
    from mathutils.bvhtree import BVHTree
    cm.open_tagged(Path(path) if path else c.OUT / (JOB + "_Blender_v1.blend"), P["owner"]); s = bpy.context.scene; body = _body(); sock = bpy.data.objects["ReviewWeaponSocket"]
    swords = {s.get("sword_file", "scene"): [o for o in s.objects if o.get("review_attachment") and o.type == "MESH"]}
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]): bpy.ops.import_scene.gltf(filepath=str(c.ASSETS / "BoatGreatsword_StrongGrip_v1.glb"))
    new = set(bpy.data.objects) - before
    for o in new:
        if o.parent not in new: o.parent = sock; o.matrix_basis = Matrix.Identity(4)
    swords["BoatGreatsword_StrongGrip_v1.glb"] = [o for o in new if o.type == "MESH"]
    gid = {g.index: g.name for g in body.vertex_groups}
    hands = {sd: [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, "").startswith(sd + "Hand")) > .5] for sd in ("Left", "Right")}
    out = {}
    for fr in frames:
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        for name, objs in swords.items():
            tris = []; verts = []
            for o in objs:
                e = o.evaluated_get(dg); m = e.to_mesh(); m.calc_loop_triangles(); base = len(verts); verts += [o.matrix_world @ v.co for v in m.vertices]; tris += [[base + i for i in t.vertices] for t in m.loop_triangles]; e.to_mesh_clear()
            bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
            for sd, ids in hands.items():
                pts = [mw @ me.vertices[i].co for i in ids]; cen = sum(pts, Vector()) / len(pts)
                d = [bvh.find_nearest(p)[3] for p in pts]
                r = out.setdefault(name, {}).setdefault(sd, {"palmCentroidToSurface": [], "handVertsWithin4mm": []})
                r["palmCentroidToSurface"].append(round(bvh.find_nearest(cen)[3], 4)); r["handVertsWithin4mm"].append(sum(1 for x in d if x < .004))
        ev.to_mesh_clear()
    return {"sceneSword": s.get("sword_file"), "results": out, "handVerts": {k: len(v) for k, v in hands.items()}}
