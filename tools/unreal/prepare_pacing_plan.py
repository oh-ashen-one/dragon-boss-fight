#!/usr/bin/env python3
"""Prepare a fresh animation-only dragon revision; does not import or activate it."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from graft_canonical_animation import graft
from import_customuse import compatible, inspect_glb

ROOT=Path(__file__).resolve().parents[2]


def prepare(exported, source_scene, base_path, version):
    if not re.fullmatch(r'v\d{3}pacing',version):raise ValueError('Expected a fresh vNNNpacing version')
    base=json.loads(base_path.read_text())
    folder=ROOT/'Local/CustomuseAssets/Polish20261025'/('pacing-'+version.removesuffix('pacing'))
    if folder.exists():raise ValueError('Fresh plan folder required')
    if (ROOT/'Unreal/Veyr/Content/Characters/Customuse/DragonV3B'/version).exists():
        raise ValueError('Native destination exists; preserve it and choose a new version')
    canonical=Path(base['rig']['file'])
    if hashlib.sha256(canonical.read_bytes()).hexdigest()!=base['rig']['sha256']:
        raise ValueError('Canonical source changed')
    source_hash=hashlib.sha256(source_scene.read_bytes()).hexdigest()
    export_receipt=json.loads(exported.with_suffix('.json').read_text())
    if export_receipt['sourceSHA256']!=source_hash:
        raise ValueError('Export is not from the specified source scene')
    if export_receipt['outputSHA256']!=hashlib.sha256(exported.read_bytes()).hexdigest():
        raise ValueError('Export changed since pose validation')
    clip=folder/'dragon'/exported.name
    proof=graft(canonical,exported,clip)
    source={'file':str(clip),'sha256':proof['outputSHA256']}
    compatible(inspect_glb(base['rig']),inspect_glb(source))
    duration=proof['durationSeconds']
    if abs(duration-7.0)>.005:raise ValueError('Unexpected source death duration')
    plan={k:v for k,v in base.items() if k not in ('clips','mesh_variants','replace_runtime_source')}
    plan.update(version=version,reuse_inherited_rig=True,mesh_variants={},
                inherit_definition='/Game/Characters/Customuse/RuntimePolish/DA_Dragon',
                replace_runtime_source=f"/Game/Characters/Customuse/DragonV3B/{base['version']}/DA_DragonV3B",
                preserve_inherited_material_bindings=True,clips=[])
    previous_finalization=ROOT/'Local/CustomuseImports'/f"finalized-DragonV3B-{base['version']}.json"
    if previous_finalization.exists():
        existing=json.loads(previous_finalization.read_text()).get('cameraOcclusionMaterial')
        if existing:plan['existing_camera_occlusion_material']=existing
    for name,start in [('DeathFall',0.0),('DeathFallDown',2.0)]:
        plan['clips'].append(dict(name=name,**source,loop=False,start_seconds=start,end_seconds=duration,
            source_duration=duration,root_motion_policy='preserve',root_motion_removed=False,
            root_translation_samples_cm=[],root_yaw_samples_degrees=[],root_sample_rate=24.,
            nominal_speed_cm_per_second=0.,gameplay_play_rate=1.,damage_windows=[],
            approved_source_file=source_scene.name,approved_source_sha256=source_hash,
            owner_requested_revision=True,owner_approved=False))
    plan['required_clips']=sorted(set(base['required_clips'])|{'DeathFall','DeathFallDown'})
    path=folder/'import-plan-DragonV3B.json';path.write_text(json.dumps(plan,indent=2)+'\n')
    receipt={'plan':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'sourceSceneSHA256':source_hash,'exportProof':export_receipt,'graftProof':proof,
             'status':'Prepared only; native import, preserved-asset audit and rendered review pending'}
    (folder/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Prepared plan',path)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exported',type=Path);p.add_argument('source_scene',type=Path)
    p.add_argument('--base-plan',type=Path,default=ROOT/'Local/CustomuseAssets/Polish20261025/overhaul-v028/import-plan-DragonV3B.json')
    p.add_argument('--version',default='v029pacing')
    a=p.parse_args();prepare(a.exported,a.source_scene,a.base_plan,a.version)
