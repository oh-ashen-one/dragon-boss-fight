"""Bounded owned-editor CPU/render-path pose equivalence and policy verification.

No editor launch, asset save or GPU-allocation claim. run() creates and finally
removes one transient native Dragon, comparing 43 clips at six fixed phases.
"""
from pathlib import Path
import datetime
import hashlib
import json
import math
import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'Unreal/Veyr'
PHASES = (0., .17, .37, .63, .83, .999)
TOLERANCE = 1.e-4


def _pose(component):
    result = {}
    for name, transform in component.get_evaluated_local_pose().items():
        t, q, s = transform.translation, transform.rotation, transform.scale3d
        values = (t.x, t.y, t.z, q.x, q.y, q.z, q.w, s.x, s.y, s.z)
        if not all(math.isfinite(v) for v in values):
            raise RuntimeError('Nonfinite local bone transform: ' + str(name))
        result[str(name)] = values
    if not result:
        raise RuntimeError('Empty evaluated pose')
    return result


def _policy(visible, probe):
    # Native reflected names avoid ambiguity in Python's acronym/plural spelling.
    count = int(visible.get_editor_property('SkinCacheRequestedLODCount'))
    allowed = list(visible.get_editor_property('SkinCacheAllowedLODs'))
    row = {
        'cpuPoseOnly': bool(probe.get_editor_property('bCPUPoseOnly')),
        'cpuPoseOnlyVerified': bool(probe.get_editor_property('bCPUPoseOnlyVerified')),
        'cpuHasRenderState': bool(probe.has_presentation_render_state()),
        'visibleSkinCacheRequested': bool(visible.get_editor_property('bSkinCacheRequested')),
        'visibleRequestedLODCount': count, 'visibleAllowedLODs': allowed,
        'visibleAllRequestedLODsAllowed': bool(visible.get_editor_property('bSkinCacheAllRequestedLODsAllowed')),
        'visibleHasRenderState': bool(visible.has_presentation_render_state()),
    }
    if not (row['cpuPoseOnly'] and row['cpuPoseOnlyVerified'] and not row['cpuHasRenderState']):
        raise RuntimeError('CPU probe unexpectedly has rendering state: ' + str(row))
    if not (row['visibleSkinCacheRequested'] and row['visibleAllRequestedLODsAllowed']
            and count > 0 and sorted(allowed) == list(range(count))):
        raise RuntimeError('Visible presentation not Skin Cache eligible on every requested LOD: ' + str(row))
    return row


