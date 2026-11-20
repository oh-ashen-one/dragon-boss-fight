"""E4 pass 3 (blind critic E3): give Greystone a sourced roll instead of the old knight's retargeted somersault.

Candidates on this machine (all free Epic content already installed; nothing downloaded):
  - GASP UEFN mannequin M_Neutral_Jump_F_Land_Roll_Rfoot / _Lfoot (copied into this project with the GASP set): a
    landing into a low forward shoulder roll that comes up on the feet.
  - Paragon Greystone, Kwang, Gideon, Crunch, Terra, Rampage: no roll, dodge or evade clip (Crunch's dash is a charge).
  - GASP M_ragdoll_getup_roll_L/R: a get-up from lying down, not a dodge.
This step retargets the two land rolls with RTG_UEFN_to_Greystone (GASP's TwinBlast retargeter, chains renamed),
holds the root bone still (gameplay moves the actor along the knight's path), measures every frame and, with
--set apply=<R|L>, makes the chosen one DA_Greystone's Roll, timed exactly like build_definition's native clips:
start S at the landing contact, rate r = (end - S) / knight game seconds (0.75..1.35), knight root path warped into
the new source time, so roll distance, duration and invulnerability (game time) stay the knight's. The previous Roll
clip is kept under RollKnightRetarget (AVeyrKnight -VeyrGreystoneKnightRoll plays it).

usage (through run_greystone.py): source-roll [--set apply=R] [--set start=<seconds>] [--set end=<seconds>]
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
library = unreal.EditorAssetLibrary
SOURCES = {'R': g.GASP_MANNEQUIN + '/Animations/Jump/M_Neutral_Jump_F_Land_Roll_Rfoot',
           'L': g.GASP_MANNEQUIN + '/Animations/Jump/M_Neutral_Jump_F_Land_Roll_Lfoot'}
SOURCE_MESH = g.GASP_MANNEQUIN + '/Meshes/SKM_UEFN_Mannequin'
DEST = g.ANIMS + '/Sourced'
rtg = unreal.load_asset(g.RIGS + '/RTG_UEFN_to_Greystone')
grey_mesh = unreal.load_asset(g.GREYSTONE_MESH)
source_mesh = unreal.load_asset(SOURCE_MESH)
assert rtg and grey_mesh and source_mesh, 'retargeter or meshes missing'
scale_doc = json.loads(Path(opts.get('scaleFile') or (g.ROOT / 'Local/greystone/retarget-20261119T095437Z/anims.json')).read_text())
scale_doc = scale_doc.get('scale', scale_doc)
g_rel = (tuple(scale_doc['rotation_xyzw']), tuple(scale_doc['translation_cm']), float(scale_doc['scale']))
options = unreal.AnimPoseEvaluationOptions()
options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)
options.set_editor_property('optional_skeletal_mesh', grey_mesh)
g_world = g.reference_world(grey_mesh)
g_parents = g.bone_parents(grey_mesh)
receipt = {'sources': SOURCES, 'retargeter': g.RIGS + '/RTG_UEFN_to_Greystone', 'swordParent': g_parents.get('sword_bottom'),
           'scale': g_rel[2], 'clips': {}}


def world(pose, name):
    """Bone in actor space, cm (mesh component space through Greystone's mesh-relative transform)."""
    return g.compose(g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD)), g_rel)


