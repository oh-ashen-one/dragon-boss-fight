#!/usr/bin/env python3
"""Fresh complete v026 plans; retain old runtime keys and override requested art."""
from __future__ import annotations
import argparse,copy,importlib.util,json
from pathlib import Path
import numpy as np
from normalize_polish import ROOT,DEFAULT_BASE,DEFAULT_OUT

def build(root:Path,base:Path,version='v026'):
    root=root.resolve();base=base.resolve();m=json.loads((root/'manifest.json').read_text())
    baseline={str(Path(c['baselineNormalizedFile']).resolve()):c for c in m['clips'] if c.get('baselineNormalizedFile')}
    replacements={key:c for c in m['clips'] if c.get('ownerRequestedRevision') for key in c['runtimeKeys']}
    def entry(key,row,previous=None):
        e=copy.deepcopy(previous or {});new=row.get('ownerRequestedRevision',False)
        if new:
            for field in ['start_seconds','end_seconds','impact_seconds']:e.pop(field,None)
            e.update(start_seconds=0,end_seconds=-1,loop=row['loop'])
        e.update(name=key,file=row['file'],sha256=row['sha256'],root_motion_policy='preserve',root_motion_removed=row['bRootMotionRemoved'],root_sample_rate=row['rootSampleRate'],root_translation_samples_cm=row['rootTranslationSamplesCm'],root_yaw_samples_degrees=row['rootYawSamplesDegrees'],source_duration=row['duration'],approved_source_file=Path(row['sourceFile']).name,approved_source_sha256=row['sourceSHA256'],root_mode=row['rootMode'],mesh_variant=row['mesh_variant'],owner_requested_revision=new)
        if new:
            e['owner_approved']=False
            art=row['blenderCandidate']
            e['gameplay_play_rate']=1.0
            e['nominal_speed_cm_per_second']=art.get('nominal_speed_cm_per_second',0.0)
            e['damage_windows']=art.get('damage_windows',[])
            if art.get('impact_seconds') is not None:e['impact_seconds']=art['impact_seconds']
            if art.get('weapon_file'):e['weapon_file']=art['weapon_file']
        e.setdefault('gameplay_play_rate',3.0 if key=='LightAttack' else 1.0)
        e.setdefault('damage_windows',[]);e.setdefault('nominal_speed_cm_per_second',0.0)
        return e
    plans={};retention=[]
    for character,kind in [('KnightB','knight'),('DragonV3B','dragon')]:
        old=json.loads((base/('import-plan-'+character+'.json')).read_text());plan=copy.deepcopy(old)
        for field in ['finalize_only','verify_pose_only','restore_editor_settings']:plan.pop(field,None)
        plan.update(version=version,owner_requested_revision=True,owner_approved=False)
        plan['purpose']='Complete baseline moveset plus independently critiqued owner-requested Blender animation corrections; native acceptance pending.'
        clips=[];keys=set()
        for previous in old['clips']:
            key=previous['name'];row=replacements.get(key) or baseline[str(Path(previous['file']).resolve())]
            clips.append(entry(key,row,previous));keys.add(key)
            retention.append({'character':character,'key':key,'revised':bool(row.get('ownerRequestedRevision')),'oldSourceSHA256':previous.get('approved_source_sha256'),'newSourceSHA256':row['sourceSHA256']})
        for key,row in replacements.items():
            if row['kind']==kind and key not in keys:clips.append(entry(key,row));keys.add(key)
        canonical=baseline[str(Path(old['rig']['file']).resolve())]
        needed_variants={c['mesh_variant'] for c in clips}|{canonical['mesh_variant']}
        plan['clips']=clips;plan['required_clips']=[c['name'] for c in clips]
        plan['rig']={k:canonical[k] for k in ['file','sha256']};plan['canonical_mesh_variant']=canonical['mesh_variant']
        plan['mesh_variants']={key:{k:m['mesh_variants'][key][k] for k in ['file','sha256']} for key in sorted(needed_variants)}
        plan['props']=m['props'] if kind=='knight' else {}
        plan['expected_morph_target_count']=len(m['morphUnion']) if kind=='dragon' else 0
        plan['required_morph_targets']=[x['name'] for x in m['morphUnion']] if kind=='dragon' else []
        plan['integration_notes']={**old.get('integration_notes',{}),'canonical_skeleton_source':m['canonicalSources'][kind],'morph_union':m['morphUnion'] if kind=='dragon' else [],'source_policy':m['sourcePolicy'],'roll_prefix':'RollAttack counter root identity through.78s on150Hz grid; normalized same-actor prefix audited against Roll.','new_knight_props':'New RunTwoHand/GripTo*/Roll/RollAttack use intact BoatGreatsword_OneHand_v4.glb.','flight_join':'Both hover runtime aliases use the corrected hover; PolishHoverBreath and every prior delta identity retained.','ground_idle_boundary':'Takeoff and landing include Blender-authored PolishIdleEndpoint corrective and exact Idle_r3 f0 ground pose; all four surface joins are audited.','acceptance':'Owner-requested revision; independent Blender readiness only. Native gameplay and owner acceptance separate.'}
        target=root/('import-plan-'+character+'.json');target.write_text(json.dumps(plan,indent=2)+'\n');plans[character]=str(target)
    spec=importlib.util.spec_from_file_location('polish_import_interface',ROOT/'tools/unreal/import_customuse.py');imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)
    audit=[]
    for character,path in plans.items():
        p=json.loads(Path(path).read_text());canon=imp.inspect_glb(p['rig']);variants={k:imp.inspect_glb(v) for k,v in p['mesh_variants'].items()}
        for v in variants.values():
            assert canon['jointNames']==v['jointNames'] and canon['jointParents']==v['jointParents']
            assert np.allclose(canon['inverseBinds'],v['inverseBinds'],rtol=0,atol=1e-4)
        for c in p['clips']:imp.compatible(variants[c['mesh_variant']],imp.inspect_glb(c))
        audit.append({'character':character,'version':version,'canonicalJoints':len(canon['jointNames']),'clips':len(p['clips']),'meshVariants':len(variants),'expectedMorphTargets':p['expected_morph_target_count'],'importInterfaceCompatible':True})
    for row in retention:
        if not row['revised']:assert row['oldSourceSHA256']==row['newSourceSHA256'],row
    result={'plans':plans,'compatibility':audit,'baselineRuntimeKeyRetention':retention,'allBaselineKeysRetained':True}
    (root/'import-compatibility.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'plans':plans,'compatibility':audit},indent=2));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=DEFAULT_OUT);p.add_argument('--base',type=Path,default=DEFAULT_BASE);p.add_argument('--version',default='v026');a=p.parse_args();build(a.root,a.base,a.version)
