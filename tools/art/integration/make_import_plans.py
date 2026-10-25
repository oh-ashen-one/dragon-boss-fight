#!/usr/bin/env python3
"""Build explicit fresh-version native import plans from verified structural outputs."""
import argparse,copy,importlib.util,json
import numpy as np
from pathlib import Path

def build(root:Path,legacy:Path,version:str):
 m=json.loads((root/'manifest.json').read_text());by_file={Path(c['file']).name:c for c in m['clips']};props=m['props']
 knight={
  'Idle':'IdleOneHand_Blender_v2r4.glb','IdleTwoHand':'IdleTwoHand_Blender_v2r4.glb',
  'LightAttack':'LightAttack_BlackKnightReference_Blender_v2r3.glb','LightAttackTwoHand':'LightAttackTwoHand_Compact_Blender_v2r3.glb',
  'HeavyAttack':'HeavyAttackOneHand_Blender_v4r5.glb','HeavyAttackAlternate':'HeavyAttackOneHand_Blender_v4r3.glb',
  'HeavyAttackTwoHand':'StrongAttackTwoHand_Sweep_Blender_v2r3.glb','HeavyAttackTwoHandAlternate':'StrongAttackTwoHand_Thrust_Blender_v2r4.glb',
  'LightCombo':'LightCombo_Blender_v5.glb','RollAttack':'RollAttack_Blender_v1.glb','GuardBreak':'GuardBreakStagger_Blender_v1r2.glb',
  'GuardTwoHand':'GuardReadyTwoHand_Blender_v4r4.glb','Heal':'Heal_Blender_v4.glb',
  'Walk':'WalkOneHand_Blender_v2r2.glb','WalkTwoHand':'WalkTwoHand_Blender_v6r2.glb',
  'Run':'RunOneHand_Blender_tripo_r2.glb','RunAlternate':'RunOneHand_Blender_meshy_r3.glb','RunStop':'RunStop_Blender_v1r2.glb',
  'Backpedal':'Backpedal_Blender_loop_v1r3.glb','BackpedalStep':'Backpedal_Blender_v4r5.glb',
  'BlinkLeft':'StrafeLeft_Blender_v4r2.glb','BlinkRight':'StrafeRight_Blender_v4r2.glb',
  'Stagger':'Stagger_Blender_v2r5.glb','Death':'Death_Blender_v2r3.glb','Roll':'Legacy_Roll.glb'}
 def clip(key,file,**overrides):
  c=by_file[file];entry={'name':key,'file':c['file'],'sha256':c['sha256'],'loop':c.get('loop',False),'root_motion_policy':'preserve','root_motion_removed':c['bRootMotionRemoved'],'root_sample_rate':c['rootSampleRate'],'root_translation_samples_cm':c['rootTranslationSamplesCm'],'root_yaw_samples_degrees':c['rootYawSamplesDegrees'],'source_duration':c['duration'],'approved_source_file':Path(c['sourceFile']).name,'approved_source_sha256':c['sourceSHA256'],'root_mode':c['rootMode'],'mesh_variant':c['mesh_variant']}
  sword=c.get('swordFile') or ('BoatGreatsword_OneHand_v4.glb' if c['kind']=='knight' else None)
  if sword:entry['weapon_file']=sword
  windows={'LightCombo':[[.30,.50],[.7667,1.0333],[1.60,1.9633]],'LightAttack':[[1.,1.2]],'LightAttackTwoHand':[[.35,.56]],'HeavyAttack':[[.52,.94]],'HeavyAttackAlternate':[[.52,.94]],'HeavyAttackTwoHand':[[.43,.74]],'HeavyAttackTwoHandAlternate':[[.70,.98]],'RollAttack':[[1.03,1.27]]}
  speeds={'Walk':157.8138,'WalkTwoHand':94.5496,'Run':460.4147,'RunAlternate':508.8226,'Backpedal':59.9455}
  entry['damage_windows']=windows.get(key,[]);entry['nominal_speed_cm_per_second']=speeds.get(key,0.) if c['kind']=='knight' else (215.6/c['duration'] if key=='Walk' else 0.)
  entry.update(overrides);return entry
 plans={}
 for kind,character,base in [('knight','KnightB','import-knight-v015.json'),('dragon','DragonV3B','import-dragon-v007.json')]:
  plan=copy.deepcopy(json.loads((legacy/base).read_text()));plan['version']=version;plan['root_motion_bone']='VeyrRoot';plan['props']=copy.deepcopy(props) if kind=='knight' else {}
  if kind=='knight':
   mapping=knight;plan['bones'].update(weapon_socket='WeaponSocket',cup_socket='CupSocket',weapon_grip='WeaponSocket');plan['required_bones']=list(plan['bones']);plan['clips']=[clip(k,v) for k,v in mapping.items()];rig=by_file[knight['Idle']]
  else:
   plan['bones']['gaze_neck']='bone_4';plan['required_bones']=list(plan['bones']);plan['clips']=[]
   replace={'Idle','Walk','TurnLeft','FireWindup','FireActive','FireRecovery','BiteWindup','BiteActive','BiteRecovery','FlightWindup','FlightActive','FlightRecovery'}
   for c in m['clips']:
    if c['kind']=='dragon' and c.get('legacy') and c['job'] not in replace:plan['clips'].append(clip(c['job'],Path(c['file']).name))
   plan['clips'] += [clip('TurnLeftFine','Legacy_TurnLeft.glb',loop=True),clip('TurnRightFine','Legacy_TurnRight.glb',loop=True)]
   plan['clips'] += [clip('Idle','Dragon_Idle_Blender_v1r3.glb',loop=True),clip('Walk','Dragon_Walk_Blender_v1r2.glb',loop=True),clip('TurnLeft','Dragon_Turn_Blender_v1r2.glb',loop=False),clip('FlightWindup','Dragon_Takeoff_Blender_v1.glb',loop=False),clip('FlightActive','Dragon_FlyHover_Blender_v1.glb',loop=True),clip('FlightRecovery','Dragon_Land_Blender_v1.glb',loop=False,impact_seconds=25/30),clip('FlightHoverAlternate','Dragon_FlyHover_Blender_v1r2.glb',loop=True)]
   for key,start,end in [('FireWindup',0,34/30),('FireActive',34/30,84/30),('FireRecovery',84/30,3.5)]:plan['clips'].append(clip(key,'Dragon_FireBreath_Blender_v1.glb',start_seconds=start,end_seconds=end,loop=False))
   for key,start,end in [('BiteWindup',0,.4),('BiteActive',.4,31/30),('BiteRecovery',31/30,1.8)]:plan['clips'].append(clip(key,'Dragon_Bite_Blender_v2.glb',start_seconds=start,end_seconds=end,loop=False))
   rig=by_file['Dragon_Idle_Blender_v1r3.glb']
  plan['mesh_variants']={key:{'file':v['file'],'sha256':v['sha256']} for key,v in m['mesh_variants'].items() if v['kind']==kind};plan['canonical_mesh_variant']=rig['mesh_variant']
  plan['rig']={'file':rig['file'],'sha256':rig['sha256']};plan['required_clips']=[c['name'] for c in plan['clips']];plan['integration_notes']={'motion_frame':'Unscaled mesh-local Unreal centimetres; apply component vector transform and C*M*C^-1 pivot correction. FlightZ remains authored. Root sample rate explicit and may be fractional near60.','prop_frame':'glTF original mesh-local coordinates, metres converted to UEcm by Interchange; no arbitrary rescale; attach using complete helper-bone world transform.','canonical_skeleton_source':m['canonicalSources'][kind],'morph_union':m['morphUnion'] if kind=='dragon' else []}
  path=root/('import-plan-'+character+'.json');path.write_text(json.dumps(plan,indent=2)+'\n');plans[character]=str(path)
 # Existing importer must accept the canonical skin and bounds across every clip.
 repo=Path(__file__).resolve().parents[3];sp=importlib.util.spec_from_file_location('importer',repo/'tools/unreal/import_customuse.py');imp=importlib.util.module_from_spec(sp);sp.loader.exec_module(imp);imp.SOURCE_ROOT=root
 audit=[]
 for character,path in plans.items():
  p=json.loads(Path(path).read_text());canon=imp.inspect_glb(p['rig'])
  variants={key:imp.inspect_glb(v) for key,v in p['mesh_variants'].items()}
  for v in variants.values():
   assert canon['jointNames']==v['jointNames'] and canon['jointParents']==v['jointParents']
   assert np.allclose(canon['inverseBinds'],v['inverseBinds'],rtol=0,atol=1e-4)
  for c in p['clips']:imp.compatible(variants[c['mesh_variant']],imp.inspect_glb(c))
  audit.append({'character':character,'canonicalJoints':len(canon['jointNames']),'clips':len(p['clips']),'meshVariants':len(variants),'variantAwareImportCompatibility':True,'requiresVariantAwareImport':True,'requiredProps':list(p['props'])})
 (root/'import-compatibility.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps({'plans':plans,'audit':audit},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);p.add_argument('--version',default='v025b');a=p.parse_args();build(a.root.resolve(),a.legacy.resolve(),a.version)