def run():
    if Path(unreal.Paths.project_dir()).resolve() != PROJECT.resolve():
        raise RuntimeError('Render-policy probe is bound to a different project checkout')
    if unreal.EditorLevelLibrary.get_game_world() is not None:
        raise RuntimeError('Stop PIE before this transient editor-world probe')
    folder = ROOT / 'Local/CustomuseAssets/Polish20261025'
    active = json.loads((folder / 'active-plans.json').read_text())['DragonV3B']
    plan_path = Path(active['path']).resolve()
    if not plan_path.is_relative_to(folder.resolve()):
        raise RuntimeError('Active plan is outside the owned Polish folder')
    plan_bytes = plan_path.read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != active['sha256']:
        raise RuntimeError('Active Dragon plan differs from its hash lock')
    plan = json.loads(plan_bytes)
    names = sorted(clip['name'] for clip in plan['clips'])
    if plan['character'] != 'DragonV3B' or plan['version'] != 'v026' or len(set(names)) != 43 or len(names) != 43:
        raise RuntimeError('Expected exactly43 current DragonV3B v026 clips')
    definition_path = '/Game/Characters/Customuse/DragonV3B/v026/DA_DragonV3B'
    definition = unreal.load_asset(definition_path)
    if not isinstance(definition, unreal.VeyrVisualDefinition):
        raise RuntimeError('Current v026 native Dragon definition missing')
    if sorted(str(name) for name in definition.get_editor_property('clips')) != names:
        raise RuntimeError('Native definition clip keys differ from locked plan')
    out = ROOT / 'Local/CustomuseImports/render-policy-proof.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    receipt = {'schema': 1, 'createdUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'plan': str(plan_path.relative_to(ROOT)), 'planSHA256': active['sha256'],
               'definition': definition_path, 'phases': PHASES, 'tolerance': TOLERANCE,
               'scope': 'Evaluated local bones/morph curves and component render policy only; Skin Cache eligibility is not GPU allocation or raster-technique proof.',
               'samples': [], 'failures': [], 'transientActorDestroyed': False, 'passed': False}
    actor = None
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.VeyrDragon, unreal.Vector(0, 0, 0), unreal.Rotator(), True)
        if not actor:
            raise RuntimeError('Could not spawn transient registered native Dragon')
        actor.set_actor_tick_enabled(False)
        actor.set_is_temporarily_hidden_in_editor(True)
        visible = actor.get_editor_property('ImportedPresentation')
        # The pointer property is intentionally protected; use the public
        # actor component query and the verified native component name.
        matches = [c for c in actor.get_components_by_class(unreal.VeyrSkeletalPresentation)
                   if c.get_name() == 'HiddenAttackEnvelopeProbe']
        if len(matches) != 1:
            raise RuntimeError('Expected one owned HiddenAttackEnvelopeProbe component')
        probe = matches[0]
        for component in (visible, probe):
            if not component or not component.set_visual_definition(definition, False):
                raise RuntimeError('Definition application failed: ' + str(component.get_editor_property('LastError') if component else 'missing component'))
        _policy(visible, probe)
        morphs = sorted(str(name) for name in definition.get_imported_morph_target_names())
        for name in names:
            for phase in PHASES:
                for component in (visible, probe):
                    if not component.sample_clip_phase(name, phase):
                        raise RuntimeError(str(component.get_editor_property('LastError')))
                a, b = _pose(visible), _pose(probe)
                if a.keys() != b.keys():
                    raise RuntimeError('Bone key mismatch: ' + name)
                # Quaternions q and -q represent the same local rotation.
                error = max(max(max(abs(a[k][j] - b[k][j]) for j in (0, 1, 2, 7, 8, 9)),
                                min(max(abs(a[k][j] - b[k][j]) for j in range(3, 7)),
                                    max(abs(a[k][j] + b[k][j]) for j in range(3, 7)))) for k in a)
                va, pa = visible.get_anim_instance(), probe.get_anim_instance()
                curves_a = [float(va.get_curve_value(m)) for m in morphs]
                curves_b = [float(pa.get_curve_value(m)) for m in morphs]
                if not all(math.isfinite(v) for v in curves_a + curves_b):
                    raise RuntimeError('Nonfinite evaluated morph curve')
                morph_error = max((abs(x - y) for x, y in zip(curves_a, curves_b)), default=0.)
                mesh = visible.get_skeletal_mesh_asset().get_path_name()
                if mesh != probe.get_skeletal_mesh_asset().get_path_name():
                    raise RuntimeError('Visible/CPU mesh variant mismatch')
                row = {'clip': name, 'phase': phase, 'mesh': mesh, 'bones': len(a), 'morphs': len(morphs),
                       'maxLocalTransformError': error, 'maxMorphCurveError': morph_error,
                       **_policy(visible, probe)}
                receipt['samples'].append(row)
                if max(error, morph_error) > TOLERANCE:
                    raise RuntimeError('CPU/render-path pose mismatch: ' + name + ' phase=' + str(phase))
        receipt['passed'] = len(receipt['samples']) == 43 * len(PHASES)
    except Exception as exc:
        receipt['failures'].append(str(exc))
    finally:
        if actor is not None:
            try:
                receipt['transientActorDestroyed'] = bool(unreal.EditorLevelLibrary.destroy_actor(actor))
            except Exception as exc:
                receipt['failures'].append('Transient cleanup exception: ' + str(exc))
        if not receipt['transientActorDestroyed']:
            receipt['failures'].append('Transient actor was not created or cleanup failed')
        receipt['passed'] = receipt['passed'] and not receipt['failures']
        out.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    if not receipt['passed']:
        raise RuntimeError('Render-policy verification failed; inspect ' + str(out))
    return {'passed': True, 'samples': len(receipt['samples']), 'report': str(out),
            'scope': receipt['scope'], 'transientActorDestroyed': True}
