"""Render exact delivered GLBs, with correct glTF Y-up prop attachment."""
from pathlib import Path
import bpy,json
p=Path(__file__).with_name('retarget.py');g={'__file__':str(p)};exec(compile(p.read_text(),str(p),'exec'),g)
for clip in sorted((g['OUT']/'Exports').glob('*.json')):
 row=json.loads(clip.read_text());s=g['reset']();s.render.fps=int(row['fps']);bpy.ops.import_scene.gltf(filepath=str(clip.with_suffix('.glb')));t=next(o for o in s.objects if o.type=='ARMATURE');t.name='Knight_Comparison';s['session_owner']=g['OWNER'];end=round(row['duration']*row['fps']);g['render']('export_'+row['name'],[0,end//4,end//2,3*end//4,end])
