"""Step E5b: the fallback motion table FVeyrMotionFeatureTable::LoadJson reads (schema veyr-motion-features-v1).

One row every 1/30 s of every clip in our PSD_GS_* databases (or, with --set source=definition, of DA_Greystone's
locomotion keys), 33 floats in the capsule frame (x forward, y right, z up; world cm at Greystone's definition scale):
  0-5   left/right foot (foot_l/foot_r) position       6-11  left/right hand position
  12-17 left/right foot velocity                       18-20 pelvis velocity
  21-26 root XY position at +1/3, +2/3, +1 s           27-32 root facing XY at the same times
Future samples clamp at the clip end for non-looping clips and wrap for looping ones. Gate tags come from the database
name (PSD_GS_<Gate>_...). Weights default to the reference hero's spread (trajectory 1.0, feet 0.75, hands 0.25,
velocities 0.5). Mean/std are over all rows. Output: Content/Characters/Greystone/MotionMatching/veyr_motion_features.json
(local-only like the rest of that folder; packaging needs it staged as a non-UFS file - see the design doc).
"""
import json
import math
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
library = unreal.EditorAssetLibrary
definition = unreal.load_asset(g.DEFINITION)
assert definition, 'build the definition first'
rel = g.from_unreal(definition.get_editor_property('mesh_relative_transform'))
mesh = definition.get_editor_property('skeletal_mesh')
options = unreal.AnimPoseEvaluationOptions()
options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
options.set_editor_property('optional_skeletal_mesh', mesh)
options.set_editor_property('extract_root_motion', True)
registry = unreal.AssetRegistryHelpers.get_asset_registry()
clips = {}
for data in registry.get_assets_by_path(g.MOTION, recursive=False):
    name = str(data.asset_name)
    if not name.startswith('PSD_GS_'):
        continue
    gate = name.split('_')[2]
    db = unreal.load_asset(str(data.package_name))
    for path in unreal.VeyrGreystoneEditorLibrary.list_pose_search_database_assets(db):
        clips.setdefault(path.split('.')[0], set()).add(gate)


def pose(seq, t):
    p = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, t, options)
    return {n: g.compose(g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(p, n, unreal.AnimPoseSpaces.WORLD)), rel)
            for n in ('root', 'pelvis', 'foot_l', 'foot_r', 'hand_l', 'hand_r')}


# The root bone's own axes are not the character's: forward is actor +X at the reference pose, so every frame is
# measured as the root's rotation relative to its reference-pose rotation (in actor space).
ref_root_q = g.compose(g.from_unreal(g.reference_world(mesh)['root']), rel)[0]


def facing(root):
    return g.qnorm(g.qmul(root[0], g.qinv(ref_root_q)))


rows = []
STEP = 1.0 / 30.0
for path, gates in sorted(clips.items()):
    seq = unreal.load_asset(path)
    if not isinstance(seq, unreal.AnimSequence):
        continue
    length = seq.get_play_length()
    loop = 'Loop' in gates or 'Idle' in gates
    times = [i * STEP for i in range(int(length / STEP) + 1)]
    cache = {}

    def at(t):
        t = (t % length) if loop else min(max(t, 0.0), length)
        key = round(t, 4)
        if key not in cache:
            cache[key] = pose(seq, t)
        return cache[key]

    for t in times:
        now, before = at(t), at(t - STEP)
        frame = (facing(now['root']), now['root'][1], 1.0)
        inv = g.tinv(frame)

        def local(p):
            return g.compose(((0, 0, 0, 1), p, 1.0), inv)[1]
        f = []
        for b in ('foot_l', 'foot_r', 'hand_l', 'hand_r'):
            f += list(local(now[b][1]))
        for b in ('foot_l', 'foot_r', 'pelvis'):
            f += list(g.vscale(g.vsub(local(now[b][1]), local(before[b][1])), 1.0 / STEP))
        future = [at(t + d) for d in (1 / 3, 2 / 3, 1.0)]
        for fu in future:
            p = local(fu['root'][1]); f += [p[0], p[1]]
        for fu in future:
            v = g.qrot(g.qinv(frame[0]), g.qrot(facing(fu['root']), (1.0, 0.0, 0.0))); f += [v[0], v[1]]
        rows.append({'clip': path, 'time': t, 'gates': sorted(gates), 'f': f})
assert rows, 'no clips found under ' + g.MOTION
mean = [sum(r['f'][i] for r in rows) / len(rows) for i in range(33)]
std = [math.sqrt(sum((r['f'][i] - mean[i]) ** 2 for r in rows) / len(rows)) for i in range(33)]
weights = [.75] * 6 + [.25] * 6 + [.5] * 9 + [1.0] * 12
table = {'schema': 'veyr-motion-features-v1', 'mean': mean, 'std': std, 'weights': weights, 'rows': rows,
         'frame': 'capsule: x forward, y right, z up; world cm', 'step': STEP}
target = g.PROJECT / 'Content/Characters/Greystone/MotionMatching/veyr_motion_features.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(table) + '\n')
g.write_result(out, {'success': True, 'rows': len(rows), 'clips': len(clips), 'file': str(target)})
