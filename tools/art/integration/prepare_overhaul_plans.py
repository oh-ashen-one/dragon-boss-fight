#!/usr/bin/env python3
"""Additive v028 banks: source-adapted blink and corrected flight joins.
Only structural representation work runs here. All motion corrections originate
in the separate saved Blender MCP scenes. Does not activate assets in Unreal.
"""
import copy,hashlib,json,sys
from pathlib import Path
from normalize_sourced import normalize_file,GLB
from normalize_approved import canonical_body,normalize,morph_info,mesh_variant
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'Local/CustomuseAssets/Polish20261025';OUT=BASE/'overhaul-v028';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
active={c:{'path':str(BASE/f/('import-plan-'+c+'.json'))} for c,f in [('KnightB','sourced-v027b'),('DragonV3B','idle-joins')]};
for value in active.values():value['sha256']=sha(value['path'])
(OUT/'previous-active-plans.json').write_text(json.dumps(active,indent=2))
plans={};reports={}
for char in ('KnightB','DragonV3B'):
 old=json.loads(Path(active[char]['path']).read_text());plan=copy.deepcopy(old)
 plan.update(version='v028',inherit_definition='/Game/Characters/Customuse/RuntimePolish/DA_'+('Knight' if char=='KnightB' else 'Dragon'),replace_runtime_source='/Game/Characters/Customuse/'+char+('/v027/DA_KnightB' if char=='KnightB' else '/v026/DA_DragonV3B'),runtime_folder='RuntimePolish',owner_approved=False,owner_requested_revision=True,purpose='Approved improvement pass: new revision awaiting native and owner visual acceptance')
 for k in ('finalize_only','verify_pose_only','restore_editor_settings'):plan.pop(k,None)
 plan['clips']=[];plan['mesh_variants']={};rows=[]
 if char=='KnightB':
  canonical=GLB(old['rig']['file']);jobs=[('BlinkLeft',ROOT/'Local/Overhaul20261026/blink/Exports/Sourced_BlinkLeft_v1.glb'),('BlinkRight',ROOT/'Local/Overhaul20261026/blink/Exports/Sourced_BlinkRight_v1.glb')]
  for key,file in jobs:
   meta=json.loads(file.with_suffix('.json').read_text());row=normalize_file(file,canonical,OUT/'knight'/file.name,meta['fps'],meta['duration']);row.update(key=key);rows.append(row)
   variant=row['mesh_variant'];plan['mesh_variants'][variant]={'file':row['file'],'sha256':row['sha256']}
   plan['clips'].append(dict(name=key,file=row['file'],sha256=row['sha256'],mesh_variant=variant,start_seconds=0,end_seconds=-1,loop=False,gameplay_play_rate=1.15,nominal_speed_cm_per_second=0.,damage_windows=[],impact_seconds=-1.,weapon_file='BoatGreatsword_OneHand_v4.glb',root_motion_policy='preserve',root_motion_removed=True,root_sample_rate=row['rootSampleRate'],root_translation_samples_cm=row['rootTranslationSamplesCm'],root_yaw_samples_degrees=[],source_duration=row['duration'],approved_source_file=file.name,approved_source_sha256=row['sourceSHA256']))
 else:
  m=json.loads((BASE/'manifest.json').read_text());canonical=GLB(m['canonicalSources']['dragon']['file']);native=GLB(old['rig']['file']);catalog={x['name']:x for x in old['integration_notes']['morph_union']};union=[];seen=set()
  for info in morph_info(native):
   entry=catalog[info['key'][0]];info.update(key=(entry['sourceName'],entry['deltaHash']),name=entry['name']);union.append(info);seen.add(info['key'])
  jobs=[('FlightWindup',ROOT/'Local/Overhaul20261026/flight-r2/Dragon_Takeoff_DangleJoin_v2.glb',False),('FlightActive',ROOT/'Local/Blender/dangle-20261025/Dragon_FlyHover_Blender_dangle_v2.glb',True),('FlightRecovery',ROOT/'Local/Overhaul20261026/flight-r2/Dragon_Land_DangleJoin_v2.glb',False)]
  for _,file,_ in jobs:
   for info in morph_info(GLB(file)):
    if info['key'] not in seen:info['name']=info['key'][0]+'_'+info['key'][1][:10];union.append(info);seen.add(info['key'])
  for key,file,loop in jobs:
   src=GLB(file);row=normalize(src,canonical_body(canonical,'dragon',union,src),'dragon',union,OUT/'dragon'/file.name);row.update(key=key);rows.append(row)
   variant='dragon_'+mesh_variant(GLB(row['file']))[:16];row['mesh_variant']=variant;plan['mesh_variants'][variant]={'file':row['file'],'sha256':row['sha256']}
   oldclip=next(c for c in old['clips'] if c['name']==key);c=copy.deepcopy(oldclip)
   c.update(name=key,file=row['file'],sha256=row['sha256'],mesh_variant=variant,start_seconds=0,end_seconds=-1,loop=loop,root_motion_removed=row['bRootMotionRemoved'],root_sample_rate=row['rootSampleRate'],root_translation_samples_cm=row['rootTranslationSamplesCm'],root_yaw_samples_degrees=row['rootYawSamplesDegrees'],source_duration=row['duration'],approved_source_file=file.name,approved_source_sha256=row['sourceSHA256']);plan['clips'].append(c)
   if key=='FlightActive':alternate=copy.deepcopy(c);alternate['name']='FlightHoverAlternate';plan['clips'].append(alternate)
  plan['expected_morph_target_count']=len(union);plan['required_morph_targets']=[x['name'] for x in union]
  plan['rig']={k:rows[0][k] for k in ('file','sha256')};plan['canonical_mesh_variant']=rows[0]['mesh_variant']
 # Inherit all unaffected clips by reference; only these keys are imported.
 path=OUT/('import-plan-'+char+'.json');path.write_text(json.dumps(plan,indent=2)+'\n');plans[char]={'path':str(path),'sha256':sha(path)};reports[char]=rows
sys.path.insert(0,str(ROOT/'tools/unreal'));import import_customuse as imp
for char,item in plans.items():
 plan=json.loads(Path(item['path']).read_text());canon=imp.inspect_glb(plan['rig'])
 for c in plan['clips']:imp.compatible(canon,imp.inspect_glb(c))
 print(char,'compatible',len(plan['clips']))
(OUT/'normalized-report.json').write_text(json.dumps(reports,indent=2)+'\n')
(OUT/'proposed-active-plans.json').write_text(json.dumps(plans,indent=2)+'\n')
print('PREPARED',OUT)
