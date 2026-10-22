"""Dragon_Turn_Blender_v1r2 (critic round 2: r3 fold, weight onto the inside legs, 18 f swings, tail curl settle). From v1: 90 deg turn to the left (counter-clockwise from above) in place, 72 f @ 30 fps (2.4 s).
Root motion: tripo::Root carries the yaw about a pivot at the centre of the four feet (x = PIV), so the root
also translates (c - Rz(psi) c). Feet: two diagonal-pair steps each (A = FL+HR, B = FR+HL), 45 deg per step, 15-frame swings,
planted feet fixed in world. Body overlays: head/neck lead, chest leads, hips and tail lag then settle."""
SET_POSE = False
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
T = 84; PIV = Vector((0.177, 0.0, 0.0)); PFX = 'TURN2_L'
s.render.fps = 30; s.frame_start = 0; s.frame_end = T
reset_ctrl(PFX)
for a in bpy.data.actions:
    if a.name.startswith(('IDLE_L', 'IDLE2_L', 'IDLE3_L', 'WALK_L', 'WALK2_L', 'TURN_L')): a.use_fake_user = True
def lay(name, ch, blend='COMBINE'): return make_layer(PFX, name, T, ch, blend=blend, length=T, cyclic=False)
def ease(u): u = min(1, max(0, u)); return u*u*(3-2*u)
T0, T1 = 6, 78                                   # yaw window
def psi(f):                                      # root yaw, gentle ease at both ends, ~linear in the middle
    u = (f - T0)/(T1 - T0)
    if u <= 0: return 0.0
    if u >= 1: return 90.0
    return 90.0*(0.5*ease(u) + 0.5*u)
def rz(v, deg):
    a = math.radians(deg); c_, s_ = math.cos(a), math.sin(a)
    return Vector((v.x*c_ - v.y*s_, v.x*s_ + v.y*c_, v.z))
# ---- root (REPLACE-free: its own layer so the base can hold the stance)
root = [(f, dict(q=YAW(psi(f)), loc=PIV - rz(PIV, psi(f)))) for f in range(0, T+1, 3)]
# ---- base stance
base = {'C_tripo::Spine_0': [(0, dict(loc=Vector((0,0,-0.0105)), q=PITCH_UP(-0.7)))],
        'C_bone_3': [(0, dict(q=PITCH_UP(-3.0)))], 'C_bone_4': [(0, dict(q=PITCH_UP(0.8)))], 'C_bone_5': [(0, dict(q=PITCH_UP(2.6)))],
        'C_tripo::Root': root}
for side, tag in (('R','PosZ'), ('L','NegZ')):
    for part in ('Root','Wrist','Elbow','Membrane'): base[f'C_VeyrWing{tag}{part}'] = [(0, dict(q=fold3_q(part, side)))]
# ---- feet: world-fixed, rotate about the pivot in 30 deg steps
B = C.data.bones
STEPS = {'A': [(6, 24, 45), (42, 60, 90)], 'B': [(24, 42, 45), (60, 78, 90)]}
PAIR = {'FL': 'A', 'HR': 'A', 'FR': 'B', 'HL': 'B'}
HGT = {'FL': 0.011, 'FR': 0.011, 'HL': 0.009, 'HR': 0.009}
for leg, pair in PAIR.items():
    ctl = 'IK_'+leg; P0 = B[ctl].head_local.copy(); P0.z = 0.0
    g0 = Vector((0, 0, GROUND[ctl]))
    keys = [(0, dict(loc=g0, q=YAW(0)))]; ang = 0.0
    for (lf, ld, a1) in STEPS[pair]:
        keys.append((lf, dict(loc=g0 + rz(P0 - PIV, ang) + PIV - P0, q=YAW(ang))))
        for u, hz in ((0.25, 0.75), (0.5, 1.0), (0.75, 0.55)):
            am = ang + (a1 - ang)*(0.5 - 0.5*math.cos(math.pi*u))
            keys.append((lf + u*(ld-lf), dict(loc=g0 + rz(P0 - PIV, am) + PIV - P0 + Vector((0, 0, HGT[leg]*hz)), q=YAW(am))))
        keys.append((ld, dict(loc=g0 + rz(P0 - PIV, a1) + PIV - P0, q=YAW(a1))))
        ang = a1
    keys.append((T, dict(loc=g0 + rz(P0 - PIV, 90) + PIV - P0, q=YAW(90))))
    base[ctl] = keys
