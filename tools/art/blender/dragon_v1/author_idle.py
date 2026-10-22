"""Dragon_Idle_Blender_v1: layered NLA keyframe authoring on DRAGON_CTRL (Blender 5.2).
Each layer is a sparse-keyed cyclic action (Bezier auto-clamped + Cycles modifier),
stacked with COMBINE. Period 180 f @ 30 fps (6 s); breath layer period 90 f.
Axes: dragon faces +X, left = +Y, up = +Z. Angles in degrees, distances in rig units
(1 unit = 21.56 m in game; dragon height 0.487)."""
import bpy, math, json
from mathutils import Quaternion, Vector, Matrix
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
s = bpy.context.scene
s.render.fps = 30; s.render.fps_base = 1; s.frame_start = 0; s.frame_end = 180
C = bpy.data.objects['DRAGON_CTRL']; P = C.pose.bones; B = C.data.bones
# chest/body uniform breath scale must not propagate to neck/scapulae/wings/hips
for n in ('C_bone_2','C_tripo::Spine_1','C_bone_3','C_bone_6','C_bone_11','C_VeyrWingPosZRoot','C_VeyrWingNegZRoot'):
    B[n].inherit_scale = 'NONE'
X, Y, Z = Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))
def R(axis, deg): return Quaternion(axis, math.radians(deg))
def YAW(d): return R(Z, d)            # + turns toward left (+Y)
def PITCH_UP(d): return R(Y, -d)      # + raises the forward end
def ROLL(d): return R(X, d)           # + raises left side
def local_q(bone, qw):
    m = B[bone].matrix_local.to_3x3().to_quaternion()
    return m.inverted() @ qw @ m
def local_v(bone, vw):
    return B[bone].matrix_local.to_3x3().inverted() @ vw
WING = {'R': ('PosZ', -1), 'L': ('NegZ', 1)}   # sign: + = left-wing positive sense
def wing_q(side, sweep_back=0., lower=0.):
    sg = WING[side][1]
    return R(Z, sg*sweep_back) @ R(X, -sg*lower)

# ---- clear previous authoring
ad = C.animation_data or C.animation_data_create()
ad.action = None
for t in list(ad.nla_tracks): ad.nla_tracks.remove(t)
for a in list(bpy.data.actions):
    if a.name.startswith('IDLE_L'): bpy.data.actions.remove(a)
for pb in P: pb.rotation_mode='QUATERNION'; pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)

def fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                yield from cb.fcurves

def make_layer(name, period, channels, blend='COMBINE'):
    """channels: {bone: [(frame, dict(q=Quaternion|None, loc=Vector|None, sc=float|None)), ...]} one cycle."""
    act = bpy.data.actions.new('IDLE_L'+name)
    ad.action = act
    for bone, keys in channels.items():
        pb = P[bone]
        ks = sorted(((f % period, k) for f, k in keys), key=lambda x: x[0])
        ks = ks + [(ks[0][0] + period, ks[0][1])]
        prev = None
        for f, k in ks:
            if 'q' in k:
                q = local_q(bone, k['q'])
                if prev is not None and prev.dot(q) < 0: q.negate()
                prev = q.copy(); pb.rotation_quaternion = q
                pb.keyframe_insert('rotation_quaternion', frame=f, group=bone)
            if 'loc' in k:
                pb.location = local_v(bone, k['loc']); pb.keyframe_insert('location', frame=f, group=bone)
            if 'sc' in k:
                pb.scale = (k['sc'],)*3; pb.keyframe_insert('scale', frame=f, group=bone)
        pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        if not any(m.type=='CYCLES' for m in fc.modifiers): fc.modifiers.new('CYCLES')
        fc.update()
    act.use_frame_range = True; act.frame_start = 0; act.frame_end = 180
    act.use_cyclic = True
    ad.action = None
    tr = ad.nla_tracks.new(); tr.name = name
    st = tr.strips.new(name, 0, act)
    st.action_frame_start, st.action_frame_end = 0, 180
    st.blend_type = blend; st.extrapolation = 'HOLD' if blend=='REPLACE' else 'NOTHING'
    try:
        if st.action_slot is None and act.slots: st.action_slot = act.slots[0]
    except AttributeError: pass
    return act

