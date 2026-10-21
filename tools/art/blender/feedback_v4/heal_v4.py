"""Heal v4: living idle body under the approved drink (owner 2026-10-21: "the rest of his body
is completely frozen so it looks inhumane ... idling but healing"). Execute ONLY inside the
owned Blender MCP session via run.py.

  1. sample_idle()      opens the APPROVED IdleOneHand rebuild scene read-only (never saves),
                        samples its native control rig (FK poses, leg targets/poles) and writes
                        the samples to a scratch JSON.
  2. revise.py open_job('heal'), then author(): the v3 drink is preserved exactly in the
     frame that matters - the left-hand target/pole curves are re-expressed relative to the
     moving chest (low phases) and moving head (at the mouth), so cup-to-mouth stays as
     authored while the body breathes, shifts weight and floats the sword like the approved
     idle. Added layers: head tilts back as he drinks, drinking-side clavicle rises with the
     cup, post-drink settle/exhale. All layers are zero at 0 and 2.4 s (idle endpoints).
  3. revise.py rebake('heal').
Cup mesh, handle grip, fingers and 2.4 s timing are untouched.
"""
from pathlib import Path
import bpy, importlib.util, math, json
from mathutils import Vector, Matrix, Quaternion

HERE = Path(__file__).resolve().parent
_cs = importlib.util.spec_from_file_location('veyr_v4_common', HERE / 'common.py'); cm = importlib.util.module_from_spec(_cs); _cs.loader.exec_module(cm)
P = cm.params(globals().get('VEYR_V4_PARAMS'))
_fs = importlib.util.spec_from_file_location('feedback2', cm.REPO / 'tools/art/blender/feedback/feedback_actions.py'); f = importlib.util.module_from_spec(_fs); _fs.loader.exec_module(f)
c = f.c; c.OUT = P['out']; c.OWNER = P['owner']
DUR = 2.4; IDLE_DUR = 4.0; KEY_STEP = .02
IDLE_SCENE = cm.REPO / 'Local/Blender/approved-rebuild-20261021/idle_one_Blender_v1.blend'
SAMPLES = Path('/Users/midir/fable-heal-tmp/idle_samples.json')
TIMES = [round(i * KEY_STEP, 4) for i in range(round(DUR / KEY_STEP) + 1)]
LEFT_ARM = ('LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand')  # LeftHand* covers fingers

TUNE = dict(
    tau_scale=IDLE_DUR / DUR,       # one full approved idle cycle under the 2.4 s drink
    # head-follow weight for the cup: 0 = rides the chest, 1 = rides the head (at the mouth)
    follow=[(0, 0), (.18, 0), (.35, .15), (.65, .6), (.95, 1), (1.7, 1), (2.0, .6), (2.25, .15), (2.4, 0)],
    head_tilt=[(0, 0), (.65, -1.5), (.95, -6), (1.2, -9), (1.45, -9.5), (1.7, -6), (2.0, -1), (2.4, 0)],  # deg, back
    clav=[(0, 0), (.35, -2), (.65, -5), (.95, -7), (1.7, -7), (2.0, -3), (2.4, 0)],                      # deg, raise
    settle=[(0, 0), (1.95, 0), (2.12, 1.), (2.28, .35), (2.4, 0)],                                       # exhale / sink
    settle_drop=-.004, settle_chest=2.0, settle_t=2.06, settle_w=.13,
    # The approved idle only breathes (shoulders/spine/arms). Added: slow weight shift onto the
    # sword-side foot while drinking, pelvis list + knee give, sword-arm float, head micro-motion.
    shift=[(0, 0), (.4, -.004), (1.0, -.011), (1.6, -.012), (2.1, -.003), (2.4, 0)],
    shift_roll=3.0, shift_yaw=1.8, give=-.007, breath_period=1.2, shift_amp=-.018,
    chest_breath=-1.4, clav_breath=1.6, hip_breath=.0016,
)


def env(t): return math.sin(math.pi * min(max(t / DUR, 0.), 1.)) ** 2


def breath(t): return math.sin(math.tau * t / TUNE['breath_period']) * env(t)


# r2 (2026-10-21, takeover): every layer must vanish at 0 and 2.4 s, including lagged ones
# (i1 failed the translated-idle endpoint by 0.5 mm because lagged layers were still non-zero).
def breath_l(t, lag): return math.sin(math.tau * (t - lag) / TUNE['breath_period']) * env(t)


def lagged_env(t, k=1.14):  # zero at both ends, peak shifted later (follow-through lag)
    u = min(max(t / DUR, 0.), 1.); return math.sin(math.pi * u ** k) ** 2


def shift_f(t):  # continuous weight transfer onto the sword-side foot and back (no plateau)
    return TUNE['shift_amp'] * env(t)


