#!/usr/bin/env python3
"""Reversible action-motion candidates from reviewed cloth-repaired GLB sources.

Resamples original motion, authors root/limb corrections, never changes geometry,
weights, joint translations, bone scales or rest nodes. Every output includes
source hashes, finite/length invariants, grounding measurements and limitations.
Requires the frozen author_knight_hold helper for actual-length arm IK.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from inspect_weapon_topology import GLB, ASSETS, primitive
from author_knight_hold import align, quaternion, rotation, unit, solve_hold, setup, PROFILES


def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def append(g,a,kind):
    a=np.asarray(a,dtype='<f4');g.binary.extend(b'\0'*(-len(g.binary)%4));off=len(g.binary);g.binary.extend(a.tobytes())
    vi=len(g.json['bufferViews']);g.json['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':a.nbytes})
    ai=len(g.json['accessors']);g.json['accessors'].append({'bufferView':vi,'componentType':5126,'count':len(a),'type':kind,'min':a.min(0).tolist(),'max':a.max(0).tolist()});g.json['buffers'][0]['byteLength']=len(g.binary);return ai


def sample(g,time):
    result={}
    for channel in g.json['animations'][0]['channels']:
        sampler=g.json['animations'][0]['samplers'][channel['sampler']];times=g.accessor(sampler['input']).reshape(-1);values=g.accessor(sampler['output']);i=max(0,min(len(times)-1,int(np.searchsorted(times,time,side='right')-1)));v=values[i].astype(float)
        if i+1<len(times) and time>times[i]:
            a=float(np.clip((time-times[i])/(times[i+1]-times[i]),0,1))
            if channel['target']['path']=='rotation':
                b=values[i+1].astype(float)
                if np.dot(v,b)<0:b=-b
                dot=float(np.clip(np.dot(v/np.linalg.norm(v),b/np.linalg.norm(b)),-1,1))
                if dot>.9995:v=unit(v*(1-a)+b*a)
                else:theta=np.arccos(dot);v=(np.sin((1-a)*theta)*v+np.sin(a*theta)*b)/np.sin(theta)
            else:v=v*(1-a)+values[i+1]*a
        result[(channel['target']['node'],channel['target']['path'])]=v.copy()
    return result


def blend(a,b,alpha):
    r={}
    for key,v in a.items():
        w=b[key]
        if key[1]=='rotation':
            if np.dot(v,w)<0:w=-w
            dot=float(np.clip(np.dot(unit(v),unit(w)),-1,1))
            if dot>.9995:r[key]=unit(v*(1-alpha)+w*alpha)
            else:angle=np.arccos(dot);r[key]=(np.sin((1-alpha)*angle)*v+np.sin(alpha*angle)*w)/np.sin(angle)
        else:r[key]=v*(1-alpha)+w*alpha
    return r


def pose_world(g,pose):
    # Apply sampled tracks to an ephemeral document; no source modification.
    d=GLB(g.bytes())
    for (node,path),value in pose.items():d.json['nodes'][node][path]=value.tolist()
    d.json.pop('animations',None)
    return d,d.world_matrices()


def build(g,poses,times,label):
    out=GLB(g.bytes());animation={'name':'Veyr_Authored_'+label,'samplers':[],'channels':[]};ti=append(out,np.asarray(times)[:,None],'SCALAR')
    for key in poses[0]:
        values=np.array([p[key] for p in poses])
        if key[1]=='rotation':
            values/=np.linalg.norm(values,axis=1)[:,None]
            for i in range(1,len(values)):
                if np.dot(values[i-1],values[i])<0:values[i]*=-1
        ai=append(out,values,'VEC4' if key[1]=='rotation' else 'VEC3');si=len(animation['samplers']);animation['samplers'].append({'input':ti,'output':ai,'interpolation':'LINEAR'});animation['channels'].append({'sampler':si,'target':{'node':key[0],'path':key[1]}})
    out.json['animations']=[animation];return GLB(out.bytes())


def set_world_hips_y(g,pose,y):
    hips=0;parent=g.parents.get(hips);pw=g.world_matrices()[parent] if parent is not None else np.eye(4);old=pose[(hips,'translation')];wp=(pw@np.r_[old,1])[:3];wp[1]=y;pose[(hips,'translation')]=(np.linalg.inv(pw)@np.r_[wp,1])[:3]


def fixed_heading(R,heading):
    c,s=np.cos(heading),np.sin(heading);return np.array([[c,0,s],[0,1,0],[-s,0,c]])@R


def root_rotation_world(g,pose,R):
    parent=g.parents.get(0);pw=g.world_matrices()[parent,:3,:3] if parent is not None else np.eye(3);pose[(0,'rotation')]=quaternion(pw.T@R)


def body_vertices(g):
    _,p,_,_=primitive(g);n=g.json['accessors'][p['attributes']['POSITION']]['count'];ids=np.ones(n,bool)
    weapon=json.loads((ASSETS/'weapon-topology-v1/candidate-mask.json').read_text())['vertexIndices'];ids[weapon]=False
    for path in (ASSETS/'cloth-skin-review-v1').glob('component-*-mask.json'):
        d=json.loads(path.read_text());v=d.get('vertexIndices',d.get('selectedVertexIndices'))
        if v is not None:ids[v]=False
    return np.flatnonzero(ids)


def ground(g,poses,kind):
    _,p,_,_=primitive(g);j=g.accessor(p['attributes']['JOINTS_0']);w=g.accessor(p['attributes']['WEIGHTS_0']);feet=np.flatnonzero((np.isin(j,[46,47,50,51])*w).sum(1)>.75);body=body_vertices(g)
    if kind in ('roll','death'):
        # Contact support is torso/head/legs; a sword/hand artifact must not bounce the whole body.
        support=(np.isin(j,[0,1,2,3,4,5,44,45,46,47,48,49,50,51])*w).sum(1)>.7
        body=body[support[body]]
    offsets=[]
    for pose in poses:
        d,W=pose_world(g,pose);xyz=d.skinned_positions();ids=feet if kind in ('heal','stagger') else body;offsets.append(-float(xyz[ids,1].min()))
    # Smooth the grounding envelope, not individual feet or mesh vertices.
    offsets=np.asarray(offsets);pad=np.pad(offsets,(2,2),mode='edge');filtered=np.convolve(pad,[.1,.2,.4,.2,.1],mode='valid')
    for pose,off in zip(poses,filtered):
        _,W=pose_world(g,pose);set_world_hips_y(g,pose,W[0,1,3]+off)
    return {'mode':'weighted-foot envelope' if kind in ('heal','stagger') else 'armor/body contact envelope excluding weapon and separately repaired cloth','offsetWorldMinMax':[float(filtered.min()),float(filtered.max())],'offsetsWorld':filtered.tolist()}


def source_mapping(label,duration):
    if label=='jump':return [0,.5,.85,1],[2.37,2.5666666667,2.93,3.0666666667]
    if label=='heal':return [0,.25,.60,.85,1.,1.25],[.1,.3,.55,.90,1.30,2.2]
    if label=='stagger':return [0,duration],[.23,.90]
    if label=='death':return [0,duration],[.1,4.5]
    if label=='roll':return [0,.52,duration],[.5,1.6,1.6]
    raise ValueError(label)


def solve_left(g,pose,target,desired_hand,pole,chain=(7,8,9)):
    d,W=pose_world(g,pose);upper,fore,hand=chain;shoulder=W[upper,:3,3];L1=np.linalg.norm(W[fore,:3,3]-shoulder);L2=np.linalg.norm(W[hand,:3,3]-W[fore,:3,3]);direction=unit(target-shoulder);distance=np.linalg.norm(target-shoulder);requested=distance;distance=float(np.clip(distance,abs(L1-L2)+.004,L1+L2-.004));target=shoulder+direction*distance;along=(L1*L1-L2*L2+distance*distance)/(2*distance);pole=unit(pole-direction*np.dot(pole,direction));elbow=shoulder+direction*along+pole*np.sqrt(max(0,L1*L1-along*along))
    handref=rotation(g.json['nodes'][hand]['rotation']);foreref=rotation(g.json['nodes'][fore]['rotation']);forehint=desired_hand@handref.T;desired_fore=align(forehint@np.asarray(g.json['nodes'][hand]['translation']),target-elbow)@forehint;upperhint=desired_fore@foreref.T;desired_upper=align(upperhint@np.asarray(g.json['nodes'][fore]['translation']),elbow-shoulder)@upperhint
    pose[(upper,'rotation')]=quaternion(W[g.parents[upper],:3,:3].T@desired_upper);pose[(fore,'rotation')]=quaternion(desired_upper.T@desired_fore);pose[(hand,'rotation')]=quaternion(desired_fore.T@desired_hand)
    _,after=pose_world(g,pose)
    return {'target':target.tolist(),'elbow':elbow.tolist(),'targetClampedWorld':abs(requested-distance),'wristResidualWorld':float(np.linalg.norm(after[hand,:3,3]-target)),'upperArmWorldLength':L1,'forearmWorldLength':L2}


def author(source,output,label,duration,ready_path,hold_profile=None):
    g=GLB(source);ready=GLB(ready_path);sourcehash=sha(source);readyhash=sha(ready_path)
    if g.json['nodes']!=ready.json['nodes']:raise ValueError('Ready donor skeleton/rest transforms differ')
    factor=244/np.ptp(g.skinned_positions()[:,1]);times=np.linspace(0,duration,round(duration*60)+1);knots,sourceknots=source_mapping(label,duration);sourcetimes=np.interp(times,knots,sourceknots);poses=[sample(g,float(t)) for t in sourcetimes];metadata={'sourceMappingRuntime':knots,'sourceMappingOriginal':sourceknots,'durationSeconds':duration};rest=g.world_matrices();neutral=sample(ready,1.5)
    if label=='jump':
        # Remove only the source's flight envelope between takeoff and pre-landing.
        start,end=2.37,2.93;y0=g.world_matrices(0,start)[0,1,3];y1=g.world_matrices(0,end)[0,1,3];offset=-pose_world(g,poses[0])[0].skinned_positions()[body_vertices(g),1].min();landing_offset=-pose_world(g,poses[-1])[0].skinned_positions()[body_vertices(g),1].min();removed=[]
        for pose,t,runtime in zip(poses,sourcetimes,times):
            _,W=pose_world(g,pose);old=W[0,1,3];baseline=y0+(y1-y0)*np.clip((t-start)/(end-start),0,1);delta=old-baseline if start<=t<=end else 0.;ground_offset=offset+(landing_offset-offset)*float(smooth((runtime/duration-.75)/.25));set_world_hips_y(g,pose,old-delta+ground_offset);removed.append(float(delta))
        metadata['flightRootEnvelopeRemovedCmMax']=max(removed)*factor;metadata['rootPolicy']='Gameplay capsule owns flight height; Hips flight envelope removed, nonroot tuck and post-flight landing compression retained';metadata['groundingOffsetCm']=[float(offset*factor),float(landing_offset*factor)];metadata['landingGroundingBlendPhase']=[.75,1.]
    elif label=='roll':
        reference=g.world_matrices(0,.5)[0,:3,:3];anchors=np.array([.5,.7,.9,1.,1.3,1.5,1.6]);angles=[]
        for t in anchors:
            rel=g.world_matrices(0,float(t))[0,:3,:3]@reference.T;q=quaternion(rel);degrees=np.degrees(2*np.arctan2(q[1],q[3]));angles.append(float((degrees+180)%360-180))
        for pose,t in zip(poses,sourcetimes):
            _,W=pose_world(g,pose);twist=np.interp(t,anchors,np.deg2rad(angles));root_rotation_world(g,pose,fixed_heading(W[0,:3,:3],-twist))
        # Grounded authored crouch-to-ready blend, not a compressed multi-second source stand-up.
        base=copy.deepcopy(poses[np.argmin(abs(times-.52))]);_,baseW=pose_world(g,base);_,readyW=pose_world(g,neutral)
        readyPose=copy.deepcopy(neutral);readyPose[(0,'translation')][[0,2]]=base[(0,'translation')][[0,2]];root_rotation_world(g,readyPose,reference)
        for i,t in enumerate(times):
            if t>.52:poses[i]=blend(base,readyPose,float(smooth((t-.52)/(duration-.52))))
        metadata['headingAnchorSeconds']=anchors.tolist();metadata['headingTwistDegrees']=angles;metadata['inversionHandling']='Continuous upright-derived heading interpolated through near-inverted interval; no singular per-frame twist extraction';metadata['recoverySeconds']=duration-.52;metadata['grounding']=ground(g,poses,label)
    else:metadata['grounding']=ground(g,poses,label)
    if label=='roll':
        # An oversized sword cannot follow the source's forward ground-planting hand.
        # Carry it laterally, parallel to the roll axis, then return to the ready donor.
        context=setup(g,PROFILES['idle']);blade=np.array([-1.,0,0]);guard=np.array([0.,0,1.]);handR=np.column_stack([blade,guard,np.cross(blade,guard)])@context['localWeaponFrame'].T;carry=[]
        for pose,t in zip(poses,times):
            _,W=pose_world(g,pose);a=float(smooth((t-.52)/(duration-.52)));shoulder=W[26,:3,3];carrytarget=shoulder+np.array([-.21,.06,.06]);target=(1-a)*carrytarget+a*W[28,:3,3]
            # Interpolate blade direction explicitly; quaternion shortest arcs can swing a long blade through the floor.
            endblade=W[28,:3,:3]@context['localWeaponFrame'][:,0];endguard=W[28,:3,:3]@context['localWeaponFrame'][:,1];bd=unit((1-a)*blade+a*endblade);gd=(1-a)*guard+a*endguard;gd=unit(gd-bd*np.dot(gd,bd));desired=np.column_stack([bd,gd,np.cross(bd,gd)])@context['localWeaponFrame'].T;pole=(1-a)*np.array([0.,-.25,1.])+a*unit(W[27,:3,3]-shoulder);metrics=solve_left(g,pose,target,desired,pole,(26,27,28))
            for finger in range(29,44):pose[(finger,'rotation')]=np.asarray(g.json['nodes'][finger].get('rotation',[0,0,0,1]),float)
            metrics['runtimeSeconds']=float(t);carry.append(metrics)
        metadata['finalRollContactGrounding']=ground(g,poses,'roll_final')
        for row,off in zip(carry,metadata['finalRollContactGrounding']['offsetsWorld']):
            row['target'][1]+=off;row['elbow'][1]+=off
        metadata['lateralSwordCarry']=carry;metadata['rollBladeDirectionWorld']=[-1,0,0]
    if label=='death':
        context=setup(g,PROFILES['idle']);carry=[]
        lateral=[];valid=[]
        for pose in poses:
            _,W=pose_world(g,pose);v=W[26,:3,3]-W[3,:3,3];v[1]=0;lateral.append(np.arctan2(v[2],v[0]));valid.append(np.linalg.norm(v)>.035)
        lateral=np.unwrap(lateral);valid=np.array(valid);lateral=np.interp(times,times[valid],lateral[valid]);lateral=np.convolve(np.pad(lateral,(3,3),mode='edge'),np.ones(7)/7,mode='valid')
        for pose,t,heading in zip(poses,times,lateral):
            _,W=pose_world(g,pose);side=np.array([np.cos(heading),0,np.sin(heading)]);tangent=np.array([-side[2],0,side[0]]);target=W[26,:3,3]+side*.20+np.array([0,.04,0]);guard=side
            def hand_at_angle(angle):
                blade=tangent*np.cos(angle)+np.array([0,np.sin(angle),0]);return np.column_stack([blade,guard,np.cross(blade,guard)])@context['localWeaponFrame'].T
            low,high=np.deg2rad(-80),0.
            for _ in range(24):
                mid=(low+high)/2;tip_y=target[1]+(hand_at_angle(mid)@context['tipLocal'][:3])[1]
                if tip_y<6/factor:low=mid
                else:high=mid
            desired=hand_at_angle((low+high)/2);metrics=solve_left(g,pose,target,desired,-tangent+np.array([0,-.3,0]),(26,27,28));metrics['runtimeSeconds']=float(t);carry.append(metrics)
            for finger in range(29,44):pose[(finger,'rotation')]=np.asarray(g.json['nodes'][finger].get('rotation',[0,0,0,1]),float)
        metadata['deathSwordCarry']=carry;metadata['bladeTipGroundTargetCm']=6.;metadata['deathSwordPolicy']='Actual-length right-arm IK carries blade outside body and angles tip toward ground during collapse; no body lift or mesh edits.'
    if label in ('stagger','jump') and hold_profile is not None:
        stage=build(g,poses,times,label);context=setup(stage,hold_profile);sign=int(hold_profile.get('twistSign',-1));hold=[]
        for pose,t in zip(poses,times):
            rotations,m=solve_hold(stage,float(t),hold_profile,context,sign)
            for node,q in rotations.items():pose[(node,'rotation')]=q
            for finger in range(29,44):pose[(finger,'rotation')]=np.asarray(g.json['nodes'][finger].get('rotation',[0,0,0,1]),float)
            hold.append(m)
        metadata['rightSafeHoldProfile']=hold_profile;metadata['rightSafeHoldMetrics']=hold
    if label=='heal':
        # Mirrored source gesture is a guide. Contact uses measured helmet surface and actual left-arm lengths.
        originalworld=g.skinned_positions();_,p,_,_=primitive(g);j=g.accessor(p['attributes']['JOINTS_0']);w=g.accessor(p['attributes']['WEIGHTS_0']);hv=np.flatnonzero((w*(j==5)).sum(1)>.8);front=hv[np.argmax(originalworld[hv,2])];mouthlocal=(np.linalg.inv(rest[5])@np.r_[originalworld[front],1])[:3]
        normal=unit(rest[3,:3,:3].T@np.array([1.,0,0]));S=np.eye(3)-2*np.outer(normal,normal)
        shoulder_mid=(rest[6,:3,3]+rest[25,:3,3])/2;plane_local=(np.linalg.inv(rest[3])@np.r_[shoulder_mid,1])[:3]
        def mirror_hand(srcW,currentChest):
            right_rest=rest[3,:3,:3].T@rest[28,:3,:3];left_rest=rest[3,:3,:3].T@rest[9,:3,:3];right_pose=srcW[3,:3,:3].T@srcW[28,:3,:3]
            return currentChest[:3,:3]@S@(right_pose@right_rest.T)@S@left_rest
        contactidx=abs(times-.85).argmin();pose=poses[contactidx];_,W=pose_world(g,pose);contactR=mirror_hand(g.world_matrices(0,.9),W[3]);mouth=(W[5]@np.r_[mouthlocal,1])[:3];gripoffset=np.array([.03,-.045,.025]);target=mouth+gripoffset;spoutlocal=contactR.T@(mouth-target);ik=[]
        for pose,t,st in zip(poses,times,sourcetimes):
            _,W=pose_world(g,pose);srcW=g.world_matrices(0,float(st));chest=W[3];srcchest=srcW[3];local=(np.linalg.inv(srcchest)@np.r_[srcW[28,:3,3],1])[:3];local-=2*normal*np.dot(local-plane_local,normal);mirrored=(chest@np.r_[local,1])[:3];oldleft=W[9,:3,3];reachweight=float(smooth(t/.35)*(1-smooth((t-1.0)/.25)));target=(1-reachweight)*oldleft+reachweight*mirrored
            desired=mirror_hand(srcW,chest);mouth=(W[5]@np.r_[mouthlocal,1])[:3];contact=float(smooth((t-.3)/.3)*(1-smooth((t-.9)/.2)));drinktarget=mouth+gripoffset;target=target*(1-contact)+drinktarget*contact;desired=align(desired@spoutlocal,mouth-target)@desired if contact>.001 else desired
            oldleftrot={node:pose[(node,'rotation')].copy() for node in [7,8,9]}
            pole=np.array([1.,-.15,.15]);metrics=solve_left(g,pose,target,desired,pole)
            if reachweight<1:
                for node in [7,8,9]:pose[(node,'rotation')]=blend({(node,'rotation'):oldleftrot[node]},{(node,'rotation'):pose[(node,'rotation')]},reachweight)[(node,'rotation')]
            metrics.update({'runtimeSeconds':float(t),'contactWeight':contact,'mouthTargetWorld':mouth.tolist()});ik.append(metrics)
        # Return fully to neutral left-arm pose by completion, never to a residual drinking hold.
        for pose,t in zip(poses,times):
            a=float(smooth((t-1.)/.25))
            if a:
                for node in [7,8,9]:pose[(node,'rotation')]=blend({(node,'rotation'):pose[(node,'rotation')]},{(node,'rotation'):neutral[(node,'rotation')]},a)[(node,'rotation')]
        profile=hold_profile
        if profile is None:raise ValueError('Heal requires explicit reviewed hold profile')
        stage=build(g,poses,times,label);context=setup(stage,profile);signs=[]
        for sign in (-1,1):
            _,m=solve_hold(stage,.85,profile,context,sign);signs.append((m['wristRotationFromReferenceDegrees']+.25*m['elbowRotationFromReferenceDegrees'],sign))
        sign=int(profile.get('twistSign',min(signs)[1]));hold=[]
        for pose,t in zip(poses,times):
            rotations,m=solve_hold(stage,float(t),profile,context,sign)
            for node,q in rotations.items():pose[(node,'rotation')]=q
            for finger in range(29,44):pose[(finger,'rotation')]=np.asarray(g.json['nodes'][finger].get('rotation',[0,0,0,1]),float)
            hold.append(m)
        metadata.update({'measuredMouthSourceVertex':int(front),'mouthTargetHeadLocal':mouthlocal.tolist(),'flaskSpoutFromLeftHandLocal':spoutlocal.tolist(),'flaskGripToSpoutCm':float(np.linalg.norm(spoutlocal)*factor),'contactRuntimeSeconds':.85,'flaskGeometryAuthored':False,'leftIK':ik,'rightFingerPolicy':'All RightHand descendant rotations use original closed reference grip','rightSafeHoldProfile':profile,'rightSafeHoldHelperSHA256':sha(Path(__file__).with_name('author_knight_hold.py')),'rightSafeHoldTwistSign':sign,'rightSafeHoldMetrics':hold,'limitation':'Measured helmet-front target represents drinking location; flask prop/socket rendering must be added and visually checked by integration owner.'})
    derived=build(g,poses,times,label);payload=derived.bytes();checks=[];before_rest=g.skinned_positions();after_rest=derived.skinned_positions()
    if not np.array_equal(before_rest,after_rest):raise ValueError('Rest skin changed')
    for key in ['nodes','meshes','skins','materials','textures','images']:
        if derived.json.get(key)!=g.json.get(key):raise ValueError('Non-animation declaration changed: '+key)
    if bytes(derived.binary[:len(g.binary)])!=bytes(g.binary):raise ValueError('Original binary geometry/skin data changed')
    restlength=np.array([np.linalg.norm(rest[n,:3,3]-rest[parent,:3,3]) for n,parent in g.parents.items()]);maxlength=0.;body=body_vertices(g)
    for t in times:
        W=derived.world_matrices(0,float(t));xyz=derived.skinned_positions(0,float(t));length=np.array([np.linalg.norm(W[n,:3,3]-W[parent,:3,3]) for n,parent in g.parents.items()]);error=float(np.abs(length-restlength).max());maxlength=max(maxlength,error)
        if error>2e-6 or not np.all(np.isfinite(xyz)):raise ValueError('Bone length or finite check failed')
        checks.append({'seconds':float(t),'bodyMinimumYcm':float(xyz[body,1].min()*factor),'hipsYcm':float(W[0,1,3]*factor),'maxBoneLengthErrorCm':error*factor})
    if label=='heal':
        W=derived.world_matrices(0,.85);tip=(W[9]@np.r_[metadata['flaskSpoutFromLeftHandLocal'],1])[:3];mouth=(W[5]@np.r_[metadata['mouthTargetHeadLocal'],1])[:3];metadata['flaskContactResidualCm']=float(np.linalg.norm(tip-mouth)*factor)
        if metadata['flaskContactResidualCm']>.5:raise ValueError('Flask contact target failed')
    report={'status':'AUTHORED_ACTION_CPU_CANDIDATE_NATIVE_REVIEW_REQUIRED','action':label,'source':source.name,'sourceSHA256':sourcehash,'readyDonor':ready_path.name,'readyDonorSHA256':readyhash,'output':output.name,'outputSHA256':hashlib.sha256(payload).hexdigest(),'durationSeconds':duration,'sampleFPS':60,'geometryWeightsTexturesRestNodesPreserved':True,'boneLengthMaxErrorCm':maxlength*factor,'noNonfiniteValues':True,'metadata':metadata,'checks':checks,'nativeAccepted':False}
    if sha(source)!=sourcehash or sha(ready_path)!=readyhash:raise ValueError('Input changed')
    if output.exists() or output.with_suffix('.action.json').exists():raise ValueError('Output exists')
    output.write_bytes(payload);output.with_suffix('.action.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ('action','output','durationSeconds','boneLengthMaxErrorCm')},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--ready',type=Path,required=True);ap.add_argument('--action',choices=['heal','jump','roll','stagger','death'],required=True);ap.add_argument('--duration',type=float);ap.add_argument('--hold-profile',type=Path)
    a=ap.parse_args();duration=a.duration or {'heal':1.25,'jump':1.,'roll':.78,'stagger':.42,'death':4.4}[a.action]
    if a.output.resolve().parent!=ASSETS.resolve() or a.output.exists() or not a.source.resolve().is_relative_to(ASSETS.resolve()):ap.error('Use existing private source and a fresh direct asset output')
    if a.action=='roll' and duration<=.52:ap.error('Roll requires time for crouch recovery')
    profile=json.loads(a.hold_profile.read_text()) if a.hold_profile else None
    author(a.source,a.output,a.action,duration,a.ready,profile)


if __name__=='__main__':main()
