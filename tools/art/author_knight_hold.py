#!/usr/bin/env python3
"""Author a review-only one-hand ready/carry pose using exact two-bone IK.

Only the right-arm rotation tracks change; right fingers keep the mesh's closed
reference grip rather than the provider's unrelated finger gestures. Hips, feet, bone
translations/scales, geometry and weights are preserved. Targets follow Hips
position and body heading, with global-up stabilization rather than floor clamps.
Use on cloth-repaired normalized rigid-sword motion; no engine or paid service.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2];ASSETS=ROOT/'Local/CustomuseAssets'
SPEC=importlib.util.spec_from_file_location('veyr_hold_cpu',ROOT/'tools/unreal/normalize_customuse_glb.py')
CPU=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CPU)
PROFILES={
    'idle':{'wristRelativeHipsGameCm':[29.1683849629,54.5967652857,16.929703794],'bladeDirectionGame':[.80,.20,-.56],'elbowPoleGame':[0.,-.6427876096865394,-.766044443118978],'twistSign':-1},
    'walk':{'wristRelativeHipsGameCm':[29.1683849629,54.5967652857,16.929703794],'bladeDirectionGame':[.80,.20,-.56],'elbowPoleGame':[0.,-.6427876096865394,-.766044443118978],'twistSign':-1},
    'run':{'wristRelativeShoulderGameCm':[10.,40.,-20.],'bladeDirectionGame':[.86,.24,-.45],'elbowPoleGame':[0.,-.6427876096865394,-.766044443118978],'twistSign':-1},
}


def unit(v):
    v=np.asarray(v,dtype=float);length=np.linalg.norm(v)
    if length<1e-10:raise ValueError('Degenerate direction')
    return v/length


def rotation(q):return CPU.trs({'rotation':np.asarray(q).tolist()})[:3,:3]


def quaternion(R):
    u,_,v=np.linalg.svd(R);R=u@v;trace=float(np.trace(R))
    if trace>0:
        s=math.sqrt(trace+1)*2;q=np.array([(R[2,1]-R[1,2])/s,(R[0,2]-R[2,0])/s,(R[1,0]-R[0,1])/s,.25*s])
    else:
        i=int(np.argmax(np.diag(R)));j=(i+1)%3;k=(j+1)%3;s=math.sqrt(max(0,1+R[i,i]-R[j,j]-R[k,k]))*2
        q=np.zeros(4);q[i]=.25*s;q[j]=(R[j,i]+R[i,j])/s;q[k]=(R[k,i]+R[i,k])/s;q[3]=(R[k,j]-R[j,k])/s
    return unit(q)


def align(a,b):
    a,b=unit(a),unit(b);v=np.cross(a,b);c=float(np.clip(np.dot(a,b),-1,1));s=np.linalg.norm(v)
    if s<1e-9:
        if c>0:return np.eye(3)
        seed=np.array([1.,0,0]) if abs(a[0])<.8 else np.array([0.,1,0]);axis=unit(np.cross(a,seed))
        return 2*np.outer(axis,axis)-np.eye(3)
    K=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return np.eye(3)+K+K@K*((1-c)/(s*s))


def angle(R):return math.degrees(math.acos(float(np.clip((np.trace(R)-1)/2,-1,1))))


def game_to_gltf(v):
    v=np.asarray(v,dtype=float);return np.array([-v[1],v[2],v[0]])


def setup(model,profile):
    names={n.get('name'):i for i,n in enumerate(model.json['nodes'])}
    chain=[names[n] for n in ['RightArm','RightForeArm','RightHand']]
    if model.parents.get(chain[1])!=chain[0] or model.parents.get(chain[2])!=chain[1]:raise ValueError('Unexpected arm hierarchy')
    rest=model.world_matrices();points=model.skinned_positions();factor=244/np.ptp(points[:,1]);ep=json.loads((ASSETS/'knight-clip-kinematics-20261019-v1.json').read_text())['weaponEndpoints']
    tip=np.asarray(ep['weapon_tip'])[[0,2,1]]/100;base=np.asarray(ep['weapon_base'])[[0,2,1]]/100
    ids=np.asarray(json.loads((ASSETS/'weapon-topology-v1/candidate-mask.json').read_text())['vertexIndices'])
    hand_local=(np.linalg.inv(rest[chain[2]])@np.column_stack([points[ids],np.ones(len(ids))]).T).T[:,:3]
    u=unit(tip-base);_,_,axes=np.linalg.svd(hand_local-hand_local.mean(0),full_matrices=False);v=unit(axes[1]-u*np.dot(axes[1],u))
    frame=np.column_stack([u,v,np.cross(u,v)])
    return {'names':names,'chain':chain,'rest':rest,'factor':float(factor),'localWeaponFrame':frame,'profile':profile,'tipLocal':np.append(tip,1),'baseLocal':np.append(base,1),'weaponIds':ids}


def solve_hold(model,time,profile,context=None,twist_sign=None):
    """Return {nodeIndex: localQuaternion}, plus exact IK targets/metrics."""
    c=context or setup(model,profile);names=c['names'];upper,fore,hand=c['chain'];W=model.world_matrices(0,time);hips=names['Hips'];rest=c['rest'];factor=c['factor']
    twist_sign=profile.get('twistSign',-1) if twist_sign is None else twist_sign
    for node in (upper,fore,hand):
        if not np.allclose(W[node,:3,:3].T@W[node,:3,:3],np.eye(3),atol=2e-5):raise ValueError('Scaled arm chain unsupported')
    body_delta=W[hips,:3,:3]@rest[hips,:3,:3].T;forward=body_delta@np.array([0.,0,1.]);heading=math.atan2(forward[0],forward[2]);co,si=math.cos(heading),math.sin(heading)
    headingR=np.array([[co,0,si],[0,1,0],[-si,0,co]])
    shoulder=W[upper,:3,3];old_elbow=W[fore,:3,3];old_hand=W[hand,:3,3]
    if 'wristRelativeShoulderGameCm' in profile:
        target=shoulder+headingR@game_to_gltf(profile['wristRelativeShoulderGameCm'])/factor
    else:
        target=W[hips,:3,3]+headingR@game_to_gltf(profile['wristRelativeHipsGameCm'])/factor
    L1=np.linalg.norm(old_elbow-shoulder);L2=np.linalg.norm(old_hand-old_elbow);D=target-shoulder;distance=np.linalg.norm(D)
    if not abs(L1-L2)+.001<distance<L1+L2-.001:raise ValueError(f'Unreachable fixed hold target at {time:.4f}s: {distance*factor:.2f}cm vs {(L1+L2)*factor:.2f}cm')
    direction=unit(D);along=(L1*L1-L2*L2+distance*distance)/(2*distance)
    pole=headingR@game_to_gltf(profile.get('elbowPoleGame',[0,.65,-.75]));pole=unit(pole-direction*np.dot(pole,direction))
    elbow=shoulder+direction*along+pole*math.sqrt(max(0,L1*L1-along*along))
    blade=unit(headingR@game_to_gltf(profile['bladeDirectionGame']));guard=unit(np.cross([0,1,0],blade))*twist_sign
    desired_hand=np.column_stack([blade,guard,np.cross(blade,guard)])@c['localWeaponFrame'].T
    hand_ref=rotation(model.json['nodes'][hand].get('rotation',[0,0,0,1]));fore_ref=rotation(model.json['nodes'][fore].get('rotation',[0,0,0,1]))
    hand_translation=np.asarray(model.json['nodes'][hand]['translation']);fore_translation=np.asarray(model.json['nodes'][fore]['translation'])
    # Resolve free axial roll against the reference elbow/wrist convention,
    # then swing onto the exact IK segment directions without changing lengths.
    fore_hint=desired_hand@hand_ref.T
    desired_fore=align(fore_hint@hand_translation,target-elbow)@fore_hint
    upper_hint=desired_fore@fore_ref.T
    desired_upper=align(upper_hint@fore_translation,elbow-shoulder)@upper_hint
    parent=model.parents[upper];parentR=W[parent,:3,:3]
    local_upper=parentR.T@desired_upper;local_fore=desired_upper.T@desired_fore;local_hand=desired_fore.T@desired_hand
    rotations={upper:quaternion(local_upper),fore:quaternion(local_fore),hand:quaternion(local_hand)}
    metrics={'seconds':float(time),'wristTargetGLTF':target.tolist(),'elbowTargetGLTF':elbow.tolist(),
             'upperArmLengthCm':float(L1*factor),'forearmLengthCm':float(L2*factor),'reachCm':float(distance*factor),
             'elbowInteriorDegrees':math.degrees(math.acos(float(np.clip(np.dot(shoulder-elbow,target-elbow)/(L1*L2),-1,1)))),
             'wristRotationFromReferenceDegrees':angle(hand_ref.T@local_hand),'elbowRotationFromReferenceDegrees':angle(fore_ref.T@local_fore),
             'bodyHeadingDegrees':math.degrees(heading)}
    return rotations,metrics


def render_pose(model,time,output,title):
    """Exact CPU-skinned triangle z-buffer; no GPU, engine, Blender or textures."""
    from PIL import Image,ImageDraw,ImageFont
    if output.exists():raise ValueError('Review image already exists')
    P=model.skinned_positions(0,time)*244/np.ptp(model.skinned_positions()[:,1]);node=model.json['nodes'][model.mesh_node()]
    parts=model.json['meshes'][node['mesh']]['primitives']
    if len(parts)!=1:raise ValueError('Review rasterizer expects one primitive')
    faces=model.accessor(parts[0]['indices']).reshape(-1,3);mask=json.loads((ASSETS/'weapon-topology-v1/candidate-mask.json').read_text());orange=np.zeros(len(faces),bool);orange[np.asarray(mask['triangleIndices'])]=True
    image=Image.new('RGB',(1600,1000),(245,247,249));font=ImageFont.load_default(size=19);small=ImageFont.load_default(size=15);draw=ImageDraw.Draw(image)
    draw.text((28,18),title,fill=(25,35,45),font=font);draw.text((28,48),'Actual CPU-skinned mesh | gray body / orange rigid weapon | orthographic | no GPU | native review pending',fill=(55,65,75),font=small)
    low=min(-20,float(P[:,1].min())-8);high=max(265,float(P[:,1].max())+8);width=max(np.ptp(P[:,0]),np.ptp(P[:,2]))+50;scale=min(700/width,820/(high-low))
    N=np.cross(P[faces[:,1]]-P[faces[:,0]],P[faces[:,2]]-P[faces[:,0]]);L=unit([.4,.8,.5]);shade=.38+.62*abs(N@L)/np.maximum(np.linalg.norm(N,axis=1),1e-10)
    for k,(name,u,depths) in enumerate([('FRONT (+Z)',P[:,0],P[:,2]),('RIGHT SIDE (-X)',P[:,2],-P[:,0])]):
        panel=Image.new('RGB',(780,885),(245,247,249));pd=ImageDraw.Draw(panel);uv=np.column_stack([390+(u-(u.min()+u.max())/2)*scale,(high-P[:,1])*scale]);pd.text((20,0),name,fill=(40,50,60),font=font)
        for h in range(0,251,50):
            yy=(high-h)*scale;pd.line((45,yy,755,yy),fill=(215,220,225) if h else (75,90,100),width=1 if h else 2);pd.text((4,yy-7),str(h),fill=(100,110,120),font=small)
        rgb=np.array(panel);z=np.full((885,780),-np.inf)
        for fi,face in enumerate(faces):
            triangle=uv[face];xmin=max(0,int(np.floor(triangle[:,0].min())));xmax=min(779,int(np.ceil(triangle[:,0].max())));ymin=max(0,int(np.floor(triangle[:,1].min())));ymax=min(884,int(np.ceil(triangle[:,1].max())))
            if xmin>xmax or ymin>ymax:continue
            x0,y0=triangle[0];x1,y1=triangle[1];x2,y2=triangle[2];den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            if abs(den)<1e-8:continue
            X,Y=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5);a=((y1-y2)*(X-x2)+(x2-x1)*(Y-y2))/den;b=((y2-y0)*(X-x2)+(x0-x2)*(Y-y2))/den;c=1-a-b;depth=a*depths[face[0]]+b*depths[face[1]]+c*depths[face[2]];patch=z[ymin:ymax+1,xmin:xmax+1];use=(a>=-1e-8)&(b>=-1e-8)&(c>=-1e-8)&(depth>patch)
            if use.any():rgb[ymin:ymax+1,xmin:xmax+1][use]=np.clip(np.array([245,126,27] if orange[fi] else [167,177,187])*shade[fi],0,255).astype(np.uint8);patch[use]=depth[use]
        image.paste(Image.fromarray(rgb),(10+k*800,90))
    output.parent.mkdir(parents=True,exist_ok=True);image.save(output);os.chmod(output,0o600)


def process(source,output,label,profile=None):
    raw=source.read_bytes();g=CPU.GLB(raw);new=CPU.GLB(g.bytes());profile=profile if profile is not None else PROFILES[label];ctx=setup(g,profile)
    clip=g.json['animations'][0];tracks={}
    for node in ctx['chain']:
        channels=[c for c in clip['channels'] if c['target'].get('node')==node and c['target'].get('path')=='rotation']
        if len(channels)!=1:raise ValueError('Expected one rotation channel per arm joint')
        s=clip['samplers'][channels[0]['sampler']]
        if s.get('interpolation','LINEAR')!='LINEAR':raise ValueError('Only LINEAR quaternion tracks supported')
        tracks[node]=(s['input'],s['output'])
    times=g.accessor(next(iter(tracks.values()))[0]).reshape(-1).astype(float)
    if any(not np.array_equal(times,g.accessor(i).reshape(-1)) for i,_ in tracks.values()):raise ValueError('Arm rotation timelines differ')
    representative=min(1.5,float(times[-1]));options=[]
    for sign in (-1,1):
        _,metrics=solve_hold(g,representative,profile,ctx,sign);options.append((metrics['wristRotationFromReferenceDegrees']+.25*metrics['elbowRotationFromReferenceDegrees'],sign))
    sign=profile.get('twistSign',min(options)[1]);key_metrics=[];previous={}
    for index,t in enumerate(times):
        rotations,metrics=solve_hold(g,float(t),profile,ctx,sign);key_metrics.append(metrics)
        for node,q in rotations.items():
            if node in previous and np.dot(previous[node],q)<0:q=-q
            new.accessor(tracks[node][1])[index]=q;previous[node]=q
    changed={output_index for _,output_index in tracks.values()}
    fingers=set();pending=list(g.json['nodes'][ctx['chain'][2]].get('children',[]))
    while pending:
        node=pending.pop();fingers.add(node);pending.extend(g.json['nodes'][node].get('children',[]))
    for channel in clip['channels']:
        node=channel['target'].get('node')
        if node in fingers and channel['target'].get('path')=='rotation':
            accessor=clip['samplers'][channel['sampler']]['output']
            new.accessor(accessor)[:]=unit(g.json['nodes'][node].get('rotation',[0,0,0,1]));changed.add(accessor)
    for i in changed:
        item=new.json['accessors'][i];values=new.accessor(i)
        if 'min'in item:item['min']=values.min(0).tolist()
        if 'max'in item:item['max']=values.max(0).tolist()
    # Every non-arm track/attribute is unchanged, and no translation or scale changes.
    for i in range(len(g.json['accessors'])):
        if i not in changed and not np.array_equal(g.accessor(i),new.accessor(i)):raise ValueError('Unexpected non-arm data edit')
    node=g.json['nodes'][g.mesh_node()];p=g.json['meshes'][node['mesh']]['primitives'][0];skin=g.json['skins'][node['skin']]
    affected=set();pending=[ctx['chain'][0]]
    while pending:
        n=pending.pop();affected.add(n);pending.extend(g.json['nodes'][n].get('children',[]))
    slots=[i for i,n in enumerate(skin['joints']) if n in affected];J=g.accessor(p['attributes']['JOINTS_0']);weights=g.accessor(p['attributes']['WEIGHTS_0']);outside=~np.any(np.isin(J,slots)&(weights>0),axis=1)
    rest_error=float(np.linalg.norm(g.skinned_positions()-new.skinned_positions(),axis=1).max())
    if rest_error!=0:raise ValueError('Reference skin changed')
    checks=[];factor=ctx['factor'];upper,fore,hand=ctx['chain'];indices=np.unique(np.linspace(0,len(times)-1,19).astype(int))
    for index in indices:
        t=float(times[index]);before=g.skinned_positions(0,t);after=new.skinned_positions(0,t);W=new.world_matrices(0,t);target=np.array(key_metrics[index]['wristTargetGLTF']);elbow=np.array(key_metrics[index]['elbowTargetGLTF']);delta=float(np.linalg.norm(before[outside]-after[outside],axis=1).max());wrist_error=float(np.linalg.norm(W[hand,:3,3]-target));elbow_error=float(np.linalg.norm(W[fore,:3,3]-elbow))
        if delta!=0 or max(wrist_error,elbow_error)>1e-5:raise ValueError('IK target or outside-arm invariance failed')
        checks.append({'seconds':t,'outsideArmWorldDelta':delta,'wristTargetResidualCm':wrist_error*factor,'elbowTargetResidualCm':elbow_error*factor,'upperArmLengthCm':float(np.linalg.norm(W[fore,:3,3]-W[upper,:3,3])*factor),'forearmLengthCm':float(np.linalg.norm(W[hand,:3,3]-W[fore,:3,3])*factor),'tipFloorCm':float((W[hand]@ctx['tipLocal'])[1]*factor)})
    payload=new.bytes();report={'status':'AUTHORED_TWO_BONE_HOLD_CANDIDATE_NATIVE_REVIEW_REQUIRED','source':source.name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'derivative':output.name,'derivativeSHA256':hashlib.sha256(payload).hexdigest(),'profile':profile,'twistSign':sign,'changedRotationNodes':['RightArm','RightForeArm','RightHand']+[g.json['nodes'][i]['name'] for i in sorted(fingers)],'rightFingerPolicy':'Fixed source reference grip; no finger translations, geometry or weights changed','translationsScalesGeometryWeightsOtherTracksUnchanged':True,'restSkinUnchanged':True,'keyMetrics':key_metrics,'checks':checks,'nativeAccepted':False}
    if source.read_bytes()!=raw:raise ValueError('Source changed during authoring')
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(payload)
    with os.fdopen(os.open(output.with_suffix('.hold.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({'file':output.name,'wristAngleRange':[min(r['wristRotationFromReferenceDegrees'] for r in key_metrics),max(r['wristRotationFromReferenceDegrees'] for r in key_metrics)],'tipFloorRange':[min(r['tipFloorCm'] for r in checks),max(r['tipFloorCm'] for r in checks)],'maxWristTargetResidualCm':max(r['wristTargetResidualCm'] for r in checks)}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--clip',choices=tuple(PROFILES),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--profile-json',type=Path,help='Optional explicit profile; copied into receipt for reproducibility');a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
    if not source.is_relative_to(ASSETS.resolve()) or output.parent!=ASSETS.resolve() or output.exists() or output.with_suffix('.hold.json').exists():p.error('Use private source and fresh output')
    process(source,output,a.clip,json.loads(a.profile_json.read_text()) if a.profile_json else None)


if __name__=='__main__':main()
