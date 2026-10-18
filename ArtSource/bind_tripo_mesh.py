"""Stage an approved, locally supplied Tripo mesh on the Veyr rig.

This does not call Tripo, spend credits, or assert final skinning quality.
First align the mesh in meters to the documented Blender rest pose; this
script deliberately does not guess anatomical alignment or alter topology.

blender Veyr_TEMP_Rig.blend --background --threads 2 --python bind_tripo_mesh.py
    -- --mesh approved_aligned.glb --output Veyr_Tripo_Working.blend

Requires the shared engine-slot protocol before launch.
"""
import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector

args=argparse.ArgumentParser()
args.add_argument('--mesh',required=True)
args.add_argument('--output',required=True)
opts=args.parse_args(sys.argv[sys.argv.index('--')+1:])
source=Path(opts.mesh).resolve();destination=Path(opts.output).resolve()
if not source.is_file():raise FileNotFoundError(source)
if destination.exists():raise FileExistsError('Refusing to overwrite existing art source')
rig=bpy.data.objects.get('Veyr_Rig')
if not rig or rig.type!='ARMATURE':raise RuntimeError('Open the Veyr source rig first')
before=set(bpy.data.objects)
if source.suffix.lower() in {'.glb','.gltf'}:bpy.ops.import_scene.gltf(filepath=str(source))
elif source.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(source))
elif source.suffix.lower()=='.obj':bpy.ops.wm.obj_import(filepath=str(source))
else:raise ValueError('Supported approved mesh formats: glb, gltf, fbx, obj')
imported=[ob for ob in set(bpy.data.objects)-before if ob.type=='MESH']
if not imported:raise RuntimeError('Import produced no mesh')
segments=[(b.name,Vector(b.head_local),Vector(b.tail_local)) for b in rig.data.bones if b.name!='root']

def distance_to_segment(p,a,b):
    v=b-a;t=max(0,min(1,(p-a).dot(v)/max(v.length_squared,1e-8)))
    return (p-a-t*v).length

for ob in imported:
    world=ob.matrix_world.copy()
    ob.parent=rig;ob.matrix_world=world
    ob.name='WIP_TRIPO_'+ob.name
    # Existing imported deform modifiers are not stacked over the new rig.
    for modifier in list(ob.modifiers):
        if modifier.type=='ARMATURE':ob.modifiers.remove(modifier)
    for group in list(ob.vertex_groups):ob.vertex_groups.remove(group)
    groups={name:ob.vertex_groups.new(name=name) for name,_,_ in segments}
    to_rig=rig.matrix_world.inverted()@ob.matrix_world
    for vertex in ob.data.vertices:
        p=to_rig@vertex.co
        nearest=sorted((distance_to_segment(p,a,b),name) for name,a,b in segments)[:3]
        values=[1/max(d,.08)**4 for d,_ in nearest];total=sum(values)
        for (_,name),value in zip(nearest,values):groups[name].add([vertex.index],value/total,'REPLACE')
    modifier=ob.modifiers.new('Veyr provisional skin — HAND REVIEW REQUIRED','ARMATURE');modifier.object=rig
    ob['skinning_status']='PROVISIONAL nearest-segment weights. Hand-paint joints and inspect all 14 actions.'
    ob['source_filename']=source.name
    ob['redistribution_status']='VERIFY APPROVED TRIPO PROVENANCE BEFORE PUBLICATION'
for ob in bpy.data.objects:
    if ob.name.startswith('TEMP_Veyr_Blockout'):
        ob.hide_render=True;ob.hide_set(True)
bpy.context.scene['asset_status']='TRIPO WORKING IMPORT: topology, weighting, action and rights review pending'
bpy.ops.wm.save_as_mainfile(filepath=str(destination))
print('TRIPO_STAGE_SAVED: '+destination.name+'; manual deformation review remains mandatory')
