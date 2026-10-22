"""Run v4 authoring (owner feedback 2026-10-21: "Why is his left hand held up like that? He needs
to be moving his whole body like he is running, like a sprint. His feet are running into each
other through the feet."). Execute ONLY inside the task-owned Blender MCP session via run.py
(owner fable-veyr-knight-run-20261021, port 9885), with --scene-in Local/Blender/remainder-20261021.

  open_run()   open the remainder Run v1 editable scene (read only) and re-tag the owner; never saves
  author()     rewrite the control rig: FK body (from the approved one-hand idle), world-space foot
               targets and knee poles for a closed sprint cycle. Native IK still solves limbs at bake.
  bake_run()   core bake (saves <out>/run_Blender_v1.blend), strap-fix body, export
               <out>/run_Blender_v1.glb and copy <out>/export/RunOneHand_Blender_v4.glb
  inspect()    evaluated-mesh checks on the baked scene (foot-to-foot distance, flight, contacts,
               sword clearance, loop seam); writes <out>/run-inspection.json
  capture(label)  front/side/three-quarter workbench renders of one cycle (no save)

Root motion: IN PLACE (same as RunOneHand_Blender_v1). Ground speed implied by the planted foot is
recorded as scene["run_speed"] and in run-report.json.
"""
from pathlib import Path
import bpy, importlib.util, math, json, hashlib, shutil
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location("veyr_v4_common", HERE / "common.py"); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get("VEYR_V4_PARAMS"))
_fs = importlib.util.spec_from_file_location("feedback2", cm.REPO / "tools/art/blender/feedback/feedback_actions.py"); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OWNER = P["owner"]
ROUND = "r6"  # r6: blade truly vertical in front view, hand inward/forward (critic), r5 kept intact
_R5 = "r5"  # round 5 (owner: "weapon held frontward ... straight up like a baseball bat"): <out>/r5, RunOneHand_Blender_v4r5.glb
c.OUT = P["out"] / ROUND
SRC = cm.REPO / "Local/Blender/remainder-20261021/run_Blender_v1.blend"
REVIEW = "RunOneHand_Blender_v" + P["revision"] + ROUND
KEY_FRAMES = 3   # authored key every 3 frames at 150 Hz (0.02 s); cyclic AUTO handles

# ----------------------------------------------------------------- tunables ---
T = dict(
    duration=.6,          # one full cycle (two steps): 3.33 steps/s
    duty=.20,             # stance fraction per foot -> 4 of 18 sheet frames; flight .28 of the cycle per step
    td=-.10, to=.15,      # ball-of-foot Y at touchdown / toe-off (Y+ is behind; hips at ~0)
    track=.042,
    x_fix={"Left": 0., "Right": .008},  # right sole contact sat ~1.5 px further out than the left           # ankle lateral track (+-X)
    swing_out=.045,       # extra outward bump while passing the stance foot
    toe_out=6.,           # degrees
    # swing waypoints (phase, ballY, ballZ, pitch deg +toes-down)
    swing=[(.30, .21, .10, 70.), (.42, .16, .21, 62.), (.56, -.03, .24, 25.), (.70, -.17, .18, 4.), (.84, -.18, .09, 6.), (.94, -.13, .03, 10.)],
    to_zslope=2.0, feet_fwd=-.040, body_fwd=-.070,
    td_pitch=12., to_pitch=46.,
    y_fix={"Left": 0., "Right": -.012},  # right chain needs ~.014 more reach at toe-off (hip sits further back); shift its path forward
    ball_above_sole={"Left": 0., "Right": 0.},  # pivot height correction (0 = ToeBase joint); lowering it measured worse
    roll_lift={"Left": .007, "Right": .016},  # sole-front armour ahead of the joint dips ~5 mm at toe-off; lift by roll_lift*sin(pitch) in stance
    sole_fix={"Left": 0., "Right": -.014},  # measured: flat right sole sat .014 above ground
    hip_drop=-.010, bob=.022, sway=.006, surge=.003,
    hip_lean=20., spine_lean=(6., 3., 2.), neck_up=-7., head_up=-15.,  # r4: +7 deg hips/spine, neck/head take it back
    pelvis_yaw=10., shoulder_yaw=25., clav=9., pelvis_roll=3., breath=.8,
    l_abd=(21., -5.), l_swing=(-12., 54.), l_elbow=(87., -17.), l_in=-27., l_sharp=.99, l_yaw=.5, arm_lag=.03,  # arm angles in the yawing chest frame, without the lean
    r_abd=9., r_swing=(44., 10.), r_elbow=(68., 6.), r_fore_out=-11., r_yaw=.5,  # r5: bat carry, hand in front of the right shoulder
    blade_up=True, blade_tilt=6., blade_out=0., blade_lag=.09, hull_ref=(-1., 0., 0.), fore_twist=.85, blade=(-.27, .86, -.43), blade_follow=.1, blade_yaw=.4, hull_upright=1.,
)
DUR = T["duration"]


def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def hermite(p0, p1, m0, m1, s, h):
    s2, s3 = s * s, s * s * s
    return (2*s3 - 3*s2 + 1) * p0 + (s3 - 2*s2 + s) * h * m0 + (-2*s3 + 3*s2) * p1 + (s3 - s2) * h * m1


def stance(ph):
    """ball y, ball z, pitch for phase ph in [0, duty]."""
    D = T["duty"]; u = ph / D
    y = T["td"] + (T["to"] - T["td"]) * u
    if u < .25: p = T["td_pitch"] * (1 - smooth01(u / .25))
    elif u < .45: p = 0.
    else: p = T["to_pitch"] * ((u - .45) / .55) ** 1.6
    return y, 0., p


def foot_curve(ph):
    """Periodic ball-of-foot path (y, z) and pitch for one foot; ph=0 touchdown."""
    ph %= 1.; D = T["duty"]
    if ph <= D: return stance(ph)
    vy = (T["to"] - T["td"]) / D
    dp_to = T["to_pitch"] * 1.6 / (.55 * D)
    pts = [(D, T["to"], 0., T["to_pitch"])] + T["swing"] + [(1., T["td"], 0., T["td_pitch"])]
    slopes = []
    for i, (x, y, z, p) in enumerate(pts):
        if i == 0: slopes.append((vy, T["to_zslope"], dp_to))
        elif i == len(pts) - 1: slopes.append((vy, 0., 0.))
        else:
            a, b = pts[i - 1], pts[i + 1]; dx = b[0] - a[0]
            slopes.append(((b[1] - a[1]) / dx, (b[2] - a[2]) / dx, (b[3] - a[3]) / dx))
    for i in range(len(pts) - 1):
        if pts[i][0] <= ph <= pts[i + 1][0]:
            h = pts[i + 1][0] - pts[i][0]; s = (ph - pts[i][0]) / h
            return tuple(hermite(pts[i][k + 1], pts[i + 1][k + 1], slopes[i][k], slopes[i + 1][k], s, h) for k in range(3))
    raise ValueError(ph)


