"""Render and measure the two licensed heavy retarget candidates without changing source files."""
import bpy
import argparse
import sys
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/Retarget'
g={'__file__':str(HELPER)};exec(compile(HELPER.read_text(),str(HELPER),'exec'),g);g['OUT']=OUT
records=[]
p=argparse.ArgumentParser();p.add_argument('--version',default='v1');p.add_argument('--variant',choices=['M','F','both'],default='both');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
for name in [f'Kevin_Heavy_{v}_{a.version}' for v in (['M','F'] if a.variant=='both' else [a.variant])]:
    assert not (OUT/'Evidence'/name).exists()
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'Exports'/(name+'.blend')),load_ui=False)
    rig=bpy.data.objects['Knight_Comparison'];s=bpy.context.scene
    samples=[]
    end=s.frame_end
    for frame in range(end+1):
        s.frame_set(frame)
        def point(b):return (rig.matrix_world@rig.pose.bones[b].matrix).translation.copy()
        right,left=point('RightHand'),point('LeftHand')
        samples.append({'frame':frame,'handSeparation':(left-right).length,'hips':list(point('Hips')),
                        'rightHand':list(right),'leftHand':list(left),'leftToe':list(point('LeftToeBase')),'rightToe':list(point('RightToeBase'))})
    records.append({'name':name,'samples':samples})
    g['render'](name,sorted(set([0,round(end*.17),round(end*.34),round(end*.43),round(end*.65),round(end*.85),end])))
path=OUT/f'preview-metrics-{a.version}.json';assert not path.exists();path.write_text(json.dumps(records,indent=2)+'\n')
print('VEYR_KEVIN_PREVIEW_COMPLETE',flush=True)
