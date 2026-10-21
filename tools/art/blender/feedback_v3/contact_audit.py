"""Native evaluated-mesh contact checks, complementing visual review."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[4]/'Local/Blender/feedback-v3-20261021'
results={}
for job in ['heal','heavy']:
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/(job+'_Blender_v1.blend')),load_ui=False);s=bpy.context.scene;assert s['session_owner']=='codex-veyr-feedback-v3-20261021';rig=bpy.data.objects['Knight_Deform'];body=next(o for o in s.objects if o.type=='MESH' and o.get('export_body') and not o.get('review_prop'))
 groups={g.index for g in body.vertex_groups if g.name.startswith('LeftHand')};ids=[v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in groups)>.5]
 closest=1e3;when=0
 if job=='heavy':
  sword=next(o for o in s.objects if o.type=='MESH' and o.get('review_attachment'));sword.data.calc_loop_triangles();bvh=BVHTree.FromPolygons([v.co for v in sword.data.vertices],[list(t.vertices) for t in sword.data.loop_triangles],all_triangles=True)
 for fr in range(0,s.frame_end+1,2):
  s.frame_set(fr);dg=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(dg);mesh=ev.to_mesh()
  handinv=(rig.matrix_world@rig.pose.bones['LeftHand'].matrix).inverted()
  if job=='heavy':sinv=sword.matrix_world.inverted();scale=sword.matrix_world.to_scale().x
  for i in ids:
   pos=ev.matrix_world@mesh.vertices[i].co
   if job=='heal':
    local=handinv@pos
    if -.025<=local.z<=.043:
     distance=math.hypot(local.x-.060,local.y-.091)-.028
    else:continue
   else:
    hit=bvh.find_nearest(sinv@pos);distance=hit[3]*scale
   if distance<closest:closest=distance;when=fr/s.render.fps
  ev.to_mesh_clear()
 results[job]={'leftHandVertices':len(ids),'minimumBowlClearance' if job=='heal' else 'minimumFreeHandSwordSurfaceDistance':closest,'atSeconds':when,'pass':closest>(.001 if job=='heal' else .025)}
print(json.dumps(results));(ROOT/'mesh-contact-audit.json').write_text(json.dumps(results,indent=2)+'\n')
