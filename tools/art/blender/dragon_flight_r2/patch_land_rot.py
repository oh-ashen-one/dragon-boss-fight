p = "/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/author_land_r2.py"; s = open(p).read()
a = "            pos = Tw.to_translation().lerp(Ew.to_translation(), u); rot = Tw.to_quaternion().slerp(Ew.to_quaternion(), u)\n"
b = """            pos = Tw.to_translation().lerp(Ew.to_translation(), u)
            if ik not in QMID: QMID[ik] = tuck_world(ik, 10).to_quaternion().slerp(Ew.to_quaternion(), 0.5)
            qa_ = Tw.to_quaternion(); qm_ = QMID[ik].copy(); qe_ = Ew.to_quaternion(); qm_.make_compatible(qa_); qe_.make_compatible(qm_)
            rot = qa_.slerp(qm_, min(1, 2 * u)) if u < 0.5 else qm_.slerp(qe_, 2 * u - 1)
"""
assert s.count(a) == 1; s = s.replace(a, b); open(p, "w").write(s); print("ok")
