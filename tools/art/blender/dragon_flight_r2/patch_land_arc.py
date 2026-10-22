p = "/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/author_land_r2.py"; s = open(p).read()
a = "            pos = Tw.to_translation().lerp(Ew.to_translation(), u); rot = Tw.to_quaternion().slerp(Ew.to_quaternion(), u)\n"
assert s.count(a) == 1
b = a + """            if ik.startswith("IK_H"):   # arc about the hip, reach bulging to ~0.97 leg length mid-way: the knee passes straight instead of flipping
                Hj = P[THIGH[ik]].head.copy(); g_ = Tw.to_translation() - Hj; t_ = Ew.to_translation() - Hj
                Lm = REACH * sum(B[n].length for n in CHAINB[ik]); ax_ = g_.normalized().cross(t_.normalized())
                if ax_.length > 1e-6:
                    dq = Quaternion(ax_.normalized(), g_.normalized().angle(t_.normalized()) * u); base_l = g_.length + (t_.length - g_.length) * u
                    pos = Hj + (dq @ g_.normalized()) * (base_l + max(0., Lm - base_l) * math.sin(math.pi * u))
"""
s = s.replace(a, b)
s = s.replace("feet = {}; QMID = {}; THIGH = {", "CHAINB = {'IK_HL': ('C_tripo::1_Right_Limb_0', 'C_tripo::1_Right_Limb_1'), 'IK_HR': ('C_tripo::0_Right_Limb_0', 'C_tripo::0_Right_Limb_1')}; REACH = globals().get('REACH', 0.97)\nfeet = {}; QMID = {}; THIGH = {")
open(p, "w").write(s); print("ok")
