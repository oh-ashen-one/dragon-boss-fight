"""E3/E4 check: every retargeted Greystone clip against its KnightB source, in actor space (each definition's
mesh-relative transform applied, so 244 cm scale and floor offset are both included). NullRHI commandlet, no renders.

Per clip, over the trimmed range StartSeconds..EndSeconds at 30 Hz:
- length and frame-count match (a resampled clip shifts every authored time);
- toe heights (KnightB LeftToeBase/RightToeBase vs Greystone ball_l/ball_r) and pelvis height (Hips vs pelvis):
  mean and max absolute difference;
- lag: the frame shift (-6..6 at 30 Hz) that best aligns the toe-height curves (0 = in time);
- grounded mismatch: share of frames where one rig has a toe within 5 cm of its clip's lowest toe height and the other
  has it more than 20 cm up (feet planted on one rig and in the air on the other).
Writes compare.json. Options: keys=[...] (default: every clip whose sequence is under our Anims folder).
"""
import json
import math
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
opts = job['options']
knight = unreal.load_asset(g.KNIGHT_DEFINITION)
grey = unreal.load_asset(g.DEFINITION)
k_rel = g.from_unreal(knight.get_editor_property('mesh_relative_transform'))
g_rel = g.from_unreal(grey.get_editor_property('mesh_relative_transform'))
k_mesh, g_mesh = knight.get_editor_property('skeletal_mesh'), grey.get_editor_property('skeletal_mesh')
k_clips = {str(k): v for k, v in knight.get_editor_property('clips').items()}
g_clips = {str(k): v for k, v in grey.get_editor_property('clips').items()}
RATE = 30.0
K_BONES = {'toeL': 'LeftToeBase', 'toeR': 'RightToeBase', 'pelvis': 'Hips'}
G_BONES = {'toeL': 'ball_l', 'toeR': 'ball_r', 'pelvis': 'pelvis'}


def options_for(mesh):
    o = unreal.AnimPoseEvaluationOptions()
    o.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
    o.set_editor_property('optional_skeletal_mesh', mesh)
    o.set_editor_property('extract_root_motion', False)
    return o


K_OPT, G_OPT = options_for(k_mesh), options_for(g_mesh)


def heights(clip, opt, bones, rel):
    seq = clip.get_editor_property('sequence')
    start = clip.get_editor_property('start_seconds')
    end = clip.get_editor_property('end_seconds')
    end = seq.get_play_length() if end is None or end < 0 else end
    rows = []
    for i in range(int((end - start) * RATE) + 1):
        t = min(end, start + i / RATE)
        p = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, t, opt)
        row = {}
        for key, bone in bones.items():
            local = g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(p, bone, unreal.AnimPoseSpaces.WORLD))
            row[key] = g.compose(local, rel)[1][2]
        rows.append(row)
    return seq, rows


report = {}
wanted = opts.get('keys') or [k for k, c in g_clips.items()
                              if c.get_editor_property('sequence') and c.get_editor_property('sequence').get_path_name().startswith(g.ANIMS)]
for key in wanted:
    if key not in k_clips or key not in g_clips:
        report[key] = {'error': 'missing in one definition'}
        continue
    k_seq, k_rows = heights(k_clips[key], K_OPT, K_BONES, k_rel)
    g_seq, g_rows = heights(g_clips[key], G_OPT, G_BONES, g_rel)
    n = min(len(k_rows), len(g_rows))
    row = {'knightSeconds': k_seq.get_play_length(), 'greystoneSeconds': g_seq.get_play_length(),
           'knightFrames': int(unreal.AnimationLibrary.get_num_frames(k_seq)),
           'greystoneFrames': int(unreal.AnimationLibrary.get_num_frames(g_seq)), 'samples': n}
    for part in ('toeL', 'toeR', 'pelvis'):
        d = [abs(k_rows[i][part] - g_rows[i][part]) for i in range(n)]
        row[part + 'MeanDiffCm'] = round(sum(d) / max(1, n), 2)
        row[part + 'MaxDiffCm'] = round(max(d) if d else 0.0, 2)

    def err(shift):
        s, c = 0.0, 0
        for i in range(n):
            j = i + shift
            if 0 <= j < n:
                s += abs(k_rows[i]['toeL'] - g_rows[j]['toeL']) + abs(k_rows[i]['toeR'] - g_rows[j]['toeR']); c += 1
        return s / max(1, c)

    row['lagFrames30Hz'] = min(range(-6, 7), key=err)
    k_low = min(min(r['toeL'], r['toeR']) for r in k_rows[:n]) if n else 0.0
    g_low = min(min(r['toeL'], r['toeR']) for r in g_rows[:n]) if n else 0.0
    mismatch = 0
    for i in range(n):
        for side in ('toeL', 'toeR'):
            kd, gd = k_rows[i][side] - k_low < 5.0, g_rows[i][side] - g_low < 5.0
            ku, gu = k_rows[i][side] - k_low > 20.0, g_rows[i][side] - g_low > 20.0
            if (kd and gu) or (gd and ku):
                mismatch += 1
                break
    row['groundedMismatchShare'] = round(mismatch / max(1, n), 3)
    report[key] = row
    unreal.log(f'VEYR_GREYSTONE_COMPARE {key} lag={row["lagFrames30Hz"]} toeMean={row["toeLMeanDiffCm"]}/{row["toeRMeanDiffCm"]} '
               f'pelvisMean={row["pelvisMeanDiffCm"]} mismatch={row["groundedMismatchShare"]}')
(out / 'compare.json').write_text(json.dumps(report, indent=1) + '\n')
g.write_result(out, {'success': all('error' not in r for r in report.values()), 'clips': len(report)})
