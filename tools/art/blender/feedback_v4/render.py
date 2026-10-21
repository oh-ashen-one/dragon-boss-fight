"""Native Blender review captures for feedback v4; run in the task-owned MCP via run.py.

Parameters come from common.params(). capture(job, ...) opens <scene_dir>/<job>_Blender_v1.blend
(default: the v4 output dir; pass scene_dir=P['scene_in'] to capture a v3 scene), re-tags the
session owner, and writes PNGs only under <out>/renders/<label>/. It never saves the scene.
Camera, views and key times are identical to v3; only resolution may be overridden.
"""
from pathlib import Path
import bpy,math,json,importlib.util
from mathutils import Vector
HERE=Path(__file__).resolve().parent
_cs=importlib.util.spec_from_file_location('veyr_v4_common',HERE/'common.py');cm=importlib.util.module_from_spec(_cs);_cs.loader.exec_module(cm)
P=cm.params(globals().get('VEYR_V4_PARAMS'))

def capture(job,full=False,close=False,scene_dir=None,resolution=None,label=None):
 src=Path(scene_dir or P['out'])/(job+'_Blender_v1.blend');assert src.is_file(),src
 cm.open_tagged(src,P['owner'])
 s=bpy.context.scene;assert s['session_owner']==P['owner'];cam=s.camera;r=bpy.data.objects['Knight_Deform']
 folder=cm.check_writable(P['out']/'renders'/(label or job));folder.mkdir(parents=True,exist_ok=True)
 s.render.resolution_x=s.render.resolution_y=int(resolution) if resolution else (600 if close else 480);s.display.shading.color_type='OBJECT'
 for o in s.objects:
  if o.get('export_body'):o.color=(.53,.55,.6,1)
  if o.get('review_prop'):o.color=(.7,.32,.06,1)
  if o.get('review_attachment'):o.color=(.25,.16,.07,1)
 times=[i/30 for i in range(math.ceil(s['duration']*30))] if full else ([0,.08,.14,.22,.3,.4,.7] if job=='guard_two' else [0,.06,.12,.18,.28,.34,.4,.5,.7] if job.startswith('strafe') else [s['duration']*i/8 for i in range(9)])
 if close:times=[.35,.7,1.,1.4,1.9]
 views={'front':(0,-4,.5),'side':(4,0,.5),'threequarter':(2.8,-4,1.)} if not close else {'grip_front':(0,-4,.8),'grip_side':(4,0,.5),'grip_back':(0,4,.8)}
 written=[]
 for view,xyz in views.items():
  for i,t in enumerate(times):
   ff=t*s.render.fps;s.frame_set(int(ff),subframe=ff-int(ff))
   center=Vector((0,0,.7))
   if job.startswith('strafe'):center.x=.5*(1 if job=='strafe_left' else -1)
   if close:center=r.pose.bones['LeftHand'].matrix.translation+Vector((0,.015,.025))
   d=Vector(xyz).normalized();cam.location=center+d*5;cam.rotation_euler=(-d).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.28 if close else 2.65 if job.startswith('strafe') else 2.35
   s.render.filepath=str(folder/(f'{view}-'+('full' if full else 'key')+f'-{i:04d}.png'));bpy.ops.render.render(write_still=True);written.append(s.render.filepath)
 info={'source':str(src),'owner':P['owner'],'times':times,'views':list(views),'duration':s['duration'],'resolution':s.render.resolution_x,'frames':len(written)}
 (folder/('close-info.json' if close else 'full-info.json' if full else 'keys-info.json')).write_text(json.dumps(info))
 print('CAPTURED',job,full,close,len(written));return {**info,'folder':str(folder)}
