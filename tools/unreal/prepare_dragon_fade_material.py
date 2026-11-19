"""Camera fifth pass (2026-11-19): clone each dragon camera-tunnel material into a "dragon gives way" fade material.

Run headless through the engine lock (no window, no GPU):
  engine_lock.py --label "fade material <tree>" -- UnrealEditor-Cmd Veyr.uproject -run=pythonscript \
      -script=tools/unreal/prepare_dragon_fade_material.py -nullrhi -unattended
Job: env VEYR_FADE_JOB=<json> with {"report": "<dir under Local/>"}.

For every tunnel material the runtime dragon can bind (the polish definition's CameraOcclusionMaterial and the
slot materials of its skeletal meshes), a clone <Name>_Fade goes to /Game/Characters/Customuse/RuntimePolish/Fade
(always cooked). The clone keeps the source PBR graph; only the tunnel Custom node's code and inputs change and its
output bypasses the temporal dither (own screen-space interleaved noise, stepped with the TAA frame index). Sources are never
modified. The knight definition's materials are only inspected (blend mode, two-sided, parameters).

Mask (all world cm): 1 = keep, 0 = clip.
  distance fade   kept fraction smoothstep(FadeNear, FadeFar, |p - lens|)
  sight fade      inside the capsule lens -> knight focus (radius SightRadius), nearer than the knight:
                  kept fraction lerp(1, SightFloor, SightAmount)
  back faces      clipped wherever either fade is active at the pixel, and everywhere while BackDiscard > 0
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'Veyr camera tunnel / '
FADE_DIR = '/Game/Characters/Customuse/RuntimePolish/Fade'
NEW_SCALARS = {'VeyrFadeNear': 80., 'VeyrFadeFar': 220., 'VeyrSightRadius': 180., 'VeyrSightAmount': 0.,
               'VeyrSightFloor': .22, 'VeyrBackDiscard': 0.}
OLD_INPUTS = [('WorldPosition', None), ('CameraStart', 'VeyrCameraStart'), ('PlayerFocus', 'VeyrPlayerFocus'),
              ('ProtectedHead', 'VeyrProtectedHead'), ('Radius', 'VeyrOcclusionRadius'),
              ('ProtectedHeadRadius', 'VeyrProtectedHeadRadius'), ('Enabled', 'VeyrOcclusionEnabled')]
NEW_INPUTS = [('FadeNear', 'VeyrFadeNear'), ('FadeFar', 'VeyrFadeFar'), ('SightRadius', 'VeyrSightRadius'),
              ('SightAmount', 'VeyrSightAmount'), ('SightFloor', 'VeyrSightFloor'), ('BackDiscard', 'VeyrBackDiscard')]

HLSL = r'''
// Veyr camera fifth pass: the dragon gives way near the lens and in front of the knight. World cm.
if (Enabled <= 0.0) return 1.0;
float3 toLens = WorldPosition - CameraStart;
float keep = smoothstep(FadeNear, max(FadeFar, FadeNear + 1.0), length(toLens));
float3 seg = PlayerFocus - CameraStart;
float lengthSquared = dot(seg, seg);
if (SightAmount > 0.0 && lengthSquared > 1.0)
{
    float segmentLength = sqrt(lengthSquared);
    float along = dot(toLens, seg) / segmentLength;
    if (along > 0.0 && along < segmentLength)
    {
        float radius = max(SightRadius, 1.0);
        float radial = length(toLens - seg * (along / segmentLength));
        float inCapsule = 1.0 - smoothstep(radius * 0.55, radius, radial);
        float knightEnd = smoothstep(0.0, radius * 0.35, segmentLength - along);
        keep = min(keep, lerp(1.0, SightFloor, saturate(SightAmount) * inCapsule * knightEnd));
    }
}
// Never an interior surface: back faces go wherever a fade touches the pixel, and everywhere while flagged.
if (Parameters.TwoSidedSign < 0.0 && (BackDiscard > 0.0 || keep < 0.999)) return 0.0;
if (keep >= 0.999) return 1.0;
float2 pixel = Parameters.SvPosition.xy;
// Interleaved gradient noise stepped with TAA's own frame index (as DitherTemporalAA does), so the history
// resolves the stipple into an even thinning instead of a fixed pattern that sparkles on moving skin.
pixel += 5.588238 * View.TemporalAAParams.x;
float noise = frac(52.9829189 * frac(dot(pixel, float2(0.06711056, 0.00583715))));
return keep > noise ? 1.0 : 0.0;
'''.strip()


def main():
    import unreal
    lib = unreal.MaterialEditingLibrary
    assets = unreal.EditorAssetLibrary
    job = json.loads(Path(os.environ['VEYR_FADE_JOB']).read_text())
    report = Path(job['report'])
    result = {'success': False, 'materials': [], 'knight': [], 'hlsl': HLSL}

    def save():
        (report / 'result.json').write_text(json.dumps(result, indent=2))

    def describe(material):
        row = {'path': material.get_path_name(), 'class': material.get_class().get_name()}
        base = material
        try:
            base = material.get_base_material()
        except Exception:
            pass
        row['base'] = base.get_path_name() if base else None
        for key in ('blend_mode', 'two_sided', 'opacity_mask_clip_value', 'used_with_skeletal_mesh'):
            try:
                row[key] = str(base.get_editor_property(key))
            except Exception as error:
                row[key] = 'n/a ' + str(error)[:60]
        try:
            row['scalars'] = [str(n) for n in lib.get_scalar_parameter_names(base)]
        except Exception:
            pass
        return row

    try:
        dragon = assets.load_asset('/Game/Characters/Customuse/RuntimePolish/DA_Dragon')
        knight = assets.load_asset('/Game/Characters/Customuse/RuntimePolish/DA_Knight')
        if dragon is None:
            raise RuntimeError('polish dragon definition missing')
        sources = []
        occlusion = dragon.get_editor_property('camera_occlusion_material')
        if occlusion:
            sources.append(occlusion)
        meshes = [dragon.get_editor_property('skeletal_mesh')]
        for clip in dragon.get_editor_property('clips').values():
            mesh = clip.get_editor_property('mesh_override')
            if mesh and mesh not in meshes:
                meshes.append(mesh)
        result['meshes'] = []
        for mesh in meshes:
            if not mesh:
                continue
            slots = [m.get_editor_property('material_interface') for m in mesh.get_editor_property('materials')]
            result['meshes'].append({'mesh': mesh.get_path_name(), 'slots': [s.get_path_name() if s else None for s in slots]})
            for slot in slots:
                if slot and slot not in sources:
                    sources.append(slot)
        for source in sources:
            row = describe(source)
            result['materials'].append(row)
            if not isinstance(source, unreal.Material):
                row['skipped'] = 'not a direct material'
                continue
            customs = [x for x in lib.get_material_expressions(source) if isinstance(x, unreal.MaterialExpressionCustom)
                       and str(x.get_editor_property('desc')) == PREFIX + 'visibility_math']
            if len(customs) != 1:
                row['skipped'] = 'no camera tunnel node'
                continue
            destination = FADE_DIR + '/' + source.get_name() + '_Fade'
            if assets.does_asset_exist(destination):
                assets.delete_asset(destination)
            material = assets.duplicate_asset(source.get_path_name(), destination)
            if not isinstance(material, unreal.Material):
                raise RuntimeError('clone failed: ' + destination)
            expressions = list(lib.get_material_expressions(material))
            by_desc = {str(x.get_editor_property('desc')): x for x in expressions}
            custom = by_desc[PREFIX + 'visibility_math']
            params = {}
            for x in expressions:
                try:
                    params[str(x.get_editor_property('parameter_name'))] = x
                except Exception:
                    pass
            world = by_desc.get(PREFIX + 'world_position')
            if world is None:
                raise RuntimeError('world position node missing')
            count = 0
            for name, value in NEW_SCALARS.items():
                if name in params:
                    continue
                node = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -3400, -900 + count * 120)
                node.set_editor_property('parameter_name', name)
                node.set_editor_property('default_value', value)
                node.set_editor_property('desc', PREFIX + 'fade ' + name)
                params[name] = node
                count += 1
            inputs = []
            for name, _ in OLD_INPUTS + NEW_INPUTS:
                entry = unreal.CustomInput()
                entry.set_editor_property('input_name', name)
                inputs.append(entry)
            custom.set_editor_property('inputs', inputs)
            custom.set_editor_property('code', HLSL)
            custom.set_editor_property('description', 'Camera fifth pass: distance and sight fade, back faces clipped')
            for name, parameter in OLD_INPUTS + NEW_INPUTS:
                node = world if parameter is None else params[parameter]
                if not lib.connect_material_expressions(node, '', custom, name):
                    raise RuntimeError('connect failed: ' + name)
            shadow = by_desc.get(PREFIX + 'preserve_shadow_mask')
            final = by_desc.get(PREFIX + 'final_mask')
            if shadow is not None:
                ok = lib.connect_material_expressions(custom, '', shadow, 'Default')
            elif final is not None:
                ok = lib.connect_material_expressions(custom, '', final, 'B')
            else:
                raise RuntimeError('no mask output node')
            if not ok:
                raise RuntimeError('mask rewire failed')
            material.set_editor_property('opacity_mask_clip_value', .5)
            errors = [str(e) for e in lib.recompile_material(material)]
            row['fade'] = destination
            row['compileErrors'] = errors
            if errors:
                raise RuntimeError('compile errors: ' + '; '.join(errors)[:400])
            if not assets.save_loaded_asset(material, False):
                raise RuntimeError('save failed: ' + destination)
            row['fadeScalars'] = [str(n) for n in lib.get_scalar_parameter_names(material)]
        if knight:
            mesh = knight.get_editor_property('skeletal_mesh')
            if mesh:
                for m in mesh.get_editor_property('materials'):
                    slot = m.get_editor_property('material_interface')
                    if slot:
                        result['knight'].append(describe(slot))
        result['success'] = any('fade' in row for row in result['materials'])
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        save()
        unreal.log('VEYR_FADE_MATERIAL_RESULT ' + str(report / 'result.json'))


main()
