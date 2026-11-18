"""Trial T3b / step 2: batch-retarget every KnightB clip of DA_Knight onto Greystone, then bake the props.

Output: /Game/Characters/Greystone/Anims/A_GS_<ClipKey> (one per distinct source sequence; keys sharing a sequence
share the output, named after the first key). build_definition.py reads anims.json from this step's report.
Options: --set keys='["Idle","Run","LightAttack","Roll"]' restricts the batch (the one-day trial), replace=true.

Baked after retargeting (the retargeter leaves unchained bones at their reference local transform):
- sword_bottom (and sword_top if it is not its child): per frame the blade points where KnightB's blade pointed
  (actor space), grip position stays Greystone's own (hand_r reference offset). Blade axis of the KnightB prop =
  far end of the clip's WeaponMesh longest bounds axis (same rule as AVeyrKnight::GetWeaponSweep); Greystone's =
  sword_bottom -> sword_top. Shortest-arc alignment only: the blade's roll (edge vs flat) is NOT matched - check on film.
- ik_hand_gun carries KnightB's CupSocket: KnightB cup actor transform per frame, moved by the left-hand position
  difference between the two rigs, so the cup stays in the palm; cup scale (the clips hide it with scale) carried.
  DA_Greystone maps cup_socket -> ik_hand_gun.

API relied on (installed 5.8.3 headers): UIKRetargetBatchOperation::RunBatchRetarget(FIKRetargetBatchOperationInputs)
(IKRigEditor/Public/RetargetEditor/IKRetargetBatchOperation.h; DuplicateAndRetarget is deprecated in 5.8),
UAnimPoseExtensions::GetAnimPoseAtFrame / GetBonePose(World) (AnimationBlueprintLibrary/Public/AnimPose.h),
UAnimSequenceBase::Controller -> IAnimationDataController::OpenBracket/AddBoneCurve/SetBoneTrackKeys/CloseBracket.
"""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
opts = job['options']
library = unreal.EditorAssetLibrary
knight = unreal.load_asset(g.KNIGHT_DEFINITION)
knight_mesh = knight.get_editor_property('skeletal_mesh')
grey_mesh = unreal.load_asset(g.GREYSTONE_MESH)
rtg = unreal.load_asset(g.RIGS + '/RTG_KnightB_to_Greystone')
assert knight and knight_mesh and grey_mesh and rtg, 'run copy_pack.py and the rigs step first'
clips = {str(k): v for k, v in knight.get_editor_property('clips').items()}
wanted = opts.get('keys') or g.KNIGHT_CLIPS
missing = [k for k in wanted if k not in clips]
assert not missing, 'KnightB definition lacks keys: ' + ', '.join(missing)

# KnightB mesh-relative transform (component -> actor) and Greystone's planned one (build_definition computes the
# same numbers; both read greystone_scale.json when present so the bake and the definition agree).
k_rel = g.from_unreal(knight.get_editor_property('mesh_relative_transform'))
scale_file = Path(opts.get('scaleFile', '')) if opts.get('scaleFile') else None
if scale_file and scale_file.is_file():
    plan = json.loads(scale_file.read_text())
    g_rel = (tuple(plan['rotation_xyzw']), tuple(plan['translation_cm']), plan['scale'])
else:
    g_rel = None  # computed below from the reference poses, then written for build_definition

k_world = g.reference_world(knight_mesh)
g_world = g.reference_world(grey_mesh)
g_parents = g.bone_parents(grey_mesh)
if g_rel is None:
    import math
    head_k = k_world['Head'].translation.z * k_rel[2]          # KnightB head bone height above its sole, world cm
    head_g = g_world['head'].translation.z                       # Greystone, mesh cm (origin at the sole assumed)
    scale = head_k / head_g
    fwd = g.vnorm(g.vsub(g.vadd(g.from_unreal(g_world['ball_l'])[1], g.from_unreal(g_world['ball_r'])[1]),
                         g.vadd(g.from_unreal(g_world['foot_l'])[1], g.from_unreal(g_world['foot_r'])[1])))
    yaw = -math.atan2(fwd[1], fwd[0])                            # turn the mesh's toe direction onto actor +X
    q = (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
    g_rel = (q, k_rel[1], scale)                                 # same capsule-to-sole offset as KnightB
    plan = {'rotation_xyzw': list(q), 'translation_cm': list(k_rel[1]), 'scale': scale,
            'yawDegrees': math.degrees(yaw), 'meshForward': fwd, 'headBoneKnightWorldCm': head_k,
            'headBoneGreystoneMeshCm': head_g, 'rule': 'head bone at the KnightB head-bone height (E-plan T4)'}
(out / 'greystone_scale.json').write_text(json.dumps(plan, indent=1) + '\n')


def blade_axis(static_mesh):
    box = static_mesh.get_bounding_box()
    lo, hi = (box.min.x, box.min.y, box.min.z), (box.max.x, box.max.y, box.max.z)
    size = [h - l for l, h in zip(lo, hi)]
    axis = size.index(max(size))
    near = lo[axis] if abs(lo[axis]) < abs(hi[axis]) else hi[axis]
    far = hi[axis] if near == lo[axis] else lo[axis]
    v = [0.0, 0.0, 0.0]; v[axis] = 1.0 if far > near else -1.0
    return tuple(v)


bottom_ref, top_ref, hand_ref = (g.from_unreal(g_world[n]) for n in ('sword_bottom', 'sword_top', 'hand_r'))
blade_g_local = g.vnorm(g.qrot(g.qinv(bottom_ref[0]), g.vsub(top_ref[1], bottom_ref[1])))
bottom_local_ref = g.relative(bottom_ref, hand_ref)
top_is_child = g_parents.get('sword_top') == 'sword_bottom'
top_from_bottom = g.relative(top_ref, bottom_ref)
gun_parent = g_parents.get('ik_hand_gun')
options = unreal.AnimPoseEvaluationOptions()
options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.RAW)


