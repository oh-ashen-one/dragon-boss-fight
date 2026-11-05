"""Retarget the already acquired Mixamo turns inside Blender for inspection.

Preserve source motion and editable actions. These are separate candidates,
not imported gameplay clips or replacements for accepted animations.
"""
import hashlib
import argparse
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT/'tools/art/blender/fab_rig_testing/retarget.py'
OUT = ROOT/'Local/AttackSources20261104/SourcedTurns'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path)
parser.add_argument('--full-foot-frames',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.output:
    OUT=args.output.resolve()
    assert OUT.is_relative_to(ROOT/'Local')
assert not OUT.exists(), 'Preserve earlier authoring/review candidates'
SRC = ROOT/'Local/AttackSources20261102/MixamoGreatSword/extracted'
JOBS = [
    ('Turn180_A', 'great sword 180 turn.fbx', '2c2619167a6a4c011a6f50786743c4cf6a55dd409dfa5bedcb18ffb23fb1dcdd'),
    ('Turn180_B', 'great sword 180 turn (2).fbx', 'f7b7f1edb67b19819c95174b56020f677135b8bf4253b41f2e6551999fe8c18f'),
    ('Turn_A', 'great sword turn.fbx', 'be010dad40f9d9fdd6f9b2ade4a23653b8af7441d9d5935f96d8a874b43789b8'),
    ('Turn_B', 'great sword turn (2).fbx', 'b126890a349342f5b96b6639fc43e959671e6f626443e9bfa1a15cbba3d1ab53'),
]
for _, filename, digest in JOBS:
    assert hashlib.sha256((SRC/filename).read_bytes()).hexdigest() == digest
ns = {'__file__': str(HELPER)}
exec(compile(HELPER.read_text(), str(HELPER), 'exec'), ns)
ns['OUT'] = OUT
ns['render'] = lambda *args: None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'Local/CustomuseAssets/Polish20261025/idle-joins/knight/IdleTwoHand_Blender_v2r4.glb'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
bpy.context.scene.frame_set(0)
hold = {b.name: b.matrix_basis.copy() for b in rig.pose.bones
        if any(b.name.startswith(side+'Hand'+finger) for side in ('Left','Right')
               for finger in ('Index','Middle','Ring','Pinky','Thumb'))}
review = {'__file__': str(HELPER)}
exec(compile(HELPER.read_text(), str(HELPER), 'exec'), review)
review['OUT'] = OUT
for key, filename, digest in JOBS:
    name = 'Mixamo_'+key+('_v2feet' if args.full_foot_frames else '_v1')
    # This process was created with --factory-startup and owns the entire scene.
    # The shared retarget helper requires the ownership marker before reset.
    bpy.context.scene['session_owner'] = ns['OWNER']
    ns['run'](SRC/filename, 'mixamo', name, True, False, True, hold,foot_frames=args.full_foot_frames)
    scene = bpy.context.scene
    rig = bpy.data.objects['Knight_Comparison']
    fps = scene.render.fps/scene.render.fps_base
    end = scene.frame_end
    scene.frame_set(0)
    first = (rig.matrix_world@rig.pose.bones['Hips'].matrix).copy()
    yaw = []
    for f in range(end+1):
        scene.frame_set(f)
        delta = (rig.matrix_world@rig.pose.bones['Hips'].matrix).to_quaternion()@first.to_quaternion().inverted()
        value = math.degrees(2*math.atan2(delta.z, delta.w))
        if yaw:
            while value-yaw[-1] > 180: value -= 360
            while value-yaw[-1] < -180: value += 360
        yaw.append(value)
    last = (rig.matrix_world@rig.pose.bones['Hips'].matrix).translation
    frames = sorted({round(i*fps/30) for i in range(round(end/fps*30)+1)})
    if args.full_foot_frames:
        # The game's character feet origin is source height0. Use that fixed
        # ground here, not this candidate's lowest vertex, so burial is visible.
        bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.0005))
        ground=bpy.context.object;ground.name='NativeZeroGround'
        material=bpy.data.materials.new('NativeZeroGround');material.diffuse_color=(.18,.20,.22,1)
        ground.data.materials.append(material)
    scales = review['render'](name, frames, resolution=960, auto_frame=True)
    p = OUT/'Exports'/(name+'.json')
    data = json.loads(p.read_text())
    data.update(sourceSHA256=digest, sourceURL='https://www.mixamo.com/',
                sourceLicense='Adobe Mixamo project incorporation; no raw-library redistribution',
                authoringApplication='Blender', editableScene=str(p.with_suffix('.blend').relative_to(ROOT)),
                sourcePlanarTravel=list(last-first.translation),
                observedHipTwistDegrees=yaw, observedFinalTurnDegrees=yaw[-1],
                reviewFrames=frames, reviewFPS=30, viewOrthoScales=scales,
                nativeImported=False, accepted=False)
    data['reviewGroundSourceUnits']=0. if args.full_foot_frames else None
    p.write_text(json.dumps(data, indent=2)+'\n')
print('SOURCED_TURN_CANDIDATES_RENDERED_NOT_ACCEPTED', flush=True)
