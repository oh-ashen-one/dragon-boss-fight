"""E3 step: measure Greystone's own clips so build_definition.py can time them to KnightB's gameplay numbers.

For every clip in greystone_common.NATIVE (+ NATIVE_CANDIDATES with --set candidates=true), at 60 Hz, mesh space,
native scale (no 244 cm scale applied here; build_definition applies it):
- length, frame count, rate scale;
- root bone path (translation + yaw) -> rootTravelCm, and whether the clip is in place;
- planted-foot speed: per frame the lower of ball_l/ball_r (within 3 cm of the clip's lowest ball height) moves
  backwards relative to the root at the walking speed; median over planted frames -> footSpeedCmPerSecond;
- blade speed: sword_top bone speed in mesh space; the peak inside the clip -> contactSeconds (attacks only).
Writes native.json. NullRHI commandlet, no renders. Not run yet.
"""
import json
import math
import statistics
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
opts = job['options']
mesh = unreal.load_asset(g.GREYSTONE_MESH)
options = unreal.AnimPoseEvaluationOptions()
options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
options.set_editor_property('optional_skeletal_mesh', mesh)
options.set_editor_property('extract_root_motion', False)
RATE = 60.0
BONES = ('root', 'pelvis', 'ball_l', 'ball_r', 'foot_l', 'foot_r', 'sword_top', 'sword_bottom', 'hand_r')
names = dict(g.NATIVE)
if opts.get('candidates'):
    for key, options_list in g.NATIVE_CANDIDATES.items():
        for i, n in enumerate(options_list):
            names[f'{key}#{i}'] = (n, 'attack' if 'Attack' in key else 'oneshot')


def sample(seq, t):
    p = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, t, options)
    return {b: g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(p, b, unreal.AnimPoseSpaces.WORLD)) for b in BONES}


report, measured = {}, {}
for key, (native, role) in names.items():
    path = g.GS_ANIMS + native
    if native in measured:
        report[key] = dict(measured[native], role=role)
        continue
    seq = unreal.load_asset(path)
    if not isinstance(seq, unreal.AnimSequence):
        report[key] = {'error': 'not an AnimSequence: ' + path}
        continue
    length = seq.get_play_length()
    count = max(2, int(length * RATE) + 1)
    frames = [sample(seq, min(length, i / RATE)) for i in range(count)]
    root = [f['root'][1] for f in frames]
    yaw = [math.degrees(2 * math.atan2(f['root'][0][2], f['root'][0][3])) for f in frames]
    travel = math.dist(root[0][:2], root[-1][:2])
    low = min(min(f['ball_l'][1][2], f['ball_r'][1][2]) for f in frames)
    foot_speeds = []
    for a, b in zip(frames, frames[1:]):
        for ball in ('ball_l', 'ball_r'):
            if b[ball][1][2] - low < 3.0:
                rel_a = g.vsub(a[ball][1], a['root'][1]); rel_b = g.vsub(b[ball][1], b['root'][1])
                foot_speeds.append(math.dist(rel_a[:2], rel_b[:2]) * RATE)
    blade = [math.dist(a['sword_top'][1], b['sword_top'][1]) * RATE for a, b in zip(frames, frames[1:])]
    peak = max(range(len(blade)), key=blade.__getitem__) if blade else 0
    row = {'sequence': path, 'role': role, 'lengthSeconds': length, 'frames': int(unreal.AnimationLibrary.get_num_frames(seq)),
           'rateScale': seq.get_editor_property('rate_scale'), 'rootTravelCm': travel, 'inPlace': travel < 5.0,
           'rootYawChangeDeg': yaw[-1] - yaw[0], 'rootSamples': [list(p) for p in root[::2]], 'rootYawSamples': yaw[::2],
           'rootSampleRate': RATE / 2, 'footSpeedCmPerSecond': statistics.median(foot_speeds) if foot_speeds else 0.0,
           'plantedFrames': len(foot_speeds), 'bladePeakCmPerSecond': blade[peak] if blade else 0.0,
           'contactSeconds': (peak + 0.5) / RATE if blade else -1.0,
           'bladeSpeedCurve': [round(v, 1) for v in blade[::2]]}
    measured[native] = row
    report[key] = row
    unreal.log(f'VEYR_GREYSTONE_NATIVE {key} {native} len={length:.2f} foot={row["footSpeedCmPerSecond"]:.0f} '
               f'contact={row["contactSeconds"]:.2f} travel={travel:.0f}')
(out / 'native.json').write_text(json.dumps(report, indent=1) + '\n')
g.write_result(out, {'success': all('error' not in r for r in report.values()), 'clips': len(report)})
