#!/usr/bin/env python3
"""Prepare a diagnostic-only native run/exit pair, without importing or enabling.

Linear actor travel for the run is shared by the exit prefix. After that prefix,
the exit factors its captured deceleration. Dense reconstruction and prefix
checks ensure representation changes do not rewrite the Blender performance.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB,UE
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import compatible,inspect_glb

BASE=ROOT/'Local/CustomuseAssets/Polish20261025/knight-v046start/import-plan-KnightB.json'
PAIR=ROOT/'Local/AttackSources20261105/ACCADMale1/ContiguousPairV18'
OUT=ROOT/'Local/CustomuseAssets/Polish20261025/knight-v047contiguous'

def main():
    assert not OUT.exists(), 'Never overwrite an earlier candidate'
    source_check=json.loads((ROOT/'docs/master-goal-20261103/contiguous-placement-export-check.json').read_text())
    assert source_check['fidelityChecksPassed'] and not source_check['qualityAccepted']
    # Remaining source failures stay explicit; this plan cannot be called a
    # quality-approved/default import merely because reconstruction passes.
    base=json.loads(BASE.read_text());canonical=Path(base['rig']['file'])
    assert hashlib.sha256(canonical.read_bytes()).hexdigest()==base['rig']['sha256']
    c=GLB(canonical);vertices=np.concatenate([c.accessor(p['attributes']['POSITION']) for m in c.json['meshes'] for p in m['primitives']])
    scale=base['target_height_cm']/float(np.ptp(vertices[:,1]));native_scale=scale/100
    pair=json.loads((PAIR/'pair.json').read_text());duration_loop=pair['clips'][0]['duration']
    plan={k:v for k,v in base.items() if k!='clips'}
    plan.update(version='v047contiguous',replace_runtime_source='/Game/Characters/Customuse/KnightB/v046start/DA_KnightB',owner_approved=False,diagnostic_only=True,
        purpose='Isolated two-hand run/exit controller trial; source late-stop contact failure and all native/visual/Opus gates remain open',scale_aware_compression=True,rotation_precision_codec='least_destructive',clips=[])
    converted=[];reports=[]
    for index,(key,meta) in enumerate(zip(['RunTwoHandContiguous','RunStopTwoHandContiguous'],pair['clips'])):
        scene=ROOT/meta['editableScene'];source=scene.with_suffix('.glb')
        assert meta['authoringApplication']=='Blender' and not meta.get('candidateStopped')
        assert hashlib.sha256(scene.read_bytes()).hexdigest()==meta['editableSceneSHA256'] and hashlib.sha256(source.read_bytes()).hexdigest()==meta['sha256']
        duration=SourceGLB(source).duration();intermediate=OUT/'intermediate'/source.name
        normal=normalize_file(source,SourceGLB(canonical),intermediate,120,duration,False,index==0,False,None if index==0 else duration_loop)
        target=OUT/'knight'/source.name;proof=graft(canonical,intermediate,target)
        entry={'file':str(target),'sha256':proof['outputSHA256']};compatible(inspect_glb(base['rig']),inspect_glb(entry))
        old,new=SourceGLB(source),SourceGLB(target);translation=np.asarray(normal['rootTranslationSamplesCm']);times=np.linspace(0,duration,2*(len(translation)-1)+1);worst=0.
        for t in times:
            f=min(t*normal['rootSampleRate'],len(translation)-1);i=int(f);j=min(i+1,len(translation)-1);w=f-i
            actor=np.eye(4);actor[:3,3]=UE.T @ ((1-w)*translation[i]+w*translation[j])/100
            a,_=old.sample(float(t));b,_=new.sample(float(t))
            worst=max(worst,max(float(np.max(np.abs(actor @ b[new.names[n]]-a[old.names[n]]))) for n in old.skin_names()))
        assert worst<3e-5
        nominal=float(np.linalg.norm(translation[-1,:2])*native_scale/duration) if index==0 else 0.
        plan['clips'].append(dict(name=key,**entry,mesh_variant=base['canonical_mesh_variant'],start_seconds=0.,end_seconds=duration,loop=index==0,
            gameplay_play_rate=1.,nominal_speed_cm_per_second=nominal,damage_windows=[],impact_seconds=-1.,weapon_file=base['clips'][0]['weapon_file'],
            root_motion_policy='preserve',root_motion_removed=True,root_motion_vertical=False,root_sample_rate=normal['rootSampleRate'],root_translation_samples_cm=normal['rootTranslationSamplesCm'],root_yaw_samples_degrees=[],
            source_duration=duration,approved_source_file=source.name,approved_source_sha256=meta['sha256']))
        reports.append({'clip':key,'maximumWorldMatrixError':worst,'samples':len(times),'normalization':normal,'graft':proof,'accepted':False})
        converted.append((new,translation))
    loop,exit=converted;prefix_error=0.
    for t in np.linspace(0,duration_loop,161):
        a,_=loop[0].sample(float(t));b,_=exit[0].sample(float(t))
        prefix_error=max(prefix_error,max(float(np.max(np.abs(a[loop[0].names[n]]-b[exit[0].names[n]]))) for n in loop[0].skin_names()))
    actor_prefix_error=float(np.max(np.abs(loop[1]-exit[1][:len(loop[1])])));assert prefix_error<3e-5 and actor_prefix_error<.001
    plan['required_clips']=sorted(set(base['required_clips'])|{clip['name'] for clip in plan['clips']})
    (OUT/'import-plan-KnightB.json').write_text(json.dumps(plan,indent=2)+'\n')
    report={'diagnosticOnly':True,'nativeImported':False,'qualityAccepted':False,'sourceContactScreenPassed':source_check['sourceContactScreenPassed'],
        'sharedNormalizedPrefixMaxMatrixError':prefix_error,'sharedActorPrefixMaxErrorCm':actor_prefix_error,'loopDurationSeconds':duration_loop,'loopNominalCmS':plan['clips'][0]['nominal_speed_cm_per_second'],'clips':reports}
    (OUT/'preparation-pair.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='clips'},indent=2))

if __name__=='__main__':main()
