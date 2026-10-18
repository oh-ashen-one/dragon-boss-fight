#!/usr/bin/env python3
"""Experimental, reviewed-mask dragon rig correction; never alter mesh geometry.

Adds independently parented mirrored wing branches and a head-parented jaw.
Wing geodesic transition weights vanish at reviewed selection boundaries.
Jaw hinge falloff is anatomical; fused lip topology currently rejects opening.
Use dormant jaw mode for the safe wing-correction foundation. Requires
explicit source-hashed masks and records rest equivalence + isolated CPU probes.
The resulting rig is an experimental candidate, not native visual acceptance.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from inspect_weapon_topology import GLB, ASSETS, primitive, topology, sha
from inspect_dragon_surfaces import dijkstra


def quat(matrix):
    # Stable symmetric eigenproblem for a proper orthogonal rotation matrix.
    r = matrix
    k = np.array([[r[0,0]-r[1,1]-r[2,2], r[1,0]+r[0,1], r[2,0]+r[0,2], r[2,1]-r[1,2]],
                  [r[1,0]+r[0,1], r[1,1]-r[0,0]-r[2,2], r[2,1]+r[1,2], r[0,2]-r[2,0]],
                  [r[2,0]+r[0,2], r[2,1]+r[1,2], r[2,2]-r[0,0]-r[1,1], r[1,0]-r[0,1]],
                  [r[2,1]-r[1,2], r[0,2]-r[2,0], r[1,0]-r[0,1], np.trace(r)]])/3
    _, vectors = np.linalg.eigh(k); q = vectors[:,-1]
    return q if q[3] >= 0 else -q


def qmul(a,b):
    return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]), a[3]*b[3]-np.dot(a[:3],b[:3])]


def append_accessor(g, values, kind, component=5126):
    values=np.ascontiguousarray(values,dtype={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[component])
    g.binary.extend(b'\0'*(-len(g.binary)%4));offset=len(g.binary);g.binary.extend(values.tobytes())
    vi=len(g.json['bufferViews']);g.json['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':values.nbytes})
    ai=len(g.json['accessors']);g.json['accessors'].append({'bufferView':vi,'componentType':component,'count':len(values),'type':kind})
    g.json['buffers'][0]['byteLength']=len(g.binary)
    return ai


def smoothstep(x):
    x=np.clip(x,0.,1.);return x*x*(3.-2.*x)


def graph(pos,tri,world):
    _,inv,_=topology(pos,tri,1e-6);n=int(inv.max())+1;count=np.bincount(inv,minlength=n)
    unique=np.column_stack([np.bincount(inv,weights=world[:,a],minlength=n)/count for a in range(3)])
    edges=np.unique(np.sort(np.concatenate([inv[tri[:,[0,1]]],inv[tri[:,[1,2]]],inv[tri[:,[2,0]]]]),axis=1),axis=0)
    adjacency=[[] for _ in range(n)]
    for a,b in edges:
        if a!=b:
            length=float(np.linalg.norm(unique[a]-unique[b]));adjacency[a].append((int(b),length));adjacency[b].append((int(a),length))
    return inv,unique,edges,adjacency


def transition(vertices,inv,edges,adjacency,width):
    selected=np.zeros(len(adjacency),bool);selected[inv[vertices]]=True
    crossing=edges[selected[edges[:,0]]!=selected[edges[:,1]]]
    boundary=np.unique(crossing[np.isin(crossing,np.flatnonzero(selected))])
    if not len(boundary):raise ValueError('No anatomical/body transition boundary found')
    distance=dijkstra(adjacency,boundary)[inv]
    alpha=np.zeros(len(inv));alpha[vertices]=smoothstep(distance[vertices]/width)
    # Disconnected selected islands have infinite distance: fully follow candidate.
    return alpha,{'widthWorld':width,'boundaryWeldedVertices':len(boundary),'blendedVertices':int(np.sum((alpha>0)&(alpha<1))), 'fullVertices':int(np.sum(alpha==1)), 'zeroBoundaryVertices':int(np.sum(alpha[vertices]==0))}


def nearest_batch(source,targets):
    result=[]
    for start in range(0,len(targets),128):
        block=targets[start:start+128]
        d=np.sum((block[:,None,:]-source[None,:,:])**2,axis=2)
        result.extend(np.argmin(d,axis=1).tolist())
    return np.asarray(result)


def add_joint(g,skin,name,parent,world,parentworld):
    local=np.linalg.inv(parentworld)@world;rotation=local[:3,:3]
    if not np.allclose(rotation.T@rotation,np.eye(3),atol=2e-6) or not np.isclose(np.linalg.det(rotation),1,atol=2e-6):
        raise ValueError('New joint orientation is not a proper unit-scale rotation')
    nodeid=len(g.json['nodes']);g.json['nodes'].append({'name':name,'translation':local[:3,3].tolist(),'rotation':quat(rotation).tolist(),'scale':[1,1,1]})
    g.json['nodes'][parent].setdefault('children',[]).append(nodeid);skin['joints'].append(nodeid)
    return nodeid,len(skin['joints'])-1


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--wing-mask',type=Path,required=True);ap.add_argument('--jaw-mask',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--approval-ref',required=True);ap.add_argument('--jaw-mode',choices=['experimental','dormant'],required=True)
    args=ap.parse_args();out=args.output.resolve()
    if out.parent!=ASSETS.resolve() or out.exists():raise ValueError('Use a fresh GLB directly in ignored asset directory')
    wm=json.loads(args.wing_mask.read_text());jm=json.loads(args.jaw_mask.read_text());sourcehash=sha(args.source)
    if wm['sourceSHA256']!=sourcehash or jm['sourceSHA256']!=sourcehash:raise ValueError('Reviewed mask/source mismatch')
    original=GLB(args.source);g=GLB(original.bytes());node,p,pos,tri=primitive(original);tri=tri.copy();world=original.skinned_positions();rest=original.world_matrices()
    if original.json.get('animations'):raise ValueError('Repair base rig only; original has animation')
    if not np.allclose(rest[original.mesh_node()],np.eye(4),atol=1e-6):raise ValueError('Use normalized source')
    skin=g.json['skins'][node['skin']];oldjointcount=len(skin['joints']);names=[g.json['nodes'][n]['name'] for n in skin['joints']];nameidx={n:i for i,n in enumerate(names)}
    attrs=p['attributes'];oldj=original.accessor(attrs['JOINTS_0']).copy();oldw=original.accessor(attrs['WEIGHTS_0']).copy();newj=oldj.copy();neww=oldw.copy()
    ibm=original.accessor(skin['inverseBindMatrices']).copy().reshape(-1,4,4).transpose(0,2,1);newibm=list(ibm.copy())
    inv,u,edges,adj=graph(pos,tri,world)
    posvertices=np.array(wm['masks']['positiveZWing']['candidateVertexIndices']);negvertices=np.array(wm['masks']['negativeZWing']['candidateVertexIndices']);jawvertices=np.array(jm['vertexIndices'])
    if len(set(posvertices)&set(negvertices)) or len(set(jawvertices)&(set(posvertices)|set(negvertices))):raise ValueError('Reviewed region masks overlap')
    # Five-joint positive-side branch: arm root, elbow, membrane tip, wrist branch, leading tip.
    source_names=['tripo::Head_1','bone_36','bone_37','tripo::Head_2','tripo::Head_3'];parents=[None,0,1,0,3]
    bodyidx=nameidx['bone_2'];bodynode=skin['joints'][bodyidx];headnode=skin['joints'][nameidx['bone_5']]
    spine_ids=[nameidx['tripo::Spine_'+str(i)] for i in range(4)];plane=float(np.median(rest[np.array(skin['joints'])[spine_ids],2,3]));reflect=np.diag([1.,1.,-1.])
    controls={};newworld={};chain_indices={};orientation=[]
    for label,mirror in [('PosZ',False),('NegZ',True)]:
        chain_nodes=[];chain_weights=[]
        for i,srcname in enumerate(source_names):
            desired=rest[skin['joints'][nameidx[srcname]]].copy()
            if mirror:
                desired[:3,:3]=reflect@desired[:3,:3]@reflect;desired[2,3]=2*plane-desired[2,3]
            parent=bodynode if parents[i] is None else chain_nodes[parents[i]]
            parentworld=rest[parent] if parent<len(rest) else newworld[parent]
            name='VeyrWing'+label+['Root','Elbow','Membrane','Wrist','Tip'][i]
            nid,ji=add_joint(g,skin,name,parent,desired,parentworld);chain_nodes.append(nid);chain_weights.append(ji);newworld[nid]=desired;newibm.append(np.linalg.inv(desired))
            orientation.append({'name':name,'determinant':float(np.linalg.det(desired[:3,:3])),'restWorld':desired.tolist()})
        controls[label]=chain_nodes;chain_indices[label]=chain_weights
    # Hinge at bilateral mandible rear midpoint measured from reviewed jaw landmarks.
    hinge=np.mean(np.asarray(jm['jawSeedWorld'])[-2:],axis=0);hinge[2]=plane
    jawworld=rest[headnode].copy();jawworld[:3,3]=hinge
    jawnid,jawji=add_joint(g,skin,'VeyrJaw',headnode,jawworld,rest[headnode]);newibm.append(np.linalg.inv(jawworld));controls['Jaw']=[jawnid]
    sourceids=[nameidx[n] for n in source_names]
    # Skin distribution from same-side audited branches; only normalization of these five weights.
    distribution=np.column_stack([np.sum(oldw*(oldj==i),axis=1) for i in sourceids]);total=distribution.sum(1)
    distribution[total>1e-8]/=total[total>1e-8,None];distribution[total<=1e-8,0]=1.
    mirrored=world[negvertices].copy();mirrored[:,2]=2*plane-mirrored[:,2]
    correspondence=posvertices[nearest_batch(world[posvertices],mirrored)]
    mirrorerror=np.linalg.norm(world[correspondence]-mirrored,axis=1)
    blendinfo={};alphas={};changed=np.zeros(len(world),bool);polluted={0,*[nameidx['tripo::Head_'+str(i)] for i in range(4)],nameidx['bone_36'],nameidx['bone_37']}
    for label,vertices,targetdist,targetjoints,width in [('PosZ',posvertices,distribution[posvertices],chain_indices['PosZ'],.025),('NegZ',negvertices,distribution[correspondence],chain_indices['NegZ'],.025),('Jaw',jawvertices,np.ones((len(jawvertices),1)),[jawji],.014)]:
        if label=='Jaw':
            # Blend only at posterior anatomical hinge, not the lip/tooth perimeter.
            # Region membership still comes exclusively from the reviewed topology mask.
            width=.025;alpha=np.zeros(len(world));alpha[vertices]=smoothstep((world[vertices,0]-hinge[0])/width)
            info={'method':'smoothstep forward distance from measured bilateral hinge axis within approved mask only', 'widthWorld':width,'blendedVertices':int(np.sum((alpha>0)&(alpha<1))),'fullVertices':int(np.sum(alpha==1)),'zeroBoundaryVertices':int(np.sum(alpha[vertices]==0))}
        else:alpha,info=transition(vertices,inv,edges,adj,width)
        if label=='Jaw' and args.jaw_mode=='dormant':
            alpha[:]=0.;info={'method':'Dormant jaw: original skin retained because shared lip bridge topology failed opening probes','blendedVertices':0,'fullVertices':0}
        alphas[label]=alpha;blendinfo[label]=info
        for local,vi in enumerate(vertices):
            a=alpha[vi]
            if a<=0:continue
            combined={}
            for joint,weight in zip(oldj[vi],oldw[vi]):
                # At shoulders, remaining support belongs to actual upper body, not polluted wing/root labels.
                joint=int(joint)
                if label!='Jaw' and joint in polluted:joint=bodyidx
                combined[joint]=combined.get(joint,0.)+(1-a)*float(weight)
            for joint,weight in zip(targetjoints,targetdist[local]):combined[joint]=combined.get(joint,0.)+a*float(weight)
            selected=sorted(combined.items(),key=lambda x:-x[1])[:4];total=sum(w for _,w in selected)
            newj[vi]=0;neww[vi]=0
            for slot,(joint,weight) in enumerate(selected):newj[vi,slot]=joint;neww[vi,slot]=weight/total
            changed[vi]=True
    # Accessor replacement, not in-place buffer overwrite: original geometry bytes stay intact.
    dp=g.json['meshes'][node['mesh']]['primitives'][0]
    dp['attributes']['JOINTS_0']=append_accessor(g,newj,'VEC4',5123);dp['attributes']['WEIGHTS_0']=append_accessor(g,neww,'VEC4')
    skin['inverseBindMatrices']=append_accessor(g,np.asarray(newibm).transpose(0,2,1).reshape(-1,16),'MAT4')
    reopened=GLB(g.bytes());newrest=reopened.skinned_positions();delta=np.linalg.norm(newrest-world,axis=1)
    if delta.max()>2e-6:raise ValueError('Rest skin equivalence failed: '+str(delta.max()))
    for name in ('POSITION','NORMAL','TEXCOORD_0'):
        if name in attrs and not np.array_equal(original.accessor(attrs[name]),reopened.accessor(dp['attributes'][name])):raise ValueError('Geometry changed')
    if bytes(reopened.binary[:len(original.binary)])!=bytes(original.binary):raise ValueError('Original binary changed')
    if not np.array_equal(oldj[~changed],newj[~changed]) or not np.array_equal(oldw[~changed],neww[~changed]):raise ValueError('Unselected weights changed')
    if not np.allclose(neww.sum(1),1,atol=3e-7):raise ValueError('Invalid weight normalization')
    # Each probe is an explicit reversible skeletal pose, never a geometry edit.
    probeinfo=[];probefiles=[];probe_dir=out.with_suffix('');probe_dir.mkdir(exist_ok=False)
    def probe(label,nid,axis,degrees,allowed=None):
        d=GLB(reopened.bytes());wmat=d.world_matrices();axis=np.asarray(axis,float);axis/=np.linalg.norm(axis);localaxis=np.linalg.inv(wmat[nid][:3,:3])@axis;localaxis/=np.linalg.norm(localaxis)
        angle=np.deg2rad(degrees);dq=np.r_[localaxis*np.sin(angle/2),np.cos(angle/2)]
        d.json['nodes'][nid]['rotation']=qmul(np.asarray(d.json['nodes'][nid].get('rotation',[0,0,0,1])),dq).tolist()
        result=d.skinned_positions();travel=np.linalg.norm(result-newrest,axis=1);row={'label':label,'joint':d.json['nodes'][nid]['name'],'degrees':degrees,'movedVertices':int(np.sum(travel>1e-7)),'maxTravel':float(travel.max())}
        if allowed is not None:
            outside=~allowed;row['maxOutsideApprovedRegionTravel']=float(travel[outside].max())
            if row['maxOutsideApprovedRegionTravel']>1e-8:raise ValueError('Probe displaced unrelated body')
        row['regionMaxTravel']={k:float(travel[v].max()) for k,v in [('positiveWing',posvertices),('negativeWing',negvertices),('outerJaw',jawvertices)]}
        if not np.all(np.isfinite(result)):raise ValueError('Nonfinite deformation')
        filename=label+'.glb';(probe_dir/filename).write_bytes(d.bytes());probefiles.append(filename);probeinfo.append(row)
    for side,angle in [('PosZ',25),('NegZ',-25)]:
        allowed=alphas[side]>0;probe('wing-'+side+'-25deg',controls[side][0],[1,0,0],angle,allowed)
    for degrees in (-15,-25):probe('jaw-open-'+str(abs(degrees))+'deg',jawnid,[0,0,1],degrees,alphas['Jaw']>0)
    # Four existing leg branches, one at a time. All non-descendant-influenced vertices must remain still.
    legnames=['tripo::1_Left_Limb_0','tripo::0_Left_Limb_1','tripo::1_Right_Limb_1','tripo::0_Right_Limb_1']
    for leg,name in enumerate(legnames):
        nid=skin['joints'][nameidx[name]];desc={nid};stack=[nid]
        while stack:
            for child in reopened.json['nodes'][stack.pop()].get('children',[]):desc.add(child);stack.append(child)
        descj=[i for i,n in enumerate(skin['joints']) if n in desc];allowed=np.any(np.isin(newj,descj)&(neww>0),axis=1)
        probe('leg-'+str(leg)+'-15deg',nid,[0,0,1],15,allowed)
    report={'status':'EXPERIMENTAL_CORRECTIVE_RIG_CPU_PASSED_NATIVE_REVIEW_REQUIRED','approvalReference':args.approval_ref,'sourceFile':args.source.name,'sourceSHA256':sourcehash,'outputFile':out.name,'outputSHA256':hashlib.sha256(reopened.bytes()).hexdigest(),'jointCountBefore':oldjointcount,'jointCountAfter':len(skin['joints']),'jawMode':args.jaw_mode,'changedSkinVertices':int(changed.sum()),'geometryTopologyTexturesAndOriginalBinaryPreserved':True,'unselectedJointWeightBytesUnchanged':True,'restSkinAllVerticesMaxError':float(delta.max()),'restSkinAllVerticesRMSError':float(np.sqrt(np.mean(delta**2))),'blendBands':blendinfo,'mirrorPlaneZ':plane,'mirroredSurfaceCorrespondenceMaxDistance':float(mirrorerror.max()),'mirroredSurfaceCorrespondenceMedianDistance':float(np.median(mirrorerror)),'jointRestTransforms':orientation,'jawHingeWorld':hinge.tolist(),'jawParent':'bone_5','probes':probeinfo,'limitations':['Experimental smooth shoulder/hinge weighting requires native deformation review.','Detached tongue and tooth islands retain original weights; some lower teeth may need separately reviewed attachment.','Original polluted joints remain in skeleton; animate new VeyrWing controls, not legacy Head-labelled wing joints.','No motion clip or gameplay behavior is accepted by these CPU checks.']}
    semantic={'status':report['status'],'sourceSHA256':sourcehash,'rigSHA256':report['outputSHA256'],'coordinateSpace':'glTF RH XYZ, Y up; source units preserved; UE mapping requires importer audit','positiveZWing':[reopened.json['nodes'][n]['name'] for n in controls['PosZ']],'negativeZWing':[reopened.json['nodes'][n]['name'] for n in controls['NegZ']],'jaw':'VeyrJaw','jawActive':args.jaw_mode=='experimental','jawVisualStatus':'Opening rejected: shared lip bridge topology needs separate repair' if args.jaw_mode=='experimental' else 'Dormant joint, no skin weights; topology repair pending','jawParent':'bone_5','head':'bone_5','wingParent':'bone_2','jawHingeWorld':hinge.tolist(),'jawOpenWorldAxis':[0,0,1],'jawOpenAngleSign':-1,'wingFlapWorldAxis':[1,0,0],'wingDownAngleSigns':{'PosZ':1,'NegZ':-1},'legProbeRoots':legnames,'legacyHeadLabelsAreNotHead':True}
    assert sha(args.source)==sourcehash
    out.write_bytes(reopened.bytes());out.with_suffix('.repair.json').write_text(json.dumps(report,indent=2));out.with_suffix('.semantic-map.json').write_text(json.dumps(semantic,indent=2))
    print(json.dumps({k:report[k] for k in ('status','jointCountAfter','changedSkinVertices','restSkinAllVerticesMaxError','blendBands','probes')},indent=2))


def split_main():
    """Duplicate a root-reviewed mouth seam; keep all original triangle faces."""
    import sys
    ap=argparse.ArgumentParser(description=split_main.__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--original-skin',type=Path,required=True)
    ap.add_argument('--seam-mask',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--approval-ref',required=True);args=ap.parse_args(sys.argv[2:])
    out=args.output.resolve()
    if out.parent!=ASSETS.resolve() or out.exists():raise ValueError('Use a new ignored output')
    mask=json.loads(args.seam_mask.read_text());sourcehash=sha(args.source)
    if mask['sourceSHA256']!=sourcehash:raise ValueError('Seam source SHA mismatch')
    src=GLB(args.source);base=GLB(args.original_skin);g=GLB(src.bytes());node,p,pos,tri=primitive(src);tri=tri.copy()
    _,bp,bpos,btri=primitive(base)
    if not np.array_equal(tri,btri) or not np.array_equal(pos,bpos):raise ValueError('Original skin does not match source geometry')
    split=np.asarray(mask['splitVertexIndices'],dtype=int);upperfaces=np.asarray(mask['upperSideTriangleIndices'],dtype=int)
    lowerfaces=np.asarray(mask['jawFaceIndices'],dtype=int);n=len(pos)
    if len(np.unique(split))!=len(split) or np.intersect1d(upperfaces,lowerfaces).size:raise ValueError('Invalid reviewed seam')
    expected_upper=np.flatnonzero((~np.isin(np.arange(len(tri)),lowerfaces)) & np.any(np.isin(tri,split),axis=1))
    if not np.array_equal(expected_upper,upperfaces):raise ValueError('Reviewed upper-side triangle set mismatch')
    oldarrays={name:src.accessor(ai).copy() for name,ai in p['attributes'].items()}
    basej=base.accessor(bp['attributes']['JOINTS_0']).copy();basew=base.accessor(bp['attributes']['WEIGHTS_0']).copy()
    hingevertices=np.asarray(mask.get('continuousHingeBoundaryVertexIndices',[]),dtype=int)
    hingechanged=0
    if len(hingevertices):
        # Root-reviewed underside branch stays topologically continuous, with zero jaw weight.
        inv,u,edges,adj=graph(pos,tri,src.skinned_positions());distance=dijkstra(adj,np.unique(inv[hingevertices]))[inv]
        falloff=smoothstep(distance/float(mask['hingeZeroFalloffWorldWidth']))
        sk=src.json['skins'][node['skin']];jawnode=next(i for i,x in enumerate(src.json['nodes']) if x.get('name')=='VeyrJaw');jawindex=sk['joints'].index(jawnode)
        jawalpha=np.sum(oldarrays['WEIGHTS_0']*(oldarrays['JOINTS_0']==jawindex),axis=1)
        for vi in np.unique(tri[lowerfaces]):
            if jawalpha[vi]<=0 or falloff[vi]>=1:continue
            a=float(jawalpha[vi]*falloff[vi]);combined={}
            for j,w in zip(basej[vi],basew[vi]):combined[int(j)]=combined.get(int(j),0.)+(1-a)*float(w)
            combined[jawindex]=a;selected=sorted(combined.items(),key=lambda x:-x[1])[:4];total=sum(w for _,w in selected)
            oldarrays['JOINTS_0'][vi]=0;oldarrays['WEIGHTS_0'][vi]=0
            for slot,(j,w) in enumerate(selected):oldarrays['JOINTS_0'][vi,slot]=j;oldarrays['WEIGHTS_0'][vi,slot]=w/total
            hingechanged+=1
        if np.any(np.sum(oldarrays['WEIGHTS_0'][hingevertices]*(oldarrays['JOINTS_0'][hingevertices]==jawindex),axis=1)>1e-8):raise ValueError('Underside hinge does not reach zero jaw weight')
    dp=g.json['meshes'][node['mesh']]['primitives'][0];newarrays={}
    for name,ai in p['attributes'].items():
        old=oldarrays[name];duplicate=old[split].copy()
        if name=='JOINTS_0':duplicate=basej[split]
        if name=='WEIGHTS_0':duplicate=basew[split]
        values=np.concatenate([old,duplicate]);newarrays[name]=values
        meta=src.json['accessors'][ai];newai=append_accessor(g,values,meta['type'],meta['componentType'])
        if name=='POSITION':g.json['accessors'][newai].update({'min':values.min(0).tolist(),'max':values.max(0).tolist()})
        dp['attributes'][name]=newai
    remap=np.arange(n);remap[split]=np.arange(n,n+len(split));newtri=tri.copy();newtri[upperfaces]=remap[newtri[upperfaces]]
    dp['indices']=append_accessor(g,newtri.reshape(-1,1),'SCALAR',5125)
    reopened=GLB(g.bytes());before=src.skinned_positions();after=reopened.skinned_positions()
    expected=np.concatenate([np.arange(n),split]);maxrest=float(np.linalg.norm(after-before[expected],axis=1).max())
    if maxrest>2e-6:raise ValueError('Seam rest-equivalence failed')
    # All faces preserve exact source position/normal/UV data after identity remapping.
    for name in oldarrays:
        if name in ('JOINTS_0','WEIGHTS_0'):continue
        if not np.array_equal(newarrays[name][newtri],oldarrays[name][tri]):raise ValueError('Face attribute changed: '+name)
    if bytes(reopened.binary[:len(src.binary)])!=bytes(src.binary):raise ValueError('Original texture/geometry bytes changed')
    names=[x.get('name') for x in reopened.json['nodes']];jawnid=names.index('VeyrJaw');wmat=reopened.world_matrices();localaxis=np.linalg.inv(wmat[jawnid][:3,:3])@np.array([0.,0.,1.]);localaxis/=np.linalg.norm(localaxis)
    probedir=out.with_suffix('');probedir.mkdir(exist_ok=False);checks=[]
    e=np.unique(np.sort(np.concatenate([newtri[:,[0,1]],newtri[:,[1,2]],newtri[:,[2,0]]]),axis=1),axis=0)
    restlen=np.linalg.norm(after[e[:,0]]-after[e[:,1]],axis=1)
    skin=reopened.json['skins'][node['skin']];jawji=skin['joints'].index(jawnid)
    jointarray=newarrays['JOINTS_0'];weightarray=newarrays['WEIGHTS_0'];jawweighted=np.any((jointarray==jawji)&(weightarray>0),axis=1)
    for degrees in (15,25):
        probe=GLB(reopened.bytes());angle=np.deg2rad(-degrees);delta=np.r_[localaxis*np.sin(angle/2),np.cos(angle/2)]
        probe.json['nodes'][jawnid]['rotation']=qmul(np.array(probe.json['nodes'][jawnid]['rotation']),delta).tolist()
        posed=probe.skinned_positions();travel=np.linalg.norm(posed-after,axis=1);length=np.linalg.norm(posed[e[:,0]]-posed[e[:,1]],axis=1)
        outside=float(travel[~jawweighted].max());upper=float(travel[n:].max())
        if outside>1e-8 or upper>1e-8:raise ValueError('Upper lip or unrelated body moved')
        severe=(length>np.maximum(restlen*3,restlen+.01))
        checks.append({'jawDegrees':degrees,'outsideJawWeightedVerticesMaxTravel':outside,'upperSeamDuplicatesMaxTravel':upper,'severeStretchedEdgeCount':int(severe.sum()),'maxEdgeLengthIncrease':float((length-restlen).max()),'maxEdgeRatio':float(np.max(length/np.maximum(restlen,1e-9)))})
        (probedir/('jaw-open-'+str(degrees)+'deg.glb')).write_bytes(probe.bytes())
    report={'status':'SEAM_SPLIT_CPU_VERIFIED_NATIVE_AND_VISUAL_REVIEW_REQUIRED','approvalReference':args.approval_ref,'sourceFile':args.source.name,'sourceSHA256':sourcehash,'originalSkinSHA256':sha(args.original_skin),'outputFile':out.name,'outputSHA256':hashlib.sha256(reopened.bytes()).hexdigest(),'duplicatedVertices':len(split),'continuousUndersideBoundaryVertices':len(hingevertices),'hingeFalloffAdjustedVertices':hingechanged,'vertexCountBefore':n,'vertexCountAfter':n+len(split),'triangleCountBefore':len(tri),'triangleCountAfter':len(newtri),'facesDeleted':0,'newSurfacesAuthored':0,'facePositionsNormalsUVUnchanged':True,'originalBinaryTexturesPreserved':True,'restPositionMaxErrorIncludingDuplicates':maxrest,'upperDuplicateSkinRestoredFromOriginal':True,'jawChecks':checks,'limitations':['A deliberate topological seam now separates upper and lower lip surfaces; native inspection must check visible gaps/interior.','Tongue and detached teeth retain original head weights.','No new inner-mouth geometry was needed for this candidate.']}
    out.write_bytes(reopened.bytes());out.with_suffix('.seam-repair.json').write_text(json.dumps(report,indent=2))
    originalmap=args.source.with_suffix('.semantic-map.json')
    semantic=json.loads(originalmap.read_text());semantic.update({'rigSHA256':report['outputSHA256'],'jawActive':True,'jawVisualStatus':'Seam derivative awaiting CPU/native visual review','seamRepair':out.with_suffix('.seam-repair.json').name})
    out.with_suffix('.semantic-map.json').write_text(json.dumps(semantic,indent=2))
    assert sha(args.source)==sourcehash
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='split':split_main()
    else:main()

