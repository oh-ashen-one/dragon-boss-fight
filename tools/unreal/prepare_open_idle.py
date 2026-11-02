#!/usr/bin/env python3
"""Normalize the Blender wing edit onto the existing dragon skin and morph union."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_approved import GLB,morph_info,canonical_body,normalize,mesh_variant
base=json.loads((ROOT/'Local/CustomuseAssets/Polish20261025/showcase-v031/import-plan-DragonV3B.json').read_text())
source=Path('/Users/midir/dragon-boss-fight/Local/idle-wings-20261102/v4/Dragon_Idle_Open_v4.glb')
raw=GLB(Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/export/Dragon_Idle_Blender_v1r3.glb'))
edited=GLB(source);canonical=GLB(Path(base['rig']['file']))
assert mesh_variant(raw)==mesh_variant(edited),'Animation-only correction must preserve original skin, geometry and materials'
union=[]
for m in morph_info(canonical):
    name=m['key'][0];union.append({**m,'name':name,'key':(name.rsplit('_',1)[0],m['key'][1])})
folder=ROOT/'Local/CustomuseAssets/Polish20261025/idle-wings-v032';assert not folder.exists();folder.mkdir()
out=folder/'dragon/Dragon_Idle_Open_v4.glb';report=normalize(edited,canonical_body(raw,'dragon',union,raw),'dragon',union,out)
variant='dragon_'+mesh_variant(GLB(out))[:16];assert variant=='dragon_4d1f533d564da478'
plan={k:v for k,v in base.items() if k!='clips'}
plan.update(version='v032wings',replace_runtime_source='/Game/Characters/Customuse/DragonV3B/v031showcase/DA_DragonV3B',owner_requested_revision=True,owner_approved=False)
plan['existing_mesh_variants']={variant:'/Game/Characters/Customuse/DragonV3B/v026/MeshVariants/dragon_4d1f533d564da478/Dragon_FlyHover_Blender_v1'}
plan['mesh_variants']={variant:{'file':str(out),'sha256':report['sha256']}}
plan['required_clips']=sorted(set(base['required_clips'])|{'IdleOpen'})
plan['clips']=[{'name':'IdleOpen','file':str(out),'sha256':report['sha256'],'mesh_variant':variant,'start_seconds':0.,'end_seconds':report['duration'],'loop':True,'gameplay_play_rate':1.,'nominal_speed_cm_per_second':0.,'damage_windows':[],'impact_seconds':-1.,'root_motion_policy':'preserve','root_motion_removed':False,'root_sample_rate':report['rootSampleRate'],'root_translation_samples_cm':report['rootTranslationSamplesCm'],'root_yaw_samples_degrees':[],'source_duration':report['duration'],'approved_source_file':source.name,'approved_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]
(folder/'import-plan-DragonV3B.json').write_text(json.dumps(plan,indent=2)+'\n');(folder/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print('Open idle prepared; native skin reused; pose/morph error',report['reconstructionMaxError'])
