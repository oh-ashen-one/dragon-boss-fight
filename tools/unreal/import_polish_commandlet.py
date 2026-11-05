"""Native CPU-only import/fidelity/activation, invoked by PythonScriptCommandlet.

The job and plan are hash-locked under this checkout's Local directory. NullRHI
is mandatory. This creates real native assets; it does not claim rendered quality.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/unreal'))
import import_customuse
import probe_approved_poses

job_path = Path(os.environ['VEYR_NATIVE_IMPORT_JOB']).resolve()
assert job_path.is_relative_to((ROOT/'Local').resolve())
job = json.loads(job_path.read_text())
plan_path = Path(job['plan']).resolve()
out = Path(job['reportDirectory']).resolve()
assert plan_path.is_relative_to((ROOT/'Local').resolve()) and out.is_relative_to((ROOT/'Local').resolve())
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == job['planSHA256']
assert Path(unreal.Paths.project_dir()).resolve() == (ROOT/'Unreal/Veyr').resolve()
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower(), 'This route must never create a renderer'
plan = json.loads(plan_path.read_text())
assert not plan.get('diagnostic_only')
plan['runtime_folder'] = 'RuntimePolish'
stage=job.get('operation','import')
assert stage in ('import','import-trial','refine-compression','verify-canonical-skin')
if plan.get('native_trial_only'):
    assert stage in ('import-trial','verify-canonical-skin') and plan.get('defer_runtime_updates')
    import_customuse.validate_native_trial_sources(plan)
else:
    assert stage!='import-trial', 'Trial operation requires a provenance-checked trial-only plan'
if stage=='refine-compression':
    plan['scale_aware_compression']=True
    plan['defer_runtime_updates']=True
if stage=='verify-canonical-skin':plan['prefer_canonical_skin']=True
manifest_path = ROOT/'Local/CustomuseAssets/Polish20261025/active-plans.json'
runtime_file = ROOT/'Unreal/Veyr/Content/Characters/Customuse/RuntimePolish/DA_Knight.uasset'
assert plan['character'] == 'KnightB', 'This job owns the knight revision only'
assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == job['activeManifestSHA256']
assert hashlib.sha256(runtime_file.read_bytes()).hexdigest() == job['runtimeAssetSHA256']
out.mkdir(parents=True, exist_ok=True)
report = {'pid': os.getpid(), 'nativeEngine': unreal.SystemLibrary.get_engine_version(),
          'project': str(ROOT/'Unreal/Veyr'), 'version': plan['version'],
          'nullRHI': True, 'renderedQualityAccepted': False, 'success': False}


def checkpoint(stage):
    report['stage'] = stage
    target = out/'result.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2)+'\n')
    temporary.replace(target)


try:
    checkpoint('loading_editor_world')
    world = unreal.EditorLoadingAndSavingUtils.load_map('/Game/Maps/VeyrArena')
    if not world:
        raise RuntimeError('Native editor world did not load for CPU pose sampling')
    if stage in ('import','import-trial'):
        checkpoint('importing')
        report['import'] = import_customuse.run(str(plan_path))
    else:
        source=unreal.load_asset(f"/Game/Characters/Customuse/KnightB/{plan['version']}/DA_KnightB")
        if not source:raise RuntimeError('Existing candidate definition is missing')
        import_customuse.verify_sourced_definition(plan,source)
    if stage!='verify-canonical-skin':
        checkpoint('finalizing')
        report['finalization'] = import_customuse.finalize_existing(plan)
    checkpoint('verifying_native_poses')
    report['poseVerification'] = probe_approved_poses.run(plan)
    assert report['poseVerification']['passed']
    if job.get('verifyCanonicalSkin') and stage!='verify-canonical-skin':
        canonical_plan=dict(plan);canonical_plan['prefer_canonical_skin']=True
        report['canonicalPoseVerification']=probe_approved_poses.run(canonical_plan)
        assert report['canonicalPoseVerification']['passed']
    if stage not in ('verify-canonical-skin','import-trial'):
        # Preserve any intervening session's manifest/runtime edits.
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == job['activeManifestSHA256']
        assert hashlib.sha256(runtime_file.read_bytes()).hexdigest() == job['runtimeAssetSHA256']
        checkpoint('activating_candidate_definition')
        runtime = import_customuse.activate_polish_plan(plan)
        report['runtimeDefinition'] = runtime.get_path_name()
        report['runtimeSourceDefinition'] = unreal.EditorAssetLibrary.get_metadata_tag(runtime, 'VeyrPolishSourceDefinition')
        assert report['runtimeSourceDefinition'] == f"/Game/Characters/Customuse/KnightB/{plan['version']}/DA_KnightB"
        original = manifest_path.read_bytes()
        (out/'previous-active-plans.json').write_bytes(original)
        manifest = json.loads(original)
        manifest['KnightB'] = {'path': str(plan_path), 'sha256': job['planSHA256']}
        temporary = manifest_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(manifest, indent=2)+'\n')
        temporary.replace(manifest_path)
    if plan.get('native_trial_only'):
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest()==job['activeManifestSHA256']
        assert hashlib.sha256(runtime_file.read_bytes()).hexdigest()==job['runtimeAssetSHA256']
        report['inactiveTrial']=True
        report['runtimeAssetAndManifestUnchanged']=True
    report['success'] = True
    checkpoint('complete')
    unreal.log('VEYR_HEADLESS_POLISH_COMPLETE')
except Exception as error:
    report['error'] = str(error)
    report['partialAssetsPreserved'] = True
    checkpoint('failed')
    raise
