import bpy
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
dst = W/'Dragon_Idle_Blender_v1r2.blend'; assert not dst.exists()
bpy.ops.wm.open_mainfile(filepath=str(W/'Dragon_Idle_Blender_v1.blend'), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
s['session_owner'] = 'fable-veyr-dragon-20261021'
print('RES', bpy.data.filepath)
