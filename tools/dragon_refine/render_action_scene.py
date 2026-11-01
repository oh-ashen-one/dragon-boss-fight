"""Render one explicitly selected rig from an editable scene using fixed review cameras."""
import argparse
import os
from pathlib import Path
import runpy
import sys

import bpy

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--rig',required=True);p.add_argument('--label',required=True);p.add_argument('--quick',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
root=Path(os.environ.get('REVIEW_ROOT',Path(__file__).resolve().parents[2]/'Local/dragon-review-20261029'))
if Path(a.label).name!=a.label or (root/'frames'/a.label).exists():raise RuntimeError('Fresh safe review label required')
rig=bpy.data.objects[a.rig]
mesh=next(o for o in bpy.data.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers))
for obj in list(bpy.data.objects):
    if obj not in (rig,mesh):bpy.data.objects.remove(obj,do_unlink=True)
rig.name='DragonArmature';mesh.name='DragonMesh'
for obj in (rig,mesh):obj.hide_set(False);obj.hide_viewport=False;obj.hide_render=False
sys.argv=['render_clip_v3.py','--',a.label]+(['--quick'] if a.quick else [])
runpy.run_path(str(Path(__file__).with_name('render_clip_v3.py')),run_name='__main__')
