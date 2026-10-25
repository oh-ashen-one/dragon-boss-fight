"""Blender-native IK/pole authoring: relaxed hind legs, retained wing actions."""
from pathlib import Path
exec(compile((Path(__file__).parent/'common.py').read_text(),str(Path(__file__).parent/'common.py'),'exec'))
HOVER=SRC/'dragon-v1-20261021/flight_r2/Dragon_FlyHover_Blender_v1r2.blend'
IDLE=SRC/'dragon-v1-20261021/Dragon_Idle_Blender_v1r3.blend'

def get_idle_feet():
 open_scene(IDLE);c=bpy.data.objects['DRAGON_CTRL'];return {n:c.pose.bones[n].matrix.copy() for n in ['IK_HL','IK_HR']}
def add_poles(c):
 result={}
 for side,prefix in [('L','1'),('R','0')]:
  name='POLISH_HindPole_'+side;o=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(o);o.empty_display_size=.02
  con=c.pose.bones[f'C_tripo::{prefix}_Right_Limb_1'].constraints['LegIK'];con.pole_target=o;con.pole_subtarget='';con.use_stretch=False;con.iterations=128
  result[side]=(o,con)
 return result

def calibrate_poles(c,poles):
 for side,prefix in [('L','1'),('R','0')]:
  hip=c.pose.bones[f'C_tripo::{prefix}_Right_Limb_0'].head.copy();desired=hip+Vector((.035,.04 if side=='L' else -.04,-.035));o,con=poles[side];o.location=c.matrix_world@(hip+Vector((.13,.12 if side=='L' else -.12,-.035)))
  best=None
  for i in range(-36,37):
   con.pole_angle=math.radians(i*5);bpy.context.view_layer.update();k=c.pose.bones[f'C_tripo::{prefix}_Right_Limb_1'].head
   score=(k-desired).length
   if best is None or score<best[0]:best=(score,con.pole_angle)
  con.pole_angle=best[1]
 return {s:math.degrees(x[1].pole_angle) for s,x in poles.items()}

def bake_export(name,key):
 with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
  return _bake_export(name,key)

def _bake_export(name,key):
 s=bpy.context.scene;D=bpy.data.objects['DRAGON_DEFORM'];M=bpy.data.objects['DRAGON_MESH'];C=bpy.data.objects['DRAGON_CTRL']
 dest=OUT/(name+'.glb');blend=OUT/(name+'.blend');assert not dest.exists() and not blend.exists()
 for o in s.objects:o.select_set(False)
 D.hide_set(False);D.select_set(True);bpy.context.view_layer.objects.active=D
 bpy.ops.object.mode_set(mode='POSE')
 bpy.ops.nla.bake(frame_start=s.frame_start,frame_end=s.frame_end,step=1,only_selected=False,visual_keying=True,clear_constraints=False,clear_parents=False,use_current_action=False,clean_curves=False,bake_types={'POSE'},channel_types={'LOCATION','ROTATION','SCALE'})
 bpy.ops.object.mode_set(mode='OBJECT');act=D.animation_data.action;act.name=name;act.use_fake_user=True
 for fc in curves(act):
  for kp in fc.keyframe_points:kp.interpolation='LINEAR'
 act['veyr_runtime_clip']=key;act['authoring']='Blender-native editable hind IK and calibrated poles; original wing actions retained';act['loop']=key=='FlightHoverAlternate'
 mutes=[(con,con.mute) for pb in D.pose.bones for con in pb.constraints]
 for con,_ in mutes:con.mute=True
 for o in s.objects:o.select_set(False)
 D.select_set(True);M.hide_set(False);M.select_set(True);bpy.context.view_layer.objects.active=D
 bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_nla_strips_merged_animation_name=name,export_frame_range=True,export_frame_step=1,export_force_sampling=True,export_optimize_animation_size=False,export_skins=True,export_extras=True,export_morph=True,export_morph_normal=False,export_morph_animation=True,export_cameras=False,export_lights=False,export_def_bones=False,export_yup=True)
 for con,m in mutes:con.mute=m
 D.animation_data.action=None;s.frame_set(0);s['session_owner']=OWNER
 text=bpy.data.texts.get('polish_20261025_dragon.py') or bpy.data.texts.new('polish_20261025_dragon.py');text.clear();text.write((ROOT/'tools/art/blender/polish_20261025/dragon.py').read_text())
 bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
 report={'key':key,'file':str(dest),'blend':str(blend),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'duration':(s.frame_end-s.frame_start)/s.render.fps,'fps':s.render.fps,'candidate':True}
 (OUT/(name+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report));return report

