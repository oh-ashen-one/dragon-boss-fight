"""Idle r3 working scene: open idle r2 (read only), drop the old fold corrective, save as r3."""
import bpy, json
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
dst = W/'Dragon_Idle_Blender_v1r3.blend'; assert not dst.exists()
bpy.ops.wm.open_mainfile(filepath=str(W/'Dragon_Idle_Blender_v1r2.blend'), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
M = bpy.data.objects['DRAGON_MESH']
for n in ('VeyrWingFold', 'VeyrWingFoldWalk'):
    if n in M.data.shape_keys.key_blocks: M.shape_key_remove(M.data.shape_keys.key_blocks[n])
bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
s['session_owner'] = 'fable-veyr-dragon-20261021'
print('RES', json.dumps({'file': bpy.data.filepath, 'keys': [k.name for k in M.data.shape_keys.key_blocks]}))
