"""Inspect licensed source FBXs in a fresh task-owned Blender process; never save them."""
import bpy
import hashlib
import json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'Local/AttackSources20261101/KevinIglesias/extracted'
OUT=ROOT/'Local/AttackSources20261101/KevinIglesias/inspection.json'
assert not OUT.exists()
records=[]
for rel in ['Models/HumanM_Model.fbx','Animations/Male/Combat/2H/HumanM@Attack2H01.fbx',
            'Animations/Female/Combat/2H/HumanF@Attack2H01.fbx',
            'Animations/Male/Combat/2H/HumanM@CombatIdle2H01.fbx']:
    path=SOURCE/rel;sha=hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps=30
    bpy.ops.import_scene.fbx(filepath=str(path))
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
    rig=rigs[0];act=rig.animation_data.action if rig.animation_data else None
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    points=[o.matrix_world@Vector(p) for o in meshes for p in o.bound_box]
    bounds=[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)] if points else None
    record={'file':rel,'sha256':sha,'rig':rig.name,'objectScale':list(rig.scale),'bones':list(rig.data.bones.keys()),
            'rest':{b.name:[list(row) for row in rig.matrix_world@b.matrix_local] for b in rig.data.bones},
            'fps':bpy.context.scene.render.fps/bpy.context.scene.render.fps_base,'bounds':bounds,
            'action':act.name if act else None,'frames':list(act.frame_range) if act else None}
    if act:
        start,end=act.frame_range;record['durationSeconds']=(end-start)/record['fps']
        record['samples']=[]
        for phase in [0,.25,.5,.75,1]:
            frame=start+(end-start)*phase;bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame))
            record['samples'].append({'phase':phase,'bones':{b.name:[list(row) for row in rig.matrix_world@b.matrix] for b in rig.pose.bones if any(s in b.name.lower() for s in ['hand','wrist','hips','pelvis','foot'])}})
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    records.append(record)
OUT.write_text(json.dumps({'sourceUnchanged':True,'records':records},indent=2)+'\n')
print('VEYR_KEVIN_SOURCE_INSPECTION_COMPLETE',flush=True)
