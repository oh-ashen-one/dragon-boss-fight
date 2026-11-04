"""Guarded review of actions actually authored and refined inside Blender.

Run through gpu_slot only, after the owned intro request has finished. Creates
private editable review copies and unannotated source frames. Not an acceptance.
"""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'Local/AttackSources20261104/BlenderReview'
SOURCES = [ROOT/'Local/AttackSources20261103/ForwardRigidPlants/Mixamo_ForwardRun_v4rigid.blend',
           ROOT/'Local/AttackSources20261104/BlenderMotion/FabMixamo_OneHandRun_v2blender.blend',
           ROOT/'Local/AttackSources20261104/BlenderMotion/Mixamo_SlideAttack_v4blender.blend']
helper = ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
ns = {'__file__': str(helper)}
exec(compile(helper.read_text(), str(helper), 'exec'), ns)
ns['OUT'] = OUT
assert not OUT.exists(), 'Preserve earlier review frames'
OUT.mkdir(parents=True)
for source in SOURCES:
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False)
    scene = bpy.context.scene
    rig = bpy.data.objects['Knight_Comparison']
    duration = max(rig.animation_data.action.frame_range)
    scene.frame_start, scene.frame_end = 0, round(duration)
    floor = float('inf')
    body = [o for o in scene.objects if o.type == 'MESH' and
            any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
    for frame in range(scene.frame_end+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        for obj in body:
            evaluated = obj.evaluated_get(deps)
            mesh = evaluated.to_mesh()
            groups = {g.index for g in obj.vertex_groups if g.name in ['LeftFoot', 'LeftToeBase', 'RightFoot', 'RightToeBase']}
            indices = [v.index for v in obj.data.vertices if sum(w.weight for w in v.groups if w.group in groups) > .75]
            if indices:
                floor = min(floor, min((evaluated.matrix_world @ mesh.vertices[i].co).z for i in indices))
            evaluated.to_mesh_clear()
    assert abs(floor) < .5
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, floor-.0005))
    ground = bpy.context.object
    ground.name = 'ReviewGround'
    material = bpy.data.materials.new('ReviewGround')
    material.diffuse_color = (.18, .20, .22, 1)
    ground.data.materials.append(material)
    for axis in range(2):
        for i in range(-20, 21):
            curve = bpy.data.curves.new('GridLine', 'CURVE')
            curve.dimensions = '3D'
            curve.bevel_depth = .001
            line = curve.splines.new('POLY')
            line.points.add(1)
            line.points[0].co = (-10, i*.25, floor+.0002, 1) if axis == 0 else (i*.25, -10, floor+.0002, 1)
            line.points[1].co = (10, i*.25, floor+.0002, 1) if axis == 0 else (i*.25, 10, floor+.0002, 1)
            obj = bpy.data.objects.new('GridLine', curve)
            scene.collection.objects.link(obj)
    fps=scene.render.fps/scene.render.fps_base
    frames = sorted({round(i*fps/30) for i in range(round(scene.frame_end/fps*30)+1)})
    ns['render'](source.stem, frames)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(source.stem+'.blend')), compress=True)
    (OUT/(source.stem+'.json')).write_text(json.dumps({'source': str(source.relative_to(ROOT)), 'frames': frames,
        'sourceFPS': fps, 'reviewFPS': 30, 'groundHeightSourceUnits': floor, 'reviewed': False, 'accepted': False}, indent=2)+'\n')
print('BLENDER_AUTHORED_MOTION_REVIEW_RENDERED', flush=True)
