"""Dragon_Walk_Blender_v1r2 (critic round 2: r3 fold, 35-45 px lift, front-landing weight, lagged head, wide tail). From v1: lateral-sequence heavy walk (LH, LF, RH, RF), in place.
96 f @ 30 fps (3.2 s), duty 0.76 (3 feet down except brief 4-foot overlaps), stride per
cycle S = 0.100 u = 215.6 cm -> ground speed 67.4 cm/s. Stance feet slide back linearly
at exactly that speed (in-place convention: actor supplies travel)."""
SET_POSE = False
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
T = 96; DUTY = 0.76; S = globals().get('STRIDE', 0.100); A = S*DUTY/2; SW = (1-DUTY)*T
K = T/84.0; QP = T/4.0  # K rescales the 84-frame design timings; QP = plant spacing
s.render.fps = 30; s.frame_start = 0; s.frame_end = T
PFX = 'WALK2_L'
reset_ctrl(PFX)
# keep the idle layer actions alive in the file for reference
for a in bpy.data.actions:
    if a.name.startswith(('IDLE_L', 'IDLE2_L', 'IDLE3_L', 'WALK_L')): a.use_fake_user = True
FEET = {  # control, lift frame, swing height, kind
 'HL': ('IK_HL', 0.00*T, 0.046, 'hind'), 'FL': ('IK_FL', 0.25*T, 0.056, 'front'),
 'HR': ('IK_HR', 0.50*T, 0.046, 'hind'), 'FR': ('IK_FR', 0.75*T, 0.056, 'front')}
SIDE = {'HL': 1, 'FL': 1, 'HR': -1, 'FR': -1}
TOES = {'HL': 'FOOT_tripo::1_Right_Limb_3', 'HR': 'FOOT_tripo::0_Right_Limb_3', 'FL': 'FOOT_bone_9', 'FR': 'FOOT_bone_14'}
CLAW = {'HL': 'FOOT_tripo::1_Right_Limb_4', 'HR': 'FOOT_tripo::0_Right_Limb_4', 'FR': 'FOOT_tripo::0_Left_Limb_3'}  # FL claws are bone_9 (TOES)

# ---------- L0 base stance (REPLACE): crouch, grounded feet, wing fold, neck carriage
base = {'C_tripo::Spine_0': [(0, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7)))],
        'C_bone_3': [(0, dict(q=PITCH_UP(-4.0)))], 'C_bone_4': [(0, dict(q=PITCH_UP(1.0)))], 'C_bone_5': [(0, dict(q=PITCH_UP(3.0)))],
        'C_bone_18': [(0, dict(q=PITCH_UP(1.0)))]}
for k, (ctl, *_ ) in FEET.items():
    base[ctl] = [(0, dict(loc=Vector((0, 0, GROUND[ctl]))))]
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part in ('Root','Wrist','Elbow','Membrane'): base[f'C_VeyrWing{tag}{part}'] = [(0, dict(q=fold3_q(part, side)))]
make_layer(PFX, '0_Base', T, base, blend='REPLACE')

# ---------- L1 feet: X (linear stance slide), Z (swing arc), rotation (peel/curl), toes/claws
fx, fz, fr, toe, claw = {}, {}, {}, {}, {}
for k, (ctl, L, H, kind) in FEET.items():
    Pl = L + SW
    fx[ctl] = [(Pl, dict(loc=Vector((A, 0, 0)), interp='LINEAR')), (L, dict(loc=Vector((-A, 0, 0))))]
    fz[ctl] = [(L, dict(loc=Vector((0,0,0)))), (L+0.16*SW, dict(loc=Vector((0,0,0.3*H)))), (L+0.45*SW, dict(loc=Vector((0,0,H)))), (L+0.78*SW, dict(loc=Vector((0,0,0.35*H)))), (Pl, dict(loc=Vector((0,0,0))))]
    sd = SIDE[k]
    if kind == 'hind':
        # heel peel about the ball (IK pivot), toes counter-rotated to stay flat; curl in swing
        th = [(L-11, 0.), (L, 15.), (L+0.2*SW, 19.), (L+0.5*SW, 14.), (L+0.8*SW, 4.), (Pl-1.5, 0.)]
        fr[ctl] = [(f, dict(q=R(Y, a))) for f, a in th]
        toe[TOES[k]] = [(L-11, dict(q=R(Y, 0))), (L, dict(q=R(Y, -15))), (L+0.2*SW, dict(q=R(Y, -19))), (L+0.5*SW, dict(q=R(Y, -14+10))), (L+0.8*SW, dict(q=R(Y, -4+3))), (Pl-1.5, dict(q=R(Y, 0)))]
    else:
        # front: wrist flexes after toe-off, flattens before contact
        fr[ctl] = [(L, dict(q=R(Y, 0))), (L+0.2*SW, dict(q=R(Y, 3))), (L+0.45*SW, dict(q=R(Y, 10))), (L+0.8*SW, dict(q=R(Y, 2))), (Pl, dict(q=R(Y, 0)))]
        toe[TOES[k]] = [(L, dict(q=R(Y, 0))), (L+0.45*SW, dict(q=R(Y, 4))), (Pl-1, dict(q=R(Y, 0))), (Pl+5, dict(q=YAW(sd*3))), (L-8, dict(q=YAW(sd*3)))]
    # claws splay outward as weight comes on, relax before lift
    if k in CLAW: claw[CLAW[k]] = [(Pl, dict(q=YAW(0))), (Pl+5, dict(q=YAW(sd*3) @ R(Y, -2))), (L-10, dict(q=YAW(sd*2.5))), (L, dict(q=YAW(0)))]
