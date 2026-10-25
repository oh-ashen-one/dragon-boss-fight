"""Blender-authored full-pose/shape ground endpoints for the corrected flight suite.

Final deform action is editable directly. The prior control rig remains in the
Blend as the unmodified base authoring layer, with its copy constraints muted.
"""
from pathlib import Path
exec(compile((Path(__file__).parent/'common.py').read_text(),str(Path(__file__).parent/'common.py'),'exec'))

def evaluated_basis(rig):
    result={}
    for bone in rig.pose.bones:
        if bone.parent:
            m=bone.bone.convert_local_to_pose(bone.matrix,bone.bone.matrix_local,parent_matrix=bone.parent.matrix,parent_matrix_local=bone.parent.bone.matrix_local,invert=True)
        else:m=bone.bone.convert_local_to_pose(bone.matrix,bone.bone.matrix_local,invert=True)
        result[bone.name]=m.copy()
    return result

def smooth(x):
    x=max(0.,min(1.,x));return x*x*(3.-2.*x)

def author(mode):
    assert mode in ('takeoff','land')
    original=OUT/('Dragon_Takeoff_Blender_polish_v2.blend' if mode=='takeoff' else 'Dragon_Land_Blender_polish_v3.blend')
    name='Dragon_Takeoff_Blender_polish_v3' if mode=='takeoff' else 'Dragon_Land_Blender_polish_v4'
    key='FlightWindup' if mode=='takeoff' else 'FlightRecovery'
    dest=OUT/(name+'.glb');blend=OUT/(name+'.blend');assert not dest.exists() and not blend.exists()
    idle_path=SRC/'dragon-v1-20261021/Dragon_Idle_Blender_v1r3.blend'
    open_scene(idle_path);bpy.context.view_layer.update();idle=evaluated_basis(bpy.data.objects['DRAGON_DEFORM'])
    shapes=bpy.data.objects['DRAGON_MESH'].data.shape_keys;basis=shapes.key_blocks['Basis'];idle_base=[x.co.copy() for x in basis.data];effective=[Vector((0,0,0)) for _ in basis.data]
    for shape in shapes.key_blocks:
        if shape.name=='Basis' or abs(shape.value)<1e-9:continue
        for i,(point,base) in enumerate(zip(shape.data,basis.data)):effective[i]+=(point.co-base.co)*shape.value
    open_scene(original);s=bpy.context.scene;D=bpy.data.objects['DRAGON_DEFORM'];M=bpy.data.objects['DRAGON_MESH'];T=s.frame_end;pose={};weights={}
    shapes=M.data.shape_keys;basis=shapes.key_blocks['Basis']
    assert len(basis.data)==len(idle_base)
    assert max((a.co-b).length for a,b in zip(basis.data,idle_base))<1e-6,'Ground corrective requires identical base vertex layout'
    for f in range(T+1):
        s.frame_set(f);bpy.context.view_layer.update();pose[f]=evaluated_basis(D);weights[f]={x.name:x.value for x in shapes.key_blocks}
    # Author an actual pose action in Blender. Existing source controls remain
    # editable/reference; only the final DCC action publishes the new blend.
    for bone in D.pose.bones:
        for constraint in bone.constraints:constraint.mute=True
        bone.rotation_mode='QUATERNION'
    D.animation_data_create();action=bpy.data.actions.new(name+'_EditableGroundPoseJoin');D.animation_data.action=action;action.use_fake_user=True
    previous={}
    for f in range(T+1):
        s.frame_set(f);w=1-smooth(f/7) if mode=='takeoff' else smooth((f-(T-7))/7)
        for bone in D.pose.bones:
            a,aq,asc=pose[f][bone.name].decompose();b,bq,bsc=idle[bone.name].decompose();bone.matrix_basis=Matrix.LocRotScale(a.lerp(b,w),aq.slerp(bq,w),asc.lerp(bsc,w));q=bone.rotation_quaternion.copy()
            if bone.name in previous:q.make_compatible(previous[bone.name])
            bone.rotation_quaternion=q;previous[bone.name]=q.copy()
            for field in ('location','rotation_quaternion','scale'):bone.keyframe_insert(field,frame=f)
    for fc in curves(action):
        for k in fc.keyframe_points:k.interpolation='LINEAR'
    corrective=M.shape_key_add(name='PolishIdleEndpoint')
    for point,base,delta in zip(corrective.data,basis.data,effective):point.co=base.co+delta
    shapes.animation_data_create();shape_action=bpy.data.actions.new(name+'_EditableGroundShapeJoin');shapes.animation_data.action=shape_action;shape_action.use_fake_user=True
    for f in range(T+1):
        w=1-smooth(f/7) if mode=='takeoff' else smooth((f-(T-7))/7)
        for shape in shapes.key_blocks:
            if shape.name=='Basis':continue
            shape.value=w if shape.name=='PolishIdleEndpoint' else weights[f].get(shape.name,0)*(1-w)
            shape.keyframe_insert('value',frame=f)
    for fc in curves(shape_action):
        for k in fc.keyframe_points:k.interpolation='LINEAR'
    action['veyr_runtime_clip']=key;action['loop']=False;action['fps']=30;action['authoring']='Native Blender deform pose and corrective-shape ground boundary keys; exact Idle_r3 ground pose, retained corrected hover boundary.'
    s['polish_note']=action['authoring'];s['ground_join_source']=str(idle_path);s['ground_join_frames']=7;s['session_owner']=OWNER;s.frame_set(0)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        for obj in s.objects:obj.select_set(False)
        D.hide_set(False);M.hide_set(False);D.select_set(True);M.select_set(True);bpy.context.view_layer.objects.active=D
        bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=name,export_frame_range=True,export_frame_step=1,export_force_sampling=True,export_optimize_animation_size=False,export_skins=True,export_extras=True,export_morph=True,export_morph_normal=False,export_morph_animation=True,export_cameras=False,export_lights=False,export_def_bones=False,export_yup=True)
        bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    report={'key':key,'file':str(dest),'blend':str(blend),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'duration':1.5,'fps':30,'candidate':True,'groundEndpoint':'Idle_r3 f0 exact full pose and effective corrective shape','groundJoinFrames':7,'internalHoverBoundaryPreserved':True}
    (OUT/(name+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report));print(render_dragon(name+'-review',(0,3,7,38,42,45),('front','side','three_quarter')))
    return report