def toe_bend(ph):
    ph %= 1.; D = T["duty"]
    if ph <= D: return stance(ph)[2]
    if ph < .45: return T["to_pitch"] * (1 - smooth01((ph - D) / (.45 - D)))
    if ph > .9: return T["td_pitch"] * smooth01((ph - .9) / .1)
    return 0.


def phase(side, t):
    return ((t / DUR) + (0. if side == "Right" else .5)) % 1.


def cyc(t, k=1, off=0.):
    return math.cos(math.tau * (k * t / DUR - off))


def hips_delta(t):
    return Vector((-T["sway"] * cyc(t, 1, .16), T["body_fwd"] + T["surge"] * cyc(t, 2, .05), T["hip_drop"] - T["bob"] * cyc(t, 2, T["duty"] / 2)))


# ----------------------------------------------------------------- helpers ----
def wr(fk, name, axis, degrees, pivot=None):
    if abs(degrees) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy(); R = Matrix.Rotation(math.radians(degrees), 4, axis)
    if isinstance(axis, str): pass
    b.matrix = Matrix.Translation(m.translation) @ R @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def aim(fk, name, child_head, direction, keep_child=False):
    """Rotate bone so the vector head->child_head points along direction (minimal rotation)."""
    b = fk.pose.bones[name]; m = b.matrix.copy(); cur = (child_head - m.translation).normalized()
    q = cur.rotation_difference(direction.normalized())
    b.matrix = Matrix.Translation(m.translation) @ q.to_matrix().to_4x4() @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


IDLE = {}


def idle_pose():
    if IDLE: return IDLE
    before = set(bpy.data.objects)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.import_scene.gltf(filepath=str(cm.REPO / "tools/asset-review/.asset-cache/review/IdleOneHand_Breathing_v3.glb"))
    added = set(bpy.data.objects) - before; r = next(o for o in added if o.type == "ARMATURE"); c.at(0)
    IDLE["basis"] = {b.name: b.matrix_basis.copy() for b in r.pose.bones}
    for o in added: bpy.data.objects.remove(o, do_unlink=True)
    for a in [a for a in bpy.data.actions if a.users == 0]: bpy.data.actions.remove(a)
    return IDLE


def open_run():
    prev = cm.open_tagged(SRC, P["owner"]); s = bpy.context.scene
    assert s.get("rebuild_job") == "run"; f.configure("run")
    return {"opened": str(SRC), "previousOwner": prev, "fps": s.render.fps, "frames": [s.frame_start, s.frame_end], "duration": s.get("duration")}


