"""Knee hint for 2-bone IK without a pole: key the IK chain bones' FK basis (the solver's start pose) along a slerp between
the evaluated (IK-solved) local rotations at FA and FB, every frame in (FA, FB), on the REPLACE body action. Globals: CHAINS, FA, FB, PFX."""
import bpy, json
s = bpy.context.scene; C = bpy.data.objects['DRAGON_CTRL']; P = C.pose.bones; B = C.data.bones
act = bpy.data.actions[PFX + '0_Body']
def visual_basis(n):
    pb = P[n]; b = B[n]
    par = P[b.parent.name].matrix @ (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
    return (par.inverted() @ pb.matrix).to_quaternion()
res = {}
for chain, (fa, fb) in CHAINS.items():
    for n in chain:
        s.frame_set(fa); qa = visual_basis(n); s.frame_set(fb); qb = visual_basis(n); qb.make_compatible(qa)
        ad = C.animation_data; prev_act = ad.action; tr_states = [(t, t.mute) for t in ad.nla_tracks]
        keys = [(f, qa.slerp(qb, (f - fa) / (fb - fa))) for f in range(fa, fb + 1)]
        fcs = {}
        for l in act.layers:
            for st in l.strips:
                for cb in st.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path == f'pose.bones["{n}"].rotation_quaternion': fcs[fc.array_index] = fc
        if len(fcs) != 4:
            res[n] = 'no rotation fcurves'; continue
        for f, q in keys:
            for i in range(4): fcs[i].keyframe_points.insert(f, q[i], options={'FAST'})
        for fc in fcs.values(): fc.update()
        res[n] = [fa, fb]
s.frame_set(0); print('RES', json.dumps(res))
