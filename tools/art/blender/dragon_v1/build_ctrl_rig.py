"""Build DRAGON_CTRL (control layer) over the v008 deform rig. Deform bones copy world
transforms of their drivers; legs are 2-bone IK to planted foot controls. Rest is unchanged."""
import bpy, json
import numpy as np
from pathlib import Path
from mathutils import Matrix, Vector
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
s = bpy.context.scene
DEF = bpy.data.objects['Armature']; DEF.name = 'DRAGON_DEFORM'
MESH = bpy.data.objects['tripo_node_c2f64f2b-a633-4e6f-accb-09e66']; MESH.name='DRAGON_MESH'
assert 'DRAGON_CTRL' not in bpy.data.objects
LEGACY = {'tripo::Head_0','tripo::Head_1','tripo::Head_2','tripo::Head_3','bone_36','bone_37'}
# legs: (name, chain upper, chain lower, foot pivot bone (IK control rest), foot bones fixed to control)
LEGS = {
 'FL': ('bone_7','tripo::1_Left_Limb_0','tripo::1_Left_Limb_1',['tripo::1_Left_Limb_1','bone_9']),
 'FR': ('tripo::0_Left_Limb_0','tripo::0_Left_Limb_1','tripo::0_Left_Limb_2',['tripo::0_Left_Limb_2','tripo::0_Left_Limb_3','bone_14']),
 'HL': ('tripo::1_Right_Limb_0','tripo::1_Right_Limb_1','tripo::1_Right_Limb_3',['tripo::1_Right_Limb_2','tripo::1_Right_Limb_3','tripo::1_Right_Limb_4']),
 'HR': ('tripo::0_Right_Limb_0','tripo::0_Right_Limb_1','tripo::0_Right_Limb_3',['tripo::0_Right_Limb_2','tripo::0_Right_Limb_3','tripo::0_Right_Limb_4']),
}
REPARENT = {'tripo::Spine_3':'tripo::Spine_1'}  # hip roots become independent siblings
win = bpy.context.window_manager.windows[0]
ctrl = DEF.copy(); ctrl.data = DEF.data.copy(); ctrl.name = 'DRAGON_CTRL'; ctrl.data.name='DRAGON_CTRL'
s.collection.objects.link(ctrl)
if ctrl.animation_data: ctrl.animation_data_clear()
for pb in ctrl.pose.bones:
    for c in list(pb.constraints): pb.constraints.remove(c)
bpy.ops.object.select_all(action='DESELECT') if bpy.context.mode=='OBJECT' else None
with bpy.context.temp_override(window=win):
    bpy.context.view_layer.objects.active = ctrl; ctrl.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ctrl.data.edit_bones
    for b in list(eb):
        if b.name in LEGACY: eb.remove(b)
    for b in eb: b.name = 'C_'+b.name
    for child, parent in REPARENT.items(): eb['C_'+child].parent = eb['C_'+parent]
    root = eb['C_tripo::Root']
    for leg,(up,lo,pivot,feet) in LEGS.items():
        pv = eb['C_'+pivot]
        ik = eb.new('IK_'+leg); ik.head, ik.tail, ik.roll = pv.head.copy(), pv.tail.copy(), pv.roll; ik.parent = root
        lob = eb['C_'+lo]
        t = eb.new('IKT_'+leg); t.head = lob.tail.copy(); t.tail = lob.tail + Vector((0,0,0.02)); t.parent = ik
        for f in feet:
            src = eb['C_'+f]; fb = eb.new('FOOT_'+f); fb.head, fb.tail, fb.roll = src.head.copy(), src.tail.copy(), src.roll; fb.parent = ik
    bpy.ops.object.mode_set(mode='OBJECT')
ctrl.select_set(False)
for leg,(up,lo,pivot,feet) in LEGS.items():
    c = ctrl.pose.bones['C_'+lo].constraints.new('IK'); c.name='LegIK'
    c.target = ctrl; c.subtarget = 'IKT_'+leg; c.chain_count = 2; c.use_tail = True; c.use_stretch = False; c.iterations = 500
# toe controls chained so a counter-rotated toe carries its claw (heel peel keeps toes flat)
with bpy.context.temp_override(window=win):
    bpy.context.view_layer.objects.active = ctrl; ctrl.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
    for c_, p_ in {'FOOT_tripo::1_Right_Limb_4':'FOOT_tripo::1_Right_Limb_3','FOOT_tripo::0_Right_Limb_4':'FOOT_tripo::0_Right_Limb_3','FOOT_tripo::0_Left_Limb_3':'FOOT_tripo::0_Left_Limb_2'}.items():
        ctrl.data.edit_bones[c_].parent = ctrl.data.edit_bones[p_]
    bpy.ops.object.mode_set(mode='OBJECT')
ctrl.select_set(False)
footbones = {f:leg for leg,v in LEGS.items() for f in v[3]}
for pb in DEF.pose.bones:
    for c in list(pb.constraints): pb.constraints.remove(c)
    if pb.name in LEGACY: continue
    c = pb.constraints.new('COPY_TRANSFORMS'); c.name='FromCtrl'; c.target = ctrl
    c.subtarget = ('FOOT_'+pb.name) if pb.name in footbones else ('C_'+pb.name)
    c.target_space = c.owner_space = 'WORLD'
for pb in ctrl.pose.bones: pb.rotation_mode = 'QUATERNION'
for pb in DEF.pose.bones: pb.rotation_mode = 'QUATERNION'
ctrl.show_in_front = True; ctrl.display_type='WIRE'; ctrl.hide_render = True
bpy.context.view_layer.update()
err = 0.
for b in DEF.data.bones:
    pm = DEF.pose.bones[b.name].matrix
    err = max(err, max(abs(pm[i][j]-b.matrix_local[i][j]) for i in range(4) for j in range(4)))
print(json.dumps({'ctrl_bones': len(ctrl.data.bones), 'rest_equivalence_max_abs': err}))
