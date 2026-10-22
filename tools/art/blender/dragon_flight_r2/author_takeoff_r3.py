"""Dragon_TakeoffLand_Blender_v1: MODE='takeoff' (ground -> hover, 45 f) or MODE='land' (hover -> ground, 45 f).
Root carries altitude 0 <-> HOV (0.14 u = 302 cm) as root motion; ends/starts match the hover clip frame 0 and the
idle r3 stance. World-space IK feet: planted keys on the ground, per-frame keys while airborne that follow the body
(tuck offsets in the chest/hips frame, as in the hover clip)."""
SET_POSE = False
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/fold_pose_r2.py').read())
MODE = globals().get('MODE', 'takeoff'); T = 45; HOV = 0.14; SPREAD = 90.0
PFX = 'TKR2_L' if MODE == 'takeoff' else 'LDR2_L'
s.render.fps = 30; s.frame_start = 0; s.frame_end = T
reset_ctrl(PFX)
for a in bpy.data.actions:
    if a.name[:5] in ('IDLE_', 'IDLE2', 'IDLE3', 'WALK_', 'WALK2', 'TURN_', 'TURN2', 'HOVER', 'HOVR2', 'TKO_L', 'LND_L'): a.use_fake_user = True
def lay(name, ch, blend='COMBINE'): return make_layer(PFX, name, T, ch, blend=blend, length=T, cyclic=False)
def wq(side, axis, deg): return Quaternion(wing_side_axis(axis, side), math.radians(deg))
def wing_open(side, flap, twist): return wq(side, (1,0,0), -flap) @ wq(side, (0,1,0), SPREAD + twist)
def slerpq(a, b, u): return a.slerp(b, u)
TUCK = {'IK_FL': (Vector((0.01, -0.035, 0.165)), R(Y, 75), 'C_bone_2'), 'IK_FR': (Vector((0.01, 0.035, 0.165)), R(Y, 75), 'C_bone_2'),
        'IK_HL': (Vector((-0.17, -0.006, 0.23)), R(Y, 185), 'C_tripo::Spine_1'), 'IK_HR': (Vector((-0.175, 0.006, 0.22)), R(Y, 185), 'C_tripo::Spine_1')}
