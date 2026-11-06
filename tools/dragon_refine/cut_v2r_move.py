"""Cut and retime a raw video2rig action in Blender the way the Leshy moves were shipped.

The fitted motion is kept as it is (steps, body lunge, wings, tail); only time is remapped:
a smooth monotone curve (PCHIP through phase knots) speeds the wind-up, keeps the strike
crisp, compresses dead holds and quickens the recovery. Nothing is pinned or blended back
to a stance. An optional additive jaw layer opens the jaw on the wind-up and snaps it shut at
contact (the fit reads the jaw only weakly). Saves an editable .blend holding the raw and cut
actions plus a JSON report.

blender RAW.blend --background --factory-startup --python cut_v2r_move.py -- --spec spec.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

ap = argparse.ArgumentParser()
ap.add_argument('--spec', type=Path, required=True)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
spec = json.loads(a.spec.read_text())
out_blend = Path(spec['output_blend'])
if out_blend.exists():
    raise RuntimeError('Refusing to overwrite ' + str(out_blend))

scene = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)
raw = arm.animation_data.action
src_fps = scene.render.fps / scene.render.fps_base
out_fps = float(spec.get('output_fps', 30))
knots = spec.get('knots')  # [[output_seconds, source_frame], ...], strictly increasing in both


def pchip(xs, ys):
    """Monotone cubic Hermite (Fritsch-Carlson). Returns f(x) and f'(x)."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = max(j for j in range(n - 1) if xs[j] <= x) if x < xs[-1] else n - 2
        t = (x - xs[i]) / h[i]
        h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i]
    return f


if 'rates' in spec:
    # Per-phase playback rates over source frames ([from, to, rate], contiguous), joined by
    # cosine blends so speed never jumps; integrated into output time, then inverted.
    rates, blend = spec['rates'], float(spec.get('blend_frames', 4))

    def rate_at(s):
        for left, right in zip(rates, rates[1:]):
            b = left[1]
            if abs(s - b) < blend / 2:
                u = (s - (b - blend / 2)) / blend
                return left[2] + (right[2] - left[2]) * (0.5 - 0.5 * math.cos(math.pi * u))
        return next((r for f0, f1, r in rates if s < f1), rates[-1][2])
    s0, s1, ds = rates[0][0], rates[-1][1], 0.02
    grid, acc = [(s0, 0.0)], 0.0
    s = s0
    while s < s1 - 1e-9:
        step = min(ds, s1 - s)
        acc += step / (src_fps * rate_at(s + step / 2))
        s += step
        grid.append((s, acc))
    duration = grid[-1][1]

    def remap(t):
        t = min(max(t, 0.0), duration)
        lo, hi = 0, len(grid) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if grid[mid][1] < t:
                lo = mid
            else:
                hi = mid
        (sa, ta), (sb, tb) = grid[lo], grid[hi]
        return sa + (sb - sa) * ((t - ta) / max(tb - ta, 1e-12))
    knots = [[round(next(t for s_, t in grid if s_ >= r[0] - 1e-9), 4), r[0]] for r in rates] + [[round(duration, 4), s1]]
else:
    remap = pchip([k[0] for k in knots], [float(k[1]) for k in knots])
    duration = knots[-1][0]
count = int(round(duration * out_fps)) + 1
src_frames = [remap(i / out_fps) for i in range(count)]


def out_seconds_for(src_frame):
    lo, hi = 0.0, duration
    for _ in range(60):
        mid = (lo + hi) / 2
        if remap(mid) < src_frame:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# 1. Capture the evaluated raw pose at every remapped (fractional) source frame.
bones = [pb.name for pb in arm.pose.bones]
poses = []
for s in src_frames:
    whole = math.floor(s)
    scene.frame_set(whole, subframe=s - whole)
    poses.append({pb.name: (pb.location.copy(), pb.matrix_basis.to_quaternion(), pb.scale.copy()) for pb in arm.pose.bones})

# 2. Additive jaw layer, authored in source frames and mapped to output time.
jaw = spec.get('jaw')
jaw_curve = None
if jaw:
    axis = Vector(jaw['axis_local']).normalized()
    pts = sorted((out_seconds_for(f), math.radians(deg)) for f, deg in jaw['keys_source_frame_deg'])

    def jaw_curve(t):
        if t <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t <= t1:
                u = (t - t0) / max(t1 - t0, 1e-6)
                u = u * u * (3 - 2 * u)
                return v0 + (v1 - v0) * u
        return pts[-1][1]

# 3. Write a fresh action at the output rate.
cut = bpy.data.actions.new(spec['action'])
cut.use_fake_user = True
raw.use_fake_user = True
arm.animation_data.action = cut
if hasattr(arm.animation_data, 'action_slot') and cut.slots:
    arm.animation_data.action_slot = cut.slots[0]
scene.render.fps, scene.render.fps_base = int(out_fps), 1.0
previous = {}
for i, pose in enumerate(poses):
    t = i / out_fps
    for name in bones:
        pb = arm.pose.bones[name]
        loc, q, scl = pose[name]
        q = q.copy()
        if name in previous and previous[name].dot(q) < 0:
            q.negate()
        if jaw_curve and name == jaw['bone']:
            q = q @ Quaternion(axis, jaw_curve(t))
        previous[name] = q
        pb.rotation_mode = 'QUATERNION'
        pb.location, pb.rotation_quaternion, pb.scale = loc, q, scl
        pb.keyframe_insert('location', frame=i, group=name)
        pb.keyframe_insert('rotation_quaternion', frame=i, group=name)
        pb.keyframe_insert('scale', frame=i, group=name)
scene.frame_start, scene.frame_end = 0, count - 1
if hasattr(arm.animation_data, 'action_slot') and cut.slots:
    arm.animation_data.action_slot = cut.slots[0]

# 4. Measure: mouth path and per-frame bone speed on the cut, for the trims and the report.
mouth, steps = [], []
prev_mats = None
for i in range(count):
    scene.frame_set(i)
    mouth.append(list(arm.matrix_world @ arm.pose.bones[spec.get('mouth_bone', 'bone_5')].tail))
    mats = {n: arm.pose.bones[n].matrix.to_quaternion() for n in bones}
    if prev_mats:
        steps.append(max(math.degrees(2 * math.acos(min(1.0, abs(prev_mats[n].dot(mats[n]))))) for n in bones))
    prev_mats = mats
trims = {k: out_seconds_for(v) for k, v in spec.get('trim_source_frames', {}).items()}
report = {
    'source_blend': bpy.data.filepath, 'raw_action': raw.name, 'cut_action': cut.name,
    'source_fps': src_fps, 'output_fps': out_fps, 'output_frames': count, 'duration_s': (count - 1) / out_fps,
    'source_seconds_used': [src_frames[0] / src_fps, src_frames[-1] / src_fps],
    'knots_out_s_src_frame': knots, 'trims_out_s': trims,
    'retime_rate_by_frame': [round((src_frames[min(i + 1, count - 1)] - src_frames[max(i - 1, 0)]) / (2 / out_fps) / src_fps, 3) for i in range(count)],
    'max_bone_step_deg_per_frame': round(max(steps), 3), 'median_bone_step_deg_per_frame': round(sorted(steps)[len(steps) // 2], 3),
    'mouth_path_m': [[round(c, 5) for c in p] for p in mouth],
    'jaw_layer': jaw,
}
out_blend.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out_blend), copy=False)
Path(spec['report']).write_text(json.dumps(report, indent=1))
print('CUT_OK', out_blend, 'duration', report['duration_s'], 'trims', trims)
