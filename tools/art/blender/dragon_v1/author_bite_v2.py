"""Dragon_Bite_Blender_v2 (critic FAIL fixes on v1): 54 f @ 30 fps (1.8 s), in place overall (paws step out and back).
f0-12 draw back with the chest dropping onto the front legs, jaw opening; f12-18 chest/shoulders drive forward
~0.14 u body plus neck reach while the front paws step 0.13 u and the hinds 0.115 u, snout held near level, jaw snaps at f18;
f18-20 hold; f20-31 one hard head shake (+-16 deg yaw); f31-54 paws step back and the body recovers to idle."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/attack_common.py').read())
T = 54
ch = {
 'C_tripo::Spine_0': [(11, dict(loc=Vector((-0.030, 0, -0.026)), q=PITCH_UP(-4))), (17, dict(loc=Vector((0.135, 0, -0.016)), q=PITCH_UP(-2))),
                      (20, dict(loc=Vector((0.140, 0, -0.016)), q=PITCH_UP(-2))), (31, dict(loc=Vector((0.128, 0, -0.014)), q=PITCH_UP(-1))),
                      (40, dict(loc=Vector((0.030, 0, -0.012)), q=PITCH_UP(0))), (47, dict(loc=Vector((0.0, 0, -0.010)), q=PITCH_UP(-0.4)))],
 'C_bone_2': [(11, dict(q=PITCH_UP(-3))), (17, dict(q=PITCH_UP(-2))), (31, dict(q=PITCH_UP(-1)))],
 'C_bone_3': [(4, dict(q=neckq(4))), (11, dict(q=neckq(26))), (15, dict(q=neckq(-14))), (18, dict(q=neckq(-22))), (20, dict(q=neckq(-22))),
              (23, dict(q=neckq(-21, 5))), (27, dict(q=neckq(-21, -4))), (31, dict(q=neckq(-9, 1))), (42, dict(q=neckq(-4)))],
 'C_bone_4': [(5, dict(q=neckq(2))), (12, dict(q=neckq(9))), (16, dict(q=neckq(-3))), (18, dict(q=neckq(-5))), (20, dict(q=neckq(-5))),
              (24, dict(q=neckq(-5, 5))), (28, dict(q=neckq(-5, -5))), (32, dict(q=neckq(-4, 1))), (43, dict(q=neckq(0)))],
 'C_bone_5': [(6, dict(q=neckq(-3))), (12, dict(q=neckq(-12))), (17, dict(q=neckq(22))), (19, dict(q=neckq(26))), (21, dict(q=neckq(25))),
              (25, dict(q=neckq(23, 9))), (29, dict(q=neckq(22, -9))), (33, dict(q=neckq(8, 2))), (44, dict(q=neckq(3)))],
 'C_VeyrJaw': [(5, dict(q=R(Y, 3))), (12, dict(q=R(Y, 22))), (16, dict(q=R(Y, 30))), (17, dict(q=R(Y, 8))), (18, dict(q=R(Y, 0))), (20, dict(q=R(Y, 0))),
               (31, dict(q=R(Y, 0))), (40, dict(q=R(Y, 2)))],
 'C_tripo::Spine_1': [(11, dict(q=PITCH_UP(3))), (18, dict(q=PITCH_UP(-3))), (31, dict(q=PITCH_UP(-1)))],
 'C_bone_18': [(11, dict(q=PITCH_UP(-4))), (19, dict(q=PITCH_UP(-8))), (25, dict(q=YAW(-6))), (29, dict(q=YAW(6))), (38, dict(q=PITCH_UP(-1)))],
 'C_tripo::Tail_0': [(13, dict(q=PITCH_UP(-3))), (21, dict(q=PITCH_UP(-8))), (27, dict(q=YAW(-8))), (31, dict(q=YAW(7))), (40, dict(q=YAW(1)))],
 'C_tripo::Tail_1': [(15, dict(q=PITCH_UP(-2))), (23, dict(q=PITCH_UP(-7))), (29, dict(q=YAW(-9))), (33, dict(q=YAW(8))), (42, dict(q=YAW(1)))],
 'C_tripo::Tail_2': [(17, dict(q=PITCH_UP(-1))), (25, dict(q=PITCH_UP(-7))), (31, dict(q=YAW(-10))), (35, dict(q=YAW(9))), (44, dict(q=YAW(1)))],
}
STEPF = Vector((0.13, 0, 0)); STEPH = Vector((0.115, 0, 0))
feet = {}
for ik, st, (l0, l1, l2), (b0, b1, b2) in (('IK_FL', STEPF, (12, 14.5, 17), (31, 34, 37)), ('IK_FR', STEPF, (13, 15.5, 18), (32, 35, 38)),
                                         ('IK_HL', STEPH, (12.5, 15, 17.5), (35, 37.5, 40)), ('IK_HR', STEPH, (13, 15.5, 18), (36, 38.5, 41))):
    lift = Vector((0, 0, 0.018))
    feet[ik] = [(l0, Vector((0, 0, 0))), (l1, st*0.5 + lift), (l2, st), (b0, st), (b1, st*0.5 + lift), (b2, Vector((0, 0, 0)))]
sk = {'VeyrBreath': [(0, 0.0), (11, 0.8), (18, 0.2), (31, 0.4), (T, 0.0)], 'VeyrWingFold': [(0, 1.0), (T, 1.0)]}
build('BITE2_L', T, ch, sk, feet)
print('RES', json.dumps({'frames': T}))
