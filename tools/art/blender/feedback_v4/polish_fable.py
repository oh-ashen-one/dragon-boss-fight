"""Fable polish round (2026-10-21): NEW A/B versions of approved Knight clips. Execute ONLY in the
owned Blender MCP session via run.py (port 9887). Opens approved scenes READ-ONLY (re-tags the owner,
never saves them), layers native FK/IK control edits, bakes with the core Blender bake and writes ONLY
under <out>/<clip>/ plus a new export name. Approved files stay byte-identical.
"""
from pathlib import Path
import bpy, importlib.util, math, json, hashlib, shutil
from mathutils import Vector, Matrix, Quaternion

HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
_fs = importlib.util.spec_from_file_location('feedback2', cm.REPO / 'tools/art/blender/feedback/feedback_actions.py'); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OWNER = P['owner']
REM = cm.REPO / 'Local/Blender/remainder-20261021'


def open_src(path):
    prev = cm.open_tagged(Path(path), P['owner']); s = bpy.context.scene
    return {'opened': str(path), 'job': s.get('rebuild_job'), 'fps': s.render.fps, 'frames': [s.frame_start, s.frame_end], 'duration': s.get('duration'), 'previousOwner': prev}


def probe_feet(step=None):
    """FK foot/toe world positions per 30 fps frame (for gait phase)."""
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; out = []
    step = step or s.render.fps / 30.
    n = int(round(s.frame_end / step))
    for i in range(n + 1):
        fr = i * step; c.at(fr); row = {'f': i}
        for sd in ('Left', 'Right'):
            fm = fk.matrix_world @ fk.pose.bones[sd + 'Foot'].matrix; tm = fk.matrix_world @ fk.pose.bones[sd + 'ToeBase'].matrix
            row[sd[0]] = [round(v, 4) for v in fm.translation]; row[sd[0] + 't'] = [round(v, 4) for v in tm.translation]
            row[sd[0] + 'pitch'] = round(math.degrees(math.asin(max(-1, min(1, (fm.to_3x3() @ Vector((0, 1, 0))).normalized().z)))), 1)
        row['hips'] = [round(v, 4) for v in fk.matrix_world @ fk.pose.bones['Hips'].head]
        out.append(row)
    return out


# ------------------------------------------------------------------ shared helpers ----
def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def smoother01(x):
    x = min(1., max(0., x)); return x * x * x * (x * (6 * x - 15) + 10)


def hermite(p0, p1, v0, v1, s, dur):
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * dur * v0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * dur * v1


def wr(fk, name, axis, degrees):
    """World-axis rotation of an FK pose bone about its head."""
    if abs(degrees) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy()
    b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(degrees), 4, axis) @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def body_obj():
    s = bpy.context.scene
    return next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))


def sole_world(side, frame):
    """Evaluated sole-mesh vertices (foot/toe groups) of the DEFORM mesh at a frame, plus the deform foot matrix."""
    s = bpy.context.scene; s.frame_set(int(frame), subframe=frame - int(frame)); body = body_obj(); rig = bpy.data.objects['Knight_Deform']
    gid = {g.index: g.name for g in body.vertex_groups}; dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
    pts = [ev.matrix_world @ v.co for v in me.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, '').startswith((side + 'Foot', side + 'ToeBase'))) > .5]
    ev.to_mesh_clear(); return pts, rig.matrix_world @ rig.pose.bones[side + 'Foot'].matrix


def strap_fix():
    sp = importlib.util.spec_from_file_location('veyr_v4_strap', HERE / 'strap_v4.py'); m = importlib.util.module_from_spec(sp); m.VEYR_V4_PARAMS = globals().get('VEYR_V4_PARAMS'); sp.loader.exec_module(m)
    s = bpy.context.scene; return m.apply_body(auto_frames=list(range(0, s.frame_end + 1, 10)))


def _core_job():
    s = bpy.context.scene; job = s['rebuild_job']
    f.configure(job)  # heal/heavy: the left hand follows the forearm (neutral wrist), others: none
    if job not in c.JOBS:
        c.JOBS[job] = (str(s.get('source_action', 'REFERENCE_?')).replace('REFERENCE_', ''), s['duration'], [m.frame for m in s.timeline_markers] or [0], bool(s.get('two_hand')))
    return job


def bake_only(clip):
    """Bake into the clip's scratch folder (core bake always saves+exports at its end)."""
    s = bpy.context.scene; assert s.get('session_owner') == P['owner']
    _core_job(); old = c.OUT; c.OUT = cm.check_writable(P['out'] / clip / 'iter')
    try:
        c.bake()
    finally:
        c.OUT = old
    return {'baked': True, 'file': bpy.data.filepath}


def bake_export(clip, review, extra=None, rebake=True):
    """Bake, apply the v4 strap-fix body, export <review>.glb and save <review>.blend under <out>/<clip>/,
    copy the GLB to the v4 export dir as a NEW name (approved names refused)."""
    s = bpy.context.scene; assert s.get('session_owner') == P['owner']
    if review + '.glb' in cm.approved_names(): raise PermissionError(review + ' is an approved clip name')
    out = cm.check_writable(P['out'] / clip); out.mkdir(parents=True, exist_ok=True)
    job = _core_job(); old = c.OUT; c.OUT = out
    try:
        if rebake: c.bake()
    finally:
        c.OUT = old
    bake_report = json.loads((out / (job + '-report.json')).read_text()) if (out / (job + '-report.json')).exists() else {}
    fix = strap_fix(); c.at(0); rig = bpy.data.objects['Knight_Deform']
    for o in s.objects: o.select_set(o == rig or o.name == 'ReviewWeaponSocket' or bool(o.get('export_body')))
    bpy.context.view_layer.objects.active = rig; glb = out / (review + '.glb')
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_nla_strips_merged_animation_name=review, export_frame_range=True, export_force_sampling=True, export_optimize_animation_size=False, export_cameras=False, export_lights=False, export_extras=True)
    tx = bpy.data.texts.get('polish_fable.py') or bpy.data.texts.new('polish_fable.py'); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s['review_name'] = review; s['polish_round'] = 'fable-2026-10-21'
    blend = out / (review + '.blend'); bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    for junk in (out / (job + '_Blender_v1.blend'), out / (job + '_Blender_v1.blend1'), out / (job + '_Blender_v1.glb')):
        if junk.exists(): junk.unlink()
    sha = hashlib.sha256(glb.read_bytes()).hexdigest()
    rep = {'clip': clip, 'reviewName': review, 'duration': s['duration'], 'sha256': sha, 'nativeIKError': bake_report.get('nativeIKError'), 'endpointMatrixDelta': bake_report.get('endpointMatrixDelta'),
           'startedFrom': s.get('v4_opened_from'), 'strapFixWeightsSHA256': s.get('strap_fix_v4'), 'ownerApproved': False, 'blender': bpy.app.version_string, **(extra or {})}
    (out / (review + '-report.json')).write_text(json.dumps(rep, indent=2) + '\n')
    dest = P['export_dir'] / (review + '.glb')
    if dest.exists() and not P['allow_overwrite']: raise FileExistsError(dest)
    P['export_dir'].mkdir(parents=True, exist_ok=True); shutil.copyfile(glb, dest)
    return {'glb': str(dest), 'sha256': sha, 'blend': str(blend), 'report': rep}


# ------------------------------------------------------------------ WalkOneHand v2 ----
WALK = dict(
    T=1.2, contact={'Left': 1 / 3, 'Right': 1 / 3 + .6}, stance=.8, v=.50, y0=-.175,
    x={'Left': .085, 'Right': -.070}, strike=10., toeoff=34., roll_in=.11, peel_start=.46, lift=.034,
    sway=.013, sway_peak={'Left': .733, 'Right': .133}, hip_dz=-.025,
    head_up=-13., breath=.8, fore_flex=5., wrist_lag=4.5, sword_lag=2.2, shoulder_damp=.25,
)
FOOT = {}


def _foot_setup(side, t_mid):
    """Base flat orientation, sole heel/ball pivots and ankle height for one foot, from v1 at mid-stance."""
    s = bpy.context.scene; fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']
    pts, Mdef = sole_world(side, t_mid * fps)
    c.at(t_mid * fps); Mfk = fk.matrix_world @ fk.pose.bones[side + 'Foot'].matrix; Mtoe = fk.matrix_world @ fk.pose.bones[side + 'ToeBase'].matrix
    local = [Mdef.inverted() @ p for p in pts]
    R0 = Mfk.to_3x3().to_4x4()
    # level the sole: equal lowest heights of the rear and front quarters
    def zones(R):
        w = [R @ q for q in local]; ys = [p.y for p in w]; y0, y1 = min(ys), max(ys)
        front = min(p.z for p in w if p.y <= y0 + .25 * (y1 - y0)); back = min(p.z for p in w if p.y >= y1 - .25 * (y1 - y0)); return front, back, y0, y1
    fr, bk, y0, y1 = zones(R0); delta = math.atan2(fr - bk, (y1 - y0) * .75)
    R0 = Matrix.Rotation(delta, 4, 'X') @ R0; fr2, bk2, y0, y1 = zones(R0)  # +X rotation lowers the toes
    w = [R0 @ q for q in local]; zmin = min(p.z for p in w)
    low = [p for p in w if p.z < zmin + .010]
    heel = Vector((sum(p.x for p in low) / len(low), max(p.y for p in low), zmin)); toe = Vector((heel.x, min(p.y for p in low), zmin))
    tj = Matrix.Rotation(delta, 4, 'X') @ (Mtoe.translation - Mfk.translation)  # toe joint offset (world units) in the flat orientation
    ball = Vector((heel.x, tj.y, zmin))  # pivot under the toe joint so counter-rotated toes stay flat
    FOOT[side] = {'tj': tj, 'R0': R0, 'fr2': fr2, 'bk2': bk2, 'heel': heel, 'ball': ball, 'toe': toe, 'rel_toe': Mfk.inverted() @ Mtoe, 'levelDeg': math.degrees(delta), 'front': fr2, 'back': bk2}
    return {'levelDeg': round(math.degrees(delta), 2), 'heel': list(heel), 'ball': list(ball), 'toe': list(toe), 'tj': list(tj), 'frontBack': [fr2, bk2], 'zmin': zmin, 'objScale': list(bpy.data.objects['Pose_Control_Rig'].matrix_world.to_scale())}


def _flat(side, ay):
    """Flat foot matrix with ankle at (x_side, ay) and the lowest sole point on z=0."""
    F = FOOT[side]; return Matrix.Translation(Vector((WALK['x'][side], ay, -F['heel'].z))) @ F['R0']


def _pivot(M, side, which, pitch):
    """Rotate a foot matrix about its heel/ball contact point (world X), +pitch = toes up."""
    p = M.translation + FOOT[side][which]  # M is flat (orientation R0); offsets are stored in that orientation
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(-pitch), 4, 'X') @ Matrix.Translation(-p) @ M  # +X rotation is toes-down


def walk_foot(side, t):
    """(target matrix, toe counter-rotation deg) for one foot at time t of the in-place cycle."""
    W = WALK; T = W['T']; u = (t - W['contact'][side]) % T; st = W['stance']; v = W['v']
    def stance(uu):
        ay = W['y0'] + v * uu; M = _flat(side, ay)
        if uu < W['roll_in']:
            return _pivot(M, side, 'heel', W['strike'] * (1 - smooth01(uu / W['roll_in']))), 0.
        if uu > W['peel_start']:
            k = ((uu - W['peel_start']) / (st - W['peel_start'])); pitch = -W['toeoff'] * k ** 1.6
            return _pivot(M, side, 'ball', pitch), pitch  # toes counter-rotate, stay flat until toe-off
        return M, 0.
    if u < st: return stance(u)
    s = (u - st) / (T - st); dur = T - st
    A, toeA = stance(st); B, _ = stance(0.)
    pa = W['toeoff']; pb = W['strike']  # pitch at toe-off (heel up = -pa) and strike (+pb toes up)
    ya = A.translation.y; yb = B.translation.y; za = A.translation.z; zb = B.translation.z
    y = hermite(ya, yb, v, v, s, dur)  # leaves and lands moving with the ground
    z = za + (zb - za) * smooth01(s) + W['lift'] * math.sin(math.pi * s) ** 1.5 * (1 - .25 * s)
    pitch = -pa + (pa + pb) * smoother01(s) + 4. * math.sin(math.pi * s)
    x = W['x'][side] - (.006 if side == 'Left' else -.006) * math.sin(math.pi * s)
    M = Matrix.Translation(Vector((x, y, z))) @ Matrix.Rotation(math.radians(-pitch), 4, 'X') @ FOOT[side]['R0']
    return M, toeA * (1 - smooth01(s / .35))


def walk_v2(step=.02):
    s = bpy.context.scene; W = WALK; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'walk', 'open walk first'
    fps = s.render.fps; T = W['T']; fk = bpy.data.objects['Pose_Control_Rig']
    setup = {sd: _foot_setup(sd, W['sway_peak'][sd]) for sd in ('Left', 'Right')}
    n = round(T / step); times = [min(T, i * step) for i in range(n + 1)]
    samples = []
    for t in times:
        c.at(t * fps); samples.append({b.name: b.matrix_basis.copy() for b in fk.pose.bones})
    fk.animation_data_clear()
    targets = {sd: bpy.data.objects[sd + 'Leg_Target'] for sd in ('Left', 'Right')}
    for o in targets.values(): o.constraints.clear(); o.parent = None; o.animation_data_clear()
    prev = {}; L = {}; reach = {'Left': 0., 'Right': 0.}
    for sd in ('Left', 'Right'):
        for b in fk.pose.bones: b.matrix_basis = samples[0][b.name]
        bpy.context.view_layer.update()
        L[sd] = (fk.pose.bones[sd + 'Leg'].head - fk.pose.bones[sd + 'UpLeg'].head).length + (fk.pose.bones[sd + 'Foot'].head - fk.pose.bones[sd + 'Leg'].head).length
    w = math.tau / T
    for t, base in zip(times, samples):
        fr = t * fps
        for b in fk.pose.bones: b.matrix_basis = base[b.name]
        bpy.context.view_layer.update()
        # weight over the stance foot (peaks at mid-stance)
        sway = W['sway'] * math.cos(w * (t - W['sway_peak']['Left']))
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((sway, 0, W['hip_dz']))
        bpy.context.view_layer.update()
        # breathing: chest lifts on the up-beat of the step cycle (2 breaths per cycle would be too fast)
        br = math.sin(w * t)
        wr(fk, 'Spine1', 'X', -.5 * W['breath'] * br); wr(fk, 'Spine2', 'X', -.5 * W['breath'] * br)
        for sd, sg in (('LeftShoulder', 1), ('RightShoulder', -1)): wr(fk, sd, 'Y', sg * .6 * W['breath'] * br)
        # head up off the floor, aimed ahead; small stabilisation against the chest yaw
        wr(fk, 'Neck', 'X', .4 * W['head_up']); wr(fk, 'Head', 'X', .6 * W['head_up'])
        # free arm: forearm flexes on the forward swing (lagged), wrist trails
        arm_fwd = 1.0  # left hand reaches furthest forward at t=1.0 in v1
        wr(fk, 'LeftForeArm', 'X', -W['fore_flex'] * math.cos(w * (t - arm_fwd - .08)))
        wr(fk, 'LeftHand', 'X', W['wrist_lag'] * math.cos(w * (t - arm_fwd - .20)))
        # sword: tip trails the arm swing a beat behind (heavy blade)
        wr(fk, 'RightHand', 'X', W['sword_lag'] * math.cos(w * (t - .4 - .12)))
        for sd in ('Left', 'Right'):
            M, toe = walk_foot(sd, t)
            tg = targets[sd]; tg.matrix_basis = M; c.key(tg, fr, prev)
            # toes stay flat during the peel: counter-rotate the FK toe relative to the foot
            F = FOOT[sd]; foot = fk.pose.bones[sd + 'Foot']; toeb = fk.pose.bones[sd + 'ToeBase']
            axis = (F['R0'].to_3x3().inverted() @ Vector((1, 0, 0))).normalized()
            rel = F['rel_toe']; relm = Matrix.Translation(rel.translation) @ Matrix.Rotation(math.radians(toe), 4, axis) @ rel.to_3x3().to_4x4()
            toeb.matrix = foot.matrix @ relm; bpy.context.view_layer.update()
            reach[sd] = max(reach[sd], (fk.pose.bones[sd + 'UpLeg'].head - M.translation).length / L[sd])
        for b in fk.pose.bones: c.key(b, fr, prev)
    for o in (fk, *targets.values()): c.smooth(o)
    s['walk_v2'] = json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()}) for k, v in W.items()})
    c.at(0)
    return {'keys': len(times), 'maxLegReach': reach, 'setup': setup}


def walk_reach(side='Left', step=.05):
    """Debug: hip-to-ankle distance / leg length over the cycle for the authored targets (FK hips)."""
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; tg = bpy.data.objects[side + 'Leg_Target']; out = []
    c.at(0); L = (fk.pose.bones[side + 'Leg'].head - fk.pose.bones[side + 'UpLeg'].head).length + (fk.pose.bones[side + 'Foot'].head - fk.pose.bones[side + 'Leg'].head).length
    for i in range(int(WALK['T'] / step) + 1):
        t = i * step; c.at(t * s.render.fps); up = fk.matrix_world @ fk.pose.bones[side + 'UpLeg'].head; a = tg.matrix_world.translation
        out.append([round(t, 2), round((up - a).length / L, 3), [round(v, 3) for v in a], [round(v, 3) for v in up]])
    return {'L': L, 'rows': out}


def sole_profile(side, t, bins=14, src_frame0=False):
    """Debug: min z (mm, relative to ankle) per y-bin of the sole in the FK foot orientation at time t."""
    s = bpy.context.scene; fps = s.render.fps; pts, Mdef = sole_world(side, t * fps)
    rel = [p - Mdef.translation for p in pts]; ys = [p.y for p in rel]; y0, y1 = min(ys), max(ys); out = []
    for i in range(bins):
        a = y0 + (y1 - y0) * i / bins; b = y0 + (y1 - y0) * (i + 1) / bins; q = [p for p in rel if a <= p.y <= b]
        out.append([round(a, 3), round(min(p.z for p in q) * 1000, 1) if q else None, len(q)])
    return {'n': len(pts), 'y': [round(y0, 3), round(y1, 3)], 'bins': out, 'toeJoint': [round(v, 3) for v in (bpy.data.objects['Knight_Deform'].matrix_world @ bpy.data.objects['Knight_Deform'].pose.bones[side + 'ToeBase'].head) - Mdef.translation]}


# ------------------------------------------------------------- GuardReadyTwoHand v4 ----
V3 = cm.REPO / 'Local/Blender/feedback-v3-20261021'
GUARD = dict(
    # hilt raise parameter v: 0 = lowered ready, 1 = face cover (v3 parametrisation); <0 loads, >1 overshoots
    v=[(0, 0), (.06, 0), (.118, -.12), (.178, .40), (.232, 1.0), (.258, 1.065), (.29, .988), (.33, 1.007), (.37, .999), (.40, 1.0), (.70, 1.0)],
    hips=[(0, 0), (.06, 0), (.115, -.018), (.19, -.005), (.262, -.023), (.32, -.0135), (.365, -.0158), (.40, -.015), (.70, -.015)],
    chest=[(0, 0), (.06, 0), (.115, 2.2), (.20, -2.0), (.262, 1.8), (.32, .2), (.365, .55), (.40, .5), (.70, .5)],
    head=[(0, 0), (.06, 0), (.12, 1.2), (.21, -1.5), (.27, 3.0), (.33, 1.6), (.37, 2.0), (.40, 1.9), (.70, 1.9)],
    shrug=[(0, 0), (.06, 0), (.12, -1.0), (.22, 2.5), (.27, 1.2), (.40, 1.4), (.70, 1.4)],
)


