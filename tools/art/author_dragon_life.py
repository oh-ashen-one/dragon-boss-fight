#!/usr/bin/env python3
"""Offline original dragon life/turn/stomp candidates. Never operates an editor.

Preserves the v006 mesh, materials, skin, rest pose and unrelated animations.
Runtime owns actor yaw/travel; turn extras specify the authored yaw cadence.
"""
import argparse,json,copy
from pathlib import Path
import numpy as np
from author_dragon_motion import DragonRig,Pose,UP,FORWARD,PITCH,ease,envelope,append_accessor
from inspect_weapon_topology import GLB,primitive,sha

CM=2155.818
TURN_SECONDS=1.8
TURN_DEGREES=20.
DUTY=.75

def rotate_y(v,degrees):
 a=np.radians(degrees);c,s=np.cos(a),np.sin(a)
 return np.array([c*v[0]+s*v[2],v[1],-s*v[0]+c*v[2]])

def root_shift(p,v):
 parent=p.rig.parents.get(p.rig.root);m=p.rig.rest_world[parent,:3,:3] if parent is not None else np.eye(3)
 p.t[p.rig.root]+=np.linalg.solve(m,np.asarray(v)/CM);p._world=None

def pose(rig,name,u,previous=None):
 p=Pose(rig);targets=[x['rest'].copy() for x in rig.legs];planted=[True]*4;yaws=np.zeros(4)
 breath=0.;neck_pitch=0.;neck_yaw=0.;tail=0.;fold=10.;body_pitch=0.;body_roll=0.;shift=np.zeros(3)
 if name=='Idle':
  breath=np.sin(4*np.pi*u);slow=np.sin(2*np.pi*u);sway=np.sin(2*np.pi*u)**3
  shift=np.array([2*slow,5*breath,8*sway]);body_pitch=1.4*breath;body_roll=1.2*sway
  neck_pitch=3.2*breath;neck_yaw=8*np.sin(2*np.pi*u)**3;tail=7*np.sin(2*np.pi*u-.35)+7*np.sin(.35);fold=10+2.3*(1-np.cos(4*np.pi*u))
 elif name.startswith('Stomp'):
  leg=int(name[5]);phase=name[6:];side=np.sign(targets[leg][2])
  if phase=='Windup':
   transfer=ease(u/.28);lift=ease((u-.18)/.30)*(1-ease((u-.76)/.24));compression=0.
  elif phase=='Active':transfer=1.;lift=0.;compression=12*envelope(u)
  else:transfer=1-ease(u);lift=0.;compression=0.
  shift=np.array([28*transfer,-compression,-side*36*transfer]);body_roll=-side*3*transfer;body_pitch=-2*transfer;neck_pitch=4*transfer;neck_yaw=side*5*transfer;tail=-side*8*transfer;fold=10+4*transfer
  targets[leg]+=np.array([20*lift,210*lift,side*8*lift])/CM;planted[leg]=lift<1e-6
 elif name.startswith('Turn'):
  # Source Y rotation has opposite sign to positive Unreal actor yaw.
  direction=1 if name=='TurnRight' else -1
  for i,offset in enumerate([0.,.5,.75,.25]):
   phase=(u+offset)%1
   if phase<DUTY:
    angle=direction*TURN_DEGREES*(phase-DUTY/2);planted[i]=True
   else:
    z=(phase-DUTY)/(1-DUTY);angle=direction*TURN_DEGREES*DUTY*(.5-ease(z));targets[i][1]+=48*np.sin(np.pi*z)**2/CM;planted[i]=False
   yaws[i]=angle;pivot=np.array([300/CM,0,0]);targets[i]=pivot+rotate_y(targets[i]-pivot,angle)
  neck_yaw=direction*7;tail=-direction*5;body_roll=-direction*.8;shift[1]=2*np.sin(4*np.pi*u)
 else:raise ValueError(name)
 root_shift(p,shift);p.rotate_world(rig.root,PITCH,body_pitch);p.rotate_world(rig.root,FORWARD,body_roll)
 for n,share in zip(rig.neck,(.65,.25,.10)):
  p.rotate_world(n,PITCH,neck_pitch*share);p.rotate_world(n,UP,-neck_yaw*share)
 for n,share in zip(rig.tail,(.2,.25,.3,.25)):p.rotate_world(n,UP,-tail*share)
 for side,chain in zip(('PosZ','NegZ'),rig.wings):
  sign=rig.semantic.get('wingDownAngleSigns',{'PosZ':1,'NegZ':-1})[side]
  p.rotate_world(chain[0],FORWARD,-sign*fold);p.rotate_world(chain[1],UP,-sign*fold*.7);p.rotate_world(chain[3],UP,-sign*fold*.45)
 errors=[]
 for i,(leg,target) in enumerate(zip(rig.legs,targets)):
  desired=max(0.,target[1]-leg['rest'][1]);raw=target[1]
  if previous is not None:target[1]+=previous.ik_corrections[i]
  best=1e10;best_q=None;besttarget=None
  for _ in range(15):
   ankle=leg['end'] if len(leg['chain'])==3 else leg['chain'][3]
   toe=rig.rest_world[leg['end'],:3,3]-rig.rest_world[ankle,:3,3]
   solve_target=target+toe-rotate_y(toe,yaws[i])
   p.solve_leg(leg,solve_target)
   if abs(yaws[i])>1e-9:
    ankle=leg['end'] if len(leg['chain'])==3 else leg['chain'][3]
    for n in set([ankle]+leg.get('leaves',[leg['end']])):
     p.set_leaf_rest_orientation(n);p.rotate_world(n,UP,yaws[i])
   error=desired-rig.sole_minimum(p,i)
   if abs(error)<best:best=abs(error);best_q=p.q.copy();besttarget=target.copy()
   if abs(error)*CM<.35:break
   target[1]+=np.clip(error*.8,-.03,.04)
  p.q=best_q;p._world=None;target[:]=besttarget;p.ik_corrections[i]=target[1]-raw
  errors.append(np.linalg.norm(p.world()[leg['end'],:3,3]-target)*CM)
 return p,targets,planted,errors

