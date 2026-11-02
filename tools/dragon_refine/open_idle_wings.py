"""Open the approved idle's existing wing fold; preserve every non-wing channel."""
import bpy,hashlib,json,math
from pathlib import Path
from mathutils import Quaternion,Vector
ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021/Dragon_Idle_Blender_v1r3.blend')
RAW=SOURCE.parent/'export/Dragon_Idle_Blender_v1r3.glb'
OUT=ROOT/'Local/idle-wings-20261102';OUT.mkdir(parents=True,exist_ok=True)
OUT=OUT/'v4';OUT.mkdir(exist_ok=True)
DEST=OUT/'Dragon_Idle_Open_v4';assert not DEST.with_suffix('.blend').exists()
assert hashlib.sha256(RAW.read_bytes()).hexdigest()=='7c057fd666e3dbbf91ecdbf8f9707a36cb767d16ab461f5565ecd229f5f4c6f8'
source_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False)
s=bpy.context.scene;s['session_owner']='codex-veyr-idle-wings-20261102'
C=bpy.data.objects['DRAGON_CTRL'];D=bpy.data.objects['DRAGON_DEFORM'];M=bpy.data.objects['DRAGON_MESH']
strip=next(t for t in C.animation_data.nla_tracks if t.name=='0_Base').strips[0]
original=strip.action;modified=original.copy();modified.name='IdleOpen_WingFoldBase'
def curves(a):return [f for l in a.layers for st in l.strips for bag in st.channelbags for f in bag.fcurves]
changes=[]
for tag in ['PosZ','NegZ']:
    for part,fraction in [('Root',.35),('Wrist',.30),('Elbow',.25),('Membrane',.30)]:
        name=f'C_VeyrWing{tag}{part}';path=f'pose.bones["{name}"].rotation_quaternion'
        fc=sorted([f for f in curves(modified) if f.data_path==path],key=lambda f:f.array_index)
        assert len(fc)==4
        q=Quaternion([f.evaluate(0) for f in fc]);q.normalize()
        if part=='Root':
            side=1 if tag=='NegZ' else -1
            world=Quaternion(Vector((0,0,1)),math.radians(side*33))@Quaternion(Vector((1,0,0)),math.radians(-side*15))
            rest=C.data.bones[name].matrix_local.to_quaternion();opened=rest.inverted()@world@rest
        else:opened=Quaternion()
        for f,value in zip(fc,opened):
            for k in f.keyframe_points:k.co.y=value;k.handle_left.y=value;k.handle_right.y=value
            f.update()
        changes.append({'control':name,'fractionTowardUnfoldedRest':fraction,'angleChangeDegrees':math.degrees(q.rotation_difference(opened).angle)})
wing_names=set()
for n in ['VeyrWingPosZRoot','VeyrWingNegZRoot']:
    wing_names.add(n);wing_names.update(b.name for b in D.data.bones[n].children_recursive)
F0,F1=s.frame_start,s.frame_end
baseline={};breath={};body_before=[tuple(v.co) for v in M.data.vertices]
for frame in range(F0,F1+1):
    s.frame_set(frame);bpy.context.view_layer.update()
    baseline[frame]={b.name:b.matrix.copy() for b in D.pose.bones}
    breath[frame]={k.name:k.value for k in M.data.shape_keys.key_blocks}
strip.action=modified
if modified.slots:strip.action_slot=modified.slots[0]
shape_action=M.data.shape_keys.animation_data.action
fold_curves=[f for f in curves(shape_action) if 'VeyrWingFold' in f.data_path]
for f in fold_curves:
    for k in f.keyframe_points:k.co.y=0.;k.handle_left.y=0.;k.handle_right.y=0.
    f.update()
body_error=morph_error=0.
for frame in range(F0,F1+1):
    s.frame_set(frame);bpy.context.view_layer.update()
    for b in D.pose.bones:
        if b.name not in wing_names:body_error=max(body_error,max(abs(a-bb) for ra,rb in zip(b.matrix,baseline[frame][b.name]) for a,bb in zip(ra,rb)))
    morph_error=max(morph_error,max(abs(k.value-breath[frame][k.name]) for k in M.data.shape_keys.key_blocks if k.name!='VeyrWingFold'))
