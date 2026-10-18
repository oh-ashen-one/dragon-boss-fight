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
                # UE Python adapts bool + out-transform to (bool, Transform).
                if not isinstance(first, tuple) or len(first) != 2 or first[0] is not True:
                    raise RuntimeError('Unexpected/missing native target result: ' + repr(first))
                first_transform = transform_data(first[1])
                if not presentation.sample_clip_phase(clip_name, phase):
                    raise RuntimeError('Repeated sample rejected')
                second = presentation.get_bone_target_world_transform('weapon_hand')
                if not second[0]:
                    raise RuntimeError('Repeated target query rejected')
                error = maximum_difference(first_transform, transform_data(second[1]))
                if error > 0.00001:
                    raise RuntimeError('Repeated synchronous sample differs: ' + str(error))
                receipt['samples'].append({"clip": str(clip_name), "phase": phase,
                    "sequenceSeconds": presentation.get_editor_property('current_sequence_seconds'),
                    "repeatMaxTransformError": error, "weaponHandWorld": first_transform})
        if presentation.sample_clip_time('__VeyrMissingClipValidation__', 0.0):
            raise RuntimeError('Missing clip unexpectedly accepted')
        missing = presentation.get_bone_target_world_transform('weapon_hand')
        if missing[0]:
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
