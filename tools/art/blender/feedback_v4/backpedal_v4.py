"""Backpedal v4 authoring, round 3 (owner feedback 2026-10-21: "backpedal sucks, looks weird
and blocky. make it more fluid and human like"; target: a trained fighter backing off while
keeping guard). Execute ONLY inside the owned Blender MCP session via run.py, after
revise.py open_job('backpedal', folder=P['out']); then revise.py rebake('backpedal').

Rewrites the opened scene's control-rig curves (Pose_Control_Rig FK, Left/RightLeg_Target,
Left/RightLeg_Pole) and sets the clip length. Arm targets/poles and the wrist-following hilt
are kept from the scene. Native Blender IK still solves knees/elbows at bake time. Never saves.

Round 3 (critic FAIL on round 2):
- One foot is on the floor at every frame. The approved idle leaves the right sole ~14 mm
  above the floor; once the right foot first lands it is planted ON the floor, and it only
  eases back to its idle height while it is unweighted during the final stand-up. The next
  foot lifts only after the reaching toe has touched. No pelvis rise in swing.
- Five alternating steps (R .12, L .20, R .14, L .16, R .10) at an even cadence with short
  double support; the pelvis travels continuously, faster while falling onto the reaching
  foot, so there is no drift over idle feet.
- Pelvis and shoulders counter-rotate ~11 degrees per step; the chest turns toward the sword
  side as the sword-side (right) foot goes back.
- The free (open) hand drifts ~2 cm and the wrist turns with every weight shift.
- Ending: the blade drops (eased) during the last step, reaches its final height, dips a
  little (<15 % of the drop) and settles; only then the body rises out of the crouch, while
  the arms finish relaxing so the blade stays put. Everything is still before the last frame.
  The clip is longer than 2.4 s for this; the required root travel stays exactly .36 back.

Round 4 polish (critic notes on the passing round 3; separate save/export, revision 4r4):
- Pelvis yaw follows backward-walking mechanics: the right hip goes back as the right foot
  reaches back; the shoulders turn against it at half the angle.
- Pelvis dips ~1.6 cm two frames after each contact and rises at the passing position.
- Free hand swings in lateral arcs counter to the sword arm and drops/overshoots after each
  landing (lagged damped response).
- The sword's step float fades out before the drop, which is a single ease from ~f56.
- Uneven rhythm: one long and one short middle step, varied lift heights.

Round 5 (owner on round 4: "looks like shit. For the backpedal he should just walk backwards.
Simple as that. Don't need to bend his knees and his back"): no crouch, no lean, no raised
guard. Idle height and posture; an upright backward walk of three natural steps with toe-first
landings, one foot always planted, walking-amplitude pelvis dip/sway/yaw, gentle shoulder
counter-rotation, head level; both arms stay in the idle pose with a small float. 2.4 s.
"""
from pathlib import Path
import bpy, importlib.util, math, json
from mathutils import Vector, Matrix, Quaternion

HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
_fs = importlib.util.spec_from_file_location('feedback2', cm.REPO / 'tools/art/blender/feedback/feedback_actions.py'); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OUT = P['out']; c.OWNER = P['owner']

DUR = 2.4  # round 5: back to the original length
KEY_STEP = 0.02  # seconds between authored keys (3 frames at 150 Hz)

# ---------------------------------------------------------------- tunables ----
TUNE = dict(
    # (side, liftoff, contact, y0, y1, x0, x1, lift height)
    # Round 4: uneven rhythm (lifts f4/f16/f31/f41/f55) and varied lift heights.
    # Round 5 (owner: "he should just walk backwards"): upright backward walk, three natural
    # steps R .18 / L .36 / R .18 (feet .18 apart at each plant, like the approved walk's stride).
    steps=[('Right', .22, .62, 0., .18, 0., -.006, .030),
           ('Left', .70, 1.20, 0., .36, 0., 0., .036),
           ('Right', 1.28, 1.68, .18, .36, -.006, 0., .027)],
    release=(1.86, 2.20),            # right foot eases back to its idle height (unweighted) during the rise
    peel=9., land=10., swing_mid=-5., heel_down=.12, peel_window=.08, swing_out=.007,
    travel_window=(.12, .50, 1.42, 1.98), travel_mod=.18, env_end=(2.05, .30),
    hip_forward=0.,
    crouch=[(0, 0), (.30, -.013), (1.70, -.013), (2.05, 0), (2.4, 0)],   # idle height; only what the stride needs
    dip=-.012, dip_delay=.06, dip_width=.08, rise=.004, rise_width=.09,
    sway_amp=.013,
    sway=None,     # derived from steps (weight shifts over the stance foot before each lift)
    # +1 while the right (sword-side) foot reaches back, -1 for the left
    stepsig=None,  # derived from steps
    pelvis_yaw=-4.5, chest_yaw=2.2, roll=-1.8,   # round 4: right hip goes BACK with the right foot; shoulders oppose at half
    body=[(0, 0), (2.4, 0)],                    # lean envelope, releases with the rise
    sword=[(0, 0), (2.4, 0)],   # sword arm stays in the idle ready pose
    guard=[(0, 0), (2.4, 0)],   # no raised guard hand
    lean=0., head_up=0., spine_bob=.25,
    sword_arm=(0., 0.), sword_float=.9, tip_float=-1.0, tip_lag=.06, sword_bob=.25,
    guard_pose=(0., 0., 0.), guard_lag=.085, open_hand=0.,
    free_drift=(3., 0., -2., 3.),   # LeftArm X, LeftArm Z, LeftForeArm X, LeftHand twist (deg per step)
    land_kick=(1.5, .8), land_lag=.05, land_tau=.11, land_period=.30,  # free-hand drop + overshoot after each landing (forearm, arm deg)
    float_fade=(1.72, 2.08),
)

