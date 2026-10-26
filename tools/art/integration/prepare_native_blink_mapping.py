#!/usr/bin/env python3
"""Prepare v029's native-axis-correct blink bindings without changing source motion.
The v028 collision replay showed negative travel along a requested forward blink.
The rig's native mesh transform reverses the source naming convention, so the
logical left/right clips are exchanged. Gameplay also derives its root basis
from the measured profile instead of assuming an axis from a clip label.
"""
import argparse,copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 a=argparse.ArgumentParser();a.add_argument('--apply-active',action='store_true');args=a.parse_args()
 base=ROOT/'Local/CustomuseAssets/Polish20261025';plan=json.loads((base/'overhaul-v028/import-plan-KnightB.json').read_text())
 plan=copy.deepcopy(plan);plan.update(version='v029',replace_runtime_source='/Game/Characters/Customuse/KnightB/v028/DA_KnightB',purpose='Native-axis-correct blink mapping; source poses and root trajectory unchanged, original guard and other clips inherited.')
 for c in plan['clips']:
  if c['name'] not in ('BlinkLeft','BlinkRight'):raise ValueError('Unexpected v028 delta clip')
  c['name']='BlinkRight' if c['name']=='BlinkLeft' else 'BlinkLeft'
 folder=base/'overhaul-v029';folder.mkdir(exist_ok=True);file=folder/'import-plan-KnightB.json';text=json.dumps(plan,indent=2)+'\n'
 if file.exists() and file.read_text()!=text:raise RuntimeError('Different prepared bank preserved')
 file.write_text(text)
 if args.apply_active:
  p=base/'active-plans.json';active=json.loads(p.read_text());active['KnightB']={'path':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()};p.write_text(json.dumps(active,indent=2)+'\n')
 print(file)
if __name__=='__main__':main()
