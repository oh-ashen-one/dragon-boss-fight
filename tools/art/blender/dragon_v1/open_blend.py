import bpy
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
bpy.ops.wm.open_mainfile(filepath=str(W/(NAME + '.blend')), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
print('RES', bpy.data.filepath)
