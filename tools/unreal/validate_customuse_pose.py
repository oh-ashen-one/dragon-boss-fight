"""Run inside the owned editor's PIE through native Python console.

Checks actual registered Veyr presentation sampling and target transforms.
This does not launch an editor, edit assets, accept visual quality, or certify
combat contacts. Private receipts remain under Local/CustomuseImports.
"""
import datetime
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[2]


def transform_data(transform):
    return {"translation": [transform.translation.x, transform.translation.y, transform.translation.z],
            "rotation": [transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w],
            "scale": [transform.scale3d.x, transform.scale3d.y, transform.scale3d.z]}


def maximum_difference(a, b):
    return max(abs(x-y) for key in a for x, y in zip(a[key], b[key]))


def validate_lower_layers(presentation, clips, receipt):
    """Compare native local poses, with mask membership from the native hierarchy."""
    def require(result, message):
        if not result:
            raise RuntimeError(message)

    def pose():
        value = {str(name): transform_data(transform)
                 for name, transform in presentation.get_evaluated_local_pose().items()}
        require(value, 'No evaluated native local pose')
        return value

    def difference(first, second, bones=None):
        require(first.keys() == second.keys(), 'Local pose bone layout changed')
        selected = list(first) if bones is None else bones
        require(selected, 'Empty local pose comparison mask')
        return max(maximum_difference(first[name], second[name]) for name in selected)

    names = {str(name): name for name in clips}
    for required in ['Guard', 'Heal', 'Walk']:
        require(required in names, 'Lower-layer test requires clip ' + required)

    def elapsed(name, phase):
        clip = clips[names[name]]
        start = clip.get_editor_property('start_seconds')
        end = clip.get_editor_property('end_seconds')
        if end < 0:
            end = clip.get_editor_property('sequence').get_play_length()
        require(end > start, 'Invalid native trim for ' + name)
        return (end-start)*phase

    require(presentation.sample_clip_time(names['Walk'], elapsed('Walk', .37)), 'Mask source rejected')
    reference = pose()
    for bone in ['Hips', 'LeftUpLeg', 'RightUpLeg', 'Spine']:
        require(bone in reference, 'Mask root missing in native local pose: ' + bone)

    def under(name, ancestor):
        visited = set()
        while name in reference and name not in visited:
            if name == ancestor:
                return True
            visited.add(name)
            name = str(presentation.get_parent_bone(name))
        return False

    lower_bones = [name for name in reference if name == 'Hips' or
                   under(name, 'LeftUpLeg') or under(name, 'RightUpLeg')]
    upper_bones = [name for name in reference if name not in lower_bones]
    require('Spine' in upper_bones and any('Arm' in name for name in upper_bones),
            'Native mask must retain spine and arm locals')
    checks = []
    receipt['lowerLayerChecks'] = {'lowerBones': lower_bones, 'upperBones': upper_bones, 'cases': checks}
    # Test every supplied directional locomotion clip without inventing a
    # forward substitute when a requested direction is absent.
    lower_names = sorted(name for name in names if name.startswith(('Walk', 'Run')))
    for upper_name in ['Guard', 'Heal']:
        upper_time = elapsed(upper_name, .41)
        for lower_name in lower_names:
            lower_time = elapsed(lower_name, .37)
            require(presentation.sample_clip_time(names[upper_name], upper_time), 'Upper reference rejected')
            upper = pose()
            require(presentation.sample_clip_time(names[lower_name], lower_time), 'Lower reference rejected')
            lower = pose()
            contrast = difference(upper, lower, lower_bones)
            require(contrast > .0001, 'Layer test lacks distinct lower poses: ' + lower_name)

            def layer(weight, alpha=1.0):
                require(presentation.sample_layered_clips(names[upper_name], upper_time,
                        names[lower_name], lower_time, weight, alpha), 'Layered sample rejected')
                return pose()

            zero_error = difference(layer(0.0), upper)
            full = layer(1.0)
            lower_error = difference(full, lower, lower_bones)
            upper_error = difference(full, upper, upper_bones)
            repeat_error = difference(full, layer(1.0))
            require(str(presentation.get_editor_property('current_lower_clip')) == lower_name,
                    'Native lower clip evidence differs from requested direction')
            require(presentation.begin_transition(), 'Layer source capture rejected')
            layer(.25, .5)
            middle = pose()
            require(presentation.begin_transition(), 'Interrupted composite capture rejected')
            interrupt_error = difference(middle, layer(.8, 0.0))
            require(presentation.sample_clip_time(names[upper_name], upper_time), 'Plain clearing sample rejected')
            clear_error = difference(upper, pose())
            require(str(presentation.get_editor_property('current_lower_clip')) == 'None' and
                    presentation.get_editor_property('current_lower_weight') == 0.0,
                    'Plain sampling retained lower-layer evidence')
            result = {'upper': upper_name, 'lower': lower_name, 'lowerPoseContrast': contrast,
                      'weightZeroMaxError': zero_error, 'weightOneLowerMaxError': lower_error,
                      'weightOneUpperMaxError': upper_error, 'repeatMaxError': repeat_error,
                      'interruptedAlphaZeroMaxError': interrupt_error, 'plainClearMaxError': clear_error}
            checks.append(result)
            require(max(zero_error, lower_error, upper_error, repeat_error, interrupt_error, clear_error) <= .00001,
                    'Native local lower-layer boundary/determinism mismatch: ' + str(result))
    require(not presentation.sample_layered_clips(names['Guard'], 0.0,
            '__VeyrMissingLowerValidation__', 0.0, 0.0, 1.0), 'Missing lower clip accepted at weight zero')
    require(not presentation.get_evaluated_local_pose(), 'Failed lower sample left local pose access valid')
    require(presentation.get_bone_target_world_transform('weapon_hand') is None,
            'Failed lower sample left world target access valid')
    receipt['lowerLayerChecks']['missingLowerAndStalePoseRejected'] = True