IK_HOV = {k: Matrix(v) for k, v in json.load(open('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/flight_r2/reports/ik_hover_v1r2_f0.json')).items()}
idle_neck = {'C_bone_3': -2.5, 'C_bone_4': 0.8, 'C_bone_5': 2.4}; hov_neck = {'C_bone_3': -11, 'C_bone_4': -4, 'C_bone_5': -4}
idle_tail_yaw = {'C_bone_18': 2.0, 'C_tripo::Tail_0': -3.0, 'C_tripo::Tail_1': -4.0, 'C_tripo::Tail_2': 5.0}
hov_tail_pitch = {'C_bone_18': -10, 'C_tripo::Tail_0': -6, 'C_tripo::Tail_1': -3, 'C_tripo::Tail_2': 0}
def ease(u): u = min(1, max(0, u)); return u*u*(3-2*u)
ch = {}
if MODE == 'takeoff':
    ch['C_tripo::Root'] = [(0, dict(loc=Vector((0,0,0)))), (17, dict(loc=Vector((0,0,0)))), (23, dict(loc=Vector((0,0,0.040)))), (27, dict(loc=Vector((0,0,0.072)))),
                           (30, dict(loc=Vector((0,0,0.071)))), (33, dict(loc=Vector((0,0,0.068)))), (40, dict(loc=Vector((0,0,0.128)))), (45, dict(loc=Vector((0,0,HOV))))]
    ch['C_tripo::Spine_0'] = [(0, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7))), (12, dict(loc=Vector((0,0,-0.030)), q=PITCH_UP(-4))),
                              (18, dict(loc=Vector((0,0,-0.022)), q=PITCH_UP(3))), (24, dict(loc=Vector((0,0,0.004)), q=PITCH_UP(13))),
                              (34, dict(loc=Vector((0,0,0.004)), q=PITCH_UP(21))), (45, dict(loc=Vector((0,0,-0.006)), q=PITCH_UP(20)))]
    ch['C_tripo::Spine_1'] = [(0, dict(q=PITCH_UP(0))), (12, dict(q=PITCH_UP(3))), (26, dict(q=PITCH_UP(-9))), (45, dict(q=PITCH_UP(-6)))]
    neck = {'C_bone_3': [(0, -2.5), (13, -7), (25, 4), (35, -8), (45, -11)], 'C_bone_4': [(0, 0.8), (14, -2), (27, 3), (45, -4)], 'C_bone_5': [(0, 2.4), (15, 5), (28, -3), (38, -5), (45, -4)]}
    # tail-side bones point -X: negative PITCH_UP lifts the tail clear of the ground as the body pitches nose-up
    tailp = {'C_bone_18': [(0, 0), (12, -1), (20, 1), (28, 1), (34, -7), (40, -13), (45, -10)], 'C_tripo::Tail_0': [(0, 0), (14, 0), (22, 2), (30, 2), (36, -3), (42, -9), (45, -6)],
             'C_tripo::Tail_1': [(0, 0), (16, 0), (24, 2), (32, 2), (38, -2), (44, -5), (45, -3)], 'C_tripo::Tail_2': [(0, 0), (18, 0), (26, 1), (34, 2), (40, -1), (45, 0)]}
    tail_yaw_end = 0.0
    wingkeys = lambda side: {'Root': [(0, fold3_q('Root', side)), (7, slerpq(fold3_q('Root', side), wing_open(side, 50, -5), 0.25)), (16, wing_open(side, 52, -5)),
                                      (22, wing_open(side, -14, 10)), (27, wing_open(side, -32, 8)), (33, wing_open(side, 30, -10)), (39, wing_open(side, -18, 8)), (45, wing_open(side, 42, -5))],
                             'Wrist': [(0, fold3_q('Wrist', side)), (14, Quaternion()), (31, wq(side, (1,0,0), 20)), (37, Quaternion()), (45, Quaternion())],
                             'Elbow': [(0, fold3_q('Elbow', side)), (14, Quaternion()), (45, Quaternion())],
                             'Membrane': [(0, fold3_q('Membrane', side)), (14, Quaternion()), (45, Quaternion())]}
    sk = {'VeyrWingFoldWalk': [(0, 1.0), (4, 1.0), (11, 0.0), (45, 0.0)], 'VeyrWingFold': [(0, 0.0), (45, 0.0)], 'VeyrBreath': [(0, 0.1), (12, 0.6), (24, 0.1), (45, 0.2)]}
    plant = {'IK_FL': (0, 16, 30), 'IK_FR': (0, 16, 30), 'IK_HL': (0, HU, HT), 'IK_HR': (0, HU, HT)}   # planted until, tucked by
else:
    ch['C_tripo::Root'] = [(0, dict(loc=Vector((0,0,HOV)))), (10, dict(loc=Vector((0,0,0.115)))), (18, dict(loc=Vector((0,0,0.045)))), (23, dict(loc=Vector((0,0,0.0)))), (45, dict(loc=Vector((0,0,0))))]
    ch['C_tripo::Spine_0'] = [(0, dict(loc=Vector((0,0,-0.006)), q=PITCH_UP(20))), (12, dict(loc=Vector((0,0,0.0)), q=PITCH_UP(26))), (22, dict(loc=Vector((0,0,-0.012)), q=PITCH_UP(6))),
                              (29, dict(loc=Vector((0,0,-0.032)), q=PITCH_UP(-4))), (37, dict(loc=Vector((0,0,-0.008)), q=PITCH_UP(0.8))), (45, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7)))]
    ch['C_tripo::Spine_1'] = [(0, dict(q=PITCH_UP(-6))), (20, dict(q=PITCH_UP(-3))), (29, dict(q=PITCH_UP(4))), (45, dict(q=PITCH_UP(0)))]
    neck = {'C_bone_3': [(0, -11), (20, -5), (31, -10), (39, -1), (45, -2.5)], 'C_bone_4': [(0, -4), (22, -1), (32, -4), (45, 0.8)], 'C_bone_5': [(0, -4), (24, 0), (33, 6), (40, 1.5), (45, 2.4)]}
    tailp = {'C_bone_18': [(0, -10), (18, -12), (27, -3), (34, -6), (45, 0)], 'C_tripo::Tail_0': [(0, -6), (20, -9), (29, -1), (36, -4), (45, 0)],
             'C_tripo::Tail_1': [(0, -3), (22, -6), (31, 1), (38, -3), (45, 0)], 'C_tripo::Tail_2': [(0, 0), (24, -4), (33, 2), (40, -1), (45, 0)]}
    wingkeys = lambda side: {'Root': [(0, wing_open(side, 42, -5)), (8, wing_open(side, -30, 20)), (16, wing_open(side, 36, 25)), (23, wing_open(side, -22, 15)),
                                      (28, wing_open(side, 10, 0)), (33, slerpq(wing_open(side, 10, 0), fold3_q('Root', side), 0.35)),
                                      (39, slerpq(wing_open(side, 10, 0), fold3_q('Root', side), 0.8)), (45, fold3_q('Root', side))],
                             'Wrist': [(0, Quaternion()), (26, Quaternion()), (45, fold3_q('Wrist', side))],
                             'Elbow': [(0, Quaternion()), (26, Quaternion()), (45, fold3_q('Elbow', side))],
                             'Membrane': [(0, Quaternion()), (26, Quaternion()), (45, fold3_q('Membrane', side))]}
    sk = {'VeyrWingFoldWalk': [(0, 0.0), (34, 0.0), (45, 1.0)], 'VeyrWingFold': [(0, 0.0), (45, 0.0)], 'VeyrBreath': [(0, 0.2), (30, 0.7), (45, 0.3)]}
    plant = {'IK_HL': (22, None, None), 'IK_HR': (22, None, None), 'IK_FL': (25, None, None), 'IK_FR': (25, None, None)}   # contact frame
