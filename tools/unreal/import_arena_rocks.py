"""Import the task's original deterministic basalt mesh through native Interchange."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = '/Game/Veyr/Environment/SM_BasaltCliff'


def run(source_file):
    import unreal
    if Path(unreal.Paths.project_dir()).resolve() != (ROOT/'Unreal/Veyr').resolve():
        raise RuntimeError('Wrong owned project')
    if unreal.EditorLevelLibrary.get_pie_worlds(False):
        raise RuntimeError('Stop PIE before importing environment assets')
    source = Path(source_file).resolve()
    if not source.is_relative_to(ROOT/'Local/EnvironmentAssets'):
        raise ValueError('Expected a task-owned original environment source')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assets = unreal.EditorAssetLibrary
    existing = assets.load_asset(TARGET) if assets.does_asset_exist(TARGET) else None
    if existing:
        if assets.get_metadata_tag(existing, 'VeyrOriginalSourceSHA256') != source_hash:
            raise RuntimeError('Existing canonical mesh differs; preserve it and use a new version')
        # The reproducible generator/hash supplies provenance. Do not publish
        # editor reimport metadata containing the author's machine path.
        existing.set_editor_property('asset_import_data', None)
        if not assets.save_loaded_asset(existing, False):
            raise RuntimeError('Saving sanitized original mesh failed')
        return {'success': True, 'reused': True, 'sourceSHA256': source_hash, 'mesh': existing.get_path_name()}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    receipt = {'success': False, 'sourceSHA256': source_hash, 'originalProceduralGeometry': True}
    destination = ROOT/'Local/EnvironmentAssets'/('native-import-'+stamp+'.json')
    try:
        pipeline = unreal.InterchangeGenericAssetsPipeline()
        mesh = pipeline.get_editor_property('mesh_pipeline')
        mesh.set_editor_property('import_static_meshes', True)
        mesh.set_editor_property('import_skeletal_meshes', False)
        mesh.set_editor_property('collision', False)
        pipeline.get_editor_property('common_meshes_properties').set_editor_property('recompute_normals', False)
        pipeline.get_editor_property('animation_pipeline').set_editor_property('import_animations', False)
        materials = pipeline.get_editor_property('material_pipeline')
        materials.set_editor_property('import_materials', False)
        materials.get_editor_property('texture_pipeline').set_editor_property('import_textures', False)
        params = unreal.ImportAssetParameters()
        for name, value in [('is_automated', True), ('force_show_dialog', False), ('replace_existing', False), ('follow_redirectors', False)]:
            params.set_editor_property(name, value)
        params.set_editor_property('override_pipelines', [unreal.SoftObjectPath(pipeline.get_path_name())])
        manager = unreal.InterchangeManager.get_interchange_manager_scripted()
        result = manager.import_asset('/Game/Veyr/Environment/Import_'+stamp,
            unreal.InterchangeManager.create_source_data(str(source)), params)
        objects = list(result or [])
        receipt['objects'] = [obj.get_path_name() for obj in objects]
        meshes = [obj for obj in objects if isinstance(obj, unreal.StaticMesh)]
        if len(meshes) != 1:
            raise RuntimeError('Expected one native static mesh; partial assets preserved')
        rock = meshes[0]
        rock.set_editor_property('asset_import_data', None)
        bounds = rock.get_bounds()
        size = [2*getattr(bounds.box_extent, axis) for axis in ('x','y','z')]
        origin = [getattr(bounds.origin, axis) for axis in ('x','y','z')]
        receipt.update(sizeCm=size, originCm=origin)
        if max(abs(v-100.) for v in size) > .01 or max(abs(v) for v in origin) > .01:
            raise RuntimeError('Unexpected imported units or centered pivot')
        assets.set_metadata_tag(rock, 'VeyrOriginalSourceSHA256', source_hash)
        if not assets.save_loaded_asset(rock, False) or not assets.rename_asset(rock.get_path_name(), TARGET):
            raise RuntimeError('Canonical save/rename failed; partial assets preserved')
        rock = assets.load_asset(TARGET)
        if not assets.save_loaded_asset(rock, False):
            raise RuntimeError('Final mesh save failed')
        receipt.update(success=True, mesh=rock.get_path_name(), reused=False)
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        destination.write_text(json.dumps(receipt, indent=2)+'\n')
        unreal.log('VEYR_BASALT_IMPORT_RECEIPT '+str(destination))
    return receipt