def run(definition_path):
    import unreal
    if not definition_path.startswith('/Game/Characters/Customuse/'):
        raise ValueError('Only this task character namespace is accepted')
    receipt = {"definition": definition_path, "passed": False, "samples": [],
               "visualAcceptance": False, "combatAcceptance": False}
    presentation = None
    destination = ROOT / 'Local/CustomuseImports'
    destination.mkdir(parents=True, exist_ok=True)
    name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8] + '-native-pose.json'
    try:
        worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if len(worlds) != 1:
            raise RuntimeError('Expected one owned PIE world')
        knights = unreal.GameplayStatics.get_all_actors_of_class(worlds[0], unreal.VeyrKnight)
        if len(knights) != 1:
            raise RuntimeError('Expected one Veyr knight in PIE')
        knight = knights[0]
        definition = unreal.load_asset(definition_path)
        if not isinstance(definition, unreal.VeyrVisualDefinition):
            raise RuntimeError('Missing native Veyr visual definition')
        before = transform_data(knight.get_actor_transform())
        if not knight.apply_customuse_visual(definition):
            raise RuntimeError('Native knight rejected the visual definition')
        presentation = knight.get_editor_property('imported_presentation')
        clips = definition.get_editor_property('clips')
        for clip_name, clip in clips.items():
            for phase in [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]:
                if not presentation.sample_clip_phase(clip_name, phase):
                    raise RuntimeError('Sample rejected: ' + str(clip_name))
                first = presentation.get_bone_target_world_transform('weapon_hand')
                # Verified UE5.8 binding adapts bool + out-transform to
                # Transform on success and None on failure.
                if not isinstance(first, unreal.Transform):
                    raise RuntimeError('Unexpected/missing native target result: ' + repr(first))
                first_transform = transform_data(first)
                if not presentation.sample_clip_phase(clip_name, phase):
                    raise RuntimeError('Repeated sample rejected')
                second = presentation.get_bone_target_world_transform('weapon_hand')
                if not isinstance(second, unreal.Transform):
                    raise RuntimeError('Repeated target query rejected')
                error = maximum_difference(first_transform, transform_data(second))
                if error > 0.00001:
                    raise RuntimeError('Repeated synchronous sample differs: ' + str(error))
                receipt['samples'].append({"clip": str(clip_name), "phase": phase,
                    "sequenceSeconds": presentation.get_editor_property('current_sequence_seconds'),
                    "repeatMaxTransformError": error, "weaponHandWorld": first_transform})
        names = list(clips.keys())
        if len(names) >= 2:
            source_name, destination_name = names[0], names[1]
            def hand():
                result = presentation.get_bone_target_world_transform('weapon_hand')
                if not isinstance(result, unreal.Transform):
                    raise RuntimeError('Blend target evaluation unavailable')
                return transform_data(result)
            def require(result, message):
                if not result:
                    raise RuntimeError(message)
            require(presentation.sample_clip_phase(source_name, .25), 'Blend source rejected')
            source_pose = hand()
            require(presentation.begin_transition(), 'Cannot capture evaluated blend source')
            require(presentation.sample_clip_phase_blended(destination_name, .75, 0.0), 'Alpha zero rejected')
            zero_error = maximum_difference(source_pose, hand())
            require(presentation.sample_clip_phase_blended(destination_name, .75, 1.0), 'Alpha one rejected')
            endpoint = hand()
            require(presentation.sample_clip_phase(destination_name, .75), 'Plain destination rejected')
            one_error = maximum_difference(endpoint, hand())
            require(presentation.sample_clip_phase(source_name, .25), 'Second blend source rejected')
            require(presentation.begin_transition(), 'Second transition capture rejected')
            require(presentation.sample_clip_phase_blended(destination_name, .75, .5), 'Midblend rejected')
            middle = hand()
            require(presentation.sample_clip_phase_blended(destination_name, .75, .5), 'Repeated midblend rejected')
            repeat_error = maximum_difference(middle, hand())
            require(presentation.begin_transition(), 'Interrupted blend capture rejected')
            require(presentation.sample_clip_phase_blended(source_name, .8, 0.0), 'Interrupted blend alpha zero rejected')
            interrupt_error = maximum_difference(middle, hand())
            receipt['blendChecks'] = {'alphaZeroMaxError': zero_error, 'alphaOneMaxError': one_error,
                                     'repeatedMiddleMaxError': repeat_error, 'interruptedMaxError': interrupt_error}
            if max(zero_error, one_error, repeat_error, interrupt_error) > .00001:
                raise RuntimeError('Native blend boundary or deterministic sampling mismatch')
        validate_lower_layers(presentation, clips, receipt)
        if presentation.sample_clip_time('__VeyrMissingClipValidation__', 0.0):
            raise RuntimeError('Missing clip unexpectedly accepted')
        missing = presentation.get_bone_target_world_transform('weapon_hand')
        if missing is not None:
            raise RuntimeError('Failed sample left target access valid')
        receipt['missingClipAndStalePoseRejected'] = True
        after = transform_data(knight.get_actor_transform())
        receipt['actorTransformMaximumChange'] = maximum_difference(before, after)
        if receipt['actorTransformMaximumChange'] > 0.00001:
            raise RuntimeError('Sampling changed gameplay actor transform')
        receipt['sourceSHA256'] = definition.get_editor_property('source_sha256')
        receipt['passed'] = True
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        if presentation is not None:
            presentation.sample_reference_pose()
        (destination / name).write_text(json.dumps(receipt, indent=2) + '\n')
        unreal.log('VEYR_NATIVE_POSE_RECEIPT ' + str(destination / name))
    return receipt
