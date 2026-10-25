"""Reimport and render the exact exported GLB through owned Blender MCP."""
from pathlib import Path
import bpy,json,math
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Blender/dangle-20261025';OWNER='codex-veyr-dangle-20261025'
assert bpy.context.scene.get('session_owner')==OWNER
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'Dragon_FlyHover_Blender_dangle_v2.glb'))
s=bpy.context.scene;s['session_owner']=OWNER;s.render.fps=30
print([(o.name,o.type) for o in s.objects])
g={'__file__':str(ROOT/'tools/art/blender/dragon_flight_r2/drender_r2.py')};exec(compile(Path(g['__file__']).read_text(),g['__file__'],'exec'),g)
g['TARGET']=g['Vector']((0,0,.30))
for v,(off,scale) in g['VIEWS'].items():g['VIEWS'][v]=(off,max(scale,1.4) if scale>0 else scale)
g['setup'](show=tuple(o.name for o in s.objects if o.type in ('MESH','ARMATURE') and not o.name.startswith('REVIEW_')))
print(g['render'](range(60),OUT/'export-playback',res=(640,480),views=('side','front','three_quarter')))
(OUT/'export-playback/timing.json').write_text(json.dumps({'duration':2,'fps':30,'frames':60,'source':'Exact reimported GLB, no synthetic frames'}))
