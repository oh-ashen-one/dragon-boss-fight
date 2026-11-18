"""Trial T4 / step 2: the Greystone data asset supplier. Writes /Game/Characters/Greystone/Runtime/DA_Greystone, which
AVeyrKnight loads under -VeyrGreystone (VeyrGreystone::DefinitionPath).

usage (through run_greystone.py): definition --set anims=<Local/greystone/retarget-*/anims.json> [--set replace=true]
       [--set shieldBack='{"translation_cm":[..],"rotation_xyzw":[..]}']   (spine_03-local, from the skin-sheet pass)

Same clip keys as the KnightB definition (all 64 when the retarget step ran without a key filter), each entry copied
field by field from DA_Knight so action code, damage windows, impact times, play rates, reach and root tracks keep
their numbers. Changed per entry: Sequence (A_GS_<key>), MeshOverride and WeaponMesh (none: Greystone's sword and
shield are skinned), RootTranslationSamplesCm converted to Greystone mesh-local cm (same world path:
p_g = Rg^-1 Rk p_k * sk/sg), ApprovedSourceFile/SHA256 (the retarget source). Extra film-only keys ParagonIdle,
ParagonJogFwd, ParagonAttackPrimaryA hold Epic's native clips (never used by gameplay code).

Bone targets: head->head, weapon_hand->hand_r, left/right_foot->ball_l/r, weapon_base/weapon_tip on sword_bottom
(28 % and 100 % from FX_Sword_Bottom to FX_Sword_Top, the old prop-sweep proportions), cup_socket->ik_hand_gun (baked),
flask_grip/flask_spout/left_grip->hand_l (KnightB offsets moved through the reference hand frames - approximate),
shield_back->spine_03 (first guess: shield turned flat on the back, 25 cm behind the chest). No weapon_socket or
weapon_grip target, so the BoatWeapon prop stays hidden and the sweep uses weapon_base/weapon_tip.
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
tools = unreal.AssetToolsHelpers.get_asset_tools()
anims_file = Path(opts['anims']).resolve()
assert anims_file.is_relative_to((g.ROOT / 'Local').resolve())
anims_doc = json.loads(anims_file.read_text())
scale = anims_doc['scale']
g_rel = (tuple(scale['rotation_xyzw']), tuple(scale['translation_cm']), float(scale['scale']))
knight = unreal.load_asset(g.KNIGHT_DEFINITION)
k_rel = g.from_unreal(knight.get_editor_property('mesh_relative_transform'))
grey_mesh = unreal.load_asset(g.GREYSTONE_MESH)
k_world = g.reference_world(knight.get_editor_property('skeletal_mesh'))
g_world = g.reference_world(grey_mesh)

if library.does_asset_exist(g.DEFINITION):
    if not opts.get('replace'):
        raise RuntimeError(g.DEFINITION + ' exists; pass --set replace=true')
    library.delete_asset(g.DEFINITION)
factory = unreal.DataAssetFactory()
factory.set_editor_property('data_asset_class', unreal.VeyrVisualDefinition)
definition = tools.create_asset('DA_Greystone', g.RUNTIME, unreal.VeyrVisualDefinition, factory)

FIELDS = ('start_seconds', 'end_seconds', 'impact_seconds', 'b_loop', 'damage_windows', 'nominal_speed_cm_per_second',
          'attack_reach_cm', 'gameplay_play_rate', 'root_yaw_samples_degrees', 'root_sample_rate', 'b_root_motion_removed',
          'b_root_motion_vertical')


def prop(struct, name, value=None, set_value=False):
    # Python names of bool UPROPERTYs drop the b prefix in some engine versions: try both spellings.
    for candidate in (name, name[2:] if name.startswith('b_') else name):
        try:
            if set_value:
                struct.set_editor_property(candidate, value)
                return True
            return struct.get_editor_property(candidate)
        except Exception:
            continue
    raise AttributeError(name)


def convert_root(point):
    v = (point.x, point.y, point.z)
    actor = g.qrot(k_rel[0], g.vscale(v, k_rel[2]))
    local = g.vscale(g.qrot(g.qinv(g_rel[0]), actor), 1.0 / g_rel[2])
    return unreal.Vector(*local)


knight_clips = {str(k): v for k, v in knight.get_editor_property('clips').items()}
clips = {}
for key, entry in anims_doc['anims'].items():
    src = knight_clips[key]
    clip = unreal.VeyrVisualClip()
    for field in FIELDS:
        prop(clip, field, prop(src, field), True)
    clip.set_editor_property('sequence', unreal.load_asset(entry['sequence']))
    clip.set_editor_property('root_translation_samples_cm', [convert_root(p) for p in src.get_editor_property('root_translation_samples_cm')])
    clip.set_editor_property('approved_source_file', entry['source'] + ' (retargeted by RTG_KnightB_to_Greystone)')
    clip.set_editor_property('approved_source_sha256', entry['sourceSHA256'])
    clips[key] = clip
for key, path in g.PARAGON_EXTRA.items():
    clip = unreal.VeyrVisualClip()
    clip.set_editor_property('sequence', unreal.load_asset(path))
    prop(clip, 'b_loop', key != 'ParagonAttackPrimaryA', True)
    clip.set_editor_property('approved_source_file', path + ' (Epic Paragon: Greystone, native)')
    clips[key] = clip
definition.set_editor_property('skeletal_mesh', grey_mesh)
definition.set_editor_property('mesh_relative_transform', g.to_unreal(g_rel))
definition.set_editor_property('clips', clips)
props = knight.get_editor_property('props')
definition.set_editor_property('props', props)  # Cup (heal) and any other approved props, unchanged


def target(bone, local=((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 1.0)):
    t = unreal.VeyrVisualBoneTarget()
    t.set_editor_property('bone_name', bone)
    t.set_editor_property('local_offset', g.to_unreal(local))
    return t


def actor(world, name, rel):
    return g.compose(g.from_unreal(world[name]), rel)


def hand_offset(k_offset, k_bone='LeftHand', g_bone='hand_l'):
    """KnightB bone-local offset -> Greystone bone-local, through the two reference-pose hand frames (actor space)."""
    hk, hg = actor(k_world, k_bone, k_rel), actor(g_world, g_bone, g_rel)
    off = g.from_unreal(k_offset)
    world_off = g.compose(off, hk)
    return g.relative(world_off, hg)


targets = {'head': target('head'), 'weapon_hand': target('hand_r'), 'left_foot': target('ball_l'),
           'right_foot': target('ball_r'), 'cup_socket': target('ik_hand_gun')}
bottom = g.from_unreal(g_world['sword_bottom'])
s_lo = g.socket_world(grey_mesh, 'FX_Sword_Bottom', g_world)
s_hi = g.socket_world(grey_mesh, 'FX_Sword_Top', g_world)
lo = g.from_unreal(s_lo)[1] if s_lo else bottom[1]
hi = g.from_unreal(s_hi)[1] if s_hi else g.from_unreal(g_world['sword_top'])[1]
for name, share in (('weapon_base', .28), ('weapon_tip', 1.0)):
    point = g.vadd(lo, g.vscale(g.vsub(hi, lo), share))
    local = g.relative(((0.0, 0.0, 0.0, 1.0), point, 1.0), bottom)
    targets[name] = target('sword_bottom', (((0.0, 0.0, 0.0, 1.0)), local[1], 1.0))
knight_targets = {str(k): v for k, v in knight.get_editor_property('bone_targets').items()}
for name in ('flask_grip', 'flask_spout', 'left_grip'):
    if name in knight_targets:
        targets[name] = target('hand_l', hand_offset(knight_targets[name].get_editor_property('local_offset')))

# Shield on the back: first guess, refined by eye on the skin sheet (pass --set shieldBack=... to override).
spine = actor(g_world, 'spine_03', g_rel)
shield = actor(g_world, 'shield_inner', g_rel)
if opts.get('shieldBack'):
    sb = opts['shieldBack']
    back_local = (tuple(sb['rotation_xyzw']), tuple(sb['translation_cm']), 1.0)
else:
    outward = g.vnorm(g.vsub(shield[1], actor(g_world, 'lowerarm_l', g_rel)[1]))   # forearm -> shield, actor space
    turn = g.qbetween(outward, (-1.0, 0.0, 0.0))                                      # point that side backwards
    behind = g.vadd(spine[1], (-25.0, 0.0, -10.0))
    target_actor = (g.qnorm(g.qmul(turn, shield[0])), behind, shield[2])
    back_local = g.relative(target_actor, spine)
targets['shield_back'] = target('spine_03', back_local)
definition.set_editor_property('bone_targets', targets)
definition.set_editor_property('required_bone_targets', sorted(targets))
definition.set_editor_property('required_clips', [k for k in g.KNIGHT_CLIPS if k in clips])
definition.set_editor_property('source_sha256', g.sha256(g.package_file(g.GREYSTONE_MESH)))
errors = [str(e) for e in definition.validate_definition(len([k for k in g.KNIGHT_CLIPS if k in clips]) == 64)]
library.save_loaded_asset(definition)
receipt = {'definition': g.DEFINITION, 'clips': sorted(clips), 'missingKnightKeys': [k for k in g.KNIGHT_CLIPS if k not in clips],
           'meshRelativeTransform': {'rotation_xyzw': list(g_rel[0]), 'translation_cm': list(g_rel[1]), 'scale': g_rel[2]},
           'boneTargets': {k: str(v.get_editor_property('bone_name')) for k, v in targets.items()},
           'shieldBackLocal': {'rotation_xyzw': list(back_local[0]), 'translation_cm': list(back_local[1])},
           'validationErrors': errors, 'fileSHA256': g.sha256(g.package_file(g.DEFINITION))}
(out / 'definition.json').write_text(json.dumps(receipt, indent=1) + '\n')
g.write_result(out, {'success': not errors, 'errors': errors, 'clips': len(clips)})
