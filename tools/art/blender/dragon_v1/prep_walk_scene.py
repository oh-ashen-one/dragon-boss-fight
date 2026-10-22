"""Open the saved idle scene (read only), reparent hind/front toe controls into chains, save as walk scene."""
import bpy, json
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
dst = W/(globals().get('DST', 'Dragon_Walk_Blender_v1') + '.blend')
assert not dst.exists()
bpy.ops.wm.open_mainfile(filepath=str(W/(globals().get('SRC', 'Dragon_Idle_Blender_v1r2') + '.blend')), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
C = bpy.data.objects['DRAGON_CTRL']
win = bpy.context.window_manager.windows[0]
CHAIN = {'FOOT_tripo::1_Right_Limb_4': 'FOOT_tripo::1_Right_Limb_3', 'FOOT_tripo::0_Right_Limb_4': 'FOOT_tripo::0_Right_Limb_3',
         'FOOT_tripo::0_Left_Limb_3': 'FOOT_tripo::0_Left_Limb_2'}
with bpy.context.temp_override(window=win):
    for o in s.objects: o.select_set(False)
    C.hide_set(False); bpy.context.view_layer.objects.active = C; C.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for c, p in CHAIN.items(): C.data.edit_bones[c].parent = C.data.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    C.select_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
s['session_owner'] = 'fable-veyr-dragon-20261021'
print('RES', json.dumps({'file': bpy.data.filepath, 'parents': {c: C.data.bones[c].parent.name for c in CHAIN}}))