made_clips = {}
for side, source_path in SOURCES.items():
    source = unreal.load_asset(source_path)
    assert source, source_path
    name = 'A_GS_LandRoll_' + side
    target_path = DEST + '/' + name
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property('assets_to_retarget', [library.find_asset_data(source_path)])
    inputs.set_editor_property('source_mesh', source_mesh)
    inputs.set_editor_property('target_mesh', grey_mesh)
    inputs.set_editor_property('ik_retarget_asset', rtg)
    inputs.set_editor_property('search', source.get_name())
    inputs.set_editor_property('replace', name)
    inputs.set_editor_property('target_path', DEST)
    inputs.set_editor_property('include_referenced_assets', False)
    inputs.set_editor_property('overwrite_existing_files', True)
    made = [str(a.package_name) for a in unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)]
    if target_path not in made:
        raise RuntimeError(f'{source_path}: retarget produced {made}, expected {target_path}')
    seq = unreal.load_asset(target_path)
    frames = unreal.AnimationLibrary.get_num_frames(seq)
    length = seq.get_play_length()
    # Hold the root bone at its reference: the game moves the actor (the knight's path), so the clip must not travel.
    rows, root_moves = [], 0.0
    first_root = None
    for f in range(frames):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_frame(seq, f, options)
        r = g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(pose, 'root', unreal.AnimPoseSpaces.LOCAL))
        first_root = first_root or r
        root_moves = max(root_moves, math.dist(r[1], first_root[1]))
        rows.append(r)
    controller = seq.get_editor_property('controller')
    controller.open_bracket(unreal.Text('Greystone roll root hold'), False)
    controller.add_bone_curve('root', False)
    ref_root = g.from_unreal(g_world['root'])  # root has no parent: its reference world transform is its local one
    controller.set_bone_track_keys('root', [unreal.Vector(*ref_root[1])] * frames, [unreal.Quat(*ref_root[0])] * frames,
                                   [unreal.Vector(1.0, 1.0, 1.0)] * frames, False)
    controller.close_bracket(False)
    # If the retargeter put the travel on the pelvis instead, take the pelvis's horizontal drift out too (its height and
    # the rotations stay the roll's): the clip plays in place, the actor carries the distance.
    pelvis_rows, drift = [], []
    for f in range(frames):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_frame(seq, f, options)
        pelvis_rows.append(g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(pose, 'pelvis', unreal.AnimPoseSpaces.LOCAL)))
        drift.append(g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(pose, 'pelvis', unreal.AnimPoseSpaces.WORLD))[1])
    up_axis = max(range(3), key=lambda i: abs(g.from_unreal(g_world['head'])[1][i] - g.from_unreal(g_world['pelvis'])[1][i]))
    travel = max(math.dist([d[i] for i in range(3) if i != up_axis], [drift[0][i] for i in range(3) if i != up_axis]) for d in drift)
    pelvis_parent_is_root = g_parents.get('pelvis') == 'root'
    if opts.get('holdPelvis', True) and travel > 15.0 and pelvis_parent_is_root:
        fixed = []
        for (q, t, sc), d in zip(pelvis_rows, drift):
            off = [d[i] - drift[0][i] if i != up_axis else 0.0 for i in range(3)]
            fixed.append((q, tuple(t[i] - off[i] for i in range(3)), sc))  # root holds identity-like: component offset = local
        controller.open_bracket(unreal.Text('Greystone roll pelvis in place'), False)
        controller.add_bone_curve('pelvis', False)
        controller.set_bone_track_keys('pelvis', [unreal.Vector(*r[1]) for r in fixed], [unreal.Quat(*r[0]) for r in fixed],
                                       [unreal.Vector(r[2], r[2], r[2]) for r in fixed], False)
        controller.close_bracket(False)
    pelvis_travel_removed = travel if (opts.get('holdPelvis', True) and travel > 15.0 and pelvis_parent_is_root) else 0.0
    seq.set_editor_property('enable_root_motion', False)
    library.save_asset(target_path, only_if_is_dirty=False)
    # Measure (actor space, cm; actor origin is the capsule centre, the floor sits at translation_cm.z).
    floor = g_rel[1][2]
    rows = []
    for f in range(frames):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_frame(seq, f, options)
        b = {n: world(pose, n)[1] for n in ('pelvis', 'head', 'ball_l', 'ball_r', 'foot_l', 'foot_r', 'hand_r', 'sword_bottom', 'sword_top', 'spine_03')}
        rows.append({'frame': f, 'seconds': f * length / max(1, frames - 1),
                     'pelvisZ': b['pelvis'][2] - floor, 'headZ': b['head'][2] - floor,
                     'footZ': min(b['ball_l'][2], b['ball_r'][2], b['foot_l'][2], b['foot_r'][2]) - floor,
                     'headAbovePelvis': b['head'][2] - b['pelvis'][2], 'pelvisX': b['pelvis'][0], 'pelvisY': b['pelvis'][1],
                     'swordTipZ': b['sword_top'][2] - floor, 'handToSwordCm': math.dist(b['hand_r'], b['sword_bottom'])})
    # The clip is fall -> landing -> shoulder roll -> stand. Roll window: from the last grounded, still-upright frame
    # before the most inverted frame (the landing crouch he dives from) to the first grounded upright frame after it.
    stand = max(r['headAbovePelvis'] for r in rows)
    ground = min(r['footZ'] for r in rows) + 12.0
    low = min(rows, key=lambda r: r['pelvisZ'])
    flip = min(rows, key=lambda r: r['headAbovePelvis'])
    before = [r['frame'] for r in rows if r['frame'] < flip['frame'] and r['footZ'] < ground and r['headAbovePelvis'] > 0.55 * stand]
    contact = before[-1] if before else next((r['frame'] for r in rows if r['footZ'] < ground), 0)
    up = next((r['frame'] for r in rows if r['frame'] > flip['frame'] and r['headAbovePelvis'] > 0.75 * stand
               and r['footZ'] < ground), frames - 1)
    made_clips[side] = (seq, length, frames, rows)
    receipt['clips'][side] = {'asset': target_path, 'frames': frames, 'lengthSeconds': length, 'rootTravelRemovedCm': root_moves,
                              'pelvisTravelRemovedCm': pelvis_travel_removed, 'pelvisParent': g_parents.get('pelvis'),
                              'contactFrame': contact, 'lowestPelvis': low, 'mostInverted': flip, 'upright frame': up,
                              'minHeadZ': min(r['headZ'] for r in rows), 'maxHandToSwordCm': max(r['handToSwordCm'] for r in rows),
                              'pelvisTravelXYcm': math.dist((rows[0]['pelvisX'], rows[0]['pelvisY']), (rows[-1]['pelvisX'], rows[-1]['pelvisY'])),
                              'rows': rows}

