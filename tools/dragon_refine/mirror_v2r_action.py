"""Mirror a fitted action left/right in Blender (e.g. a right-foreleg claw into a left-foreleg claw).

Works on deltas from the rest pose in armature space, so it stays correct when the twin bones'
rest orientations are not exact mirror images: for each bone b with mirror twin t,
target(t) = S . (M_b . R_b^-1) . S . R_t, with S the reflection across the creature's sagittal
plane. Twins are paired by mirrored rest-head position. The action's frames and timing are kept;
a new action is written and the scene saved as a new editable .blend, with a JSON report.

blender SOURCE.blend --background --factory-startup --python mirror_v2r_action.py -- \
    --action NEW_ACTION_NAME --output OUT.blend --report OUT.json [--axis y]
"""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ap = argparse.ArgumentParser()
ap.add_argument('--action', required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--report', type=Path, required=True)
ap.add_argument('--axis', choices=('auto', 'x', 'y', 'z'), default='auto', help='Armature axis across which the creature is mirrored')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
if a.output.exists():
    raise RuntimeError('Refusing to overwrite ' + str(a.output))

scene = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action)
source = arm.animation_data.action
start, end = (int(round(x)) for x in source.frame_range)
bones = arm.data.bones
rest = {b.name: b.matrix_local.copy() for b in bones}
height = max(b.head_local.length for b in bones) or 1.0


def axis_cost(axis):
    total = 0.0
    for b in bones:
        t = b.head_local.copy()
        t[axis] = -t[axis]
        total += min((c.head_local - t).length for c in bones)
    return total


# The armature's own axes may be rotated relative to the world: pick the reflection that pairs best.
k = 'xyz'.index(a.axis) if a.axis != 'auto' else min(range(3), key=axis_cost)
a.axis = 'xyz'[k]
S = Matrix.Identity(4)
S[k][k] = -1.0


def mirrored(v):
    v = v.copy()
    v[k] = -v[k]
    return v


# Explicit pairs from the rig's limb chains (the Tripo rest pose is not symmetric enough to pair by
# position). Front chains differ by one segment; links are matched in order. Unlisted bones are midline.
PAIRS = [('bone_6', 'bone_11'), ('bone_7', 'tripo::0_Left_Limb_0'), ('tripo::1_Left_Limb_0', 'tripo::0_Left_Limb_1'),
         ('bone_9', 'bone_14'), ('tripo::1_Left_Limb_1', 'tripo::0_Left_Limb_2')]
PAIRS += [(f'tripo::1_Right_Limb_{i}', f'tripo::0_Right_Limb_{i}') for i in range(5)]
PAIRS += [(f'VeyrWingPosZ{p}', f'VeyrWingNegZ{p}') for p in ('Root', 'Elbow', 'Membrane', 'Wrist', 'Tip')]
twin = {b.name: b.name for b in bones}
for l, r in PAIRS:
    if l in twin and r in twin:
        twin[l], twin[r] = r, l
pairs_broken = []
residual = {b.name: (mirrored(b.head_local) - bones[twin[b.name]].head_local).length / height for b in bones}
asym = sorted(((v, n) for n, v in residual.items()), reverse=True)[:5]
# A bone with no twin is only a midline bone when its rest head lies on the mirror plane. The FR toe
# (tripo::0_Left_Limb_3, the front chains differ by one segment) is not: mirroring it as a midline
# bone reflected its own source motion onto the other side and tore it up to 0.72 rig heights away
# from its foot in every mirrored clip (owner-seen foot pinch, 2026-11-18). Unpaired side bones now
# keep their rest pose relative to their (mirrored) parent, and the output is gated on bone stretch.
SIDE_LIMIT = 0.02
unpaired_side = sorted(n for n, v in residual.items() if twin[n] == n and v > SIDE_LIMIT)
pairs_broken = list(unpaired_side)
# Midline/root bones may carry translation (body offset, flight root). Every other link is rigid.
TRANSLATING = {'VeyrRoot', 'tripo::Root', 'tripo::Spine_0'}

