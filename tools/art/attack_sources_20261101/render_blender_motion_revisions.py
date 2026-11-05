"""Guarded review of actions actually authored and refined inside Blender.

Run through gpu_slot only, after the owned intro request has finished. Creates
private editable review copies and unannotated source frames. Not an acceptance.
"""
import bpy
import argparse
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'Local/AttackSources20261104/BlenderReviewFramed'
SOURCES = [ROOT/'Local/AttackSources20261103/ForwardRigidPlants/Mixamo_ForwardRun_v4rigid.blend',
           ROOT/'Local/AttackSources20261104/BlenderMotion/FabMixamo_OneHandRun_v2blender.blend',
           ROOT/'Local/AttackSources20261104/BlenderMotion/Mixamo_SlideAttack_v4blender.blend']
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-directory',type=Path)
parser.add_argument('--source',type=Path,action='append')
parser.add_argument('--output',type=Path)
parser.add_argument('--floor-source',type=float)
parser.add_argument('--ortho-scale',type=float)
parser.add_argument('--reference-review-directory',type=Path,help='Match existing per-view camera scales for before/after playback')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
reference_reviews={}
if args.reference_review_directory:
    reference=args.reference_review_directory.resolve(strict=True)
    assert reference.is_relative_to(ROOT/'Local') and args.ortho_scale is None
    reference_reviews={p.stem.rsplit('_v',1)[0]:p for p in reference.glob('*.json') if p.with_suffix('.blend').exists()}
    assert reference_reviews
assert not (args.source and args.source_directory)
if args.source:
    SOURCES=[p.resolve(strict=True) for p in args.source]
    assert args.output and all(p.is_relative_to(ROOT/'Local') and p.suffix=='.blend' for p in SOURCES)
if args.source_directory:
    source_directory=args.source_directory.resolve(strict=True)
    assert source_directory.is_relative_to(ROOT/'Local')
    SOURCES=sorted(source_directory.glob('*.blend'))
    assert SOURCES and args.output
if args.output:
    OUT=args.output.resolve()
    assert OUT.is_relative_to(ROOT/'Local')
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
    measured_floor=floor
    if args.floor_source is not None:
        assert abs(args.floor_source)<.5
        floor=args.floor_source
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
    frames = sorted({min(scene.frame_end,round(i*fps/30)) for i in range(round(scene.frame_end/fps*30)+1)})
    assert args.ortho_scale is None or args.ortho_scale>0
    reference_path=reference_reviews.get(source.stem.rsplit('_v',1)[0])
    if reference_reviews:assert reference_path, 'Missing matched baseline camera'
    reference_scales=json.loads(reference_path.read_text())['viewOrthoScales'] if reference_path else None
    scales=ns['render'](source.stem, frames, ortho_scale=args.ortho_scale or 2.1,resolution=960,
        auto_frame=args.ortho_scale is None and reference_scales is None,view_ortho_scales=reference_scales)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(source.stem+'.blend')), compress=True)
    (OUT/(source.stem+'.json')).write_text(json.dumps({'source': str(source.relative_to(ROOT)), 'frames': frames,
        'sourceFPS': fps, 'reviewFPS': 30, 'viewOrthoScales':scales,'groundHeightSourceUnits': floor,
        'measuredMinimumBootHeightSourceUnits':measured_floor,'referenceCameraMetadata':str(reference_path.relative_to(ROOT)) if reference_path else None,
        'reviewed': False, 'accepted': False}, indent=2)+'\n')
print('BLENDER_AUTHORED_MOTION_REVIEW_RENDERED', flush=True)
