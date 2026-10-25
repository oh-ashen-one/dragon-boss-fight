"""Bake the reviewed editable scene through the owned Blender MCP."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
p=ROOT/'tools/art/blender/dangle_20261025/hover.py'
g={'__file__':str(p)};exec(compile(p.read_text().rsplit('\nauthor()',1)[0],str(p),'exec'),g)
g['open_scene'](g['OUT']/'working-v3.blend')
bpy=g['bpy'];t=bpy.data.texts.get('dangle_hover.py') or bpy.data.texts.new('dangle_hover.py');t.clear();t.write(p.read_text())
g['bake_export']('Dragon_FlyHover_Blender_dangle_v2','FlightHoverAlternate')