def settle_f(t):  # smooth exhale/sink after the cup is lowered, gone by 2.4 s
    return math.exp(-((t - TUNE['settle_t']) / TUNE['settle_w']) ** 2) * (1 - min(max(t / DUR, 0.), 1.) ** 14)


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


def _flat(m): return [x for row in m for x in row]
def _mat(v): return Matrix([v[0:4], v[4:8], v[8:12], v[12:16]])


def sample_idle():
    """Read-only sampling of the approved one-hand idle control rig. Never saves."""
    cm.open_tagged(IDLE_SCENE, P['owner']); s = bpy.context.scene; fps = s.render.fps
    assert s.get('rebuild_job') == 'idle_one', s.get('rebuild_job')
    fk = bpy.data.objects['Pose_Control_Rig']; out = {'fps': fps, 'frames': {}, 'duration': s.get('duration')}
    names = ['LeftLeg_Target', 'RightLeg_Target', 'LeftLeg_Pole', 'RightLeg_Pole']
    for t in TIMES:
        tau = min(IDLE_DUR, t * TUNE['tau_scale']); c.at(tau * fps)
        out['frames'][str(t)] = {'fk': {b.name: _flat(b.matrix_basis) for b in fk.pose.bones},
                                 'obj': {n: _flat(bpy.data.objects[n].matrix_world) for n in names}}
    SAMPLES.write_text(json.dumps(out))
    hd = [Vector(_mat(out['frames'][str(t)]['fk']['Hips'])[i][3] for i in range(3)) for t in TIMES]
    return {'samples': len(TIMES), 'hipsLocRange': [max(v[k] for v in hd) - min(v[k] for v in hd) for k in range(3)], 'file': str(SAMPLES)}


def _rot_about(b, axis, deg):
    if abs(deg) < 1e-9: return
    m = b.matrix.copy(); b.matrix = Matrix.Translation(m.translation) @ Matrix.Rotation(math.radians(deg), 4, axis.normalized()) @ m.to_3x3().to_4x4()
    bpy.context.view_layer.update()


def _blend(a, b, w):
    """Blend two near-identity rigid transforms."""
    q = a.to_quaternion().slerp(b.to_quaternion(), w); tr = a.translation.lerp(b.translation, w)
    return Matrix.LocRotScale(tr, q, Vector((1, 1, 1)))