def pose_at(sequence, frame, mesh):
    options.set_editor_property('optional_skeletal_mesh', mesh)
    return unreal.AnimPoseExtensions.get_anim_pose_at_frame(sequence, frame, options)


def bone(pose, name):
    return g.from_unreal(unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD))


def set_track(controller, name, rows):
    controller.add_bone_curve(name, False)
    controller.set_bone_track_keys(name, [unreal.Vector(*r[1]) for r in rows], [unreal.Quat(*r[0]) for r in rows],
                                   [unreal.Vector(r[2], r[2], r[2]) for r in rows], False)


by_sequence = {}
for key in wanted:
    seq = clips[key].get_editor_property('sequence')
    by_sequence.setdefault(seq.get_path_name(), []).append(key)

anims = {}
for source_path, keys in by_sequence.items():
    source = unreal.load_asset(source_path)
    name = 'A_GS_' + keys[0]
    target_path = g.ANIMS + '/' + name
    if library.does_asset_exist(target_path) and not opts.get('replace'):
        raise RuntimeError(target_path + ' exists; pass --set replace=true')
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property('assets_to_retarget', [library.find_asset_data(source_path)])
    inputs.set_editor_property('source_mesh', clips[keys[0]].get_editor_property('mesh_override') or knight_mesh)
    inputs.set_editor_property('target_mesh', grey_mesh)
    inputs.set_editor_property('ik_retarget_asset', rtg)
    inputs.set_editor_property('search', source.get_name())
    inputs.set_editor_property('replace', name)
    inputs.set_editor_property('target_path', g.ANIMS)
    inputs.set_editor_property('include_referenced_assets', False)
    inputs.set_editor_property('overwrite_existing_files', True)
    made = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    made_paths = [str(a.package_name) for a in made]
    if target_path not in made_paths:
        raise RuntimeError(f'{source_path}: retarget produced {made_paths}, expected {target_path}')
    result = unreal.load_asset(target_path)
    frames_k = unreal.AnimationLibrary.get_num_frames(source)
    frames_g = unreal.AnimationLibrary.get_num_frames(result)
    assert frames_k == frames_g, f'{name}: frame count changed {frames_k} -> {frames_g}'
    weapon = clips[keys[0]].get_editor_property('weapon_mesh')
    blade_k_local = blade_axis(weapon) if weapon else None
    sword_rows, top_rows, gun_rows, worst_turn = [], [], [], 0.0
    for frame in range(frames_g):
        pk, pg = pose_at(source, frame, knight_mesh), pose_at(result, frame, grey_mesh)
        hand_g = g.compose(bone(pg, 'hand_r'), g_rel)
        if blade_k_local:
            weapon_k = g.compose(bone(pk, 'WeaponSocket'), k_rel)
            fix = g.qbetween(blade_g_local, blade_k_local)              # Greystone blade axis -> KnightB blade axis (local)
            sword_actor_q = g.qnorm(g.qmul(weapon_k[0], fix))
            local_q = g.qnorm(g.qmul(g.qinv(hand_g[0]), sword_actor_q))  # (S * H^-1).q = H.q^-1 * S.q
            row = (local_q, bottom_local_ref[1], bottom_local_ref[2])
            worst_turn = max(worst_turn, g.angle_deg(g.qmul(g.qinv(bottom_local_ref[0]), local_q)))
        else:
            row = bottom_local_ref
        sword_rows.append(row)
        if not top_is_child:
            # sword_top is a sibling under hand_r: keep it rigid with the rebaked sword_bottom.
            top_rows.append(g.compose(top_from_bottom, row))
        if gun_parent:
            cup_k = g.compose(bone(pk, 'CupSocket'), k_rel)
            hand_l_k = g.compose(bone(pk, 'LeftHand'), k_rel)
            hand_l_g = g.compose(bone(pg, 'hand_l'), g_rel)
            cup_actor = (cup_k[0], g.vadd(cup_k[1], g.vsub(hand_l_g[1], hand_l_k[1])), cup_k[2])
            cup_comp_g = g.compose(cup_actor, g.tinv(g_rel))
            parent_g = bone(pg, gun_parent)
            gun_rows.append(g.relative(cup_comp_g, parent_g))
    controller = result.get_editor_property('controller')
    controller.open_bracket(unreal.Text('Greystone prop bake'), False)
    set_track(controller, 'sword_bottom', sword_rows)
    if top_rows:
        set_track(controller, 'sword_top', top_rows)
    if gun_rows:
        set_track(controller, 'ik_hand_gun', gun_rows)
    controller.close_bracket(False)
    library.save_loaded_asset(result)
    for key in keys:
        anims[key] = {'sequence': target_path, 'source': source_path, 'sourceSHA256': g.sha256(g.package_file(source_path.split('.')[0])),
                      'frames': frames_g, 'swordBaked': bool(blade_k_local), 'swordMaxTurnFromGripDeg': worst_turn,
                      'cupBaked': bool(gun_rows), 'outputSHA256': g.sha256(g.package_file(target_path))}
    unreal.log(f'VEYR_GREYSTONE_RETARGET {name} frames={frames_g} keys={",".join(keys)}')

(out / 'anims.json').write_text(json.dumps({'scale': plan, 'swordTopIsChild': top_is_child, 'ikHandGunParent': gun_parent,
                                            'anims': anims}, indent=1) + '\n')
g.write_result(out, {'success': len(anims) == len(wanted), 'clips': len(anims), 'sequences': len(by_sequence)})