# ---------------------------------------------------------------- curves ------
def pchip(points, t):
    """Monotone cubic Hermite (no overshoot, flat at extrema, zero end slopes)."""
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    if t <= xs[0]: return ys[0]
    if t >= xs[-1]: return ys[-1]
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0: m[i] = 0.
        else:
            w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    i = max(j for j in range(n - 1) if xs[j] <= t)
    s = (t - xs[i]) / h[i]; s2, s3 = s * s, s * s * s
    return ((2 * s3 - 3 * s2 + 1) * ys[i] + (s3 - 2 * s2 + s) * h[i] * m[i]
            + (-2 * s3 + 3 * s2) * ys[i + 1] + (s3 - s2) * h[i] * m[i + 1])


def smooth01(x):
    x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def smoother01(x):
    x = min(1., max(0., x)); return x * x * x * (x * (6 * x - 15) + 10)


def env(t):
    """Locomotion envelope: on after the first weight shift, off once the feet are home."""
    a, w = TUNE['env_end']; return smooth01(t / .16) * smooth01((a - t) / w)


def g(x):
    return math.exp(-x * x)


def bob(t):
    T = TUNE; v = 0.
    for side, lift, contact, *_ in T['steps']:
        v += T['dip'] * g((t - contact - T['dip_delay']) / T['dip_width'])
        v += T['rise'] * g((t - .5 * (lift + contact) - .02) / T['rise_width'])  # passing position
    return v * env(t)


def _derived():
    T = TUNE; st = T['steps']
    if T.get('_sig') is None:
        sig = [(0, 0), (.10, 0)]; sw = [(0, 0), (.06, .3)]
        for i, (side, lift, contact, *_r) in enumerate(st):
            s = 1. if side == 'Right' else -1.; a = .6 if i == len(st) - 1 else 1.
            sig += [(.5 * (lift + contact), s * a), (contact + .03, 0.)]
            sw += [(lift + .10, s * (.75 if i == len(st) - 1 else 1.)), (contact - .01, s * .22)]
        sig += [(DUR, 0)]; sw += [(st[-1][2] + .3, 0), (DUR, 0)]
        T['_sig'] = sig; T['_sway'] = sw
    return T['_sig'], T['_sway']


def stepsig(t): return pchip(_derived()[0], t)
def sway(t): return pchip(_derived()[1], t)


def landing(t):
    """Damped response to each foot landing: drops, then overshoots and settles."""
    T = TUNE; v = 0.
    for side, lift, contact, *_ in T['steps']:
        u = t - contact - T['land_lag']
        if u > 0: v += -math.exp(-u / T['land_tau']) * math.sin(math.tau * u / T['land_period'])
    return v * env(t)


def float_fade(t):
    a, b = TUNE['float_fade']; return 1 - smooth01((t - a) / (b - a))
def body_env(t): return pchip(TUNE['body'], t)


def crouch_frac(t):
    """1 while crouched, falls to 0 through the final stand-up."""
    lo = min(v for _, v in TUNE['crouch']); return max(0., pchip(TUNE['crouch'], t) / lo) if t > 1.2 else 1.


def sword_ready(t): return pchip(TUNE['sword'], t) * crouch_frac(t)
def guard_ready(t): return pchip(TUNE['guard'], t) * crouch_frac(t)
def pelvis_yaw(t): return TUNE['pelvis_yaw'] * stepsig(t)
def chest_yaw(t): return TUNE['chest_yaw'] * stepsig(t - .04)
def roll(t): return TUNE['roll'] * stepsig(t - .02)


