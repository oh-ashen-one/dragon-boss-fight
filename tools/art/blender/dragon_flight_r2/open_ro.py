"""Open a dragon v1 scene READ-ONLY into my session (never saved back): tag my owner; record source."""
import bpy, json
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
src = W / (NAME + '.blend')
bpy.ops.wm.open_mainfile(filepath=str(src), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-knight-walk-20261021'; s['mcp_port'] = 9886; s['flight_r2_source'] = str(src)
print('RES', json.dumps({'opened': bpy.data.filepath, 'frames': [s.frame_start, s.frame_end], 'fps': s.render.fps, 'tracks': [t.name for t in bpy.data.objects['DRAGON_CTRL'].animation_data.nla_tracks]}))
