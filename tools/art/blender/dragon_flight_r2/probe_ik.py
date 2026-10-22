import bpy, json
C = bpy.data.objects['DRAGON_CTRL']; s = bpy.context.scene
ik = {}
for pb in C.pose.bones:
    for c in pb.constraints:
        if c.type == 'IK':
            ik[pb.name] = {'target': c.subtarget, 'chain': c.chain_count, 'pole': c.pole_subtarget, 'pole_angle': round(c.pole_angle, 3), 'use_tail': c.use_tail, 'stretch': c.use_stretch, 'iter': c.iterations}
chains = {}
for n, d in ik.items():
    b = C.data.bones[n]; seq = []; L = 0.
    for i in range(d['chain']):
        seq.append((b.name, round(b.length, 4))); L += b.length; b = b.parent
    chains[n] = {'bones': seq, 'len': round(L, 4)}
s.frame_set(0)
pos = {n: [round(x, 4) for x in C.matrix_world @ C.pose.bones[n].head] for n in ('IK_FL', 'IK_FR', 'IK_HL', 'IK_HR', 'C_bone_2', 'C_tripo::Spine_1', 'C_tripo::Spine_0')}
sh = {n: [round(x, 4) for x in C.matrix_world @ C.pose.bones[chains[n]['bones'][-1][0]].head] for n in chains}
print('RES', json.dumps({'ik': ik, 'chains': chains, 'f0': pos, 'chainRootF0': sh}))