(out / 'roll.json').write_text(json.dumps(receipt, indent=1, default=str) + '\n')  # measured, before any apply
side = opts.get('apply')
if side:
    seq, length, frames, rows = made_clips[side]
    knight = unreal.load_asset(g.KNIGHT_DEFINITION)
    k_rel = g.from_unreal(knight.get_editor_property('mesh_relative_transform'))
    src = {str(k): v for k, v in knight.get_editor_property('clips').items()}['Roll']
    definition = unreal.load_asset(g.DEFINITION)
    clips = {str(k): v for k, v in definition.get_editor_property('clips').items()}
    old = clips.get('RollKnightRetarget', clips['Roll'])
    r_k = src.get_editor_property('gameplay_play_rate') or 1.0
    s_k = src.get_editor_property('start_seconds')
    e_k = src.get_editor_property('end_seconds')
    e_k = src.get_editor_property('sequence').get_play_length() if e_k is None or e_k < 0 else e_k
    dur_k = (e_k - s_k) / r_k
    contact = receipt['clips'][side]['contactFrame']
    up = receipt['clips'][side]['upright frame']
    s_n = float(opts.get('start', contact * length / max(1, frames - 1)))
    end_n = float(opts.get('end', up * length / max(1, frames - 1)))
    r_n = min(1.35, max(0.75, (end_n - s_n) / dur_k))
    e_n = min(length, s_n + dur_k * r_n)

    def convert_root(v):
        actor = g.qrot(k_rel[0], g.vscale((v.x, v.y, v.z), k_rel[2]))
        return unreal.Vector(*g.vscale(g.qrot(g.qinv(g_rel[0]), actor), 1.0 / g_rel[2]))

    samples = src.get_editor_property('root_translation_samples_cm')
    yaws = list(src.get_editor_property('root_yaw_samples_degrees'))
    rate = src.get_editor_property('root_sample_rate') or 60.0
    root, yaw = [], []
    for i in range(int((e_n - s_n) * rate) + 1):
        f = min(max(i / rate * r_k / r_n * rate, 0.0), len(samples) - 1.0)
        a = int(f); b = min(a + 1, len(samples) - 1); w = f - a
        pa, pb = samples[a], samples[b]
        root.append(convert_root(unreal.Vector(pa.x + (pb.x - pa.x) * w, pa.y + (pb.y - pa.y) * w, pa.z + (pb.z - pa.z) * w)))
        if len(yaws) == len(samples):
            yaw.append(yaws[a] + (yaws[b] - yaws[a]) * w)
    keep = old.copy()
    clip = old.copy()
    clip.set_editor_property('sequence', seq)
    clip.set_editor_property('start_seconds', s_n)
    clip.set_editor_property('end_seconds', e_n)
    clip.set_editor_property('loop', False)
    clip.set_editor_property('gameplay_play_rate', r_n)
    clip.set_editor_property('root_translation_samples_cm', root)
    if yaw:
        clip.set_editor_property('root_yaw_samples_degrees', yaw)
    clip.set_editor_property('root_sample_rate', rate)
    clip.set_editor_property('approved_source_file', SOURCES[side] + ' (Epic Game Animation Sample, free; retargeted by '
                             'RTG_UEFN_to_Greystone; root held; timed to KnightB Roll)')
    if 'RollKnightRetarget' not in clips:
        clips['RollKnightRetarget'] = keep
    clips['Roll'] = clip
    definition.set_editor_property('clips', clips)
    library.save_asset(g.DEFINITION, only_if_is_dirty=False)
    receipt['applied'] = {'side': side, 'start': s_n, 'end': e_n, 'rate': r_n, 'knightRate': r_k, 'knightGameSeconds': dur_k,
                          'newGameSeconds': (e_n - s_n) / r_n, 'rootSamples': len(root),
                          'oldRollSequence': old.get_editor_property('sequence').get_path_name()}
(out / 'roll.json').write_text(json.dumps(receipt, indent=1, default=str) + '\n')
g.write_result(out, {'ok': True, 'applied': receipt.get('applied'),
                     'summary': {k: {x: v[x] for x in v if x != 'rows'} for k, v in receipt['clips'].items()}})
