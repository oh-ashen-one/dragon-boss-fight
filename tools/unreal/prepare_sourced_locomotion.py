#!/usr/bin/env python3
"""Prepare three sourced locomotion clips on immutable canonical knight geometry.

The loop factors only linear cycle travel, retaining its in-place hip sway. Stops
retain their measured root profiles. Does not change the active native definition.
"""
import json,hashlib,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import inspect_glb,compatible
BASE=ROOT/'Local/CustomuseAssets/Polish20261025/knight-v039mixamo/import-plan-KnightB.json';OUT=ROOT/'Local/CustomuseAssets/Polish20261025/knight-v040locomotion'
def main():
 assert not OUT.exists(),'Preserve existing preparation; use a new version'
 base=json.loads(BASE.read_text());canonical=Path(base['rig']['file']);assert hashlib.sha256(canonical.read_bytes()).hexdigest()==base['rig']['sha256']
 body=GLB(canonical);vertices=np.concatenate([body.accessor(p['attributes']['POSITION']) for m in body.json['meshes'] for p in m['primitives']]);native_scale=base['target_height_cm']/(float(np.ptp(vertices[:,1]))*100)
 sources=[('RunTwoHandSourced',ROOT/'Local/AttackSources20261103/ForwardRun/Exports/Mixamo_ForwardRun_v1.glb',True),('RunStopOneHandSourced',ROOT/'Local/AttackSources20261103/LocomotionContacts/Mixamo_RunStopOneHand_v2contacts.glb',False),('RunStopTwoHandSourced',ROOT/'Local/AttackSources20261103/LocomotionContacts/Mixamo_RunStopTwoHand_v3composed.glb',False)]
 plan={k:v for k,v in base.items() if k!='clips'};plan.update(version='v040locomotion',inherit_definition='/Game/Characters/Customuse/KnightB/v039mixamo/DA_KnightB',replace_runtime_source='/Game/Characters/Customuse/KnightB/v039mixamo/DA_KnightB',owner_approved=False,owner_requested_revision=True,purpose='Sourced forward two-hand run and both-grip stops; candidate only, runtime foot/transition and blind gates pending',clips=[])
 for key,source,loop in sources:
  fit=json.loads(source.with_suffix('.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==fit['sha256'];raw=SourceGLB(source);duration=raw.duration()
  normal=normalize_file(source,SourceGLB(canonical),OUT/'intermediate'/source.name,120,duration,False,loop)
  target=OUT/'knight'/source.name;proof=graft(canonical,OUT/'intermediate'/source.name,target);entry={'file':str(target),'sha256':proof['outputSHA256']};compatible(inspect_glb(base['rig']),inspect_glb(entry))
  nominal=float(np.linalg.norm(np.array(normal['rootTranslationSamplesCm'][-1])[:2])*native_scale/duration) if loop else 0.
  if loop:assert 100<nominal<900,'Implausible measured sprint cycle speed'
  plan['clips'].append(dict(name=key,**entry,mesh_variant=base['canonical_mesh_variant'],start_seconds=0.,end_seconds=duration,loop=loop,gameplay_play_rate=1.,nominal_speed_cm_per_second=nominal,damage_windows=[],impact_seconds=-1.,weapon_file=base['clips'][0]['weapon_file'],root_motion_policy='preserve',root_motion_removed=True,root_motion_vertical=False,root_sample_rate=normal['rootSampleRate'],root_translation_samples_cm=normal['rootTranslationSamplesCm'],root_yaw_samples_degrees=[],source_duration=duration,approved_source_file=source.name,approved_source_sha256=fit['sha256']))
  (OUT/('preparation-'+key+'.json')).write_text(json.dumps({'normalization':normal,'graft':proof,'nominalSpeedCmS':nominal,'accepted':False},indent=2)+'\n');print(key,'prepared; duration',round(duration,3),'nominal cm/s',round(nominal,2),flush=True)
 plan['required_clips']=sorted(set(base['required_clips'])|{x[0] for x in sources});(OUT/'import-plan-KnightB.json').write_text(json.dumps(plan,indent=2)+'\n')
if __name__=='__main__':main()
