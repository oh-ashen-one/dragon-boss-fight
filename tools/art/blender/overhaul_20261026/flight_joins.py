import bpy,json,hashlib,math
from pathlib import Path
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Overhaul20261026/flight';OUT.mkdir(exist_ok=True)
OWNER='codex-veyr-overhaul-20261026'
def load(file):
 assert bpy.context.scene.get('session_owner')==OWNER
 for o in list(bpy.context.scene.objects):bpy.data.objects.remove(o,do_unlink=True)
 bpy.ops.import_scene.gltf(filepath=str(file));bpy.context.scene['session_owner']=OWNER
 return next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
rig=load(ROOT/'Local/Blender/dangle-20261025/Dragon_FlyHover_Blender_dangle_v2.glb');s=bpy.context.scene;s.frame_set(0)
limbs={b.name:b.matrix_basis.copy() for b in rig.pose.bones if 'Limb' in b.name}
print('Corrective limb joints',len(limbs))
for source,name,takeoff in [('Dragon_Takeoff_Blender_polish_v3','Dragon_Takeoff_DangleJoin_v1',True),('Dragon_Land_Blender_polish_v4','Dragon_Land_DangleJoin_v1',False)]:
 rig=load(ROOT/'Local/Blender/polish-20261025'/(source+'.glb'));s=bpy.context.scene;fps=s.render.fps/s.render.fps_base
 old=rig.animation_data.action;end=round(old.frame_range[1]);s.frame_start=0;s.frame_end=end
 poses={}
 for f in range(end+1):
  s.frame_set(f);poses[f]={n:rig.pose.bones[n].matrix_basis.copy() for n in limbs if n in rig.pose.bones}
 rig.animation_data.action=old.copy();rig.animation_data.action.name=name
 for f in range(end+1):
  s.frame_set(f);x=(f-(end-fps*.4))/(fps*.4) if takeoff else 1-f/(fps*.4);x=max(0,min(1,x));w=x*x*(3-2*x)
  for n,m in poses[f].items():
   p=rig.pose.bones[n];a,q,sc=m.decompose();b,r,ss=limbs[n].decompose();p.matrix_basis=Matrix.LocRotScale(a.lerp(b,w),q.slerp(r,w),sc.lerp(ss,w));p.rotation_mode='QUATERNION'
   for prop in ('location','rotation_quaternion','scale'):p.keyframe_insert(prop,frame=f)
 for o in s.objects:o.select_set(o==rig or o.type=='MESH')
 bpy.context.view_layer.objects.active=rig
 file=OUT/(name+'.glb');bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_optimize_animation_size=False,export_cameras=False,export_lights=False)
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')),compress=True)
 (OUT/(name+'.json')).write_text(json.dumps({'source':source,'name':name,'fps':fps,'duration':end/fps,'correction':'Existing approved source motion; only limb locals ease to/from the reviewed dangling hover over0.4seconds in Blender MCP','sha256':hashlib.sha256(file.read_bytes()).hexdigest()},indent=2))
 print(name,'duration',end/fps,'limbs',len(limbs))
