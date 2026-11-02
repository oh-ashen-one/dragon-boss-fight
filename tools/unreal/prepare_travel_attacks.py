#!/usr/bin/env python3
"""Append fitted, measured locomoting attacks to a fresh knight import plan."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);a=p.parse_args();plan=json.loads(a.plan.read_text());folder=a.plan.parent
canonical=Path(plan['rig']['file']);body=GLB(canonical);vertices=np.concatenate([body.accessor(p['attributes']['POSITION']) for m in body.json['meshes'] for p in m['primitives']]);scale=plan['target_height_cm']/float(np.ptp(vertices[:,1]))
weapon=GLB(ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb');wv=np.concatenate([weapon.accessor(p['attributes']['POSITION']) for m in weapon.json['meshes'] for p in m['primitives']]);tip=wv[wv[:,1]>wv[:,1].max()-.005].mean(0)
for source_key,key,vertical in [('JumpAttack','LeapAttackSourced',True),('SlideAttack','RunningAttackSourced',False)]:
    assert all(c['name']!=key for c in plan['clips'])
    source=ROOT/f'Local/AttackSources20261102/MixamoGreatSword/Retarget/Exports/Mixamo_{source_key}_v2.glb';fit=json.loads(source.with_suffix('.json').read_text());assert hashlib.sha256(source.read_bytes()).hexdigest()==fit['sha256']
    normalized=folder/'intermediate'/source.name;normal=normalize_file(source,SourceGLB(canonical),normalized,120,fit['duration'],vertical)
    target=folder/'knight'/source.name;proof=graft(canonical,normalized,target);g=GLB(target);socket=next(i for i,n in enumerate(g.json['nodes']) if n.get('name')=='WeaponSocket');duration=proof['durationSeconds'];times=np.linspace(0,duration,round(duration*120)+1)
    points=np.array([(g.world_matrices(0,float(t))[socket]@np.r_[tip,1])[:3] for t in times]);velocity=np.gradient(points,times,axis=0);speed=np.linalg.norm(velocity,axis=1)
    # Exclude the authored entry/exit joins from finding the strike, then
    # extend the active interval through its actual fast follow-through.
    eligible=(times>=fit['intro'])&(times<=duration-fit['outro']);score=np.where(eligible&(velocity[:,2]>0),speed,0);peak=int(np.argmax(score));threshold=score[peak]*.25;low=high=peak
    while low>0 and eligible[low-1] and speed[low-1]>=threshold:low-=1
    while high<len(times)-1 and eligible[high+1] and speed[high+1]>=threshold:high+=1
    assert times[high]-times[low]>=.05
    entry=dict(name=key,file=str(target.resolve()),sha256=proof['outputSHA256'],mesh_variant=plan['canonical_mesh_variant'],start_seconds=0.,end_seconds=duration,loop=False,gameplay_play_rate=1.,nominal_speed_cm_per_second=0.,attack_reach_cm=float(max(0,points[low:high+1,2].max())*scale),damage_windows=[[float(times[low]),float(times[high])]],impact_seconds=float(times[peak]),weapon_file=plan['clips'][0]['weapon_file'],root_motion_policy='preserve',root_motion_removed=True,root_motion_vertical=vertical,root_sample_rate=normal['rootSampleRate'],root_translation_samples_cm=normal['rootTranslationSamplesCm'],root_yaw_samples_degrees=[],source_duration=duration,approved_source_file=source.name,approved_source_sha256=fit['sha256'])
    plan['clips'].append(entry);plan['required_clips']=sorted(set(plan['required_clips'])|{key})
    (folder/f'preparation-{key}.json').write_text(json.dumps({'normalization':normal,'graft':proof,'damageWindow':entry['damage_windows'],'verticalRootMethod':'Positive hip elevation above the higher standing endpoint; crouch stays in the pose' if vertical else None,'accepted':False},indent=2)+'\n');print(key,'duration',duration,'window',entry['damage_windows'])
a.plan.write_text(json.dumps(plan,indent=2)+'\n')
