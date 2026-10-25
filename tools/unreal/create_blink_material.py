"""Create the owned native blink afterimage material without replacing existing art."""
import unreal

PATH='/Game/ArtPass/Materials/M_BlinkAfterimage'
OWNER='Veyr.approved-blink-integration.20261025'

def run():
    existing=unreal.load_asset(PATH)
    if existing:
        if not isinstance(existing,unreal.Material) or unreal.EditorAssetLibrary.get_metadata_tag(existing,'VeyrOwner') != OWNER:
            raise RuntimeError('Preserving material at occupied blink path')
        return existing
    material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_BlinkAfterimage','/Game/ArtPass/Materials',unreal.Material,unreal.MaterialFactoryNew())
    if not material:raise RuntimeError('Blink material creation failed')
    material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided',True)
    material.set_editor_property('used_with_skeletal_mesh',True)
    library=unreal.MaterialEditingLibrary
    tint=library.create_material_expression(material,unreal.MaterialExpressionVectorParameter,-300,0)
    tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',unreal.LinearColor(.13,.62,1.,1.))
    opacity=library.create_material_expression(material,unreal.MaterialExpressionScalarParameter,-300,150)
    opacity.set_editor_property('parameter_name','Opacity');opacity.set_editor_property('default_value',.30)
    if not library.connect_material_property(tint,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR):raise RuntimeError('Blink tint connection failed')
    if not library.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY):raise RuntimeError('Blink opacity connection failed')
    unreal.EditorAssetLibrary.set_metadata_tag(material,'VeyrOwner',OWNER)
    library.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material,False):raise RuntimeError('Blink material save failed')
    return material
