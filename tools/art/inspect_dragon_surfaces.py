#!/usr/bin/env python3
"""Diagnostic geodesic wing candidates and one exact mouth-surface island.

No skin, skeleton, geometry or animation edits. Color-only GLB derivatives and
source-index masks require anatomical review before any corrective weighting.
Wing regions use mesh-edge distances from audited wing/body seeds, not boxes.
"""
import argparse
from collections import Counter
import copy
import heapq
import json
from pathlib import Path

import numpy as np
from inspect_weapon_topology import GLB, ASSETS, sha, primitive, topology, highlight


def nearest(points, target):
    return int(np.argmin(np.einsum('ij,ij->i', points-target, points-target)))


def coverage_sample(points, count=64):
    chosen = [int(np.argmax(points[:, 2]))]
    distance = np.sum((points-points[chosen[0]])**2, axis=1)
    for _ in range(min(count, len(points))-1):
        i = int(np.argmax(distance)); chosen.append(i)
        distance = np.minimum(distance, np.sum((points-points[i])**2, axis=1))
    return np.asarray(chosen, dtype=int)


def dijkstra(adjacency, seeds):
    distance = np.full(len(adjacency), np.inf)
    heap = []
    for i in sorted(set(seeds)):
        distance[i] = 0.; heap.append((0., i))
    heapq.heapify(heap)
    while heap:
        cost, v = heapq.heappop(heap)
        if cost != distance[v]: continue
        for w, length in adjacency[v]:
            new = cost+length
            if new < distance[w]:
                distance[w] = new; heapq.heappush(heap, (new, w))
    return distance


