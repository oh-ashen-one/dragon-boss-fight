"""Shared layered-NLA keyframe helpers for DRAGON_CTRL (Blender 5.2). exec() into a namespace.
Axes: dragon faces +X, left = +Y, up = +Z. Angles deg, distances rig units (1 u = 2155.818 cm)."""
import bpy, math, json
from mathutils import Quaternion, Vector, Matrix
from pathlib import Path
W = Path("/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021")  # READ-ONLY inputs; outputs go to OUT
OUT = W / "flight_r2"
CM = 2155.818
s = bpy.context.scene
C = bpy.data.objects['DRAGON_CTRL']; P = C.pose.bones; B = C.data.bones
for n in ('C_bone_2','C_tripo::Spine_1','C_bone_3','C_bone_6','C_bone_11','C_VeyrWingPosZRoot','C_VeyrWingNegZRoot'):
    B[n].inherit_scale = 'NONE'
X, Y, Z = Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))
def R(axis, deg): return Quaternion(axis, math.radians(deg))
def YAW(d): return R(Z, d)
def PITCH_UP(d): return R(Y, -d)
def ROLL(d): return R(X, d)
def local_q(bone, qw):
    m = B[bone].matrix_local.to_3x3().to_quaternion(); return m.inverted() @ qw @ m
def local_v(bone, vw): return B[bone].matrix_local.to_3x3().inverted() @ vw
WING = {'R': ('PosZ', -1), 'L': ('NegZ', 1)}
def wing_q(side, sweep_back=0., lower=0.):
    sg = WING[side][1]; return R(Z, sg*sweep_back) @ R(X, -sg*lower)
ad = C.animation_data or C.animation_data_create()
def reset_ctrl(prefix):
    ad.action = None
    for t in list(ad.nla_tracks): ad.nla_tracks.remove(t)
    for a in list(bpy.data.actions):
        if a.name.startswith(prefix): bpy.data.actions.remove(a)
    for pb in P: pb.rotation_mode='QUATERNION'; pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)
def fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags: yield from cb.fcurves
def make_layer(prefix, name, period, channels, blend='COMBINE', length=None, cyclic=True):
    """channels: {bone: [(frame, dict(q=, loc=, sc=, interp='BEZIER'|'LINEAR')), ...]} one period.
    cyclic=False: keys used as given (no wrap/duplicate, no Cycles modifier)."""
    length = length or period
    act = bpy.data.actions.new(prefix+name); ad.action = act
    interp_map = {}
    for bone, keys in channels.items():
        pb = P[bone]
        if cyclic:
            ks = sorted(((f % period, k) for f, k in keys), key=lambda x: x[0]); ks = ks + [(ks[0][0] + period, ks[0][1])]
        else: ks = sorted(keys, key=lambda x: x[0])
        prev = None
        for f, k in ks:
            interp_map[(bone, round(f, 3))] = k.get('interp', 'BEZIER')
            if 'q' in k or 'ql' in k:
                q = Quaternion(k['ql']) if 'ql' in k else local_q(bone, k['q'])
                if prev is not None and prev.dot(q) < 0: q.negate()
                prev = q.copy(); pb.rotation_quaternion = q; pb.keyframe_insert('rotation_quaternion', frame=f, group=bone)
            if 'loc' in k or 'locl' in k:
                pb.location = Vector(k['locl']) if 'locl' in k else local_v(bone, k['loc']); pb.keyframe_insert('location', frame=f, group=bone)
            if 'sc' in k or 'scl' in k:
                pb.scale = Vector(k['scl']) if 'scl' in k else (k['sc'],)*3; pb.keyframe_insert('scale', frame=f, group=bone)
        pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)
    for fc in fcurves(act):
        bone = fc.data_path.split('"')[1]
        for kp in fc.keyframe_points:
            kp.interpolation = interp_map.get((bone, round(kp.co.x, 3)), 'BEZIER')
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        if cyclic and not any(m.type=='CYCLES' for m in fc.modifiers): fc.modifiers.new('CYCLES')
        fc.update()
    act.use_frame_range = True; act.frame_start = 0; act.frame_end = length; act.use_cyclic = cyclic
    ad.action = None
    tr = ad.nla_tracks.new(); tr.name = name
    st = tr.strips.new(name, 0, act); st.action_frame_start, st.action_frame_end = 0, length
    st.blend_type = blend; st.extrapolation = 'HOLD' if blend=='REPLACE' else 'NOTHING'
    try:
        if st.action_slot is None and act.slots: st.action_slot = act.slots[0]
    except AttributeError: pass
    return act
def sine_keys(period, peak_frame, amp, fn, n=4):
    """n evenly spaced keys of a sinusoid with peak at peak_frame (values amp*cos)."""
    return [((peak_frame + i*period/n) % period, fn(amp*math.cos(2*math.pi*i/n))) for i in range(n)]
GROUND = {'IK_FR': -0.00244, 'IK_HL': -0.008794, 'IK_HR': -0.011235, 'IK_FL': 0.0}
WING_FOLD = {'L': (33, -3), 'R': (35, 2)}   # v1 (half-spread mantle) - superseded by FOLD_V2
# v2 flank fold (r2): arm swept back and tilted down, finger chain collapsed onto the trailing chain.
# Right-wing world axes at rest; left wing mirrored (pseudo-vector mirror across XZ).
FOLD_V2 = {'Root': [((0,0,1), -72), ((0,1,0), -40), ((1,0,0), 0)], 'Wrist': [((1,0,0), 145)], 'Elbow': [((1,0,0), -25)], 'Membrane': [((1,0,0), -15)]}
def mirror_axis(ax): return Vector((-ax[0], ax[1], -ax[2]))
# walk: trailing chain lifted clear of the swinging thighs (bottom edge ~0.083 u instead of ~0.03)
FOLD_WALK = {'Root': [((0,0,1), -72), ((0,1,0), -30), ((1,0,0), 0)], 'Wrist': [((1,0,0), 145)], 'Elbow': [((1,0,0), -40)], 'Membrane': [((1,0,0), -15)]}
def fold_q(part, side, scale=1.0, extra=(), fold=None):
    """world-at-rest quaternion for wing part (Root/Wrist/Elbow/Membrane/Tip) on side 'R'/'L'."""
    q = Quaternion()
    for ax, d in list((fold or FOLD_V2).get(part, [])) + list(extra):
        a = Vector(ax); a = mirror_axis(a) if side == 'L' else a
        q = Quaternion(a, math.radians(d*scale)) @ q
    return q
def wing_side_axis(ax, side):
    a = Vector(ax); return mirror_axis(a) if side == 'L' else a
