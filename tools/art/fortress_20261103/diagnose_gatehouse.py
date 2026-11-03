"""Compare retained source and reduced mesh with identical review lighting/camera."""
import bpy,json,sys
from pathlib import Path
p=Path(sys.argv[sys.argv.index('--')+1]);bpy.ops.wm.open_mainfile(filepath=str((p/'FortressGatehouse.blend').resolve()));scene=bpy.context.scene;assert scene.get('session_owner')=='veyr-fortress-20261103'
raw=bpy.data.objects['SOURCE_Gatehouse'];low=bpy.data.objects['FortressGatehouse'];info={}
for obj in [raw,low]:
 info[obj.name]={'smoothFaces':sum(f.use_smooth for f in obj.data.polygons),'faces':len(obj.data.polygons),'hasCustomNormals':obj.data.has_custom_normals,'materials':[]}
 for m in obj.data.materials:
  info[obj.name]['materials'].append({'name':m.name,'imageNodes':[{'name':n.image.name,'colorSpace':n.image.colorspace_settings.name} for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]})
raw.hide_set(False);raw.hide_render=False;low.hide_render=True;scene.render.filepath=str((p/'source-threequarter.png').resolve());bpy.ops.render.render(write_still=True)
# Separate material copy isolates normal-map contribution without changing source.
raw.hide_render=True;low.hide_render=False
for slot in low.material_slots:
 slot.material=slot.material.copy();m=slot.material;bsdf=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 for link in list(bsdf.inputs['Normal'].links):m.node_tree.links.remove(link)
scene.render.filepath=str((p/'reduced-no-normalmap.png').resolve());bpy.ops.render.render(write_still=True)
(p/'normal-diagnosis.json').write_text(json.dumps(info,indent=2)+'\n');print('GATEHOUSE_DIAGNOSIS_COMPLETE',flush=True)
