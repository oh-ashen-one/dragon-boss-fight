"""Native Blender review captures; run in task-owned MCP, never another renderer."""
from pathlib import Path
import bpy,math,json
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[4]/'Local/Blender/feedback-v3-20261021'

def capture(job,full=False,close=False):
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/(job+'_Blender_v1.blend')),load_ui=False)
 s=bpy.context.scene;assert s['session_owner']=='codex-veyr-feedback-v3-20261021';cam=s.camera;r=bpy.data.objects['Knight_Deform']
 folder=ROOT/'renders'/job;folder.mkdir(parents=True,exist_ok=True)
 s.render.resolution_x=s.render.resolution_y=600 if close else 480;s.display.shading.color_type='OBJECT'
 for o in s.objects:
  if o.get('export_body'):o.color=(.53,.55,.6,1)
  if o.get('review_prop'):o.color=(.7,.32,.06,1)
  if o.get('review_attachment'):o.color=(.25,.16,.07,1)
 times=[i/30 for i in range(math.ceil(s['duration']*30))] if full else ([0,.08,.14,.22,.3,.4,.7] if job=='guard_two' else [0,.06,.12,.18,.28,.34,.4,.5,.7] if job.startswith('strafe') else [s['duration']*i/8 for i in range(9)])
 if close:times=[.35,.7,1.,1.4,1.9]
 views={'front':(0,-4,.5),'side':(4,0,.5),'threequarter':(2.8,-4,1.)} if not close else {'grip_front':(0,-4,.8),'grip_side':(4,0,.5),'grip_back':(0,4,.8)}
 for view,xyz in views.items():
  for i,t in enumerate(times):
   ff=t*s.render.fps;s.frame_set(int(ff),subframe=ff-int(ff))
   center=Vector((0,0,.7))
   if job.startswith('strafe'):center.x=.5*(1 if job=='strafe_left' else -1)
   if close:center=r.pose.bones['LeftHand'].matrix.translation+Vector((0,.015,.025))
   d=Vector(xyz).normalized();cam.location=center+d*5;cam.rotation_euler=(-d).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.28 if close else 2.65 if job.startswith('strafe') else 2.35
   s.render.filepath=str(folder/(f'{view}-'+('full' if full else 'key')+f'-{i:04d}.png'));bpy.ops.render.render(write_still=True)
 (folder/('close-info.json' if close else 'full-info.json' if full else 'keys-info.json')).write_text(json.dumps({'times':times,'views':list(views),'duration':s['duration']}))
 print('CAPTURED',job,full,close)