# 1. Target armature-space matrices for every frame.
targets = []
for f in range(start, end + 1):
    scene.frame_set(f)
    pose = {pb.name: pb.matrix.copy() for pb in arm.pose.bones}
    frame = {}
    for b in bones:
        src = b.name
        dst = twin[src]
        delta = pose[src] @ rest[src].inverted()
        frame[dst] = S @ delta @ S @ rest[dst]
    targets.append(frame)

# 2. Basis per bone from its parent's target: M_c = M_p . (R_p^-1 R_c) . B.
mirror = bpy.data.actions.new(a.action)
mirror.use_fake_user = True
source.use_fake_user = True
arm.animation_data.action = mirror
if hasattr(arm.animation_data, 'action_slot') and mirror.slots:
    arm.animation_data.action_slot = mirror.slots[0]
previous = {}
for i, frame in enumerate(targets):
    f = start + i
    for pb in arm.pose.bones:
        b = pb.bone
        M = frame[b.name]
        if b.parent:
            offset = rest[b.parent.name].inverted() @ rest[b.name]
            basis = offset.inverted() @ frame[b.parent.name].inverted() @ M
        else:
            basis = rest[b.name].inverted() @ M
        loc, rot, scl = basis.decompose()
        if b.name in unpaired_side:
            loc, rot, scl = Matrix.Identity(4).decompose()
        elif b.name not in TRANSLATING:
            # Rest asymmetry turns the mirrored target into small link translations (up to 0.016 rig
            # heights measured). The source rig is rotation-only on these links: keep them rigid.
            loc = loc * 0.0
        if b.name in previous and previous[b.name].dot(rot) < 0:
            rot.negate()
        previous[b.name] = rot
        pb.rotation_mode = 'QUATERNION'
        pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
        for path in ('location', 'rotation_quaternion', 'scale'):
            pb.keyframe_insert(path, frame=f, group=b.name)
if hasattr(arm.animation_data, 'action_slot') and mirror.slots:
    arm.animation_data.action_slot = mirror.slots[0]

# 3. Verify the evaluated pose reproduces the targets (rotation part; link translations are pinned
# above), and refuse any output where a rigid link stretches away from its parent.
worst = 0.0
stretch = 0.0
stretch_bone = ''
for i, frame in enumerate(targets):
    scene.frame_set(start + i)
    for pb in arm.pose.bones:
        if pb.name not in unpaired_side:
            d = pb.matrix.to_3x3() - frame[pb.name].to_3x3()
            worst = max(worst, max(abs(d[r][c]) for r in range(3) for c in range(3)))
        if pb.parent and pb.name not in TRANSLATING:
            rest_gap = (pb.bone.head_local - pb.parent.bone.head_local).length
            gap = abs((pb.head - pb.parent.head).length - rest_gap) / height
            if gap > stretch:
                stretch, stretch_bone = gap, pb.name
if stretch > 0.01:
    raise RuntimeError(f'Mirrored action stretches {stretch_bone} by {stretch:.4f} rig heights; refusing to save')
a.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.output), copy=False)
report = {'source_blend': bpy.data.filepath, 'source_action': source.name, 'mirror_action': mirror.name,
          'axis': a.axis, 'frames': [start, end], 'twins': twin, 'unpaired_or_one_way': pairs_broken,
          'largest_rest_asymmetry_share_of_height': [[round(v, 4), n] for v, n in asym],
          'evaluated_vs_target_max_error': worst, 'max_link_stretch_share_of_height': stretch,
          'max_link_stretch_bone': stretch_bone, 'unpaired_side_bones_kept_at_rest': unpaired_side}
a.report.write_text(json.dumps(report, indent=1))
print('MIRROR_OK', a.output, 'max rotation error', worst, 'max link stretch', stretch, 'unpaired side bones at rest', unpaired_side)
