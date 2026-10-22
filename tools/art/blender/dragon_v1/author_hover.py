"""Dragon_FlyHover_Blender_v1: seamless hover, 60 f @ 30 fps (2 s), one heavy wing beat:
22 f powerful downstroke with membrane billow, 38 f lighter upstroke with partial fan fold.
Root carries a constant hover altitude HOV (0.14 u = 302 cm, shared with TakeoffLand); body bobs
+-0.0095 u (+-20 cm) peaking ~5 f after the downstroke ends; legs tucked (IK controls ride body)."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/anim_common.py').read())
T = 60; BT = 60; HOV = 0.14; PFX = 'HOVER_L'
s.render.fps = 30; s.frame_start = 0; s.frame_end = T
reset_ctrl(PFX)
for a in bpy.data.actions:
    if a.name.startswith(('IDLE_L', 'IDLE2_L', 'WALK_L', 'TURN_L')): a.use_fake_user = True
def lay(name, period, ch, blend='COMBINE'): return make_layer(PFX, name, period, ch, blend=blend, length=T)
def wq(side, axis, deg): return Quaternion(wing_side_axis(axis, side), math.radians(deg))
def billow_axis(part, side):
    b = B[f'C_VeyrWingPosZ{part}']; d = (b.tail_local - b.head_local).normalized()
    a = d.cross(Vector((1, 0, 0))).normalized(); return mirror_axis(a) if side == 'L' else a
SPREAD = 90.0
FLAP = [(0, 42), (6, 36), (14, 0), (22, -36), (27, -31), (40, 0), (52, 34)]       # + = wing up
TWIST = [(0, -5), (5, 10), (20, 10), (28, -3), (40, -10), (52, -8)]               # + = leading edge down
FOLD = [(0, 0), (22, 0), (36, 24), (48, 10)]                                      # upstroke fan fold
BILLOW = [(0, 3), (8, -2), (18, -10), (28, -5), (40, 6), (50, 5)]                 # membrane pushed against the stroke
def sample(keys, f, period):
    ks = sorted(keys) + [(sorted(keys)[0][0] + period, sorted(keys)[0][1])]; f = f % period
    if f < ks[0][0]: f += period
    for (a, va), (b, vb) in zip(ks, ks[1:]):
        if a <= f <= b: u = (f-a)/(b-a); u = u*u*(3-2*u); return va + (vb-va)*u
    return ks[0][1]
# ---- L0 base: altitude, hover attitude, tucked legs, spread wings, tail trailing
base = {'C_tripo::Root': [(0, dict(loc=Vector((0, 0, HOV))))],
        'C_tripo::Spine_0': [(0, dict(q=PITCH_UP(20)))],
        'C_bone_3': [(0, dict(q=PITCH_UP(-11)))], 'C_bone_4': [(0, dict(q=PITCH_UP(-4)))], 'C_bone_5': [(0, dict(q=PITCH_UP(-4)))],
        'C_tripo::Spine_1': [(0, dict(q=PITCH_UP(-6)))],   # tail-side bones point -X: negative PITCH_UP lifts them
        'C_bone_18': [(0, dict(q=PITCH_UP(-10)))], 'C_tripo::Tail_0': [(0, dict(q=PITCH_UP(-6)))], 'C_tripo::Tail_1': [(0, dict(q=PITCH_UP(-3)))],
        'IK_FL': [(0, dict(loc=Vector((-0.045, 0.004, 0.075)), q=R(Y, 45)))], 'IK_FR': [(0, dict(loc=Vector((-0.045, -0.004, 0.075)), q=R(Y, 45)))],
        'IK_HL': [(0, dict(loc=Vector((0.045, -0.006, 0.055)), q=R(Y, 40)))], 'IK_HR': [(0, dict(loc=Vector((0.045, 0.006, 0.055)), q=R(Y, 40)))]}
lay('0_Base', T, base, blend='REPLACE')
# ---- L1 wing beat (period 30)
wb = {}
for side, tag in (('R','PosZ'), ('L','NegZ')):
    KF = sorted({f for f, _ in FLAP + TWIST})
    # world composition: spread (about the lateral axis), then twist, then flap about the forward axis
    wb[f'C_VeyrWing{tag}Root'] = [(f, dict(q=wq(side, (1,0,0), -sample(FLAP, f, BT)) @ wq(side, (0,1,0), SPREAD + sample(TWIST, f, BT)))) for f in KF]
    wb[f'C_VeyrWing{tag}Wrist'] = [(f, dict(q=wq(side, (1,0,0), v))) for f, v in FOLD]
    wb[f'C_VeyrWing{tag}Elbow'] = [((f+1) % BT, dict(q=Quaternion(billow_axis('Elbow', side), math.radians(v)))) for f, v in BILLOW]
    wb[f'C_VeyrWing{tag}Membrane'] = [((f+3) % BT, dict(q=Quaternion(billow_axis('Membrane', side), math.radians(1.2*v)))) for f, v in BILLOW]
    wb[f'C_VeyrWing{tag}Tip'] = [((f+2) % BT, dict(q=wq(side, (0,0,1), -0.12*sample(FLAP, f, BT)))) for f, _ in FLAP]   # finger tip lags the arm (rest Z = world forward after the spread)
lay('1_WingBeat', BT, wb, blend='COMBINE')
# ---- L2 body lift lagging the beat, head steady, tail and legs trailing
body = {'C_tripo::Spine_0': [(6, dict(loc=Vector((0, 0, -0.0095)), q=PITCH_UP(-1.5))), (31, dict(loc=Vector((0, 0, 0.0095)), q=PITCH_UP(1.8)))],
        'C_bone_3': [(12, dict(q=PITCH_UP(1.6))), (37, dict(q=PITCH_UP(-1.8)))],          # counters the bob, late
        'C_bone_5': [(17, dict(q=PITCH_UP(0.9))), (42, dict(q=PITCH_UP(-1.0)))],         # slight head bob, later still
        'C_bone_18': [(12, dict(q=PITCH_UP(2.5))), (40, dict(q=PITCH_UP(-2.5)))],
        'C_tripo::Tail_0': [(18, dict(q=PITCH_UP(3.5))), (46, dict(q=PITCH_UP(-3.5)))],
        'C_tripo::Tail_1': [(24, dict(q=PITCH_UP(4.5))), (52, dict(q=PITCH_UP(-4.5)))],
        'C_tripo::Tail_2': [(30, dict(q=PITCH_UP(5.5))), (58, dict(q=PITCH_UP(-5.5)))],
        'IK_HL': [(13, dict(loc=Vector((0, 0, 0.003)))), (38, dict(loc=Vector((0, 0, -0.003))))],
        'IK_HR': [(14, dict(loc=Vector((0, 0, 0.003)))), (39, dict(loc=Vector((0, 0, -0.003))))],
        'IK_FL': [(11, dict(loc=Vector((0, 0, 0.002)))), (36, dict(loc=Vector((0, 0, -0.002))))],
        'IK_FR': [(11, dict(loc=Vector((0, 0, 0.002)))), (36, dict(loc=Vector((0, 0, -0.002))))]}
lay('2_BodyLift', BT, body)
# ---- L3 slow tail sway + breath-like chest over the full loop
sway = {b: [(lag, dict(q=YAW(a))), (lag + 30, dict(q=YAW(-a)))] for b, lag, a in
        (('C_bone_18', 0, 1.5), ('C_tripo::Tail_0', 6, 2.5), ('C_tripo::Tail_1', 12, 3.5), ('C_tripo::Tail_2', 18, 4.5))}
lay('3_TailSway', T, sway)
M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
kad = key.animation_data or key.animation_data_create()
old = bpy.data.actions.get(PFX+'ShapeKeys')
if old: bpy.data.actions.remove(old)
ska = bpy.data.actions.new(PFX+'ShapeKeys'); kad.action = ska
for name, vals in (('VeyrWingFold', ((0, 0.0), (T, 0.0))), ('VeyrWingFoldWalk', ((0, 0.0), (T, 0.0))), ('VeyrBreath', ((0, 0.2), (31, 0.5), (60, 0.2)))):
    kb = key.key_blocks[name]
    for f, v in vals: kb.value = v; kb.keyframe_insert('value', frame=f)
for fc in fcurves(ska):
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'
ska.use_fake_user = True
s.frame_set(0)
print('RES', json.dumps({'frames': T, 'tracks': [t.name for t in ad.nla_tracks]}))
