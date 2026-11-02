#!/usr/bin/env python3
"""Prepare a delegated, licensed heavy candidate on immutable native canonical geometry."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/art/integration'))
from normalize_sourced import normalize_file
from normalize_approved import GLB as SourceGLB
from normalize_customuse_glb import GLB
from graft_canonical_animation import graft
from import_customuse import inspect_glb,compatible

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version',default='v032kevin')
parser.add_argument('--export-name',default='Kevin_Heavy_M_v7')
parser.add_argument('--previous-version',default='v030t')
parser.add_argument('--clip-key',default='HeavyAttackTwoHandSourced')
parser.add_argument('--base-plan',type=Path,default=ROOT/'Local/CustomuseAssets/Polish20261025/knight-v030t/import-plan-KnightB.json')
parser.add_argument('--export-file',type=Path);parser.add_argument('--append-plan',type=Path)
args=parser.parse_args()
if args.append_plan:args.append_plan=args.append_plan.resolve()
if args.export_file:args.export_file=args.export_file.resolve()
if not all(x.replace('_','').isalnum() for x in [args.version,args.export_name,args.previous_version,args.clip_key]):parser.error('Names must contain only letters, digits or underscores')
base=json.loads((args.append_plan or args.base_plan).read_text())
folder=args.append_plan.parent if args.append_plan else ROOT/f'Local/CustomuseAssets/Polish20261025/knight-{args.version}'
if not args.append_plan:assert not folder.exists()
exported=args.export_file or ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget/Exports'/f'{args.export_name}.glb'
fit=json.loads(exported.with_suffix('.json').read_text())
assert hashlib.sha256(exported.read_bytes()).hexdigest()==fit['sha256']
canonical=Path(base['rig']['file']);assert hashlib.sha256(canonical.read_bytes()).hexdigest()==base['rig']['sha256']
normalized=folder/'intermediate'/exported.name;normal=normalize_file(exported,SourceGLB(canonical),normalized,120)
out=folder/'knight'/exported.name;proof=graft(canonical,normalized,out)
entry={'file':str(out),'sha256':proof['outputSHA256']};compatible(inspect_glb(base['rig']),inspect_glb(entry))
clip=GLB(out);socket=next(i for i,n in enumerate(clip.json['nodes']) if n.get('name')=='WeaponSocket')
weapon=GLB(ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb')
vertices=np.concatenate([weapon.accessor(p['attributes']['POSITION']) for m in weapon.json['meshes'] for p in m['primitives']])
tip=vertices[vertices[:,1]>vertices[:,1].max()-.005].mean(0)
duration=proof['durationSeconds'];times=np.linspace(0,duration,round(duration*120)+1)
points=np.array([(clip.world_matrices(0,float(t))[socket]@np.r_[tip,1])[:3] for t in times])
velocity=np.gradient(points,times,axis=0);speed=np.linalg.norm(velocity,axis=1)
forward=np.maximum(velocity[:,2],0);score=np.where(forward>0,speed,0)
peak=int(np.argmax(score));threshold=float(score[peak])*.30
if threshold<=0:raise ValueError('No measured forward strike')
low=high=peak
while low>0 and score[low-1]>=threshold:low-=1
while high<len(times)-1 and score[high+1]>=threshold:high+=1
window=[float(times[low]),float(times[high])]
body=GLB(canonical)
body_vertices=np.concatenate([body.accessor(p['attributes']['POSITION']) for m in body.json['meshes'] for p in m['primitives']])
native_scale=base['target_height_cm']/float(np.ptp(body_vertices[:,1]))
reach=float(max(0.,points[low:high+1,2].max())*native_scale)
if window[1]-window[0]<.05:raise ValueError('Measured strike window is too short')
plan={k:v for k,v in base.items() if k!='clips'}
if not args.append_plan:plan.update(version=args.version,replace_runtime_source=f'/Game/Characters/Customuse/KnightB/{args.previous_version}/DA_KnightB',owner_approved=False,owner_requested_revision=True)
plan['required_clips']=sorted(set(base['required_clips'])|{args.clip_key})
assert not args.append_plan or all(c['name']!=args.clip_key for c in base['clips'])
plan['clips']=(base['clips'] if args.append_plan else [])+[dict(name=args.clip_key,**entry,mesh_variant=base['canonical_mesh_variant'],start_seconds=0.,end_seconds=duration,loop=False,
 gameplay_play_rate=1.,nominal_speed_cm_per_second=0.,attack_reach_cm=reach,damage_windows=[window],impact_seconds=float(times[peak]),
 weapon_file=base['clips'][0]['weapon_file'],root_motion_policy='preserve',root_motion_removed=False,root_sample_rate=120.,
 root_translation_samples_cm=[],root_yaw_samples_degrees=[],source_duration=duration,approved_source_file=exported.name,approved_source_sha256=fit['sha256'])]
path=folder/'import-plan-KnightB.json';path.write_text(json.dumps(plan,indent=2)+'\n')
receipt={'plan':str(path),'sourceExport':str(exported),'normalization':normal,'graft':proof,'damageWindow':window,'impactSeconds':float(times[peak]),
 'windowMethod':'Contiguous blade-tip speed above 30 percent of forward-strike peak, sampled at 120 Hz; glTF +Z is character forward',
 'attackReachCm':reach,'reachMethod':'Maximum forward blade-tip position within the measured damage window, scaled by target height divided by canonical mesh height',
 'ownerAuthority':'Owner delegated source/implementation decisions on 2026-11-01; no human playback approval is claimed',
 'status':'Offline candidate only; native integration, runtime contacts and blind quality review pending'}
(folder/f'preparation-{args.clip_key}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Prepared licensed heavy; duration',duration,'measured damage window',window,'impact',float(times[peak]))
