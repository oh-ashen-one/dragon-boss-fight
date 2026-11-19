"""Import the dragon SkinFix GLBs as NEW skeletal meshes beside the old ones (PythonScriptCommandlet, -nullrhi).

Quality goal F, 2026-11-19. The manifest (Local/quality-goal/dragon-skin-20261118/manifest.json) lists three meshes whose
skin weights were refit (wing roots, left front paw). The old assets stay untouched so -VeyrLegacyDragonSkin can restore
them; the new ones go to /Game/Characters/Customuse/DragonV3B/SkinFix20261119/<old name>_SkinFix_v1 and are bound to the
old mesh's skeleton asset (no new skeleton, no animation import, morph targets imported, materials and physics copied
from the old mesh). The runtime remaps old -> new by these names.

Run:  python3 tools/unreal/engine_lock.py --label "<who> dragon skinfix import" -- \
        <UnrealEditor-Cmd> <uproject> -run=pythonscript -script=<this file> -nullrhi -unattended ...
with VEYR_SKINFIX_MANIFEST=<manifest> and VEYR_SKINFIX_REPORT=<new dir under Local/>.
"""
import hashlib
import json
import os
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
assert Path(unreal.Paths.project_dir()).resolve() == (ROOT/'Unreal/Veyr').resolve()
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower(), 'This route must never create a renderer'
manifest_path = Path(os.environ['VEYR_SKINFIX_MANIFEST']).resolve(strict=True)
out = Path(os.environ['VEYR_SKINFIX_REPORT']).resolve()
assert out.is_relative_to((ROOT/'Local').resolve())
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads(manifest_path.read_text())
base = manifest_path.parent
DEST = '/Game/Characters/Customuse/DragonV3B/SkinFix20261119'
report = {'manifest': str(manifest_path), 'manifestSHA256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
          'destination': DEST, 'meshes': [], 'success': False}


def save():
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def glb_for(entry):
    rel = entry['from_'].split(' ')[0]
    path = (base/rel).resolve(strict=True)
    known = {g['output']: g['outputSHA256'] for g in manifest['glbs']}
    digest = sha(path)
    assert known.get(str(path)) == digest, 'SkinFix GLB hash differs from the manifest: ' + str(path)
    return path, digest


def import_mesh(source, target_folder, skeleton):
    pipeline = unreal.InterchangeGenericAssetsPipeline()
    common = pipeline.get_editor_property('common_skeletal_meshes_and_animations_properties')
    common.set_editor_property('import_only_animations', False)
    common.set_editor_property('try_auto_select_skeleton', False)
    common.set_editor_property('use_t0_as_ref_pose', False)
    common.set_editor_property('skeleton', skeleton)
    mesh = pipeline.get_editor_property('mesh_pipeline')
    mesh.set_editor_property('import_skeletal_meshes', True)
    mesh.set_editor_property('import_static_meshes', False)
    mesh.set_editor_property('import_morph_targets', True)
    mesh.set_editor_property('merge_morph_targets_with_same_name', False)
    mesh.set_editor_property('update_skeleton_reference_pose', False)
    for name in ('create_physics_asset',):
        try:
            mesh.set_editor_property(name, False)
        except Exception:
            pass
    anim = pipeline.get_editor_property('animation_pipeline')
    anim.set_editor_property('import_animations', False)
    materials = pipeline.get_editor_property('material_pipeline')
    materials.set_editor_property('import_materials', False)
    materials.get_editor_property('texture_pipeline').set_editor_property('import_textures', False)
    params = unreal.ImportAssetParameters()
    params.set_editor_property('is_automated', True)
    params.set_editor_property('force_show_dialog', False)
    params.set_editor_property('replace_existing', False)
    params.set_editor_property('follow_redirectors', False)
    params.set_editor_property('override_pipelines', [unreal.SoftObjectPath(pipeline.get_path_name())])
    data = unreal.InterchangeManager.create_source_data(str(source))
    result = unreal.InterchangeManager.get_interchange_manager_scripted().import_asset(target_folder, data, params)
    objects = list(result) if result is not None else []
    meshes = [o for o in objects if isinstance(o, unreal.SkeletalMesh)]
    if len(meshes) != 1:
        raise RuntimeError('Expected one skeletal mesh from %s, got %s' % (source, [o.get_path_name() for o in objects]))
    return meshes[0], objects


