#!/usr/bin/env python3
"""Independently inspect real Blender GLBs for the contiguous run/exit study.

This is an export/source diagnostic, never an engine or visual acceptance gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from normalize_customuse_glb import GLB


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--contact-reference',type=Path,help='Keep an earlier untrimmed source contact reference fixed across root-path revisions')
    a=p.parse_args();root=Path(__file__).resolve().parents[2]
    directory=a.directory.resolve(strict=True)
    pair=json.loads((directory/'pair.json').read_text())
    scale=json.loads((root/'docs/master-goal-20261103/sourced-turn-diagnostics.json').read_text())['scaleCmPerSourceUnit']
    clips=[]
    for row in pair['clips']:
        scene=root/row['editableScene'];path=scene.with_suffix('.glb')
        assert hashlib.sha256(scene.read_bytes()).hexdigest()==row['editableSceneSHA256']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        g=GLB(path);ids={n.get('name'):i for i,n in enumerate(g.json['nodes'])}
        count=round(row['duration']*120)
        worlds=np.stack([g.world_matrices(0,i/120) for i in range(count+1)])
        clips.append((g,ids,worlds,row))
    loop,exit=clips;assert len(loop[2])==81 and len(exit[2])>81
    names=set(loop[1])&set(exit[1]);names={n for n in names if n is not None}
    # Compare by bone name; GLB exporter node ordering is not an identity.
    names={n for n in names if n in ['VeyrRoot','Hips','WeaponSocket'] or n.startswith(('Left','Right','Spine','Neck','Head'))}
    prefix=max(float(np.max(np.abs(loop[2][:,loop[1][n]]-exit[2][:81,exit[1][n]]))) for n in names)
    travel=loop[2][-1,loop[1]['Hips'],:3,3]-loop[2][0,loop[1]['Hips'],:3,3]
    seam=max(float(np.linalg.norm(loop[2][-1,loop[1][n],:3,3]-loop[2][0,loop[1][n],:3,3]-travel)*scale) for n in names)
    seam_rotation=max(float(np.max(np.abs(loop[2][-1,loop[1][n],:3,:3]-loop[2][0,loop[1][n],:3,:3]))) for n in names)
    source=GLB((root/exit[3]['source']).with_suffix('.glb'));src_ids={n.get('name'):i for i,n in enumerate(source.json['nodes'])}
    src_worlds=np.stack([source.world_matrices(0,(i+16)/120) for i in range(len(exit[2]))])
    reference_path=a.contact_reference.resolve(strict=True) if a.contact_reference else (root/exit[3]['source']).with_suffix('.glb')
    reference=GLB(reference_path);ref_ids={n.get('name'):i for i,n in enumerate(reference.json['nodes'])}
    full_source=np.stack([reference.world_matrices(0,i/120) for i in range(len(exit[2])+16)])
    origin=src_worlds[0,src_ids['Hips'],:3,3].copy();origin[1]=0
    retained=[i for i in range(len(exit[2])) if i>=8 and abs(i-80)>=8]
    retained_error=max(float(np.linalg.norm(exit[2][retained,exit[1][n],:3,3]-(src_worlds[retained,src_ids[n],:3,3]-origin),axis=1).max()*scale) for n in names)
    source_grip=np.linalg.inv(src_worlds[:,src_ids['RightHand']]) @ src_worlds[:,src_ids['WeaponSocket']]
    grip=np.linalg.inv(exit[2][:,exit[1]['RightHand']]) @ exit[2][:,exit[1]['WeaponSocket']]
    grip_error=float(np.max(np.abs(source_grip-grip)))
    # Skin-based airborne check, rather than assuming ankle height is the sole.
    mesh=source.json['nodes'][source.mesh_node()];joints=source.json['skins'][mesh['skin']]['joints'];masks=[]
    for side in ['Left','Right']:
        ji=[i for i,n in enumerate(joints) if n in [src_ids[side+'Foot'],src_ids[side+'ToeBase']]]
        masks.append(np.concatenate([(np.isin(source.accessor(pr['attributes']['JOINTS_0']),ji)*source.accessor(pr['attributes']['WEIGHTS_0'])).sum(axis=1)>.75 for pr in source.json['meshes'][mesh['mesh']]['primitives']]))
    corrected=[i for i in range(len(exit[2])) if i<8 or abs(i-80)<8]
    airborne_min=min(float(source.skinned_positions(0,(i+16)/120)[mask,1].min()*scale) for i in corrected for mask in masks)
    contact=[]
    for side in ['Left','Right']:
        pos=np.take(exit[2],[exit[1][side+'Foot'],exit[1][side+'ToeBase']],axis=1)[:,:,:3,3]*scale
        # Trimming a lead-in changes the percentile population. Hold the full
        # baseline's references fixed so trimming cannot erase a failing window.
        baseline_pos=np.take(full_source,[ref_ids[side+'Foot'],ref_ids[side+'ToeBase']],axis=1)[:,:,:3,3]*scale
        ref=np.minimum(np.sort(baseline_pos[:,:,1],axis=0)[len(baseline_pos)//10],np.median(baseline_pos[-36:,:,1],axis=0))
        planted=np.all(pos[:,:,1]<=ref+2.5,axis=1)
        travel_cm=np.max(np.linalg.norm(np.diff(pos[:,:,[0,2]],axis=0),axis=-1),axis=1)
        windows=[{'seconds':i/120,'cmS':float(travel_cm[i-4:i].mean()*120)} for i in range(4,len(pos)) if all(planted[i-4:i+1])]
        contact.append({'side':side,'fixedBaselineReferenceCm':ref.tolist(),'windows':len(windows),'windowsOver60':sum(w['cmS']>60 for w in windows),'worst':max(windows,key=lambda w:w['cmS'],default=None)})
    checks={'prefixPoseMaxError':prefix,'loopSeamPositionErrorCm':seam,'loopSeamRotationMaxError':seam_rotation,'unmodifiedPosePositionErrorCm':retained_error,'handRelativeSocketMaxError':grip_error,'minimumSourceBootHeightDuringSeamCm':airborne_min}
    passed=prefix<1e-5 and seam<.01 and seam_rotation<1e-5 and retained_error<.01 and grip_error<1e-5 and airborne_min>3
    report={'scope':'Independent exported source/pair diagnostic; no native contact, gameplay or visual acceptance','contactReference':str(reference_path.relative_to(root)),'contactReferenceSHA256':hashlib.sha256(reference_path.read_bytes()).hexdigest(),'fidelityChecksPassed':passed,'checks':checks,'sourceContactScreen':contact,'sourceContactScreenPassed':all(c['windows'] and c['windowsOver60']==0 for c in contact),'nativeImported':False,'qualityAccepted':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