_TRAVEL = []


def _travel_table():
    """Pelvis backward travel: integral of a smooth speed profile that is ~22 % faster while
    the body falls onto a reaching foot and slower through each plant; normalised to .36."""
    T = TUNE; a, b, c2, d = T['travel_window']; dt = .001; acc = 0.; tab = [(0., 0.)]
    n = int(DUR / dt)
    for i in range(1, n + 1):
        t = i * dt; base = smooth01((t - a) / (b - a)) * smooth01((d - t) / (d - c2))
        mod = 1.
        for side, lift, contact, *_ in T['steps']:
            if lift < t < contact: mod += T['travel_mod'] * math.sin(math.pi * (t - lift) / (contact - lift))
        acc += base * mod * dt; tab.append((t, acc))
    return [(t, .36 * v / acc) for t, v in tab]


def hip_y(t):
    if not _TRAVEL: _TRAVEL.extend(_travel_table())
    i = min(len(_TRAVEL) - 1, max(0, int(round(t / .001)))); return _TRAVEL[i][1]


def hips_delta(t):
    T = TUNE
    return Vector((T['sway_amp'] * sway(t) * env(t), hip_y(t) + T['hip_forward'] * body_env(t), pchip(T['crouch'], t) + bob(t)))


# ---------------------------------------------------------------- feet --------
FLOOR = {'Left': 0., 'Right': 0.}


def foot_state(side, t):
    """Return (flat-foot ankle offset, pitch degrees +toes-down, pivot kind).
    Before toe-off the heel lifts (pivot on the toe); the swing foot reaches back toes-down,
    lands toe first and rolls down to the heel. After its first landing a foot stands on the
    floor (FLOOR offset); the right foot returns to its idle height only during `release`."""
    T = TUNE; steps = [s for s in T['steps'] if s[0] == side]; fz = FLOOR[side]
    y = x = 0.; z = 0.
    for idx, (_, lift, contact, y0, y1, x0, x1, h) in enumerate(steps):
        z0 = 0. if idx == 0 else fz; z1 = fz
        if t < lift - T['peel_window']:
            return Vector((x0, y0, z0)), 0., None
        if t < lift:
            k = smooth01((t - (lift - T['peel_window'])) / T['peel_window']) ** 1.3
            return Vector((x0, y0, z0)), T['peel'] * k, 'ball'
        if t < contact:
            s = (t - lift) / (contact - lift); e = smoother01(s)
            yy = y0 + (y1 - y0) * e; xx = x0 + (x1 - x0) * e
            zz = z0 + (z1 - z0) * smooth01(s) + h * math.sin(math.pi * s) ** 2
            sign = 1 if side == 'Left' else -1
            pitch = T['peel'] + (T['land'] - T['peel']) * smooth01(s) + T['swing_mid'] * math.sin(math.pi * s) ** 2
            return Vector((xx + sign * T['swing_out'] * math.sin(math.pi * s), yy, zz)), pitch, 'ball'
        if t < contact + T['heel_down']:
            k = 1 - (1 - (t - contact) / T['heel_down']) ** 2.2
            return Vector((x1, y1, z1)), T['land'] * (1 - smooth01(k)), 'ball'
        y, x, z = y1, x1, z1
    if steps and abs(fz) > 1e-9:
        r0, r1 = T['release']; z = fz * (1 - smoother01((t - r0) / (r1 - r0)))
    return Vector((x, y, z)), 0., None


SOLE = {}


def sole_pivots():
    """Toe-tip and heel-back contact points of each sole, from the evaluated idle mesh."""
    s = bpy.context.scene; c.at(0); body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    gid = {g.index: g.name for g in body.vertex_groups}; dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
    for sd in ('Left', 'Right'):
        pts = [ev.matrix_world @ v.co for v in me.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, '').startswith((sd + 'Foot', sd + 'ToeBase'))) > .5]
        z0 = min(p.z for p in pts); low = [p for p in pts if p.z < z0 + .012]
        x = sum(p.x for p in low) / len(low)
        SOLE[sd] = {'toe': Vector((x, min(p.y for p in low), z0)), 'heel': Vector((x, max(p.y for p in low), z0))}
        FLOOR[sd] = -z0 if z0 > .001 else 0.
    ev.to_mesh_clear(); return {k: {a: list(b) for a, b in v.items()} for k, v in SOLE.items()} | {'floor': dict(FLOOR)}


def foot_matrix(side, t, world):
    m0 = world[side + 'Foot'].copy(); off, pitch, kind = foot_state(side, t)
    m = Matrix.Translation(off) @ m0
    if kind and abs(pitch) > 1e-9:
        pivot = SOLE[side]['toe' if kind == 'ball' else 'heel'] + off
        m = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(pitch), 4, 'X') @ Matrix.Translation(-pivot) @ m
    return m