def author_hover(name='Dragon_FlyHover_Blender_polish_v1'):
 idle=get_idle_feet();open_scene(HOVER);s=bpy.context.scene;c=bpy.data.objects['DRAGON_CTRL'];p=c.pose.bones;ad=c.animation_data
 # Explicit foot placements live below and slightly behind the hip. Toes retain
 # the idle facing and rotate down35deg, rather than curling180deg above the rump.
 desired={};hips={}
 for f in range(61):
  s.frame_set(f);desired[f]={};hips[f]={}
  for side,prefix in [('L','1'),('R','0')]:
   n='IK_H'+side;hip=p[f'C_tripo::{prefix}_Right_Limb_0'].head.copy();hips[f][side]=hip
   rot=Quaternion(Vector((0,1,0)),math.radians(35))@idle[n].to_quaternion()
   desired[f][n]=Matrix.Translation(hip+Vector((-.03,.035 if side=='L' else -.035,-.12)))@rot.to_matrix().to_4x4()
 act=bpy.data.actions.new(name+'_EditableHindTargets');ad.action=act
 for f in range(61):
  s.frame_set(f)
  for n,m in desired[f].items():key_matrix(p[n],m,f)
 for fc in curves(act):
  for kp in fc.keyframe_points:kp.interpolation='LINEAR'
 poles=add_poles(c);s.frame_set(0);angles=calibrate_poles(c,poles)
 for f in range(61):
  s.frame_set(f)
  for side,(o,con) in poles.items():o.location=c.matrix_world@(hips[f][side]+Vector((.13,.12 if side=='L' else -.12,-.035)));o.keyframe_insert('location',frame=f)
 s.frame_set(0)
 endpoint={'bones':{b.name:{'loc':list(b.location),'q':list(b.rotation_quaternion),'sc':list(b.scale),'matrix':[list(r) for r in b.matrix]} for b in p},'morph':{b.name:b.value for b in bpy.data.objects['DRAGON_MESH'].data.shape_keys.key_blocks},'poleAngles':angles}
 (OUT/'hover-endpoint.json').write_text(json.dumps(endpoint,indent=2))
 print('POLES',angles);print(render_dragon('dragon-hover-v1',(0,15,30,45),('side','front','three_quarter')))
 return bake_export(name,'FlightHoverAlternate')

