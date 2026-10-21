"""Native evaluated-mesh contact checks for feedback v4, complementing visual review.

Run in the task-owned MCP via run.py: audit(scene_dir=None, name='mesh-contact-audit.json').
Reads <scene_dir>/<job>_Blender_v1.blend (default: v4 output dir), re-tags the owner,
writes the result only to <out>/<name>. Thresholds are identical to v3. Never saves scenes.
"""
import bpy,json,math,importlib.util
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
_cs=importlib.util.spec_from_file_location('veyr_v4_common',HERE/'common.py');cm=importlib.util.module_from_spec(_cs);_cs.loader.exec_module(cm)
P=cm.params(globals().get('VEYR_V4_PARAMS'))

def audit(scene_dir=None,name='mesh-contact-audit.json',jobs=('heal','heavy')):
 ROOT=Path(scene_dir or P['out']);results={}
 for job in jobs:
  cm.open_tagged(ROOT/(job+'_Blender_v1.blend'),P['owner']);s=bpy.context.scene;assert s['session_owner']==P['owner'];rig=bpy.data.objects['Knight_Deform'];body=next(o for o in s.objects if o.type=='MESH' and o.get('export_body') and not o.get('review_prop'))
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
  results[job]={'leftHandVertices':len(ids),'minimumBowlClearance' if job=='heal' else 'minimumFreeHandSwordSurfaceDistance':closest,'atSeconds':when,'pass':closest>(.001 if job=='heal' else .025),'source':str(ROOT/(job+'_Blender_v1.blend'))}
 out=cm.check_writable(P['out']);out.mkdir(parents=True,exist_ok=True)
 print(json.dumps(results));(out/name).write_text(json.dumps(results,indent=2)+'\n');return results
