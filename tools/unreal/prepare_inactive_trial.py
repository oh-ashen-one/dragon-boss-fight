#!/usr/bin/env python3
"""Derive a provenance-checked inactive import job; preserve diagnostic plan.

The native operation cannot activate RuntimePolish or replace its manifest.
Only actual, hash-verified Blender sources qualify; CPU-only diagnostics remain
blocked by import_customuse. This does not grant visual or gameplay acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import import_customuse

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--prepared-plan',type=Path,required=True)
p.add_argument('--proof-directory',type=Path,required=True)
p.add_argument('--report-directory',type=Path,required=True)
p.add_argument('--job',type=Path,required=True)
a=p.parse_args()
prepared=a.prepared_plan.resolve(strict=True);proofdir=a.proof_directory.resolve(strict=True)
out=a.report_directory.resolve();jobpath=a.job.resolve();trial=prepared.with_name('inactive-trial-plan-KnightB.json')
assert all(path.is_relative_to(ROOT/'Local') for path in [prepared,proofdir,out,jobpath])
assert not trial.exists() and not out.exists() and not jobpath.exists()
original=prepared.read_bytes();plan=json.loads(original)
assert plan['character']=='KnightB' and plan.get('diagnostic_only') and not plan.get('owner_approved')
assert not (ROOT/'Unreal/Veyr/Content/Characters/Customuse/KnightB'/plan['version']).exists(), 'Preserve an existing native version'
plan.update(diagnostic_only=False,native_trial_only=True,defer_runtime_updates=True,
    prepared_diagnostic_plan_sha256=hashlib.sha256(original).hexdigest(),
    purpose='Inactive Blender-authored controller trial only; source contact failures and native/visual/Opus gates remain open')
plan['blender_trial_sources']=[{'name':clip['name'],'metadata':str((proofdir/Path(clip['approved_source_file']).with_suffix('.json')).relative_to(ROOT))} for clip in plan['clips']]
verified=import_customuse.validate_native_trial_sources(plan)
trial.write_text(json.dumps(plan,indent=2)+'\n')
manifest=ROOT/'Local/CustomuseAssets/Polish20261025/active-plans.json'
runtime=ROOT/'Unreal/Veyr/Content/Characters/Customuse/RuntimePolish/DA_Knight.uasset'
job={'plan':str(trial),'planSHA256':hashlib.sha256(trial.read_bytes()).hexdigest(),
    'activeManifestSHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
    'runtimeAssetSHA256':hashlib.sha256(runtime.read_bytes()).hexdigest(),
    'reportDirectory':str(out),'operation':'import-trial','verifyCanonicalSkin':True,
    'blenderSourcesVerified':verified}
jobpath.parent.mkdir(parents=True,exist_ok=True);jobpath.write_text(json.dumps(job,indent=2)+'\n')
assert prepared.read_bytes()==original
print('Inactive native job prepared; original diagnostic plan retained; authored sources verified:',len(verified))
