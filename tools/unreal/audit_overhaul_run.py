#!/usr/bin/env python3
"""Check cross-state camera/contact invariants from actual native replay evidence.
Does not launch a game or reinterpret a failed run as passing.
"""
import argparse,json,math
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
d=json.loads(a.evidence.read_text());samples=d.get('samples',[])+d.get('events',[])+[d.get('latest',{})]
samples=[s for s in samples if isinstance(s,dict) and s.get('seconds',0)>.5]
cameras=[s['camera'] for s in samples if isinstance(s.get('camera'),dict)]
issues=[]
if not(d.get('finished') and d.get('passed') and d.get('finalWrite')):issues.append('Native scenario did not complete successfully')
if not cameras:issues.append('No actual camera samples')
for c in cameras:
 if not math.isclose(c.get('requestedArmCm',-1),560,abs_tol=.2):issues.append('Camera arm changed from close framing');break
for c in cameras:
 if not math.isclose(c.get('fieldOfViewDegrees',-1),72,abs_tol=.1):issues.append('Camera lens changed or FOV evidence missing');break
for s in samples:
 if s.get('warningContainmentFailures',0)>0:issues.append('Contact escaped its committed warning');break
for s in samples:
 if s.get('stamina',0)<-.01 or s.get('stamina',100)>100.01:issues.append('Stamina outside valid range');break
latest=d.get('latest',{})
if not latest.get('overhaulAssetsReady'):issues.append('Generated architecture, destructibles or sky dragons missing')
if latest.get('recordedCuesLoaded',0)!=13 or not latest.get('musicLoaded') or not latest.get('ambienceLoaded'):issues.append('Recorded audio payload incomplete')
states=sorted({s.get('dragonState','') for s in samples});moves=sorted({s.get('dragonMove','') for s in samples})
r={'evidence':str(a.evidence),'nativeScenarioPassed':d.get('passed',False),'cameraSamples':len(cameras),'observedStates':states,'observedMoves':moves,'fixedRequestedCameraCm':560,'fixedFOVDegrees':72,'passed':not issues,'issues':issues,'scope':'Recorded actual scenario states only. Manual input responsiveness, visual fit, audible quality and performance need separate checks.'}
if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2));raise SystemExit(bool(issues))