assert body_error<1e-6 and morph_error<1e-6
assert body_before==[tuple(v.co) for v in M.data.vertices]
# Use a common camera framing for the two states, including the opened wings.
frames=[F0,(F0+F1)//4,(F0+F1)//2,3*(F0+F1)//4,F1]
points=[]
for action in [original,modified]:
    strip.action=action
    for fc in fold_curves:
        for kp in fc.keyframe_points:kp.co.y=1. if action==original else 0.;kp.handle_left.y=kp.co.y;kp.handle_right.y=kp.co.y
        fc.update()
    if action.slots:strip.action_slot=action.slots[0]
    for frame in frames:
        s.frame_set(frame);bpy.context.view_layer.update();o=M.evaluated_get(bpy.context.evaluated_depsgraph_get());points.extend(o.matrix_world@Vector(v) for v in o.bound_box)
lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)]);center=(lo+hi)*.5;span=max(hi-lo)
for o in s.objects:
    if o.type=='MESH' and o!=M:o.hide_render=True
cam=bpy.data.objects.new('IdleWingReviewCamera',bpy.data.cameras.new('IdleWingReviewCamera'));s.collection.objects.link(cam);s.camera=cam
s.render.engine='BLENDER_WORKBENCH';sh=s.display.shading;sh.light='STUDIO';sh.color_type='TEXTURE';sh.show_shadows=True;sh.show_cavity=True;sh.background_type='WORLD'
s.view_settings.view_transform='Standard';s.view_settings.exposure=.8
s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
for label,action in [('before',original),('after',modified)]:
    strip.action=action
    for fc in fold_curves:
        for kp in fc.keyframe_points:kp.co.y=1. if action==original else 0.;kp.handle_left.y=kp.co.y;kp.handle_right.y=kp.co.y
        fc.update()
    if action.slots:strip.action_slot=action.slots[0]
    folder=OUT/label;folder.mkdir(exist_ok=True)
    for view,off in {'front':(1,0,.15),'side':(0,-1,.15),'threequarter':(1,-1,.35)}.items():
        cam.location=center+Vector(off).normalized()*span*2;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO'
        rot=cam.rotation_euler.to_matrix();right=rot@Vector((1,0,0));up=rot@Vector((0,1,0))
        width=max(p.dot(right) for p in points)-min(p.dot(right) for p in points);height=max(p.dot(up) for p in points)-min(p.dot(up) for p in points)
        cam.data.ortho_scale=max(width,height*960/540)*1.15
        for frame in frames:s.frame_set(frame);s.render.filepath=str(folder/f'{view}_{frame:04d}.png');bpy.ops.render.render(write_still=True)
strip.action=modified
if modified.slots:strip.action_slot=modified.slots[0]
with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
    bpy.ops.object.select_all(action='DESELECT');D.hide_set(False);D.select_set(True);bpy.context.view_layer.objects.active=D
    bpy.ops.object.mode_set(mode='POSE')
    for b in D.pose.bones:b.select=True
    bpy.ops.nla.bake(frame_start=F0,frame_end=F1,step=1,only_selected=False,visual_keying=True,clear_constraints=False,clear_parents=False,use_current_action=False,clean_curves=False,bake_types={'POSE'},channel_types={'LOCATION','ROTATION','SCALE'})
    bpy.ops.object.mode_set(mode='OBJECT')
action=D.animation_data.action;action.name='Dragon_Idle_Open_v4';action.use_fake_user=True
for f in curves(action):
    for k in f.keyframe_points:k.interpolation='LINEAR'
constraints=[(c,c.mute) for b in D.pose.bones for c in b.constraints]
for c,_ in constraints:c.mute=True
bpy.ops.object.select_all(action='DESELECT');D.select_set(True);M.hide_set(False);M.select_set(True);bpy.context.view_layer.objects.active=D
bpy.ops.export_scene.gltf(filepath=str(DEST.with_suffix('.glb')),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=DEST.stem,export_frame_range=True,export_frame_step=1,export_force_sampling=True,export_optimize_animation_size=False,export_skins=True,export_extras=True,export_morph=True,export_morph_normal=False,export_morph_animation=True,export_cameras=False,export_lights=False,export_def_bones=False,export_yup=True)
for c,mute in constraints:c.mute=mute
D.animation_data.action=None;s.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=str(DEST.with_suffix('.blend')),compress=True)
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_sha
receipt={'source':str(SOURCE),'sourceSHA256':source_sha,'approvedRawSHA256':hashlib.sha256(RAW.read_bytes()).hexdigest(),'outputSHA256':hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest(), 'changes':changes,'nonWingBoneMaxError':body_error,'nonWingMorphCurveMaxError':morph_error,'wingFoldWeight':0.,'poseMethod':'Earlier half-spread mantle approach: root sweep 33 degrees, lower 15 degrees, unfolded distal wing controls; current breathing unchanged','basisGeometryPreserved':True,'frames':[F0,F1],'fps':s.render.fps,'accepted':False}
receipt['outputSHA256']=hashlib.sha256(DEST.with_suffix('.glb').read_bytes()).hexdigest()
DEST.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n');print('VEYR_IDLE_WINGS_AUTHORED',flush=True)