def author(source,semantic,outdir,fps=30):
 rig=DragonRig(source,semantic,CM);out=GLB(source.bytes());prefix=bytes(source.binary)
 configs={'Idle':(8.,True),**{f'Stomp{i}{s}':(d,False) for i in [2,3] for s,d in [('Windup',1.25),('Active',.28),('Recovery',1.5)]},'TurnLeft':(TURN_SECONDS,True),'TurnRight':(TURN_SECONDS,True)}
 reports=[];endposes={};newanimations={}
 for name,(duration,loop) in configs.items():
  times=np.linspace(0,duration,int(np.ceil(duration*fps))+1)
  if name.startswith('Turn'):times=np.unique(np.r_[times,duration*np.array([.25,.5,.75])])
  previous=endposes.get(name.replace('Active','Windup').replace('Recovery','Active'))
  if loop:
   for t in times:previous=pose(rig,name,t/duration,previous)[0]
  rotations={n:[] for n in rig.joints};translations=[];tr=[];maxlength=0
  for t in times:
   p,targets,planted,errors=pose(rig,name,t/duration,previous);previous=p;W=p.world()
   lengths=np.array([np.linalg.norm(W[b,:3,3]-W[a,:3,3]) for a,b in rig.joint_edges]);maxlength=max(maxlength,float(abs(lengths-rig.lengths).max())*CM)
   if not np.isfinite(W).all() or maxlength>.001:raise ValueError('Invalid skeleton '+name)
   for n in rig.joints:
    q=p.q[n].copy()
    if rotations[n] and np.dot(q,rotations[n][-1])<0:q=-q
    rotations[n].append(q)
   translations.append(p.t[rig.root].copy())
   tr.append({'seconds':float(t),'planted':list(map(bool,planted)),'feetCm':[(W[x['end'],:3,3]*CM).tolist() for x in rig.legs],'soleMinimumCm':[rig.sole_minimum(p,i)*CM for i in range(4)],'headCm':(W[rig.head,:3,3]*CM).tolist(),'ikErrorCm':list(map(float,errors))})
  if loop:
   for n in rotations:rotations[n][-1]=rotations[n][0].copy()
   translations[-1]=translations[0].copy()
  animation={'name':name,'samplers':[],'channels':[],'extras':{'originalVeyrMotion':True,'loop':loop,'candidate':'dragon-life-v3','actorTravelNotAuthored':True}}
  if name.startswith('Turn'):animation['extras'].update({'actorYawDegreesPerCycle':TURN_DEGREES*(1 if name=='TurnRight' else -1),'actorYawDegreesPerSecond':TURN_DEGREES/duration*(1 if name=='TurnRight' else -1),'footDutyFraction':DUTY})
  timeline=append_accessor(out,times[:,None],'SCALAR')
  for n,values in list(rotations.items())+[(rig.root,translations)]:
   path='translation' if values is translations else 'rotation';accessor=append_accessor(out,values,'VEC3' if path=='translation' else 'VEC4');animation['channels'].append({'sampler':len(animation['samplers']),'target':{'node':n,'path':path}});animation['samplers'].append({'input':timeline,'output':accessor,'interpolation':'LINEAR'})
  newanimations[name]=animation;endposes[name]=previous
  reports.append({'name':name,'durationSeconds':duration,'loop':loop,'maximumBoneLengthChangeCm':maxlength,'trajectories':tr})
  print(name,flush=True)
 out.json['animations']=[newanimations.get(a['name'],a) for a in source.json['animations']]+[a for n,a in newanimations.items() if n not in {x['name'] for x in source.json['animations']}]
 assert bytes(out.binary[:len(prefix)])==prefix
 for field in ['meshes','skins','nodes','materials','textures','images','samplers']:assert out.json.get(field)==source.json.get(field),field
 assert all(a==b for a,b in zip(source.json['animations'],out.json['animations']) if a['name'] not in newanimations)
 destination=outdir/'dragon-life-v3.glb'
 if destination.exists():raise ValueError('Fresh destination required')
 destination.write_bytes(out.bytes());reopened=GLB(destination)
 # Independent decoded CPU probes, including between authored keys.
 for report in reports:
  index=next(i for i,a in enumerate(reopened.json['animations']) if a['name']==report['name']);name=report['name'];duration=report['durationSeconds'];samples=np.linspace(0,duration,int(np.ceil(duration*60))+1);feet=[];solemins=[];bodymin=[];head=[];slips=[];last=None
  for t in samples:
   W=reopened.world_matrices(index,float(t));vertices=reopened.skinned_positions(index,float(t));assert np.isfinite(vertices).all();foot=[vertices[m] for m in rig.foot_masks];jointfoot=np.array([W[l['end'],:3,3] for l in rig.legs])*CM
   # Compensate the intended actor yaw to measure stance sliding in WORLD.
   if name.startswith('Turn'):
    angle=-(1 if name=='TurnRight' else -1)*TURN_DEGREES*t/duration
    foot=[np.array([np.array([300/CM,0,0])+rotate_y(v-np.array([300/CM,0,0]),angle) for v in f]) for f in foot];jointfoot=np.array([np.array([300,0,0])+rotate_y(v-np.array([300,0,0]),angle) for v in jointfoot])
   centers=np.array([f.mean(0)*CM for f in foot]);minima=np.array([f[:,1].min()*CM for f in foot]);solemins.append(minima);bodymin.append(float(vertices[:,1].min()*CM));head.append(W[rig.head,:3,3]*CM)
   if last is not None:
    prevt,prevc,prevj=last
    for i in range(4):
     stance=True
     if name.startswith('Turn'):stance=((t/duration+[0,.5,.75,.25][i])%1)<DUTY and ((prevt/duration+[0,.5,.75,.25][i])%1)<DUTY
     elif name.startswith('Stomp') and i==int(name[5]) and name.endswith('Windup'):stance=t/duration<=.18 or prevt/duration>=1
     if stance:slips.append({'leg':i,'cmPerSec':float(np.linalg.norm((centers[i]-prevc[i])[[0,2]])/(t-prevt)),'pointCmPerSec':float(np.linalg.norm((jointfoot[i]-prevj[i])[[0,2]])/(t-prevt))})
   last=(t,centers,jointfoot)
  report.update({'cpuSkinFinite':True,'minimumWholeMeshHeightCm':min(bodymin),'footSoleRangesCm':np.array([np.min(solemins,axis=0),np.max(solemins,axis=0)]).tolist(),'headExcursionCm':np.ptp(head,axis=0).tolist(),'stanceSurfaceCentroidSpeedP50P95MaxCmSec':np.percentile([s['cmPerSec'] for s in slips],[50,95,100]).tolist(),'stanceFootJointSpeedP50P95MaxCmSec':np.percentile([s['pointCmPerSec'] for s in slips],[50,95,100]).tolist(),'loopSkinEndpointMaximumGapCm':float(np.linalg.norm(reopened.skinned_positions(index,0)-reopened.skinned_positions(index,duration),axis=1).max()*CM) if report['loop'] else None})
  print('QA',name,report['stanceSurfaceCentroidSpeedP50P95MaxCmSec'],flush=True)
 receipt={'status':'OFFLINE_CANDIDATE_NATIVE_REVIEW_REQUIRED','output':str(destination.resolve()),'outputSHA256':sha(destination),'sourceSHA256':__import__('hashlib').sha256(source.bytes()).hexdigest(),'scriptSHA256':sha(Path(__file__)),'worldCmPerUnit':CM,'meshWeightsRestMaterialsAndOtherClipsPreserved':True,'contactBoundary':'Stomp foot reaches planted pose at Windup end / Active start; durations unchanged.','turnRuntime':'Actor yaw must match signed20degrees/1.8seconds at playback1. Root has zero horizontal travel; small idle/stomp body weight shifts return to baseline.','nativeAccepted':False,'clips':reports}
 (outdir/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--semantic-map',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
 if 'Local/art-pass-20261019/dragon' not in str(args.output_dir.resolve()):raise ValueError('Task-owned output directory required')
 author(GLB(args.source),json.loads(args.semantic_map.read_text()),args.output_dir)