def pchip(points, t):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    if t <= xs[0]: return ys[0]
    if t >= xs[-1]: return ys[-1]
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0: m[i] = 0.
        else:
            w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]; m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = max(j for j in range(n - 1) if xs[j] <= t); s = (t - xs[i]) / h[i]; s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * ys[i] + (s3 - 2 * s2 + s) * h[i] * m[i] + (-2 * s3 + 3 * s2) * ys[i + 1] + (s3 - s2) * h[i] * m[i + 1]


def guard_v4():
    s = bpy.context.scene; G = GUARD; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'guard_two', 'open the v3 guard first'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; h = bpy.data.objects['Hilt_Control']; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    m0 = h.matrix_world.copy(); a = Vector((0, .015, -.14)); b1 = Vector((.005, -.015, .055))
    raised3 = Matrix.Rotation(math.radians(48), 4, 'Y') @ m0.to_3x3().to_4x4(); raised_t = m0.translation - a
    def hilt(v):
        return Matrix.Translation(raised_t + a * (1 - v) + b1 * v) @ Matrix.Rotation(math.radians(-48 * (1 - v) + 18 * v), 4, 'Y') @ raised3
    err0 = max(abs((hilt(0) - m0)[i][j]) for i in range(4) for j in range(4))
    fk.animation_data_clear(); h.animation_data_clear()
    times = [round(i * .01, 4) for i in range(41)] + [.55, .70]; prev = {}
    for t in times:
        v = pchip(G['v'], t)
        for bb in fk.pose.bones: bb.matrix_basis = base[bb.name]
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((0, 0, pchip(G['hips'], t)))
        bpy.context.view_layer.update()
        ch = pchip(G['chest'], t); wr(fk, 'Spine1', 'X', .5 * ch); wr(fk, 'Spine2', 'X', .5 * ch)
        hd = pchip(G['head'], t); wr(fk, 'Neck', 'X', .4 * hd); wr(fk, 'Head', 'X', .6 * hd)
        sh = pchip(G['shrug'], t); wr(fk, 'LeftShoulder', 'Y', sh); wr(fk, 'RightShoulder', 'Y', -sh)
        fr = t * fps
        for bb in fk.pose.bones: c.key(bb, fr, prev)
        h.matrix_basis = hilt(v); c.key(h, fr, prev)
    for o in (fk, h): c.smooth(o)
    s['guard_v4'] = json.dumps(G); s['guard_ready_seconds'] = .3; c.at(0)
    return {'keys': len(times), 'hiltParamCheck': err0, 'vAt030': pchip(G['v'], .3)}


# ------------------------------------------------------------- StrafeLeft/Right v4 ----
# Blink timing/distance are fixed by the approved contract: vanish .18, reappear .34, +-1.0, 0.7 s.
STRAFE = dict(
    hips_x=[(0, 0), (.04, 0), (.10, -.016), (.15, .075), (.18, .20), (.26, .56), (.34, .905), (.38, .972), (.42, .998), (.50, 1.006), (.58, 1.001), (.70, 1.0)],
    hips_z=[(0, 0), (.04, 0), (.10, -.046), (.135, -.024), (.16, .012), (.18, .026), (.26, .034), (.34, .010), (.385, -.04), (.43, -.056), (.50, -.032), (.565, -.004), (.62, .010), (.70, 0)],
    lean=[(0, 0), (.04, 0), (.10, 3.5), (.16, -11.), (.26, -11.), (.34, -6.), (.40, 7.5), (.48, 4.), (.58, -1.), (.66, 0), (.70, 0)],
    crouch=[(0, 0), (.04, 0), (.10, 5.5), (.16, 1.5), (.30, 2.), (.42, 8.), (.55, 2.), (.70, 0)],
    sword=[(0, 0), (.04, 0), (.10, -2.5), (.13, -2.), (.17, -.5), (.21, 2.5), (.30, 0.), (.34, -2.), (.40, 1.), (.45, 2.), (.52, 1.), (.60, -.3), (.65, 0), (.70, 0)], sword_crouch_comp=.9,
    free=[(0, 0), (.04, 0), (.10, 5.), (.18, -14.), (.34, -10.), (.42, 8.), (.50, 3.), (.58, -1.), (.65, 0), (.70, 0)],
    free_out=[(0, 0), (.04, 0), (.12, 2.), (.20, 9.), (.34, 9.), (.42, 4.), (.55, 1.), (.70, 0)],
    # feet: lead steps out first and lands on the final spot; trail pushes off its ball, lands short, then a recovery step
    lead_x=[(0, 0), (.10, 0), (.18, .22), (.34, .975), (.365, 1.0), (.70, 1.0)],
    lead_z=[(0, 0), (.10, 0), (.15, .05), (.20, .085), (.30, .07), (.34, .02), (.365, 0), (.70, 0)],
    trail_x=[(0, 0), (.15, 0), (.18, .11), (.34, .80), (.40, .945), (.54, .945), (.64, 1.0), (.70, 1.0)],
    trail_z=[(0, 0), (.15, 0), (.20, .06), (.30, .09), (.36, .035), (.40, 0), (.54, 0), (.59, .022), (.64, 0), (.70, 0)],
    trail_heel=[(0, 0), (.09, 0), (.15, 18.), (.20, 8.), (.36, 3.), (.40, 0), (.54, 0), (.57, 8.), (.62, 2.), (.64, 0), (.70, 0)],
)


def strafe_v4():
    s = bpy.context.scene; job = s.get('rebuild_job'); S = STRAFE
    assert s.get('session_owner') == P['owner'] and job in ('strafe_left', 'strafe_right'), 'open a v3 strafe first'
    sign = 1 if job == 'strafe_left' else -1; lead, trail = ('Left', 'Right') if sign == 1 else ('Right', 'Left')
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}; world = {b.name: b.matrix.copy() for b in fk.pose.bones}
    toe = {sd: (fk.matrix_world @ fk.pose.bones[sd + 'ToeBase'].head).copy() for sd in ('Left', 'Right')}
    tip = {}
    for sd in ('Left', 'Right'):
        pts, _ = sole_world(sd, 0); zmin = min(p.z for p in pts); low = [p for p in pts if p.z < zmin + .004]
        fr_ = min(low, key=lambda p: p.y); tip[sd] = Vector((fr_.x, fr_.y, zmin))
    c.at(0)
    fk.animation_data_clear(); tg = {}; pl = {}; polebase = {}
    for sd in ('Left', 'Right'):
        tg[sd] = bpy.data.objects[sd + 'Leg_Target']; pl[sd] = bpy.data.objects[sd + 'Leg_Pole']
        for o in (tg[sd], pl[sd]): f.reset_animation(o)
        a, mid, end = [world[sd + n].translation for n in ('UpLeg', 'Leg', 'Foot')]; axis = (end - a).normalized(); d = mid - a - axis * (mid - a).dot(axis)
        polebase[sd] = mid + d.normalized() * .3
    times = [round(i * .01, 4) for i in range(71)]; prev = {}
    for t in times:
        fr = t * fps; hx = sign * pchip(S['hips_x'], t); hz = pchip(S['hips_z'], t)
        for b in fk.pose.bones: b.matrix_basis = base[b.name]
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((hx, 0, hz))
        bpy.context.view_layer.update()
        ln = sign * pchip(S['lean'], t); cr = pchip(S['crouch'], t)
        wr(fk, 'Spine', 'Y', -.35 * ln); wr(fk, 'Spine2', 'Y', -.65 * ln)
        wr(fk, 'Spine', 'X', .55 * cr); wr(fk, 'Spine1', 'X', .45 * cr)
        wr(fk, 'Neck', 'Y', .3 * ln); wr(fk, 'Head', 'Y', .35 * ln); wr(fk, 'Head', 'X', -.35 * cr)
        wr(fk, 'RightArm', 'X', pchip(S['sword'], t) - S.get('sword_crouch_comp', 0.) * cr); wr(fk, 'RightForeArm', 'X', .5 * pchip(S['sword'], t - .03))  # r2: arm holds the blade against the torso pitch
        wr(fk, 'LeftArm', 'X', pchip(S['free'], t)); wr(fk, 'LeftForeArm', 'X', .6 * pchip(S['free'], t - .03))
        wr(fk, 'LeftArm', 'Y', -pchip(S['free_out'], t))
        for b in fk.pose.bones: c.key(b, fr, prev)
        for sd in ('Left', 'Right'):
            isl = sd == lead; x = sign * pchip(S['lead_x' if isl else 'trail_x'], t); z = pchip(S['lead_z' if isl else 'trail_z'], t)
            m = Matrix.Translation(Vector((x, 0, z))) @ world[sd + 'Foot']
            heel = 0. if isl else pchip(S['trail_heel'], t)
            if heel > 1e-6:
                pv = tip[sd] + Vector((x, 0, z))  # r2: pivot on the toe TIP so the toe cap never goes under the floor
                m = Matrix.Translation(pv) @ Matrix.Rotation(math.radians(heel), 4, 'X') @ Matrix.Translation(-pv) @ m
            tg[sd].matrix_basis = m; c.key(tg[sd], fr, prev)
            pl[sd].location = polebase[sd] + Vector((.5 * (x + hx), 0, .5 * hz)); pl[sd].keyframe_insert('location', frame=fr)
    for o in (fk, *tg.values(), *pl.values()): c.smooth(o)
    s['strafe_v4'] = json.dumps(S); c.at(0)
    return {'keys': len(times), 'sign': sign, 'lead': lead, 'blink': s.get('blink_vfx'), 'veyrBlink': bpy.data.objects['Knight_Deform'].get('veyrBlink')}


