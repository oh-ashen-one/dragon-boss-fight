import bpy,bmesh,math,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'Local/Overhaul20261026/architecture'
m=next(o for o in bpy.context.scene.objects if o.type=='MESH');vs=m.data.vertices;adj=[set() for _ in vs]
for e in m.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
seen=set();remove=set()
for i in range(len(vs)):
 if i in seen:continue
 todo=[i];ids=[];seen.add(i)
 while todo:
  j=todo.pop();ids.append(j)
  for k in adj[j]:
   if k not in seen:seen.add(k);todo.append(k)
 if max(math.hypot(vs[j].co.x,vs[j].co.y) for j in ids)>1.65 and min(vs[j].co.z for j in ids)>1.6:remove.update(ids)
assert remove,'Expected fabric shade islands'
bm=bmesh.new();bm.from_mesh(m.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in remove],context='VERTS');bm.to_mesh(m.data);bm.free();m.data.update()
for o in bpy.context.scene.objects:o.select_set(o==m)
bpy.context.view_layer.objects.active=m
f=OUT/'Chandelier_Normalized.glb';bpy.ops.export_scene.gltf(filepath=str(f),export_format='GLB',use_selection=True,export_animations=False,export_cameras=False,export_lights=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Chandelier_Adapted.blend'),compress=True)
s=bpy.context.scene;s.render.filepath=str(OUT/'chandelier-review.png');bpy.ops.render.render(write_still=True)
p=OUT/'manifest.json';report=json.loads(p.read_text());report['sha256']=hashlib.sha256(f.read_bytes()).hexdigest();report['trianglesAfter']=sum(len(p.vertices)-2 for p in m.data.polygons);report['modifications']+='; removed fabric shade islands, retaining original iron scrollwork, candles, stem and suspension chain';p.write_text(json.dumps(report,indent=2));print(report)