# ----------------------------------------------------------------- authoring --
def pose_body(fk, base, t, chest0):
    for b in fk.pose.bones: b.matrix_basis = base[b.name]
    hips = fk.pose.bones["Hips"]; hips.location += fk.data.bones["Hips"].matrix_local.to_3x3().inverted() @ hips_delta(t)
    bpy.context.view_layer.update()
    yaw = T["pelvis_yaw"] * cyc(t); roll = T["pelvis_roll"] * cyc(t, 1, .16)
    lag = lambda d: cyc(t, 1, d)
    # 1) leans (sagittal), 2) twists about the leaned spine axis, 3) small rolls
    wr(fk, "Hips", "X", T["hip_lean"])
    for name, lean in zip(("Spine", "Spine1", "Spine2"), T["spine_lean"]):
        wr(fk, name, "X", lean + (T["breath"] * cyc(t, 2, .1) if name == "Spine2" else 0.))
    wr(fk, "Neck", "X", T["neck_up"]); wr(fk, "Head", "X", T["head_up"] + 1.2 * cyc(t, 2, T["duty"] / 2 + .06))
    U = (fk.pose.bones["Neck"].head - fk.pose.bones["Hips"].head).normalized()
    UN = (fk.pose.bones["Head"].head - fk.pose.bones["Neck"].head).normalized()
    tot = T["pelvis_yaw"] + T["shoulder_yaw"]
    wr(fk, "Hips", U, yaw)
    for name, share, d in zip(("Spine", "Spine1", "Spine2"), (.35, .35, .30), (.01, .02, .03)):
        wr(fk, name, U, -share * tot * lag(d))
    # neck/head cancel the shoulder twist exactly (same phase) so the visor stays straight ahead
    net = yaw - sum(share * tot * lag(d) for share, d in zip((.35, .35, .30), (.01, .02, .03)))
    wr(fk, "Neck", UN, -.5 * net); wr(fk, "Head", UN, -.5 * net)
    wr(fk, "Hips", "Y", roll)
    for name, d in zip(("Spine", "Spine1", "Spine2"), (.01, .02, .03)): wr(fk, name, "Y", -.3 * T["pelvis_roll"] * cyc(t, 1, .16 + d))
    wr(fk, "Head", "Y", -.25 * roll)
    wr(fk, "LeftShoulder", "Z", -T["clav"] * cyc(t, 1, T["arm_lag"])); wr(fk, "RightShoulder", "Z", -T["clav"] * cyc(t, 1, T["arm_lag"]))
    # chest frame relative to idle chest (arms ride the counter-rotating shoulders)
    R = fk.pose.bones["Spine2"].matrix.to_quaternion() @ chest0.inverted()
    fwd = R @ Vector((0, -1, 0)); chest_yaw = math.atan2(fwd.x, -fwd.y); RA = Matrix.Rotation(chest_yaw, 3, "Z")
    # Free left arm: tucked upper arm, ~90 deg elbow, pumping opposite the left leg.
    k = T["l_sharp"]; w = lambda d: math.asin(k * cyc(t, 1, d)) / math.asin(k)  # sharper peaks than cos: brief dwell at front/back
    a = T["l_swing"][0] + T["l_swing"][1] * w(T["arm_lag"])
    e = T["l_elbow"][0] - T["l_elbow"][1] * w(T["arm_lag"] + .08)  # elbow closes after the forward peak: short dwell
    abd = T["l_abd"][0] + T["l_abd"][1] * w(T["arm_lag"])
    d0 = Vector((math.sin(math.radians(abd)), 0, -math.cos(math.radians(abd))))
    RL = Matrix.Rotation(T["l_yaw"] * chest_yaw, 3, "Z")
    up = RL @ (Matrix.Rotation(math.radians(-a), 3, "X") @ d0)
    fin = Vector((-math.sin(math.radians(T["l_in"])), 0, -math.cos(math.radians(T["l_in"]))))
    fore = RL @ (Matrix.Rotation(math.radians(-(a + e)), 3, "X") @ fin)
    hand_rel = fk.pose.bones["LeftForeArm"].matrix.inverted() @ fk.pose.bones["LeftHand"].matrix
    aim(fk, "LeftArm", fk.pose.bones["LeftForeArm"].head, up)
    aim(fk, "LeftForeArm", fk.pose.bones["LeftHand"].head, fore)
    # Sword arm (r5): bat carry; upper arm hangs slightly forward, elbow ~100 deg, hand at chest height before the right shoulder.
    ar = T["r_swing"][0] - T["r_swing"][1] * cyc(t, 1, T["arm_lag"])
    er = T["r_elbow"][0] + T["r_elbow"][1] * cyc(t, 1, T["arm_lag"] + .03)
    d0 = Vector((-math.sin(math.radians(T["r_abd"])), 0, -math.cos(math.radians(T["r_abd"]))))
    RR = Matrix.Rotation(T.get("r_yaw", 1.) * chest_yaw, 3, "Z")
    up = RR @ (Matrix.Rotation(math.radians(-ar), 3, "X") @ d0)
    fore = RR @ (Matrix.Rotation(math.radians(-(ar + er)), 3, "X") @ Vector((-math.sin(math.radians(T["r_fore_out"])), 0, -math.cos(math.radians(T["r_fore_out"])))))
    aim(fk, "RightArm", fk.pose.bones["RightForeArm"].head, up)
    aim(fk, "RightForeArm", fk.pose.bones["RightHand"].head, fore)
    hilt = bpy.data.objects["Hilt_Control"].matrix_basis.to_3x3()
    hb = fk.pose.bones["RightHand"]; cur = (hb.matrix.to_3x3() @ hilt @ Vector((0, 0, 1))).normalized()
    Ryaw = Matrix.Rotation(T["blade_yaw"] * chest_yaw, 3, "Z")  # chest yaw only; lean must not lift the blade
    if T.get("blade_up"):  # blade vertical; wrist lets it rock fore/aft a few degrees behind the arm swing, tip leaning slightly outward
        tilt = T["blade_tilt"] * cyc(t, 1, T["arm_lag"] + T["blade_lag"])
        want = (Matrix.Rotation(math.radians(tilt), 3, "X") @ Matrix.Rotation(math.radians(-T["blade_out"]), 3, "Y") @ Vector((0, 0, 1))).normalized()
    else:
        want = (Ryaw @ (Matrix.Rotation(math.radians(-T["blade_follow"] * ar), 3, "X") @ Vector(T["blade"]).normalized())).normalized()
    q = cur.rotation_difference(want); m = hb.matrix.copy()
    hb.matrix = Matrix.Translation(m.translation) @ q.to_matrix().to_4x4() @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()
    # Keep the boat hull upright (socket +X toward world up) so it trails edge-on, not flaring outward.
    xw = (hb.matrix.to_3x3() @ hilt @ Vector((1, 0, 0))); up = Vector(T["hull_ref"]); up = (up - want * up.dot(want)).normalized(); xw = (xw - want * xw.dot(want)).normalized()
    ang = math.atan2(want.dot(xw.cross(up)), xw.dot(up)) * T["hull_upright"]; m = hb.matrix.copy()
    hb.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(ang, 4, want) @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()
    if T.get("blade_up") and T.get("fore_twist", 0):
        # Move most of the wrist roll into forearm pronation/supination (twist about the forearm axis);
        # the hand keeps its world orientation, so the blade stays exactly where it was aimed.
        fb = fk.pose.bones["RightForeArm"]; H = hb.matrix.copy()
        d = (fb.matrix.to_quaternion().inverted() @ H.to_quaternion()) @ REL0["R"].inverted()  # change vs idle grip, in the forearm frame
        tau = 2 * math.atan2(d.y, d.w); tau = (tau + math.pi) % math.tau - math.pi
        ax = fb.matrix.col[1].xyz.normalized(); m = fb.matrix.copy()
        fb.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(T["fore_twist"] * tau, 4, ax) @ m.to_3x3().to_4x4(); bpy.context.view_layer.update()
        hb.matrix = H; bpy.context.view_layer.update()
    return {"lArm": a, "lElbow": e, "rArm": ar, "chestYaw": math.degrees(chest_yaw)}


REL0 = {}


def foot_matrix(side, t, idle_world, ball_local):
    ph = phase(side, t); y, z, p = foot_curve(ph); sign = 1 if side == "Left" else -1
    D = T["duty"]; out = 0. if ph <= D else T["swing_out"] * math.sin(math.pi * (ph - D) / (1 - D)) ** .7
    m0 = idle_world[side + "Foot"]
    # toe-out correction about the ankle, then place the ball at (x, y, z), then pitch about the ball
    toe = idle_world[side + "ToeBase"].translation - m0.translation
    cur = math.degrees(math.atan2(toe.x, -toe.y))  # + = toes toward +X
    want = sign * T["toe_out"]
    Rz = Matrix.Rotation(math.radians(want - cur), 4, "Z")  # round 3: sign fixed (was doubling toe-out)
    flat = Matrix.Translation(m0.translation) @ Rz @ Matrix.Translation(-m0.translation) @ m0
    ball = flat @ ball_local
    x = sign * (T["track"] + out) + T["x_fix"][side] + (ball.x - flat.translation.x)
    lift = T["roll_lift"][side] * math.sin(math.radians(p)) if (ph <= D and p > 0 and ph > D * .3) else 0.
    target = Vector((x, y + T["feet_fwd"] + T["y_fix"][side], idle_world["_ballZ"][side] + T["sole_fix"][side] + z + lift))
    flat = Matrix.Translation(target - ball) @ flat
    pivot = target - Vector((0, 0, max(0., T["ball_above_sole"][side] - z)))
    return Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(p), 4, "X") @ Matrix.Translation(-pivot) @ flat, p, ph