def leg_reach(step=3):
    """Debug: per-frame hip-to-target distance / leg length for both legs, plus end-vs-start deform error."""
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; rig = bpy.data.objects['Knight_Deform']; out = {'Left': [], 'Right': []}
    c.at(0); L = {sd: (fk.pose.bones[sd + 'Leg'].head - fk.pose.bones[sd + 'UpLeg'].head).length + (fk.pose.bones[sd + 'Foot'].head - fk.pose.bones[sd + 'Leg'].head).length for sd in out}
    start = {n: (rig.matrix_world @ rig.pose.bones[n].head).copy() for n in ('Hips', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot')}
    for fr in range(0, s.frame_end + 1, step):
        c.at(fr)
        for sd in out:
            r = ((fk.matrix_world @ fk.pose.bones[sd + 'UpLeg'].head) - bpy.data.objects[sd + 'Leg_Target'].matrix_world.translation).length / L[sd]
            if r > .985: out[sd].append([fr, round(r, 3)])
    c.at(s.frame_end)
    end = {n: [round(v, 5) for v in (rig.matrix_world @ rig.pose.bones[n].head) - start[n]] for n in start}
    c.at(0); return {'over985': out, 'endMinusStart': end}


def hide_keys(path):
    """hide_render keyframes (frame, value, interpolation) per exported mesh, plus the veyrBlink extra."""
    open_src(path); s = bpy.context.scene; out = {}
    for o in s.objects:
        if o.type == 'MESH' and (o.get('export_body') or o.get('review_attachment')) and o.animation_data and o.animation_data.action:
            for fc in c.curves(o.animation_data.action):
                if fc.data_path == 'hide_render': out[o.name] = [(round(k.co.x, 4), k.co.y, k.interpolation) for k in fc.keyframe_points]
    return {'keys': out, 'veyrBlink': bpy.data.objects['Knight_Deform'].get('veyrBlink'), 'fps': s.render.fps}


# ---------------------------------------------------------------- WalkOneHand v2r2 ----
def idle_feet(path=None):
    """Store the approved idle's foot orientation, toe joint and sole points (foot-local) for both feet."""
    path = path or (cm.REPO / 'Local/Blender/feedback-v4-20261021/backpedal-round5/backpedal_Blender_v1.blend')
    open_src(path); s = bpy.context.scene; c.at(0); fk = bpy.data.objects['Pose_Control_Rig']; out = {}
    for sd in ('Left', 'Right'):
        pts, Mdef = sole_world(sd, 0)
        Mfk = fk.matrix_world @ fk.pose.bones[sd + 'Foot'].matrix; Mt = fk.matrix_world @ fk.pose.bones[sd + 'ToeBase'].matrix
        out[sd] = {'R': [list(r) for r in Mfk.to_3x3()], 'toeJoint': list(Mt.translation - Mfk.translation), 'relToe': [list(r) for r in (Mfk.inverted() @ Mt)],
                   'local': [list(Mdef.inverted() @ p) for p in pts], 'defVsFk': (Mdef.translation - Mfk.translation).length, 'soleMinZ': min(p.z for p in pts)}
    dst = cm.check_writable(P['out']) / 'idle_feet.json'; dst.write_text(json.dumps(out)); return {sd: {'defVsFk': v['defVsFk'], 'soleMinZ': v['soleMinZ'], 'n': len(v['local'])} for sd, v in out.items()}


def _foot_setup_idle(side, t_mid):
    """Flat = the approved idle foot orientation, turned to the walk's heading at mid-stance."""
    s = bpy.context.scene; fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']
    d = json.loads((P['out'] / 'idle_feet.json').read_text())[side]
    Ri = Matrix(d['R']); local = [Vector(q) for q in d['local']]
    pw, Mdw = sole_world(side, t_mid * fps); c.at(t_mid * fps)
    Mtw = fk.matrix_world @ fk.pose.bones[side + 'ToeBase'].matrix
    def heading(pts, toward):
        # major axis of the sole footprint (XY PCA), pointing toward the toe joint
        mx = sum(p.x for p in pts) / len(pts); my = sum(p.y for p in pts) / len(pts)
        sxx = sum((p.x - mx) ** 2 for p in pts); syy = sum((p.y - my) ** 2 for p in pts); sxy = sum((p.x - mx) * (p.y - my) for p in pts)
        ang = .5 * math.atan2(2 * sxy, sxx - syy); v = Vector((math.cos(ang), math.sin(ang), 0))
        if v.dot(Vector((toward.x - mx, toward.y - my, 0))) < 0: v = -v
        return math.atan2(v.y, v.x)
    wi = [Ri.to_4x4() @ q for q in local]
    yaw = heading([p - Mdw.translation for p in pw], Mtw.translation - Mdw.translation) - heading(wi, Vector(d['toeJoint']))
    yaw = (yaw + math.pi) % math.tau - math.pi
    Rz = Matrix.Rotation(yaw, 4, 'Z'); R0 = Rz @ Ri.to_4x4()
    w = [R0 @ q for q in local]; zmin = min(p.z for p in w); low = [p for p in w if p.z < zmin + .010]
    tj = Rz @ Vector(d['toeJoint'])
    heel = Vector((sum(p.x for p in low) / len(low), max(p.y for p in w if p.z < zmin + .012), zmin))
    ball = Vector((heel.x, tj.y, zmin))
    FOOT[side] = {'R0': R0, 'heel': heel, 'ball': ball, 'tj': tj, 'rel_toe': Matrix(d['relToe'])}
    ys = [p.y for p in w]; y0, y1 = min(ys), max(ys)
    front = min(p.z for p in w if p.y <= y0 + .25 * (y1 - y0)); back = min(p.z for p in w if p.y >= y1 - .25 * (y1 - y0))
    return {'yawDeg': round(math.degrees(yaw), 2), 'heel': [round(v, 4) for v in heel], 'ball': [round(v, 4) for v in ball], 'frontMinusBackMM': round(1000 * (front - back), 1)}


WALK2 = dict(v=.66, stance=.64, y0=-.19, hip_dz=-.036, sway=.008, sway_counter=.55,
             sword_swing=.7, sword_fore=.5, sword_hand=1.8, tip_lift=-2.5, fore_flex=9., wrist_lag=7., lagF=.067, lagH=.10, even_dips=True)


def walk_v2r2(step=.02):
    """v2 plus the critic's r2 fixes: both feet use the idle's flat sole (heel strike, flat stance), baseline ground
    speed .66 u/s, evened step dips, head kept over the pelvis sway, continuously swinging sword arm with lag."""
    s = bpy.context.scene; W = WALK; W2 = WALK2; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'walk'
    W.update(v=W2['v'], stance=W2['stance'], y0=W2['y0'], hip_dz=W2['hip_dz'], sway=W2['sway'], fore_flex=W2['fore_flex'], wrist_lag=W2['wrist_lag'], sword_lag=0.)
    fps = s.render.fps; T = W['T']; fk = bpy.data.objects['Pose_Control_Rig']
    setup = {sd: _foot_setup_idle(sd, (W['contact'][sd] + W['stance'] / 2) % T) for sd in ('Left', 'Right')}
    n = round(T / step); times = [min(T, i * step) for i in range(n + 1)]
    samples = []; hz = []
    for t in times:
        c.at(t * fps); samples.append({b.name: b.matrix_basis.copy() for b in fk.pose.bones}); hz.append((fk.matrix_world @ fk.pose.bones['Hips'].head).z)
    half = n // 2
    dz_even = [(.5 * (hz[i] + hz[(i + half) % n]) - hz[i]) if W2['even_dips'] else 0. for i in range(n)] + [0.]
    dz_even[-1] = dz_even[0]
    fk.animation_data_clear()
    targets = {sd: bpy.data.objects[sd + 'Leg_Target'] for sd in ('Left', 'Right')}
    for o in targets.values(): o.constraints.clear(); o.parent = None; o.animation_data_clear()
    prev = {}; reach = {'Left': 0., 'Right': 0.}; L = {}
    for b in fk.pose.bones: b.matrix_basis = samples[0][b.name]
    bpy.context.view_layer.update()
    for sd in ('Left', 'Right'):
        L[sd] = (fk.pose.bones[sd + 'Leg'].head - fk.pose.bones[sd + 'UpLeg'].head).length + (fk.pose.bones[sd + 'Foot'].head - fk.pose.bones[sd + 'Leg'].head).length
    w = math.tau / T; lf = W['contact']['Left']
    for i, (t, base) in enumerate(zip(times, samples)):
        fr = t * fps
        for b in fk.pose.bones: b.matrix_basis = base[b.name]
        bpy.context.view_layer.update()
        sway = W['sway'] * math.cos(w * (t - W['sway_peak']['Left']))
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((sway, 0, W['hip_dz'] + dz_even[i]))
        bpy.context.view_layer.update()
        # keep the head over the feet: lean the spine against the pelvis sway
        wr(fk, 'Spine', 'Y', -math.degrees(math.asin(max(-1, min(1, W2['sway_counter'] * sway / .33)))))
        br = math.sin(w * t)
        wr(fk, 'Spine1', 'X', -.5 * W['breath'] * br); wr(fk, 'Spine2', 'X', -.5 * W['breath'] * br)
        for sd, sg in (('LeftShoulder', 1), ('RightShoulder', -1)): wr(fk, sd, 'Y', sg * .6 * W['breath'] * br)
        wr(fk, 'Neck', 'X', .4 * W['head_up']); wr(fk, 'Head', 'X', .6 * W['head_up'])
        # free arm: visible forearm follow-through and trailing wrist
        wr(fk, 'LeftForeArm', 'X', -W['fore_flex'] * math.cos(w * (t - 1.0 - .08)))
        wr(fk, 'LeftHand', 'X', W['wrist_lag'] * math.cos(w * (t - 1.0 - .20)))
        # sword arm swings continuously (forward with the left leg); forearm and blade trail by 2 and 3 frames
        wr(fk, 'RightArm', 'X', -W2['sword_swing'] * math.cos(w * (t - lf)))
        wr(fk, 'RightForeArm', 'X', -W2['sword_fore'] * math.cos(w * (t - lf - W2['lagF'])))
        wr(fk, 'RightHand', 'X', W2['tip_lift'] - W2['sword_hand'] * math.cos(w * (t - lf - W2['lagH'])))
        for sd in ('Left', 'Right'):
            M, toe = walk_foot(sd, t)
            tg = targets[sd]; tg.matrix_basis = M; c.key(tg, fr, prev)
            F = FOOT[sd]; foot = fk.pose.bones[sd + 'Foot']; toeb = fk.pose.bones[sd + 'ToeBase']
            axis = (F['R0'].to_3x3().inverted() @ Vector((1, 0, 0))).normalized(); rel = F['rel_toe']
            toeb.matrix = foot.matrix @ (Matrix.Translation(rel.translation) @ Matrix.Rotation(math.radians(toe), 4, axis) @ rel.to_3x3().to_4x4()); bpy.context.view_layer.update()
            reach[sd] = max(reach[sd], (fk.pose.bones[sd + 'UpLeg'].head - M.translation).length / L[sd])
        for b in fk.pose.bones: c.key(b, fr, prev)
    for o in (fk, *targets.values()): c.smooth(o)
    s['walk_v2r2'] = json.dumps({'WALK': {k: v for k, v in W.items()}, 'WALK2': W2}); c.at(0)
    return {'keys': len(times), 'maxLegReach': reach, 'setup': setup, 'impliedGroundSpeed_units_per_s': W['v'], 'stanceTravel': W['v'] * W['stance']}



# ------------------------------------------------------- GuardReadyTwoHand v4r2 (critic) ----
GUARD_R2 = dict(
    # eased 4-frame anticipation (f1-f4), one ramp-in frame, then the v4 snap/brake/overshoot/rebound shape shifted +1 frame
    v=[(0, 0), (.035, 0), (.135, -.12), (.167, .02), (.20, .40), (.265, 1.0), (.291, 1.065), (.323, .988), (.36, 1.007), (.385, .999), (.40, 1.0), (.70, 1.0)],
    hips=[(0, 0), (.035, 0), (.135, -.02), (.22, -.004), (.30, -.046), (.345, -.009), (.375, -.0175), (.40, -.015), (.70, -.015)],
    chest=[(0, 0), (.035, 0), (.135, 2.4), (.22, -2.0), (.30, 4.2), (.35, -.6), (.38, .3), (.40, 0), (.70, 0)],
    head=[(0, 0), (.035, 0), (.135, 1.4), (.23, -1.5), (.31, 7.5), (.355, -1.2), (.38, .4), (.40, 0), (.70, 0)],
    shrug=[(0, 0), (.035, 0), (.135, -1.2), (.24, 2.5), (.295, 6.5), (.35, -.8), (.38, .3), (.40, 0), (.70, 0)],
)


def guard_v4r2():
    GUARD.update(GUARD_R2); return guard_v4()


# ------------------------------------------------------------------- Stagger v2 ----
# Key poses come from the approved v1's own recoil (FK at .07 s) and absorb (FK at .23 s); v2 re-times them
# with an impact snap and a clean ease home (v1 jumps back to idle in its last frame), adds overlap
# (head, arms and blade lag the trunk) and keeps both feet planted so the knees take the weight.
STAG = dict(lag_spine1=0., lag_spine2=0., tA=.07, tB=.23, snap=.045, over=1.14, settleA=.085, absorb=.17, home=.355,
            lag_head=.035, lag_neck=.02, lag_arm=.02, lag_fore=.035, lag_hand=.05, extra_dip=-.012)
LAGS = {'Spine1': 'lag_spine1', 'Spine2': 'lag_spine2', 'Neck': 'lag_neck', 'Head': 'lag_head', 'LeftArm': 'lag_arm', 'LeftForeArm': 'lag_fore', 'LeftHand': 'lag_hand',
        'RightForeArm': 'lag_fore', 'RightHand': 'lag_hand'}


def _blend(pa, pb, k):
    out = {}
    for n in pa:
        la, ra, sa = pa[n].decompose(); lb, rb, sb = pb[n].decompose()
        if ra.dot(rb) < 0: rb = -rb
        out[n] = Matrix.LocRotScale(la.lerp(lb, k), ra.slerp(rb, k) if 0 <= k <= 1 else _qextrap(ra, rb, k), sa.lerp(sb, k))
    return out


def _qextrap(qa, qb, k):
    d = qa.inverted() @ qb; ang = d.angle; ax = d.axis
    return qa @ Quaternion(ax, ang * k)


def stagger_pose(t, I, A, B, prof=None):
    S = STAG; Ao = _blend(I, A, S['over'])
    if S.get('b_mix') is not None: B = _blend(A, B, S['b_mix'])  # r2: a smaller second lurch
    if prof and prof.endswith('A'): B = A  # r4: this group holds the recoil pose through the absorb (no second push)
    if prof == 'trapHA' and t >= S['settleA']:  # r4 head: own long eased return window
        h0, h1 = S['head_home']; u = min(1., max(0., (t - h0) / (h1 - h0))); a_ = S.get('trap_a', .3); vmax = 1 / (1 - a_)
        k = (vmax * u * u / (2 * a_)) if u < a_ else (1 - vmax * (1 - u) ** 2 / (2 * a_)) if u > 1 - a_ else (vmax * (u - a_ / 2))
        return _blend(A, I, k)
    if t <= 0: return I
    if t < S['snap']: s = (t / S['snap']); return _blend(I, Ao, 1 - (1 - s) ** 3)  # impact: full speed at once, braking into the overshoot
    if t < S['settleA']: return _blend(Ao, A, smooth01((t - S['snap']) / (S['settleA'] - S['snap'])))
    if t < S['absorb']: return _blend(A, B, smooth01((t - S['settleA']) / (S['absorb'] - S['settleA'])))
    h0 = S.get('home_start', S['absorb'])
    if t < h0: return B
    if t < S['home']:
        u = (t - h0) / (S['home'] - h0)
        if prof in ('bell', 'bellA'): return _blend(B, I, smoother01(u))
        if S.get('home_trap') or prof in ('trap', 'trapA'):  # constant-velocity middle: lowest peak speed for the distance (accelerate/decelerate 30% each)
            a_ = S.get('trap_a', .3); vmax = 1 / (1 - a_)
            k = (vmax * u * u / (2 * a_)) if u < a_ else (1 - vmax * (1 - u) ** 2 / (2 * a_)) if u > 1 - a_ else (vmax * (u - a_ / 2))
            return _blend(B, I, k)
        return _blend(B, I, smooth01(u) if S.get('home_soft') else smoother01(u))
    return I


def stagger_v2(step=.005):
    s = bpy.context.scene; S = STAG; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'stagger'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; dur = s['duration']
    def basis(t): c.at(t * fps); return {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    I = basis(0.); A = basis(S['tA']); B = basis(S['tB'])
    c.at(0); world = {b.name: b.matrix.copy() for b in fk.pose.bones}
    fk.animation_data_clear(); prev = {}
    for sd in ('Left', 'Right'):
        tg = bpy.data.objects[sd + 'Leg_Target']; tg.constraints.clear(); tg.parent = None; tg.animation_data_clear()
        if S.get('rstep') and sd == 'Right': continue
        for t in (0., dur): tg.matrix_basis = world[sd + 'Foot']; c.key(tg, t * fps, prev)  # planted: weight goes into the ground
    n = round(dur / step); times = [min(dur, i * step) for i in range(n + 1)]; BB = {}
    for t in times:
        base = stagger_pose(t, I, A, B)
        for b in fk.pose.bones:
            lag = S[LAGS[b.name]] if b.name in LAGS else 0.
            pr = S.get('prof', {}).get(b.name)
            b.matrix_basis = stagger_pose(max(0., t - lag), I, A, B, pr)[b.name] if (lag or pr) else base[b.name]
            if b.name.endswith('ToeBase'): b.matrix_basis = I[b.name]  # planted toes stay flat
        dip = S['extra_dip'] * math.sin(math.pi * min(1., max(0., (t - S['settleA']) / (S['home'] - S['settleA'])))) ** 2
        if S.get('impact_dip'): dip += S['impact_dip'] * (1 - (1 - min(1., t / .05)) ** 2 if t < .05 else 1.) * (1 - smooth01((t - .05) / .2))
        hy = pchip(S['hip_y'], t) if S.get('hip_y') else 0.; hx = pchip(S['hip_x'], t) if S.get('hip_x') else 0.
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((hx, hy, dip))
        bpy.context.view_layer.update()
        if S.get('blade_bell'): _stag_blade_bell(t, fk, BB)
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        if S.get('rstep'): _stag_rstep(t, world, prev, fps)
    for o in (fk,): c.smooth(o)
    # keep the impact discontinuity sharp at t=0: linear first segment
    for fc in c.curves(fk.animation_data.action):
        for k in fc.keyframe_points:
            if k.co.x <= S['snap'] * fps + 1e-6: k.interpolation = 'LINEAR'
    s['stagger_v2'] = json.dumps(S); c.at(0)
    return {'keys': len(times), 'fps': fps, 'duration': dur}


# --------------------------------------------------------------------- Death v2 ----
# Re-timed from the approved v1's own FK action: a sharper hit (faster first 0.3 s), lagging head/arms
# (overlap; the held blade follows the wrist until its native release), compression on the knee and body
# impacts with a head nod, feet kept on/above the floor, and the v1 terminal drift (3.0-4.4 s) compressed
# into a settle so the final pose is held perfectly still from 3.8 s.
DEATH = dict(lag_spine1=0., lag_spine2=0., warp_end=.30, warp_pow=1.8, settle0=3.0, settle1=3.8, src_end=4.4,
             knee=(1.42, -.014, .09), slam=(2.20, -.010, .10), nod=(2.22, 6., .12),
             lag_head=.045, lag_neck=.025, lag_arm=.025, lag_fore=.04, lag_hand=.06)


def death_tau(t):
    D = DEATH
    if t <= 0: return 0.
    if t < D['warp_end']: return D['warp_end'] * (1 - (1 - t / D['warp_end']) ** D['warp_pow'])
    if t < D['settle0']: return t
    if t < D['settle1']: return D['settle0'] + (D['src_end'] - D['settle0']) * smoother01((t - D['settle0']) / (D['settle1'] - D['settle0']))
    return D['src_end']


def _bump(t, c0, amp, w):
    return amp * math.exp(-((t - c0) / w) ** 2) if abs(t - c0) < 3 * w else 0.


def death_v2(step=1 / 75):
    s = bpy.context.scene; D = DEATH; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'death'
    fps = s.render.fps; fk = bpy.data.objects['Pose_Control_Rig']; dur = s['duration']; ns = round(dur * fps)
    src = {}
    for fr in range(0, ns + 1, 2):
        c.at(fr); src[fr] = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    keys = sorted(src)
    def v1(tau):
        x = min(ns, max(0., tau * fps)); i = min(range(len(keys) - 1), key=lambda j: abs(keys[j] - x)) if False else min(len(keys) - 2, int(x // 2))
        a, b = keys[i], keys[i + 1]; k = (x - a) / (b - a)
        return _blend(src[a], src[b], max(0., min(1., k)))
    d = json.loads((P['out'] / 'idle_feet.json').read_text())
    low = {sd: sorted([Vector(q) for q in d[sd]['local']], key=lambda q: q.z)[:220] for sd in ('Left', 'Right')}
    lowall = {sd: [Vector(q) for q in d[sd]['local']] for sd in ('Left', 'Right')}
    fk.animation_data_clear(); prev = {}; tg = {}
    for sd in ('Left', 'Right'):
        tg[sd] = bpy.data.objects[sd + 'Leg_Target']; tg[sd].constraints.clear(); tg[sd].parent = None; tg[sd].animation_data_clear()
    n = round(dur / step); times = [min(dur, i * step) for i in range(n + 1)]; lifted = {'Left': 0., 'Right': 0.}
    FINAL = v1(D['src_end'])
    def posed(tt):
        if D.get('tail') is None: return v1(death_tau(tt))
        a, b_ = D['tail']; p = v1(min(tt, D['src_end']) if tt >= D['warp_end'] else death_tau(tt))
        return p if tt <= a else _blend(p, FINAL, smoother01((tt - a) / (b_ - a)))  # r2: late arm drift merged into the main settle
    for t in times:
        base = posed(t)
        for b in fk.pose.bones:
            lag = D[LAGS[b.name]] if b.name in LAGS else 0.
            b.matrix_basis = posed(max(0., t - lag))[b.name] if lag else base[b.name]
        dz = _bump(t, *D['knee']) + _bump(t, *D['slam']) + (pchip(D['lift'], t) if D.get('lift') else 0.)  # lift keeps knees/body on the floor
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((0, 0, dz))
        bpy.context.view_layer.update()
        nod = _bump(t, *D['nod']); wr(fk, 'Head', 'X', nod); wr(fk, 'Neck', 'X', .4 * nod)
        if D.get('bend'): bd = pchip(D['bend'], t); wr(fk, 'Spine', 'X', .5 * bd); wr(fk, 'Spine1', 'X', .5 * bd)  # r3: keeps the head from rising after the knee lands
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        wk = smoother01((t - D['kneel'][0]) / .12) * (1 - smoother01((t - D['kneel'][1]) / .12)) if D.get('kneel') else 0.
        for sd in ('Left', 'Right'):
            M = fk.matrix_world @ fk.pose.bones[sd + 'Foot'].matrix
            if wk > 0 and sd == D.get('trail'):
                # trailing shin lies on the floor: swing the shin down about the knee to the floor, foot riding with it
                K = fk.matrix_world @ fk.pose.bones[sd + 'Leg'].head; A = M.translation; old = A - K; b_ = old.length
                dxy = Vector((old.x, old.y, 0)); dxy = dxy.normalized() if dxy.length > 1e-4 else Vector((0, 1, 0))
                fz = D['ankle_z']; dz = fz - K.z; horiz = math.sqrt(max(0., b_ * b_ - dz * dz)); new = dxy * horiz + Vector((0, 0, dz))
                R = old.normalized().rotation_difference(new.normalized()).to_matrix().to_4x4()
                Mn = Matrix.Translation(K + new) @ R @ Matrix.Translation(-A) @ M
                M = _mblend(M, Mn, wk)
            elif wk > 0 and sd == D.get('front'):
                M = _mblend(M, _roll_contact(sd, M), wk)  # front foot planted flat on the floor
            zmin = min((M @ q).z for q in (lowall[sd] if t > 1.0 else low[sd]))
            if zmin < 0: M = Matrix.Translation(Vector((0, 0, -zmin))) @ M; lifted[sd] = max(lifted[sd], -zmin)
            tg[sd].matrix_basis = M; c.key(tg[sd], t * fps, prev)
    for o in (fk, *tg.values()): c.smooth(o)
    s['death_v2'] = json.dumps(D); c.at(0)
    return {'keys': len(times), 'footLiftApplied_m': lifted}


def body_ground(step_s=.1, t0=0.):
    """Whole-body evaluated mesh min z (mm) per sample and key-bone motion over the last 0.6 s."""
    s = bpy.context.scene; body = body_obj(); rig = bpy.data.objects['Knight_Deform']; fps = s.render.fps; out = []
    t = t0
    while t <= s['duration'] + 1e-6:
        fr = t * fps; s.frame_set(int(fr), subframe=fr - int(fr)); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        out.append([round(t, 2), round(1000 * min((mw @ v.co).z for v in me.vertices), 1)]); ev.to_mesh_clear(); t += step_s
    def pos(tt):
        fr = tt * fps; s.frame_set(int(fr), subframe=fr - int(fr)); return {b.name: (rig.matrix_world @ b.head).copy() for b in rig.pose.bones}
    a = pos(s['duration'] - .6); b = pos(s['duration'])
    still = max((a[n] - b[n]).length for n in a)
    return {'minZ': out, 'terminalMaxBoneMove_m_last0.6s': still}


def death_iterate(passes=2):
    """Measure whole-body floor penetration, add a smooth hips lift, re-author and re-bake (repeat)."""
    hist = []
    for k in range(passes):
        open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2')
        g = body_ground(step_s=.05, t0=1.0)
        cur = dict(DEATH.get('lift') or [])
        pts = []
        for tt, mz in g['minZ']:
            if tt > 2.6: break
            base = pchip(DEATH['lift'], tt) if DEATH.get('lift') else 0.
            pts.append((tt, max(0., base + max(0., -(mz - 1.) / 1000.) * 1.05)))
        pts = [(0., 0.), (.95, 0.)] + [p for p in pts if p[0] >= 1.0] + [(2.75, 0.), (4.4, 0.)]
        DEATH['lift'] = pts; hist.append({'pass': k, 'worstMM': min(m for _, m in g['minZ'])})
    open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2'); g = body_ground(step_s=.05, t0=0.)
    return {'history': hist, 'finalWorstMM': min(m for _, m in g['minZ']), 'finalMinZ': g['minZ'], 'still': g['terminalMaxBoneMove_m_last0.6s'], 'lift': DEATH['lift']}


def sword_probe(step30=1):
    """Per 30 fps frame: blade tip and pommel world positions vs the hips (y back, z up), and left-arm elevation."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; fps = s.render.fps
    sword = [o for o in s.objects if o.type == 'MESH' and o.get('review_attachment')]
    out = []; st = fps / 30.; n = int(s.frame_end / st + 1e-6) + 1; idx = {}
    for i in range(0, n, step30):
        fr = i * st; s.frame_set(int(fr), subframe=fr - int(fr)); dg = bpy.context.evaluated_depsgraph_get(); hand = rig.matrix_world @ rig.pose.bones['RightHand'].head
        pts = []
        for o in sword:
            e = o.evaluated_get(dg); m = e.to_mesh(); w = e.matrix_world
            if o.name not in idx:
                d = [((w @ v.co) - hand).length for v in m.vertices]; idx[o.name] = (max(range(len(d)), key=lambda k: d[k]),)
            pts += [w @ v.co for v in m.vertices]; e.to_mesh_clear()
        far = max(pts, key=lambda p: (p - hand).length)
        axis = (far - hand).normalized(); pom = min(pts, key=lambda p: (p - hand).dot(axis))
        hp = rig.matrix_world @ rig.pose.bones['Hips'].head; la = rig.matrix_world @ rig.pose.bones['LeftArm'].head; le = rig.matrix_world @ rig.pose.bones['LeftForeArm'].head
        out.append({'f': i, 'tipZ': round(far.z, 4), 'tipY': round(far.y, 4), 'pomY_minus_hipY': round(pom.y - hp.y, 4), 'pomZ': round(pom.z, 4), 'hipZ': round(hp.z, 4), 'hipX': round(hp.x, 4),
                    'leftUpperArmElevDeg': round(math.degrees(math.asin(max(-1, min(1, (le - la).normalized().z)))), 1)})
    return out


def armpit_close(label, frames30=(0, 30, 38, 44), res=600, scale=.38):
    """Close renders of the drinking-side armpit (front, side, back-diagonal) at given 30 fps frames. Never saves."""
    s = bpy.context.scene; cam = s.camera; rig = bpy.data.objects['Knight_Deform']; fps = s.render.fps
    folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_attachment') or o.get('review_prop'): o.color = (.7, .32, .06, 1)
    views = {'front': Vector((0, -1, .1)), 'side': Vector((1, 0, .05)), 'frontside': Vector((.7, -.7, .15))}
    out = []
    for i in frames30:
        fr = i * fps / 30.; s.frame_set(int(fr), subframe=fr - int(fr)); ctr = rig.matrix_world @ rig.pose.bones['LeftArm'].head + Vector((0, 0, -.05))
        for v, d in views.items():
            d = d.normalized(); cam.location = ctr + d * 5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = scale
            s.render.filepath = str(folder / f'armpit-{v}-{i:04d}.png'); bpy.ops.render.render(write_still=True); out.append(s.render.filepath)
    return {'folder': str(folder), 'n': len(out)}



# ---------------------------------------------------------------------- Heal v5 ----
HEAL5 = dict(
    end_ease=.20,                                  # last 0.2 s re-timed to arrive with zero velocity (last 4+ frames eased)
    inhale=[(0, 0), (.30, 0), (.55, .55), (.85, 1.), (1.15, .9), (1.6, .6), (1.95, 0.), (2.4, 0)],
    exhale=[(0, 0), (1.85, 0), (2.08, 1.), (2.26, .25), (2.4, 0)],
    chest_in=-3.0, shoulder_in=2.4, hips_in=.004, chest_ex=1.6, shoulder_ex=-1.6, hips_ex=-.004,
    shift_amp=-.018,                               # added on top of v4's -.018 -> doubled weight shift
    give=[(0, 0), (1.55, 0), (1.85, -.013), (2.12, -.004), (2.4, 0)],   # knee give timed to the cup lowering
    give_roll=0.0,
    sag=[(0, 0), (.45, .45), (1.2, 1.), (1.9, .7), (2.4, 0)], sag_shoulder=4.5,   # sword sags with a dropped clavicle only
    pole_drop=[(0, 0), (.45, 0), (.85, 1.), (1.55, 1.), (1.95, 0), (2.4, 0)], pole_off=(-.03, -.03, -.11), clav_up=-7.0,
)
RIGHT_CHAIN = ('RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')


def heal_tau(t):
    D = 2.4; e = HEAL5['end_ease']; t0 = D - e
    if t <= t0: return t
    u = (t - t0) / e; return t0 + e * (u + u * u - u ** 3)


def heal_v5(step=.02):
    s = bpy.context.scene; H = HEAL5; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heal'
    fps = s.render.fps; dur = s['duration']; fk = bpy.data.objects['Pose_Control_Rig']; tg = bpy.data.objects['LeftArm_Target']; pl = bpy.data.objects['LeftArm_Pole']
    n = round(dur / step); times = [min(dur, i * step) for i in range(n + 1)]
    src = {}; c.at(0); I = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    for t in sorted(set(times + [heal_tau(t) for t in times])):
        c.at(t * fps); src[round(t, 6)] = ({b.name: b.matrix_basis.copy() for b in fk.pose.bones}, tg.matrix_world.copy(), pl.matrix_world.copy())
    fk.animation_data_clear(); tg.animation_data_clear(); pl.animation_data_clear(); prev = {}
    env = lambda t: math.sin(math.pi * min(max(t / dur, 0.), 1.)) ** 2
    for t in times:
        tau = heal_tau(t); fkb, tgm, plm = src[round(tau, 6)]
        for b in fk.pose.bones:
            b.matrix_basis = I[b.name] if b.name in RIGHT_CHAIN else fkb[b.name]  # sword arm: idle pose + sag only
        ins = pchip(H['inhale'], tau); exs = pchip(H['exhale'], tau); gv = pchip(H['give'], tau)
        dx = H['shift_amp'] * env(tau); dz = H['hips_in'] * ins + H['hips_ex'] * exs + gv
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((dx, 0, dz))
        bpy.context.view_layer.update()
        wr(fk, 'Hips', 'Y', H['give_roll'] * gv / .013)
        ch = H['chest_in'] * ins + H['chest_ex'] * exs; wr(fk, 'Spine1', 'X', .5 * ch); wr(fk, 'Spine2', 'X', .5 * ch)
        sh = H['shoulder_in'] * ins + H['shoulder_ex'] * exs; wr(fk, 'LeftShoulder', 'Y', sh); wr(fk, 'RightShoulder', 'Y', -sh)
        wr(fk, 'LeftShoulder', 'Y', -H['clav_up'] * pchip(H['pole_drop'], tau))  # drinking clavicle lifts with the cup (pauldron covers the armpit)
        wr(fk, 'RightShoulder', 'Y', H['sag_shoulder'] * pchip(H['sag'], tau))
        if H.get('tip_corr'): wr(fk, 'RightHand', 'X', pchip(H['tip_corr'], tau))  # keeps the blade from rising: sag only
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        tg.matrix_basis = tgm; c.key(tg, t * fps, prev)
        pd = pchip(H['pole_drop'], tau); pl.location = plm.translation + Vector(H['pole_off']) * pd; pl.keyframe_insert('location', frame=t * fps)
    for o in (fk, tg, pl): c.smooth(o)
    s['heal_v5'] = json.dumps(H); c.at(0)
    return {'keys': len(times)}


def heal_iterate(passes=3, sag_mm=6.):
    """Solve a wrist correction so the blade tip never rises above the idle start and sags ~sag_mm mid-drink."""
    HEAL5['tip_corr'] = None; hist = []; gain = None
    for k in range(passes):
        open_src(cm.REPO / 'Local/Blender/feedback-v4-20261021/heal_Blender_v1.blend'); heal_v5(); bake_only('heal_v5')
        rows = sword_probe(); z0 = rows[0]['tipZ']
        want = {r['f']: z0 - sag_mm / 1000. * pchip(HEAL5['sag'], heal_tau(r['f'] / 30.)) for r in rows}
        err = {r['f']: r['tipZ'] - want[r['f']] for r in rows}
        hist.append({'pass': k, 'maxRiseMM': round(1000 * max(r['tipZ'] - z0 for r in rows), 1), 'maxErrMM': round(1000 * max(abs(v) for v in err.values()), 1),
                     'pomBehindMaxMM': round(1000 * max(r['pomY_minus_hipY'] for r in rows), 1)})
        if k == passes - 1: break
        if gain is None: gain = 57.3 / 1.0  # deg per metre at ~1 m lever; sign learned below
        old = dict(HEAL5['tip_corr'] or [])
        pts = []
        for r in rows[::2]:
            tt = r['f'] / 30.; base = pchip(HEAL5['tip_corr'], tt) if HEAL5['tip_corr'] else 0.
            pts.append((tt, base + gain * err[r['f']]))
        pts[0] = (0., 0.); pts[-1] = (2.4, 0.); HEAL5['tip_corr'] = pts
        if k == 0:
            open_src(cm.REPO / 'Local/Blender/feedback-v4-20261021/heal_Blender_v1.blend'); heal_v5(); bake_only('heal_v5')
            r2 = sword_probe(); e2 = max(abs(r['tipZ'] - want[r['f']]) for r in r2)
            if e2 > max(abs(v) for v in err.values()): gain = -gain; HEAL5['tip_corr'] = [(a, -b) for a, b in pts]
    return {'history': hist, 'gainSign': 1 if gain and gain > 0 else -1}


def grip_close(label, frames30=(0, 18), res=600, scale=.30):
    """Close renders of both hands on the hilt (front, side, below) at 30 fps frames. Never saves."""
    s = bpy.context.scene; cam = s.camera; rig = bpy.data.objects['Knight_Deform']; fps = s.render.fps
    folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_attachment') or o.get('review_prop'): o.color = (.7, .32, .06, 1)
    views = {'front': Vector((0, -1, .15)), 'side': Vector((1, 0, .1)), 'outer': Vector((-1, -.4, .3)), 'top': Vector((0, -.3, 1))}
    out = []
    for i in frames30:
        fr = i * fps / 30.; s.frame_set(int(fr), subframe=fr - int(fr))
        ctr = .5 * ((rig.matrix_world @ rig.pose.bones['LeftHand'].head) + (rig.matrix_world @ rig.pose.bones['RightHand'].head))
        for v, d in views.items():
            d = d.normalized(); cam.location = ctr + d * 5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = scale
            s.render.filepath = str(folder / f'grip-{v}-{i:04d}.png'); bpy.ops.render.render(write_still=True); out.append(s.render.filepath)
    return {'folder': str(folder), 'n': len(out)}


# ------------------------------------------------------------------ WalkTwoHand v6 ----
W6 = dict(hs_pitch=-24., to_pitch=42., breath=[1.8, 2.4, 5.5], hilt_breath=.009, grip_open=.16)
FINGER_PREFIX = tuple(sd + 'Hand' + n for sd in ('Left', 'Right') for n in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'))


def _relax_fingers(fk, k):
    """Open each finger segment by fraction k toward its parent direction (wrap the handle instead of a folded fist)."""
    if k <= 0: return
    for b in fk.pose.bones:
        if b.name.startswith(FINGER_PREFIX) and b.parent:
            pd = (b.parent.tail - b.parent.head).normalized(); bd = (b.tail - b.head).normalized(); ax = pd.cross(bd)
            if ax.length > 1e-4:
                ang = pd.angle(bd) * k * (.5 if 'Thumb' in b.name else 1.)
                m = b.matrix.copy(); b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(-ang, 4, ax.normalized()) @ m.to_3x3().to_4x4()
                bpy.context.view_layer.update()


def walk_two_v6():
    """Rebuild the approved v5r2 two-hand walk with its own recipe (walk_v4.py, read as a library, its v5r2 TUNE taken
    from the approved scene) plus stronger heel strike/peel, deeper breathing and a wrapping (less folded) grip."""
    sp = importlib.util.spec_from_file_location('veyr_walk_lib', HERE / 'walk_v4.py'); W = importlib.util.module_from_spec(sp); W.VEYR_V4_PARAMS = globals().get('VEYR_V4_PARAMS'); sp.loader.exec_module(W)
    W.c.OUT = cm.check_writable(P['out'] / 'walk_two_v6')  # never the v5r2 folder
    src = cm.REPO / 'Local/Blender/feedback-v4-20261021/walk_v5r2/walk_two_Blender_v1.blend'; open_src(src)
    tune = json.loads(bpy.context.scene['walk_v5_tune']); W.TUNE.clear(); W.TUNE.update(tune)
    for k in ('hs_pitch', 'to_pitch', 'breath', 'hilt_breath'): W.TUNE[k] = W6[k]
    orig = W.pose_body
    def pose_body6(fk, base, t):
        orig(fk, base, t); _relax_fingers(fk, W6['grip_open'])
    W.pose_body = pose_body6
    W.REVIEW = 'WalkTwoHand_Blender_v6'
    a = W.setup(); b = W.author()
    s = bpy.context.scene; s['walk_v6'] = json.dumps({'base': 'v5r2 TUNE', 'changes': W6}); s['review_name'] = 'WalkTwoHand_Blender_v6'
    return {'reach': b['maxLegReach'], 'speed': b['speed'], 'tune': {k: W.TUNE[k] for k in ('hs_pitch', 'to_pitch', 'breath', 'hilt_breath', 'lean')}}


# ----------------------------------------------------------- Backpedal loop v1 ----
# Seamless in-place loop of the owner-preferred upright walk-back (r5 quality): idle height and posture,
# toe-first landings rolling to the heel, the heel last to leave, one foot always down, arms in the idle
# pose with a small float, head level. Cycle 1.2 s (2 steps), same cadence as the approved one-hand walk.
BL = dict(T=1.2, contact={'Right': 0., 'Left': .6}, stance=.70, step=.15, x=None,
          land=11., roll_in=.12, toe_lift=18., lift_start=.50, lift=.030,
          hip_dz=-.018, dip=-.010, dip_lag=.06, rise=.003, sway=.011, yaw=4.5, chest=-.5, roll=1.6,
          sword_float=.9, tip_float=-1.0, free_swing=2.5, breath=.7)


def _foot_from_idle(side):
    d = json.loads((P['out'] / 'idle_feet.json').read_text())[side]
    Ri = Matrix(d['R']).to_4x4(); w = [Ri @ Vector(q) for q in d['local']]; zmin = min(p.z for p in w)
    low = [p for p in w if p.z < zmin + .010]
    cont = [p for p in w if p.z < zmin + .006]
    heel = Vector((sum(p.x for p in low) / len(low), max(p.y for p in cont), zmin))
    toe = Vector((heel.x, min(p.y for p in cont), zmin))
    tj = Vector(d['toeJoint']); ball = Vector((heel.x, max(toe.y, tj.y), zmin))
    FOOT[side] = {'R0': Ri, 'heel': heel, 'ball': ball, 'toe': toe, 'tj': tj, 'rel_toe': Matrix(d['relToe']),
                  'low': sorted([Vector(q) for q in d['local']], key=lambda q: (Ri @ q).z)[:260] + [Vector(q) for q in d['local']][::6]}


def _roll_contact(side, M, clamp_only=False, heel_side_of_ball=False):
    """Rolling contact: shift the foot so its lowest sole point touches z=0 (stance) or is never below it (swing).
    heel_side_of_ball: ignore the toes (they are counter-rotated flat onto the floor separately)."""
    F = FOOT[side]; pts = F['low']
    if heel_side_of_ball: pts = [q for q in pts if (F['R0'] @ q).y >= F['ball'].y - .002]
    zmin = min((M @ q).z for q in pts)
    if clamp_only and zmin >= 0: return M
    return Matrix.Translation(Vector((0, 0, -zmin))) @ M


def _blflat(side, ay):
    F = FOOT[side]; return Matrix.Translation(Vector((BL['x'][side], ay, -F['heel'].z))) @ F['R0']


def bl_foot(side, t):
    """Backward gait (in place): the stance foot slides forward (-y) under the body at ground speed v;
    contact at the rear on the ball (heel up), heel rolls down, flat, toes lift with the heel pivot, heel leaves last."""
    B = BL; T = B['T']; st = B['stance']; v = 2 * B['step'] / T; u = (t - B['contact'][side]) % T; y0 = v * st / 2
    def stance(uu):
        ay = y0 - v * uu; M = _blflat(side, ay)
        if uu < B['roll_in']:
            p = -B['land'] * (1 - smooth01(uu / B['roll_in'])); return _roll_contact(side, _pivot(M, side, 'ball', p), heel_side_of_ball=True), .8 * p
        if uu > B['lift_start']:
            k = (uu - B['lift_start']) / (st - B['lift_start']); return _roll_contact(side, _pivot(M, side, 'heel', B['toe_lift'] * k ** 1.5)), 0.
        return M, 0.
    if u < st: return stance(u)
    s = (u - st) / (T - st); dur = T - st
    A, _ = stance(st); Bm, toeB = stance(0.)
    pa = B['toe_lift']; pb = -B['land']
    ya, yb = A.translation.y, Bm.translation.y; za, zb = A.translation.z, Bm.translation.z
    y = hermite(ya, yb, -v, -v, s, dur); z = za + (zb - za) * smooth01(s) + B['lift'] * math.sin(math.pi * s) ** 1.4
    pitch = pa + (pb - pa) * smoother01(s) - 3. * math.sin(math.pi * s)
    M = Matrix.Translation(Vector((B['x'][side], y, z))) @ Matrix.Rotation(math.radians(-pitch), 4, 'X') @ FOOT[side]['R0']
    return _roll_contact(side, M, clamp_only=True), toeB * smooth01((s - .65) / .35)


def backloop_v1(step=.02):
    s = bpy.context.scene; B = BL; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'backpedal'
    T = B['T']; fk = bpy.data.objects['Pose_Control_Rig']; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}; world = {b.name: b.matrix.copy() for b in fk.pose.bones}
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    B['x'] = {sd: world[sd + 'Foot'].translation.x for sd in ('Left', 'Right')}  # idle stance width (r5)
    end = round(T * 150); s['duration'] = T; s.frame_start = 0; s.frame_end = end; s.render.fps = 150; s.render.fps_base = 1; fps = 150
    hilt = bpy.data.objects['Hilt_Control']
    if hilt.animation_data and hilt.animation_data.action:
        for fc in c.curves(hilt.animation_data.action):
            kp = sorted(fc.keyframe_points, key=lambda k: k.co.x)
            if len(kp) >= 2 and all(abs(k.co.y - kp[0].co.y) < 1e-9 for k in kp):
                d = end - kp[-1].co.x; kp[-1].co.x += d; kp[-1].handle_left.x += d; kp[-1].handle_right.x += d
    fk.animation_data_clear(); tg = {}; pl = {}; polebase = {}
    for sd in ('Left', 'Right'):
        tg[sd] = bpy.data.objects[sd + 'Leg_Target']; pl[sd] = bpy.data.objects[sd + 'Leg_Pole']
        for o in (tg[sd], pl[sd]): f.reset_animation(o)
        a, mid, e = [world[sd + n].translation for n in ('UpLeg', 'Leg', 'Foot')]; ax = (e - a).normalized(); dd = mid - a - ax * (mid - a).dot(ax)
        polebase[sd] = mid + dd.normalized() * .3
    L = {sd: (world[sd + 'Leg'].translation - world[sd + 'UpLeg'].translation).length + (world[sd + 'Foot'].translation - world[sd + 'Leg'].translation).length for sd in tg}
    w = math.tau / T; prev = {}; reach = {'Left': 0., 'Right': 0.}
    n = round(T / step); times = [min(T, i * step) for i in range(n + 1)]
    def stepsig(t):  # +1 while the right foot travels back (right swing), -1 for the left
        return math.sin(w * (t - B['contact']['Right'] - B['stance'] - (T - B['stance']) / 2 + T / 4))
    for t in times:
        fr = t * fps
        for b in fk.pose.bones: b.matrix_basis = base[b.name]
        def bobf(tt):
            tt = tt % T; bb = 0.
            for sd in ('Left', 'Right'):
                for k in (-1, 0, 1):
                    cc = B['contact'][sd] + k * T; bb += B['dip'] * math.exp(-((tt - cc - B['dip_lag']) / .09) ** 2)
                    mid = cc + B['stance'] + (T - B['stance']) / 2; bb += B['rise'] * math.exp(-((tt - mid) / .1) ** 2)
            return bb
        bob = bobf(t)
        sway = B['sway'] * math.cos(w * (t - B['contact']['Right'] - B['stance'] / 2)) * -1  # over the stance foot
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((sway, 0, B['hip_dz'] + bob))
        bpy.context.view_layer.update()
        ss = stepsig(t)
        wr(fk, 'Hips', 'Z', -B['yaw'] * ss); wr(fk, 'Hips', 'Y', -B['roll'] * ss)
        wr(fk, 'Spine', 'Z', .5 * (B['chest'] * -B['yaw'] * ss + B['yaw'] * ss)); wr(fk, 'Spine2', 'Z', .5 * (B['chest'] * -B['yaw'] * ss + B['yaw'] * ss))
        wr(fk, 'Spine', 'Y', .5 * B['roll'] * ss)
        br = math.sin(2 * w * t); wr(fk, 'Spine1', 'X', -.5 * B['breath'] * br); wr(fk, 'Spine2', 'X', -.5 * B['breath'] * br)
        hd = -(B['chest'] * -B['yaw'] * ss); wr(fk, 'Neck', 'Z', .4 * -(-B['yaw'] * ss + hd)); wr(fk, 'Head', 'Z', .6 * -(-B['yaw'] * ss + hd))
        bn = bob / abs(B['dip']); wr(fk, 'Head', 'X', -.3 * bn)
        wr(fk, 'RightArm', 'X', .25 * math.sin(w * 2 * (t - .09)) * 0 + .3 * bn); wr(fk, 'RightForeArm', 'X', B['sword_float'] * bn); wr(fk, 'RightHand', 'X', B['tip_float'] * bn)
        wr(fk, 'LeftArm', 'X', B['free_swing'] * math.sin(w * (t - .1))); wr(fk, 'LeftForeArm', 'X', .6 * B['free_swing'] * math.sin(w * (t - .17)))
        if B.get('abd1'): wr(fk, 'LeftArm', 'Y', B['abd1'] * math.sin(w * (t - .1)))  # cancels the swing's one-sided inward drift (mirror steps)
        if B.get('sword_bob'):  # greatsword bob trails the body bob
            bl = bobf(t - B['sword_bob_lag']) / abs(B['dip']); wr(fk, 'RightHand', 'X', B['sword_bob'] * bl); wr(fk, 'RightForeArm', 'X', .4 * B['sword_bob'] * bobf(t - .5 * B['sword_bob_lag']) / abs(B['dip']))
        if B.get('chest_sway'):  # chest shifts over the stance foot with the pelvis on both steps (side lean of the upper spine)
            sw = math.cos(w * (t - B['contact']['Right'] - B['stance'] / 2)) * -1; wr(fk, 'Spine1', 'Y', B['chest_sway'] * sw); wr(fk, 'Spine2', 'Y', B['chest_sway'] * sw)
        if B.get('clav'):  # shoulders swing fore/aft with the chest turn (visible width change)
            cs = B['clav'] * ss; wr(fk, 'LeftShoulder', 'Z', cs); wr(fk, 'RightShoulder', 'Z', cs); wr(fk, 'LeftShoulder', 'Y', .5 * cs); wr(fk, 'RightShoulder', 'Y', .5 * cs)
        if B.get('clav2'):  # shoulder line narrows at the chest-turn extremes and opens at the passing pose (2x step rate)
            nn = ss * ss - .5; wr(fk, 'LeftShoulder', 'Y', B['clav2'] * nn); wr(fk, 'RightShoulder', 'Y', -B['clav2'] * nn)
            wr(fk, 'LeftArm', 'Y', B.get('abd2', 0.) * nn); wr(fk, 'RightArm', 'Y', -B.get('abd2r', 0.) * nn)
        for b in fk.pose.bones:
            if b.name.endswith('ToeBase'): pass
        for sd in ('Left', 'Right'):
            M, toe = bl_foot(sd, t); tg[sd].matrix_basis = M; c.key(tg[sd], fr, prev)
            F = FOOT[sd]; foot = fk.pose.bones[sd + 'Foot']; toeb = fk.pose.bones[sd + 'ToeBase']
            axis = (F['R0'].to_3x3().inverted() @ Vector((1, 0, 0))).normalized(); rel = F['rel_toe']
            toeb.matrix = foot.matrix @ (Matrix.Translation(rel.translation) @ Matrix.Rotation(math.radians(toe), 4, axis) @ rel.to_3x3().to_4x4()); bpy.context.view_layer.update()
            off = M.translation - world[sd + 'Foot'].translation
            pl[sd].location = polebase[sd] + Vector((.5 * sway, .5 * off.y, .5 * bob)); pl[sd].keyframe_insert('location', frame=fr)
            reach[sd] = max(reach[sd], (fk.pose.bones[sd + 'UpLeg'].head - M.translation).length / L[sd])
        for b in fk.pose.bones: c.key(b, fr, prev)
    for o in (fk, *tg.values(), *pl.values()): c.smooth(o)
    s['rebuild_job'] = 'backpedal'; s['root_motion'] = 'in place (loop); backward speed %.4f rig units/s' % (2 * B['step'] / T)
    s['backloop_v1'] = json.dumps({k: v for k, v in B.items()}); c.at(0)
    return {'keys': len(times), 'reach': reach, 'speed': 2 * B['step'] / T}


# ------------------------------------------------------- GuardReadyTwoHand v4r3 (critic) ----
GUARD_R3 = dict(
    # snap capped ~20 deg/frame: f5 +15, f6 +20, f7 +20, f8 +19; overshoot/rebound kept; hold frozen from 0.4 s
    v=[(0, 0), (.035, 0), (.133, -.12), (.167, .11), (.20, .41), (.233, .71), (.265, 1.0), (.291, 1.065), (.323, .988), (.36, 1.007), (.385, .999), (.40, 1.0), (.70, 1.0)],
    # settle: impact at f9 then ONE monotone ease back over f9-f12 (no key at f10)
    hips=[(0, 0), (.035, 0), (.135, -.02), (.22, -.004), (.30, -.032), (.40, -.015), (.70, -.015)],
    chest=[(0, 0), (.035, 0), (.135, 2.4), (.22, -2.0), (.30, 3.8), (.40, 0), (.70, 0)],
    head=[(0, 0), (.035, 0), (.135, 1.4), (.23, -1.5), (.30, 7.0), (.40, 0), (.70, 0)],
    shrug=[(0, 0), (.035, 0), (.135, -1.2), (.24, 2.5), (.295, 6.0), (.40, 0), (.70, 0)],
)


def guard_v4r3():
    GUARD.update(GUARD_R3); return guard_v4()


def hilt_angles():
    """Per 30 fps frame: blade direction angle change (deg/frame) and helmet-top height (mm)."""
    s = bpy.context.scene; fps = s.render.fps; sock = bpy.data.objects['ReviewWeaponSocket']; rig = bpy.data.objects['Knight_Deform']; out = []; prev = None
    body = body_obj()
    for i in range(int(s.frame_end / (fps / 30.) + 1e-6) + 1):
        fr = i * fps / 30.; s.frame_set(int(fr), subframe=fr - int(fr)); d = (sock.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
        hd = rig.matrix_world @ rig.pose.bones['Head'].tail
        out.append({'f': i, 'step': round(math.degrees(prev.angle(d)), 1) if prev else 0., 'headTopZmm': round(hd.z * 1000, 1), 'hipZmm': round((rig.matrix_world @ rig.pose.bones['Hips'].head).z * 1000, 1)}); prev = d
    return out


# ---------------------------------------------------------- RunStart / RunStop v1 ----
RUNSRC = cm.REPO / 'Local/Blender/feedback-v4-20261021/meshy_r3/run_Blender_v1.blend'   # matched sprint: RunOneHand_Blender_meshy_r3
OBJS = ('Hilt_Control', 'LeftLeg_Target', 'RightLeg_Target', 'LeftLeg_Pole', 'RightLeg_Pole', 'RightArm_Pole')


def idle_controls():
    """Approved one-hand idle frame 0 (r5 scene start = idle): FK basis and control world matrices -> JSON."""
    open_src(cm.REPO / 'Local/Blender/feedback-v4-20261021/backpedal-round5/backpedal_Blender_v1.blend'); c.at(0)
    fk = bpy.data.objects['Pose_Control_Rig']
    d = {'fk': {b.name: [list(r) for r in b.matrix_basis] for b in fk.pose.bones}, 'obj': {n: [list(r) for r in bpy.data.objects[n].matrix_world] for n in OBJS}}
    (P['out'] / 'idle_controls.json').write_text(json.dumps(d)); return {'bones': len(d['fk'])}


def _mblend(a, b, k):
    k = min(1., max(0., k))
    la, ra, sa = a.decompose(); lb, rb, sb = b.decompose()
    if ra.dot(rb) < 0: rb = -rb
    return Matrix.LocRotScale(la.lerp(lb, k), ra.slerp(rb, k), sa.lerp(sb, k))


RUN_T = dict(start=dict(dur=.5, phi0=.35, body=(0., .45), lean=[(0, 0), (.06, 0), (.22, 7.), (.40, 3.), (.5, 0)], dip=[(0, 0), (.08, -.018), (.2, -.008), (.5, 0)],
                         Right=(.35, .50), Left=(.37, .60)),
             stop=dict(dur=.6, body=(.12, .55), lean=[(0, 0), (.12, -3.), (.27, -7.), (.40, 2.5), (.50, -.6), (.6, 0)], dip=[(0, 0), (.15, -.006), (.30, -.024), (.42, -.006), (.5, .003), (.6, 0)],
                        Right=(.13, .28), Left_adjust=(.45, .58), adjust_lift=.016))


def run_transition(kind='start', step=.01):
    s0 = open_src(RUNSRC); s = bpy.context.scene; fps = s.render.fps; per = s['duration']; R = RUN_T[kind]
    fk = bpy.data.objects['Pose_Control_Rig']; obj = {n: bpy.data.objects[n] for n in OBJS}
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    idle = json.loads((P['out'] / 'idle_controls.json').read_text()); IF = {k: Matrix(v) for k, v in idle['fk'].items()}; IO = {k: Matrix(v) for k, v in idle['obj'].items()}
    nf = round(per * fps); run = []
    for fr in range(nf + 1):
        c.at(fr); run.append(({b.name: b.matrix_basis.copy() for b in fk.pose.bones}, {n: o.matrix_world.copy() for n, o in obj.items()}))
    def runat(phi):
        x = (phi % per) * fps; i = int(x); k = x - i; j = min(i + 1, nf); a, b = run[min(i, nf)], run[j]
        return {n: _mblend(a[0][n], b[0][n], k) for n in a[0]}, {n: _mblend(a[1][n], b[1][n], k) for n in a[1]}
    D = R['dur']
    if kind == 'start':
        phi = lambda t: R['phi0'] + t * t / (2 * D)                       # run speed ramps linearly 0 -> 1
        tw = lambda win: (math.sqrt(max(0., win[0] - R['phi0']) * 2 * D), math.sqrt(max(0., win[1] - R['phi0']) * 2 * D))
        wfoot = {sd: (lambda t, a=tw(R[sd]): smoother01((t - a[0]) / max(1e-6, a[1] - a[0]))) for sd in ('Left', 'Right')}
        if R.get('right_plant'): wfoot['Right'] = lambda t, a=R['right_plant']: smoother01((t - a['lift']) / (a['land'] - a['lift']))
        if R.get('left_time'): wfoot['Left'] = lambda t, a=R['left_time']: smoother01((t - a[0]) / (a[1] - a[0]))  # push leg stays down until late
        if R.get('body_easeout'): wbody = lambda t: 1 - (1 - min(1., max(0., t / R['body'][1]))) ** 2.2  # weight shift starts at once, arrives with zero slope
        else: wbody = lambda t: smoother01((t - R['body'][0]) / (R['body'][1] - R['body'][0]))
        speed = lambda t: t / D
    else:
        tb = .42; phi = lambda t: (t - t ** 3 / (3 * tb * tb)) if t < tb else (tb - tb / 3)   # brake: run speed 1 -> 0 by 0.42 s
        speed = lambda t: max(0., 1 - (t / tb) ** 2)
        wbody = lambda t: 1 - smoother01((t - R['body'][0]) / (R['body'][1] - R['body'][0]))
        wr_ = lambda t: 1 - smoother01((t - R['Right'][0]) / (R['Right'][1] - R['Right'][0]) * (R['Right'][1] - R['Right'][0]) / (.42 - R['Right'][0]))
        wfoot = {'Right': wr_, 'Left': lambda t: 1.}
    end = round(D * fps); s['duration'] = D; s.frame_start = 0; s.frame_end = end; s['rebuild_job'] = 'run'
    for o in (fk, *obj.values()): o.animation_data_clear()
    prev = {}; times = [round(i * step, 6) for i in range(round(D / step) + 1)]
    lfinal = None
    for t in times:
        rf, ro = runat(phi(t)); wb = wbody(t)
        for b in fk.pose.bones: b.matrix_basis = _mblend(IF[b.name], rf[b.name], wb)
        for sd in ('Left', 'Right'):  # toes follow their own foot's blend, so a planted idle foot keeps flat idle toes
            if kind == 'start': kf = wfoot[sd](t)
            else: kf = wfoot['Right'](t) if sd == 'Right' else (1. if t < R['Left_adjust'][0] else 1 - smoother01((t - R['Left_adjust'][0]) / (R['Left_adjust'][1] - R['Left_adjust'][0])))
            fk.pose.bones[sd + 'ToeBase'].matrix_basis = _mblend(IF[sd + 'ToeBase'], rf[sd + 'ToeBase'], kf)
        dz = pchip(R['dip'], t); hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((0, 0, dz))
        bpy.context.view_layer.update()
        ln = pchip(R['lean'], t); wr(fk, 'Spine', 'X', .5 * ln); wr(fk, 'Spine1', 'X', .5 * ln); wr(fk, 'Head', 'X', -.5 * ln)
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        for n in ('Hilt_Control', 'LeftLeg_Pole', 'RightLeg_Pole', 'RightArm_Pole'):
            obj[n].matrix_basis = _mblend(IO[n], ro[n], wb); c.key(obj[n], t * fps, prev)
        for sd in ('Left', 'Right'):
            n = sd + 'Leg_Target'
            if kind == 'stop' and sd == 'Left':
                if lfinal is None and phi(t) >= .26: lfinal = ro[n].copy()
                M = ro[n] if lfinal is None else lfinal                       # left plants (brake step) and stays
                g = smoother01((phi(t) - .19) / .07)                            # the source run floats this contact ~5 cm: bring the sole onto the floor
                if g > 0:
                    Mc = _roll_contact(sd, M); M = _mblend(M, Mc, g)
                a0, a1 = R['Left_adjust']
                if t > a0:  # small settle step into the idle stance
                    k = smoother01((t - a0) / (a1 - a0)); M = _mblend(M, IO[n], k); M = Matrix.Translation(Vector((0, 0, R['adjust_lift'] * math.sin(math.pi * k) ** 2))) @ M
            elif kind == 'start' and sd == 'Right' and R.get('right_plant'):
                M = _rs_right_plant(t, R, IO[n], runat, phi)
            else:
                k = wfoot[sd](t); M = _mblend(IO[n], ro[n], k)
                lift = .03 * math.sin(math.pi * k) ** 2 if (kind == 'start' and sd == 'Right') or (kind == 'stop' and sd == 'Right') else 0.
                M = Matrix.Translation(Vector((0, 0, lift))) @ M
            M = _roll_contact(sd, M, clamp_only=True); obj[n].matrix_basis = M; c.key(obj[n], t * fps, prev)
    for o in (fk, *obj.values()): c.smooth(o)
    s['run_transition'] = json.dumps({'kind': kind, 'matched': 'RunOneHand_Blender_meshy_r3 (frame 0, bat carry)', 'params': {k: v for k, v in R.items()}})
    c.at(0)
    return {'kind': kind, 'dur': D, 'phiEnd': phi(D), 'speedProfile': [round(speed(t), 3) for t in times[::5]]}


def walk_two_v6r2():
    """v6 with the critic's r2: heel strike 20 deg (24 read as a march) rolling to flat over 4 frames; rest unchanged."""
    W6.update(hs_pitch=-20.)
    sp = importlib.util.spec_from_file_location('veyr_walk_lib', HERE / 'walk_v4.py'); W = importlib.util.module_from_spec(sp); W.VEYR_V4_PARAMS = globals().get('VEYR_V4_PARAMS'); sp.loader.exec_module(W)
    W.c.OUT = cm.check_writable(P['out'] / 'walk_two_v6r2')
    open_src(cm.REPO / 'Local/Blender/feedback-v4-20261021/walk_v5r2/walk_two_Blender_v1.blend')
    tune = json.loads(bpy.context.scene['walk_v5_tune']); W.TUNE.clear(); W.TUNE.update(tune)
    for k in ('hs_pitch', 'to_pitch', 'breath', 'hilt_breath'): W.TUNE[k] = W6[k]
    W.TUNE['heel_end'] = round(4 / 30 / W.T, 4)  # heel roll to flat over 4 frames at 30 fps
    orig = W.pose_body
    def pose_body6(fk, base, t):
        orig(fk, base, t); _relax_fingers(fk, W6['grip_open'])
    W.pose_body = pose_body6; W.REVIEW = 'WalkTwoHand_Blender_v6r2'
    W.setup(); b = W.author(); s = bpy.context.scene; s['walk_v6r2'] = json.dumps({'base': 'v5r2 TUNE', 'changes': W6, 'heel_end': W.TUNE['heel_end']}); s['review_name'] = 'WalkTwoHand_Blender_v6r2'
    return {'reach': b['maxLegReach'], 'tune': {k: W.TUNE[k] for k in ('hs_pitch', 'to_pitch', 'heel_end', 'breath')}}


def stagger_v2r2():
    """Critic r2: recovery spread over f6-f11 (gentler ease), head and blade arriving last, softer f4-5 second lurch,
    1.5 cm hip drop on the impact."""
    STAG.update(b_mix=.55, home_start=.20, home=.345, home_soft=True, lag_head=.065, lag_neck=.035, lag_hand=.07, lag_fore=.045, impact_dip=-.015, absorb=.16)
    return stagger_v2()


def motion_profile(names=('Hips', 'Head', 'RightHand', 'LeftHand')):
    """Per 30 fps frame: summed key-joint displacement (mm/frame) and head height (mm)."""
    s = bpy.context.scene; fps = s.render.fps; rig = bpy.data.objects['Knight_Deform']; out = []; prev = None
    for i in range(int(s.frame_end / (fps / 30.) + 1e-6) + 1):
        fr = i * fps / 30.; s.frame_set(int(fr), subframe=fr - int(fr)); cur = {n: (rig.matrix_world @ rig.pose.bones[n].head).copy() for n in names}
        out.append({'f': i, 'mm': round(1000 * sum((cur[n] - prev[n]).length for n in names), 1) if prev else 0., 'headZ': round(1000 * cur['Head'].z, 1), 'hipZ': round(1000 * cur['Hips'].z, 1)}); prev = cur
    return out


def part_ground(t0=1.0, t1=2.4, step_s=.0667, groups=('LeftLeg', 'RightLeg', 'LeftUpLeg', 'RightUpLeg', 'LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase', 'Hips', 'Spine', 'Head')):
    """Per sample: min z (mm) of vertices dominated (>0.5) by each bone group (exact name)."""
    s = bpy.context.scene; body = body_obj(); fps = s.render.fps; gid = {g.index: g.name for g in body.vertex_groups}
    dom = {}
    for v in body.data.vertices:
        if v.groups:
            gmax = max(v.groups, key=lambda gg: gg.weight)
            if gmax.weight > .5 and gid.get(gmax.group) in groups: dom.setdefault(gid[gmax.group], []).append(v.index)
    out = []; t = t0
    while t <= t1 + 1e-6:
        fr = t * fps; s.frame_set(int(fr), subframe=fr - int(fr)); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        out.append({'t': round(t, 3), 'f30': round(t * 30), **{g: round(1000 * min((mw @ me.vertices[i].co).z for i in ids), 1) for g, ids in dom.items()}}); ev.to_mesh_clear(); t += step_s
    return out


def death_v2r2(passes=2):
    """Critic r2: arm drift merged into the main settle (motion only decreases after ~f88); hips placed so the
    kneeling (right) knee rests on the floor (target 0-1 cm), trailing shin laid on the floor, front foot planted."""
    D = DEATH; D.update(tail=(2.75, 3.55), kneel=(1.16, 1.70), trail='Right', front='Left', ankle_z=.05, settle0=9., settle1=9.5, lift=None)
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    hist = []
    for k in range(passes + 1):
        open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2r2')
        g = part_ground(t0=1.0, t1=2.6, step_s=.05)
        if k == passes: break
        pts = [(0., 0.), (.95, 0.)]
        for row in g:
            tt = row['t']; base = pchip(D['lift'], tt) if D.get('lift') else 0.
            knee = row.get('RightLeg', 999.) / 1000.
            pts.append((tt, base - (knee - .004) if 1.15 <= tt <= 1.75 else base))
        pts += [(2.75, 0.), (4.4, 0.)]; D['lift'] = pts; hist.append({'pass': k, 'rightKneeMinMM': [row.get('RightLeg') for row in g if 1.15 <= row['t'] <= 1.75]})
    return {'history': hist, 'final': g}


# ------------------------------------------------------- GuardReadyTwoHand v4r4 (critic) ----
GUARD_R4 = dict(
    # per-frame keys solved from rendered blade angles: anticipation +2,+4,+2 deg, raise bell -4.4,-10.8,-17.2,-18.2,-15.2,-9.8,-4.9,
    # then the overshoot comes back +1.3,+0.7; frozen hold from 0.4 s (audit)
    v=[(0.0, 0.0), (0.03333, -0.029), (0.06667, -0.088), (0.1, -0.1185), (0.13333, -0.0526), (0.16667, 0.1055), (0.2, 0.3491), (0.23333, 0.605), (0.26667, 0.8196), (0.3, 0.9588), (0.33333, 1.0301), (0.36667, 1.0074), (0.4, 1.0), (0.7, 1.0)],
    # settle mostly done by f11 so the motion tapers into the f12 freeze
    hips=[(0, 0), (.035, 0), (.10, -.016), (.20, -.005), (.29, -.030), (.367, -.0153), (.40, -.015), (.70, -.015)],
    chest=[(0, 0), (.035, 0), (.10, 2.2), (.20, -1.6), (.29, 3.5), (.367, .08), (.40, 0), (.70, 0)],
    head=[(0, 0), (.035, 0), (.10, 1.3), (.21, -1.2), (.29, 6.5), (.367, .15), (.40, 0), (.70, 0)],
    shrug=[(0, 0), (.035, 0), (.10, -1.0), (.22, 2.2), (.285, 6.0), (.367, 3.6), (.40, 2.2), (.435, .7), (.47, 0), (.70, 0)],
)


def guard_v4r4():
    GUARD.update(GUARD_R4); return guard_v4()


def lean_profile(scene_file=None):
    """Per 30 fps frame: torso lean (deg, Hips->Neck vs vertical, + forward/-Y), hips z (mm), lowest sole of each foot (mm)."""
    if scene_file: open_src(scene_file)
    s = bpy.context.scene; fps = s.render.fps; rig = bpy.data.objects['Knight_Deform']; body = body_obj(); gid = {g.index: g.name for g in body.vertex_groups}
    ids = {sd: [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, '').startswith((sd + 'Foot', sd + 'ToeBase'))) > .5] for sd in ('Left', 'Right')}
    out = []
    for i in range(int(s.frame_end / (fps / 30.) + 1e-6) + 1):
        fr = i * fps / 30.; s.frame_set(int(fr), subframe=fr - int(fr))
        h = rig.matrix_world @ rig.pose.bones['Hips'].head; n = rig.matrix_world @ rig.pose.bones['Neck'].head; d = n - h
        dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        soles = {sd: round(1000 * min((mw @ me.vertices[k].co).z for k in ids[sd]), 1) for sd in ids}; ev.to_mesh_clear()
        out.append({'f': i, 'lean': round(math.degrees(math.atan2(-d.y, d.z)), 1), 'hipZ': round(1000 * h.z, 1), **soles})
    return out


def run_start_r2():
    """Critic r2: weight shift from f1 (ease-out blend), lean rises monotonically (no extra hump), push leg planted until
    f13 so the only flight is the last 2 frames into the exact Meshy r3 f0 join."""
    RUN_T['start'].update(body=(0., .5), body_easeout=True, lean=[(0, 0), (.5, 0)], dip=[(0, 0), (.06, -.012), (.2, -.006), (.5, 0)], left_time=(.43, .5))
    return run_transition('start')


def run_stop_r2(step=.01, D=.6, tb=.30, v_run=1.3115):
    """Critic r2 stop: braking (left) foot planted by f4 at the idle width, both soles on the floor from f9, planted feet
    travel back exactly with the decelerating capsule (no skate), real lean-back and hip drop f9-11, exact sprint join."""
    open_src(RUNSRC); s = bpy.context.scene; fps = s.render.fps; per = s['duration']
    fk = bpy.data.objects['Pose_Control_Rig']; obj = {n: bpy.data.objects[n] for n in OBJS}
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    idle = json.loads((P['out'] / 'idle_controls.json').read_text()); IF = {k: Matrix(v) for k, v in idle['fk'].items()}; IO = {k: Matrix(v) for k, v in idle['obj'].items()}
    nf = round(per * fps); run = []
    for fr in range(nf + 1):
        c.at(fr); run.append(({b.name: b.matrix_basis.copy() for b in fk.pose.bones}, {n: o.matrix_world.copy() for n, o in obj.items()}))
    def runat(phi):
        x = (phi % per) * fps; i = int(x); k = x - i; j = min(i + 1, nf); a, b = run[min(i, nf)], run[j]
        return {n: _mblend(a[0][n], b[0][n], k) for n in a[0]}, {n: _mblend(a[1][n], b[1][n], k) for n in a[1]}
    sp = lambda t: max(0., 1 - (t / tb) ** 2)
    X = lambda t: v_run * ((min(t, tb)) - min(t, tb) ** 3 / (3 * tb * tb))      # capsule travel so far
    Xend = X(tb); phi = lambda t: X(t) / v_run
    def planted(n, t):  # idle spot, ahead by the capsule distance still to travel (moves back at capsule speed)
        return Matrix.Translation(Vector((0, -(Xend - X(t)), 0))) @ IO[n]
    lean = [(0, 0), (.07, -3.2), (.15, -12.3), (.25, -19.6), (.33, -18.7), (.44, -7.3), (.54, -1.4), (.6, 0)]
    dip = [(0, 0), (.12, -.008), (.28, -.044), (.34, -.050), (.45, -.020), (.54, -.004), (.6, 0)]
    wL = lambda t: smoother01((t - .02) / .11)        # braking foot down by .13 s (f4)
    wR = lambda t: smoother01((t - .13) / .17)        # right foot swings home, down by .30 s (f9)
    wB = lambda t: 1 - smoother01((t - .02) / .40)
    end = round(D * fps); s['duration'] = D; s.frame_start = 0; s.frame_end = end; s['rebuild_job'] = 'run'
    for o in (fk, *obj.values()): o.animation_data_clear()
    prev = {}; times = [round(i * step, 6) for i in range(round(D / step) + 1)]
    for t in times:
        rf, ro = runat(phi(t)); wb = wB(t)
        for b in fk.pose.bones: b.matrix_basis = _mblend(IF[b.name], rf[b.name], wb)
        for sd, w in (('Left', wL(t)), ('Right', wR(t))): fk.pose.bones[sd + 'ToeBase'].matrix_basis = _mblend(rf[sd + 'ToeBase'], IF[sd + 'ToeBase'], w)
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((0, 0, pchip(dip, t)))
        bpy.context.view_layer.update()
        ln = pchip(lean, t); wr(fk, 'Spine', 'X', .45 * ln); wr(fk, 'Spine1', 'X', .35 * ln); wr(fk, 'Head', 'X', -.4 * ln)
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        for n in ('Hilt_Control', 'LeftLeg_Pole', 'RightLeg_Pole', 'RightArm_Pole'):
            obj[n].matrix_basis = _mblend(IO[n], ro[n], wb); c.key(obj[n], t * fps, prev)
        for sd, w in (('Left', wL(t)), ('Right', wR(t))):
            n = sd + 'Leg_Target'; M = _mblend(ro[n], planted(n, t), w)
            if sd == 'Right' and 0 < w < 1: M = Matrix.Translation(Vector((0, 0, .035 * math.sin(math.pi * w) ** 2))) @ M
            M = _roll_contact(sd, M, clamp_only=True); obj[n].matrix_basis = M; c.key(obj[n], t * fps, prev)
    for o in (fk, *obj.values()): c.smooth(o)
    s['run_transition'] = json.dumps({'kind': 'stop r2', 'matched': 'RunOneHand_Blender_meshy_r3 (frame 0, bat carry)', 'capsuleTravel_units': Xend})
    c.at(0); return {'capsuleTravel': Xend, 'phiEnd': phi(D)}


def stagger_v2r3():
    """Critic r3: torso home over f5-f10, head arrives 2.5 frames later (last 30% after the torso settles, <=8 px/frame),
    blade two frames behind the chest; impact hip drop kept."""
    STAG.update(lag_spine1=0., lag_spine2=0., b_mix=.25, home_start=.08, home=.345, home_soft=True, home_trap=True, lag_head=.08, lag_neck=.045, lag_hand=.067, lag_fore=.045, lag_arm=.025,
                impact_dip=-.015, absorb=.10)
    return stagger_v2()


def head_track(t0=.8, t1=1.9, step_s=1 / 30.):
    s = bpy.context.scene; fps = s.render.fps; rig = bpy.data.objects['Knight_Deform']; out = []; t = t0
    while t <= t1 + 1e-6:
        fr = t * fps; s.frame_set(int(fr), subframe=fr - int(fr)); out.append((round(t, 4), (rig.matrix_world @ rig.pose.bones['Head'].tail).z)); t += step_s
    return out


def death_v2r3(passes=3):
    """Critic r3: the knee-down becomes an accelerating fall over f30-36 (hips lowered gradually instead of a one-frame
    snap), then no rebound: a small spine bend holds the head from rising f36-50. Knee contact and the f86+ tail kept."""
    D = DEATH; D.update(tail=(2.75, 3.55), kneel=(1.16, 1.70), trail='Right', front='Left', ankle_z=.05, settle0=9., settle1=9.5)
    r2 = json.loads((P['out'] / 'death_v2r2' / 'Death_Blender_v2r2-report.json').read_text()) if False else None
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    # rebuild the r2 lift (knee on the floor) exactly as r2 did
    D['lift'] = None
    for k in range(3):
        open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2r3')
        g = part_ground(t0=1.0, t1=2.6, step_s=.05)
        if k == 2: break
        pts = [(0., 0.), (.95, 0.)]
        for row in g:
            tt = row['t']; base = pchip(D['lift'], tt) if D.get('lift') else 0.
            knee = row.get('RightLeg', 999.) / 1000.
            pts.append((tt, base - (knee - .004) if 1.15 <= tt <= 1.75 else base))
        pts += [(2.75, 0.), (4.4, 0.)]; D['lift'] = pts
    lift = D['lift']; L120 = pchip(lift, 1.20)
    # accelerating descent: replace the snap before 1.20 s with an ease from 0 at 0.98 s
    D['lift'] = [(0., 0.), (.98, 0.)] + [(round(.98 + i * .22 / 8, 4), L120 * smooth01(i / 8) ** 1.2) for i in range(1, 8)] + [p_ for p_ in lift if p_[0] >= 1.20]
    D['bend'] = None; hist = []
    for k in range(passes):
        open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2r3')
        hz = head_track(); hist.append([round(1000 * z, 1) for _, z in hz])
        if k == passes - 1: break
        # bottom of the fall, then no rise: bend the spine forward by the excess height (about 0.32 m lever)
        tb = [i for i, (tt, z) in enumerate(hz) if tt >= 1.17]; i0 = tb[0]; zmin = hz[i0][1]; pts = [(0., 0.), (1.12, 0.)]
        for tt, z in hz[i0:]:
            if tt > 1.75: break
            zmin = min(zmin, z); ex = max(0., z - zmin)
            base = pchip(D['bend'], tt) if D.get('bend') else 0.
            pts.append((tt, base + math.degrees(math.asin(min(.9, ex / .32)))))
        pts += [(1.95, 0.), (4.4, 0.)]; D['bend'] = pts
    return {'headZmm': hist, 'kneeLiftAt120': L120}


DEATH3_STATE = P['out'] / 'death_v2r3_state.json'


def death_r3_step(step):
    """Split version of death_v2r3 (each call stays under the RPC timeout). step 'lift0','lift1','lift2' build the r2 knee
    lift; 'ease' applies the accelerating descent; 'bend' adds/updates the no-rebound spine bend; 'final' just re-authors."""
    D = DEATH; D.update(tail=(2.75, 3.55), kneel=(1.16, 1.70), trail='Right', front='Left', ankle_z=.05, settle0=9., settle1=9.5)
    st = json.loads(DEATH3_STATE.read_text()) if DEATH3_STATE.exists() and step != 'lift0' else {}
    D['lift'] = [tuple(x) for x in st['lift']] if st.get('lift') else None
    D['bend'] = [tuple(x) for x in st['bend']] if st.get('bend') else None
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    open_src(REM / 'death_Blender_v1.blend'); death_v2(); bake_only('death_v2r3')
    out = {'step': step}
    if step.startswith('lift'):
        g = part_ground(t0=1.0, t1=2.6, step_s=.05); pts = [(0., 0.), (.95, 0.)]
        for row in g:
            tt = row['t']; base = pchip(D['lift'], tt) if D.get('lift') else 0.; knee = row.get('RightLeg', 999.) / 1000.
            pts.append((tt, base - (knee - .004) if 1.15 <= tt <= 1.75 else base))
        pts += [(2.75, 0.), (4.4, 0.)]; st['lift'] = pts; out['kneeMM'] = [row.get('RightLeg') for row in g if 1.15 <= row['t'] <= 1.75]
    elif step == 'ease':
        lift = D['lift']; L120 = pchip(lift, 1.20)
        st['lift'] = [(0., 0.), (.98, 0.)] + [(round(.98 + i * .22 / 8, 4), L120 * smooth01(i / 8) ** 1.2) for i in range(1, 8)] + [p_ for p_ in lift if p_[0] >= 1.20]
        out['L120'] = L120
    elif step == 'bend':
        hz = head_track(); tb = [i for i, (tt, z) in enumerate(hz) if tt >= 1.17]; i0 = tb[0]; zmin = hz[i0][1]; pts = [(0., 0.), (1.12, 0.)]
        for tt, z in hz[i0:]:
            if tt > 1.75: break
            zmin = min(zmin, z); ex = max(0., z - zmin); base = pchip(D['bend'], tt) if D.get('bend') else 0.
            pts.append((tt, base + 1.8 * math.degrees(math.asin(min(.9, ex / .32)))))
        pts += [(1.95, 0.), (4.4, 0.)]; st['bend'] = pts
    hz = head_track(); out['headStepsMM'] = [round(1000 * (hz[i][1] - hz[i - 1][1]), 1) for i in range(1, len(hz))]
    DEATH3_STATE.write_text(json.dumps(st)); return out


def backloop_v1r2(**kw):
    """Critic r2: chest counter-yaw about +-5 deg against the pelvis, clavicles swinging with it, off-hand swing ~3 cm."""
    BL.update(chest=-1.15, free_swing=6.5, clav=4.0); BL.update(kw)
    return backloop_v1()


def axis_probe(bones=('LeftShoulder', 'RightShoulder', 'LeftArm'), deg=10.):
    """World displacement (mm) of each bone's child head when the bone is rotated +deg about local X/Y/Z at frame 0."""
    fk = bpy.data.objects['Pose_Control_Rig']; c.at(0); out = {}
    for bn in bones:
        pb = fk.pose.bones[bn]; ch = pb.children[0]; h0 = (fk.matrix_world @ ch.head).copy(); b0 = pb.matrix_basis.copy()
        for ax in 'XYZ':
            wr(fk, bn, ax, deg); bpy.context.view_layer.update(); d = fk.matrix_world @ ch.head - h0
            out[bn + ax] = [round(1000 * v, 1) for v in d]; pb.matrix_basis = b0; bpy.context.view_layer.update()
    return out


def band_widths(t_step=.1, bands=(.82, .78, .74, .70, .66), exclude=('sword', 'blade', 'hilt', 'scabbard')):
    """Front-view silhouette proxy: world X extent (mm) of the evaluated knight mesh in thin Z bands, per sampled time."""
    s = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get(); res = []
    obs = [o for o in s.objects if o.type == 'MESH' and o.visible_get() and not any(e in o.name.lower() for e in exclude)]
    T = s.frame_end / s.render.fps; n = int(round(T / t_step))
    for i in range(n + 1):
        s.frame_set(round(i * t_step * s.render.fps)); dg = bpy.context.evaluated_depsgraph_get(); row = {}
        import numpy as np
        pts = []
        for o in obs:
            e = o.evaluated_get(dg); m = e.to_mesh(); a = np.empty(len(m.vertices) * 3); m.vertices.foreach_get('co', a)
            a = a.reshape(-1, 3); M = np.array(o.matrix_world); a = a @ M[:3, :3].T + M[:3, 3]; pts.append(a); e.to_mesh_clear()
        A = np.concatenate(pts)
        for z in bands:
            sel = A[np.abs(A[:, 2] - z) < .01]; row[z] = round(1000 * float(sel[:, 0].max() - sel[:, 0].min()), 1) if len(sel) else 0
        res.append(row)
    return {'objects': [o.name for o in obs], 'rows': res}


def scene_brief():
    s = bpy.context.scene; out = {'job': s.get('rebuild_job'), 'fps': s.render.fps, 'range': [s.frame_start, s.frame_end], 'duration': s.get('duration'), 'two_hand': s.get('two_hand'),
                                  'source_action': s.get('source_action'), 'markers': [(m.name, m.frame) for m in s.timeline_markers], 'props': [k for k in s.keys()][:60]}
    obs = {}
    for o in s.objects:
        if o.type in ('EMPTY', 'ARMATURE') or 'Target' in o.name or 'Pole' in o.name or 'Hilt' in o.name:
            ad = o.animation_data; obs[o.name] = {'type': o.type, 'parent': o.parent.name if o.parent else None, 'parent_bone': o.parent_bone,
                'cons': [(cn.type, getattr(cn, 'subtarget', ''), getattr(getattr(cn, 'target', None), 'name', None)) for cn in getattr(o, 'constraints', [])],
                'action': ad.action.name if ad and ad.action else None, 'loc': [round(v, 4) for v in o.matrix_world.translation]}
    fk = bpy.data.objects['Pose_Control_Rig']; ik = {}
    for pb in fk.pose.bones:
        for cn in pb.constraints: ik.setdefault(pb.name, []).append((cn.type, getattr(getattr(cn, 'target', None), 'name', None), getattr(cn, 'subtarget', ''), round(cn.influence, 3)))
    out['objects'] = obs; out['fk_constraints'] = ik; return out


def pose_deltas(times=(.0, .033, .07, .1, .15, .23, .3), bones=('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head', 'LeftShoulder', 'RightShoulder', 'LeftArm', 'RightArm', 'LeftUpLeg', 'RightUpLeg')):
    """World-space rotation deltas (deg, XYZ euler of R_t @ R_0^-1) of FK bones and Hilt_Control vs frame 0, plus hips/hilt translation (mm)."""
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; h = bpy.data.objects.get('Hilt_Control'); c.at(0)
    R0 = {b: (fk.matrix_world @ fk.pose.bones[b].matrix).to_3x3() for b in bones}; P0 = {b: fk.matrix_world @ fk.pose.bones[b].head for b in ('Hips', 'Head')}
    H0 = h.matrix_world.copy() if h else None; out = []
    for t in times:
        c.at(t * s.render.fps); row = {'t': t}
        for b in bones:
            d = (fk.matrix_world @ fk.pose.bones[b].matrix).to_3x3() @ R0[b].inverted(); row[b] = [round(math.degrees(a), 1) for a in d.to_euler()]
        for b in ('Hips', 'Head'): row[b + '_mm'] = [round(1000 * v, 1) for v in (fk.matrix_world @ fk.pose.bones[b].head - P0[b])]
        if h:
            d = h.matrix_world.to_3x3() @ H0.to_3x3().inverted(); row['hilt'] = [round(math.degrees(a), 1) for a in d.to_euler()]; row['hilt_mm'] = [round(1000 * v, 1) for v in h.matrix_world.translation - H0.translation]
        out.append(row)
    c.at(0); return out


# --------------------------------------------------------- GuardBreakStagger v1 ----
# One-shot 1.2 s from and back to the two-hand guard idle (IdleTwoHand v2r4 frame 0). Hit at f0: the blade is
# thrown wide (knight's right) and up with both arms, torso snaps back ~18 deg using the approved Stagger's
# language (back + twist to the sword side + right tilt), head whips last; 2-frame hit-stop hold f2-f3;
# two heel-first stumbling catches back (right long, left shorter), the hips absorb each; recovery drags the
# right foot in and hauls the sword down through guard height and back up (weight, no snap). Root travels +Y.
GB = dict(
    T=1.2, snap=.0667, hold=.10,
    fling=[(0, 0), (.0667, .62), (.10, .62), (.22, 1.0), (.32, .92), (.45, .76), (.62, .64), (.72, .56), (.80, .43), (.92, .19), (1.04, .045), (1.13, 0), (1.2, 0)],
    drop=[(0, 0), (.80, 0), (.96, 1.), (1.08, .28), (1.16, .03), (1.2, 0)],
    hy=[(0, 0), (.0667, .010), (.10, .010), (.20, .045), (.34, .115), (.44, .150), (.52, .168), (.62, .196), (.72, .222), (.85, .221), (1.0, .212), (1.12, .2102), (1.2, .21)],
    hx=[(0, 0), (.10, 0), (.30, -.008), (.42, -.020), (.52, -.014), (.66, .010), (.76, .008), (.95, .001), (1.2, 0)],
    hz=[(0, 0), (.0667, -.012), (.10, -.012), (.20, -.008), (.30, -.006), (.35, -.012), (.42, -.032), (.53, -.017), (.62, -.016), (.70, -.026), (.80, -.019), (.96, -.009), (1.06, -.010), (1.2, 0)],
    pelvis=[(0, 0), (.0667, -4.), (.10, -4.), (.20, -6.), (.36, -4.), (.45, -1.5), (.62, -2.), (.72, .3), (.90, .8), (1.2, 0)],
    chest=[(0, 0), (.0667, -12.), (.10, -12.), (.20, -20.), (.30, -17.), (.36, -13.), (.45, -8.), (.55, -9.), (.62, -8.), (.70, -4.5), (.80, -2.5), (.92, 2.2), (1.05, .5), (1.2, 0)],
    twist=[(0, 0), (.0667, -13.), (.10, -13.), (.22, -22.), (.36, -15.), (.50, -10.), (.62, -6.), (.80, -2.), (1.0, 0), (1.2, 0)], pelvis_twist=.35,
    tilt=[(0, 0), (.0667, -4.), (.10, -4.), (.22, -6.), (.38, -5.), (.50, -1.), (.66, 2.), (.80, 1.), (1.0, 0), (1.2, 0)],
    head=[(0, 0), (.0667, 6.), (.10, 6.), (.17, 0), (.26, -9.), (.34, -4.), (.42, 2.), (.52, -1.), (.62, 1.), (.72, -1.5), (.82, 0), (.95, -1.), (1.08, .3), (1.2, 0)],
    head_twist=[(0, 0), (.0667, 5.), (.10, 5.), (.25, -4.), (.40, 0), (1.2, 0)],
    hilt_rot=(-32., -46., -14.), hilt_up=(-.15, .10, .11), pivot_grip=1., drop_rot=9., drop_mv=(0, -.008, -.032), shrug=6., pole_flare=(.16, .0, .18), pole_flare_R=(-.30, 0., -.08), pole_flare_L=(.05, -.10, .05),
    # stumbling catches: (lift, land, dy, height, heel-first pitch); recovery drag of the right foot
    steps={'Right': [(.12, .35, .28, .05, 14.), (.84, .98, -.07, .014, 3.)], 'Left': [(.44, .62, .21, .034, 10.)]}, roll=.09, peel=.035, peel_pitch=7.,
)
GBF = {}


def _gb_snap(pts, t):
    """pchip, but the impact segment leaves at full speed (ease-out) instead of easing in."""
    if t < GB['snap']:
        v1 = pchip(pts, GB['snap']); u = t / GB['snap']; return v1 * (u if GB.get('snap_lin') else 1 - (1 - u) ** 2)
    return pchip(pts, t)


def _gb_foot(side, t):
    F = GBF[side]; M = F['M0'].copy(); y = 0.; z = 0.; pitch = 0.; pivot = 'heel'
    for (t0, t1, dy, hgt, pl) in GB['steps'][side]:
        if t < t0 - GB['peel']: break
        if t < t0:  # toes peel up about the heel just before the lift
            pitch = -GB['peel_pitch'] * smooth01((t - (t0 - GB['peel'])) / GB['peel']) if dy > 0 else 0; break
        if t < t1:
            s = (t - t0) / (t1 - t0); dur = t1 - t0; v_land = 1.3 * dy / dur
            y += hermite(0., dy, 0., v_land, s, dur) if dy > 0 else dy * smoother01(s)
            z = hgt * math.sin(math.pi * min(1., s / .92)) ** 1.3 if s < .92 else 0.
            p0 = -GB['peel_pitch'] if dy > 0 else 0.
            pitch = p0 + (-pl - p0) * smooth01(s / .8); break
        y += dy
        if t < t1 + GB['roll']:  # heel down first, foot slaps flat about the heel
            pitch = -pl * (1 - smooth01((t - t1) / GB['roll'])) ** 1.5 if pl > 4 else -pl * (1 - smooth01((t - t1) / GB['roll'])); break
    flat = Matrix.Translation(Vector((0, y, z))) @ M
    hw = flat @ F['heel']; R = Matrix.Translation(hw) @ Matrix.Rotation(math.radians(pitch), 4, 'X') @ Matrix.Translation(-hw)
    Mf = R @ flat; zmin = min((Mf @ q).z for q in F['sole'])
    if zmin < F['ground']: Mf = Matrix.Translation(Vector((0, 0, F['ground'] - zmin))) @ Mf
    return Mf


def guardbreak_v1(step=1 / 75.):
    s = bpy.context.scene; G = GB; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'idle_two', 'open IdleTwoHand v2r4 first'
    fps = s.render.fps; T = G['T']; end = round(T * fps)
    fk = bpy.data.objects['Pose_Control_Rig']; h = bpy.data.objects['Hilt_Control']; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}; world = {b.name: (fk.matrix_world @ b.matrix).copy() for b in fk.pose.bones}
    H0 = h.matrix_world.copy(); C0 = world['Spine2'].copy()
    for sd in ('Left', 'Right'):
        pts, _ = sole_world(sd, 0); c.at(0); tg = bpy.data.objects[sd + 'Leg_Target']; M0 = tg.matrix_world.copy(); inv = M0.inverted()
        loc = [inv @ p for p in pts]; zmin = min(p.z for p in pts); cont = [q for q, p in zip(loc, pts) if p.z < zmin + .006]
        heel = max(cont, key=lambda q: (M0 @ q).y)
        GBF[sd] = {'M0': M0, 'sole': loc[::3] + cont, 'heel': heel, 'ground': zmin}
    armt = {sd: bpy.data.objects[sd + 'Arm_Target'] for sd in ('Left', 'Right')}; armb = {sd: o.matrix_basis.copy() for sd, o in armt.items()}
    tg = {sd: bpy.data.objects[sd + 'Leg_Target'] for sd in ('Left', 'Right')}; lp = {sd: bpy.data.objects[sd + 'Leg_Pole'] for sd in tg}; ap = {sd: bpy.data.objects[sd + 'Arm_Pole'] for sd in tg}
    gripmid = (armt['Left'].matrix_world.translation + armt['Right'].matrix_world.translation) / 2
    lp0 = {sd: o.matrix_world.translation.copy() for sd, o in lp.items()}; ap0 = {sd: o.matrix_world.translation.copy() for sd, o in ap.items()}
    fk.animation_data_clear(); h.animation_data_clear()
    for o in (*tg.values(), *lp.values(), *ap.values()): f.reset_animation(o)
    for sd, o in armt.items(): o.animation_data_clear(); o.matrix_basis = armb[sd]
    s.frame_start = 0; s.frame_end = end; s['duration'] = T
    for mk in list(s.timeline_markers): s.timeline_markers.remove(mk)
    for nm, tt in (('Impact', 0.), ('HitStop', G['snap']), ('CatchRight', .35), ('CatchLeft', .62), ('Guard', 1.13)): s.timeline_markers.new(nm, frame=round(tt * fps))
    times = sorted(set([round(i / fps, 6) for i in range(round(.14 * fps) + 1)] + [round(min(T, .14 + i * step), 6) for i in range(int((T - .14) / step) + 2)])); prev = {}
    reach = {'LeftArm': 0., 'RightArm': 0., 'LeftLeg': 0., 'RightLeg': 0.}
    L = {sd + k: (world[sd + a].translation - world[sd + b].translation).length + (world[sd + b].translation - world[sd + e].translation).length
         for sd in ('Left', 'Right') for k, (a, b, e) in (('Arm', ('Arm', 'ForeArm', 'Hand')), ('Leg', ('UpLeg', 'Leg', 'Foot')))}
    for t in times:
        fr = t * fps
        for b in fk.pose.bones: b.matrix_basis = base[b.name]
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((_gb_snap(G['hx'], t), _gb_snap(G['hy'], t), _gb_snap(G['hz'], t)))
        bpy.context.view_layer.update()
        pv = _gb_snap(G['pelvis'], t); ch = _gb_snap(G['chest'], t); tw = _gb_snap(G['twist'], t); tl = _gb_snap(G['tilt'], t)
        wr(fk, 'Hips', 'X', pv); wr(fk, 'Hips', 'Z', G['pelvis_twist'] * tw)
        for bn, w_ in (('Spine', .25), ('Spine1', .35), ('Spine2', .40)):
            wr(fk, bn, 'X', w_ * (ch - pv)); wr(fk, bn, 'Z', w_ * (1 - G['pelvis_twist']) * tw); wr(fk, bn, 'Y', w_ * tl)
        hd = _gb_snap(G['head'], t); ht = _gb_snap(G['head_twist'], t)
        wr(fk, 'Neck', 'X', .4 * hd); wr(fk, 'Head', 'X', .6 * hd); wr(fk, 'Neck', 'Z', .4 * ht); wr(fk, 'Head', 'Z', .6 * ht)
        k = _gb_snap(G['fling'], t); dr = pchip(G['drop'], t)
        wr(fk, 'LeftShoulder', 'Y', -G['shrug'] * k); wr(fk, 'RightShoulder', 'Y', G['shrug'] * k)
        for b in fk.pose.bones: c.key(b, fr, prev)
        Cn = fk.matrix_world @ fk.pose.bones['Spine2'].matrix; carry = Cn @ C0.inverted()
        rx, ry, rz = G['hilt_rot']; pvt = H0.translation.lerp(gripmid, G.get('pivot_grip', 0.))
        Rf = Matrix.Rotation(math.radians(rz * k), 4, 'Z') @ Matrix.Rotation(math.radians(ry * k), 4, 'Y') @ Matrix.Rotation(math.radians(rx * k + G['drop_rot'] * dr), 4, 'X')
        mv = Vector(G['hilt_up']) * k + Vector(G['drop_mv']) * dr
        h.matrix_world = carry @ Matrix.Translation(pvt + mv) @ Rf @ Matrix.Translation(-pvt) @ H0; c.key(h, fr, prev)
        for sd in ('Left', 'Right'):
            M = _gb_foot(sd, t); tg[sd].matrix_basis = M; c.key(tg[sd], fr, prev)
            off = M.translation - GBF[sd]['M0'].translation
            lp[sd].location = lp0[sd] + Vector((0, .5 * off.y + .5 * (_gb_snap(G['hy'], t)), .5 * off.z)); lp[sd].keyframe_insert('location', frame=fr)
            sg = -1 if sd == 'Right' else 1; pf = Vector(G.get('pole_flare_' + sd[0], (sg * G['pole_flare'][0], G['pole_flare'][1], G['pole_flare'][2])))
            ap[sd].location = carry @ ap0[sd] + pf * k; ap[sd].keyframe_insert('location', frame=fr)
        bpy.context.view_layer.update()
        for sd in ('Left', 'Right'):
            reach[sd + 'Arm'] = max(reach[sd + 'Arm'], ((fk.matrix_world @ fk.pose.bones[sd + 'Arm'].head) - armt[sd].matrix_world.translation).length / L[sd + 'Arm'])
            reach[sd + 'Leg'] = max(reach[sd + 'Leg'], ((fk.matrix_world @ fk.pose.bones[sd + 'UpLeg'].head) - tg[sd].matrix_world.translation).length / L[sd + 'Leg'])
    for o in (fk, h, *tg.values(), *lp.values(), *ap.values()):
        for fc in c.curves(o.animation_data.action):
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR' if kp.co.x <= .14 * fps + 1e-6 else 'BEZIER'
    s['guardbreak_v1'] = json.dumps({k_: v for k_, v in G.items()}); s['root_motion'] = 'travel: +Y (backward) %.3f rig units over 1.2 s; feet and hips end at idle pose + travel' % G['hy'][-1][1]
    s['root_travel'] = [0., G['hy'][-1][1], 0.]; c.at(0)
    return {'keys': len(times), 'frames': end, 'reach': {k_: round(v, 4) for k_, v in reach.items()}}


def critic_proj(views_=('front', 'side', 'threequarter'), loop=False, helm=False):
    """Exact critic-camera projection (480 px, ortho 2.35, centre (0,0,.7), render.py directions) of the Knight_Deform
    head top, hilt and blade tip per 30 fps frame: pixel positions, per-frame steps (px) and the blade's image angle (deg)."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; sock = bpy.data.objects['ReviewWeaponSocket']
    V = {'front': (0, -4, .5), 'side': (4, 0, .5), 'threequarter': (2.8, -4, 1.)}; out = {v: [] for v in views_}
    st = s.render.fps / 30.; nfr = int(math.floor(s.frame_end / st + 1e-6)) + (0 if loop else 1); prev = {}
    if helm:
        body = body_obj(); gi = body.vertex_groups['Head'].index
        hidx = [v.index for v in body.data.vertices if any(g.group == gi and g.weight > .5 for g in v.groups)]
    for i in range(nfr):
        fr = i * st; s.frame_set(int(fr), subframe=fr - int(fr))
        hd = rig.matrix_world @ rig.pose.bones['Head'].tail; hilt = sock.matrix_world.translation; tip = sock.matrix_world @ Vector((0, -1.0, 0))
        if helm:  # helmet: centroid of the top of the head-weighted vertices (what a silhouette tracker sees)
            body = body_obj(); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
            pts = [ev.matrix_world @ me.vertices[i].co for i in hidx]; ev.to_mesh_clear(); zt = max(p.z for p in pts)
            top = [p for p in pts if p.z > zt - .03]; hd = sum(top, Vector()) / len(top)
        hips = rig.matrix_world @ rig.pose.bones['Hips'].head
        for v in views_:
            d = Vector(V[v]).normalized(); q = (-d).to_track_quat('-Z', 'Y'); R = q.to_matrix(); right = R @ Vector((1, 0, 0)); up = R @ Vector((0, 1, 0))
            def px(p): w = p - Vector((0, 0, .7)); return (240 + w.dot(right) / 2.35 * 480, 240 - w.dot(up) / 2.35 * 480)
            H, Hi, Ti, Hp = px(hd), px(hilt), px(tip), px(hips); ang = math.degrees(math.atan2(-(Ti[1] - Hi[1]), Ti[0] - Hi[0]))
            row = {'f': i, 'head': [round(H[0], 1), round(H[1], 1)], 'tip': [round(Ti[0], 1), round(Ti[1], 1)], 'hips': [round(Hp[0], 1), round(Hp[1], 1)], 'blade': round(ang, 1)}
            if v in prev:
                ph, pt, pa, pp = prev[v]; row['headStep'] = round(math.hypot(H[0] - ph[0], H[1] - ph[1]), 1); row['tipStep'] = round(math.hypot(Ti[0] - pt[0], Ti[1] - pt[1]), 1)
                row['bladeStep'] = round((ang - pa + 180) % 360 - 180, 1); row['hipStep'] = round(math.hypot(Hp[0] - pp[0], Hp[1] - pp[1]), 1)
            prev[v] = (H, Ti, ang, Hp); out[v].append(row)
    c.at(0); return out


def _rs_right_plant(t, R, I, runat, phi):
    """RunStart r3 lead foot: lifts at 'lift', knee peak 3 frames later, plants flat-to-ball at 'land' and stays on the floor,
    sliding back at the ramping ground speed (in place), then joins the run's own right-foot matrices over the last frames."""
    A = R['right_plant']; D = R['dur']; n = 'RightLeg_Target'
    slide = lambda tt: A['v_run'] * (tt * tt - A['land'] ** 2) / (2 * D)
    Mend = runat(phi(D))[1][n]; Rl = runat(A['phase_land'])[1][n]
    land = Matrix.Translation(Vector((Mend.translation.x, Mend.translation.y - slide(D), Rl.translation.z))) @ Rl.to_3x3().to_4x4()
    land = _roll_contact('Right', land)
    if t <= A['lift']: return I
    if t < A['land']:
        s = (t - A['lift']) / (A['land'] - A['lift']); M = _mblend(I, land, smoother01(s))
        sp = (A['peak'] - A['lift']) / (A['land'] - A['lift'])
        z = A['z'] * (math.sin(math.pi / 2 * s / sp) if s < sp else math.cos(math.pi / 2 * (s - sp) / (1 - sp)) ** 1.5)
        return _roll_contact('Right', Matrix.Translation(Vector((0, 0, z))) @ M, clamp_only=True)
    M = Matrix.Translation(Vector((0, slide(t), 0))) @ land
    if t > A['join']: M = _mblend(M, runat(phi(t))[1][n], smoother01((t - A['join']) / (D - A['join'])))
    else: M = _roll_contact('Right', M)
    return M


def run_start_r3():
    """Critic r3: the lead (right) foot plants by f9 with the sole on the floor and the body pushes off it; knee peak 3 frames
    after the lift; flight only after that contact (into the exact Meshy r3 f0 join). Lean/push of r2 kept."""
    RUN_T['start'].update(body=(0., .5), body_easeout=True, lean=[(0, 0), (.5, 0)], dip=[(0, 0), (.06, -.012), (.18, -.016), (.29, -.040), (.36, -.036), (.43, -.018), (.5, 0)], left_time=(.43, .5),
                          right_plant=dict(lift=.10, peak=.20, land=.30, z=.075, join=.433, v_run=1.3115, phase_land=16 / 30.))
    return run_transition('start')


_RS = {}


def _stag_rstep(t, world, prev, fps):
    """Stagger r4: the right foot steps back (ball first, rolls flat) to take the hit, then returns to the idle spot."""
    St = STAG['rstep']; tg = bpy.data.objects['RightLeg_Target']; M0 = world['RightFoot']
    if t == 0: _RS.clear()
    Sc = _RS
    if 'sole' not in Sc:
        pts, _ = sole_world('Right', 0); c.at(t * fps); inv = M0.inverted(); zmin = min(p.z for p in pts)
        Sc['sole'] = [inv @ p for p in pts][::2]; Sc['ground'] = zmin
        cont = [inv @ p for p in pts if p.z < zmin + .006]; Sc['ball'] = min(cont, key=lambda q: (M0 @ q).y); Sc['heel'] = max(cont, key=lambda q: (M0 @ q).y)
    y = pchip(St['y'], t); z = pchip(St['z'], t); p = pchip(St['pitch'], t)
    M = Matrix.Translation(Vector((0, y, z))) @ M0
    piv = M @ (Sc['ball'] if p > 0 else Sc['heel']); M = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(p), 4, 'X') @ Matrix.Translation(-piv) @ M
    zm = min((M @ q).z for q in Sc['sole'])
    if zm < Sc['ground'] or (z == 0 and p == 0): M = Matrix.Translation(Vector((0, 0, Sc['ground'] - zm))) @ M
    tg.matrix_basis = M; c.key(tg, t * fps, prev)


def stagger_v2r4():
    return _stag_r4({})


def _stag_r4(over, extra=None):
    """Critic r4: recovery starts eased over f4-f6 (linear velocity ramp, head/torso), blade returns on a bell (smootherstep
    on the sword arm), and v1's step-back is restored: the right foot steps back ~8 cm to take the hit (weight shifts onto it)
    and returns to the idle spot during the recovery."""
    STAG.update(lag_spine1=0., lag_spine2=0., b_mix=.25, home_start=.10, home=.345, home_soft=True, home_trap=False, trap_a=.36,
                lag_head=.075, lag_neck=.045, lag_hand=.067, lag_fore=.045, lag_arm=.025, impact_dip=-.015, absorb=.10,
                prof={**{n: 'trap' for n in ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand')},
                      **{n: 'bell' for n in ('RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')}, **over},
                hip_y=[(0, 0), (.04, .004), (.13, .022), (.22, .024), (.30, .016), (.38, .003), (.42, 0)],
                hip_x=[(0, 0), (.06, 0), (.15, -.010), (.24, -.010), (.34, -.002), (.42, 0)],
                rstep=dict(y=[(0, 0), (.03, 0), (.12, .080), (.24, .080), (.35, .002), (.37, 0), (.42, 0)],
                           z=[(0, 0), (.03, 0), (.075, .020), (.12, 0), (.24, 0), (.295, .011), (.35, 0), (.42, 0)],
                           pitch=[(0, 0), (.03, 0), (.09, 7.), (.12, 4.), (.16, 0), (.24, 0), (.27, -4.), (.33, -2.), (.36, 0), (.42, 0)]))
    STAG.update(extra or {})
    return stagger_v2()


def stagger_v2r4b():
    """r4 variant: sword arm holds the recoil through the absorb then returns on one smootherstep bell (f5-f12); head/neck hold
    the recoil and return on their own eased window f3-f12.6 (linear velocity ramp, low peak)."""
    r = {n: 'bellA' for n in ('RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')}
    r.update({n: 'trapHA' for n in ('Neck', 'Head')})
    return _stag_r4(r, dict(head_home=(.10, .42), trap_a=.40, lag_head=0., lag_neck=0.))


def _front_blade_angle():
    h = bpy.data.objects['Hilt_Control']; d = h.matrix_world.to_3x3() @ Vector((0, -1, 0)); return math.degrees(math.atan2(d.z, d.x))


def _stag_blade_bell(t, fk, BB):
    """r4: the sword's front-view angle returns on one smootherstep bell between blade_bell=(t0, t1) (wrist turned about the
    view axis); outside the window the natural pose is kept and the correction fades out as the arm reaches idle."""
    t0, t1 = STAG['blade_bell']; a = _front_blade_angle()
    if t == 0: BB['end'] = a; return
    if t < t0: return
    if 'a0' not in BB: BB['a0'] = a
    tgt = BB['a0'] + ((BB['end'] - BB['a0'] + 180) % 360 - 180) * smoother01((t - t0) / (t1 - t0))
    for _ in range(3):
        dlt = (tgt - _front_blade_angle() + 180) % 360 - 180
        if abs(dlt) < 1e-3: break
        wr(fk, 'RightHand', 'Y', -dlt)


def stagger_v2r4c():
    r = {n: 'bellA' for n in ('RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')}
    r.update({n: 'trapHA' for n in ('Neck', 'Head')})
    return _stag_r4(r, dict(head_home=(.10, .42), trap_a=.40, lag_head=0., lag_neck=0., blade_bell=(.0667, .30)))


# ------------------------------------------------------------------ RunStart r4 ----
# Root-motion start: the body travels forward (-Y) on a linear speed ramp (0 -> run speed over 0.5 s); planted feet are
# fixed in the world. Lead (right) foot: lifts f3, knee peak f6, lands heel-touch f9 and is flat by f10, fixed through
# f13, then rolls onto its ball (toe fixed) into the run's own f0 right-foot matrix. Rear (left) foot: heel peels about
# the ball from f8, toe leaves last at f11, swings past the lead foot into the run's f0 left-foot matrix. The clip ends on
# Meshy r3 run f0 + root travel.
RS4 = dict(D=.5, phi0=.35, V=1.3115, r_lift=.10, r_peak=.20, r_land=.30, r_flat=.333, r_z=.075, r_land_pitch=6., r_roll=.40,
           l_peel=.267, l_off=.367, l_peel_pitch=28., dip=[(0, 0), (.06, -.012), (.18, -.018), (.29, -.044), (.36, -.036), (.43, -.016), (.5, 0)])


def _ploc(M, q, deg):
    """Rotate foot matrix M about world X through its local point q (+deg = toes down)."""
    p = M @ q; return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, 'X') @ Matrix.Translation(-p) @ M


def run_start_r4(step=.01):
    s0 = open_src(RUNSRC); s = bpy.context.scene; fps = s.render.fps; per = s['duration']; A = RS4; D = A['D']
    fk = bpy.data.objects['Pose_Control_Rig']; obj = {n: bpy.data.objects[n] for n in OBJS}
    for sd in ('Left', 'Right'): _foot_from_idle(sd)
    idle = json.loads((P['out'] / 'idle_controls.json').read_text()); IF = {k: Matrix(v) for k, v in idle['fk'].items()}; IO = {k: Matrix(v) for k, v in idle['obj'].items()}
    nf = round(per * fps); run = []
    for fr in range(nf + 1):
        c.at(fr); run.append(({b.name: b.matrix_basis.copy() for b in fk.pose.bones}, {n: o.matrix_world.copy() for n, o in obj.items()}))
    def runat(phi):
        x = (phi % per) * fps; i = int(x); k = x - i; j = min(i + 1, nf); a, b = run[min(i, nf)], run[j]
        return {n: _mblend(a[0][n], b[0][n], k) for n in a[0]}, {n: _mblend(a[1][n], b[1][n], k) for n in a[1]}
    pw = A.get('p', 1.); phi0 = .6 - D / (pw + 1) if A.get('p') else A['phi0']   # speed v = V (t/D)^p: slow until the lead foot is down, then the drive
    dist = lambda t: t ** (pw + 1) / ((pw + 1) * D ** pw)
    phi = lambda t: phi0 + dist(t)
    off = lambda t: Vector((0, -A['V'] * dist(t), 0))
    wbody = lambda t: 1 - (1 - min(1., max(0., t / D))) ** 2.2
    loc = {sd: {k: FOOT[sd]['R0'].inverted() @ FOOT[sd][k] for k in ('heel', 'ball', 'toe')} for sd in ('Left', 'Right')}  # foot-local contact points
    # lead foot: flat landing placed so its ball sits where the run-f0 ball is (after root travel)
    Rend = Matrix.Translation(off(D)) @ runat(phi(D))[1]['RightLeg_Target']; IR = IO['RightLeg_Target']
    flat = Matrix.Translation(Vector((0, 0, 0))) @ IR; bw = flat @ loc['Right']['ball']; be = Rend @ loc['Right']['ball']
    Rflat = _roll_contact('Right', Matrix.Translation(Vector((be.x - bw.x, be.y - bw.y, 0))) @ IR)  # sole flat ON the floor
    # rotation of the end pose relative to flat, as a pitch about X (the run foot is on its ball)
    dq = (Rend.to_3x3() @ IR.to_3x3().inverted()).to_euler(); end_pitch = math.degrees(dq.x)
    IL = IO['LeftLeg_Target']
    def right(t):
        if t <= A['r_lift']: return IR
        if t < A['r_land']:
            s_ = (t - A['r_lift']) / (A['r_land'] - A['r_lift']); sp = (A['r_peak'] - A['r_lift']) / (A['r_land'] - A['r_lift'])
            M = _mblend(IR, Rflat, smoother01(s_)); z = A['r_z'] * (math.sin(math.pi / 2 * s_ / sp) if s_ < sp else math.cos(math.pi / 2 * (s_ - sp) / (1 - sp)) ** 1.6)
            M = _ploc(M, loc['Right']['heel'], -A['r_land_pitch'] * smooth01(s_ / .7))
            return _roll_contact('Right', Matrix.Translation(Vector((0, 0, z))) @ M, clamp_only=True)
        if t < A['r_flat']:  # heel touched: toes come down about the heel
            return _roll_contact('Right', _ploc(Rflat, loc['Right']['heel'], -A['r_land_pitch'] * (1 - smooth01((t - A['r_land']) / (A['r_flat'] - A['r_land'])))))
        if t < A['r_roll']: return Rflat
        u = min(1., (t - A['r_roll']) / (D - A['r_roll'])); a_ = A.get('roll_a')
        if A.get('roll_linear_low'):  # choose the blend so the foot's lowest point rises at a constant rate onto the run's f0 height
            def Mk(k):
                M = _mblend(Rflat, Rend, k); b0 = Rflat @ loc['Right']['ball']; b1 = Rend @ loc['Right']['ball']; bm = M @ loc['Right']['ball']
                return _roll_contact('Right', Matrix.Translation(b0.lerp(b1, k) - bm) @ M, clamp_only=True)
            zl = lambda M: min((M @ q).z for q in FOOT['Right']['low'])
            z1 = zl(Rend); tgt = z1 * u; lo_, hi_ = 0., 1.
            if u >= 1: return Rend
            for _ in range(30):
                mid = (lo_ + hi_) / 2
                if zl(Mk(mid)) < tgt: lo_ = mid
                else: hi_ = mid
            return Mk((lo_ + hi_) / 2)
        if a_:  # trapezoid: near-constant rise, lowest peak speed for the distance
            vm = 1 / (1 - a_); k = vm * u * u / (2 * a_) if u < a_ else 1 - vm * (1 - u) ** 2 / (2 * a_) if u > 1 - a_ else vm * (u - a_ / 2)
        else: k = smoother01(u)
        M = _mblend(Rflat, Rend, k); b0 = Rflat @ loc['Right']['ball']; b1 = Rend @ loc['Right']['ball']; bm = M @ loc['Right']['ball']
        bt = b0.lerp(b1, k); M = Matrix.Translation(bt - bm) @ M  # the ball (toe) stays put while the heel rises
        return _roll_contact('Right', M, clamp_only=True) if k < 1 else M
    def left(t):
        if t <= A['l_peel']: return IL
        if t < A['l_off']:
            return _ploc(IL, loc['Left']['toe'], A['l_peel_pitch'] * smooth01((t - A['l_peel']) / (A['l_off'] - A['l_peel'])))
        P0 = _ploc(IL, loc['Left']['toe'], A['l_peel_pitch']); k = smoother01((t - A['l_off']) / (D - A['l_off']))
        Mr = Matrix.Translation(off(t)) @ runat(phi(t))[1]['LeftLeg_Target']
        M = _mblend(P0, Mr, k)
        return _roll_contact('Left', M, clamp_only=True)
    end = round(D * fps); s['duration'] = D; s.frame_start = 0; s.frame_end = end; s['rebuild_job'] = 'run'
    for o in (fk, *obj.values()): o.animation_data_clear()
    prev = {}; times = [round(i * step, 6) for i in range(round(D / step) + 1)]; reach = {'Left': 0., 'Right': 0.}
    L = {sd: (IF and 0) or 0 for sd in ('Left', 'Right')}
    for t in times:
        rf, ro = runat(phi(t)); wb = wbody(t)
        for b in fk.pose.bones: b.matrix_basis = _mblend(IF[b.name], rf[b.name], wb)
        kf = {'Right': smoother01((t - A['r_lift']) / (A['r_land'] - A['r_lift'])), 'Left': smoother01((t - A['l_off']) / (D - A['l_off']))}
        for sd in ('Left', 'Right'): fk.pose.bones[sd + 'ToeBase'].matrix_basis = _mblend(IF[sd + 'ToeBase'], rf[sd + 'ToeBase'], kf[sd] if sd == 'Left' else (0. if t < A['r_roll'] else (min(1., (t - A['r_roll']) / (D - A['r_roll'])) if A.get('roll_linear_low') else smoother01((t - A['r_roll']) / (D - A['r_roll'])))))
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ (off(t) + Vector((0, 0, pchip(A['dip'], t))))
        bpy.context.view_layer.update()
        for b in fk.pose.bones: c.key(b, t * fps, prev)
        for n in ('Hilt_Control', 'LeftLeg_Pole', 'RightLeg_Pole', 'RightArm_Pole'):
            obj[n].matrix_basis = Matrix.Translation(off(t)) @ _mblend(IO[n], ro[n], wb); c.key(obj[n], t * fps, prev)
        for sd, fn in (('Right', right), ('Left', left)):
            M = fn(t); obj[sd + 'Leg_Target'].matrix_basis = M; c.key(obj[sd + 'Leg_Target'], t * fps, prev)
    for o in (fk, *obj.values()): c.smooth(o)
    s['run_transition'] = json.dumps({'kind': 'start_r4', 'matched': 'RunOneHand_Blender_meshy_r3 f0 + root travel', 'params': {k: v for k, v in A.items()}})
    tr = A['V'] * dist(D)
    s['root_motion'] = 'travel: -Y (forward) %.4f rig units over %.2f s (speed V*(t/D)^%g to %.4f u/s); ends on run f0 + travel' % (tr, D, pw, A['V'])
    s['root_travel'] = [0., -tr, 0.]; c.at(0)
    return {'dur': D, 'endPitch': round(end_pitch, 1), 'travel': tr, 'phi0': phi0}


def run_start_r4b():
    """r4: 0.6 s; lead foot flat f10 and fixed through f13; the drive starts once it is down (speed ~ t^3); the heel rises
    over f13-f18 into the run's f0 right foot (lowest point <= 6.5 mm/frame); rear heel peels f8-f11, toe leaves f12."""
    RS4.update(D=.6, p=3., r_roll=.41, roll_a=None, roll_linear_low=True, l_peel=.267, l_off=.40,
               dip=[(0, 0), (.06, -.012), (.18, -.018), (.29, -.040), (.36, -.034), (.45, -.020), (.6, 0)])
    return run_start_r4()


def guardbreak_v1r2():
    """Critic r2: a bigger throw (torso ~30 deg back, hips driven back early: side head offset >= 60 px) and a hard
    freeze: the impact travels at full speed through f1->f2 (linear) into the f2-f3 hold."""
    GB.update(snap_lin=True,
              chest=[(0, 0), (.0667, -19.), (.10, -19.), (.20, -36.), (.30, -31.), (.36, -23.), (.45, -12.), (.55, -12.), (.62, -10.), (.70, -6.), (.80, -3.), (.92, 2.2), (1.05, .5), (1.2, 0)],
              pelvis=[(0, 0), (.0667, -6.), (.10, -6.), (.20, -9.), (.36, -6.), (.45, -2.5), (.62, -2.5), (.72, .3), (.90, .8), (1.2, 0)],
              hz=[(0, 0), (.0667, -.016), (.10, -.016), (.20, -.026), (.30, -.022), (.35, -.024), (.42, -.036), (.53, -.019), (.62, -.017), (.70, -.026), (.80, -.019), (.96, -.009), (1.06, -.010), (1.2, 0)],
              hy=[(0, 0), (.0667, .028), (.10, .028), (.20, .100), (.34, .158), (.44, .175), (.52, .186), (.62, .205), (.72, .224), (.85, .221), (1.0, .212), (1.12, .2102), (1.2, .21)],
              head=[(0, 0), (.0667, 3.), (.10, 3.), (.17, 0), (.26, -9.), (.34, -4.), (.42, 2.), (.52, -1.), (.62, 1.), (.72, -1.5), (.82, 0), (.95, -1.), (1.08, .3), (1.2, 0)])
    return guardbreak_v1()


def stagger_v2r5(**kw):
    """Critic r5: no overshoot settle and no second push after the impact (the recoil pose is held, so nothing reverses),
    and every group starts home at f2 on a linear velocity ramp: head and blade speeds rise steadily f2-f5."""
    r = {n: 'bellA' for n in ('RightShoulder', 'RightArm', 'RightForeArm', 'RightHand')}
    r.update({n: 'trapHA' for n in ('Neck', 'Head')})
    ex = dict(over=1.0, b_mix=0., home_start=.0667, home=.345, head_home=(.0667, .42), trap_a=.40, lag_head=0., lag_neck=0., blade_bell=(.0667, .30))
    ex.update(kw)
    return _stag_r4(r, ex)


def chest_track(names=('Hips', 'Spine2', 'Neck', 'LeftArm', 'RightArm', 'Head')):
    """Deform-rig world X/Y/Z (mm) of trunk joints per 30 fps frame + chest-minus-hips X (front-view lateral shift)."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; st = s.render.fps / 30.; out = []
    for i in range(int(s.frame_end / st + 1e-6) + 1):
        fr = i * st; s.frame_set(int(fr), subframe=fr - int(fr)); p = {n: rig.matrix_world @ rig.pose.bones[n].head for n in names}
        sh = (p['LeftArm'] + p['RightArm']) / 2
        out.append({'f': i, 'hipX': round(1000 * p['Hips'].x, 1), 'chestX': round(1000 * p['Spine2'].x, 1), 'shX': round(1000 * sh.x, 1), 'neckX': round(1000 * p['Neck'].x, 1),
                    'chestMinusHip': round(1000 * (p['Spine2'].x - p['Hips'].x), 1), 'shMinusHip': round(1000 * (sh.x - p['Hips'].x), 1), 'hipZ': round(1000 * p['Hips'].z, 1)})
    return out


def backloop_v1r3(**kw):
    """Critic r3: mirrored chest shift on both steps (no one-sided arm drift, upper spine leans over each stance foot) and a
    small lagging bob on the greatsword."""
    a = dict(chest=-.75, clav2=9., abd2=-6., abd2r=0., free_swing=5.5, abd1=0., sword_bob=0., sword_bob_lag=.08, chest_sway=0.)
    a.update(kw); return backloop_v1r2(**a)