# ---------------------------------------------------------------- author ------
def wr(fk, name, axis, degrees):
    if abs(degrees) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy()
    b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(degrees), 4, axis) @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def lr(fk, name, degrees):
    """Twist a bone about its own length axis."""
    if abs(degrees) < 1e-9: return
    b = fk.pose.bones[name]; m = b.matrix.copy(); ax = (b.tail - b.head).normalized()
    b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(degrees), 4, ax) @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


FINGERS = ('LeftHandThumb', 'LeftHandIndex', 'LeftHandMiddle', 'LeftHandRing', 'LeftHandPinky')


def pose_body(fk, base, t):
    T = TUNE; rs = sword_ready(t); rg = guard_ready(t); be = body_env(t); e = env(t); bn = bob(t) / abs(T['dip'])
    for b in fk.pose.bones: b.matrix_basis = base[b.name]
    hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ hips_delta(t)
    bpy.context.view_layer.update()
    py, cy = pelvis_yaw(t), chest_yaw(t)
    # Pelvis turns against the shoulders each step and drops on the swing side.
    wr(fk, 'Hips', 'Z', py); wr(fk, 'Hips', 'Y', roll(t))
    # Spine: low fighter lean; the twist is spread up the spine with small lags so the chest
    # arrives at its own yaw a beat after the pelvis.
    twist1 = chest_yaw(t - .01) - py; twist2 = cy - py
    wr(fk, 'Spine', 'X', T['lean'] * .55 * be + T['spine_bob'] * bn * e)
    wr(fk, 'Spine', 'Z', .45 * twist1); wr(fk, 'Spine', 'Y', -.6 * roll(t - .04))
    wr(fk, 'Spine1', 'X', T['lean'] * .45 * be); wr(fk, 'Spine1', 'Z', .30 * twist2); wr(fk, 'Spine1', 'Y', -.45 * roll(t - .07))
    wr(fk, 'Spine2', 'Z', .25 * twist2 + .55 * (twist2 - twist1)); wr(fk, 'Spine2', 'X', .35 * math.sin(math.tau * t / 1.2) * e)
    # Head stays aimed at the enemy against the shoulder turn and lean.
    wr(fk, 'Neck', 'X', .4 * T['head_up'] * be)
    wr(fk, 'Head', 'X', .6 * T['head_up'] * be - .4 * bn * e)
    wr(fk, 'Neck', 'Z', -.4 * chest_yaw(t - .06)); wr(fk, 'Head', 'Z', -.45 * chest_yaw(t - .1)); wr(fk, 'Head', 'Y', .35 * roll(t - .12))
    # Sword arm: low guard aimed at the enemy; the arm keeps the point centred against the chest turn,
    # dips and settles after each plant.
    sa, sf = T['sword_arm']
    wr(fk, 'RightArm', 'Z', -.55 * chest_yaw(t - .05))
    ff = float_fade(t) * e  # the step float fades out before the blade drop so the drop is one ease
    wr(fk, 'RightArm', 'X', sa * rs + T['sword_bob'] * bob(t - .09) / abs(T['dip']) * ff)
    wr(fk, 'RightForeArm', 'X', sf * rs + T['sword_float'] * bob(t - .11) / abs(T['dip']) * ff)
    wr(fk, 'RightHand', 'X', T['tip_float'] * bob(t - .11 - T['tip_lag']) / abs(T['dip']) * ff)
    # Free hand: raised open guard; drifts and turns with every weight shift, trailing the torso.
    ga, gb, gf = T['guard_pose']; lag = T['guard_lag']; dx, dz, df, dh = T['free_drift']
    s1 = stepsig(t - lag) * e; s2 = stepsig(t - lag - .05) * e
    lk, la = T['land_kick']; ld = landing(t)
    wr(fk, 'LeftArm', 'Z', dz * s1)   # lateral arc counter to the sword arm, riding the chest turn
    wr(fk, 'LeftArm', 'X', ga * rg + .5 * bob(t - lag) / abs(T['dip']) * e + dx * s1 + la * ld)
    wr(fk, 'LeftArm', 'Y', gb * rg - 1.0 * roll(t - .1))
    wr(fk, 'LeftForeArm', 'X', gf * rg + .8 * bob(t - lag - .04) / abs(T['dip']) * e + df * s2 + lk * landing(t - .03))
    lr(fk, 'LeftHand', dh * stepsig(t - lag - .09) * e)
    # Open the guard hand: straighten each finger segment toward its parent's direction.
    k = T['open_hand'] * max(0., guard_ready(t - .05) if t > .05 else 0.)
    k = min(1., k)
    if k > 0:
        for b in fk.pose.bones:
            if b.name.startswith(FINGERS) and b.parent:
                pd = (b.parent.tail - b.parent.head).normalized(); bd = (b.tail - b.head).normalized()
                ax = pd.cross(bd)
                if ax.length > 1e-4:
                    ang = pd.angle(bd) * (k * (.6 if 'Thumb' in b.name else 1.))
                    m = b.matrix.copy(); b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(-ang, 4, ax.normalized()) @ m.to_3x3().to_4x4()
                    bpy.context.view_layer.update()


