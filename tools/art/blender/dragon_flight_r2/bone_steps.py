import bpy, json, math
s = bpy.context.scene; D = bpy.data.objects['DRAGON_DEFORM']; out = {}
for n in BONES:
    prev = None; st = []
    for f in range(F0, F1 + 1):
        s.frame_set(f); pb = D.pose.bones[n]; q = (pb.parent.matrix.inverted() @ pb.matrix).to_quaternion()
        if prev is not None: st.append(round(math.degrees(prev.rotation_difference(q).angle), 1))
        prev = q
    out[n] = st
C = bpy.data.objects['DRAGON_CTRL']; s.frame_set(21); a = C.pose.bones['IK_HR'].matrix.copy(); s.frame_set(23); b = C.pose.bones['IK_HR'].matrix.copy()
out['ikHR_21_23'] = [round((b.translation - a.translation).length * 2155.8, 1), round(math.degrees(a.to_quaternion().rotation_difference(b.to_quaternion()).angle), 1)]
print('RES', json.dumps(out))
