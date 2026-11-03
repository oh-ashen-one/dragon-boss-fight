#!/usr/bin/env python3
"""Check explicit fortress readiness in native evidence; not a visual quality verdict."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
d=json.loads(a.evidence.read_text());s=d.get('latest',{});issues=[]
if not all(d.get(k) for k in ['finished','passed','finalWrite']):issues.append('Native scenario incomplete or failed')
for k in ['fortressCandidate','fortressAssetsReady','connectedCourtAssetsReady']:
 if s.get(k) is not True:issues.append(k+' absent or false')
for k,n in [('fortressMeshCount',4),('fortressMuralCount',4),('fortressTowerCount',12),('breakablePropCount',8)]:
 if s.get(k)!=n:issues.append(k+' count mismatch')
if d.get('presentationAssets',{}).get('importedCathedral'):issues.append('Legacy cathedral unexpectedly active')
if s.get('overhaulAssetsReady'):issues.append('Legacy overhaul readiness incorrectly claimed')
if d.get('warningContainmentFailures',0):issues.append('Damage escaped committed warning')
r={'mode':d.get('mode'),'passed':not issues,'issues':issues,'sourceId':d.get('sourceId'),'scope':'Native state and asset-count evidence only. Full fortress identity, mural appearance, collision/camera and visual quality need rendered inspection and separate review.'}
if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2));raise SystemExit(bool(issues))