def set_length():
    s = bpy.context.scene; end = round(DUR * 150)
    s['duration'] = DUR; s.frame_start = 0; s.frame_end = end; s.render.fps = 150; s.render.fps_base = 1
    return end


def author():
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'backpedal', 'open_job(backpedal) first'
    _TRAVEL.clear(); TUNE['_sig'] = None
    fk = bpy.data.objects['Pose_Control_Rig']; sole = sole_pivots(); c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    world = {b.name: b.matrix.copy() for b in fk.pose.bones}
    assert fk.matrix_world == Matrix.Identity(4)
    end = set_length(); fps = s.render.fps
    fk.animation_data_clear()
    targets = {sd: bpy.data.objects[sd + 'Leg_Target'] for sd in ('Left', 'Right')}
    poles = {sd: bpy.data.objects[sd + 'Leg_Pole'] for sd in ('Left', 'Right')}
    for o in (*targets.values(), *poles.values()): f.reset_animation(o)
    # The wrist-following hilt keeps two keys; move its last key to the new end frame.
    hilt = bpy.data.objects['Hilt_Control']
    if hilt.animation_data and hilt.animation_data.action:
        for fc in c.curves(hilt.animation_data.action):
            kp = sorted(fc.keyframe_points, key=lambda k: k.co.x)
            if len(kp) >= 2 and all(abs(k.co.y - kp[0].co.y) < 1e-9 for k in kp):
                d = end - kp[-1].co.x; kp[-1].co.x += d; kp[-1].handle_left.x += d; kp[-1].handle_right.x += d
    L = {sd: (world[sd + 'Leg'].translation - world[sd + 'UpLeg'].translation).length + (world[sd + 'Foot'].translation - world[sd + 'Leg'].translation).length for sd in targets}
    polebase = {}
    for sd in targets:
        a, mid, endp = [world[sd + n].translation for n in ('UpLeg', 'Leg', 'Foot')]
        axis = (endp - a).normalized(); d = mid - a - axis * (mid - a).dot(axis)
        polebase[sd] = mid + d.normalized() * .3
    prev = {}; reach = {sd: 0. for sd in targets}; n = round(DUR / KEY_STEP)
    for i in range(n + 1):
        t = min(DUR, i * KEY_STEP); fr = t * fps
        pose_body(fk, base, t)
        for b in fk.pose.bones: c.key(b, fr, prev)
        dh = hips_delta(t)
        for sd in targets:
            m = foot_matrix(sd, t, world); tg = targets[sd]; tg.matrix_basis = m; c.key(tg, fr, prev)
            off = foot_state(sd, t)[0]
            pb = polebase[sd].copy(); aligned = world[sd + 'Foot'].translation.x + off.x + (.01 if sd == 'Left' else -.01)
            pb.x = pb.x + (aligned - pb.x) * body_env(t)  # knees track over the feet, not splayed
            pl = poles[sd]; pl.location = pb + Vector((dh.x * .5, .5 * (dh.y + off.y), .5 * dh.z)); pl.keyframe_insert('location', frame=fr)
            if .2 < t < 1.9: reach[sd] = max(reach[sd], (fk.pose.bones[sd + 'UpLeg'].head - m.translation).length / L[sd])
    for o in (fk, *targets.values(), *poles.values()): c.smooth(o)
    tx = bpy.data.texts.get('feedback_v4_backpedal.py') or bpy.data.texts.new('feedback_v4_backpedal.py'); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s['root_motion'] = 'backward .36'; s['backpedal_v4'] = json.dumps({'round': 5, 'duration': DUR, 'steps': TUNE['steps'], 'keyStep': KEY_STEP, 'interpolation': 'BEZIER AUTO_CLAMPED'})
    c.at(0)
    return {'keys': n + 1, 'frameEnd': end, 'maxLegReach': reach, 'fps': fps, 'sole': sole}


