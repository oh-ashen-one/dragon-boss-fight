#!/usr/bin/env python3
"""Original frontal strikes on the reviewed cloth/rigid-sword lineage.

Uses the reviewed ready pose at both endpoints, actual-length arm IK, measured
weapon axes, and explicit runtime timing. Does not change meshes, skin weights,
inverse binds, joint translations/scales or original inputs. Native QA required.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from inspect_weapon_topology import GLB, primitive
from author_knight_hold import setup, PROFILES, game_to_gltf, quaternion, rotation, unit, align, render_pose
from author_knight_actions import sample, build, pose_world, solve_left, sha, smooth


def to_game(v, factor):
    return np.asarray(v)[..., [2, 0, 1]]*np.array([1., -1., 1.])*factor


def slerp(a, b, t):
    a,b=quaternion(a),quaternion(b)
    if np.dot(a,b)<0:b=-b
    d=float(np.clip(np.dot(a,b),-1,1))
    q=unit(a*(1-t)+b*t) if d>.9995 else (np.sin((1-t)*np.arccos(d))*a+np.sin(t*np.arccos(d))*b)/np.sin(np.arccos(d))
    return rotation(q)


def segment_hits(a,b,triangles):
    """Moller-Trumbore segment/triangle intersections (actual skinned body)."""
    direction=b-a;e1=triangles[:,1]-triangles[:,0];e2=triangles[:,2]-triangles[:,0]
    p=np.cross(np.broadcast_to(direction,e2.shape),e2);det=np.sum(e1*p,axis=1)
    valid=np.abs(det)>1e-10;inv=np.zeros_like(det);inv[valid]=1/det[valid]
    t=a-triangles[:,0];u=np.sum(t*p,axis=1)*inv;q=np.cross(t,e1);v=q@direction*inv
    distance=np.sum(e2*q,axis=1)*inv
    return int(np.sum(valid&(u>=0)&(v>=0)&(u+v<=1)&(distance>.0001)&(distance<.9999)))


def author(source, ready_path, output, kind):
    if output.exists() or output.with_suffix('.strike.json').exists():raise ValueError('Use fresh immutable output')
    g=GLB(source);ready=GLB(ready_path);ctx=setup(g,PROFILES['idle']);factor=ctx['factor'];names=ctx['names'];chain=ctx['chain'];upper,fore,hand=chain
    if g.json['nodes']!=ready.json['nodes']:raise ValueError('Ready donor bind hierarchy mismatch')
    neutral=sample(ready,1.5);_,neutralworld=pose_world(g,neutral)
    hold_position=to_game(neutralworld[hand,:3,3],factor);hold_rotation=neutralworld[hand,:3,:3]
    def hand_rotation(direction):
        blade=unit(game_to_gltf(direction));guard=-unit(np.cross([0,1,0],blade))
        return np.column_stack([blade,guard,np.cross(blade,guard)])@ctx['localWeaponFrame'].T
    # Runtime seconds, wrist world position in actor game centimeters, blade
    # axis, chest yaw. Position targets use the actual donor's grounded frame.
    if kind=='LightAttack':
        duration=.85;impact=.522;window=[.425,.664]
        controls=[(0,hold_position,None,0),(.25,[12,88,190],[.45,.65,.60],-8),
                  (.40,[32,78,185],[.75,.35,-.40],-4),(.522,[40,70,180],[.80,-.42,-.43],5),
                  (.664,[35,55,165],[.45,-.86,-.23],10),(.75,[25,60,162],[.75,.10,-.64],3),
                  (.85,hold_position,None,0)]
    else:
        duration=1.2;impact=.617;window=[.53,.73]
        controls=[(0,hold_position,None,0),(.28,[10,75,210],[.15,-.25,.96],-3),
                  (.45,[25,72,210],[.50,-.28,.82],-3),(.617,[40,70,190],[.80,-.42,-.43],4),
                  (.73,[35,75,160],[.80,-.38,-.46],6),(.92,[22,60,162],[.75,.10,-.64],2),
                  (1.2,hold_position,None,0)]
    keys=[(t,np.asarray(pos,float),hold_rotation if axis is None else hand_rotation(axis),yaw) for t,pos,axis,yaw in controls]
    times=np.unique(np.r_[np.linspace(0,duration,round(duration*60)+1),[k[0] for k in keys],window,impact])
    poses=[];ik=[]
    for time in times:
        i=max(0,min(len(keys)-2,int(np.searchsorted([k[0] for k in keys],time,side='right')-1)))
        a,b=keys[i],keys[i+1];weight=float(smooth((time-a[0])/(b[0]-a[0])))
        target=(1-weight)*a[1]+weight*b[1];desired=slerp(a[2],b[2],weight);yaw=(1-weight)*a[3]+weight*b[3]
        pose={key:value.copy() for key,value in neutral.items()}
        spine=names['Spine2'];theta=np.radians(yaw);c,s=np.cos(theta),np.sin(theta);turn=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        parent=g.parents[spine];pose[(spine,'rotation')]=quaternion(neutralworld[parent,:3,:3].T@turn@neutralworld[spine,:3,:3])
        m=solve_left(g,pose,game_to_gltf(target)/factor,desired,neutralworld[fore,:3,3]-neutralworld[upper,:3,3],tuple(chain))
        # Keep upper/forearm axial roll nearest the reviewed hold rather than
        # coupling the entire chain to a rotating blade frame (which can flip).
        _, currentworld=pose_world(g,pose)
        shoulder=currentworld[upper,:3,3];elbow=np.array(m['elbow']);wrist=np.array(m['target'])
        upperR=align(neutralworld[fore,:3,3]-neutralworld[upper,:3,3],elbow-shoulder)@neutralworld[upper,:3,:3]
        foreR=align(neutralworld[hand,:3,3]-neutralworld[fore,:3,3],wrist-elbow)@neutralworld[fore,:3,:3]
        pose[(upper,'rotation')]=quaternion(currentworld[g.parents[upper],:3,:3].T@upperR)
        pose[(fore,'rotation')]=quaternion(upperR.T@foreR)
        pose[(hand,'rotation')]=quaternion(foreR.T@desired)
        if m['targetClampedWorld']*factor>.001:raise ValueError(f'Unreachable wrist at {time}: clamp{m["targetClampedWorld"]*factor}cm')
        if time==0 or time==duration:pose={key:value.copy() for key,value in neutral.items()}
        ik.append({'seconds':float(time),**m});poses.append(pose)
    result=build(g,poses,times,kind)
    # Exact geometry and reference checks before motion probes.
    for field in ['meshes','skins','nodes','materials','textures','images']:
        if g.json.get(field)!=result.json.get(field):raise ValueError('Unexpected structure change '+field)
    for i in range(len(g.json['accessors'])):
        if not np.array_equal(g.accessor(i),result.accessor(i)):raise ValueError('Original accessor changed')
    if not np.array_equal(g.skinned_positions(),result.skinned_positions()):raise ValueError('Reference skin changed')
    _,part,_,faces=primitive(g);skin=g.json['skins'][0];J=g.accessor(part['attributes']['JOINTS_0']);W=g.accessor(part['attributes']['WEIGHTS_0'])
    hand_nodes=set();pending=[hand]
    while pending:
        n=pending.pop();hand_nodes.add(n);pending.extend(g.json['nodes'][n].get('children',[]))
    hand_slots=[i for i,n in enumerate(skin['joints']) if n in hand_nodes]
    grip=np.sum(np.where(np.isin(J,hand_slots),W,0),axis=1)>.5
    weapon=np.zeros(len(J),bool);weapon[ctx['weaponIds']]=True
    body_faces=faces[~np.any((weapon|grip)[faces],axis=1)]
    blade_axis=ctx['localWeaponFrame'][:,0];side=ctx['localWeaponFrame'][:,1];normal=ctx['localWeaponFrame'][:,2]
    local_weapon=(np.linalg.inv(ctx['rest'][hand])@np.column_stack([g.skinned_positions()[ctx['weaponIds']],np.ones(len(ctx['weaponIds']))]).T).T[:,:3]
    weapon_frame=(local_weapon-ctx['baseLocal'][:3])@ctx['localWeaponFrame']
    blade_section=weapon_frame[weapon_frame[:,0]*factor>20]
    half_width,half_thickness=np.max(np.abs(blade_section[:,1:]),axis=0)
    offsets=[(0,0),(-half_width,0),(half_width,0),(0,-half_thickness),(0,half_thickness)]
    bone_edges=[(p,n) for n,p in g.parents.items() if n in skin['joints'] and p in skin['joints']]
    rest=g.world_matrices();lengths=np.array([np.linalg.norm(rest[n,:3,3]-rest[p,:3,3]) for p,n in bone_edges])
    rows=[];max_length=0.;max_angle=0.;previous=None;all_hits=0;hilt_hits=0
    probe_times=np.unique(np.r_[times,(times[1:]+times[:-1])*.5])
    for time in probe_times:
        world=result.world_matrices(0,float(time));vertices=result.skinned_positions(0,float(time));body=vertices[body_faces]
        if not np.isfinite(vertices).all():raise ValueError('Non-finite mesh')
        length=np.array([np.linalg.norm(world[n,:3,3]-world[p,:3,3]) for p,n in bone_edges]);max_length=max(max_length,float(np.abs(length-lengths).max()*factor))
        rotations=world[skin['joints'],:3,:3];rotations=rotations/np.linalg.norm(rotations,axis=-2,keepdims=True)
        if previous is not None:max_angle=max(max_angle,float(np.degrees(np.arccos(np.clip((np.sum(rotations*previous,axis=(1,2))-1)/2,-1,1))).max()))
        previous=rotations
        a=(world[hand]@ctx['baseLocal'])[:3];b=(world[hand]@ctx['tipLocal'])[:3]
        hits=0
        for sy,sz in offsets:
            offset=world[hand,:3,:3]@(side*sy+normal*sz)
            hits+=segment_hits(a+offset,b+offset,body)
        all_hits+=hits
        # Measured crossguard span and grip/pommel axis; right-hand grip skin
        # is excluded, while forearm/torso/left-hand collisions still count.
        guard_center=ctx['baseLocal'][:3]-blade_axis*.035
        ga=(world[hand]@np.r_[guard_center+side*weapon_frame[:,1].min(),1])[:3]
        gb=(world[hand]@np.r_[guard_center+side*weapon_frame[:,1].max(),1])[:3]
        pommel=(world[hand]@np.r_[ctx['baseLocal'][:3]+blade_axis*weapon_frame[:,0].min(),1])[:3]
        hilt=segment_hits(ga,gb,body)+segment_hits(pommel,a,body);hilt_hits+=hilt
        localweapon=(np.linalg.inv(world[hand])@np.column_stack([vertices[ctx['weaponIds']],np.ones(len(ctx['weaponIds']))]).T).T[:,:3]
        rows.append({'seconds':float(time),'baseGameCm':to_game(a,factor).tolist(),'tipGameCm':to_game(b,factor).tolist(),
                     'bladeBodyProbeHits':hits,'hiltBodyProbeHits':hilt,'wholeWeaponMinimumFloorCm':float(vertices[ctx['weaponIds'],1].min()*factor)})
    contacts=[]
    for height in [50.,80.,180.]:
        for reach in [150.,185.,220.]:
            best=1e9;besttime=0
            for row in rows:
                if not window[0]-1e-5<=row['seconds']<=window[1]+1e-5:continue
                a,b=np.array(row['baseGameCm']),np.array(row['tipGameCm']);p=np.array([reach,0,height]);t=np.clip(np.dot(p-a,b-a)/np.dot(b-a,b-a),0,1);d=float(np.linalg.norm(p-a-t*(b-a)))
                if d<best:best=d;besttime=row['seconds']
            contacts.append({'targetGameCm':[reach,0,height],'minimumBladeDistanceCm':best,'atSeconds':besttime,'insideExistingRadius':best<=(108 if height==180 else 83)})
    impact_row=min(rows,key=lambda row:abs(row['seconds']-impact))
    ia,ib=np.array(impact_row['baseGameCm']),np.array(impact_row['tipGameCm'])
    impact_contacts=[]
    for target in contacts:
        point=np.array(target['targetGameCm']);fraction=np.clip(np.dot(point-ia,ib-ia)/np.dot(ib-ia,ib-ia),0,1)
        distance=float(np.linalg.norm(point-ia-fraction*(ib-ia)))
        impact_contacts.append({'targetGameCm':target['targetGameCm'],'bladeDistanceCm':distance,
                                'insideExistingRadius':distance<=(108 if point[2]==180 else 83)})
    endpoint_error=max(float(np.max(np.abs(result.world_matrices(0,t)-neutralworld))) for t in [0,duration])
    report={'status':'ORIGINAL_FRONTAL_STRIKE_CANDIDATE_NATIVE_REVIEW_REQUIRED','source':str(source),'sourceSHA256':sha(source),
            'ready':str(ready_path),'readySHA256':sha(ready_path),'helperSHA256':sha(__file__),'durationSeconds':duration,'startSeconds':0,
            'impactSeconds':impact,'activeWindowSeconds':window,'worldCmPerUnit':factor,'originalGeometryWeightsInverseBindsRestUnchanged':True,
            'allJointTranslationsScalesUnchangedFromReady':True,'readyEndpointWorldMatrixError':endpoint_error,'maximumJointLengthErrorCm':max_length,
            'maximumAdjacentHalfFrameWorldAngleDegrees':max_angle,'bladeBodyProbeHits':all_hits,'hiltBodyProbeHits':hilt_hits,'measuredBladeHalfWidthCm':float(half_width*factor),'measuredBladeHalfThicknessCm':float(half_thickness*factor),'clearanceProbeDescription':'Five actual blade-axis/edge segments vs skinned body triangles; excludes rigid weapon and dominant right-hand grip surfaces. Does not prove full triangle-mesh clearance.',
            'wholeWeaponMinimumFloorCm':min(r['wholeWeaponMinimumFloorCm'] for r in rows),'contactTargets':contacts,'exactImpactContactTargets':impact_contacts,'samples':rows,'IK':ik,'nativeAccepted':False}
    if all_hits or hilt_hits or report['wholeWeaponMinimumFloorCm']<0 or max_length>.001 or endpoint_error>1e-5:
        raise ValueError('Strike rejected: body/floor intersection, bone stretch or ready endpoint mismatch')
    if not all(row['insideExistingRadius'] for row in impact_contacts):
        raise ValueError('Strike rejected: exact contact time misses one or more frontal target probes')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(result.bytes())
    report['outputSHA256']=sha(output)
    with output.with_suffix('.strike.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:report[k] for k in ['outputSHA256','bladeBodyProbeHits','hiltBodyProbeHits','wholeWeaponMinimumFloorCm','maximumJointLengthErrorCm','maximumAdjacentHalfFrameWorldAngleDegrees','contactTargets']}),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--ready',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--kind',choices=['LightAttack','HeavyAttack'],required=True);a=p.parse_args();author(a.source,a.ready,a.output,a.kind)


if __name__=='__main__':main()
