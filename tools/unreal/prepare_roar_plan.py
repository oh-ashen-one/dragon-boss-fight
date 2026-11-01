#!/usr/bin/env python3
"""Prepare the owner-approved roar as an animation-only native revision."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from graft_canonical_animation import graft
from normalize_customuse_glb import GLB
from import_customuse import inspect_glb, compatible

ROOT=Path(__file__).resolve().parents[2]


def prepare(exported, source):
    base=json.loads((ROOT/'Local/CustomuseAssets/Polish20261025/pacing-v030/import-plan-DragonV3B.json').read_text())
    folder=ROOT/'Local/CustomuseAssets/Polish20261025/showcase-v031'
    if folder.exists() or (ROOT/'Unreal/Veyr/Content/Characters/Customuse/DragonV3B/v031showcase').exists():
        raise ValueError('Fresh showcase version required')
    export=json.loads(exported.with_suffix('.json').read_text())
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha!=export['sourceSHA256'] or hashlib.sha256(exported.read_bytes()).hexdigest()!=export['outputSHA256']:
        raise ValueError('Source/export changed since validation')
    canonical=Path(base['rig']['file'])
    if hashlib.sha256(canonical.read_bytes()).hexdigest()!=base['rig']['sha256']:raise ValueError('Canonical changed')
    out=folder/'dragon'/exported.name;proof=graft(canonical,exported,out)
    entry={'file':str(out),'sha256':proof['outputSHA256']};compatible(inspect_glb(base['rig']),inspect_glb(entry))
    glb=GLB(out);jaw=next(i for i,n in enumerate(glb.json['nodes']) if n.get('name')=='VeyrJaw')
    anim=glb.json['animations'][0]
    channel=next(c for c in anim['channels'] if c['target']['node']==jaw and c['target']['path']=='rotation')
    sampler=anim['samplers'][channel['sampler']];times=glb.accessor(sampler['input']).reshape(-1)
    q=glb.accessor(sampler['output']).astype(float);q/=np.linalg.norm(q,axis=1,keepdims=True)
    angles=np.degrees(2*np.arccos(np.clip(np.abs(q@q[0]),0,1)))
    if float(angles.max())<2:raise ValueError('No meaningful authored jaw opening found for roar cue')
    cue=float(times[np.flatnonzero(angles>=angles.max()*.8)[0]])
    plan={k:v for k,v in base.items() if k!='clips'}
    plan.update(version='v031showcase',replace_runtime_source='/Game/Characters/Customuse/DragonV3B/v030pacing/DA_DragonV3B')
    plan['required_clips']=sorted(set(base['required_clips'])|{'Roar'})
    plan['clips']=[dict(name='Roar',**entry,loop=False,start_seconds=0.,end_seconds=proof['durationSeconds'],
        impact_seconds=cue,source_duration=proof['durationSeconds'],root_motion_policy='preserve',
        root_motion_removed=False,root_translation_samples_cm=[],root_yaw_samples_degrees=[],root_sample_rate=24.,
        nominal_speed_cm_per_second=0.,gameplay_play_rate=1.,damage_windows=[],
        approved_source_file=source.name,approved_source_sha256=source_sha,owner_approved=True)]
    path=folder/'import-plan-DragonV3B.json';path.write_text(json.dumps(plan,indent=2)+'\n')
    receipt={'plan':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'exportProof':export,'graftProof':proof,
             'cue':{'seconds':cue,'method':'first authored jaw-rotation sample reaching 80 percent of its maximum opening','maximumDegrees':float(angles.max()),'meaning':'vocal-motion shake cue, not a hit or damage window'},
             'approval':'Owner approved roar v2 on 2026-10-28; source is reused, not regenerated',
             'status':'prepared; native import and rendered verification pending'}
    (folder/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Roar prepared; duration',proof['durationSeconds'],'measured cue',cue)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exported',type=Path);p.add_argument('source',type=Path)
    a=p.parse_args();prepare(a.exported,a.source)