def author():
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"] and s.get("rebuild_job") == "run", "open_run() first"
    fps = s.render.fps; fk = bpy.data.objects["Pose_Control_Rig"]; assert fk.matrix_world == Matrix.Identity(4)
    assert abs(s["duration"] - DUR) < 1e-9 and s.frame_end == round(DUR * fps)
    base = idle_pose()["basis"]
    fk.animation_data_clear()
    for b in fk.pose.bones: b.matrix_basis = base[b.name]
    bpy.context.view_layer.update()
    idle_world = {b.name: b.matrix.copy() for b in fk.pose.bones}
    chest0 = idle_world["Spine2"].to_quaternion()
    REL0["R"] = (idle_world["RightForeArm"].inverted() @ idle_world["RightHand"]).to_quaternion()
    ball_local = {sd: idle_world[sd + "Foot"].inverted() @ idle_world[sd + "ToeBase"].translation for sd in ("Left", "Right")}
    idle_world["_ballZ"] = {sd: idle_world[sd + "ToeBase"].translation.z for sd in ("Left", "Right")}
    lat = {sd: idle_world[sd + "Foot"].to_3x3().inverted() @ Vector((1, 0, 0)) for sd in ("Left", "Right")}
    targets = {sd: bpy.data.objects[sd + "Leg_Target"] for sd in ("Left", "Right")}
    poles = {sd: bpy.data.objects[sd + "Leg_Pole"] for sd in ("Left", "Right")}
    for o in (*targets.values(), *poles.values()): f.reset_animation(o)
    L = {sd: (idle_world[sd + "Leg"].translation - idle_world[sd + "UpLeg"].translation).length + (idle_world[sd + "Foot"].translation - idle_world[sd + "Leg"].translation).length for sd in targets}
    prev = {}; reach = {sd: 0. for sd in targets}; n = round(s.frame_end / KEY_FRAMES); info = []
    for i in range(n + 1):
        fr = min(s.frame_end, i * KEY_FRAMES); t = (fr / fps) % DUR if fr < s.frame_end else 0.
        r = pose_body(fk, base, t, chest0)
        for sd in targets:
            m, p, ph = foot_matrix(sd, t, idle_world, ball_local[sd])
            # toes stay flat while the heel is up (FK toe bend is carried through the bake)
            tb = fk.pose.bones[sd + "ToeBase"]; ax = (fk.pose.bones[sd + "Foot"].matrix.to_3x3() @ lat[sd]).normalized()
            mm = tb.matrix.copy(); tb.matrix = Matrix.Translation(mm.translation) @ Matrix.Rotation(math.radians(-toe_bend(ph)), 4, ax) @ mm.to_3x3().to_4x4(); bpy.context.view_layer.update()
            targets[sd].matrix_basis = m; c.key(targets[sd], fr, prev)
            hip = fk.pose.bones[sd + "UpLeg"].head
            poles[sd].location = Vector((m.translation.x, hip.y - .45, .5 * (hip.z + m.translation.z) + .05)); poles[sd].keyframe_insert("location", frame=fr)
            reach[sd] = max(reach[sd], (hip - m.translation).length / L[sd])
        for b in fk.pose.bones: c.key(b, fr, prev)
        info.append({"t": round(t, 3), **{k: round(v, 1) for k, v in r.items()}})
    for o in (fk, *targets.values(), *poles.values()): cyclic(o)
    tx = bpy.data.texts.get("feedback_v4_run.py") or bpy.data.texts.new("feedback_v4_run.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    stride = (T["to"] - T["td"]) / T["duty"]  # ball travel per cycle
    s["run_speed"] = stride / DUR; s["root_motion"] = f"in place; planted-foot ground speed {stride / DUR:.4f} units/s"
    s["run_v4"] = json.dumps({k: v for k, v in T.items()}); s["loop_expected"] = True; s["review_name"] = REVIEW
    c.at(0)
    return {"keys": n + 1, "maxLegReach": reach, "speed": s["run_speed"], "info": info[::5]}


def cyclic(o):
    a = o.animation_data.action; a.use_fake_user = True
    for fc in c.curves(a):
        for k in fc.keyframe_points: k.interpolation = "BEZIER"; k.handle_left_type = k.handle_right_type = "AUTO"
        if not any(m.type == "CYCLES" for m in fc.modifiers): fc.modifiers.new("CYCLES")
        fc.update()


# ----------------------------------------------------------------- bake/export
def _jobs():
    s = bpy.context.scene; c.JOBS["run"] = ("Reference_Run", DUR, [i * KEY_FRAMES / s.render.fps for i in range(round(s.frame_end / KEY_FRAMES) + 1)], False)


def bake_run():
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"] and s.get("rebuild_job") == "run"
    out = cm.check_writable(c.OUT); out.mkdir(parents=True, exist_ok=True); assert not cm._inside(out, P["scene_in"])
    dest = P["export_dir"] / (REVIEW + ".glb"); assert (REVIEW + ".glb") not in cm.approved_names()
    f.configure("run"); _jobs(); c.bake()
    sp = importlib.util.spec_from_file_location("veyr_v4_strap", HERE / "strap_v4.py"); m = importlib.util.module_from_spec(sp); m.VEYR_V4_PARAMS = globals().get("VEYR_V4_PARAMS"); sp.loader.exec_module(m)
    strap = m.apply_body(auto_frames=list(range(0, s.frame_end + 1, 10)))
    c.at(0); rig = bpy.data.objects["Knight_Deform"]
    for o in s.objects: o.select_set(o == rig or o.name == "ReviewWeaponSocket" or bool(o.get("export_body")))
    bpy.context.view_layer.objects.active = rig; p = out / "run_Blender_v1.glb"
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.export_scene.gltf(filepath=str(p), export_format="GLB", use_selection=True, export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_nla_strips_merged_animation_name=REVIEW, export_frame_range=True, export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False, export_extras=True)
    tx = bpy.data.texts.get("feedback_v4_run.py") or bpy.data.texts.new("feedback_v4_run.py"); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s["feedback_revision"] = P["revision"]; s["v4_opened_from"] = str(SRC)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "run_Blender_v1.blend"), compress=True); assert cm._inside(bpy.data.filepath, out)
    rp = out / "run-report.json"; r = json.loads(rp.read_text()) if rp.exists() else {}
    r.update(job="run", reviewName=REVIEW, duration=s["duration"], sha256=hashlib.sha256(p.read_bytes()).hexdigest(), ownerApproved=False, feedbackRevision=P["revision"], startedFrom=str(SRC), rootMotion=s["root_motion"], runSpeedUnitsPerSecond=s["run_speed"], previewLoop=True, loopExpected=True, strapFix=strap, strapFixWeightsSHA256=s.get("strap_fix_v4"), tunables=T)
    rp.write_text(json.dumps(r, indent=2) + "\n")
    P["export_dir"].mkdir(parents=True, exist_ok=True)
    if dest.exists() and not P["allow_overwrite"]: raise FileExistsError(dest)
    shutil.copyfile(p, dest)
    return {"glb": str(dest), "sha256": r["sha256"], "blend": bpy.data.filepath, "strap": strap, "ikError": r.get("nativeIKError")}


