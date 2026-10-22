"""Dragon_Bite_Blender_v1: 48 f @ 30 fps (1.6 s), in place, from/back to the idle r3 stance.
f0-12 weight forward onto the front legs while the head draws back and the jaw opens (anticipation);
f12-18 lunge, jaw snaps shut at f18; f18-20 hold; f20-31 one head shake; f31-48 recover."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/attack_common.py').read())
T = 48
ch = {
 'C_tripo::Spine_0': [(10, dict(loc=Vector((0.006, 0, -0.016)), q=PITCH_UP(-2.5))), (16, dict(loc=Vector((0.014, 0, -0.021)), q=PITCH_UP(-5))),
                      (20, dict(loc=Vector((0.015, 0, -0.020)), q=PITCH_UP(-5))), (30, dict(loc=Vector((0.010, 0, -0.016)), q=PITCH_UP(-3))),
                      (40, dict(loc=Vector((0.0, 0, -0.009)), q=PITCH_UP(0.3)))],
 'C_bone_2': [(10, dict(q=PITCH_UP(2))), (16, dict(q=PITCH_UP(-4))), (30, dict(q=PITCH_UP(-2)))],
 'C_bone_3': [(4, dict(q=neckq(2))), (11, dict(q=neckq(15))), (15, dict(q=neckq(-14))), (18, dict(q=neckq(-21))), (20, dict(q=neckq(-21))),
              (24, dict(q=neckq(-18, 6))), (28, dict(q=neckq(-17, -5))), (31, dict(q=neckq(-15, 1))), (40, dict(q=neckq(-5)))],
 'C_bone_4': [(5, dict(q=neckq(1))), (12, dict(q=neckq(8))), (16, dict(q=neckq(-7))), (18, dict(q=neckq(-10))), (20, dict(q=neckq(-10))),
              (24, dict(q=neckq(-9, 8))), (28, dict(q=neckq(-9, -7))), (32, dict(q=neckq(-7, 1))), (41, dict(q=neckq(-1)))],
 'C_bone_5': [(6, dict(q=neckq(-2))), (12, dict(q=neckq(-10))), (17, dict(q=neckq(8))), (19, dict(q=neckq(11))), (21, dict(q=neckq(10))),
              (25, dict(q=neckq(9, 11))), (29, dict(q=neckq(9, -9))), (33, dict(q=neckq(6, 2))), (42, dict(q=neckq(3)))],
 'C_VeyrJaw': [(5, dict(q=R(Y, 3))), (12, dict(q=R(Y, 20))), (15, dict(q=R(Y, 30))), (17, dict(q=R(Y, 6))), (18, dict(q=R(Y, 0))), (20, dict(q=R(Y, 0))),
               (31, dict(q=R(Y, 0))), (38, dict(q=R(Y, 2)))],
 'C_tripo::Spine_1': [(10, dict(q=PITCH_UP(2))), (17, dict(q=PITCH_UP(-3))), (30, dict(q=PITCH_UP(-1)))],
 'C_bone_18': [(10, dict(q=PITCH_UP(-3))), (18, dict(q=PITCH_UP(-7))), (25, dict(q=YAW(-4))), (29, dict(q=YAW(4))), (36, dict(q=PITCH_UP(-1)))],
 'C_tripo::Tail_0': [(12, dict(q=PITCH_UP(-2))), (20, dict(q=PITCH_UP(-7))), (27, dict(q=YAW(-6))), (31, dict(q=YAW(5))), (38, dict(q=YAW(1)))],
 'C_tripo::Tail_1': [(14, dict(q=PITCH_UP(-1))), (22, dict(q=PITCH_UP(-6))), (29, dict(q=YAW(-7))), (33, dict(q=YAW(6))), (40, dict(q=YAW(1)))],
 'C_tripo::Tail_2': [(16, dict(q=PITCH_UP(0))), (24, dict(q=PITCH_UP(-6))), (31, dict(q=YAW(-8))), (35, dict(q=YAW(7))), (42, dict(q=YAW(1)))],
}
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part in ('Root', 'Wrist', 'Elbow', 'Membrane'):
        ch[f'C_VeyrWing{tag}{part}'] = [(f, dict(q=flare(part, side, u))) for f, u in ((8, 0.0), (17, 0.04), (24, 0.03), (36, 0.0))]   # wings stay folded (tiny lift)
sk = {'VeyrBreath': [(0, 0.0), (11, 0.7), (18, 0.2), (30, 0.4), (T, 0.0)], 'VeyrWingFold': [(0, 1.0), (T, 1.0)]}
build('BITE_L', T, ch, sk)
print('RES', json.dumps({'frames': T}))