for b, ks in neck.items(): ch[b] = [(f, dict(q=PITCH_UP(v))) for f, v in ks]
for b, ks in tailp.items():
    yaw0 = idle_tail_yaw[b] if MODE == 'takeoff' else 0.0; yaw1 = 0.0 if MODE == 'takeoff' else idle_tail_yaw[b]
    ch[b] = [(f, dict(q=YAW(yaw0 + (yaw1-yaw0)*ease(f/T)) @ PITCH_UP(v))) for f, v in ks]
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part, ks in wingkeys(side).items(): ch[f'C_VeyrWing{tag}{part}'] = [(f, dict(q=q)) for f, q in ks]
# boundary poses sampled from the neighbouring clips (local channels), so the chain idle -> takeoff -> hover -> land -> idle is continuous
WD = '/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/reports/'
pose_idle = json.load(open(WD + 'pose_idle_r3_f0.json')); pose_hov = json.load(open('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/flight_r2/reports/pose_hover_v1r2_f0.json'))
first, last = (pose_idle, pose_hov) if MODE == 'takeoff' else (pose_hov, pose_idle)
for bname in set(first) | set(last):
    if bname.startswith('C_tripo::Root'): continue
    keys = [k for k in ch.get(bname, []) if 0 < k[0] < T]
    for f, src in ((0, first), (T, last)):
        if bname in src: keys.append((f, dict(ql=src[bname]['q'], locl=src[bname]['loc'], scl=src[bname]['sc'])))
    keys.sort(key=lambda x: x[0])
    # inner keys keep their authored world-space rotations; add matching loc/scale defaults so channels stay consistent
    for i, (f, k) in enumerate(keys):
        if 0 < f < T:
            k.setdefault('loc', Vector((0, 0, 0))) if 'locl' not in k and any('locl' in kk for _, kk in keys) and 'loc' not in k else None
    ch[bname] = keys
lay('0_Body', ch, blend='REPLACE')
# ---- feet: evaluate the body, then key world IK targets per frame where they ride it
sc = bpy.context.scene
def tuck_world(ik, f):
    off, q, par = TUCK[ik]
    sc.frame_set(f)
    Mp = P[par].matrix                                   # armature space (armature object at identity)
    rel = B[par].matrix_local.inverted() @ B[ik].matrix_local
    basis = Matrix.Translation(local_v(ik, off)) @ local_q(ik, q).to_matrix().to_4x4()
    return Mp @ rel @ basis
def ground_world(ik):
    return B[ik].matrix_local @ Matrix.Translation(local_v(ik, Vector((0, 0, GROUND[ik]))))