try:
    sub = unreal.SkeletalMeshEditorSubsystem() if hasattr(unreal, 'SkeletalMeshEditorSubsystem') else None
    for entry in manifest['unrealAssetsToReimport']:
        old_path = entry['asset']
        name = old_path.rsplit('/', 1)[1]
        old = unreal.load_asset(old_path)
        if not isinstance(old, unreal.SkeletalMesh):
            raise RuntimeError('Old mesh missing: ' + old_path)
        glb, digest = glb_for(entry)
        skeleton = old.get_editor_property('skeleton')
        folder = DEST + '/' + name + '_SkinFix_v1'
        new, objects = import_mesh(glb, folder, skeleton)
        record = {'old': old_path, 'new': new.get_path_name(), 'glb': str(glb), 'glbSHA256': digest,
                  'importedObjects': [o.get_path_name() for o in objects]}
        if new.get_editor_property('skeleton') != skeleton:
            raise RuntimeError('SkinFix mesh did not bind to the old skeleton: ' + name)
        old_mats = list(old.get_editor_property('materials'))
        new_mats = list(new.get_editor_property('materials'))
        record['oldMaterialSlots'] = [str(m.get_editor_property('material_slot_name')) for m in old_mats]
        record['newMaterialSlotsImported'] = [str(m.get_editor_property('material_slot_name')) for m in new_mats]
        if len(old_mats) != len(new_mats):
            raise RuntimeError('Material slot count differs for ' + name)
        new.set_editor_property('materials', old_mats)
        for prop in ('physics_asset', 'shadow_physics_asset', 'positive_bounds_extension', 'negative_bounds_extension'):
            try:
                new.set_editor_property(prop, old.get_editor_property(prop))
                record.setdefault('copied', []).append(prop)
            except Exception as error:
                record.setdefault('notCopied', []).append(prop + ': ' + str(error))
        try:
            record['oldMorphTargets'] = sorted(str(m.get_name()) for m in old.get_editor_property('morph_targets'))
            record['newMorphTargets'] = sorted(str(m.get_name()) for m in new.get_editor_property('morph_targets'))
        except Exception as error:
            record['morphTargets'] = 'unreadable: ' + str(error)
        if sub:
            record['oldVerts'] = sub.get_num_verts(old, 0)
            record['newVerts'] = sub.get_num_verts(new, 0)
            record['oldLODs'] = sub.get_lod_count(old)
            record['newLODs'] = sub.get_lod_count(new)
            if record['oldVerts'] != record['newVerts']:
                raise RuntimeError('Vertex count differs for %s: %s vs %s' % (name, record['oldVerts'], record['newVerts']))
        if not unreal.EditorAssetLibrary.save_loaded_asset(new, False):
            raise RuntimeError('Save failed: ' + new.get_path_name())
        # The runtime looks the mesh up by a fixed name: <folder>/<old name>_SkinFix_v1.
        wanted = folder + '/' + name + '_SkinFix_v1'
        if new.get_path_name().split('.')[0] != wanted:
            if not unreal.EditorAssetLibrary.rename_asset(new.get_path_name().split('.')[0], wanted):
                raise RuntimeError('Rename failed: %s -> %s' % (new.get_path_name(), wanted))
            new = unreal.load_asset(wanted)
            unreal.EditorAssetLibrary.save_loaded_asset(new, False)
        record['new'] = new.get_path_name()
        report['meshes'].append(record)
        save()
    report['success'] = True
except Exception as error:
    report['error'] = repr(error)
save()
print('VEYR_SKINFIX_IMPORT success=%s' % report['success'])
