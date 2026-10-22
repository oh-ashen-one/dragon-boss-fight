"""Set the r3 fold pose (both wings, right params mirrored to the left) in the idle crouch with NLA muted. Defines FOLD3."""
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_flight_r2/dcommon.py').read())
FOLD3 = globals().get('FOLD3', [-87.1, -68.4, -8.4, 60.1, -40.0, -10.1, 3.7, 20.0])
def oop_axis_side(part, side):
    b = B[f'C_VeyrWingPosZ{part}']; d = (b.tail_local - b.head_local).normalized(); a = d.cross(Vector((1, 0, 0))).normalized()
    return mirror_axis(a) if side == 'L' else a
def fold3_q(part, side, p=None, scale=1.0):
    p = p or FOLD3
    def q(ax, d): return Quaternion(wing_side_axis(ax, side), math.radians(d*scale))
    if part == 'Root': return q((1,0,0), p[2]) @ q((0,1,0), p[1]) @ q((0,0,1), p[0])
    if part == 'Wrist': return q((1,0,0), p[3]) @ Quaternion(oop_axis_side('Wrist', side), math.radians(p[4]*scale))
    if part == 'Elbow': return q((1,0,0), p[5]) @ Quaternion(oop_axis_side('Elbow', side), math.radians(p[6]*scale))
    if part == 'Membrane': return q((1,0,0), p[7])
    return Quaternion()
if globals().get('SET_POSE', True):
    for t in ad.nla_tracks: t.mute = True
    key = bpy.data.objects['DRAGON_MESH'].data.shape_keys
    if key.animation_data: key.animation_data.action = None
    for kb in key.key_blocks[1:]: kb.value = 0.0
    for pb in P: pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)
    P['C_tripo::Spine_0'].location = local_v('C_tripo::Spine_0', Vector((0,0,-0.0105)))
    P['C_tripo::Spine_0'].rotation_quaternion = local_q('C_tripo::Spine_0', PITCH_UP(-0.7))
    for k_, z in GROUND.items(): P[k_].location = local_v(k_, Vector((0,0,z)))
    for side, tag in (('R','PosZ'), ('L','NegZ')):
        for part in ('Root','Wrist','Elbow','Membrane'): P[f'C_VeyrWing{tag}{part}'].rotation_quaternion = local_q(f'C_VeyrWing{tag}{part}', fold3_q(part, side))
    bpy.context.view_layer.update()
