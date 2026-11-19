"""B5/B6 (2026-11-18): author the two owned feel materials, never replacing art that is not ours.

  /Game/Veyr/FX/Feel/M_VeyrHitFlash     additive unlit overlay for the dragon mesh; lights a sphere around the
                                         blow: FlashColor * Intensity * saturate(1 - |WorldPos - HitPos| / Radius)^2
  /Game/Veyr/FX/Feel/M_VeyrWeaponTrail  translucent unlit two-sided ribbon; colour and alpha from vertex colour,
                                         scaled by Tint, Brightness and Opacity; soft at both long edges

Run inside the editor (owned instance, PythonScriptPlugin):  UnrealEditor-Cmd Veyr.uproject -run=pythonscript
-script=tools/unreal/create_feel_materials.py. Until it runs, AVeyrFightFeel uses M_BlinkAfterimage as the fallback.
"""
import unreal

FOLDER = '/Game/Veyr/FX/Feel'
OWNER = 'Veyr.quality-goal-B5B6.20261118'
LIB = unreal.MaterialEditingLibrary


def owned_or_new(name):
    path = f'{FOLDER}/{name}'
    existing = unreal.load_asset(path)
    if existing:
        if not isinstance(existing, unreal.Material) or unreal.EditorAssetLibrary.get_metadata_tag(existing, 'VeyrOwner') != OWNER:
            raise RuntimeError(f'Preserving material at occupied path {path}')
        LIB.delete_all_material_expressions(existing)
        return existing
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError(f'{name} creation failed')
    return material


def node(material, cls, x, y, **props):
    expression = LIB.create_material_expression(material, cls, x, y)
    for key, value in props.items():
        expression.set_editor_property(key, value)
    return expression


def link(a, a_out, b, b_in):
    if not LIB.connect_material_expressions(a, a_out, b, b_in):
        raise RuntimeError(f'connect {a.get_name()}.{a_out} -> {b.get_name()}.{b_in} failed')


def finish(material, emissive, opacity=None):
    if not LIB.connect_material_property(emissive, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError('emissive connection failed')
    if opacity is not None and not LIB.connect_material_property(opacity, '', unreal.MaterialProperty.MP_OPACITY):
        raise RuntimeError('opacity connection failed')
    unreal.EditorAssetLibrary.set_metadata_tag(material, 'VeyrOwner', OWNER)
    LIB.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f'{material.get_name()} save failed')


def hit_flash():
    m = owned_or_new('M_VeyrHitFlash')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('used_with_skeletal_mesh', True)
    m.set_editor_property('two_sided', False)
    world = node(m, unreal.MaterialExpressionWorldPosition, -900, 0)
    hit = node(m, unreal.MaterialExpressionVectorParameter, -900, 150, parameter_name='HitPos', default_value=unreal.LinearColor(0, 0, 0, 0))
    radius = node(m, unreal.MaterialExpressionScalarParameter, -700, 300, parameter_name='Radius', default_value=120.0)
    intensity = node(m, unreal.MaterialExpressionScalarParameter, -300, 300, parameter_name='Intensity', default_value=0.0)
    colour = node(m, unreal.MaterialExpressionVectorParameter, -300, 450, parameter_name='FlashColor', default_value=unreal.LinearColor(1, .82, .6, 1))
    distance = node(m, unreal.MaterialExpressionDistance, -650, 60)
    link(world, '', distance, 'A'); link(hit, '', distance, 'B')
    ratio = node(m, unreal.MaterialExpressionDivide, -500, 100)
    link(distance, '', ratio, 'A'); link(radius, '', ratio, 'B')
    inverse = node(m, unreal.MaterialExpressionOneMinus, -380, 100); link(ratio, '', inverse, '')
    clamp = node(m, unreal.MaterialExpressionSaturate, -280, 100); link(inverse, '', clamp, '')
    square = node(m, unreal.MaterialExpressionMultiply, -180, 100); link(clamp, '', square, 'A'); link(clamp, '', square, 'B')
    lit = node(m, unreal.MaterialExpressionMultiply, -60, 160); link(square, '', lit, 'A'); link(intensity, '', lit, 'B')
    out = node(m, unreal.MaterialExpressionMultiply, 80, 200); link(lit, '', out, 'A'); link(colour, '', out, 'B')
    finish(m, out)


def weapon_trail():
    m = owned_or_new('M_VeyrWeaponTrail')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided', True)
    m.set_editor_property('used_with_static_lighting', False)
    vertex = node(m, unreal.MaterialExpressionVertexColor, -700, 0)
    tint = node(m, unreal.MaterialExpressionVectorParameter, -700, 200, parameter_name='Tint', default_value=unreal.LinearColor(1, 1, 1, 1))
    brightness = node(m, unreal.MaterialExpressionScalarParameter, -700, 350, parameter_name='Brightness', default_value=2.0)
    opacity = node(m, unreal.MaterialExpressionScalarParameter, -700, 450, parameter_name='Opacity', default_value=0.9)
    uv = node(m, unreal.MaterialExpressionTextureCoordinate, -700, 550)
    # Soft long edges: 4 * v * (1 - v), with v across the blade (base 0, tip 0.9 after the scale).
    mask = node(m, unreal.MaterialExpressionComponentMask, -650, 550, r=False, g=True, b=False, a=False); link(uv, '', mask, '')
    v = node(m, unreal.MaterialExpressionMultiply, -550, 550, const_b=0.9); link(mask, '', v, 'A')  # tip edge keeps 60 %
    one_minus = node(m, unreal.MaterialExpressionOneMinus, -430, 600); link(v, '', one_minus, '')
    bump = node(m, unreal.MaterialExpressionMultiply, -320, 560); link(v, '', bump, 'A'); link(one_minus, '', bump, 'B')
    soft = node(m, unreal.MaterialExpressionMultiply, -200, 560, const_b=4.0); link(bump, '', soft, 'A')
    edge = node(m, unreal.MaterialExpressionSquareRoot, -100, 560); link(soft, '', edge, '')
    rgb = node(m, unreal.MaterialExpressionMultiply, -400, 100); link(vertex, '', rgb, 'A'); link(tint, '', rgb, 'B')
    emissive = node(m, unreal.MaterialExpressionMultiply, -200, 150); link(rgb, '', emissive, 'A'); link(brightness, '', emissive, 'B')
    alpha = node(m, unreal.MaterialExpressionMultiply, -300, 400); link(vertex, 'A', alpha, 'A'); link(opacity, '', alpha, 'B')
    out_alpha = node(m, unreal.MaterialExpressionMultiply, 0, 450); link(alpha, '', out_alpha, 'A'); link(edge, '', out_alpha, 'B')
    finish(m, emissive, out_alpha)


def run():
    unreal.EditorAssetLibrary.make_directory(FOLDER)
    hit_flash()
    weapon_trail()
    unreal.log('VEYR_FEEL_MATERIALS authored M_VeyrHitFlash and M_VeyrWeaponTrail')


run()
