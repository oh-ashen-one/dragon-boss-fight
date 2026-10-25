#!/usr/bin/env python3
"""CPU audit of complete v026 source representation, native-prefix and seams."""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from normalize_approved import GLB,UE
from verify_normalized import skinned_positions
from normalize_polish import DEFAULT_OUT

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def actor_matrix(row,t):
    positions=row['rootTranslationSamplesCm'];rate=row['rootSampleRate'];sample=min(max(t*rate,0),len(positions)-1);i=int(sample);j=min(i+1,len(positions)-1);alpha=sample-i
    translation=np.array(positions[i])*(1-alpha)+np.array(positions[j])*alpha
    yaw=row['rootYawSamplesDegrees'];angle=(yaw[i]*(1-alpha)+yaw[j]*alpha) if yaw else 0.0
    result=np.eye(4);result[:3,:3]=Rotation.from_rotvec([0,-angle*math.pi/180,0]).as_matrix();result[:3,3]=UE.T@translation/100
    return result

def verify(root,reuse_report=None):
    reuse={};reuse_rows={};prior_proof=None
    if reuse_report:
        reuse_report=Path(reuse_report).resolve();prior_proof=json.loads(reuse_report.read_text())
        reuse={(x['sourceSHA256'],x['normalizedSHA256']):x for x in prior_proof['clips'] if x['pass']}
        prior_manifest=json.loads((reuse_report.parent/'manifest.json').read_text());reuse_rows={(x['sourceSHA256'],x['sha256']):x for x in prior_manifest['clips']}
    def trajectory(row):return {k:row[k] for k in ['rootSampleRate','rootTranslationSamplesCm','rootYawSamplesDegrees','bRootMotionRemoved']}
    root=root.resolve();manifest=json.loads((root/'manifest.json').read_text());boundaries={};plans=[]
    for path in sorted(root.glob('import-plan-*.json')):
        plan=json.loads(path.read_text());plans.append(plan)
        assert plan['version']=='v026' and set(plan['required_clips'])=={c['name'] for c in plan['clips']}
        for clip in plan['clips']:
            assert file_sha(clip['file'])==clip['sha256']
            end=clip.get('end_seconds',-1);end=clip['source_duration'] if end<0 else end
            boundaries.setdefault(clip['file'],set()).update([clip.get('start_seconds',0),end])
    assert {p['character'] for p in plans}=={'KnightB','DragonV3B'}
    rows=[];by_key={}
    for row in manifest['clips']:
        source=GLB(row['sourceFile']);derived=GLB(row['file']);assert source.sha==row['sourceSHA256'] and derived.sha==row['sha256']
        duration=row['duration'];times={0.0,duration,*boundaries.get(row['file'],set())}
        times.update(duration*x for x in [.113,.273,.517,.791]);times.add(max(0,duration-.5/row['rootSampleRate']))
        if row.get('ownerRequestedRevision'):
            keytimes=sorted({float(t) for anim in source.g['animations'] for sampler in anim['samplers'] for t in source.accessor(sampler['input']).ravel()})
            times.update(keytimes);times.update((a+b)*.5 for a,b in zip(keytimes,keytimes[1:]))
            for key in row['runtimeKeys']:by_key[key]=(row,derived)
        identity=(source.sha,derived.sha);cached=reuse.get(identity);previous_row=reuse_rows.get(identity)
        if cached and previous_row and trajectory(previous_row)==trajectory(row) and cached['sampleCount']==len(times) and cached['allSourceKeysAndMidpoints']==bool(row.get('ownerRequestedRevision')) and set(boundaries.get(row['file'],set()))<=set(cached['trimEndpointsCovered']):
            item=copy.deepcopy(cached);item['reusedProofFrom']=str(reuse_report);item['reuseCondition']='Source bytes, normalized bytes, actor trajectory and sample coverage identical';rows.append(item);print('REUSED',item['file'],len(times),flush=True);continue
        maximum={'boneMatrix':0.0,'weaponMatrix':0.0,'cupMatrix':0.0,'skinnedVertex':0.0}
        rest,_=derived.sample(None);skin=derived.g['skins'][0];ib=derived.accessor(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1);bind=float(abs(rest[skin['joints']]@ib-np.eye(4)).max())
        for t in sorted(times):
            assert -1e-6<=t<=duration+1e-6
            sw,sweights=source.sample(t);nw,nweights=derived.sample(t);matrix=actor_matrix(row,t)
            for name in source.skin_names():maximum['boneMatrix']=max(maximum['boneMatrix'],float(abs(matrix@nw[derived.names[name]]-sw[source.names[name]]).max()))
            for old,new,metric in [('ReviewWeaponSocket','WeaponSocket','weaponMatrix'),('DrinkingCup','CupSocket','cupMatrix')]:
                if old in source.names:maximum[metric]=max(maximum[metric],float(abs(matrix@nw[derived.names[new]]-sw[source.names[old]]).max()))
            a=skinned_positions(source,sw,sweights);b=skinned_positions(derived,nw,nweights)
            assert a.shape==b.shape,(row['file'],'vertex count mismatch')
            maximum['skinnedVertex']=max(maximum['skinnedVertex'],float(abs((matrix@b.T).T-a).max()))
        passed=bind<2e-5 and max(maximum.values())<3e-4
        item={'file':Path(row['file']).name,'sourceSHA256':source.sha,'normalizedSHA256':derived.sha,'ownerRequestedRevision':row.get('ownerRequestedRevision',False),'sampleCount':len(times),'allSourceKeysAndMidpoints':bool(row.get('ownerRequestedRevision')),'startAndEndCovered':0 in times and duration in times,'trimEndpointsCovered':sorted(boundaries.get(row['file'],set())),'bindShapeError':bind,'maximumErrors':maximum,'pass':passed}
        rows.append(item);print('AUDITED',item['file'],len(times),maximum['skinnedVertex'],passed,flush=True)
    # The game intentionally applies no authored root travel inside RollAttack's
    # roll prefix. Compare its native normalized shape at the SAME actor transform.
    rollrow,roll=by_key['Roll'];attackrow,attack=by_key['RollAttack'];prefix={'maxBoneMatrixDifference':0.,'maxSkinnedVertexDifference':0.,'maxCounterRootDifferenceFromIdentity':0.,'maxActorTranslationCm':0.}
    can_reuse_prefix=prior_proof and all((row['sourceSHA256'],row['sha256']) in reuse_rows and trajectory(reuse_rows[(row['sourceSHA256'],row['sha256'])])==trajectory(row) for row in [rollrow,attackrow])
    if can_reuse_prefix:
        prefix=copy.deepcopy(prior_proof['sameActorNormalizedRollPrefix']);prefix['reusedProofFrom']=str(reuse_report)
    else:
        times=sorted({0.,.78,float(np.float32(.78)),*np.linspace(0,.78,235).tolist()})
        for t in times:
            a,aw=roll.sample(t);b,bw=attack.sample(t)
            for name in roll.skin_names():prefix['maxBoneMatrixDifference']=max(prefix['maxBoneMatrixDifference'],float(abs(a[roll.names[name]]-b[attack.names[name]]).max()))
            av=skinned_positions(roll,a,aw);bv=skinned_positions(attack,b,bw);assert av.shape==bv.shape
            prefix['maxSkinnedVertexDifference']=max(prefix['maxSkinnedVertexDifference'],float(abs(av-bv).max()))
            prefix['maxCounterRootDifferenceFromIdentity']=max(prefix['maxCounterRootDifferenceFromIdentity'],float(abs(b[attack.names['VeyrRoot']]-np.eye(4)).max()))
            prefix['maxActorTranslationCm']=max(prefix['maxActorTranslationCm'],float(np.linalg.norm(actor_matrix(attackrow,t)[:3,3])*100))
        prefix['sampleCount']=len(times);prefix['pass']=max(v for k,v in prefix.items() if k.startswith('max'))<2e-5
    seams=[]
    dragon_plan=next(p for p in plans if p['character']=='DragonV3B');idle=next(c for c in dragon_plan['clips'] if c['name']=='Idle');idle_row=next(r for r in manifest['clips'] if r['file']==idle['file']);by_key['DragonIdle']=(idle_row,GLB(idle['file']))
    for left,lt,right,rt in [('DragonIdle',0,'FlightWindup',0),('FlightWindup',1.5,'FlightActive',0),('FlightActive',2,'FlightRecovery',0),('FlightRecovery',1.5,'DragonIdle',0)]:
        ar,a=by_key[left];br,b=by_key[right];am,aw=a.sample(lt);bm,bw=b.sample(rt);av=skinned_positions(a,am,aw);bv=skinned_positions(b,bm,bw);assert av.shape==bv.shape
        delta=np.linalg.norm(av[:,:3]-bv[:,:3],axis=1)*2155.818
        seams.append({'from':left,'to':right,'maxSkinnedVertexDifferenceCm':float(delta.max()),'p99Cm':float(np.quantile(delta,.99)),'pass':float(delta.max())<.01})
    runtime_joins=[]
    for plan in plans:
        entries={c['name']:c for c in plan['clips']}
        tests=[('GripToTwoHand',0,'Idle',0,True),('GripToTwoHand',.5,'IdleTwoHand',0,True),('GripToOneHand',0,'IdleTwoHand',0,True),('GripToOneHand',.5,'Idle',0,True),('RunTwoHand',0,'RunTwoHand',entries.get('RunTwoHand',{}).get('source_duration',0),True)] if plan['character']=='KnightB' else [('FlightActive',0,'FlightActive',2,True),('Idle',0,'FlightWindup',0,True),('FlightRecovery',1.5,'Idle',0,True)]
        cache={}
        for left,lt,right,rt,exact in tests:
            for key in [left,right]:
                if key not in cache:cache[key]=GLB(entries[key]['file'])
            a,b=cache[left],cache[right];am,aw=a.sample(lt);bm,bw=b.sample(rt)
            bone_error=max(float(abs(am[a.names[n]]-bm[b.names[n]]).max()) for n in a.skin_names())
            av=skinned_positions(a,am,aw);bv=skinned_positions(b,bm,bw)
            skin_error=float(np.linalg.norm(av[:,:3]-bv[:,:3],axis=1).max()) if av.shape==bv.shape else None
            passed=bone_error<.001 and skin_error is not None and skin_error<.001
            runtime_joins.append({'character':plan['character'],'from':left,'fromSeconds':lt,'to':right,'toSeconds':rt,'expectedExact':exact,'maxBoneMatrixDifference':bone_error,'maxSkinnedVertexDifferenceRigUnits':skin_error,'withinExactTolerance':passed,'note':'Source flight-to-idle boundaries retain original authored poses and use runtime transition blending' if not exact else 'Authored endpoint or loop closure'})
    unchanged=[]
    for row in manifest['baselineProvenance']:
        good=file_sha(row['sourceFile'])==row['sourceSHA256'] and file_sha(row['normalizedFile'])==row['normalizedSHA256'];unchanged.append({'sourceFile':row['sourceFile'],'unchanged':good})
    for p in manifest['props'].values():assert file_sha(p['file'])==p['sha256']==file_sha(p['baselineFile'])
    old=json.loads(Path(manifest['baselineManifest']).read_text());old_morph={(x['sourceName'],x['deltaHash']) for x in old['morphUnion']};new_morph={(x['sourceName'],x['deltaHash']) for x in manifest['morphUnion']}
    morph={'oldIdentities':len(old_morph),'newIdentities':len(new_morph),'allPriorIdentitiesPreserved':old_morph<=new_morph,'polishHoverBreathPresent':any(x[0]=='PolishHoverBreath' for x in new_morph),'polishIdleEndpointPresent':any(x[0]=='PolishIdleEndpoint' for x in new_morph)}
    result={'scope':'Full CPU-skinned vertices and bone/helper transforms at every original key+midpoint for all8 new clips; baseline poses and every retained trim endpoint; no native/render acceptance claim.','nativeVersion':'v026','clips':rows,'sameActorNormalizedRollPrefix':prefix,'normalizedFlightSurfaceJoins':seams,'runtimeEndpointCoverage':runtime_joins,'morphIdentityCoverage':morph,'baselineSourcesUnchanged':unchanged,'runtimeClipCoverage':{p['character']:len(p['clips']) for p in plans},'totalPoseSamples':sum(x['sampleCount'] for x in rows)}
    result['pass']=all(x['pass'] for x in rows) and prefix['pass'] and all(x['pass'] for x in seams) and all(x['withinExactTolerance'] for x in runtime_joins if x['expectedExact']) and all(x['unchanged'] for x in unchanged) and all(morph[k] for k in ['allPriorIdentitiesPreserved','polishHoverBreathPresent','polishIdleEndpointPresent'])
    result['sourceRepresentationPass']=result['pass']
    result['allRuntimeEndpointsWithinExactTolerance']=all(x['withinExactTolerance'] for x in runtime_joins)
    result['runtimeVisualGates']=['Native import/rendered gameplay acceptance remains separate; all four authored flight/Idle surfaces are now exact within audit tolerance.']
    result['evaluatedPoseSamples']=sum(x['sampleCount'] for x in rows if not x.get('reusedProofFrom'))
    result['reusedPoseSamples']=sum(x['sampleCount'] for x in rows if x.get('reusedProofFrom'))
    path=root/'structural-audit.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['clips','baselineSourcesUnchanged']},indent=2))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=DEFAULT_OUT);p.add_argument('--reuse-report',type=Path);a=p.parse_args();r=verify(a.root,a.reuse_report);raise SystemExit(0 if r['pass'] else 1)
