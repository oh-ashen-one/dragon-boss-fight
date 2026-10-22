"""Fly scene from the walk scene: IK foot controls ride the body (front -> chest, hind -> hips) so tucked legs follow it."""
import bpy, json
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
dst = W/(globals().get('DST', 'Dragon_FlyHover_Blender_v1') + '.blend'); assert not dst.exists()
bpy.ops.wm.open_mainfile(filepath=str(W/'Dragon_Walk_Blender_v1.blend'), load_ui=False)
s = bpy.context.scene; s['session_owner'] = 'fable-veyr-dragon-20261021'; s['mcp_port'] = 9888
C = bpy.data.objects['DRAGON_CTRL']; win = bpy.context.window_manager.windows[0]
PAR = globals().get('PAR', {'FL': 'C_bone_2', 'FR': 'C_bone_2', 'HL': 'C_tripo::Spine_1', 'HR': 'C_tripo::Spine_1'})
with bpy.context.temp_override(window=win):
    for o in s.objects: o.select_set(False)
    C.hide_set(False); bpy.context.view_layer.objects.active = C; C.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for leg, p in PAR.items(): C.data.edit_bones['IK_'+leg].parent = C.data.edit_bones[p] if p else None
    bpy.ops.object.mode_set(mode='OBJECT'); C.select_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(dst), compress=True)
s['session_owner'] = 'fable-veyr-dragon-20261021'
print('RES', json.dumps({'file': bpy.data.filepath, 'ik_parents': {l: (C.data.bones['IK_'+l].parent.name if C.data.bones['IK_'+l].parent else None) for l in PAR}}))
