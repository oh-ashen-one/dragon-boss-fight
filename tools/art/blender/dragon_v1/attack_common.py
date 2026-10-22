"""Shared one-shot attack authoring on DRAGON_CTRL (idle r3 stance, r3 fold). Keys use world-at-rest rotations ('q')
except the boundary frames 0 and T, which take the sampled idle r3 frame-0 local channels ('ql') for a seamless return."""
SET_POSE = False
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/fold_pose_v3.py').read())
SPREAD = 90.0
def wq(side, axis, deg): return Quaternion(wing_side_axis(axis, side), math.radians(deg))
def wing_open(side, flap, twist): return wq(side, (1,0,0), -flap) @ wq(side, (0,1,0), SPREAD + twist)
def flare(part, side, u, flap=18.0, twist=0.0):
    """blend from the r3 fold (u=0) toward an open, slightly raised wing (u=1)."""
    tgt = wing_open(side, flap, twist) if part == 'Root' else Quaternion()
    return fold3_q(part, side).slerp(tgt, u)
WD = '/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/reports/'
POSE_IDLE = json.load(open(WD + 'pose_idle_r3_f0.json'))
def build(prefix, T, ch, sk, feet=None):
    s.render.fps = 30; s.frame_start = 0; s.frame_end = T
    reset_ctrl(prefix)
    for a in bpy.data.actions:
        if not a.name.startswith(prefix): a.use_fake_user = True
    for bname, src in POSE_IDLE.items():
        if bname.startswith('C_tripo::Root'): continue
        keys = [k for k in ch.get(bname, []) if 0 < k[0] < T]
        for f in (0, T): keys.append((f, dict(ql=src['q'], locl=src['loc'], scl=src['sc'])))
        ch[bname] = sorted(keys, key=lambda x: x[0])
    for ik, z in GROUND.items():   # feet: ground offset plus any authored lift (IK controls are children of the static root)
        ks = (feet or {}).get(ik, [])
        ch[ik] = [(0, dict(loc=Vector((0, 0, z))))] + [(f, dict(loc=Vector((0, 0, z)) + v)) for f, v in ks] + [(T, dict(loc=Vector((0, 0, z))))]
        ch[ik].sort(key=lambda x: x[0])
    make_layer(prefix, '0_Attack', T, ch, blend='REPLACE', length=T, cyclic=False)
    M = bpy.data.objects['DRAGON_MESH']; key = M.data.shape_keys
    kad = key.animation_data or key.animation_data_create()
    old = bpy.data.actions.get(prefix+'ShapeKeys')
    if old: bpy.data.actions.remove(old)
    ska = bpy.data.actions.new(prefix+'ShapeKeys'); kad.action = ska
    for name in [k.name for k in key.key_blocks[1:]]:
        kb = key.key_blocks[name]; kb.slider_max = 2.0
        for f, v in sk.get(name, [(0, 0.0), (T, 0.0)]): kb.value = v; kb.keyframe_insert('value', frame=f)
    for fc in fcurves(ska):
        for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
    ska.use_fake_user = True
    s.frame_set(0)
def neckq(pitch, yaw=0.0): return YAW(yaw) @ PITCH_UP(pitch)