# ----------------------------------------------------------------- inspection -
def _groups(body, prefixes):
    gid = {g.index: g.name for g in body.vertex_groups}
    return [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, "").startswith(prefixes)) > .5]


def inspect(step=1, name="run-inspection.json"):
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000)
    feet = {sd: _groups(body, (sd + "Foot", sd + "ToeBase")) for sd in ("Left", "Right")}
    shins = {sd: _groups(body, (sd + "Leg", sd + "Foot", sd + "ToeBase")) for sd in ("Left", "Right")}
    notarm = [i for i in range(len(body.data.vertices))]
    rarm = set(_groups(body, ("RightHand", "RightForeArm")))
    rlimb = set(_groups(body, ("RightHand", "RightForeArm", "RightArm", "RightShoulder")))
    legs = set(_groups(body, ("LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase")))
    lhand = _groups(body, ("LeftHand",))
    helm = _groups(body, ("Head", "Neck")); larm = _groups(body, ("LeftArm", "LeftForeArm", "LeftHand"))
    gidx = {g.index: g.name for g in body.vertex_groups}
    def wsum(v, pre): return sum(gg.weight for gg in v.groups if gidx.get(gg.group, "").startswith(pre))
    thighs = {sd: set(i for i, v in enumerate(body.data.vertices) if wsum(v, sd + "UpLeg") > .5) for sd in ("Left", "Right")}
    tabard = [i for i, v in enumerate(body.data.vertices) if wsum(v, ("Hips", "Spine")) > .6 and v.co.z < .45 and wsum(v, ("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg")) < .05]
    tris = [tuple(t.vertices) for t in body.data.loop_triangles] if body.data.loop_triangles else (body.data.calc_loop_triangles() or [tuple(t.vertices) for t in body.data.loop_triangles])
    thigh_tris = {sd: [tt for tt in tris if all(i in thighs[sd] for i in tt)] for sd in thighs}
    prev_contact = {}
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    bvh0 = ([v.co.copy() for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles])
    rows = []; z0 = None
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        P_ = {sd: [mw @ me.vertices[i].co for i in feet[sd]] for sd in feet}
        S_ = {sd: [mw @ me.vertices[i].co for i in shins[sd]] for sd in shins}
        kd = KDTree(len(P_["Right"]))
        for i, p in enumerate(P_["Right"]): kd.insert(p, i)
        kd.balance(); ff = min(kd.find(p)[2] for p in P_["Left"])
        kd2 = KDTree(len(S_["Right"]))
        for i, p in enumerate(S_["Right"]): kd2.insert(p, i)
        kd2.balance(); ss = min(kd2.find(p)[2] for p in S_["Left"])
        smw = sword.matrix_world; bvh = BVHTree.FromPolygons([smw @ v for v in bvh0[0]], bvh0[1], all_triangles=True)
        sw = 1e3; swwhere = None
        for i in range(0, len(me.vertices), 3):
            if i in rarm: continue
            hit = bvh.find_nearest(mw @ me.vertices[i].co)
            if hit[3] is not None and hit[3] < sw: sw = hit[3]; swwhere = i
        sl = 1e3
        for i in range(0, len(me.vertices), 3):
            if i in rlimb: continue
            hit = bvh.find_nearest(mw @ me.vertices[i].co)
            if hit[3] is not None and hit[3] < sl: sl = hit[3]
        sleg = 1e3
        for i in legs:
            hit = bvh.find_nearest(mw @ me.vertices[i].co)
            if hit[3] is not None and hit[3] < sleg: sleg = hit[3]
        # tabard/skirt vertices inside a thigh (BVH normal test)
        inside = 0; depth = 0.
        for sd in thighs:
            tb = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], thigh_tris[sd], all_triangles=True)
            for i in tabard:
                q = mw @ me.vertices[i].co; hit = tb.find_nearest(q, .03)
                if hit[0] is not None and (q - hit[0]).dot(hit[1]) < -1e-4: inside += 1; depth = max(depth, hit[3])
        lhx = min((mw @ me.vertices[i].co).x for i in lhand)
        hp = [mw @ me.vertices[i].co for i in helm]; sh = min(bvh.find_nearest(p)[3] for p in hp); sa = min(bvh.find_nearest(mw @ me.vertices[i].co)[3] for i in larm)
        hz0, hz1 = min(p.z for p in hp), max(p.z for p in hp); hx0, hx1 = min(p.x for p in hp), max(p.x for p in hp)
        band = [smw @ v for v in bvh0[0] if hz0 <= (smw @ v).z <= hz1]
        fgap = min((hx0 - q.x) if q.x < (hx0 + hx1) / 2 else (q.x - hx1) for q in band) if band else 1.
        tip = min((smw @ v).z for v in bvh0[0])
        row = {"frame": fr, "t": round(fr / s.render.fps, 4), "footFootMin": ff, "shinFootMin": ss, "leftSoleZ": min(p.z for p in P_["Left"]), "rightSoleZ": min(p.z for p in P_["Right"]), "swordBodyMin": sw, "swordLegTorsoMin": sl, "swordLegsMin": sleg, "tabardInsideThighVerts": inside, "tabardInsideDepth": depth, "leftHandMinX": lhx, "swordHelmetMin": sh, "swordLeftArmMin": sa, "frontViewSwordHelmetGap": fgap, "swordLowestZ": tip,
               "swordNearestBone": max(((g.group, g.weight) for g in body.data.vertices[swwhere].groups), key=lambda x: x[1])[0] if swwhere is not None else None}
        a, b_, cc = [(rig.matrix_world @ rig.pose.bones[n].head) for n in ("LeftArm", "LeftForeArm", "LeftHand")]
        row["leftElbowDeg"] = math.degrees((a - b_).angle(cc - b_))
        sp = rig.matrix_world @ rig.pose.bones["Spine"].head; nk = rig.matrix_world @ rig.pose.bones["Neck"].head
        row["torsoLeanDeg"] = math.degrees(math.atan2(-(nk - sp).y, (nk - sp).z))
        for sd in ("Left", "Right"):
            if abs(phase(sd, fr / s.render.fps) - .5 * T["duty"]) < .02:
                an = rig.matrix_world @ rig.pose.bones[sd + "Foot"].head; row["ankleLineLeanDeg"] = math.degrees(math.atan2(-(nk - an).y, (nk - an).z))
        row["leftHandZ"] = (rig.matrix_world @ rig.pose.bones["LeftHand"].head).z
        hd = rig.matrix_world @ rig.pose.bones["Head"].head; row["headZ"] = hd.z
        for sd in ("Left", "Right"):
            h, k, ft = [(rig.matrix_world @ rig.pose.bones[sd + n].head) for n in ("UpLeg", "Leg", "Foot")]
            row[sd + "KneeDeg"] = math.degrees((h - k).angle(ft - k)); row[sd + "ThighFromVertical"] = math.degrees(math.atan2(-(k - h).y, -(k - h).z))
        for sd in ("Left", "Right"):
            z0s = min(p.z for p in P_[sd]); low = [p for p in P_[sd] if p.z < z0s + .004]; row[sd + "Contact"] = list(sum(low, Vector()) / len(low)); row[sd + "ContactZ"] = z0s
        ev.to_mesh_clear(); rows.append(row)
    g0 = min(min(r["leftSoleZ"] for r in rows), min(r["rightSoleZ"] for r in rows))
    v = s.get("run_speed", 0.) / s.render.fps; slide = {}
    for sd in ("Left", "Right"):
        st = [fr for fr in range(s.frame_end + 1) if phase(sd, fr / s.render.fps) < T["duty"]]
        mid = min(st, key=lambda fr: abs(phase(sd, fr / s.render.fps) - .35 * T["duty"]))
        s.frame_set(mid); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
        vid = min(feet[sd], key=lambda i: (ev.matrix_world @ me.vertices[i].co).z); ev.to_mesh_clear()
        track = []
        for fr in st:
            s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); track.append((fr, ev.matrix_world @ me.vertices[vid].co)); ev.to_mesh_clear()
        down = [(fr, p) for fr, p in track if p.z - g0 < .003]; worst = 0.
        for (f0, p0), (f1, p1) in zip(down, down[1:]):
            if f1 - f0 == 1: d = p1 - p0; worst = max(worst, math.hypot(d.x, d.y - v))
        slide[sd] = {"trackedVertex": vid, "framesDown": len(down), "maxPerFrameSlideVsGroundSpeed": worst, "groundSpeedPerFrame": v}
    gid = {g.index: g.name for g in body.vertex_groups}
    for r in rows: r["swordNearestBone"] = gid.get(r["swordNearestBone"], r["swordNearestBone"])
    groundL = min(r["leftSoleZ"] for r in rows); groundR = min(r["rightSoleZ"] for r in rows); g0 = min(groundL, groundR)  # (used by slide)
    for r in rows: r["flight"] = r["leftSoleZ"] - g0 > .006 and r["rightSoleZ"] - g0 > .006
    # loop seam: pose and velocity continuity of every deform bone (world head positions)
    def heads(fr):
        s.frame_set(fr); return {b.name: (rig.matrix_world @ b.head).copy() for b in rig.pose.bones}
    h0, h1, hm1, hm = heads(0), heads(1), heads(s.frame_end - 1), heads(s.frame_end)
    seam = max((h0[n] - hm[n]).length for n in h0)
    vel = max(((h1[n] - h0[n]) - (hm[n] - hm1[n])).length for n in h0)  # second difference across the seam
    allh = [heads(k) for k in range(s.frame_end + 1)]
    typical = max(((allh[k+1][n] - allh[k][n]) - (allh[k][n] - allh[k-1][n])).length for k in range(1, s.frame_end) for n in h0)  # worst in-cycle second difference
    res = {"frames": len(rows), "minFootFoot": min(r["footFootMin"] for r in rows), "minShinFoot": min(r["shinFootMin"] for r in rows),
           "minSwordBody": min(r["swordBodyMin"] for r in rows), "minSwordHelmet": min(r["swordHelmetMin"] for r in rows), "minSwordLeftArm": min(r["swordLeftArmMin"] for r in rows), "minFrontViewSwordHelmetGap": min(r["frontViewSwordHelmetGap"] for r in rows), "swordLowestZRange": [min(r["swordLowestZ"] for r in rows), max(r["swordLowestZ"] for r in rows)], "minSwordLegs": min(r["swordLegsMin"] for r in rows), "tabardInsideMaxVerts": max(r["tabardInsideThighVerts"] for r in rows), "tabardInsideMaxDepth": max(r["tabardInsideDepth"] for r in rows), "leftHandMinX": min(r["leftHandMinX"] for r in rows), "ankleLineLeanDeg": [r["ankleLineLeanDeg"] for r in rows if "ankleLineLeanDeg" in r], "leftHandZRange": [min(r["leftHandZ"] for r in rows), max(r["leftHandZ"] for r in rows)], "stanceSlide": slide, "minSwordLegsTorso": min(r["swordLegTorsoMin"] for r in rows), "minSwordZ": min(r["swordLowestZ"] for r in rows),
           "flightFrames": [r["frame"] for r in rows if r["flight"]], "groundZ": g0, "loopSeamMaxHeadDelta": seam, "loopSeamSecondDiff": vel, "maxInCycleSecondDiff": typical,
           "leftElbowRange": [min(r["leftElbowDeg"] for r in rows), max(r["leftElbowDeg"] for r in rows)],
           "torsoLeanRange": [min(r["torsoLeanDeg"] for r in rows), max(r["torsoLeanDeg"] for r in rows)],
           "headZRange": [min(r["headZ"] for r in rows), max(r["headZ"] for r in rows)],
           "thighMaxFromVertical": max(max(r["LeftThighFromVertical"], r["RightThighFromVertical"]) for r in rows),
           "kneeMin": min(min(r["LeftKneeDeg"], r["RightKneeDeg"]) for r in rows), "rows": rows}
    out = cm.check_writable(c.OUT); out.mkdir(parents=True, exist_ok=True); (out / name).write_text(json.dumps(res, indent=1, default=str) + "\n")
    short = {k: v for k, v in res.items() if k != "rows"}
    short["table"] = [(r["frame"], round(r["footFootMin"], 4), round(r["shinFootMin"], 4), round(r["leftSoleZ"] - g0, 3), round(r["rightSoleZ"] - g0, 3), round(r["swordBodyMin"], 3), round(r["swordLegTorsoMin"], 3), round(r["swordLegsMin"], 3), r["tabardInsideThighVerts"], round(r["swordLowestZ"], 3), r["swordNearestBone"]) for r in rows[::3]]
    return short


