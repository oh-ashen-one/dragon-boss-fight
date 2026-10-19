#!/usr/bin/env python3
"""Center the generated boat weapon on its measured handle, not the hull bounds.

This is a rigid translation only. The small measured shaft taper remains intact;
topology, textures, normals and proportions remain the original Tripo output.
"""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/unreal'))
from normalize_customuse_glb import GLB

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--right-grip-source-y',type=float,default=0.);a=p.parse_args()
    src,dst=a.source.resolve(),a.output.resolve()
    assert src.is_relative_to(ROOT/'Local/art-pass-20261019/tripo') and dst.is_relative_to(src.parent) and not dst.exists()
    g=GLB(src);prims=g.json['meshes'][0]['primitives'];ids=sorted({p['attributes']['POSITION'] for p in prims})
    v=np.concatenate([g.accessor(i).astype(float) for i in ids]);samples=[]
    for y in [a.right_grip_source_y,a.right_grip_source_y-.28]:
        section=v[np.abs(v[:,1]-y)<=.025];assert len(section)>20
        center=(section.min(0)+section.max(0))*.5;center[1]=y;samples.append(center)
    # Right palm is the attachment reference; left residual is below 1cm and
    # fits inside the actual shaft. Do not change the accepted weapon axis.
    shift=-samples[0]
    for i in ids:
        points=g.accessor(i);points[:]=points+shift
        g.json['accessors'][i]['min']=points.min(0).astype(float).tolist();g.json['accessors'][i]['max']=points.max(0).astype(float).tolist()
    v+=shift
    base=v[np.abs(v[:,1]-(.35+shift[1]))<.025].mean(0);tip=v[v[:,1]>v[:,1].max()-.005].mean(0)
    ue=lambda a:[float(a[0]*100),float(a[2]*100),float(a[1]*100)]
    report={'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(g.bytes()).hexdigest(),
            'translationGLTFMeters':shift.tolist(),'rightGripCenterUECm':ue(samples[0]+shift),'leftGripCenterUECm':ue(samples[1]+shift),
            'bladeBaseUECm':ue(base),'bladeTipUECm':ue(tip),'topologyNormalsTexturesUnchanged':True,'nativeVerified':False}
    assert np.linalg.norm((samples[1]+shift)-np.array([0,-.28,0]))<.01
    dst.write_bytes(g.bytes())
    dst.with_suffix('.grip.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
