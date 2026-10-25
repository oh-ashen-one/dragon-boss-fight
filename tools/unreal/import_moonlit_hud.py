"""Import the approved B-derived HUD atlas in the owned native editor."""
from pathlib import Path
import hashlib,json
import unreal
ROOT=Path(__file__).resolve().parents[2]

def run():
    if Path(unreal.Paths.project_dir()).resolve()!=(ROOT/'Unreal/Veyr').resolve():
        raise RuntimeError('Wrong Veyr project')
    if unreal.EditorLevelLibrary.get_game_world() is not None:
        raise RuntimeError('Stop PIE before HUD import')
    src=ROOT/'Local/HUDMoonlitB/MoonlitSilverAtlas.png'
    digest=hashlib.sha256(src.read_bytes()).hexdigest()
    name='T_MoonlitSilverAtlas_v1';folder='/Game/UI/MoonlitB';path=folder+'/'+name
    lib=unreal.EditorAssetLibrary
    if lib.does_asset_exist(path):
        obj=lib.load_asset(path)
        if lib.get_metadata_tag(obj,'VeyrHUDSourceSHA256')!=digest:
            raise RuntimeError('Preserving a different existing HUD atlas')
    else:
        task=unreal.AssetImportTask();task.filename=str(src);task.destination_path=folder;task.destination_name=name
        task.automated=True;task.replace_existing=False;task.save=False
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        obj=lib.load_asset(path)
        if not isinstance(obj,unreal.Texture2D):raise RuntimeError('Atlas import failed')
        obj.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_EDITOR_ICON)
        obj.set_editor_property('lod_group',unreal.TextureGroup.TEXTUREGROUP_UI)
        obj.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        obj.set_editor_property('never_stream',True)
        obj.set_editor_property('srgb',True)
        obj.set_editor_property('address_x',unreal.TextureAddress.TA_CLAMP)
        obj.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
        lib.set_metadata_tag(obj,'VeyrHUDSourceSHA256',digest)
        if not lib.save_loaded_asset(obj,False):raise RuntimeError('HUD atlas save failed')
    (ROOT/'Local/HUDMoonlitB/import-receipt.json').write_text(json.dumps({'asset':path,'sourceSHA256':digest,'saved':True,'runtimeVerified':False},indent=2)+'\n')
    return obj
