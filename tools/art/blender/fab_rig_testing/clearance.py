"""Frame-by-frame exact exported mesh overlap check in owned Blender MCP."""
import bpy,json,struct
from pathlib import Path
from mathutils import Vector,geometry
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/FabRigTesting';OWNER='codex-veyr-fab-grip'
def glb_geometry(path):
 data=path.read_bytes();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);blob=data[n+28:];p=doc['meshes'][0]['primitives'][0]
 def acc(i):
  a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']];n={'SCALAR':1,'VEC3':3}[a['type']];fmt={5126:'f',5123:'H',5125:'I'}[a['componentType']];size=struct.calcsize(fmt)*n;start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',size);return [struct.unpack_from('<'+fmt*n,blob,start+j*stride) for j in range(a['count'])]
 verts=[Vector(x) for x in acc(p['attributes']['POSITION'])];idx=[x[0] for x in acc(p['indices'])];tris=[tuple(idx[i:i+3]) for i in range(0,len(idx),3)];return verts,tris

def triangle_hit(a,b):
 # BVH overlap is broad phase. Confirm finite segment/triangle intersections.
 for triangle,other in ((a,b),(b,a)):
  for i in range(3):
   start=triangle[i];edge=triangle[(i+1)%3]-start;length=edge.length
   if length<1e-9:continue
   direction=edge/length;hit=geometry.intersect_ray_tri(*other,direction,start,True)
   if hit is not None:
    distance=(hit-start).dot(direction)
    if 1e-6<distance<length-1e-6:return True
 na=(a[1]-a[0]).cross(a[2]-a[0]);nb=(b[1]-b[0]).cross(b[2]-b[0])
 if na.length>1e-10 and nb.length>1e-10:
  na.normalize();nb.normalize()
  if abs(na.dot(nb))>.999999 and max(abs((p-a[0]).dot(na)) for p in b)<1e-7:
   drop=max(range(3),key=lambda i:abs(na[i]));axes=[i for i in range(3) if i!=drop]
   aa=[Vector((p[axes[0]],p[axes[1]])) for p in a];bb=[Vector((p[axes[0]],p[axes[1]])) for p in b]
   return bool(geometry.intersect_tri_tri_2d(*aa,*bb))
 return False

def audit(version='v3', names=None, substeps=1):
 assert bpy.context.scene.get('session_owner')==OWNER
 verts,tris=glb_geometry(ROOT/'Local/polish-review-20261025/BoatGreatsword_OneHand_v4.glb');blade=[t for t in tris if min(verts[i].y for i in t)>.55];handle=[t for t in tris if t not in blade];reports=[]
 for clip in ([OUT/'Exports'/(name+'.json') for name in names] if names else sorted((OUT/'Exports').glob('*_'+version+'.json'))):
  row=json.loads(clip.read_text());s=bpy.context.scene
  for o in list(s.objects):bpy.data.objects.remove(o,do_unlink=True)
  bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=False,do_recursive=True);s.render.fps=int(row['fps']);bpy.ops.import_scene.gltf(filepath=str(clip.with_suffix('.glb')));s['session_owner']=OWNER
  rig=next(o for o in s.objects if o.type=='ARMATURE');body=next(o for o in s.objects if o.type=='MESH');names={g.index:g.name for g in body.vertex_groups};allowed=set()
  for v in body.data.vertices:
   if sum(g.weight for g in v.groups if 'Hand' in names.get(g.group,''))>.3:allowed.add(v.index)
  rows=[];N=round(row['duration']*row['fps'])
  for sample in range(N*substeps+1):
   f=sample/substeps;s.frame_set(int(f),subframe=f-int(f));dg=bpy.context.evaluated_depsgraph_get();ob=body.evaluated_get(dg);mesh=ob.to_mesh();mesh.calc_loop_triangles();bodyverts=[ob.matrix_world@v.co for v in mesh.vertices];alltris=[tuple(t.vertices) for t in mesh.loop_triangles];nonhand=[t for t in alltris if not any(i in allowed for i in t)]
   bv=BVHTree.FromPolygons(bodyverts,alltris,all_triangles=True);nh=BVHTree.FromPolygons(bodyverts,nonhand,all_triangles=True);H=rig.matrix_world@rig.pose.bones['WeaponSocket'].matrix;wp=[H@v for v in verts];sb=BVHTree.FromPolygons(wp,blade,all_triangles=True);sh=BVHTree.FromPolygons(wp,handle,all_triangles=True)
   broad_b=bv.overlap(sb);broad_h=nh.overlap(sh);bh=[(i,j) for i,j in broad_b if triangle_hit([bodyverts[k] for k in alltris[i]],[wp[k] for k in blade[j]])];hh=[(i,j) for i,j in broad_h if triangle_hit([bodyverts[k] for k in nonhand[i]],[wp[k] for k in handle[j]])];rows.append({'frame':f,'broadPhaseBladePairs':len(broad_b),'broadPhaseHandlePairs':len(broad_h),'bladeBodyPairs':len(bh),'handleNonHandPairs':len(hh),'minSwordZ':min(v.z for v in wp)})
   ob.to_mesh_clear()
  report={'name':row['name'],'sampleCount':len(rows),'samplesPerSourceFrame':substeps,'minSwordZ':min(x['minSwordZ'] for x in rows),'bladeHitFrames':[x for x in rows if x['bladeBodyPairs']],'handleHitFrames':[x for x in rows if x['handleNonHandPairs']],'samples':rows};reports.append(report);print(row['name'],'blade',len(report['bladeHitFrames']),'handle',len(report['handleHitFrames']),'floor',report['minSwordZ'],flush=True)
 (OUT/'Evidence'/('clearance-'+version+'.json')).write_text(json.dumps(reports,indent=2))
