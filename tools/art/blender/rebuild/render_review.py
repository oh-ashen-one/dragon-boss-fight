"""Run inside Blender MCP. Native viewport-quality three-view review frames."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[4]/'Local/Blender/approved-rebuild-20261021'
VIEWS={'front':(0,-4,1.25),'side':(4,0,1.25),'threequarter':(2.8,-4,1.7)}

def render_review(job,full=False):
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/(job+'_Blender_v1.blend')),load_ui=False)
 scene=bpy.context.scene;assert scene.get('session_owner')=='codex-veyr-walk-20261021'
 cam=scene.camera;duration=scene['duration'];end=scene.frame_end
 # Fixed framing for the entire clip; measure evaluated mesh bounds including sword.
 points=[]
 for f in range(0,end+1,max(1,end//30)):
  scene.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
  for o in scene.objects:
   if o.type=='MESH' and (o.get('export_body') or o.get('review_attachment')):
    e=o.evaluated_get(dg);points.extend(e.matrix_world@Vector(c) for c in e.bound_box)
 lo=Vector(tuple(min(v[i] for v in points) for i in range(3)));hi=Vector(tuple(max(v[i] for v in points) for i in range(3)))
 center=Vector((0,-.30 if job=='idle_one' else -.16,.78 if job not in ('idle_one','overhead') else .58))
 mesh=bpy.data.meshes.new('Review_Ground');mesh.from_pydata([(-100,-100,-.004),(100,-100,-.004),(100,100,-.004),(-100,100,-.004)],[],[(0,1,2,3)])
 ground=bpy.data.objects.new('Review_Ground',mesh);scene.collection.objects.link(ground)
 ground.color=(.12,.13,.15,1)
 scene.display.shading.color_type='OBJECT'
 for o in scene.objects:
  if o.get('export_body'):o.color=(.53,.55,.6,1)
  if o.get('review_attachment'):o.color=(.27,.19,.11,1)
 scene.render.resolution_x=480;scene.render.resolution_y=480
 frame_times=[0,.25,.5,.75,1.] if not full else [i/(math.ceil(duration*30)) for i in range(math.ceil(duration*30))]
 folder=ROOT/'renders'/job;folder.mkdir(parents=True,exist_ok=True)
 for view,xyz in VIEWS.items():
  direction=Vector(xyz).normalized();cam.location=center+direction*5
  cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
  rotation=cam.rotation_euler.to_matrix().transposed()
  screen=[rotation@(p-center) for p in points]
  cam.data.ortho_scale=2.25 if job!='idle_one' else 1.85
  for i,t in enumerate(frame_times):
   f=t*end;scene.frame_set(int(f),subframe=f-int(f))
   scene.render.filepath=str(folder/(('%s-%04d.png' if full else '%s-key-%02d.png')%(view,i)))
   bpy.ops.render.render(write_still=True)
 (folder/'render-info.json').write_text(json.dumps({'duration':duration,'framesPerView':len(frame_times),'views':list(VIEWS),'full':full}))
 print('Rendered',job,'full' if full else 'poses',len(frame_times)*3)
