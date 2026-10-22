"""Turn scene from the walk scene: IK foot controls become world-space (unparented) so planted feet
stay fixed while the root bone carries the 90 deg yaw (root motion)."""
import bpy, json
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
dst = W/(globals().get('DST', 'Dragon_Turn_Blender_v1') + '.blend'); assert not dst.exists()
bpy.ops.wm.open_mainfile(filepath=str(W/(globals().get('SRC', 'Dragon_Walk_Blender_v1') + '.blend')), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
C = bpy.data.objects['DRAGON_CTRL']; win = bpy.context.window_manager.windows[0]
with bpy.context.temp_override(window=win):
    for o in s.objects: o.select_set(False)
    C.hide_set(False); bpy.context.view_layer.objects.active = C; C.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for leg in ('FL','FR','HL','HR'): C.data.edit_bones['IK_'+leg].parent = None
    bpy.ops.object.mode_set(mode='OBJECT'); C.select_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
s['session_owner'] = 'fable-veyr-dragon-20261021'
print('RES', json.dumps({'file': bpy.data.filepath, 'ik_parents': {l: (C.data.bones['IK_'+l].parent.name if C.data.bones['IK_'+l].parent else None) for l in ('FL','FR','HL','HR')}}))