make_layer(PFX, '1_FootX', T, fx)
make_layer(PFX, '2_FootZ', T, fz)
make_layer(PFX, '3_FootRot', T, fr)
make_layer(PFX, '4_ToesClaws', T, {**toe, **claw})

# ---------- L2 body: bob at each plant, lateral weight transfer, hip/shoulder rock + yaw (spine S-bend)
plants = [FEET[k][1] + SW for k in ('HL','FL','HR','FR')]
PLF, PRF, PLH, PRH = FEET['FL'][1] + SW, FEET['FR'][1] + SW, FEET['HL'][1] + SW, FEET['HR'][1] + SW
bob = {'C_tripo::Spine_0': [(PLH + 3, dict(loc=Vector((0,0,-0.0030)))), (PLH + 13, dict(loc=Vector((0,0,0.0010)))),
                            (PLF + 3, dict(loc=Vector((0,0,-0.0095)), q=ROLL(-1.5))), (PLF + 14, dict(loc=Vector((0,0,0.0015)))),
                            (PRH + 3, dict(loc=Vector((0,0,-0.0030)))), (PRH + 13, dict(loc=Vector((0,0,0.0010)))),
                            (PRF + 3, dict(loc=Vector((0,0,-0.0095)), q=ROLL(1.5))), (PRF + 14, dict(loc=Vector((0,0,0.0015))))],
       'C_tripo::Spine_1': [(PLH + 4, dict(q=ROLL(-2.0))), (PRH + 4, dict(q=ROLL(2.0)))]}
make_layer(PFX, '5_Bob', T, bob, length=T)
body = {
 'C_tripo::Spine_0': sine_keys(T, 59*K, 0.0062, lambda v: dict(loc=Vector((0, v, 0)), q=ROLL(-v/0.0062*0.8))),   # weight over support side
 'C_tripo::Spine_1': sine_keys(T, 51*K, 1.0, lambda v: dict(q=YAW(3.5*v) @ ROLL(2.0*v))),                       # pelvis yaw + drop on swing side
 'C_bone_2':         sine_keys(T, 72*K, 1.0, lambda v: dict(q=YAW(3.0*v) @ ROLL(1.6*v))),                       # shoulders, 1/4 cycle later
 'C_bone_6':  [(21*K, dict(q=PITCH_UP(-4))), (39.5*K, dict(q=PITCH_UP(4)))],                                     # scapula swings with LF
 'C_bone_11': [(63*K, dict(q=PITCH_UP(-4))), (81.5*K, dict(q=PITCH_UP(4)))],
 'C_tripo::Spine_2': [(0*K, dict(q=PITCH_UP(-3))), (18.5*K, dict(q=PITCH_UP(3)))],                               # hip roots with LH / RH
 'C_tripo::Spine_3': [(42*K, dict(q=PITCH_UP(-3))), (60.5*K, dict(q=PITCH_UP(3)))],
}
make_layer(PFX, '6_Body', T, body)