def sample(keys, f, period):
    """value of a piecewise-smoothstep keyed scalar (for derived quantities only)."""
    ks = sorted(((k % period, v) for k, v in keys)); ks = ks + [(ks[0][0]+period, ks[0][1])]
    f = f % period
    if f < ks[0][0]: f += period
    for (a, va), (b, vb) in zip(ks, ks[1:]):
        if a <= f <= b:
            u = (f-a)/(b-a); u = u*u*(3-2*u); return va+(vb-va)*u
    return ks[0][1]

# ================= L0 base stance (REPLACE) =================
base = {
 'C_tripo::Spine_0': [(0, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7)))],
 'C_bone_3': [(0, dict(q=PITCH_UP(-2.5)))],
 'C_bone_4': [(0, dict(q=PITCH_UP(0.8)))],
 'C_bone_5': [(0, dict(q=PITCH_UP(2.4)))],
 'C_bone_18': [(0, dict(q=YAW(2.0)))],
 'C_tripo::Tail_0': [(0, dict(q=YAW(-3.0)))],
 'C_tripo::Tail_1': [(0, dict(q=YAW(-4.0)))],
 'C_tripo::Tail_2': [(0, dict(q=YAW(5.0)))],
}
# Ground the feet: the Tripo bind leaves the soles hovering (FR 5 cm, HL 19 cm, HR 24 cm game scale)
base['IK_FR'] = [(0, dict(loc=Vector((0, 0, -0.00244))))]
base['IK_HL'] = [(0, dict(loc=Vector((0, 0, -0.008794))))]
base['IK_HR'] = [(0, dict(loc=Vector((0, 0, -0.011235))))]
for side in 'RL':
    tag, sg = WING[side]
    sweep, lower = globals().get('WING_FOLD', {}).get(side, {'L': (33, -3), 'R': (35, 2)}[side])  # left root clears its shoulder only with less drop (audited)
    base[f'C_VeyrWing{tag}Root'] = [(0, dict(q=wing_q(side, sweep, lower)))]
    base[f'C_VeyrWing{tag}Wrist'] = [(0, dict(q=R(Z, sg*10)))]
make_layer('0_Base', 180, base, blend='REPLACE')

# ================= L1 breath (period 90) =================
BR = [(0, 0.0), (40, 1.0), (48, 0.96), (90-0.001, 0.0)]  # inhale 40f, brief hold, long exhale
BR = [(0, 0.0), (40, 1.0), (48, 0.96)]
def breath(lag, fn):
    return [((f+lag) % 90, fn(v)) for f, v in BR]
br = {
 'C_tripo::Spine_0': breath(0, lambda v: dict(loc=Vector((0,0,0.0045*v)), q=PITCH_UP(0.75*v), sc=1+0.015*v)),
 'C_bone_2': breath(2, lambda v: dict(q=PITCH_UP(1.6*v), sc=1+0.030*v)),
 'C_bone_6': breath(3, lambda v: dict(q=ROLL(1.3*v))),
 'C_bone_11': breath(3, lambda v: dict(q=ROLL(-1.3*v))),
 'C_bone_3': breath(5, lambda v: dict(q=PITCH_UP(1.1*v))),
 'C_bone_5': breath(7, lambda v: dict(q=PITCH_UP(-1.4*v))),
 'C_tripo::Spine_1': breath(4, lambda v: dict(q=PITCH_UP(-0.35*v))),
 'C_bone_18': breath(10, lambda v: dict(q=PITCH_UP(0.7*v))),
 'C_tripo::Tail_0': breath(16, lambda v: dict(q=PITCH_UP(-0.5*v))),
 'C_VeyrJaw': [(0, dict(q=R(Y, 0.0))), (46, dict(q=R(Y, 0.0))), (64, dict(q=R(Y, 2.2))), (82, dict(q=R(Y, 0.5)))],
}
# jaw opens about the head's lateral axis: positive Y rotation pitches forward end down (= open)
for side in 'RL':
    tag, sg = WING[side]
    br[f'C_VeyrWing{tag}Root'] = breath(6, lambda v, sg=sg: dict(q=R(X, sg*1.6*v)))       # lift toward vertical
    br[f'C_VeyrWing{tag}Wrist'] = breath(12, lambda v, sg=sg: dict(q=R(Z, -sg*2.2*v)))   # leading finger opens forward
    br[f'C_VeyrWing{tag}Elbow'] = breath(17, lambda v, sg=sg: dict(q=R(Z, -sg*2.4*v)))   # trailing membrane follows late
