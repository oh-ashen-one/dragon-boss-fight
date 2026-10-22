"""Dragon_FireBreath_Blender_v1: 105 f @ 30 fps (3.5 s), in place, from and back to the idle r3 stance.
f0-30 rear onto the hind legs (front paws lift), neck coils back, chest inflates (VeyrBreath 1.8), jaw starts to open;
f31-34 committed thrust: front paws slam down, neck/head drive forward, jaw wide; f36-39 hold at full extension;
f39-84 sweep ~30 deg left -> right with the jaw held open while the chest deflates; f84-92 recoil; f92-105 settle.
Wings half-flare f14-90; tail counterbalances."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/attack_common.py').read())
T = 105
ch = {
 'C_tripo::Spine_0': [(14, dict(loc=Vector((-0.002, 0, -0.010)), q=PITCH_UP(2))), (28, dict(loc=Vector((-0.004, 0, 0.003)), q=PITCH_UP(8))),
                      (33, dict(loc=Vector((0.006, 0, -0.019)), q=PITCH_UP(-4))), (37, dict(loc=Vector((0.007, 0, -0.017)), q=PITCH_UP(-3.5))),
                      (60, dict(loc=Vector((0.006, 0, -0.016)), q=PITCH_UP(-3) @ YAW(-2))), (84, dict(loc=Vector((0.005, 0, -0.015)), q=PITCH_UP(-3) @ YAW(3))),
                      (91, dict(loc=Vector((-0.002, 0, -0.008)), q=PITCH_UP(2))), (98, dict(loc=Vector((0, 0, -0.012)), q=PITCH_UP(-1)))],
 'C_bone_2': [(14, dict(q=PITCH_UP(2), sc=1.01)), (28, dict(q=PITCH_UP(6), sc=1.02)), (33, dict(q=PITCH_UP(-4), sc=1.02)), (60, dict(q=PITCH_UP(-3), sc=1.02)),
              (84, dict(q=PITCH_UP(-2), sc=1.0)), (92, dict(q=PITCH_UP(1), sc=1.0))],
 'C_bone_6': [(28, dict(q=ROLL(3))), (33, dict(q=ROLL(-2))), (84, dict(q=ROLL(-1)))], 'C_bone_11': [(28, dict(q=ROLL(-3))), (33, dict(q=ROLL(2))), (84, dict(q=ROLL(1)))],
 # neck: coil back (raise base, tuck chin), thrust forward, hold, sweep left -> right, recoil
 'C_bone_3': [(12, dict(q=neckq(8))), (28, dict(q=neckq(26))), (32, dict(q=neckq(-10))), (35, dict(q=neckq(-17))), (39, dict(q=neckq(-16, 6))),
              (61, dict(q=neckq(-15, 0))), (84, dict(q=neckq(-15, -6))), (88, dict(q=neckq(6, -3))), (95, dict(q=neckq(-4, 0)))],
 'C_bone_4': [(14, dict(q=neckq(4))), (29, dict(q=neckq(14))), (33, dict(q=neckq(-4))), (36, dict(q=neckq(-9))), (39, dict(q=neckq(-8, 5.5))),
              (62, dict(q=neckq(-8, 0))), (84, dict(q=neckq(-8, -5.5))), (89, dict(q=neckq(4, -2))), (96, dict(q=neckq(0, 0)))],
 'C_bone_5': [(16, dict(q=neckq(-6))), (30, dict(q=neckq(-14))), (34, dict(q=neckq(6))), (37, dict(q=neckq(9))), (39, dict(q=neckq(8, 4))),
              (63, dict(q=neckq(8, 0))), (84, dict(q=neckq(8, -4))), (90, dict(q=neckq(-6, -1))), (97, dict(q=neckq(3, 0)))],
 'C_VeyrJaw': [(20, dict(q=R(Y, 2))), (30, dict(q=R(Y, 12))), (34, dict(q=R(Y, 27))), (39, dict(q=R(Y, 28))), (60, dict(q=R(Y, 26))), (84, dict(q=R(Y, 28))),
               (89, dict(q=R(Y, 5))), (93, dict(q=R(Y, 0)))],
 'C_tripo::Spine_1': [(28, dict(q=PITCH_UP(-4))), (34, dict(q=PITCH_UP(3))), (84, dict(q=PITCH_UP(2)))],
 # tail: presses down and swings opposite as the front rears, whips on the thrust, sways against the sweep
 'C_bone_18': [(28, dict(q=PITCH_UP(-9))), (35, dict(q=PITCH_UP(-4))), (60, dict(q=PITCH_UP(-2) @ YAW(4))), (84, dict(q=PITCH_UP(-2) @ YAW(-4))), (92, dict(q=PITCH_UP(-1)))],
 'C_tripo::Tail_0': [(30, dict(q=PITCH_UP(-6))), (37, dict(q=PITCH_UP(-7))), (63, dict(q=YAW(6))), (87, dict(q=YAW(-6))), (95, dict(q=PITCH_UP(-1)))],
 'C_tripo::Tail_1': [(32, dict(q=PITCH_UP(-4))), (39, dict(q=PITCH_UP(-8))), (66, dict(q=YAW(8))), (90, dict(q=YAW(-8))), (98, dict(q=PITCH_UP(-1)))],
 'C_tripo::Tail_2': [(34, dict(q=PITCH_UP(-3))), (41, dict(q=PITCH_UP(-9))), (69, dict(q=YAW(10))), (93, dict(q=YAW(-9))), (100, dict(q=YAW(2)))],
}
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part in ('Root', 'Wrist', 'Elbow', 'Membrane'):
        ch[f'C_VeyrWing{tag}{part}'] = [(f, dict(q=flare(part, side, u))) for f, u in ((10, 0.0), (24, 0.35), (33, 0.5), (36, 0.46), (84, 0.42), (92, 0.15), (100, 0.0))]
feet = {'IK_FL': [(8, Vector((0, 0, 0))), (14, Vector((-0.002, 0, 0.012))), (22, Vector((-0.004, 0, 0.030))), (29, Vector((-0.002, 0, 0.038))), (33, Vector((0.0, 0, 0)))],
        'IK_FR': [(8, Vector((0, 0, 0))), (14, Vector((-0.002, 0, 0.012))), (23, Vector((-0.004, 0, 0.029))), (29, Vector((-0.002, 0, 0.037))), (33, Vector((0.0, 0, 0)))]}
sk = {'VeyrBreath': [(0, 0.0), (12, 0.6), (29, 1.8), (36, 1.5), (84, 0.3), (95, 0.0), (T, 0.0)],
      'VeyrWingFold': [(0, 1.0), (12, 1.0), (28, 0.45), (86, 0.45), (100, 1.0), (T, 1.0)]}
build('FIRE_L', T, ch, sk, feet)
print('RES', json.dumps({'frames': T, 'tracks': [t.name for t in ad.nla_tracks]}))
