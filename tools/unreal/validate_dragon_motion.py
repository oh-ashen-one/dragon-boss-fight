"""Owner-run native UE5.8 fresh-PIE dragon pose/geometry checks; never launches UE.

Call run_from_import_receipt('/absolute/Local/CustomuseImports/receipt.json') or
run('/Game/Characters/Customuse/DragonV3B/v005/DA_DragonV3B.DA_DragonV3B').
Applies that definition, then samples the actor's existing hidden native pose
probe. It never writes combat state, health, transforms or input. No screenshots
or rendered acceptance are claimed. Private JSON follows replay footprint keys;
derived contacts/warnings are explicitly separate from live runtime getters.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'Unreal/Veyr'
RECEIPTS = ROOT / 'Local/CustomuseImports'
TARGETS = ('head', 'mouth', 'mouth_aim', 'tail_tip') + tuple(
    f'{kind}{i}' for kind in ('leg', 'foot', 'tail') for i in range(4))
PHASES = (0., .25, .5, .75, 1.)


def xyz(value):
    result = [float(value.x), float(value.y), float(value.z)]
    if not all(math.isfinite(x) for x in result):
        raise RuntimeError('Non-finite native vector')
    return result


def transform(value):
    result = {'translation': xyz(value.translation), 'scale': xyz(value.scale3d),
              'rotation': [float(getattr(value.rotation, a)) for a in ('x', 'y', 'z', 'w')]}
    if not all(math.isfinite(v) for row in result.values() for v in row):
        raise RuntimeError('Non-finite native transform')
    return result


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def difference(first, second):
    if first.keys() != second.keys():
        raise RuntimeError('Target transform layout changed')
    return max(abs(a-b) for name in first for key in first[name]
               for a, b in zip(first[name][key], second[name][key]))


def capsule(a, b, radius):
    return {'shape': 3, 'origin': list(a), 'end': list(b), 'outerRadius': float(radius),
            'innerRadius': 0., 'halfAngleDegrees': 180., 'damaging': False}


def project_flame(origin, direction, radius, half_height):
    """Conservative ground capsule, same finite-cone interval policy as C++."""
    k = math.tan(math.radians(12.));step = 1750./32;points = [];radii = []
    for i in range(33):
        along = i*step;p = [a+along*d for a, d in zip(origin, direction)]
        r = along*k+radius+step*.5*(1+k)
        dz = max(0., radius-p[2], p[2]-(2*half_height-radius))
        if dz <= r:
            points.append([p[0], p[1], 0.]);radii.append(math.sqrt(max(0., r*r-dz*dz)))
    return capsule(points[0], points[-1], max(radii)) if points else None


def sampled_geometry(clip, points, radius, half_height):
    """Diagnostics from sampled bones, never a call that enables actor damage."""
    contacts = [];beam = None
    if clip == 'FireActive':
        a, b = points['mouth'], points['mouth_aim'];length = distance(a, b)
        direction = [(y-x)/length for x, y in zip(a, b)]
        beam = {'origin': a, 'direction': direction, 'length': 1750., 'halfAngleDegrees': 12.,
                'damaging': False, 'standingCapsuleGroundProjection': project_flame(a, direction, radius, half_height)}
    elif clip == 'BiteActive':
        contacts = [capsule(points['head'], points['mouth'], 100.)]
    elif clip in ('ClawActive', 'Claw0Active', 'Claw1Active'):
        p = points['foot1' if clip == 'Claw1Active' else 'foot0'];contacts = [capsule(p, p, 115.)]
    elif clip in ('Stomp2Active', 'Stomp3Active'):
        p = points['foot'+clip[5]];contacts = [capsule(p, p, 230.)]
    elif clip == 'TailActive':
        chain = [points[f'tail{i}'] for i in range(4)] + [points['tail_tip']]
        contacts = [capsule(a, b, r) for a, b, r in zip(chain, chain[1:], (130., 95., 65., 35.))]
    ground = [capsule([*c['origin'][:2], 0.], [*c['end'][:2], 0.], c['outerRadius']+radius) for c in contacts]
    return {'sampledBoneContactCapsules': contacts, 'sampledGroundContactProjections': ground, 'flame': beam,
            'scope': 'Native-pose geometry diagnostics only; actor state and damaging flags remain unchanged'}


def run(definition_path, max_wall_seconds=45., expected_source_sha256=None):
    import unreal
    if not definition_path.startswith('/Game/Characters/Customuse/DragonV3B/'):
        raise ValueError('Expected this task DragonV3B definition namespace')
    if not 5 <= max_wall_seconds <= 60:
        raise ValueError('Use a bounded 5–60 second wall budget')
    if Path(unreal.Paths.project_dir()).resolve() != PROJECT.resolve():
        raise RuntimeError('Wrong owned project')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = RECEIPTS / (stamp+'-'+uuid.uuid4().hex[:8]+'-native-dragon-validation.json')
    receipt = {'definition': definition_path, 'passed': False, 'samples': [], 'checks': {},
               'visualAcceptance': False, 'combatAcceptance': False, 'runtimeAttackCoverage': False,
               'scope': 'Fresh PIE native hidden-pose sampling; no damage/state/input writes',
               'scriptSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    probe = None;dragon = None;knight = None;before = None;target_names = TARGETS;started = time.monotonic()

    def require(value, message):
        if not value:
            raise RuntimeError(message)

    def state():
        return {'dragonTransform': transform(dragon.get_actor_transform()),
                'knightTransform': transform(knight.get_actor_transform()),
                'dragonHealth': float(dragon.get_editor_property('health')),
                'knightHealth': float(knight.get_editor_property('health')),
                'knightStamina': float(knight.get_editor_property('stamina')),
                'charges': int(knight.get_editor_property('healing_charges')),
                'state': str(dragon.get_editor_property('state')), 'move': str(dragon.get_editor_property('move')),
                'stateElapsed': float(dragon.get_state_elapsed()), 'stateDuration': float(dragon.get_state_duration()),
                'damageContacts': int(dragon.get_damage_contact_count()), 'swordContacts': int(dragon.get_sword_contact_count()),
                'collapseCount': int(dragon.get_collapse_count()), 'enteredEncounter': bool(knight.has_entered_encounter())}

    def live_footprints(values):
        result = []
        for f in values:
            result.append({'shape': str(f.get_editor_property('shape')),
                           'origin': xyz(f.get_editor_property('origin')), 'end': xyz(f.get_editor_property('end')),
                           'outerRadius': float(f.get_editor_property('outer_radius')),
                           'innerRadius': float(f.get_editor_property('inner_radius')),
                           'halfAngleDegrees': float(f.get_editor_property('half_angle_degrees')),
                           'damaging': bool(f.get_editor_property('damaging'))})
        return result

    def targets():
        out = {}
        for key in target_names:
            # Verified UE5.8 binding: bool + out Transform becomes Transform/None.
            value = probe.get_bone_target_world_transform(key)
            require(isinstance(value, unreal.Transform), 'Missing evaluated target: '+key)
            out[key] = transform(value)
        return out

    try:
        worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        require(len(worlds) == 1, 'Expected exactly one owned fresh PIE world')
        dragons = unreal.GameplayStatics.get_all_actors_of_class(worlds[0], unreal.VeyrDragon)
        knights = unreal.GameplayStatics.get_all_actors_of_class(worlds[0], unreal.VeyrKnight)
        require(len(dragons) == len(knights) == 1, 'Expected one native Veyr dragon and knight')
        dragon, knight = dragons[0], knights[0]
        require(not knight.has_entered_encounter(), 'Use fresh PIE before capture/replay input; no active-fight sampling')
        before = state();receipt['before'] = before
        require('IDLE' in before['state'].upper() and before['damageContacts'] == before['swordContacts'] == 0,
                'Expected untouched Idle encounter')
        definition = unreal.load_asset(definition_path)
        require(isinstance(definition, unreal.VeyrVisualDefinition), 'Definition asset unavailable')
        errors = list(definition.validate_definition(True));receipt['definitionErrors'] = [str(e) for e in errors]
        require(not errors, 'Definition validation failed')
        target_names = tuple(sorted(str(n) for n in definition.get_editor_property('bone_targets')))
        require(set(TARGETS).issubset(target_names) and len(target_names) <= 64, 'Missing/unbounded semantic target map')
        receipt['targetNames'] = list(target_names)
        require(dragon.apply_customuse_visual(definition), 'Dragon rejected definition')
        # Existing CPU-only component is a reflected UPROPERTY; do not create
        # another actor/component or sample the visible gameplay presentation.
        probes = [component for component in dragon.get_components_by_class(unreal.VeyrSkeletalPresentation)
                  if component.get_name() == 'HiddenAttackEnvelopeProbe']
        require(len(probes) == 1, 'Expected one owned hidden attack-envelope component')
        probe = probes[0]
        require(isinstance(probe, unreal.VeyrSkeletalPresentation), 'Hidden native probe binding unavailable')
        receipt['probe'] = probe.get_path_name()
        receipt['sourceSHA256'] = str(definition.get_editor_property('source_sha256'))
        require(expected_source_sha256 is None or receipt['sourceSHA256'] == expected_source_sha256,
                'Loaded definition source differs from successful import receipt')
        receipt['importedCombatDiagnostic'] = str(dragon.get_editor_property('imported_combat_diagnostic'))
        require('cached' in receipt['importedCombatDiagnostic'].lower(), 'Runtime attack envelope cache did not initialize')
        capsule_component = knight.get_editor_property('capsule_component')
        radius = float(capsule_component.get_scaled_capsule_radius())
        half_height = float(capsule_component.get_scaled_capsule_half_height())
        receipt['knightCapsule'] = {'radius': radius, 'halfHeight': half_height}
        actor_origin = xyz(dragon.get_actor_location());forward = xyz(dragon.get_actor_forward_vector())
        right = xyz(dragon.get_actor_right_vector());up = xyz(dragon.get_actor_up_vector())
        clips = definition.get_editor_property('clips');names = {str(n): n for n in clips}
        require(1 <= len(names) <= 48, 'Unexpected/unbounded clip count')
        required = ('Idle', 'DeathDown', 'Claw0Active', 'Claw1Active', 'Stomp2Windup', 'Stomp3Windup', 'FireActive', 'BiteActive', 'TailActive')
        require(all(n in names for n in required), 'V5 independent-limb/death-down moveset is incomplete')
        per_clip = {};maximum_repeat = 0.
        for name in sorted(names):
            require(time.monotonic()-started <= max_wall_seconds, 'Bounded validation wall budget exceeded')
            rows = [];per_clip[name] = rows
            for phase in PHASES:
                require(probe.sample_clip_phase(names[name], phase), 'Native sample rejected: '+name)
                transforms = targets();points = {k: v['translation'] for k, v in transforms.items()}
                mouth_delta = [b-a for a, b in zip(points['mouth'], points['mouth_aim'])]
                mouth_length = math.sqrt(dot(mouth_delta, mouth_delta))
                require(10. <= mouth_length <= 100., 'Mouth aim length/units invalid: '+name)
                direction = [d/mouth_length for d in mouth_delta]
                local = [dot(direction, axis) for axis in (forward, right, up)]
                row = {'clip': name, 'phase': phase, 'sequenceSeconds': float(probe.get_editor_property('current_sequence_seconds')),
                       'targets': transforms, 'mouthDirection': direction, 'mouthAimDistanceCm': mouth_length,
                       'mouthYawActorDegrees': math.degrees(math.atan2(local[1], local[0])),
                       'mouthPitchActorDegrees': math.degrees(math.asin(max(-1., min(1., local[2])))),
                       **sampled_geometry(name, points, radius, half_height)}
                if phase == .5:
                    require(probe.sample_clip_phase(names[name], phase), 'Repeated native sample rejected')
                    error = difference(transforms, targets());row['repeatMaxTransformError'] = error
                    maximum_repeat = max(maximum_repeat, error)
                    require(error <= .0001, 'Native sample is not deterministic: '+name)
                receipt['samples'].append(row);rows.append(row)
        checks = receipt['checks'];checks['clipsSampled'] = len(per_clip);checks['maximumRepeatTransformError'] = maximum_repeat
        checks['independentFootMotion'] = []
        for name, moving in [('Claw0Active', 0), ('Claw1Active', 1), ('Stomp2Windup', 2), ('Stomp3Windup', 3)]:
            rows = per_clip[name]
            travel = [max(distance(r['targets'][f'foot{i}']['translation'], rows[0]['targets'][f'foot{i}']['translation']) for r in rows) for i in range(4)]
            result = {'clip': name, 'movingFoot': moving, 'maximumTravelCm': travel}
            checks['independentFootMotion'].append(result)
            require(travel[moving] >= 80., 'Selected foot did not meaningfully move: '+name)
            require(max(v for i, v in enumerate(travel) if i != moving) <= 20., 'Unrelated planted foot moved excessively: '+name)
        fire = per_clip['FireActive'];yaws = [r['mouthYawActorDegrees'] for r in fire];pitches = [r['mouthPitchActorDegrees'] for r in fire]
        checks['fireDirection'] = {'yawRange': [min(yaws), max(yaws)], 'pitchRange': [min(pitches), max(pitches)]}
        require(min(yaws) < -50 and max(yaws) > 50, 'Fire mouth does not sweep both authored sides')
        require(all(-60 < p < -5 for p in pitches), 'Fire mouth is not directed toward reachable ground')
        checks['biteMouthHeightCm'] = [dot([v-a for v, a in zip(r['targets']['mouth']['translation'], actor_origin)], up) for r in per_clip['BiteActive']]
        require(all(30 < z < 350 for z in checks['biteMouthHeightCm']), 'Bite mouth is not at knight contact height')
        receipt['liveWarningFootprints'] = live_footprints(dragon.get_warning_footprints())
        receipt['liveActiveFootprints'] = live_footprints(dragon.get_active_footprints())
        require(not receipt['liveWarningFootprints'] and not receipt['liveActiveFootprints'], 'Fresh Idle unexpectedly has live attack geometry')
        receipt['warningContainmentFailures'] = int(dragon.get_editor_property('warning_containment_failures'))
        require(receipt['warningContainmentFailures'] == 0, 'Runtime reports warning containment failure')
        receipt['after'] = state();require(receipt['after'] == before, 'Validation changed gameplay state or transforms')
        receipt['passed'] = True
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        if probe is not None:
            try:
                receipt['hiddenProbeRestoredToReference'] = bool(probe.sample_reference_pose())
                if not receipt['hiddenProbeRestoredToReference']:
                    receipt['passed'] = False;receipt['restoreError'] = 'Hidden reference pose restore failed'
            except Exception as error:
                receipt['passed'] = False;receipt['restoreError'] = str(error)
        if before is not None:
            try:
                receipt['afterFinally'] = state();receipt['gameplayStateUnchanged'] = receipt['afterFinally'] == before
                if not receipt['gameplayStateUnchanged']:
                    receipt['passed'] = False
            except Exception as error:
                receipt['passed'] = False;receipt['stateReadError'] = str(error)
        receipt['wallSeconds'] = time.monotonic()-started
        RECEIPTS.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(receipt, stream, indent=2, allow_nan=False);stream.write('\n')
        unreal.log('VEYR_NATIVE_DRAGON_VALIDATION '+str(destination)+' passed='+str(receipt['passed']))
    return receipt


def run_from_import_receipt(receipt_path, max_wall_seconds=45.):
    source = Path(receipt_path).resolve()
    if not source.is_relative_to(RECEIPTS.resolve()):
        raise ValueError('Expected a private task import receipt')
    imported = json.loads(source.read_text())
    if not imported.get('success') or not imported.get('definition'):
        raise ValueError('Import receipt is not successful')
    return run(imported['definition'], max_wall_seconds, imported.get('sourceSHA256'))