# ----------------------------------------------------------------- capture ----
def capture(label, fps=30, res=420, views=None, ortho=1.45, center_z=.5):
    """Render the CURRENT scene (no open, no save) every 1/fps of one cycle, three views.
    Same workbench/ortho approach as render.py; a temporary ground plane is added and removed."""
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"]
    cam = s.camera; folder = cm.check_writable(P["out"] / "renders" / label); folder.mkdir(parents=True, exist_ok=True)
    for p in folder.glob("*.png"): p.unlink()
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = "OBJECT"
    for o in s.objects:
        if o.get("export_body"): o.color = (.53, .55, .6, 1)
        if o.get("review_attachment"): o.color = (.25, .16, .07, 1)
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, 0)); g = bpy.context.object; g.name = "TMP_Ground"; g.color = (.16, .17, .15, 1)
    marks = []
    for i in range(-6, 7):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, i * .1, .0005)); m = bpy.context.object; m.scale = (.5, .003, .001); m.color = (.3, .3, .28, 1); marks.append(m)
    views = views or {"front": (0, -4, .35), "side": (4, 0, .35), "threequarter": (2.8, -4, 1.), "rear": (0, 4, .35)}
    n = round(s["duration"] * fps); written = []
    try:
        for view, xyz in views.items():
            for i in range(n):
                ff = i / fps * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
                center = Vector((0, 0, center_z)); d = Vector(xyz).normalized(); cam.location = center + d * 5
                cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cam.data.ortho_scale = ortho
                s.render.filepath = str(folder / f"{view}-{i:04d}.png"); bpy.ops.render.render(write_still=True); written.append(s.render.filepath)
    finally:
        for o in [g, *marks]: bpy.data.objects.remove(o, do_unlink=True)
        for me in [m for m in bpy.data.meshes if m.users == 0]: bpy.data.meshes.remove(me)
    return {"folder": str(folder), "frames": len(written), "perView": n, "fps": fps}


