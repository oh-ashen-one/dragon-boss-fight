"""Dragon_Idle_Blender_v1r3 (critic round 2): r3 flank fold (FOLD3 + projection corrective VeyrWingFold), deeper breath, jaw 9 deg on exhale.
Derived from r2 (critic round 1): wings folded on the flanks (FOLD_V2 + VeyrWingFold
corrective), visible breathing (VeyrBreath shape key + torso bones), head lagging the torso
10-20 f with overshoot/settle and one independent side scan, vertical tail wave, jaw gap at breath top.
180 f @ 30 fps; breath period 90 f."""
SET_POSE = False
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
T = 180; BP = 90
s.render.fps = 30; s.frame_start = 0; s.frame_end = T
PFX = 'IDLE3_L'
reset_ctrl(PFX)
for a in bpy.data.actions:
    if a.name.startswith(('IDLE_L', 'IDLE2_L')): a.use_fake_user = True
def lay(name, period, ch, blend='COMBINE'): return make_layer(PFX, name, period, ch, blend=blend, length=T)
BKEYS = [(0, 0.0), (40, 1.0), (48, 0.96)]              # torso breath: inhale 40 f, hold, long exhale
def bsample(f):
    ks = BKEYS + [(BP, 0.0)]; f = f % BP
    for (a, va), (b, vb) in zip(ks, ks[1:]):
        if a <= f <= b: u = (f-a)/(b-a); u = u*u*(3-2*u); return va+(vb-va)*u
    return 0.0
def breath(lag, fn): return [((f+lag) % BP, fn(v)) for f, v in BKEYS]

# L0 base stance: crouch, grounded feet, flank fold, neck carriage
base = {'C_tripo::Spine_0': [(0, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7)))],
        'C_bone_3': [(0, dict(q=PITCH_UP(-2.5)))], 'C_bone_4': [(0, dict(q=PITCH_UP(0.8)))], 'C_bone_5': [(0, dict(q=PITCH_UP(2.4)))],
        'C_bone_18': [(0, dict(q=YAW(2.0)))], 'C_tripo::Tail_0': [(0, dict(q=YAW(-3.0)))], 'C_tripo::Tail_1': [(0, dict(q=YAW(-4.0)))], 'C_tripo::Tail_2': [(0, dict(q=YAW(5.0)))]}
for k, z in GROUND.items(): base[k] = [(0, dict(loc=Vector((0,0,z))))]
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part in ('Root','Wrist','Elbow','Membrane'): base[f'C_VeyrWing{tag}{part}'] = [(0, dict(q=fold3_q(part, side)))]
lay('0_Base', T, base, blend='REPLACE')

# L1 breath (torso bones; shape key VeyrBreath keyed separately with the same timing)
br = {'C_tripo::Spine_0': breath(0, lambda v: dict(loc=Vector((0,0,0.0060*v)), q=PITCH_UP(0.9*v), sc=1+0.008*v)),
      'C_bone_2': breath(2, lambda v: dict(q=PITCH_UP(2.0*v), sc=1+0.015*v)),
      'C_bone_6': breath(3, lambda v: dict(q=ROLL(2.0*v) @ PITCH_UP(1.5*v))), 'C_bone_11': breath(3, lambda v: dict(q=ROLL(-2.0*v) @ PITCH_UP(1.5*v))),
      'C_tripo::Spine_1': breath(4, lambda v: dict(q=PITCH_UP(-0.4*v))),
      'C_VeyrJaw': [(0, dict(q=R(Y, 0.0))), (36, dict(q=R(Y, 0.0))), (46, dict(q=R(Y, 3.0))), (56, dict(q=R(Y, 9.0))), (66, dict(q=R(Y, 7.5))), (80, dict(q=R(Y, 0.5)))]}
for side, tag in (('R','PosZ'), ('L','NegZ')):   # wings trail the breath by ~10 f, small
    br[f'C_VeyrWing{tag}Root'] = breath(10, lambda v, side=side: dict(q=Quaternion(wing_side_axis((1,0,0), side), math.radians(-0.5*v))))
    br[f'C_VeyrWing{tag}Elbow'] = breath(16, lambda v, side=side: dict(q=Quaternion(wing_side_axis((1,0,0), side), math.radians(0.5*v))))
