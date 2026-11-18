"""Trial T1/T2 look check: one render per Greystone skin, same camera and light, beside a 244 cm pole and the current
KnightB, plus the Default skin with the shield pinned on the back (shield_back target) and the retargeted Idle.
Rendered commandlet (run_greystone.py skin-sheet: shared GPU slot, -AllowCommandletRendering, never while STREAMING).
compose_sheet.py then lays the frames out next to the owner's pick
(Local/knight-candidates/greystone-owner-pick-20261118.png) for a by-eye skin decision - nothing here scores it.

Scene (a new level under /Game/Characters/Greystone/Review, .gitignored): flat grey floor, one directional key light
45 degrees high from front-left, a sky light at 1.0, a SceneCapture2D at 1.6 m height, 7 m away, 35 degree FOV, final
colour LDR into a 1024x1024 RGBA8 render target, exported as PNG with UKismetRenderingLibrary::ExportRenderTarget.
Not run yet: Paragon (UE 4.19) materials compile on first load, so the first run is slow.
"""
import json
import math
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
opts = job['options']
assert '-allowcommandletrendering' in unreal.SystemLibrary.get_command_line().lower(), 'needs -AllowCommandletRendering'
level_path = g.OURS + '/Review/L_SkinSheet'
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if unreal.EditorAssetLibrary.does_asset_exist(level_path):
    levels.load_level(level_path)
else:
    levels.new_level(level_path)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in actors.get_all_level_actors():
    actors.destroy_actor(a)

floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -1))
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(40, 40, 1))
sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500), unreal.Rotator(0, -45, 135))
sun.light_component.set_intensity(6.0)
sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300))
sky.light_component.set_intensity(1.0)
pole = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, -160, g.TARGET_HEIGHT_CM / 2))
pole.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cylinder'))
pole.set_actor_scale3d(unreal.Vector(.08, .08, g.TARGET_HEIGHT_CM / 100.0))  # basic cylinder is 100 cm tall

capture = actors.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(700, 0, 160), unreal.Rotator(0, -4, 180))
component = capture.capture_component2d
target = unreal.RenderingLibrary.create_render_target2d(world, 1024, 1024, unreal.TextureRenderTargetFormat.RTF_RGBA8)
component.set_editor_property('texture_target', target)
component.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
component.set_editor_property('fov_angle', 35.0)
component.set_editor_property('b_capture_every_frame', False)

scale = json.loads(Path(opts['scaleFile']).read_text()) if opts.get('scaleFile') else None
g_scale = scale['scale'] if scale else 1.0
g_yaw = scale['yawDegrees'] if scale else -90.0
frames = []


def shoot(name, setup):
    spawned = setup()
    for view, yaw in (('front', 0.0), ('side', 90.0)):
        capture.set_actor_location_and_rotation(
            unreal.Vector(700 * math.cos(math.radians(yaw)), 700 * math.sin(math.radians(yaw)), 160),
            unreal.Rotator(0, -4, 180 + yaw), False, False)
        component.capture_scene()
        file = f'{len(frames):02d}-{name}-{view}'
        unreal.RenderingLibrary.export_render_target(world, target, str(out), file + '.png')
        frames.append({'file': file + '.png', 'subject': name, 'view': view})
    for a in spawned:
        actors.destroy_actor(a)


def skeletal(path, location, scale_value, yaw):
    actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, location, unreal.Rotator(0, yaw, 0))
    actor.skeletal_mesh_component.set_skinned_asset_and_update(unreal.load_asset(path))
    actor.set_actor_scale3d(unreal.Vector(scale_value, scale_value, scale_value))
    return actor


knight = unreal.load_asset(g.KNIGHT_DEFINITION)
k_rel = knight.get_editor_property('mesh_relative_transform')
k_mesh = knight.get_editor_property('skeletal_mesh').get_path_name()
for skin, path in g.SKINS.items():
    shoot('greystone-' + skin, lambda path=path: [skeletal(path, unreal.Vector(0, 0, 0), g_scale, g_yaw),
                                                  skeletal(k_mesh, unreal.Vector(0, 160, 0), k_rel.scale3d.z, k_rel.rotation.rotator().yaw)])

# Shield on the back (two-hand grip) on a poseable copy of the Default skin, from DA_Greystone's shield_back target.
definition = unreal.load_asset(g.DEFINITION) if unreal.EditorAssetLibrary.does_asset_exist(g.DEFINITION) else None
if definition:
    tgt = definition.get_editor_property('bone_targets').get('shield_back')

    def posed():
        actor = actors.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0), unreal.Rotator(0, g_yaw, 0))
        poseable = actor.add_component_by_class(unreal.PoseableMeshComponent, False, unreal.Transform(), False) \
            if hasattr(actor, 'add_component_by_class') else None
        if poseable is None:
            raise RuntimeError('PoseableMeshComponent could not be added (editor API changed?)')
        poseable.set_skinned_asset_and_update(unreal.load_asset(g.GREYSTONE_MESH))
        actor.set_actor_scale3d(unreal.Vector(g_scale, g_scale, g_scale))
        anchor = poseable.get_bone_transform_by_name(tgt.get_editor_property('bone_name'), unreal.BoneSpaces.COMPONENT_SPACE)
        poseable.set_bone_transform_by_name('shield_inner', tgt.get_editor_property('local_offset') * anchor, unreal.BoneSpaces.COMPONENT_SPACE)
        return [actor]
    shoot('greystone-Default-shield-back', posed)

(out / 'frames.json').write_text(json.dumps({'frames': frames, 'scale': g_scale, 'yaw': g_yaw, 'poleCm': g.TARGET_HEIGHT_CM}, indent=1) + '\n')
g.write_result(out, {'success': all((out / f['file']).is_file() for f in frames), 'frames': len(frames)})