def bake_only():
    """Iteration bake (core bake saves <out>/run_Blender_v1.blend); no delivered export."""
    s = bpy.context.scene; assert s.get("session_owner") == P["owner"] and s.get("rebuild_job") == "run"
    cm.check_writable(c.OUT); c.OUT.mkdir(parents=True, exist_ok=True); f.configure("run"); _jobs(); c.bake(); return {"blend": bpy.data.filepath}


def reach_report():
    s = bpy.context.scene; fk = bpy.data.objects["Pose_Control_Rig"]; out = []
    for fr in range(0, s.frame_end + 1, 3):
        c.at(fr); row = [fr]
        for sd in ("Left", "Right"):
            h = fk.pose.bones[sd + "UpLeg"].head; tg = bpy.data.objects[sd + "Leg_Target"].matrix_world.translation
            row.append(round((h - tg).length, 4))
        out.append(row)
    return out


def blade_probe(frames=(0, 30, 55, 75)):
    """World blade axis (socket +Z) and hull axes (socket +X/+Y) on the baked scene; idle for reference."""
    s = bpy.context.scene; sock = bpy.data.objects["ReviewWeaponSocket"]; out = {}
    sw = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment"))
    loc = [v.co for v in sw.data.vertices]
    # where is the hull mass in socket-local x/y for z>1 (blade part)?
    blade = [p for p in loc if p.z > 1.]
    out["bladeLocalMeanXY"] = [sum(p.x for p in blade) / len(blade), sum(p.y for p in blade) / len(blade)]
    out["bladeLocalRangeX"] = [min(p.x for p in blade), max(p.x for p in blade)]
    out["bladeLocalRangeY"] = [min(p.y for p in blade), max(p.y for p in blade)]
    for fr in frames:
        s.frame_set(fr); m = sock.matrix_world.to_3x3().normalized()
        out[fr] = {"z": [round(v, 3) for v in m.col[2]], "x": [round(v, 3) for v in m.col[0]], "y": [round(v, 3) for v in m.col[1]], "o": [round(v, 3) for v in sock.matrix_world.translation]}
    return out


def sword_contact(fr=0, n=8):
    """Nearest body vertices (excluding right hand/forearm) to the sword at frame fr, in sword-local coords."""
    s = bpy.context.scene; s.frame_set(fr); rig = bpy.data.objects["Knight_Deform"]
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000)
    sword = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); sword.data.calc_loop_triangles()
    smw = sword.matrix_world; bvh = BVHTree.FromPolygons([smw @ v.co for v in sword.data.vertices], [list(t.vertices) for t in sword.data.loop_triangles], all_triangles=True)
    excl = set(_groups(body, ("RightHand", "RightForeArm"))); gid = {g.index: g.name for g in body.vertex_groups}
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); res = []
    for i, v in enumerate(me.vertices):
        if i in excl: continue
        p = ev.matrix_world @ v.co; hit = bvh.find_nearest(p)
        if hit[3] is not None and hit[3] < .01: res.append((hit[3], i, [round(x, 3) for x in p], [round(x, 3) for x in (smw.inverted() @ hit[0])], sorted([(gid[g.group], round(g.weight, 2)) for g in body.data.vertices[i].groups], key=lambda x: -x[1])[:3]))
    ev.to_mesh_clear(); res.sort()
    hand = rig.matrix_world @ rig.pose.bones["RightHand"].head; elbow = rig.matrix_world @ rig.pose.bones["RightForeArm"].head
    return {"count": len(res), "nearest": res[:n], "hand": list(hand), "elbow": list(elbow)}


def left_hand_clearance(step=2):
    """Minimum distance from left hand/forearm vertices to the rest of the body (excluding the left arm chain)."""
    s = bpy.context.scene; body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000)
    hand = _groups(body, ("LeftHand", "LeftForeArm")); arm = set(_groups(body, ("LeftHand", "LeftForeArm", "LeftArm", "LeftShoulder")))
    rest = [i for i in range(len(body.data.vertices)) if i not in arm][::2]; worst = (1e3, None)
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        kd = KDTree(len(rest))
        for k, i in enumerate(rest): kd.insert(mw @ me.vertices[i].co, k)
        kd.balance(); d = min(kd.find(mw @ me.vertices[i].co)[2] for i in hand); ev.to_mesh_clear()
        if d < worst[0]: worst = (d, fr)
    return {"minLeftHandForearmToBody": worst[0], "atFrame": worst[1]}


def left_hand_near(fr, n=6):
    s = bpy.context.scene; body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000)
    gid = {g.index: g.name for g in body.vertex_groups}
    hand = _groups(body, ("LeftHand", "LeftForeArm")); arm = set(_groups(body, ("LeftHand", "LeftForeArm", "LeftArm", "LeftShoulder")))
    rest = [i for i in range(len(body.data.vertices)) if i not in arm]
    s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
    kd = KDTree(len(rest))
    for k, i in enumerate(rest): kd.insert(mw @ me.vertices[i].co, k)
    kd.balance(); out = []
    for i in hand:
        co, k, d = kd.find(mw @ me.vertices[i].co)
        if d < .01: out.append((round(d, 4), [round(x, 3) for x in co], sorted([(gid[g.group], round(g.weight, 2)) for g in body.data.vertices[rest[k]].groups], key=lambda x: -x[1])[:2], sorted([(gid[g.group], round(g.weight, 2)) for g in body.data.vertices[i].groups], key=lambda x: -x[1])[:2]))
    ev.to_mesh_clear(); out.sort(); return {"n": len(out), "near": out[:n]}



