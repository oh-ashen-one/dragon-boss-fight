#!/usr/bin/env python3
"""Add the licensed consume candidate to an unactivated versioned import plan."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB
from graft_canonical_animation import graft
from import_customuse import inspect_glb,compatible
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--export-name',default='Quaternius_Heal_v4');p.add_argument('--only-heal',action='store_true');p.add_argument('--export-file',type=Path);p.add_argument('--weapon-key');a=p.parse_args()
assert a.export_name.replace('_','').isalnum()
plan=json.loads(a.plan.read_text());weapon_key=a.weapon_key or (plan['clips'][0]['weapon_file'] if plan['clips'] else None);assert weapon_key in plan.get('existing_props',{}) or weapon_key in plan.get('props',{}),'Explicit existing weapon key required';assert all(c['name']!='HealSourced' for c in plan['clips'])
source=a.export_file.resolve() if a.export_file else ROOT/'Local/AttackSources20261102/QuaterniusRetarget/Exports'/f'{a.export_name}.glb'
assert source.is_relative_to(ROOT/'Local')
fit=json.loads(source.with_suffix('.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==fit['sha256']
canonical=Path(plan['rig']['file']);assert hashlib.sha256(canonical.read_bytes()).hexdigest()==plan['rig']['sha256']
folder=a.plan.parent;normalized=folder/'intermediate'/source.name
normal=normalize_file(source,SourceGLB(canonical),normalized,120)
output=folder/'knight'/source.name;proof=graft(canonical,normalized,output)
entry={'file':str(output.resolve()),'sha256':proof['outputSHA256']};compatible(inspect_glb(plan['rig']),inspect_glb(entry))
assert abs(proof['durationSeconds']-2.4)<1e-4
clip=dict(name='HealSourced',**entry,mesh_variant=plan['canonical_mesh_variant'],start_seconds=0.,end_seconds=proof['durationSeconds'],loop=False,
          gameplay_play_rate=1.,nominal_speed_cm_per_second=0.,damage_windows=[],impact_seconds=-1.,weapon_file=weapon_key,
          root_motion_policy='preserve',root_motion_removed=False,root_sample_rate=120.,root_translation_samples_cm=[],root_yaw_samples_degrees=[],
          source_duration=proof['durationSeconds'],approved_source_file=source.name,approved_source_sha256=fit['sha256'])
plan['clips']=[clip] if a.only_heal else plan['clips']+[clip]
plan['required_clips']=sorted(set(plan['required_clips'])|{'HealSourced'})
a.plan.write_text(json.dumps(plan,indent=2)+'\n')
(folder/'heal-preparation.json').write_text(json.dumps({'source':str(source),'fit':fit,'normalization':normal,'graft':proof,'status':'Default-off native comparison candidate; no quality approval'},indent=2)+'\n')
print('Prepared sourced heal on canonical geometry; unchanged 2.4 second duration')
