import bpy,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Overhaul20261026/flight';OWNER='codex-veyr-overhaul-20261026'
for name in ('Dragon_Takeoff_DangleJoin_v1','Dragon_Land_DangleJoin_v1'):
 assert bpy.context.scene.get('session_owner')==OWNER
 for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 bpy.context.scene.render.fps=30;bpy.ops.import_scene.gltf(filepath=str(OUT/(name+'.glb')))
 s=bpy.context.scene;s['session_owner']=OWNER;rig=next(o for o in s.objects if o.type=='ARMATURE');end=round(rig.animation_data.action.frame_range[1])
 g={'__file__':str(ROOT/'tools/art/blender/dragon_flight_r2/drender_r2.py')};exec(compile(Path(g['__file__']).read_text(),g['__file__'],'exec'),g)
 g['TARGET']=Vector((0,0,.30))
 for v,(off,scale) in g['VIEWS'].items():g['VIEWS'][v]=(off,1.5 if scale>0 else scale)
 g['setup'](show=tuple(o.name for o in s.objects if o.type in ('MESH','ARMATURE') and not o.name.startswith('REVIEW_')))
 g['render']([0,end//3,2*end//3,end],OUT/'review'/name,res=(640,480),views=('side','front','three_quarter'))
