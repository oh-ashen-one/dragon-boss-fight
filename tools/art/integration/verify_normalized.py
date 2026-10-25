#!/usr/bin/env python3
"""Independent source/derived reconstruction audit at keys AND between root keys."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from normalize_approved import GLB,UE,morph_info

def skinned_positions(g,worlds,weights):
 index,node=g.body();mesh=g.g['meshes'][node['mesh']];primitive=mesh['primitives'][0];a=primitive['attributes'];pos=g.accessor(a['POSITION']).astype(float);morph=weights.get(index,node.get('weights',mesh.get('weights',[0.]*len(primitive.get('targets',[])))))
 for i,target in enumerate(primitive.get('targets',[])):
  if abs(morph[i])>1e-12:pos+=g.accessor(target['POSITION'])*morph[i]
 skin=g.g['skins'][node['skin']];ibm=g.accessor(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1);mat=worlds[skin['joints']]@ibm;point=np.column_stack([pos,np.ones(len(pos))]);out=np.zeros_like(point)
 for suffix in ('0','1'):
  if 'JOINTS_'+suffix not in a:continue
  j=g.accessor(a['JOINTS_'+suffix]).astype(int);w=g.accessor(a['WEIGHTS_'+suffix])
  for k in range(j.shape[1]):out+=np.einsum('nij,nj->ni',mat[j[:,k]],point)*w[:,k:k+1]
 return out

def audit(root):
 manifest=json.loads((root/'manifest.json').read_text());rows=[]
 for clip in manifest['clips']:
  source=GLB(clip['sourceFile']);derived=GLB(clip['file']);assert derived.sha==clip['sha256'];duration=clip['duration'];rate=clip['rootSampleRate'];trajectory=np.array(clip['rootTranslationSamplesCm']);yaw=np.array(clip['rootYawSamplesDegrees'] or [0.]*len(trajectory));errors={'bone':0.,'weapon':0.,'cup':0.,'morph':0.,'skinnedVertex':0.};sn=source.names;dn=derived.names
  rest,_=derived.sample(None);skin=derived.g['skins'][0];ib=derived.accessor(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1);bind=float(abs(rest[skin['joints']]@ib-np.eye(4)).max())
  sm=morph_info(source);nm=morph_info(derived);source_body=source.body()[0];new_body=derived.body()[0]
  for t in [0,duration*.113,duration*.273,duration*.517,duration*.791,duration-.5/rate,duration]:
   t=max(0,min(duration,t));u=t*rate;i=min(len(trajectory)-1,int(u));j=min(i+1,len(trajectory)-1);f=min(1,u-i);d=trajectory[i]*(1-f)+trajectory[j]*f;a=yaw[i]*(1-f)+yaw[j]*f;M=np.eye(4);M[:3,:3]=Rotation.from_rotvec([0,-a*np.pi/180,0]).as_matrix();M[:3,3]=UE.T@d/100
   sw,sweights=source.sample(t);nw,nweights=derived.sample(t)
   for name in source.skin_names():errors['bone']=max(errors['bone'],float(abs(M@nw[dn[name]]-sw[sn[name]]).max()))
   for old,new,kind in [('ReviewWeaponSocket','WeaponSocket','weapon'),('DrinkingCup','CupSocket','cup')]:
    if old in sn:errors[kind]=max(errors[kind],float(abs(M@nw[dn[new]]-sw[sn[old]]).max()))
   source_vertices=skinned_positions(source,sw,sweights);derived_vertices=skinned_positions(derived,nw,nweights)
   assert source_vertices.shape==derived_vertices.shape,(clip['file'],'vertex count changed')
   errors['skinnedVertex']=max(errors['skinnedVertex'],float(abs((M@derived_vertices.T).T-source_vertices).max()))
   if sm:
    sdefault=source.g['meshes'][source.g['nodes'][source_body]['mesh']].get('weights',[0.]*len(sm));ndefault=derived.g['meshes'][0].get('weights',[0.]*len(nm));sv=sweights.get(source_body,sdefault);nv=nweights.get(new_body,ndefault)
    for semantic in sm[0]['arrays']:
     left=sum(e['arrays'][semantic]*sv[k] for k,e in enumerate(sm));right=sum(e['arrays'][semantic]*nv[k] for k,e in enumerate(nm));errors['morph']=max(errors['morph'],float(abs(left-right).max()))
  passed=bind<2e-5 and max(errors.values())<3e-4
  rows.append({'file':Path(clip['file']).name,'sourceSHA256':source.sha,'normalizedSHA256':derived.sha,'rootMode':clip['rootMode'],'duration':duration,'bindShapeError':bind,'reconstructionErrors':errors,'pass':passed})
 report={'scope':'Structural representation and imported-skin compatibility; not native rendering, gameplay or artistic approval. Per-clip source geometry, weights, inverse binds and materials preserved through shared-skeleton mesh variants.','clips':rows,'meshVariants':len(manifest['mesh_variants']),'morphTargetVariants':len(manifest['morphUnion']),'maximumReconstructionError':max(max(r['reconstructionErrors'].values()) for r in rows),'maximumBindShapeError':max(r['bindShapeError'] for r in rows),'pass':all(r['pass'] for r in rows)}
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();r=audit(a.root);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='clips'},indent=2));raise SystemExit(0 if r['pass'] else 1)
