"""Open one of MY flight_r2 scenes (no save)."""
import bpy, json
from pathlib import Path
bpy.ops.wm.open_mainfile(filepath=str(Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/flight_r2') / (NAME + '.blend')), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-knight-walk-20261021'; s['mcp_port'] = 9886
print('RES', bpy.data.filepath)
