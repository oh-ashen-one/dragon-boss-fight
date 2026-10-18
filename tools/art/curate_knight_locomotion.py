#!/usr/bin/env python3
"""Curate measured directional loops; retain source footwork and skin geometry.

Read-only analysis ranks actual stance phases after upright heading correction
and planted-sole grounding. Explicit loop windows create new private derivatives.
No source overwrite, engine, provider operation or hidden direction relabeling.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from inspect_weapon_topology import GLB, ASSETS, primitive, EVALUATOR
from author_knight_actions import sample, build, smooth, set_world_hips_y, fixed_heading, solve_left
from author_knight_hold import quaternion, rotation, setup, solve_hold

DIRECTIONS={'StrafeLeft':np.array([1.,0,0]),'StrafeRight':np.array([-1.,0,0]),'Backpedal':np.array([0.,0,-1.])}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def world_pose(g,pose):
    nodes=copy.deepcopy(g.json['nodes'])
    for (n,p),v in pose.items():nodes[n][p]=v.tolist()
    cache={}
    def get(i):
        if i not in cache:
            local=EVALUATOR.trs(nodes[i]);cache[i]=get(g.parents[i])@local if i in g.parents else local
        return cache[i]
    return np.array([get(i) for i in range(len(nodes))])


def yaw(R):
    q=quaternion(R);den=np.linalg.norm(q[[1,3]])
    if den<.7:raise ValueError('Upright heading normalization cannot handle inversion')
    return float(2*np.arctan2(q[1],q[3]))


def world_rotate(g,pose,node,desired,W):
    parent=g.parents.get(node);parentR=W[parent,:3,:3] if parent is not None else np.eye(3);pose[(node,'rotation')]=quaternion(parentR.T@desired)


def foot_sets(g):
    _,p,_,_=primitive(g);J=g.accessor(p['attributes']['JOINTS_0']);W=g.accessor(p['attributes']['WEIGHTS_0'])
    return [np.flatnonzero((np.isin(J,js)*W).sum(1)>.75) for js in [[46,47],[50,51]]]


def prepare(g,source_times):
    rest=g.world_matrices();factor=244/np.ptp(g.skinned_positions()[:,1]);poses=[];heading=[]
    for t in source_times:
        pose=sample(g,float(t));W=world_pose(g,pose);rootyaw=yaw(W[0,:3,:3]@rest[0,:3,:3].T);world_rotate(g,pose,0,fixed_heading(W[0,:3,:3],-rootyaw),W)
        # Locked combat faces the actor's forward direction; preserve pitch/roll and all foot rotations.
        W=world_pose(g,pose);chestyaw=yaw(W[3,:3,:3]@rest[3,:3,:3].T);world_rotate(g,pose,3,fixed_heading(W[3,:3,:3],-chestyaw),W)
        W=world_pose(g,pose);headyaw=yaw(W[5,:3,:3]@rest[5,:3,:3].T);world_rotate(g,pose,4,fixed_heading(W[4,:3,:3],-headyaw*.5),W)
        W=world_pose(g,pose);headyaw2=yaw(W[5,:3,:3]@rest[5,:3,:3].T);world_rotate(g,pose,5,fixed_heading(W[5,:3,:3],-headyaw2),W)
        poses.append(pose);heading.append([rootyaw,chestyaw,headyaw])
    times=source_times-source_times[0];stage=build(g,poses,times,'LocomotionFacingAnalysis');feet=foot_sets(g);soles=[]
    for t in times:
        xyz=stage.skinned_positions(0,float(t));soles.append([float(xyz[f,1].min()) for f in feet])
    soles=np.asarray(soles);offset=-soles.min(1);filtered=np.convolve(np.pad(offset,(2,2),mode='edge'),[.1,.2,.4,.2,.1],mode='valid')
    for pose,off in zip(poses,filtered):W=world_pose(g,pose);set_world_hips_y(g,pose,W[0,1,3]+off)
    return poses,times,{'headingRemovedDegrees':np.rad2deg(heading).tolist(),'soleGroundOffsetsCm':(filtered*factor).tolist(),'sourceSoleYcm':(soles*factor).tolist(),'sourceTimes':source_times.tolist()}


def measurements(g,times,direction):
    factor=244/np.ptp(g.skinned_positions()[:,1]);feet=foot_sets(g);W=np.array([g.world_matrices(0,float(t)) for t in times]);xyz=W[:,:,:3,3]*factor;sole=[]
    for t in times:
        pts=g.skinned_positions(0,float(t))*factor;sole.append([pts[f,1].min() for f in feet])
    sole=np.asarray(sole);velocity=np.gradient(xyz[:,[46,50]],times,axis=0);backward=-np.einsum('tfj,j->tf',velocity,direction);contacts=sole<3.;return xyz,W,sole,velocity,backward,contacts


def rank_windows(g,times,source_times,direction):
    xyz,W,sole,vel,speed,contacts=measurements(g,times,direction);rows=[];legs=[44,45,46,48,49,50]
    for i in range(len(times)):
        for j in range(i+1,len(times)):
            duration=times[j]-times[i]
            if not .65<=duration<=2.6 or source_times[i]<.25:continue
            speeds=[];counts=[];ratios=[]
            for foot in range(2):
                mask=contacts[i:j+1,foot]&(speed[i:j+1,foot]>15)
                values=speed[i:j+1,foot][mask];counts.append(len(values));speeds.append(float(np.median(values)) if len(values) else 0.)
                contact=contacts[i:j+1,foot];allv=speed[i:j+1,foot][contact];ratios.append(float(np.mean(allv>0)) if len(allv) else 0.)
            if min(counts)<4 or min(speeds)<20:continue
            gap=float(np.sqrt(np.mean(np.sum((xyz[i,[46,50]]-xyz[j,[46,50]])**2,axis=1))));vgap=float(np.sqrt(np.mean(np.sum((vel[i]-vel[j])**2,axis=1))));angles=[]
            for n in legs:angles.append(float(np.degrees(np.arccos(np.clip((np.trace(W[i,n,:3,:3].T@W[j,n,:3,:3])-1)/2,-1,1)))))
            rotgap=float(np.mean(angles));hipgap=abs(float(xyz[i,0,1]-xyz[j,0,1]));score=gap+.12*rotgap+.015*vgap+.5*hipgap+20*(1-min(ratios))
            rows.append({'startSource':float(source_times[i]),'endSource':float(source_times[j]),'duration':float(duration),'score':score,'feetEndpointRmsGapCm':gap,'legRotationGapDeg':rotgap,'footVelocityGapCmS':vgap,'hipsYgapCm':hipgap,'medianPositiveStanceSpeedsCmS':speeds,'positiveStanceSamples':counts,'correctStanceDirectionFraction':ratios})
    rows.sort(key=lambda x:x['score']);return rows


def analyze(source,outdir,label):
    g=GLB(source);duration=max(float(g.accessor(s['input']).max()) for s in g.json['animations'][0]['samplers']);source_times=np.arange(1/30,duration-.001,1/30);poses,times,meta=prepare(g,source_times);prepared=build(g,poses,times,label+'_analysis');rows=rank_windows(prepared,times,source_times,DIRECTIONS[label]);outdir.mkdir(parents=True,exist_ok=True)
    report={'source':source.name,'sourceSHA256':sha(source),'runtimeLabel':label,'status':'ANALYZED_NOT_ACCEPTED_LOOP','facingPolicy':'Upright root/chest world-up heading removed; head correction shared across neck/head; pitch/roll and actual leg tracks retained.','groundingPolicy':'Smooth offset from minimum measured weighted sole surface; Hips gait bob is not flattened.','candidates':rows[:20],'candidateCount':len(rows),'preparation':meta}
    (outdir/(label+'-loop-analysis.json')).write_text(json.dumps(report,indent=2));path=outdir/(label+'-analysis.glb')
    if path.exists():raise ValueError('Analysis derivative exists')
    path.write_bytes(prepared.bytes());print(json.dumps({'label':label,'candidates':rows[:5]},indent=2))


def qmul(a,b):
    return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),a[3]*b[3]-np.dot(a[:3],b[:3])]


def face_existing(g,pose):
    rest=g.world_matrices();W=world_pose(g,pose);angle=yaw(W[0,:3,:3]@rest[0,:3,:3].T);world_rotate(g,pose,0,fixed_heading(W[0,:3,:3],-angle),W)
    W=world_pose(g,pose);angle=yaw(W[3,:3,:3]@rest[3,:3,:3].T);world_rotate(g,pose,3,fixed_heading(W[3,:3,:3],-angle),W)
    W=world_pose(g,pose);angle=yaw(W[5,:3,:3]@rest[5,:3,:3].T);world_rotate(g,pose,4,fixed_heading(W[4,:3,:3],-angle*.5),W)
    W=world_pose(g,pose);angle=yaw(W[5,:3,:3]@rest[5,:3,:3].T);world_rotate(g,pose,5,fixed_heading(W[5,:3,:3],-angle),W)


def periodic_closure(poses):
    first,last=copy.deepcopy(poses[0]),copy.deepcopy(poses[-1]);changes={}
    for key in first:
        if key[1]=='rotation':
            inverse=np.r_[-last[key][:3],last[key][3]];delta=qmul(first[key],inverse)
            if delta[3]<0:delta=-delta
            changes[str(key)]={'angularCorrectionDegrees':float(np.degrees(2*np.arccos(np.clip(delta[3],-1,1))))}
        else:changes[str(key)]={'translationCorrection':(first[key]-last[key]).tolist()}
        for i,pose in enumerate(poses):
            a=float(smooth(i/(len(poses)-1)))
            if key[1]=='rotation':pose[key]=qmul(EVALUATOR.slerp(np.array([0.,0,0,1.]),delta,a),pose[key])
            else:pose[key]=pose[key]+a*(first[key]-last[key])
    return changes


def mirror_feet(g,poses):
    rest=g.world_matrices();S=np.diag([-1.,1.,1.]);records=[]
    for pose in poses:
        old=world_pose(g,pose);oldpose=copy.deepcopy(pose)
        # Proper rest-relative reflection of midline orientation, never a negative-scale skeleton.
        for n in range(6):
            W=world_pose(g,pose);desired=S@(old[n,:3,:3]@rest[n,:3,:3].T)@S@rest[n,:3,:3];world_rotate(g,pose,n,desired,W)
        row=[]
        for dest,src,toe,source_toe in [((44,45,46),(48,49,50),47,51),((48,49,50),(44,45,46),51,47)]:
            W=world_pose(g,pose);hip=old[0,:3,3];target=W[0,:3,3]+S@(old[src[2],:3,3]-hip);knee=W[0,:3,3]+S@(old[src[1],:3,3]-hip);footR=S@(old[src[2],:3,:3]@rest[src[2],:3,:3].T)@S@rest[dest[2],:3,:3];pole=knee-W[dest[0],:3,3];metrics=solve_left(g,pose,target,footR,pole,dest)
            W=world_pose(g,pose);toeR=S@(old[source_toe,:3,:3]@rest[source_toe,:3,:3].T)@S@rest[toe,:3,:3];world_rotate(g,pose,toe,toeR,W);row.append(metrics)
        records.append(row)
    return records


def finalize(source,output,label,start,end,profile_file,reverse=False,mirror=False):
    if output.exists() or output.with_suffix('.locomotion.json').exists():raise ValueError('Fresh output required')
    g=GLB(source);sourcehash=sha(source);factor=244/np.ptp(g.skinned_positions()[:,1]);source_times=np.linspace(start,end,round((end-start)*30)+1);poses,times,prep=prepare(g,source_times)
    if reverse:poses=list(reversed(poses))
    mirrorproof=mirror_feet(g,poses) if mirror else None
    # Small distributed closure corrects measured endpoint mismatch, without freezing gait bob.
    closure=periodic_closure(poses)
    for pose in poses:face_existing(g,pose)
    stage=build(g,poses,times,label+'_periodic');feet=foot_sets(g);offset=[]
    for t in times:
        xyz=stage.skinned_positions(0,float(t));offset.append(-min(float(xyz[f,1].min()) for f in feet))
    periodic=np.asarray(offset[:-1]);filtered=np.convolve(np.pad(periodic,(2,2),mode='wrap'),[.1,.2,.4,.2,.1],mode='valid');filtered=np.r_[filtered,filtered[0]]
    for pose,off in zip(poses,filtered):W=world_pose(g,pose);set_world_hips_y(g,pose,W[0,1,3]+off)
    profile=json.loads(profile_file.read_text());profile['wristRelativeHipsGameCm']=list(profile['wristRelativeHipsGameCm']);profile['wristRelativeHipsGameCm'][2]=25.
    stage=build(g,poses,times,label+'_grounded');context=setup(stage,profile);hold=[]
    for pose,t in zip(poses,times):
        rotations,m=solve_hold(stage,float(t),profile,context,int(profile.get('twistSign',-1)))
        for node,q in rotations.items():pose[(node,'rotation')]=q
        for node in range(29,44):pose[(node,'rotation')]=np.array(g.json['nodes'][node].get('rotation',[0,0,0,1]),float)
        hold.append(m)
    derived=build(g,poses,times,label);rest=g.world_matrices();xyz,W,sole,velocity,speed,contacts=measurements(derived,times,DIRECTIONS[label]);stance=[]
    for foot in range(2):
        mask=contacts[:,foot]&(abs(velocity[:,foot,1])<35);values=speed[:,foot][mask];positive=values[values>10]
        stance.append({'foot':'LeftFoot' if foot==0 else 'RightFoot','contactSamples':int(mask.sum()),'signedMedianCmS':float(np.median(values)),'positiveMedianCmS':float(np.median(positive)) if len(positive) else 0.,'correctDirectionFraction':float(np.mean(values>0)),'positive10PercentileCmS':float(np.quantile(positive,.1)) if len(positive) else 0.,'positive90PercentileCmS':float(np.quantile(positive,.9)) if len(positive) else 0.})
    if bytes(derived.binary[:len(g.binary)])!=bytes(g.binary):raise ValueError('Original geometry/skin data changed')
    if not np.array_equal(g.skinned_positions(),derived.skinned_positions()):raise ValueError('Reference skin changed')
    for field in ['meshes','skins','nodes','materials','textures','images']:
        if derived.json.get(field)!=g.json.get(field):raise ValueError('Non-animation data changed')
    length_error=0.
    for n,parent in g.parents.items():
        expected=np.linalg.norm(rest[n,:3,3]-rest[parent,:3,3]);length_error=max(length_error,float(np.abs(np.linalg.norm(W[:,n,:3,3]-W[:,parent,:3,3],axis=1)-expected).max()))
    if length_error>2e-6:raise ValueError('Bone length stretched')
    endpoint=float(np.linalg.norm(xyz[0]-xyz[-1],axis=1).max());rot_error=float(np.max(np.abs(W[0,:,:3,:3]-W[-1,:,:3,:3])))
    if endpoint>1e-3 or rot_error>1e-5:raise ValueError('Loop pose endpoints are not continuous')
    report={'status':'CURATED_DIRECTIONAL_LOOP_CPU_CANDIDATE_NATIVE_REVIEW_REQUIRED','runtimeClip':label,'source':source.name,'sourceSHA256':sourcehash,'output':output.name,'outputSHA256':hashlib.sha256(derived.bytes()).hexdigest(),'sourceWindowSeconds':[start,end],'durationSeconds':float(times[-1]),'sourceAttribution':'Mirrored provider RightStrafe foot trajectories with actual-length opposite-leg IK' if mirror else 'Explicit reversed-time curated forward Walk; rejected generated Backpedal retained separately' if reverse else 'Curated provider RightStrafe human footwork','reverseTime':reverse,'mirroredOppositeLegIK':mirror,'mirrorIKProof':mirrorproof,'headingPolicy':prep,'periodicClosure':closure,'finalGroundOffsetsCm':(filtered*factor).tolist(),'rightCarryProfile':profile,'rightCarryIK':hold,'stanceSpeeds':stance,'hipsBobRangeCm':float(np.ptp(xyz[:,0,1])),'soleYRangeCm':[float(sole.min()),float(sole.max())],'loopEndpointJointPositionMaxGapCm':endpoint,'loopEndpointRotationMatrixMaxGap':rot_error,'maxBoneLengthErrorCm':length_error*factor,'geometryWeightsTexturesRestPreserved':True,'nativeAccepted':False}
    if sha(source)!=sourcehash:raise ValueError('Input changed')
    output.write_bytes(derived.bytes());output.with_suffix('.locomotion.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['runtimeClip','durationSeconds','stanceSpeeds','hipsBobRangeCm','soleYRangeCm','loopEndpointJointPositionMaxGapCm']},indent=2))


def surface_stance_speed(g,times,label):
    xyz,W,sole,velocity,speed,contacts=measurements(g,times,DIRECTIONS[label]);feet=foot_sets(g);factor=244/np.ptp(g.skinned_positions()[:,1]);points=[g.skinned_positions(0,float(t))*factor for t in times];segments=[]
    for foot in range(2):
        indices=np.flatnonzero((sole[:,foot]<3)&(abs(velocity[:,foot,1])<35)&(speed[:,foot]>10))
        for segment in np.split(indices,np.where(np.diff(indices)>1)[0]+1):
            if len(segment)<3:continue
            middle=segment[len(segment)//2];ids=feet[foot];height=points[middle][ids,1];patch=ids[height<=height.min()+.4];centers=np.array([points[i][patch].mean(0) for i in segment]);along=centers@DIRECTIONS[label];coef=np.polyfit(times[segment],along,1);fit=np.polyval(coef,times[segment]);den=float(np.sum((along-along.mean())**2));r2=1-float(np.sum((along-fit)**2))/den if den else 0.
            segments.append({'foot':foot,'start':float(times[segment[0]]),'end':float(times[segment[-1]]),'fixedPatchVertices':patch.tolist(),'surfaceSpeedCmS':float(-coef[0]),'fitR2':r2})
    useful=[x for x in segments if x['surfaceSpeedCmS']>10 and x['fitR2']>.7]
    if not useful:raise ValueError('No credible fixed-sole stance segments')
    weights=np.array([x['end']-x['start'] for x in useful]);speeds=np.array([x['surfaceSpeedCmS'] for x in useful]);return float(np.sum(weights*speeds)/weights.sum()),segments


def expand_stride(source,output,label,stride_scale,target_speed,max_cadence=1.4,max_drop_cm=8.):
    if label not in ('StrafeLeft','StrafeRight') or not 1<stride_scale<=1.8:raise ValueError('Bounded lateral stride scale must be1..1.8')
    if output.exists() or output.with_suffix('.stride.json').exists():raise ValueError('Fresh output required')
    g=GLB(source);sourcehash=sha(source);factor=244/np.ptp(g.skinned_positions()[:,1]);duration=max(float(g.accessor(s['input']).max()) for s in g.json['animations'][0]['samplers']);times=np.linspace(0,duration,round(duration*30)+1);poses=[sample(g,float(t)) for t in times];W=np.array([world_pose(g,p) for p in poses]);direction=DIRECTIONS[label];rest=g.world_matrices();chains=[(44,45,46),(48,49,50)];targets=[];lengths=[]
    for chain in chains:
        ankle=W[:,chain[2],:3,3];along=ankle@direction;center=(along.min()+along.max())/2;targets.append(ankle+(stride_scale-1)*(along-center)[:,None]*direction)
        lengths.append([np.linalg.norm(rest[chain[1],:3,3]-rest[chain[0],:3,3]),np.linalg.norm(rest[chain[2],:3,3]-rest[chain[1],:3,3])])
    drop=None;feasibility=[]
    for cm in np.arange(0,max_drop_cm+.001,1.):
        worst=0.;kneemax=0.
        for foot,chain in enumerate(chains):
            shoulder=W[:,chain[0],:3,3]-np.array([0,cm/factor,0]);reach=np.linalg.norm(targets[foot]-shoulder,axis=1);L1,L2=lengths[foot];worst=max(worst,float((reach/(L1+L2)).max()));kneemax=max(kneemax,float(np.degrees(np.arccos(np.clip((L1*L1+L2*L2-reach*reach)/(2*L1*L2),-1,1))).max()))
        feasibility.append({'pelvisDropCm':float(cm),'maximumReachFraction':worst,'maximumKneeInteriorDegrees':kneemax})
        if worst<=.98 and kneemax<=160:drop=float(cm);break
    if drop is None:raise ValueError('Requested stride exceeds conservative reach/knee bounds: '+json.dumps(feasibility))
    proof=[]
    for i,pose in enumerate(poses):
        set_world_hips_y(g,pose,W[i,0,1,3]-drop/factor);row=[]
        for foot,chain in enumerate(chains):
            current=world_pose(g,pose);pole=W[i,chain[1],:3,3]-W[i,chain[0],:3,3];m=solve_left(g,pose,targets[foot][i],W[i,chain[2],:3,:3],pole,chain);after=world_pose(g,pose);a=after[chain[0],:3,3]-after[chain[1],:3,3];b=after[chain[2],:3,3]-after[chain[1],:3,3];m['kneeInteriorDegrees']=float(np.degrees(np.arccos(np.clip(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1))));upper=after[chain[1],:3,3]-after[chain[0],:3,3];m['frontalUpperLegSwingDegrees']=float(np.degrees(np.arctan2(abs(upper[0]),max(-upper[1],1e-9))));row.append(m)
        proof.append(row)
    stage=build(g,poses,times,label+'_expanded');feet=foot_sets(g);offset=[]
    for t in times:
        pts=stage.skinned_positions(0,float(t));offset.append(-min(float(pts[f,1].min()) for f in feet))
    f=np.convolve(np.pad(np.array(offset[:-1]),(2,2),mode='wrap'),[.1,.2,.4,.2,.1],mode='valid');f=np.r_[f,f[0]]
    for pose,off in zip(poses,f):current=world_pose(g,pose);set_world_hips_y(g,pose,current[0,1,3]+off)
    stage=build(g,poses,times,label+'_expanded_grounded');nominal,segments=surface_stance_speed(stage,times,label);cadence=min(max_cadence,max(1.,target_speed/nominal));final_times=times/cadence;derived=build(g,poses,final_times,label);achieved,final_segments=surface_stance_speed(derived,final_times,label)
    if bytes(derived.binary[:len(g.binary)])!=bytes(g.binary) or not np.array_equal(g.skinned_positions(),derived.skinned_positions()):raise ValueError('Geometry/skin/rest changed')
    world=np.array([derived.world_matrices(0,float(t)) for t in final_times]);length_error=0.
    for n,parent in g.parents.items():
        expected=np.linalg.norm(rest[n,:3,3]-rest[parent,:3,3]);length_error=max(length_error,float(np.abs(np.linalg.norm(world[:,n,:3,3]-world[:,parent,:3,3],axis=1)-expected).max()))
    if length_error>2e-6:raise ValueError('Limb stretch')
    endpoint=float(np.max(np.linalg.norm(world[0,:,:3,3]-world[-1,:,:3,3],axis=1))*factor)
    if endpoint>1e-3:raise ValueError('Loop endpoint lost')
    flat=[x for row in proof for x in row]
    if max(x['targetClampedWorld'] for x in flat)>1e-7:raise ValueError('IK silently clamped a stride target')
    report={'status':'BOUNDED_STRIDE_EXPANSION_CPU_CANDIDATE_NATIVE_LIMIT_REVIEW_REQUIRED','runtimeClip':label,'source':source.name,'sourceSHA256':sourcehash,'output':output.name,'outputSHA256':hashlib.sha256(derived.bytes()).hexdigest(),'lateralStrideExcursionScale':stride_scale,'pelvisDropCm':drop,'cadenceMultiplier':cadence,'durationSeconds':float(final_times[-1]),'targetSurfaceSpeedCmS':target_speed,'expandedSurfaceSpeedBeforeRetimingCmS':nominal,'achievedSurfaceSpeedCmS':achieved,'stanceSegments':final_segments,'feasibility':feasibility,'maximumKneeInteriorDegrees':max(x['kneeInteriorDegrees'] for x in flat),'minimumKneeInteriorDegrees':min(x['kneeInteriorDegrees'] for x in flat),'maximumFrontalUpperLegSwingDegrees':max(x['frontalUpperLegSwingDegrees'] for x in flat),'allIKTargetsReachableWithoutClamp':True,'maxBoneLengthErrorCm':length_error*factor,'loopEndpointJointPositionGapCm':endpoint,'geometryWeightsRestAndUpperBodyRotationsPreserved':True,'groundOffsetsCm':(f*factor).tolist(),'nativeAccepted':False,'limitations':['Frontal swing and knee angle are conservative kinematic checks, not a full anatomical collision model.','Expanded crossed-step leg/armor clearance requires native visual review.','Cadence retiming is explicit and bounded, not hidden movement-speed compensation.']}
    assert sha(source)==sourcehash;output.write_bytes(derived.bytes());output.with_suffix('.stride.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['runtimeClip','durationSeconds','lateralStrideExcursionScale','pelvisDropCm','cadenceMultiplier','achievedSurfaceSpeedCmS','maximumKneeInteriorDegrees','maximumFrontalUpperLegSwingDegrees']},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--label',choices=DIRECTIONS,required=True);ap.add_argument('--analysis-dir',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--start',type=float);ap.add_argument('--end',type=float);ap.add_argument('--profile-json',type=Path);ap.add_argument('--reverse',action='store_true');ap.add_argument('--mirror',action='store_true');ap.add_argument('--stride-scale',type=float);ap.add_argument('--target-speed',type=float,default=160.);a=ap.parse_args()
    if not a.source.resolve().is_relative_to(ASSETS.resolve()):raise ValueError('Private asset source required')
    if a.stride_scale:
        if a.output is None or a.output.resolve().parent!=ASSETS.resolve():raise ValueError('Explicit private stride output required')
        expand_stride(a.source,a.output,a.label,a.stride_scale,a.target_speed)
    elif a.output:
        if a.output.resolve().parent!=ASSETS.resolve() or a.start is None or a.end is None or not a.profile_json:raise ValueError('Explicit private output, window and profile required')
        finalize(a.source,a.output,a.label,a.start,a.end,a.profile_json,a.reverse,a.mirror)
    else:
        if a.analysis_dir is None or not a.analysis_dir.resolve().is_relative_to(ASSETS.resolve()):raise ValueError('Private analysis directory required')
        analyze(a.source,a.analysis_dir,a.label)


if __name__=='__main__':main()
