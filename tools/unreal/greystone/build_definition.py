"""Trial T4 / step 2: the Greystone data asset supplier. Writes /Game/Characters/Greystone/Runtime/DA_Greystone, which
AVeyrKnight loads under -VeyrGreystone (VeyrGreystone::DefinitionPath).

usage (through run_greystone.py): definition --set anims=<Local/greystone/retarget-*/anims.json>
       --set native=<Local/greystone/native-*/native.json> [--set trial=true] [--set replace=true]
       Greystone's own clips (greystone_common.NATIVE; with trial=true only TRIAL_NATIVE) replace retargeted ones,
       timed to KnightB's gameplay numbers (see the native block below); everything else is retargeted.
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
# anims: one anims.json or a list of them (the retarget step runs in short batches under the 6-minute lock rule).
anims_doc = {'anims': {}}
for item in (opts['anims'] if isinstance(opts['anims'], list) else [opts['anims']]):
    anims_file = Path(item).resolve()
    assert anims_file.is_relative_to((g.ROOT / 'Local').resolve())
    doc = json.loads(anims_file.read_text())
    if 'scale' in anims_doc and doc['scale'] != anims_doc['scale']:
        raise RuntimeError('retarget batches disagree on the scale plan: ' + str(anims_file))
    anims_doc['scale'] = doc['scale']
    anims_doc['anims'].update(doc['anims'])
scale = anims_doc['scale']
g_rel = (tuple(scale['rotation_xyzw']), tuple(scale['translation_cm']), float(scale['scale']))
knight = unreal.load_asset(g.KNIGHT_DEFINITION)
k_rel = g.from_unreal(knight.get_editor_property('mesh_relative_transform'))
grey_mesh = unreal.load_asset(g.GREYSTONE_MESH)
# Shown skin: the owner's pick (Novaborn, gold energy) when the skin step made it; --set mesh=<path> overrides.
shown_path = opts.get('mesh') or (g.OWNER_SKIN_MESH if library.does_asset_exist(g.OWNER_SKIN_MESH) else g.GREYSTONE_MESH)
shown_mesh = unreal.load_asset(shown_path)
k_world = g.reference_world(knight.get_editor_property('skeletal_mesh'))
g_world = g.reference_world(grey_mesh)

if library.does_asset_exist(g.DEFINITION):
    if not opts.get('replace'):
        raise RuntimeError(g.DEFINITION + ' exists; pass --set replace=true')
    # Rewrite in place: delete_asset leaves the package name taken in an unattended commandlet (2026-11-19 W5),
    # and every field below is set again from this run's inputs.
    definition = unreal.load_asset(g.DEFINITION)
    assert isinstance(definition, unreal.VeyrVisualDefinition), g.DEFINITION + ' is not a VeyrVisualDefinition'
else:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', unreal.VeyrVisualDefinition)
    definition = tools.create_asset('DA_Greystone', g.RUNTIME, unreal.VeyrVisualDefinition, factory)
assert definition is not None, 'could not create or load ' + g.DEFINITION

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
    if opts.get('native') and key in g.NATIVE and key in json.loads(Path(opts['native']).read_text()):
        continue  # Greystone's own clip wins (below)
    src = knight_clips[key]
    clip = unreal.VeyrVisualClip()
    for field in FIELDS:
        prop(clip, field, prop(src, field), True)
    clip.set_editor_property('sequence', unreal.load_asset(entry['sequence']))
    clip.set_editor_property('root_translation_samples_cm', [convert_root(p) for p in src.get_editor_property('root_translation_samples_cm')])
    clip.set_editor_property('approved_source_file', entry['source'] + ' (retargeted by RTG_KnightB_to_Greystone)')
    clip.set_editor_property('approved_source_sha256', entry['sourceSHA256'])
    clips[key] = clip
# ---- Greystone's own clips, timed so every gameplay number stays KnightB's (owner-fixed hitboxes and difficulty) ----
# Game time tau of a KnightB action = source seconds since the action start / GameplayPlayRate (AVeyrKnight).
# For a native clip we pick start S_n and rate r_n so the native moment lands at the same tau, then express KnightB's
# windows and root path in native source time:  windows_n = windows_k * r_n / r_k ;  root sample at native source time
# t (since start) = KnightB root sample at t * r_k / r_n, converted to Greystone mesh space. Play rate is kept within
# RATE_MIN..RATE_MAX; when it hits a limit the miss is recorded (seconds of game time the native moment is off).
RATE_MIN, RATE_MAX = 0.75, 1.35
native_doc = json.loads(Path(opts['native']).read_text()) if opts.get('native') else {}
native_keys = [k for k in (g.TRIAL_NATIVE if opts.get('trial') else g.NATIVE) if k in native_doc]
native_receipt = {}


def knight_game(src):
    r = prop(src, 'gameplay_play_rate') or 1.0
    start = prop(src, 'start_seconds')
    seq = prop(src, 'sequence')
    end = prop(src, 'end_seconds')
    end = seq.get_play_length() if end is None or end < 0 else end
    windows = [(w.x, w.y) for w in prop(src, 'damage_windows')]
    impact = prop(src, 'impact_seconds')
    hit = windows[0][0] / r if windows else ((impact - start) / r if impact is not None and impact >= 0 else None)
    return r, start, end, windows, hit, (end - start) / r


def warp_root(src, r_k, r_n, length_n):
    samples = src.get_editor_property('root_translation_samples_cm')
    yaws = list(src.get_editor_property('root_yaw_samples_degrees'))
    rate = prop(src, 'root_sample_rate') or 60.0
    if len(samples) < 2:
        return [], [], rate
    out_t, out_y = [], []
    for i in range(int(length_n * rate) + 1):
        f = min(max(i / rate * r_k / r_n * rate, 0.0), len(samples) - 1.0)
        a = int(f); b = min(a + 1, len(samples) - 1); w = f - a
        pa, pb = samples[a], samples[b]
        out_t.append(convert_root(unreal.Vector(pa.x + (pb.x - pa.x) * w, pa.y + (pb.y - pa.y) * w, pa.z + (pb.z - pa.z) * w)))
        if len(yaws) == len(samples):
            out_y.append(yaws[a] + (yaws[b] - yaws[a]) * w)
    return out_t, out_y, rate


for key in native_keys:
    n = native_doc[key]
    src = knight_clips[key]
    role = n['role']
    clip = unreal.VeyrVisualClip()
    for field in FIELDS:
        prop(clip, field, prop(src, field), True)
    clip.set_editor_property('sequence', unreal.load_asset(n['sequence']))
    r_k, s_k, e_k, w_k, hit_k, dur_k = knight_game(src)
    length = n['lengthSeconds']
    row = {'native': n['sequence'], 'role': role}
    if role == 'loop':
        speed = n['footSpeedCmPerSecond'] * g_rel[2]
        prop(clip, 'start_seconds', 0.0, True); prop(clip, 'end_seconds', -1.0, True); prop(clip, 'b_loop', True, True)
        # Keep the knight's nominal: lock-on strafe speed is derived from it (LockOnSpeedCap), so gameplay speed stays
        # the knight's. The stride difference goes into the play rate: source advance = speed / nominal * rate
        # = speed / Greystone's planted-foot speed, so his feet stay planted.
        knight_nominal = prop(src, 'nominal_speed_cm_per_second') or 0.0
        rate = min(4.0, max(0.1, knight_nominal / speed)) if knight_nominal > 1.0 and speed > 1.0 else 1.0
        prop(clip, 'gameplay_play_rate', rate, True)
        row.update(rate=rate)
        root, yaw = [unreal.Vector(*p) for p in n['rootSamples']], n['rootYawSamples']
        clip.set_editor_property('root_translation_samples_cm', root)
        prop(clip, 'root_yaw_samples_degrees', yaw, True); prop(clip, 'root_sample_rate', n['rootSampleRate'], True)
        prop(clip, 'b_root_motion_removed', False, True)
        row.update(nominalSpeedWorld=speed, knightNominal=prop(src, 'nominal_speed_cm_per_second'))
    else:
        if role == 'attack' and hit_k is not None and n['contactSeconds'] > 0:
            contact = n['contactSeconds']
            r_n = min(RATE_MAX, max(RATE_MIN, contact / hit_k))
            s_n = max(0.0, contact - hit_k * r_n)
            row['contactMissSeconds'] = (contact - s_n) / r_n - hit_k
        else:
            r_n = min(RATE_MAX, max(RATE_MIN, length / dur_k)) if dur_k > 0 else 1.0
            s_n = 0.0
        e_n = min(length, s_n + dur_k * r_n)
        row['recoveryShortSeconds'] = max(0.0, dur_k - (e_n - s_n) / r_n)   # native ends early: last pose held
        prop(clip, 'start_seconds', s_n, True); prop(clip, 'end_seconds', e_n, True); prop(clip, 'b_loop', False, True)
        prop(clip, 'gameplay_play_rate', r_n, True)
        prop(clip, 'damage_windows', [unreal.Vector2D(a * r_n / r_k, b * r_n / r_k) for a, b in w_k], True)
        impact = prop(src, 'impact_seconds')
        if impact is not None and impact >= 0:
            prop(clip, 'impact_seconds', s_n + (impact - s_k) * r_n / r_k, True)
        root, yaw, rate = warp_root(src, r_k, r_n, e_n - s_n)
        clip.set_editor_property('root_translation_samples_cm', root)
        if yaw:
            prop(clip, 'root_yaw_samples_degrees', yaw, True)
        prop(clip, 'root_sample_rate', rate, True)
        row.update(rate=r_n, start=s_n, end=e_n, knightRate=r_k, knightGameSeconds=dur_k, knightHitGameSeconds=hit_k)
    clip.set_editor_property('approved_source_file', n['sequence'] + ' (Epic Paragon: Greystone, native; timed to KnightB)')
    clips[key] = clip
    native_receipt[key] = row
missing = [k for k in (g.TRIAL_NATIVE if opts.get('trial') else g.NATIVE) if k not in native_keys]
if missing:
    native_receipt['_missingMeasurements'] = missing

for key, path in g.PARAGON_EXTRA.items():
    clip = unreal.VeyrVisualClip()
    clip.set_editor_property('sequence', unreal.load_asset(path))
    prop(clip, 'b_loop', key != 'ParagonAttackPrimaryA', True)
    clip.set_editor_property('approved_source_file', path + ' (Epic Paragon: Greystone, native)')
    clips[key] = clip
definition.set_editor_property('skeletal_mesh', shown_mesh)
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
s_lo = g.socket_world(shown_mesh, 'FX_Sword_Bottom', g_world) or g.socket_world(grey_mesh, 'FX_Sword_Bottom', g_world)
s_hi = g.socket_world(shown_mesh, 'FX_Sword_Top', g_world) or g.socket_world(grey_mesh, 'FX_Sword_Top', g_world)
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
(out / 'native-timing.json').write_text(json.dumps(native_receipt, indent=1) + '\n')
library.save_loaded_asset(definition)
receipt = {'definition': g.DEFINITION, 'shownMesh': shown_path, 'clips': sorted(clips), 'missingKnightKeys': [k for k in g.KNIGHT_CLIPS if k not in clips],
           'meshRelativeTransform': {'rotation_xyzw': list(g_rel[0]), 'translation_cm': list(g_rel[1]), 'scale': g_rel[2]},
           'boneTargets': {k: str(v.get_editor_property('bone_name')) for k, v in targets.items()},
           'shieldBackLocal': {'rotation_xyzw': list(back_local[0]), 'translation_cm': list(back_local[1])},
           'validationErrors': errors, 'fileSHA256': g.sha256(g.package_file(g.DEFINITION))}
(out / 'definition.json').write_text(json.dumps(receipt, indent=1) + '\n')
g.write_result(out, {'success': not errors, 'errors': errors, 'clips': len(clips)})