feet = {}; QMID = {}; THIGH = {"IK_HL": "C_tripo::1_Right_Limb_0", "IK_HR": "C_tripo::0_Right_Limb_0"}
for ik in TUCK:
    G = ground_world(ik); keys = []
    if MODE == 'takeoff':
        until, tuck_by = plant[ik][1], plant[ik][2]
        keys.append((0, G)); keys.append((until, G))
        for f in range(until+1, T+1):
            u = ease((f-until)/(tuck_by-until)); Tw = tuck_world(ik, f)
            lift = Matrix.Translation(Vector((0, 0, 0.02*math.sin(math.pi*min(1, (f-until)/(tuck_by-until))))))
            pos = G.to_translation().lerp(Tw.to_translation(), u); qg = G.to_quaternion(); qt = Tw.to_quaternion(); qt.make_compatible(qg); rot = qg.slerp(qt, u)
            if ik.startswith("IK_H"):   # via the extended (bind) leg: ground -> extended -> tuck (land-style), two-stage foot rotation
                par_ = TUCK[ik][2]; Ew = P[par_].matrix @ (B[par_].matrix_local.inverted() @ B[ik].matrix_local)
                if ik not in QMID: QMID[ik] = tuck_world(ik, QF).to_quaternion().slerp(Ew.to_quaternion(), 0.5)
                qe = Ew.to_quaternion(); qe.make_compatible(qg)
                if u < 0.5:
                    pos = G.to_translation().lerp(Ew.to_translation(), 2 * u); rot = qg.slerp(qe, 2 * u)
                else:
                    v2 = 2 * u - 1; pos = Ew.to_translation().lerp(Tw.to_translation(), v2); qm = QMID[ik].copy(); qm.make_compatible(qe); qt.make_compatible(qm)
                    rot = qe.slerp(qm, min(1, 2 * v2)) if v2 < 0.5 else qm.slerp(qt, 2 * v2 - 1)
            Mf = lift @ Matrix.Translation(pos) @ rot.to_matrix().to_4x4()
            if f >= tuck_by:   # blend onto the exact hover r2 frame-0 IK matrix (includes the hover lift offsets)
                wv = ease((f - tuck_by) / max(1, T - tuck_by)); Mf = Matrix.Translation(Mf.to_translation().lerp(IK_HOV[ik].to_translation(), wv)) @ Mf.to_quaternion().slerp(IK_HOV[ik].to_quaternion(), wv).to_matrix().to_4x4()
            keys.append((f, Mf))
    else:
        contact = plant[ik][0]
        par = TUCK[ik][2]
        for f in range(0, contact):
            Tw = tuck_world(ik, f)                                            # tucked, riding the body
            Ew = P[par].matrix @ (B[par].matrix_local.inverted() @ B[ik].matrix_local)   # legs extended (bind leg), riding the body
            u = ease((f-5)/10.0); v = ease((f-(contact-5))/5.0)               # untuck f5-15, then meet the landing spot
            pos = Tw.to_translation().lerp(Ew.to_translation(), u); rot = Tw.to_quaternion().slerp(Ew.to_quaternion(), u)
            gp = G.to_translation(); pos = pos.lerp(gp, v); pos.z = max(pos.z, gp.z); rot = rot.slerp(G.to_quaternion(), v)
            keys.append((f, Matrix.Translation(pos) @ rot.to_matrix().to_4x4()))
        keys.append((contact, G)); keys.append((T, G))
    feet[ik] = keys
sc.frame_set(0)
act = bpy.data.actions.new(PFX+'1_Feet'); ad.action = act
for ik, keys in feet.items():
    pb = P[ik]; prev = None
    for f, Mw in keys:
        basis = B[ik].matrix_local.inverted() @ Mw
        loc, rot, _ = basis.decompose()
        if prev is not None and prev.dot(rot) < 0: rot.negate()
        prev = rot.copy(); pb.location = loc; pb.rotation_quaternion = rot
        pb.keyframe_insert('location', frame=f, group=ik); pb.keyframe_insert('rotation_quaternion', frame=f, group=ik)
    pb.location = (0,0,0); pb.rotation_quaternion = (1,0,0,0)
for fc in fcurves(act):
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    fc.update()
ad.action = None
tr = ad.nla_tracks.new(); tr.name = '1_Feet'; st = tr.strips.new('1_Feet', 0, act); st.blend_type = 'REPLACE'; st.extrapolation = 'HOLD'
try:
    if st.action_slot is None and act.slots: st.action_slot = act.slots[0]
except AttributeError: pass
M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
kad = key.animation_data or key.animation_data_create()
old = bpy.data.actions.get(PFX+'ShapeKeys')
if old: bpy.data.actions.remove(old)
ska = bpy.data.actions.new(PFX+'ShapeKeys'); kad.action = ska
for name, vals in sk.items():
    kb = key.key_blocks[name]
    for f, v in vals: kb.value = v; kb.keyframe_insert('value', frame=f)
ska.use_fake_user = True
sc.frame_set(0)
print('RES', json.dumps({'mode': MODE, 'frames': T, 'tracks': [t.name for t in ad.nla_tracks]}))