lay('1_Breath', BP, br)

# L2 head rides behind the torso: cancel torso lift at the neck base, add a 14 f lagged lift with overshoot
def H(f):
    return bsample(f-14) + 0.32*math.exp(-((f % BP - 57)/6.0)**2) - 0.05*math.exp(-((f % BP - 71)/6.0)**2)
KF = list(range(0, BP, 6))
head = {'C_bone_3': [(f, dict(q=PITCH_UP(-2.7*bsample(f) + 2.4*H(f)))) for f in KF],
        'C_bone_5': [((f+4) % BP, dict(q=PITCH_UP(-0.9*(2.4*H(f) - 2.7*bsample(f))))) for f in KF]}
lay('2_HeadLag', BP, head)

# L3 one independent side scan (head leads, neck follows), with micro drift elsewhere
LOOK = [(0, 1.5), (40, -1.0), (92, 1.0), (104, -14.0), (114, -23.5), (122, -21.5), (142, -20.0), (160, -3.0), (170, 1.8)]
def scan(lag, share, over=0.0):
    return [((f+lag) % T, dict(q=YAW(v*share + (over if f == 114 else 0.0)))) for f, v in LOOK]
sc = {'C_bone_5': scan(0, 0.42, over=-1.5), 'C_bone_4': scan(4, 0.33), 'C_bone_3': scan(8, 0.25), 'C_bone_2': scan(12, 0.07)}
lay('3_Scan', T, sc)

# L4 weight shift (as v1, slightly smaller)
SH = [(10, 1.04), (22, 1.0), (55, 0.88), (98, -1.04), (110, -1.0), (145, -0.88)]
def shift(lag, fn): return [((f+lag) % T, fn(v)) for f, v in SH]
sh = {'C_tripo::Spine_0': shift(0, lambda v: dict(loc=Vector((0, 0.009*v, -0.0018*min(1.0, v*v))), q=ROLL(-1.4*v) @ YAW(0.5*v))),
      'C_tripo::Spine_1': shift(8, lambda v: dict(q=ROLL(0.6*v) @ YAW(-0.7*v))),
      'C_bone_2': shift(5, lambda v: dict(q=ROLL(-0.3*v))), 'C_bone_5': shift(7, lambda v: dict(q=ROLL(1.1*v)))}
lay('4_WeightShift', T, sh)

# L5 tail: lateral wave (180 f) + vertical wave (90 f) with phase offsets down the chain
TAIL = [('C_bone_18', 35, 3.0), ('C_tripo::Tail_0', 50, 4.5), ('C_tripo::Tail_1', 65, 6.5), ('C_tripo::Tail_2', 80, 9.0)]
lay('5_TailYaw', T, {b: [(lag, dict(q=YAW(-a))), (lag+90, dict(q=YAW(a)))] for b, lag, a in TAIL})
TV = [('C_bone_18', 8, 1.3), ('C_tripo::Tail_0', 18, 1.7), ('C_tripo::Tail_1', 28, 2.2), ('C_tripo::Tail_2', 38, 2.8)]
lay('6_TailPitch', BP, {b: [(lag, dict(q=PITCH_UP(a))), (lag+45, dict(q=PITCH_UP(-a)))] for b, lag, a in TV})

# shape keys: VeyrWingFold constant 1, VeyrBreath = torso breath curve
M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
kad = key.animation_data or key.animation_data_create()
old = bpy.data.actions.get('IDLE3_ShapeKeys')
if old: bpy.data.actions.remove(old)
ska = bpy.data.actions.new('IDLE3_ShapeKeys'); kad.action = ska
kbf, kbb = key.key_blocks['VeyrWingFold'], key.key_blocks['VeyrBreath']
for f in (0, T): kbf.value = 1.0; kbf.keyframe_insert('value', frame=f)
for f in range(0, T+1, BP):
    for df, v in BKEYS: kbb.value = v; kbb.keyframe_insert('value', frame=f+df)
kbb.value = 0.0; kbb.keyframe_insert('value', frame=T)
for fc in fcurves(ska):
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    fc.update()
ska.use_fake_user = True
s.frame_set(0)
print('RES', json.dumps({'tracks': [t.name for t in ad.nla_tracks], 'shape_keys': [k.name for k in key.key_blocks]}))