def author():
    s = bpy.context.scene
    assert s.get('session_owner') == P['owner'] and s.get('rebuild_job') == 'heal', 'open_job(heal) first'
    data = json.loads(SAMPLES.read_text()); fps = s.render.fps; T = TUNE
    fk = bpy.data.objects['Pose_Control_Rig']; tgt = bpy.data.objects['LeftArm_Target']; pole = bpy.data.objects['LeftArm_Pole']
    legs = {n: bpy.data.objects[n] for n in ('LeftLeg_Target', 'RightLeg_Target', 'LeftLeg_Pole', 'RightLeg_Pole')}
    # 1. Record the approved v3 drink exactly as evaluated (world), plus original FK of the left arm/fingers.
    orig = {}
    for t in TIMES:
        c.at(t * fps)
        orig[t] = {'tgt': tgt.matrix_world.copy(), 'pole': pole.matrix_world.translation.copy(),
                   'left': {b.name: b.matrix_basis.copy() for b in fk.pose.bones if b.name.startswith(LEFT_ARM)}}
    c.at(0)
    C0 = fk.matrix_world @ fk.pose.bones['Spine2'].matrix; H0 = fk.matrix_world @ fk.pose.bones['Head'].matrix
    base0 = {b.name: b.matrix_basis.copy() for b in fk.pose.bones}
    idle0 = {n: _mat(v) for n, v in data['frames']['0.0']['fk'].items()}
    basediff = max(max(abs(a - b) for a, b in zip(_flat(base0[n]), _flat(idle0[n]))) for n in base0 if not n.startswith(LEFT_ARM))
    # 2. Rewrite controls.
    fk.animation_data_clear()
    for o in (tgt, pole, *legs.values()): f.reset_animation(o)
    prev = {}; stillest = {}
    for t in TIMES:
        fr = t * fps; smp = data['frames'][str(t)]
        for b in fk.pose.bones:
            b.matrix_basis = orig[t]['left'][b.name] if b.name in orig[t]['left'] else _mat(smp['fk'][b.name])
        # LeftShoulder breathes with the idle too (its idle basis), the clavicle then rises with the cup.
        fk.pose.bones['LeftShoulder'].matrix_basis = _mat(smp['fk']['LeftShoulder'])
        st = settle_f(t); sh = shift_f(t); shn = sh / abs(T['shift_amp'])
        hips = fk.pose.bones['Hips']; hips.location += fk.data.bones['Hips'].matrix_local.to_3x3().inverted() @ Vector((sh, 0, T['settle_drop'] * st + T['give'] * abs(shn) + T['hip_breath'] * breath_l(t, .05)))
        bpy.context.view_layer.update()
        _rot_about(hips, Vector((0, 1, 0)), -T['shift_roll'] * shn)          # free (left) hip drops as weight goes right
        _rot_about(hips, Vector((0, 0, 1)), T['shift_yaw'] * shn)
        _rot_about(fk.pose.bones['Spine'], Vector((0, 1, 0)), .8 * T['shift_roll'] * T['shift_amp'] * lagged_env(t) / abs(T['shift_amp']))  # chest stays level, lags
        C = fk.matrix_world @ fk.pose.bones['Spine2'].matrix
        Rc = (C.to_quaternion() @ C0.to_quaternion().inverted())
        _rot_about(fk.pose.bones['Spine1'], Rc @ Vector((1, 0, 0)), T['settle_chest'] * st)       # exhale/sink after lowering
        _rot_about(fk.pose.bones['Spine2'], Rc @ Vector((1, 0, 0)), T['chest_breath'] * breath_l(t, 0.))  # chest lifts on the inhale
        _rot_about(fk.pose.bones['RightShoulder'], Rc @ Vector((0, 1, 0)), T['clav_breath'] * breath_l(t, .06))
        _rot_about(fk.pose.bones['LeftShoulder'], Rc @ Vector((0, 1, 0)), pchip(T['clav'], t) - T['clav_breath'] * breath_l(t, .06))   # clavicle lifts with cup + breath
        _rot_about(fk.pose.bones['Head'], Rc @ Vector((1, 0, 0)), pchip(T['head_tilt'], t))       # tilt back to drink
        _rot_about(fk.pose.bones['Head'], Rc @ Vector((0, 0, 1)), 1.6 * math.sin(math.tau * t / 1.9 + .6) * env(t))
        _rot_about(fk.pose.bones['Head'], Rc @ Vector((0, 1, 0)), 1.1 * math.sin(math.tau * t / 2.4 + 1.1) * env(t) + .8 * shn)
        _rot_about(fk.pose.bones['RightArm'], Rc @ Vector((1, 0, 0)), -2.4 * breath_l(t, .1))     # sword arm floats with the breath
        _rot_about(fk.pose.bones['RightForeArm'], Rc @ Vector((1, 0, 0)), -1.8 * breath_l(t, .18))
        for b in fk.pose.bones: c.key(b, fr, prev)
        for n, o in legs.items():
            m = _mat(smp['obj'][n])
            if 'Pole' in n: o.location = m.translation; o.keyframe_insert('location', frame=fr)
            else: o.matrix_basis = m; c.key(o, fr, prev)
        C = fk.matrix_world @ fk.pose.bones['Spine2'].matrix; H = fk.matrix_world @ fk.pose.bones['Head'].matrix
        Ac = C @ C0.inverted(); Ah = H @ H0.inverted(); A = _blend(Ac, Ah, pchip(T['follow'], t))
        tgt.matrix_basis = A @ orig[t]['tgt']; c.key(tgt, fr, prev)
        pole.location = Ac @ orig[t]['pole']; pole.keyframe_insert('location', frame=fr)
    for o in (fk, tgt, pole, *legs.values()): c.smooth(o)
    tx = bpy.data.texts.get('feedback_v4_heal.py') or bpy.data.texts.new('feedback_v4_heal.py'); tx.clear(); tx.write(Path(__file__).read_text()); tx.use_fake_user = True
    s['heal_v4'] = json.dumps({'idleReference': str(IDLE_SCENE.name), 'tauScale': T['tau_scale'], 'keyStep': KEY_STEP})
    c.at(0)
    return {'keys': len(TIMES), 'baseVsIdleMaxDiff': basediff}


def stillness(threshold=1e-4, window=.3):
    """Longest interval any deform bone (or the cup) stays within `threshold` of its position."""
    s = bpy.context.scene; rig = bpy.data.objects['Knight_Deform']; fps = s.render.fps
    cup = bpy.data.objects.get('DrinkingCup'); pos = {}
    for fr in range(0, s.frame_end + 1):
        s.frame_set(fr)
        for b in rig.pose.bones:
            if b.name.startswith(('LeftHand', 'RightHand')) and b.name not in ('LeftHand', 'RightHand'): continue
            pos.setdefault(b.name, []).append((rig.matrix_world @ b.tail).copy())
        if cup: pos.setdefault('cup', []).append(cup.matrix_world.translation.copy())
    worst = {}
    for n, ps in pos.items():
        run = best = 0
        for a, b in zip(ps, ps[1:]):
            run = run + 1 if (a - b).length < threshold / fps * 30 else 0; best = max(best, run)
        worst[n] = best / fps
    top = sorted(worst.items(), key=lambda kv: -kv[1])[:8]
    return {'longestStillSeconds': top}