def author_transition(mode,name):
 assert mode in ('takeoff','land')
 endpoint=json.loads((OUT/'hover-endpoint.json').read_text());endbones=endpoint['bones']
 open_scene(OUT/'Dragon_FlyHover_Blender_polish_v1.blend');shape=bpy.data.objects['DRAGON_MESH'].data.shape_keys;hover_delta=[(p.co-b.co).copy() for p,b in zip(shape.key_blocks['VeyrBreath'].data,shape.key_blocks['Basis'].data)]
 source=SRC/('dragon-v1-20261021/Dragon_'+('Takeoff' if mode=='takeoff' else 'Land')+'_Blender_v1.blend')
 open_scene(source);s=bpy.context.scene;c=bpy.data.objects['DRAGON_CTRL'];p=c.pose.bones;T=s.frame_end
 mesh=bpy.data.objects['DRAGON_MESH'];corrective=mesh.shape_key_add(name='PolishHoverBreath');basis=mesh.data.shape_keys.key_blocks['Basis'];assert len(corrective.data)==len(hover_delta)
 for point,basepoint,delta in zip(corrective.data,basis.data,hover_delta):point.co=basepoint.co+delta
 base={};feet={};morph={}
 for f in range(T+1):
  s.frame_set(f);base[f]={b.name:b.matrix_basis.copy() for b in p};feet[f]={n:p[n].matrix.copy() for n in ('IK_HL','IK_HR','IK_FL','IK_FR')};morph[f]={b.name:b.value for b in bpy.data.objects['DRAGON_MESH'].data.shape_keys.key_blocks}
 ground=feet[0 if mode=='takeoff' else T]
 # Keep approved wing/body motion except a short smooth endpoint join to the
 # retained hover-r2 pose. This new control action remains editable in Blender.
 act=bpy.data.actions.new(name+'_EditableEndpointJoin');c.animation_data.action=act
 def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
 for f in range(T+1):
  s.frame_set(f);w=smooth((f-(T-7))/7) if mode=='takeoff' else 1-smooth(f/7)
  for n,b in p.items():
   if not n.startswith('C_'):continue
   m=base[f][n];eb=endbones[n];target=Matrix.LocRotScale(Vector(eb['loc']),Quaternion(eb['q']),Vector(eb['sc']));a,aq,asc=m.decompose();z,zq,zsc=target.decompose();b.matrix_basis=Matrix.LocRotScale(a.lerp(z,w),aq.slerp(zq,w),asc.lerp(zsc,w))
   for prop in ('location','rotation_quaternion','scale'):b.keyframe_insert(prop,frame=f)
 bpy.context.view_layer.update()
 # IK targets follow the new hips while airborne, with an explicit planted
 # interval and a continuous world-space arc instead of the old inverted tuck.
 hips={}
 for f in range(T+1):
  s.frame_set(f);hips[f]={}
  for side,prefix in [('L','1'),('R','0')]:
   n='IK_H'+side;hip=p[f'C_tripo::{prefix}_Right_Limb_0'].head.copy();hips[f][side]=hip
   hov=Matrix(endbones[n]['matrix']);hoverhip=Vector([endbones[f'C_tripo::{prefix}_Right_Limb_0']['matrix'][i][3] for i in range(3)])
   desired=hov.copy();desired.translation=hip+(hov.translation-hoverhip)
   u=smooth((f-20)/20) if mode=='takeoff' else 1-smooth((f-3)/19)
   g=ground[n];pos=g.translation.lerp(desired.translation,u);q=g.to_quaternion().slerp(desired.to_quaternion(),u)
   if mode=='takeoff':pos.z+=.012*math.sin(math.pi*u)
   foot_matrix=Matrix.Translation(pos)@q.to_matrix().to_4x4()
   key_matrix(p[n],foot_matrix,f)
   if mode=='land':
    target=p['IKT_H'+side].head.copy();delta=target-hip
    maxreach=.94*(c.data.bones[f'C_tripo::{prefix}_Right_Limb_0'].length+c.data.bones[f'C_tripo::{prefix}_Right_Limb_1'].length)
    if delta.length>maxreach:
     foot_matrix.translation-=delta.normalized()*(delta.length-maxreach);key_matrix(p[n],foot_matrix,f)
  for n in ('IK_FL','IK_FR'):
   w=smooth((f-(T-7))/7) if mode=='takeoff' else 1-smooth(f/7)
   a=feet[f][n];b=Matrix(endbones[n]['matrix']);key_matrix(p[n],Matrix.Translation(a.translation.lerp(b.translation,w))@a.to_quaternion().slerp(b.to_quaternion(),w).to_matrix().to_4x4(),f)
 for fc in curves(act):
  for kp in fc.keyframe_points:kp.interpolation='LINEAR'
 poles=add_poles(c)
 # Use the same calibrated bend plane throughout the connected flight suite.
 for side,(o,con) in poles.items():con.pole_angle=math.radians(endpoint['poleAngles'][side])
 for f in range(T+1):
  s.frame_set(f)
  for side,(o,con) in poles.items():o.location=c.matrix_world@(hips[f][side]+Vector((.13,.12 if side=='L' else -.12,-.035)));o.keyframe_insert('location',frame=f)
 # Match corrective morph endpoints; preserve source curves away from join.
 sk=bpy.data.objects['DRAGON_MESH'].data.shape_keys;sk.animation_data.action=bpy.data.actions.new(name+'_EditableShapeJoin')
 for f in range(T+1):
  w=smooth((f-(T-7))/7) if mode=='takeoff' else 1-smooth(f/7)
  for b in sk.key_blocks:
   if b.name=='Basis':continue
   if b.name=='VeyrBreath':b.value=morph[f].get(b.name,0)*(1-w)
   elif b.name=='PolishHoverBreath':b.value=endpoint['morph'].get('VeyrBreath',0)*w
   else:b.value=morph[f].get(b.name,0)*(1-w)+endpoint['morph'].get(b.name,0)*w
   b.keyframe_insert('value',frame=f)
 print(render_dragon(name+'-review',(0,10,20,30,45),('side','front','three_quarter')))
 return bake_export(name,'FlightWindup' if mode=='takeoff' else 'FlightRecovery')