def colored(g, p, triangle_labels, path):
    derived = GLB(g.bytes()); node, _, _, triangles = primitive(derived)
    triangles = triangles.copy()  # Buffer append may relocate its backing memory.
    prefix = bytes(g.binary)
    colors = {1: ('positive_Z_wing_candidate', [.05, 1., .12, 1.]),
              2: ('negative_Z_wing_candidate', [.08, .35, 1., 1.]),
              3: ('ambiguous_geodesic_boundary', [1., .65, .02, 1.])}
    material_ids = {0: p.get('material', 0)}
    for label, (name, color) in colors.items():
        material_ids[label] = len(derived.json['materials'])
        derived.json['materials'].append({'name': 'INSPECTION_ONLY_'+name,
            'pbrMetallicRoughness': {'baseColorFactor': color, 'metallicFactor': 0, 'roughnessFactor': 1},
            'extensions': {'KHR_materials_unlit': {}}, 'doubleSided': True})
    derived.json.setdefault('extensionsUsed', [])
    if 'KHR_materials_unlit' not in derived.json['extensionsUsed']: derived.json['extensionsUsed'].append('KHR_materials_unlit')
    parts = []
    for label in sorted(set(triangle_labels.tolist())):
        values = triangles[triangle_labels == label].astype('<u4').reshape(-1)
        derived.binary.extend(b'\0'*(-len(derived.binary)%4)); offset = len(derived.binary)
        derived.binary.extend(values.tobytes()); view = len(derived.json['bufferViews'])
        derived.json['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':values.nbytes,'target':34963})
        ai = len(derived.json['accessors']); derived.json['accessors'].append({'bufferView':view,'componentType':5125,
            'count':len(values),'type':'SCALAR','min':[int(values.min())],'max':[int(values.max())]})
        parts.append({'attributes':copy.deepcopy(p['attributes']),'indices':ai,'mode':4,'material':material_ids[label]})
        assert np.array_equal(derived.accessor(ai).reshape(-1,3),triangles[triangle_labels==label])
    derived.json['meshes'][node['mesh']]['primitives'] = parts
    derived.json['buffers'][0]['byteLength'] = len(derived.binary)
    assert bytes(derived.binary[:len(prefix)]) == prefix
    assert sum(derived.accessor(x['indices']).size for x in parts) == triangles.size
    assert derived.json['nodes']==g.json['nodes'] and derived.json['skins']==g.json['skins']
    path.write_bytes(derived.bytes())
    return {'file':path.name,'sha256':sha(path),'geometrySkinTexturesAndOriginalBinaryUnchanged':True,'allTrianglesPreservedOnce':True}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--mouth-component',type=int,default=3469)
    ap.add_argument('--wing-joints',nargs='+',default=['bone_36','bone_37','tripo::Head_2','tripo::Head_3'])
    ap.add_argument('--body-joints',nargs='+',default=['tripo::Spine_0','tripo::Spine_1','bone_18','bone_4','bone_5','bone_9','bone_14','tripo::0_Left_Limb_3','tripo::1_Right_Limb_4','tripo::0_Right_Limb_4','tripo::Tail_0','tripo::Tail_1','tripo::Tail_2'])
    args=ap.parse_args();out=args.output_dir.resolve()
    if not out.is_relative_to(ASSETS.resolve()) or out==ASSETS.resolve():raise ValueError('Use a new ignored asset subdirectory')
    out.mkdir(parents=True,exist_ok=False)
    source_hash=sha(args.source);g=GLB(args.source);node,p,pos,tris=primitive(g)
    groups,inv,step=topology(pos,tris,1e-6);main_id=max(groups,key=lambda i:len(groups[i]));main_faces=groups[main_id]
    world=g.skinned_positions();n=int(inv.max())+1
    world_unique=np.zeros((n,3));counts=np.bincount(inv,minlength=n)
    for axis in range(3):world_unique[:,axis]=np.bincount(inv,weights=world[:,axis],minlength=n)/counts
    main_unique=np.unique(inv[tris[main_faces]])
    edges=np.concatenate((inv[tris[:,[0,1]]],inv[tris[:,[1,2]]],inv[tris[:,[2,0]]]))
    edges=np.unique(np.sort(edges,axis=1),axis=0);edges=edges[edges[:,0]!=edges[:,1]]
    adjacency=[[] for _ in range(n)]
    for (a,b),length in zip(edges,np.linalg.norm(world_unique[edges[:,0]]-world_unique[edges[:,1]],axis=1)):
        adjacency[int(a)].append((int(b),float(length)));adjacency[int(b)].append((int(a),float(length)))
    skin=g.json['skins'][node['skin']];names=[g.json['nodes'][j].get('name','') for j in skin['joints']]
    wing_indices=[names.index(x) for x in args.wing_joints]
    joints=g.accessor(p['attributes']['JOINTS_0']);weights=g.accessor(p['attributes']['WEIGHTS_0'])
    wing_weight=(np.isin(joints,wing_indices)*weights).sum(1)
    eligible=np.flatnonzero(wing_weight>.85);eligible=eligible[np.isin(inv[eligible],main_unique)]
    if len(eligible)<64:raise ValueError('Insufficient audited positive-wing core')
    worlds=g.world_matrices();spines=[names.index(x) for x in ['tripo::Spine_0','tripo::Spine_1','tripo::Spine_2','tripo::Spine_3']]
    plane=float(np.median(worlds[np.asarray(skin['joints'])[spines],2,3]))
    if np.mean(world[eligible,2]>plane)<.95:raise ValueError('Audited positive-wing seed set crosses body plane')
    core=eligible[coverage_sample(world[eligible])];positive=inv[core]
    mirrored=world[core].copy();mirrored[:,2]=2*plane-mirrored[:,2]
    negative=np.asarray([main_unique[nearest(world_unique[main_unique],x)] for x in mirrored])
    body_positions=[worlds[skin['joints'][names.index(x)],:3,3] for x in args.body_joints]
    body=np.asarray([main_unique[nearest(world_unique[main_unique],x)] for x in body_positions])
    seeds=[body,positive,negative];distances=np.array([dijkstra(adjacency,s) for s in seeds])
    labels=np.argmin(distances,axis=0);ordered=np.sort(distances,axis=0)
    with np.errstate(invalid='ignore'):gap=ordered[1]-ordered[0]
    length=float(np.ptp(world,axis=0).max());band=length*.015
    vertex_labels=labels[inv];vertex_gap=gap[inv]
    detached=[]
    # Detached islands are assigned as whole surfaces by nearest main surface for display only.
    for cid,faces in groups.items():
        if cid==main_id:continue
        vi=np.unique(tris[faces]);center=world[vi].mean(0);near=main_unique[nearest(world_unique[main_unique],center)]
        label=int(labels[near]);vertex_labels[vi]=label;vertex_gap[vi]=gap[near]
        detached.append({'componentId':int(cid),'triangleCount':len(faces),'center':center.tolist(),
                         'nearestMainDisplayLabel':label,'distanceToMainSurface':float(np.linalg.norm(center-world_unique[near]))})
    tri_labels=np.zeros(len(tris),dtype=np.int32)
    for i,t in enumerate(tris):
        ls=vertex_labels[t]
        if np.all(ls==1) and np.all(vertex_gap[t]>band):tri_labels[i]=1
        elif np.all(ls==2) and np.all(vertex_gap[t]>band):tri_labels[i]=2
        elif np.any(ls!=0):tri_labels[i]=3
    masks={}
    for label,name in [(1,'positiveZWing'),(2,'negativeZWing')]:
        vi=np.flatnonzero(vertex_labels==label);core_vi=vi[vertex_gap[vi]>band]
        masks[name]={'candidateVertexIndices':vi.tolist(),'coreVertexIndices':core_vi.tolist(),
                     'transitionVertexIndices':vi[vertex_gap[vi]<=band].tolist(),
                     'fullyInteriorTriangleIndices':np.flatnonzero(np.all(vertex_labels[tris]==label,axis=1)).tolist()}
    mouth_faces=groups[args.mouth_component];mouth_vertices=np.unique(tris[mouth_faces]);mouth_mask=np.zeros(len(tris),dtype=bool);mouth_mask[mouth_faces]=True
    mouth_edges=Counter()
    for tri in inv[tris[mouth_faces]]:
        for a,b in [(tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])]:mouth_edges[tuple(sorted((int(a),int(b))))]+=1
    masks['mouthIsland']={'componentId':args.mouth_component,'vertexIndices':mouth_vertices.tolist(),'triangleIndices':mouth_faces.tolist(),
                          'semanticStatus':'UNCONFIRMED: may be inner-mouth/tongue/lower-jaw surface; root must inspect before any jaw weighting',
                          'centerWorld':world[mouth_vertices].mean(0).tolist(),'boundsWorld':[world[mouth_vertices].min(0).tolist(),world[mouth_vertices].max(0).tolist()],
                          'boundaryEdges':sum(v==1 for v in mouth_edges.values()),'nonmanifoldEdges':sum(v>2 for v in mouth_edges.values())}
    manifest={'status':'ANATOMICAL_REVIEW_REQUIRED_NO_CORRECTIVE_WEIGHTS_APPLIED','sourceFile':args.source.name,'sourceSHA256':source_hash,
              'meshIndex':node['mesh'],'primitiveIndex':0,'masks':masks,'selectionMethod':'Shortest paths on welded triangle edges from audited positive-wing skin cores, mirrored surface seeds, and explicit body bone anchors. No box-based region cut.',
              'uncertaintyBandWorldUnits':band,'uncertaintyBandIsNotAWeightPrescription':True}
    (out/'surface-candidates.json').write_text(json.dumps(manifest,indent=2))
    report={'sourceFile':args.source.name,'sourceSHA256':source_hash,'triangles':len(tris),'components':len(groups),'mainComponentId':main_id,
            'mainComponentTriangles':len(main_faces),'bodyPlaneZ':plane,'wingSeedJointNames':args.wing_joints,'bodySeedJointNames':args.body_joints,
            'seedPositions':{'body':world_unique[body].tolist(),'positiveWing':world_unique[positive].tolist(),'negativeWingMirroredAndSnapped':world_unique[negative].tolist()},
            'wingCandidates':{k:{'vertices':len(v['candidateVertexIndices']),'coreVertices':len(v['coreVertexIndices']),'transitionVertices':len(v['transitionVertexIndices']),'interiorTriangles':len(v['fullyInteriorTriangleIndices'])} for k,v in masks.items() if k!='mouthIsland'},
            'mouthCandidate':{k:v for k,v in masks['mouthIsland'].items() if k not in ('vertexIndices','triangleIndices')},'detachedComponents':detached,
            'legend':{'originalMaterial':'body or unclassified surface','green':'positive-Z wing core candidate','blue':'negative-Z wing core candidate','yellow':'mixed/uncertain geodesic boundary','redInMouthFile':'exact disconnected mouth island only'},
            'limitations':['Geodesic seeds are evidence-backed candidates, not an accepted anatomical boundary.','Mirroring assumes approximate bilateral wing correspondence and is explicitly reviewable.','Shared main-component topology means wing cut boundaries need review; no vertices were cut, welded or moved.','The mouth island cannot yet be called the complete lower jaw.','No new bones, weights or motion were authored.']}
    report['wingHighlight']=colored(g,p,tri_labels,out/'wing-geodesic-highlight.glb')
    report['mouthHighlight']=highlight(g,p,mouth_mask,out/'mouth-island-highlight.glb')
    assert sha(args.source)==source_hash;report['sourceUnchanged']=True
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('components','mainComponentTriangles','wingCandidates','mouthCandidate','sourceUnchanged')},indent=2))


if __name__=='__main__':main()
