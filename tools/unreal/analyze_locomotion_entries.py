#!/usr/bin/env python3
"""Separate recorded foot displacement into capsule, actor yaw and local pose.

Read-only diagnosis of the instantaneous pair at each gated peak. Vector
magnitudes are not additive percentages, and this does not replace visual QA.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np


def rotation(degrees):
    t=math.radians(degrees)
    return np.array([[math.cos(t),-math.sin(t),0],[math.sin(t),math.cos(t),0],[0,0,1]])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();rows=[json.loads(l) for l in a.frames.read_text().splitlines()]
    result=[]
    for seq in sorted({r['seq'] for r in rows}):
        samples=[r for r in rows if r['seq']==seq]
        index=max(range(1,len(samples)),key=lambda i:max(samples[i]['footSlideCmPerSecond']))
        old,new=samples[index-1:index+1]
        side=int(np.argmax(new['footSlideCmPerSecond']));dt=new['t']-old['t']
        assert dt>0
        ra,rb=rotation(old['actorYawDegrees']),rotation(new['actorYawDegrees'])
        ca,cb=np.asarray(old['capsule']),np.asarray(new['capsule'])
        points={}
        for key in (('toeL','ankleL') if side==0 else ('toeR','ankleR')):
            pa,pb=np.asarray(old[key]),np.asarray(new[key])
            la,lb=ra.T@(pa-ca),rb.T@(pb-cb)
            pieces={'capsule':cb-ca,'actorYaw':(rb-ra)@la,'localPose':rb@(lb-la)}
            error=float(np.max(np.abs(sum(pieces.values())-(pb-pa))))
            assert error<1e-8
            points[key]={'horizontalSpeedComponentsCmS':{k:float(np.linalg.norm(v[:2])/dt) for k,v in pieces.items()},
                         'vectorReconstructionErrorCm':error}
        result.append({'sequence':new['sequence'],'atSeconds':new['t'],'gateWindowPeakCmS':max(new['footSlideCmPerSecond']),
                       'instantaneousPairSeconds':dt,'actorYawDegrees':[old['actorYawDegrees'],new['actorYawDegrees']],
                       'clip':new['clip'],'fromClip':new['blendFrom'],'blendAlpha':new['blendAlpha'],'points':points})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({'scope':__doc__,'sequences':result},indent=2)+'\n')
    print('Locomotion displacement decomposition verified')


if __name__=='__main__':main()