lay('0_Base', base, blend='REPLACE')
# ---- body overlays (relative to the rotating root)
def k(*pairs, fn): return [(f, fn(v)) for f, v in pairs]
body = {
 # anticipation: weight back and to the right, then forward/into the turn; bob at pair landings
 'C_tripo::Spine_0': [(0, dict(loc=Vector((0,0,0)))), (6, dict(loc=Vector((-0.004, -0.004, -0.002)), q=ROLL(1.0))),
                      (14, dict(loc=Vector((0.0, 0.006, -0.0085)), q=ROLL(-5.0))), (27, dict(loc=Vector((0.0, 0.007, -0.0105)), q=ROLL(-5.5))),
                      (36, dict(loc=Vector((0.0, 0.006, -0.0080)), q=ROLL(-4.5))), (47, dict(loc=Vector((0.0, 0.004, -0.0095)), q=ROLL(-3.5))),
                      (58, dict(loc=Vector((0.0, 0.003, -0.0050)), q=ROLL(-2.0))), (66, dict(loc=Vector((0.0, 0.002, -0.0060)), q=ROLL(-1.5))),
                      (78, dict(loc=Vector((0.0, 0.0, -0.0040)), q=ROLL(0.6))), (84, dict(loc=Vector((0, 0, -0.0012)), q=ROLL(0.0)))],
 'C_bone_2': k((0, 0), (6, -2), (19, 7), (47, 6), (69, 3), (78, -1.5), (84, 0), fn=lambda v: dict(q=YAW(v))),                 # chest leads
 'C_tripo::Spine_1': k((0, 0), (9, 2), (24, -6), (50, -6), (71, -2), (79, 2), (84, 0), fn=lambda v: dict(q=YAW(v))),          # hips lag, overshoot
 'C_bone_3': k((0, 0), (5, 6), (15, 9), (47, 8), (65, 4), (76, -2), (84, 0), fn=lambda v: dict(q=YAW(v))),                    # neck leads
 'C_bone_4': k((0, 0), (6, 5), (19, 8), (50, 6), (69, 2), (79, -1.5), (84, 0), fn=lambda v: dict(q=YAW(v))),
 'C_bone_5': k((0, 0), (8, 7), (22, 9), (52, 6), (71, 0), (80, -2.5), (84, -1), fn=lambda v: dict(q=YAW(v))),                # eyes/head first, settles last
 'C_bone_18': k((0, 0), (13, 3), (30, -7), (56, -7), (70, 3), (76, 5), (84, 3), fn=lambda v: dict(q=YAW(v))),                  # tail drags, whips through, settles curled
 'C_tripo::Tail_0': k((0, 0), (15, 3), (34, -9), (60, -9), (72, 4), (79, 8), (84, 6), fn=lambda v: dict(q=YAW(v))),
 'C_tripo::Tail_1': k((0, 0), (18, 3), (37, -11), (63, -10), (75, 4), (82, 10), (84, 9), fn=lambda v: dict(q=YAW(v))),
 'C_tripo::Tail_2': k((0, 0), (20, 4), (41, -13), (66, -12), (78, 3), (84, 12), fn=lambda v: dict(q=YAW(v))),
}
for side, tag in (('R','PosZ'), ('L','NegZ')):  # wings ride the chest yaw with delay
    body[f'C_VeyrWing{tag}Root'] = k((0, 0), (11, -1.5), (24, 2.0), (48, 1.5), (67, -1.0), (72, 0), fn=lambda v: dict(q=YAW(v)))
lay('1_Body', body)
# shape keys: walk fold corrective on, subtle breath
M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
kad = key.animation_data or key.animation_data_create()
old = bpy.data.actions.get(PFX+'ShapeKeys')
if old: bpy.data.actions.remove(old)
ska = bpy.data.actions.new(PFX+'ShapeKeys'); kad.action = ska
for name, vals in (('VeyrWingFold', ((0, 0.0), (T, 0.0))), ('VeyrWingFoldWalk', ((0, 1.0), (T, 1.0))), ('VeyrBreath', ((0, 0.05), (33, 0.25), (84, 0.08)))):
    kb = key.key_blocks[name]
    for f, v in vals: kb.value = v; kb.keyframe_insert('value', frame=f)
ska.use_fake_user = True
s.frame_set(0)
print('RES', json.dumps({'frames': T, 'yaw_end': psi(T), 'tracks': [t.name for t in ad.nla_tracks]}))