make_layer('1_Breath', 90, br)

# ================= L2 weight shift (period 180) =================
SH = [(10, 1.04), (22, 1.0), (55, 0.88), (98, -1.04), (110, -1.0), (145, -0.88)]
def shift(lag, fn): return [((f+lag) % 180, fn(v)) for f, v in SH]
sh = {
 'C_tripo::Spine_0': shift(0, lambda v: dict(loc=Vector((0, 0.0100*v, -0.0022*min(1.0, v*v))), q=ROLL(-1.6*v) @ YAW(0.6*v))),
 'C_tripo::Spine_1': shift(8, lambda v: dict(q=ROLL(0.7*v) @ YAW(-0.8*v))),
 'C_bone_2': shift(5, lambda v: dict(q=ROLL(-0.35*v))),
 'C_bone_5': shift(7, lambda v: dict(q=ROLL(1.3*v))),
}
for side in 'RL':
    tag, sg = WING[side]
    # loaded-side wing settles a touch lower; delayed rustle (overlap)
    sh[f'C_VeyrWing{tag}Root'] = shift(14, lambda v, sg=sg: dict(q=R(X, -sg*0.9*v*sg)))
make_layer('2_WeightShift', 180, sh)

# ================= L3 neck/head scan (period 180) =================
LOOK = [(0, 15), (38, 12), (54, -2), (70, -17), (80, -15), (128, -12), (144, 2), (160, 17), (170, 15)]
DIP = {54: -3.0, 144: -3.0}
def scan(lag, share, dip=0.0, over=0.0):
    out = []
    for f, v in LOOK:
        vv = v*share + (math.copysign(over, v) if f in (70, 160) else 0.0)
        out.append(((f+lag) % 180, dict(q=YAW(vv) @ PITCH_UP(DIP.get(f, 0.0)*dip))))
    return out
sc = {
 'C_bone_3': scan(0, 0.34, dip=0.4),
 'C_bone_4': scan(4, 0.34, dip=0.3),
 'C_bone_5': scan(8, 0.32, dip=0.5, over=1.2),
 'C_bone_2': scan(11, 0.10),
 'C_tripo::Spine_0': scan(16, 0.04),
}
make_layer('3_Scan', 180, sc)

# ================= L4 tail wave (period 180) =================
TAIL = [('C_bone_18', 35, 3.0), ('C_tripo::Tail_0', 50, 4.5), ('C_tripo::Tail_1', 65, 6.5), ('C_tripo::Tail_2', 80, 9.0)]
tl = {b: [(lag, dict(q=YAW(-a))), (lag+90, dict(q=YAW(a)))] for b, lag, a in TAIL}
make_layer('4_TailWave', 180, tl)

C['idle_authoring'] = 'author_idle.py layered NLA v1'
bpy.context.view_layer.update()
s.frame_set(0)
print(json.dumps({'tracks': [t.name for t in ad.nla_tracks], 'actions': [a.name for a in bpy.data.actions if a.name.startswith('IDLE_L')],
                  'slots': [ (t.strips[0].action.name, getattr(t.strips[0],'action_slot',None) and t.strips[0].action_slot.name_display) for t in ad.nla_tracks]}))