def sheet_metrics(px_per_unit=220 / 1.45):
    """Numbers the critic reads off the 18-frame sheets, from the evaluated mesh at the 30 fps sheet times."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]
    body = next(o for o in s.objects if o.type == "MESH" and o.get("export_body") and len(o.data.vertices) > 1000)
    feet = {sd: _groups(body, (sd + "Foot", sd + "ToeBase")) for sd in ("Left", "Right")}
    torso = _groups(body, ("Spine2", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm"))
    head = _groups(body, ("Head",))
    rows = []
    for i in range(18):
        ff = i / 30 * s.render.fps; s.frame_set(int(ff), subframe=ff - int(ff))
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        r = {"f": i}
        for sd in feet:
            pts = [mw @ me.vertices[j].co for j in feet[sd]]; z0 = min(p.z for p in pts); low = [p for p in pts if p.z < z0 + .01]
            r[sd + "Z"] = z0; r[sd + "Xpx"] = round(112 + sum(p.x for p in low) / len(low) * px_per_unit, 1)
        sh = rig.matrix_world @ rig.pose.bones["LeftArm"].head; band = [mw @ me.vertices[j].co for j in torso]; band = [p for p in band if abs(p.z - sh.z) < .04]
        r["shoulderWidthPx"] = round((max(p.x for p in band) - min(p.x for p in band)) * px_per_unit, 1)
        hp = [mw @ me.vertices[j].co for j in head]; r["headSideXpx"] = round(112 + (sum(p.y for p in hp) / len(hp)) * px_per_unit, 1)
        r["headFrontXpx"] = round(112 + (sum(p.x for p in hp) / len(hp)) * px_per_unit, 1)
        for sd in feet:
            an = rig.matrix_world @ rig.pose.bones[sd + "Foot"].head; r[sd + "AnkleSideXpx"] = round(112 + an.y * px_per_unit, 1)
        hb = rig.matrix_world @ rig.pose.bones["Hips"].head; r["pelvisSideXpx"] = round(112 + hb.y * px_per_unit, 1)
        lh = rig.matrix_world @ rig.pose.bones["LeftHand"].head; r["leftHandSideXpx"] = round(112 + lh.y * px_per_unit, 1); r["leftHandZ"] = round(lh.z, 3)
        ev.to_mesh_clear(); rows.append(r)
    g = min(min(r["LeftZ"], r["RightZ"]) for r in rows)
    for r in rows:
        r["LeftDown"] = r["LeftZ"] - g < .007; r["RightDown"] = r["RightZ"] - g < .007; r["airborne"] = not (r["LeftDown"] or r["RightDown"])
        r["airborne2px"] = min(r["LeftZ"], r["RightZ"]) - g > 2 / px_per_unit
    sw = [r["shoulderWidthPx"] for r in rows]
    return {"contactFramesLeft": [r["f"] for r in rows if r["LeftDown"]], "contactFramesRight": [r["f"] for r in rows if r["RightDown"]],
            "airborneFrames": [r["f"] for r in rows if r["airborne"]], "airborne2pxFrames": [r["f"] for r in rows if r["airborne2px"]],
            "frontContactXpx": {"Left": [r["LeftXpx"] for r in rows if r["LeftDown"]], "Right": [r["RightXpx"] for r in rows if r["RightDown"]]},
            "shoulderWidthPxRange": [min(sw), max(sw)], "headSideXpx": [r["headSideXpx"] for r in rows], "pelvisSideXpx": [r["pelvisSideXpx"] for r in rows],
            "headFrontXpx": [r["headFrontXpx"] for r in rows],
            "headAheadOfPlantedAnklePx": [(r["f"], round((r["LeftAnkleSideXpx"] if r["LeftDown"] else r["RightAnkleSideXpx"]) - r["headSideXpx"], 1)) for r in rows if r["LeftDown"] or r["RightDown"]],
            "leftHandSideXpx": [r["leftHandSideXpx"] for r in rows], "leftHandZ": [r["leftHandZ"] for r in rows]}


def wrist_report(step=5):
    """Right wrist rotation relative to the forearm, compared with the approved idle grip (degrees)."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; idle = idle_pose()["basis"]
    fk = bpy.data.objects["Pose_Control_Rig"]
    # idle relation from the approved idle basis on a scratch evaluation of the FK rig at rest-basis
    keep = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}; act = fk.animation_data.action; fk.animation_data.action = None
    for b in fk.pose.bones: b.matrix_basis = idle[b.name]
    bpy.context.view_layer.update(); rel0 = (fk.pose.bones["RightForeArm"].matrix.inverted() @ fk.pose.bones["RightHand"].matrix).to_quaternion()
    fk.animation_data.action = act
    out = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); rel = (rig.pose.bones["RightForeArm"].matrix.inverted() @ rig.pose.bones["RightHand"].matrix).to_quaternion()
        d = rel0.rotation_difference(rel); e = d.to_euler("XYZ")
        out.append((fr, round(math.degrees(d.angle), 1), [round(math.degrees(x), 1) for x in e]))
    return out



def blade_report(step=3):
    """Per-frame blade axis lean in front view (deg, + = top toward the body centre for the right hand),
    blade/hull silhouette centre x, grip position relative to the chest (side view forward = -Y)."""
    s = bpy.context.scene; rig = bpy.data.objects["Knight_Deform"]; sock = bpy.data.objects["ReviewWeaponSocket"]
    sw = next(o for o in s.objects if o.type == "MESH" and o.get("review_attachment")); out = []
    for fr in range(0, s.frame_end + 1, step):
        s.frame_set(fr); m = sock.matrix_world; z = m.to_3x3().normalized().col[2]
        pts = [sw.matrix_world @ v.co for v in list(sw.data.vertices)[::7]]
        ch = rig.matrix_world @ rig.pose.bones["Spine2"].head; sh = rig.matrix_world @ rig.pose.bones["RightArm"].head
        out.append({"f": fr, "frontLeanDeg": round(math.degrees(math.atan2(z.x, z.z)), 1), "sideLeanDeg": round(math.degrees(math.atan2(-z.y, z.z)), 1),
                    "bladeCentreX": round(sum(p.x for p in pts) / len(pts), 3), "gripX": round(m.translation.x, 3), "shoulderX": round(sh.x, 3),
                    "gripAheadOfChest": round(ch.y - m.translation.y, 3), "gripZ": round(m.translation.z, 3)})
    return out
