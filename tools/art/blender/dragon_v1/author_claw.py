"""Dragon_ClawSwipe_Blender_v1: 54 f @ 30 fps (1.8 s), in place, from/back to the idle r3 stance.
f0-14 rear onto the hind legs (both front paws lift, right paw cocked outside), torso winds to the right, wings open
for balance; f14-22 front-right claw swipes across (outside right -> inside left, forward) with the torso unwinding;
f22-24 hold at the end of the arc; f24-36 drop back onto all fours with a body dip; f36-54 recover, wings refold."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/attack_common.py').read())
T = 54
ch = {
 'C_tripo::Spine_0': [(6, dict(loc=Vector((-0.002, 0, -0.008)), q=PITCH_UP(2))), (14, dict(loc=Vector((-0.006, -0.003, 0.010)), q=PITCH_UP(12) @ YAW(-5))),
                      (19, dict(loc=Vector((0.0, 0.002, 0.008)), q=PITCH_UP(10) @ YAW(3))), (22, dict(loc=Vector((0.004, 0.004, 0.006)), q=PITCH_UP(8) @ YAW(6))),
                      (24, dict(loc=Vector((0.004, 0.004, 0.005)), q=PITCH_UP(8) @ YAW(6))), (30, dict(loc=Vector((0.004, 0.002, -0.018)), q=PITCH_UP(-3) @ YAW(3))),
                      (33, dict(loc=Vector((0.003, 0.001, -0.024)), q=PITCH_UP(-4) @ YAW(2))), (42, dict(loc=Vector((0.0, 0, -0.010)), q=PITCH_UP(0)))],
 'C_bone_2': [(14, dict(q=YAW(-10) @ ROLL(-3))), (19, dict(q=YAW(4) @ ROLL(2))), (22, dict(q=YAW(12) @ ROLL(4))), (24, dict(q=YAW(12) @ ROLL(4))), (32, dict(q=YAW(3) @ PITCH_UP(-2))), (42, dict(q=YAW(0)))],
 'C_bone_11': [(14, dict(q=PITCH_UP(-6) @ ROLL(-6))), (19, dict(q=PITCH_UP(8) @ ROLL(4))), (22, dict(q=PITCH_UP(10) @ ROLL(8))), (24, dict(q=PITCH_UP(10) @ ROLL(8))), (32, dict(q=PITCH_UP(0)))],
 'C_bone_6': [(14, dict(q=PITCH_UP(3))), (22, dict(q=PITCH_UP(-2))), (32, dict(q=PITCH_UP(0)))],
 'C_bone_3': [(14, dict(q=neckq(6, -8))), (19, dict(q=neckq(0, 4))), (22, dict(q=neckq(-2, 10))), (24, dict(q=neckq(-2, 10))), (33, dict(q=neckq(-8, 3))), (42, dict(q=neckq(-3, 0)))],
 'C_bone_4': [(15, dict(q=neckq(3, -6))), (20, dict(q=neckq(-1, 4))), (23, dict(q=neckq(-2, 8))), (25, dict(q=neckq(-2, 8))), (34, dict(q=neckq(-3, 2))), (43, dict(q=neckq(0.5, 0)))],
 'C_bone_5': [(16, dict(q=neckq(-4, -4))), (21, dict(q=neckq(2, 3))), (24, dict(q=neckq(3, 6))), (26, dict(q=neckq(3, 6))), (36, dict(q=neckq(5, 1))), (44, dict(q=neckq(2.4, 0)))],
 'C_VeyrJaw': [(14, dict(q=R(Y, 6))), (21, dict(q=R(Y, 14))), (26, dict(q=R(Y, 10))), (36, dict(q=R(Y, 1)))],
 'C_tripo::Spine_1': [(14, dict(q=PITCH_UP(-6) @ YAW(4))), (22, dict(q=PITCH_UP(-4) @ YAW(-5))), (32, dict(q=PITCH_UP(2))), (42, dict(q=PITCH_UP(0)))],
 'C_bone_18': [(14, dict(q=PITCH_UP(-8) @ YAW(6))), (22, dict(q=PITCH_UP(-6) @ YAW(-6))), (32, dict(q=PITCH_UP(-2) @ YAW(-3))), (44, dict(q=YAW(2)))],
 'C_tripo::Tail_0': [(16, dict(q=PITCH_UP(-6) @ YAW(8))), (24, dict(q=PITCH_UP(-5) @ YAW(-9))), (34, dict(q=YAW(-4))), (46, dict(q=YAW(-3)))],
 'C_tripo::Tail_1': [(18, dict(q=PITCH_UP(-4) @ YAW(9))), (26, dict(q=PITCH_UP(-4) @ YAW(-11))), (36, dict(q=YAW(-5))), (48, dict(q=YAW(-4)))],
 'C_tripo::Tail_2': [(20, dict(q=PITCH_UP(-3) @ YAW(10))), (28, dict(q=PITCH_UP(-3) @ YAW(-13))), (38, dict(q=YAW(-4))), (50, dict(q=YAW(5)))],
 'FOOT_bone_14': [(12, dict(q=R(Y, 0))), (17, dict(q=R(Y, -16))), (24, dict(q=R(Y, -16))), (29, dict(q=R(Y, 0)))],
}
for side, tag in (('R','PosZ'), ('L','NegZ')):
    lifted = wq(side, (1,0,0), -26) @ fold3_q('Root', side)     # swing the folded wing out off the flank before opening (clears the legs)
    for part in ('Root', 'Wrist', 'Elbow', 'Membrane'):
        ks = [(f, flare(part, side, u, flap=28.0 if f < 26 else 40.0)) for f, u in ((2, 0.0), (11, 0.50), (16, 0.64), (20, 0.68), (26, 0.62))]
        ks += [(6, lifted if part == 'Root' else fold3_q(part, side)), (33, lifted if part == 'Root' else fold3_q(part, side)), (39, lifted if part == 'Root' else fold3_q(part, side)), (44, fold3_q(part, side))]
        ch[f'C_VeyrWing{tag}{part}'] = [(f, dict(q=q)) for f, q in sorted(ks, key=lambda x: x[0])]
feet = {'IK_FR': [(4, Vector((0, 0, 0))), (10, Vector((-0.006, -0.012, 0.040))), (14, Vector((-0.012, -0.030, 0.070))),
                  (17, Vector((0.030, -0.008, 0.060))), (20, Vector((0.048, 0.060, 0.040))), (22, Vector((0.044, 0.105, 0.036))), (24, Vector((0.042, 0.108, 0.036))),
                  (28, Vector((0.012, 0.030, 0.020))), (31, Vector((0, 0, 0)))],
        'IK_FL': [(5, Vector((0, 0, 0))), (11, Vector((-0.004, 0.004, 0.030))), (16, Vector((-0.004, 0.006, 0.040))), (24, Vector((0.004, 0.004, 0.034))),
                  (28, Vector((0.002, 0, 0.010))), (30, Vector((0, 0, 0)))]}
sk = {'VeyrBreath': [(0, 0.0), (12, 0.8), (22, 0.3), (34, 0.6), (T, 0.0)], 'VeyrWingFold': [(0, 1.0), (6, 1.0), (10, 0.0), (28, 0.0), (33, 1.0), (T, 1.0)]}
build('CLAW_L', T, ch, sk, feet)
print('RES', json.dumps({'frames': T}))
