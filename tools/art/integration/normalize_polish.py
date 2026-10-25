#!/usr/bin/env python3
"""Source-preserving v026 representation; no animation authoring or engine calls."""
from __future__ import annotations
import argparse,copy,hashlib,json,math,shutil
from pathlib import Path
import numpy as np
from normalize_approved import GLB,Writer,UE,actor_motion,canonical_body,decompose,digest,mesh_variant,morph_info,normalize
ROOT=Path(__file__).resolve().parents[3]
DEFAULT_BASE=ROOT/'Local/CustomuseAssets/Integration20261025b'
DEFAULT_ART=ROOT/'Local/Blender/polish-20261025/manifest.json'
DEFAULT_OUT=ROOT/'Local/CustomuseAssets/Polish20261025'

def exact_roll_prefix(source:GLB,row:dict):
    """Keep the counter root identity during the manually driven .78s roll.

    The existing uniform root metadata must agree with the animation counter.
    A150Hz structural sampling grid includes the117th (.78s) boundary, unlike
    the previous60Hz grid. Source bone/helper channels are never modified.
    """
    rate=150.0
    count=round(source.duration()*rate)
    if abs(count/rate-source.duration())>1e-5:raise ValueError('RollAttack source is not on its authored150Hz grid')
    times=np.arange(count+1,dtype=float)/rate
    motion,mode=actor_motion(source,Path(row['file']).stem,times,'knight')
    motion[times<=.78+1e-9]=np.eye(4)
    out=GLB(row['file']);writer=Writer(out.g,out.binary);animation=writer.g['animations'][0]
    inv=np.linalg.inv(motion)
    data={'translation':np.array([decompose(m)[0] for m in inv]),'rotation':np.array([decompose(m)[1] for m in inv])}
    for channel in animation['channels']:
        if channel['target']['node']!=out.names['VeyrRoot']:continue
        path=channel['target']['path']
        if path not in data:continue
        sampler=animation['samplers'][channel['sampler']]
        sampler['input']=writer.add(times,'SCALAR',bounds=True)
        sampler['output']=writer.add(data[path],'VEC3' if path=='translation' else 'VEC4')
        sampler['interpolation']='LINEAR'
    row['sha256']=writer.write(row['file'])
    row['rootSampleRate']=rate
    row['rootTranslationSamplesCm']=[(UE@m[:3,3]*100).tolist() for m in motion]
    row['rootYawSamplesDegrees']=[]
    row['rootMode']=mode
    row['rollPrefixCounterIdentityThroughSeconds']=.78
    row['rootRepresentation']='150Hz counter/actor samples; identity through authored roll prefix; exact source channels retained'
    return row

def run(base:Path,art_manifest:Path,out:Path):
    base=base.resolve();out=out.resolve();art_manifest=art_manifest.resolve()
    if out==base or out.is_relative_to(base):raise ValueError('Fresh output must not overwrite the baseline')
    if (out/'manifest.json').exists():raise FileExistsError('Preserve existing normalized set; choose a fresh output')
    previous=json.loads((base/'manifest.json').read_text());art=json.loads(art_manifest.read_text())
    baseline_checks=[];sources=[]
    for old in previous['clips']:
        source=GLB(old['sourceFile']);derived=Path(old['file'])
        if source.sha!=old['sourceSHA256'] or digest(derived.read_bytes())!=old['sha256']:raise ValueError('Baseline provenance changed: '+source.path.name)
        baseline_checks.append({'sourceFile':str(source.path),'sourceSHA256':source.sha,'normalizedFile':str(derived),'normalizedSHA256':old['sha256']})
        sources.append((source,copy.deepcopy(old),False))
    for item in art['clips']:
        source=GLB(item['file'])
        if source.sha!=item['sha256']:raise ValueError('Final Blender candidate changed: '+source.path.name)
        sources.append((source,{'kind':'dragon' if source.path.name.startswith('Dragon_') else 'knight','job':item['key'],'loop':item.get('loop',False),'swordFile':item.get('weapon_file'),'runtimeKeys':item['runtimeKeys'],'blenderCandidate':item},True))
    union=[];seen=set()
    for source,row,_ in sources:
        if row['kind']!='dragon':continue
        for info in morph_info(source):
            if info['key'] in seen:continue
            seen.add(info['key']);union.append({**info,'name':info['key'][0]+'_'+info['key'][1][:10]})
    old_keys={(m['sourceName'],m['deltaHash']) for m in previous['morphUnion']}
    if not old_keys<=seen:raise ValueError('Lost a prior distinct morph identity')
    canonical={kind:GLB(spec['file']) for kind,spec in previous['canonicalSources'].items()}
    for kind,spec in previous['canonicalSources'].items():
        if canonical[kind].sha!=spec['sha256']:raise ValueError('Canonical source changed')
    out.mkdir(parents=True,exist_ok=True)
    result={'version':2,'nativeVersion':'v026','sourcePolicy':'Structural normalization only; every original geometry, skin, material and authored curve preserved. New motion originates only in owner-requested Blender revisions.','ownerRequestedRevision':True,'ownerApproved':False,'baselineManifest':str(base/'manifest.json'),'blenderManifest':str(art_manifest),'canonicalSources':previous['canonicalSources'],'morphUnion':[{'name':u['name'],'sourceName':u['key'][0],'deltaHash':u['key'][1]} for u in union],'clips':[],'props':{},'baselineProvenance':baseline_checks}
    for source,old,is_new in sources:
        kind=old['kind'];morphs=union if kind=='dragon' else []
        filename=source.path.name if is_new else Path(old['file']).name
        representation=canonical_body(canonical[kind],kind,morphs,source)
        row=normalize(source,representation,kind,morphs,out/kind/filename)
        if is_new and old['job']=='RollAttack':row=exact_roll_prefix(source,row)
        row.update(kind=kind,job=old['job'],loop=old.get('loop',False),swordFile=old.get('swordFile'),legacy=old.get('legacy',False),ownerRequestedRevision=is_new,ownerApproved=False if is_new else old.get('ownerApproved',None))
        if is_new:row['runtimeKeys']=old['runtimeKeys'];row['blenderCandidate']=old['blenderCandidate']
        else:row['baselineNormalizedFile']=old['file']
        result['clips'].append(row)
        print('NORMALIZED',filename,flush=True)
    for filename,spec in previous['props'].items():
        source=Path(spec['file']);actual=digest(source.read_bytes())
        if actual!=spec['sha256']:raise ValueError('Baseline rigid prop changed')
        target=out/'props'/filename;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        result['props'][filename]={**spec,'file':str(target),'baselineFile':str(source),'baselineSHA256':actual}
    variants={}
    for row in result['clips']:
        key=row['kind']+'_'+mesh_variant(GLB(row['file']))[:16];row['mesh_variant']=key
        variants.setdefault(key,{'file':row['file'],'sha256':row['sha256'],'kind':row['kind'],'sourceSHA256':row['sourceSHA256']})
    result['mesh_variants']=variants
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'manifest':str(out/'manifest.json'),'clips':len(result['clips']),'meshVariants':len(variants),'morphTargets':len(union),'oldMorphIdentitiesPreserved':len(old_keys)}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=DEFAULT_BASE);p.add_argument('--art-manifest',type=Path,default=DEFAULT_ART);p.add_argument('--out',type=Path,default=DEFAULT_OUT);a=p.parse_args();run(a.base,a.art_manifest,a.out)
