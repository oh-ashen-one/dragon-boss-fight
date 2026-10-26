#!/usr/bin/env python3
"""Prepare a hash-locked additive native bank, retaining the active original guard."""
import copy,hashlib,json,sys
from pathlib import Path
from normalize_sourced import ROOT,BASE,OUT,normalize_file,GLB
ART=ROOT/'Local/FabRigTesting/Exports'
OUT=ROOT/'Local/CustomuseAssets/Sourced20261025b'
JOBS=[
 ('Walk','Mixamo_Walk_v17',1.,200.,[],None),('WalkTwoHand','Mixamo_WalkTwoHand_v17',1.,200.,[],None),
 ('Run','Fab_RunOneHand_v18',1.,800.,[],None),('RunTwoHand','Fab_Run_v17',1.,800.,[],None),
 ('LightAttack','Mixamo_Attack_v17',1.6,0.,[[.45,.72]],None),
 ('Roll','Fab_Roll_v17',1/.78,0.,[],1.),('RollAttack','Sourced_RollAttack_v2',1/.78,0.,[[1.36,1.576]],1.)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 old=json.loads(BASE.read_text());canonical=GLB(old['rig']['file']);out=OUT;out.mkdir(parents=True,exist_ok=True)
 if (out/'sourced-manifest.json').exists():raise FileExistsError('Native source bank already exists; preserve it')
 plan=copy.deepcopy(old);plan.update(version='v027',inherit_definition='/Game/Characters/Customuse/RuntimePolish/DA_Knight',replace_runtime_source='/Game/Characters/Customuse/KnightB/v026/DA_KnightB',runtime_folder='RuntimePolish',owner_approved=True,purpose='Owner-selected sourced walk/run in both grips, one-hand primary slash, roll and continuous roll counter; original guard and other explicit styles inherited unchanged.')
 for key in ['finalize_only','verify_pose_only','restore_editor_settings']:plan.pop(key,None)
 plan['props']={k:v for k,v in old['props'].items() if k in ('BoatGreatsword_OneHand_v4.glb','DrinkingCup.glb')};plan['mesh_variants']={};plan['clips']=[];rows=[]
 for key,name,rate,speed,windows,prefix in JOBS:
  file=ART/(name+'.glb');meta=json.loads(file.with_suffix('.json').read_text());assert sha(file)==meta['sha256']
  row=normalize_file(file,canonical,out/'knight'/file.name,meta['fps'],prefix);rows.append({**row,'key':key,'sourceFPS':meta.get('sourceFPS',meta['fps']),'bakeFPS':meta['fps']});plan['mesh_variants'].setdefault(row['mesh_variant'],{'file':row['file'],'sha256':row['sha256']})
  plan['clips'].append({'name':key,'file':row['file'],'sha256':row['sha256'],'mesh_variant':row['mesh_variant'],'start_seconds':0,'end_seconds':-1,'loop':key in ('Walk','WalkTwoHand','Run','RunTwoHand'),'gameplay_play_rate':rate,'nominal_speed_cm_per_second':speed,'damage_windows':windows,'impact_seconds':sum(windows[0])/2 if windows else -1,'weapon_file':'BoatGreatsword_OneHand_v4.glb','root_motion_policy':'preserve','root_motion_removed':row['bRootMotionRemoved'],'root_sample_rate':row['rootSampleRate'],'root_translation_samples_cm':row['rootTranslationSamplesCm'],'root_yaw_samples_degrees':[],'source_duration':row['duration'],'approved_source_file':file.name,'approved_source_sha256':row['sourceSHA256']})
  print('NORMALIZED',key,'error',row['canonicalReconstructionMaxMatrixError'],flush=True)
 guard=next(c for c in old['clips'] if c['name']=='GuardTwoHand');plan['preserved_guard']={'source_sha256':guard['approved_source_sha256'],'normalized_sha256':guard['sha256'],'nativeSourceDefinition':'/Game/Characters/Customuse/KnightB/v026/DA_KnightB','strategy':'inherit exact existing clip/sequence/weapon references; no guard reimport'}
 plan['integration_notes']={'sourcePolicy':'Licensed downloaded motion fitted in Blender; structural normalization preserves poses and authored sword path.','sourceBodyGaits':'Mixamo walk, VanillaLoop run/roll, Mixamo slash body/cadence with fitted heavy-blade arm arc.','rollPrefixSeconds':1.,'rollGameplaySeconds':.78,'counterPrefixGameplaySeconds':.78,'sourceFrameActorRoot':'Only roll prefix planar motion extracted; swept character movement replaces constant roll drive.','guard':'Original native GuardTwoHand inherited byte-for-byte by reference.'}
 path=ROOT/'Local/CustomuseAssets/Polish20261025/sourced-v027b/import-plan-KnightB.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(plan,indent=2)+'\n')
 # Validate against the same interface used by the native importer.
 sys.path.insert(0,str(ROOT/'tools/unreal'));import import_customuse
 canon=import_customuse.inspect_glb(plan['rig'])
 for clip in plan['clips']:
  checked=import_customuse.inspect_glb(clip);import_customuse.compatible(canon,checked)
 (out/'sourced-manifest.json').write_text(json.dumps({'version':'v027','canonicalRig':plan['rig'],'clips':rows,'plan':str(path),'planSHA256':sha(path),'guard':plan['preserved_guard']},indent=2)+'\n')
 active=ROOT/'Local/CustomuseAssets/Polish20261025/active-plans.json';prior=json.loads(active.read_text());(out/'previous-active-plans.json').write_text(json.dumps(prior,indent=2)+'\n');prior['KnightB']={'path':str(path),'sha256':sha(path)};active.write_text(json.dumps(prior,indent=2)+'\n');print('PLAN_READY',path,flush=True)
if __name__=='__main__':run()
