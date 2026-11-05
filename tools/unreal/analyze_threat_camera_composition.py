#!/usr/bin/env python3
"""Read-only camera composition study using actual recorded combat positions.

Tests eye elevation independently from pitch; no animation or engine mutation.
Projection alone cannot establish collision, comfort, or visual acceptance.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def project(points, origins, pitch, yaw, fov):
    p, y = np.radians(pitch), np.radians(yaw)
    forward = np.stack([np.cos(p)*np.cos(y), np.cos(p)*np.sin(y), np.sin(p)], axis=-1)
    right = np.stack([-np.sin(y), np.cos(y), np.zeros_like(y)], axis=-1)
    up = np.cross(forward, right)
    delta = points[None, :, :] - origins[:, None, :]
    depth = np.einsum('npi,ni->np', delta, forward)
    h = np.tan(np.radians(fov/2))[:, None]
    x = .5 + .5*np.einsum('npi,ni->np', delta, right)/(depth*h)
    yy = .5 - .5*np.einsum('npi,ni->np', delta, up)/(depth*h*9/16)
    return x, yy, depth


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    data = json.loads(a.evidence.read_text())
    distance, elevation, pitch, fov = [v.ravel() for v in np.meshgrid(
        np.arange(480, 1281, 40), np.arange(100, 701, 50),
        np.arange(-20, 31, 2), [72,78,84,90,94], indexing='ij')]
    results = []
    for s in data['samples']:
        if not (s['lockedOn'] and s['dragonMove']=='FlyAway' and s['dragonState'] in ['Windup','Active','Recovery']):
            continue
        feet = np.array(s['playerFeet']); head = np.array(s['headPosition'])
        yaw = s['camera']['yaw']; y = np.radians(yaw)
        fw = np.array([np.cos(y),np.sin(y),0]); right=np.array([-np.sin(y),np.cos(y),0])
        points = np.array([feet,feet+[0,0,244],head+[0,0,80],
                           feet+fw*400-right*200, feet+fw*400+right*200])
        origins = feet-distance[:,None]*fw+right*42+elevation[:,None]*[0,0,1]
        xs,ys,zs=project(points,origins,pitch,np.full(len(pitch),yaw),fov)
        # Keep the hero above the bottom HUD and the padded head below boss bar.
        valid=np.all((xs[:,:3]>=.08)&(xs[:,:3]<=.92)&(zs[:,:3]>1),axis=1)
        valid &= np.all((ys[:,:3]>=.14)&(ys[:,:3]<=.88),axis=1)
        hero=ys[:,0]-ys[:,1]
        # Depression angle to the near-floor hazard patch: reject grazing views.
        ground_angle=np.degrees(np.arctan2(elevation,distance+400))
        valid &= ground_angle>=12
        # Prefer readable hero height, then reduce broad FOV/elevation. This is
        # a diagnostic score, not a gameplay quality or acceptance threshold.
        score=hero-.015*((fov-72)/22)**2-.008*((elevation-250)/450)**2
        candidates=np.flatnonzero(valid)
        best=int(candidates[np.argmax(score[candidates])]) if len(candidates) else None
        c=s['camera'];bx,by,bz=project(points,np.array([c['position']]),np.array([c['pitch']]),np.array([yaw]),np.array([c['fieldOfViewDegrees']]))
        results.append({'seconds':s['worldTimeSeconds'],'state':s['dragonState'],
            'existing':{'heroHeightViewport':float(by[0,0]-by[0,1]),'feetY':float(by[0,0]),'headPaddedY':float(by[0,2])},
            'fit':None if best is None else {'distance':float(distance[best]),'eyeElevation':float(elevation[best]),'pitch':float(pitch[best]),'fov':float(fov[best]),'heroHeightViewport':float(hero[best]),'feetY':float(ys[best,0]),'headPaddedY':float(ys[best,2]),'groundDepressionDegrees':float(ground_angle[best])}})
    report={'scope':'Offline geometry only; no rendered, collision, motion or quality acceptance','sourceId':data['sourceId'],'samples':results}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'samples':len(results),'feasible':sum(r['fit'] is not None for r in results),
        'medianExistingHeroHeight':float(np.median([r['existing']['heroHeightViewport'] for r in results])),
        'medianCandidateHeroHeight':float(np.median([r['fit']['heroHeightViewport'] for r in results if r['fit']]))}))


if __name__=='__main__':
    main()