# ---------- L3 neck counterbalance with lag, head stabilised
neck = {   # head follows the shoulder yaw 4-8 f late (follow-through), not counter-phase
 'C_bone_3': sine_keys(T, (72)*K + 1, 1.0, lambda v: dict(q=YAW(1.2*v))),
 'C_bone_4': sine_keys(T, (72)*K + 2, 1.0, lambda v: dict(q=YAW(0.9*v))),
 'C_bone_5': sine_keys(T, (72)*K + 3, 1.0, lambda v: dict(q=YAW(0.6*v))),
}
make_layer(PFX, '7_Neck', T, neck)
neckbob = {'C_bone_3': [(6.0*K, dict(q=PITCH_UP(-0.9))), (16.0*K, dict(q=PITCH_UP(0.4)))],
           'C_bone_5': [(8.0*K, dict(q=PITCH_UP(1.0))), (18.0*K, dict(q=PITCH_UP(-0.4)))]}
make_layer(PFX, '8_NeckBob', QP, neckbob, length=T)

# ---------- L4 tail opposite the hips, travelling wave
TAIL = [('C_bone_18', 6, 4.0), ('C_tripo::Tail_0', 12, 6.0), ('C_tripo::Tail_1', 18, 8.0), ('C_tripo::Tail_2', 24, 10.0)]
tail = {b: sine_keys(T, (51+lag)*K, 1.0, lambda v, a=a: dict(q=YAW(-a*v))) for b, lag, a in TAIL}
make_layer(PFX, '9_Tail', T, tail)
tailbob = {'C_tripo::Tail_0': [(7.0*K, dict(q=PITCH_UP(-0.8))), (17.0*K, dict(q=PITCH_UP(0.5)))],
           'C_tripo::Tail_2': [(11.0*K, dict(q=PITCH_UP(-1.2))), (21.0*K, dict(q=PITCH_UP(0.6)))]}
make_layer(PFX, '10_TailBob', QP, tailbob, length=T)

# ---------- L5 wings ride the body with delay (root only, small elbow/wrist follow)
wings = {}
for side, peak in (('L', (30+7)*K), ('R', (72+7)*K)):
    tag, sg = WING[side]
    wings[f'C_VeyrWing{tag}Root'] = sine_keys(T, peak, 1.0, lambda v, side=side: dict(q=wing_q(side, 0.0, 1.8*v)))
    wings[f'C_VeyrWing{tag}Wrist'] = sine_keys(T, peak+6*K, 1.0, lambda v, sg=sg: dict(q=R(Z, -sg*1.2*v)))
make_layer(PFX, '11_Wings', T, wings)
wbob = {}
for side in 'LR':
    tag, sg = WING[side]
    wbob[f'C_VeyrWing{tag}Root'] = [(7.0*K, dict(q=wing_q(side, 0, 1.0))), (17.0*K, dict(q=wing_q(side, 0, -0.4)))]
    wbob[f'C_VeyrWing{tag}Elbow'] = [(10.0*K, dict(q=R(Z, -sg*1.0))), (20.0*K, dict(q=R(Z, sg*0.4)))]
make_layer(PFX, '12_WingBob', QP, wbob, length=T)

# ---------- L6 subtle breathing (one per cycle)
br = {'C_bone_2': sine_keys(T, 30*K, 1.0, lambda v: dict(sc=1+0.006*(v+1))),
      'C_tripo::Spine_0': sine_keys(T, 28*K, 1.0, lambda v: dict(sc=1+0.003*(v+1)))}
make_layer(PFX, '13_Breath', T, br)

# shape keys: corrective fold on, breathing subtle (one per cycle)
M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
kad = key.animation_data or key.animation_data_create()
old = bpy.data.actions.get(PFX+'ShapeKeys')
if old: bpy.data.actions.remove(old)
ska = bpy.data.actions.new(PFX+'ShapeKeys'); kad.action = ska
kbf, kbb = key.key_blocks['VeyrWingFold'], key.key_blocks['VeyrBreath']
kbw = key.key_blocks['VeyrWingFoldWalk']   # walk corrective: membrane cleared over the swept legs
for f in (0, T):
    kbf.value = 0.0; kbf.keyframe_insert('value', frame=f); kbw.value = 1.0; kbw.keyframe_insert('value', frame=f)
for f, v in ((0, 0.05), (34, 0.25), (41, 0.24), (T, 0.05)): kbb.value = v; kbb.keyframe_insert('value', frame=f)
for fc in fcurves(ska):
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    fc.update()
ska.use_fake_user = True
C['walk'] = json.dumps({'frames': T, 'fps': 30, 'duty': DUTY, 'stride_units': S, 'stride_cm': S*CM, 'ground_speed_cm_s': S*CM/(T/30),
                        'lift_frames': {k: v[1] for k, v in FEET.items()}, 'swing_frames': SW})
s.frame_set(0)
print('RES', C['walk'])
