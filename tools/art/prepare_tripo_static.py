#!/usr/bin/env python3
"""Normalize a private Tripo GLB's scale/pivot without changing its topology or textures.

Source GLBs stay untouched. glTF uses meters and Y up; Unreal Interchange handles
axis conversion. Output pivot is ground center or an explicit grip above the base.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    size=p.add_mutually_exclusive_group(required=True)
    size.add_argument('--height-m',type=float)
    size.add_argument('--width-m',type=float)
    p.add_argument('--flatten-height-m',type=float,help='Optional low-profile paving height; normals/tangents are transformed consistently')
    p.add_argument('--pivot-above-base-m',type=float,default=0.)
    a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
    if not all(x.is_relative_to((ROOT/'Local').resolve()) for x in [source,output]):
        p.error('Use private task-owned art-pass paths')
    target=a.height_m if a.height_m is not None else a.width_m
    if output.exists() or target<=0 or (a.flatten_height_m is not None and a.flatten_height_m<=0):
        p.error('Fresh output and positive dimensions required')
    g=GLB(source);assert not g.json.get('skins') and not g.json.get('animations')
    nodes=[n for n in g.json['nodes'] if 'mesh' in n]
    assert len(nodes)==1 and all(k not in nodes[0] for k in ['matrix','translation','rotation','scale'])
    primitives=g.json['meshes'][nodes[0]['mesh']]['primitives']
    accessors=sorted({q['attributes']['POSITION'] for q in primitives})
    positions=np.concatenate([g.accessor(i) for i in accessors])
    low,high=positions.min(0),positions.max(0)
    assert high[1]>low[1] and np.isfinite(positions).all()
    axis=1 if a.height_m is not None else 0
    scale=target/float(high[axis]-low[axis])
    scales=np.array([scale,scale,scale])
    if a.flatten_height_m is not None:scales[1]=a.flatten_height_m/float(high[1]-low[1])
    center=np.array([(low[0]+high[0])*.5,low[1],(low[2]+high[2])*.5])
    for i in accessors:
        values=g.accessor(i);values[:]=(values-center)*scales-np.array([0,a.pivot_above_base_m,0])
        g.json['accessors'][i]['min']=values.min(0).astype(float).tolist()
        g.json['accessors'][i]['max']=values.max(0).astype(float).tolist()
    if a.flatten_height_m is not None:
        for i in sorted({q['attributes']['NORMAL'] for q in primitives if 'NORMAL' in q['attributes']}):
            values=g.accessor(i);transformed=values/scales
            values[:]=transformed/np.maximum(np.linalg.norm(transformed,axis=1,keepdims=True),1e-12)
        seen=set()
        for q in primitives:
            i=q['attributes'].get('TANGENT')
            if i is None or i in seen:continue
            seen.add(i);values=g.accessor(i);t=values[:,:3]*scales
            n=g.accessor(q['attributes']['NORMAL']);t-=n*np.sum(n*t,axis=1,keepdims=True)
            values[:,:3]=t/np.maximum(np.linalg.norm(t,axis=1,keepdims=True),1e-12)
    # No private provider job IDs in authored object names.
    for collection in ['nodes','meshes','materials','textures','images']:
        for i,item in enumerate(g.json.get(collection,[])):item['name']=output.stem+'_'+collection+'_'+str(i)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(g.bytes())
    receipt={'sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'outputSHA256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'heightMeters':float((high[1]-low[1])*scales[1]),'widthMeters':float((high[0]-low[0])*scales[0]),
        'pivotAboveBaseMeters':a.pivot_above_base_m,'scaleXYZ':scales.tolist(),
        'uniformScale':scale if a.flatten_height_m is None else None,
        'normalsAndTangentsTransformed':a.flatten_height_m is not None,
        'triangles':sum(len(g.accessor(q['indices']))//3 for q in primitives),
        'topologyAndTextureBytesUnchanged':True,'nativeImportVerified':False}
    output.with_suffix('.prepare.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
