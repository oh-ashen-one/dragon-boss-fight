#!/usr/bin/env python3
"""Prepare a knight heal revision (the "sip" heal fit) on top of the active runtime definition.

usage: prepare_heal_revision.py <version, e.g. v049heal> <fit name, e.g. Quaternius_Heal_v10sip>

The plan inherits every active clip and replaces only HealSourced. Nothing is imported or activated
here; run_polish_import.py does that through the null-renderer commandlet.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
POLISH = ROOT/'Local/CustomuseAssets/Polish20261025'
VERSION, FIT = sys.argv[1], sys.argv[2]
assert VERSION.isalnum() and FIT.replace('_', '').isalnum()
SOURCE = ROOT/'Local/AttackSources20261103/HealGeometry'/(FIT+'.glb')
OUT = POLISH/('knight-'+VERSION)

assert not OUT.exists(), 'Preserve previous preparation'
manifest = json.loads((POLISH/'active-plans.json').read_text())['KnightB']
base_path = Path(manifest['path'])
assert hashlib.sha256(base_path.read_bytes()).hexdigest() == manifest['sha256'], 'active knight plan changed'
base = json.loads(base_path.read_text())
previous = json.loads((POLISH/'knight-v042heal/import-plan-KnightB.json').read_text())
weapon = previous['clips'][0]['weapon_file']
plan = dict(base)
plan.update(version=VERSION, clips=[], owner_approved=False,
            purpose='Heal sip fit '+FIT+': rim at the lower visor, one continuous drink (progressive tip, head and neck '
                    'back, two swallows), cup lowered past the chin before it leaves the hand',
            replace_runtime_source=f"/Game/Characters/Customuse/KnightB/{base['version']}/DA_KnightB")
OUT.mkdir(parents=True)
plan_path = OUT/'import-plan-KnightB.json'
plan_path.write_text(json.dumps(plan, indent=2)+'\n')
subprocess.run([sys.executable, str(ROOT/'tools/unreal/prepare_sourced_heal.py'), '--plan', str(plan_path), '--only-heal',
                '--export-file', str(SOURCE), '--weapon-key', weapon], check=True)
print('prepared', plan_path)
