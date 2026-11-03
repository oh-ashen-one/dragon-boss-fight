"""Assign the measured flat plaster faces a mural UV/material slot, preserving the generated wall."""
import argparse,json,sys,hashlib
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('blend',type=Path);p.add_argument('output',type=Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.output.mkdir(parents=True,exist_ok=True)
out=a.output/'FortressMuralWall_baked.glb';assert not out.exists()
bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()));o=bpy.data.objects['FortressMuralWall'];mesh=o.data
# Coordinates in the baked generated source, metres. The panel is broad and
# flat inside the imported stone/iron frame. A centred 2:1 region preserves
# the generated paintings' aspect ratio and leaves worn plaster at the edges.
x0,x1,z0,z1=-.27,.27,.135,.405
mat=bpy.data.materials.new('FortressMuralSurface');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.25,.25,.25,1);bs.inputs['Roughness'].default_value=.94
mesh.materials.append(mat);slot=len(mesh.materials)-1;uv=mesh.uv_layers.active.data;selected=[]
for f in mesh.polygons:
 c=f.center
 if x0<=c.x<=x1 and z0<=c.z<=z1 and c.y<0 and f.normal.y<-.8:
  f.material_index=slot;selected.append(f)
  for li in f.loop_indices:
   v=mesh.vertices[mesh.loops[li].vertex_index].co
   uv[li].uv=((v.x-x0)/(x1-x0),(v.z-z0)/(z1-z0))
assert len(selected)>1000,'Insufficient flat front plaster faces'
y=[mesh.vertices[i].co.y for f in selected for i in f.vertices]
report={'sourceBlend':str(a.blend),'selectedFaces':len(selected),'materialSlot':slot,'sourceRectangle':[x0,x1,z0,z1],'aspectRatio':2.,'surfaceDepthRange': [min(y),max(y)],'method':'Reassigned existing generated plaster faces; no floating decal plane, changed topology or new sculpt. UV mapping is front-facing 2:1.'}
for obj in bpy.context.scene.objects:obj.select_set(False)
o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o
bpy.ops.export_scene.gltf(filepath=str(out.resolve()),export_format='GLB',use_selection=True,export_apply=True,export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=str((a.output/'FortressMuralWall.blend').resolve()))
report['sha256']=hashlib.sha256(out.read_bytes()).hexdigest();(a.output/'mural-surface.json').write_text(json.dumps(report,indent=2)+'\n');print('MURAL_SURFACE_PREPARED',len(selected),flush=True)