def probe(times=(0, .3, .46, .77, 1.2, 1.92, 2.4)):
    """Sample evaluated FK hips / targets (sanity)."""
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; out = {}
    for t in times:
        c.at(t * s.render.fps)
        out[t] = {'hips': list(fk.pose.bones['Hips'].head), 'L': list(bpy.data.objects['LeftLeg_Target'].matrix_world.translation), 'R': list(bpy.data.objects['RightLeg_Target'].matrix_world.translation)}
    return out


def bake_only():
    """Bake the deform action from the controls for inspection between iterations. approved_actions.bake()
    always saves/exports at its end, so point it at a scratch folder inside the v4 output dir
    (never the delivered scene); the final candidate is written only by revise.rebake()."""
    s = bpy.context.scene; assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'backpedal'
    old = c.OUT; c.OUT = cm.check_writable(P['out'] / 'backpedal-iter')
    try:
        c.bake()
    finally:
        c.OUT = old
    return {'baked': True, 'frameEnd': s.frame_end, 'file': bpy.data.filepath}


# ---------------------------------------------------------------- round-3 diagnostics ----
TIPIDX = {}


def soles(step=5, frames=None):
    """Per-frame (30 fps at step=5) lowest evaluated sole-mesh vertex of BOTH feet (world z),
    plus hips/head height, sword tip and free-hand position. Reads the baked deform result."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    gid = {g.index: g.name for g in body.vertex_groups}
    sole = {sd: [v.index for v in body.data.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, '').startswith((sd + 'Foot', sd + 'ToeBase'))) > .5] for sd in ('Left', 'Right')}
    sword = [o for o in s.objects if o.type == 'MESH' and o.get('review_attachment')]
    rows = []
    for fr in (frames or range(0, s.frame_end + 1, step)):
        s.frame_set(fr); dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
        row = {'f30': round(fr / s.render.fps * 30, 2), 't': round(fr / s.render.fps, 4)}
        for sd in ('Left', 'Right'):
            pts = [mw @ me.vertices[i].co for i in sole[sd]]
            row[sd[0]] = round(min(p.z for p in pts) * 1000, 1)
            row[sd[0] + 'y'] = round(sum(p.y for p in pts) / len(pts), 4)
            lowp = [p for p in pts if p.z < min(q.z for q in pts) + .006]; row[sd[0] + 'cx'] = round(sum(p.x for p in lowp) / len(lowp), 4); row[sd[0] + 'cy'] = round(sum(p.y for p in lowp) / len(lowp), 4)
        ev.to_mesh_clear()
        hb = lambda n: rig.matrix_world @ rig.pose.bones[n].head
        row['hipZ'] = round(hb('Hips').z, 4); row['hipY'] = round(hb('Hips').y, 4); row['headZ'] = round(hb('Head').z, 4)
        tip = None
        for o in sword:
            e = o.evaluated_get(dg); m = e.to_mesh(); w = e.matrix_world
            if o.name not in TIPIDX:
                hand = hb('RightHand'); TIPIDX[o.name] = max(range(len(m.vertices)), key=lambda i: ((w @ m.vertices[i].co) - hand).length)
            p = w @ m.vertices[TIPIDX[o.name]].co; e.to_mesh_clear()
            tip = p if tip is None or (p - hb('RightHand')).length > (tip - hb('RightHand')).length else tip
        if tip is not None: row['tip'] = [round(tip.x, 4), round(tip.y, 4), round(tip.z, 4)]
        lh = hb('LeftHand'); row['lh'] = [round(lh.x, 4), round(lh.y, 4), round(lh.z, 4)]
        lhh = lh - hb('Hips'); row['lhh'] = [round(lhh.x, 4), round(lhh.y, 4), round(lhh.z, 4)]
        lc = (rig.matrix_world @ rig.pose.bones['Spine2'].matrix).inverted() @ lh; row['lhc'] = [round(lc.x, 4), round(lc.y, 4), round(lc.z, 4)]
        # pelvis vs shoulder yaw (deg) from the bone line between thighs and between upper arms
        def yawof(a, b):
            d = hb(a) - hb(b); return math.degrees(math.atan2(d.y, d.x))
        row['pelvisYaw'] = round(yawof('LeftUpLeg', 'RightUpLeg'), 2); row['shoulderYaw'] = round(yawof('LeftArm', 'RightArm'), 2)
        rows.append(row)
    return rows


def foot_shape(fr=0):
    """Toe/heel/inner/outer lowest-zone heights of each sole at a frame (mm), and foot bone matrices."""
    s = bpy.context.scene; s.frame_set(fr); rig = bpy.data.objects['Knight_Deform']
    body = next(o for o in s.objects if o.type == 'MESH' and o.get('export_body') and not o.get('review_prop'))
    gid = {g.index: g.name for g in body.vertex_groups}; dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
    out = {}
    for sd in ('Left', 'Right'):
        pts = [mw @ v.co for v in me.vertices if sum(gg.weight for gg in v.groups if gid.get(gg.group, '').startswith((sd + 'Foot', sd + 'ToeBase'))) > .5]
        ys = [p.y for p in pts]; y0, y1 = min(ys), max(ys)
        def zone(a, b): q = [p.z for p in pts if y0 + a * (y1 - y0) <= p.y <= y0 + b * (y1 - y0)]; return round(min(q) * 1000, 1)
        out[sd] = {'n': len(pts), 'yRange': [round(y0, 4), round(y1, 4)], 'toeZone': zone(0, .25), 'midZone': zone(.4, .6), 'heelZone': zone(.75, 1),
                   'footHead': [round(x, 4) for x in rig.matrix_world @ rig.pose.bones[sd + 'Foot'].head], 'toeHead': [round(x, 4) for x in rig.matrix_world @ rig.pose.bones[sd + 'ToeBase'].head]}
    ev.to_mesh_clear(); return out


def feet_strip(scene_file, label, step=5, views=('side', 'front'), cy_fixed=.14, loop=False):
    """Feet-only ground-line renders of every 30 fps frame (side + front), with a thin red bar at
    z=0 (temporary object, never saved). Opens scene_file (re-tags owner); PNGs under <out>/renders/<label>/."""
    cm.open_tagged(Path(scene_file), P['owner']); s = bpy.context.scene; assert s['session_owner'] == P['owner']
    cam = s.camera; folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    me = bpy.data.meshes.new('tmp_groundline'); me.from_pydata([(-3, -2, -.0015), (3, -2, -.0015), (3, 2, -.0015), (-3, 2, -.0015), (-3, -2, -.004), (3, -2, -.004), (3, 2, -.004), (-3, 2, -.004)], [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    gl = bpy.data.objects.new('tmp_groundline', me); s.collection.objects.link(gl); gl.color = (.9, .1, .1, 1)
    s.render.resolution_x = 720; s.render.resolution_y = 240; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_attachment'): o.color = (.7, .32, .06, 1)
    out = []
    st = s.render.fps / 30.; nfr = int(math.floor(s.frame_end / st + 1e-6)) + (0 if loop else 1)
    for i30 in range(nfr):
        fr = i30 * st; s.frame_set(int(fr), subframe=fr - int(fr)); rig = bpy.data.objects['Knight_Deform']
        cy = cy_fixed  # fixed camera: a planted foot must not move in the strip
        for v in views:
            fx = .5 * ((rig.matrix_world @ rig.pose.bones['LeftFoot'].head).x + (rig.matrix_world @ rig.pose.bones['RightFoot'].head).x)
            d = Vector((1, 0, 0)) if v == 'side' else Vector((0, -1, 0)); center = Vector((0, cy, .07)) if v == 'side' else Vector((round(fx * 4) / 4, 0, .07))  # front: snaps in 0.25 steps so planted feet stay still between snaps
            cam.location = center + d * 5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = .84 if v == 'side' else .6
            s.render.filepath = str(folder / f'feet-{v}-{i30:04d}.png'); bpy.ops.render.render(write_still=True); out.append(s.render.filepath)
    bpy.data.objects.remove(gl, do_unlink=True); bpy.data.meshes.remove(me)
    return {'folder': str(folder), 'frames': len(out)}


def views(scene_file, label, step=5, res=520, zoom=.85, cz=None, track_x=True, loop=False, only=None, track=True):
    """Tracked full-body review renders of every 30 fps frame: front, side, three-quarter.
    Camera follows the travel (hips y) so the body stays large in frame. Never saves."""
    if scene_file: cm.open_tagged(Path(scene_file), P['owner'])
    s = bpy.context.scene; assert s['session_owner'] == P['owner']
    cam = s.camera; folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = res; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_attachment'): o.color = (.7, .32, .06, 1)
    me = bpy.data.meshes.new('tmp_floor'); me.from_pydata([(-3, -3, -.002), (3, -3, -.002), (3, 3, -.002), (-3, 3, -.002)], [], [(0, 1, 2, 3)])
    fl = bpy.data.objects.new('tmp_floor', me); s.collection.objects.link(fl); fl.color = (.16, .17, .19, 1)
    V = {'front': ((0, -4, .5), Vector((0, 0, .5)), 1.35), 'side': ((4, 0, .5), Vector((0, -.32, .5)), 1.75), 'threequarter': ((2.8, -4, 1.), Vector((0, -.2, .45)), 1.6)}
    if zoom != 1. or cz is not None:
        V = {k: (xyz, Vector((off.x, off.y, cz if cz is not None else off.z)), sc * zoom) for k, (xyz, off, sc) in V.items()}
    n = 0; rig = bpy.data.objects['Knight_Deform']
    st = s.render.fps / 30.; nfr = int(math.floor(s.frame_end / st + 1e-6)) + (0 if loop else 1)
    for i30 in range(nfr):  # every 30 fps frame regardless of scene rate; loop: skip the closing frame
        fr = i30 * st; s.frame_set(int(fr), subframe=fr - int(fr)); hp = rig.matrix_world @ rig.pose.bones['Hips'].head; hy = hp.y; hx = hp.x if track_x else 0.
        for v, (xyz, off, scale) in V.items():
            if only and v not in only: continue
            d = Vector(xyz).normalized(); center = off + (Vector((hx if v != 'side' else 0., hy, 0)) if track else Vector((0, 0, 0)))
            cam.location = center + d * 5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = scale
            s.render.filepath = str(folder / f'{v}-full-{i30:04d}.png'); bpy.ops.render.render(write_still=True); n += 1
    bpy.data.objects.remove(fl, do_unlink=True); bpy.data.meshes.remove(me)
    return {'folder': str(folder), 'frames': n}


def hand_jacobian(t=1.0):
    """Hand displacement (mm, world) for +10 deg world rotations of LeftArm / LeftForeArm at time t (FK rig)."""
    fk = bpy.data.objects['Pose_Control_Rig']; s = bpy.context.scene; c.at(0)
    base = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}; out = {}
    for bone in ('LeftArm', 'LeftForeArm'):
        for ax in ('X', 'Y', 'Z'):
            pose_body(fk, base, t); h0 = fk.pose.bones['LeftHand'].head.copy()
            wr(fk, bone, ax, 10.); h1 = fk.pose.bones['LeftHand'].head.copy()
            out[bone + ax] = [round(1000 * v, 1) for v in (h1 - h0)]
    pose_body(fk, base, t); rel = fk.pose.bones['LeftHand'].head - fk.pose.bones['LeftArm'].head
    for b in fk.pose.bones: b.matrix_basis = base[b.name]
    s.frame_set(0); return {'jac': out, 'handFromShoulder': [round(v, 3) for v in rel]}


def hand_check(frames=(60, 90, 120, 150, 180)):
    s = bpy.context.scene; fk = bpy.data.objects['Pose_Control_Rig']; rig = bpy.data.objects['Knight_Deform']; tg = bpy.data.objects['LeftArm_Target']
    out = {}
    for fr in frames:
        s.frame_set(fr)
        out[fr] = {'fk': [round(v, 3) for v in fk.matrix_world @ fk.pose.bones['LeftHand'].head], 'def': [round(v, 3) for v in rig.matrix_world @ rig.pose.bones['LeftHand'].head],
                   'tgt': [round(v, 3) for v in tg.matrix_world.translation], 'cons': [(cn.type, getattr(cn, 'subtarget', '')) for cn in tg.constraints], 'tgtAnim': bool(tg.animation_data and tg.animation_data.action)}
    return out


def critic_views(scene_file, label, loop=False, views_=('front', 'side', 'threequarter')):
    """Renders exactly like feedback_v4/render.py capture(full=True): 480 px, ortho 2.35, fixed center (0,0,0.7), same view
    directions, every 30 fps frame. Lets pixel numbers be quoted in the critic's 480 px cell scale. Never saves."""
    if scene_file: cm.open_tagged(Path(scene_file), P['owner'])
    s = bpy.context.scene; cam = s.camera; folder = cm.check_writable(P['out'] / 'renders' / label); folder.mkdir(parents=True, exist_ok=True)
    s.render.resolution_x = s.render.resolution_y = 480; s.display.shading.color_type = 'OBJECT'
    for o in s.objects:
        if o.get('export_body'): o.color = (.53, .55, .6, 1)
        if o.get('review_prop'): o.color = (.7, .32, .06, 1)
        if o.get('review_attachment'): o.color = (.25, .16, .07, 1)
    V = {'front': (0, -4, .5), 'side': (4, 0, .5), 'threequarter': (2.8, -4, 1.)}; n = 0
    st = s.render.fps / 30.; nfr = int(math.floor(s.frame_end / st + 1e-6)) + (0 if loop else 1)
    for i30 in range(nfr):
        fr = i30 * st; s.frame_set(int(fr), subframe=fr - int(fr))
        for v in views_:
            d = Vector(V[v]).normalized(); cam.location = Vector((0, 0, .7)) + d * 5; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler(); cam.data.ortho_scale = 2.35
            s.render.filepath = str(folder / f'{v}-full-{i30:04d}.png'); bpy.ops.render.render(write_still=True); n += 1
    return {'folder': str(folder), 'frames': n}
