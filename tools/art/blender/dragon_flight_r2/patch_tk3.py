p = "/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/author_takeoff_r3.py"; s = open(p).read()
i0 = s.index("            pos = G.to_translation().lerp(Tw.to_translation(), u)\n            if ik not in QMID:")
i1 = s.index("            Mf = lift @ Matrix.Translation(pos)")
new = """            pos = G.to_translation().lerp(Tw.to_translation(), u); qg = G.to_quaternion(); qt = Tw.to_quaternion(); qt.make_compatible(qg); rot = qg.slerp(qt, u)
            if ik.startswith("IK_H"):   # via the extended (bind) leg: ground -> extended -> tuck (land-style), two-stage foot rotation
                par_ = TUCK[ik][2]; Ew = P[par_].matrix @ (B[par_].matrix_local.inverted() @ B[ik].matrix_local)
                if ik not in QMID: QMID[ik] = tuck_world(ik, QF).to_quaternion().slerp(Ew.to_quaternion(), 0.5)
                qe = Ew.to_quaternion(); qe.make_compatible(qg)
                if u < 0.5:
                    pos = G.to_translation().lerp(Ew.to_translation(), 2 * u); rot = qg.slerp(qe, 2 * u)
                else:
                    v2 = 2 * u - 1; pos = Ew.to_translation().lerp(Tw.to_translation(), v2); qm = QMID[ik].copy(); qm.make_compatible(qe); qt.make_compatible(qm)
                    rot = qe.slerp(qm, min(1, 2 * v2)) if v2 < 0.5 else qm.slerp(qt, 2 * v2 - 1)
"""
s = s[:i0] + new + s[i1:]
open(p, "w").write(s); print("ok")
