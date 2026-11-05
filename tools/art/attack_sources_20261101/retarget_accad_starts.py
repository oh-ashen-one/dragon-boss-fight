"""Inspect publisher-sourced ACCAD locomotion bases on the knight in Blender.

These first candidates retain the source upper-body action; weapon-specific
adaptation and native integration are separate, unaccepted steps.
"""
import hashlib
import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'Local/AttackSources20261105/ACCADMale1'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--standing-reference',action='store_true');parser.add_argument('--stop-end-reference',action='store_true');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
assert not args.stop_end_reference or args.standing_reference
OUT=SOURCE/('RetargetStartsReferenceV3' if args.stop_end_reference else 'RetargetStartsReference' if args.standing_reference else 'RetargetStarts');assert not OUT.exists()
manifest=json.loads((SOURCE/'selected.json').read_text())
records={r['file']:r for r in manifest['clips']}
jobs=[('ACCAD_StandToWalk_v1','Male1_B1_StandToWalk.bvh'),
      ('ACCAD_StandToRun_v1','Male1_C01_StandToRun.bvh'),
      ('ACCAD_RunToStand_v1','Male1_C02_RunToStand.bvh')]
helper=ROOT/'tools/art/blender/fab_rig_testing/retarget.py';ns={'__file__':str(helper)}
exec(compile(helper.read_text(),str(helper),'exec'),ns);ns['OUT']=OUT;ns['render']=lambda *args:None
bpy.ops.wm.read_factory_settings(use_empty=True)
for name,filename in jobs:
    if args.standing_reference:name=name.replace('_v1','_v3reference' if args.stop_end_reference else '_v2reference')
    source=SOURCE/'selected'/filename
    assert hashlib.sha256(source.read_bytes()).hexdigest()==records[filename]['sha256']
    bpy.context.scene['session_owner']=ns['OWNER']
    ns['run'](source,'accad',name,True,False,False,None,foot_frames=True,standing_reference=args.standing_reference,reference_at_end=args.stop_end_reference and 'RunToStand' in name)
    p=OUT/'Exports'/(name+'.json');d=json.loads(p.read_text());d.update(
        authoringApplication='Blender',editableScene=str(p.with_suffix('.blend').relative_to(ROOT)),
        editableSceneSHA256=hashlib.sha256(p.with_suffix('.blend').read_bytes()).hexdigest(),
        sourceSHA256=records[filename]['sha256'],sourceURL='https://accad.ohio-state.edu/research/motion-lab/mocap-system-and-data',
        license='CC BY 3.0',licenseURL='https://creativecommons.org/licenses/by/3.0/',
        attribution='Open Motion Project by ACCAD/The Ohio State University. Retargeted for Veyr; modifications not endorsed by the licensor.',
        weaponSpecificAdaptation=False,nativeImported=False,accepted=False)
    p.write_text(json.dumps(d,indent=2)+'\n')
print('ACCAD_BASES_RETARGETED_NOT_ACCEPTED',flush=True)
