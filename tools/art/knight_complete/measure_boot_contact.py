"""Read-only source-mesh sole/marker measurements; run in task-owned background Blender."""
import argparse
import bpy
import hashlib
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser()
p.add_argument('source',type=Path)
p.add_argument('output',type=Path)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
assert not a.output.exists()
before=hashlib.sha256(a.source.read_bytes()).hexdigest()
bpy.ops.import_scene.gltf(filepath=str(a.source))
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE' and 'LeftToeBase' in o.pose.bones]
assert len(rigs)==1
rig=rigs[0];action=rig.animation_data.action
assert action
start,end=map(float,action.frame_range)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
samples=[]
for phase in [0.,.47,.5,.97,1.]:
    frame=start+(end-start)*phase
    bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    for side in ['Left','Right']:
        toe=(rig.matrix_world@rig.pose.bones[side+'ToeBase'].matrix).translation
        ankle=(rig.matrix_world@rig.pose.bones[side+'Foot'].matrix).translation
        positions=[]
        for mesh in meshes:
            groups={g.index for g in mesh.vertex_groups if g.name in [side+'Foot',side+'ToeBase']}
            if not groups:continue
            ev=mesh.evaluated_get(deps);data=ev.to_mesh()
            assert len(data.vertices)==len(mesh.data.vertices)
            for v in mesh.data.vertices:
                if sum(g.weight for g in v.groups if g.group in groups)>=.5:
                    positions.append((ev.matrix_world@data.vertices[v.index].co).z)
            ev.to_mesh_clear()
        assert positions
        positions.sort();sole=positions[0]
        samples.append({'phase':phase,'side':side,'vertices':len(positions),
                        'soleZ':sole,'solePercentile1Z':positions[len(positions)//100],
                        'toeZ':toe.z,'ankleZ':ankle.z,'toeAboveSole':toe.z-sole,
                        'ankleAboveSole':ankle.z-sole})
assert hashlib.sha256(a.source.read_bytes()).hexdigest()==before
result={'source':str(a.source),'sha256':before,'sourceUnchanged':True,'actionFrames':[start,end],
        'coordinateUnits':'Blender world units after glTF import; determine native scale separately',
        'selection':'vertices with at least 0.5 combined weight on Foot/ToeBase; no geometry edits',
        'samples':samples}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
print('VEYR_BOOT_CONTACT_MEASURED',flush=True)
