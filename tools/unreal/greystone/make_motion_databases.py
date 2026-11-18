"""Step E5a: motion-matching databases on Greystone's skeleton, built from GASP's Dense databases.

Needs copy_pack.py --gasp and the rigs step (RTG_UEFN_to_Greystone). Writes under /Game/Characters/Greystone/MotionMatching:
  Anims/GS_<GASP clip>           every UEFN clip the chosen databases use, retargeted with RTG_UEFN_to_Greystone
  PSS_GS_Default                 duplicate of GASP PSS_Default, skeleton swapped to Greystone_Skeleton, no mirror table
  PSD_GS_<Gate>_<GASP suffix>    duplicates of the GASP databases below, clips swapped (UVeyrGreystoneEditorLibrary),
                                 mirrored entries dropped to "original only" (no Greystone mirror table yet)
  PSN_GS_All                     normalization set over our databases
The gate word in each name is how FVeyrMotionMatcher files a database (Idle/Start/Loop/Stop/Pivot/Turn).
Crouch, jump, land, traversal and spin databases are left out: the knight has none of those states.

API relied on: UPoseSearchSchema::Skeletons (FPoseSearchRoledSkeleton {Skeleton, MirrorDataTable, Role}, EditAnywhere),
UPoseSearchDatabase::Schema / NormalizationSet (EditAnywhere), UPoseSearchNormalizationSet::Databases (EditAnywhere);
the database's animation list is private, hence the C++ helpers. Not run yet.
"""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
opts = job['options']
library = unreal.EditorAssetLibrary
helper = unreal.VeyrGreystoneEditorLibrary
DENSE = g.GASP_MANNEQUIN + '/Animations/MotionMatchingData/Databases/Dense/'
GATES = {
    'Idle': ['PSD_Dense_Stand_Idles'],
    'Start': ['PSD_Dense_Stand_Walk_Starts', 'PSD_Dense_Stand_Run_Starts', 'PSD_Dense_Stand_Sprint_Starts'],
    'Loop': ['PSD_Dense_Stand_Walk_Loops', 'PSD_Dense_Stand_Run_Loops', 'PSD_Dense_Stand_Sprint_Loops'],
    'Stop': ['PSD_Dense_Stand_Walk_Stops', 'PSD_Dense_Stand_Run_Stops', 'PSD_Dense_Stand_Sprint_Stops'],
    'Pivot': ['PSD_Dense_Stand_Walk_Pivots', 'PSD_Dense_Stand_Run_Pivots', 'PSD_Dense_Stand_Sprint_Pivots'],
    'Turn': ['PSD_Dense_Stand_TurnInPlace'],
}
rtg = unreal.load_asset(g.RIGS + '/RTG_UEFN_to_Greystone')
uefn_mesh = unreal.load_asset(g.GASP_MANNEQUIN + '/Meshes/SK_UEFN_Mannequin')
grey_mesh = unreal.load_asset(g.GREYSTONE_MESH)
assert rtg and uefn_mesh and grey_mesh, 'needs copy_pack.py --gasp and the rigs step'
skeleton = grey_mesh.get_editor_property('skeleton')

sources, used = {}, set()
for gate, names in GATES.items():
    for name in names:
        db = unreal.load_asset(DENSE + name)
        if not db:
            raise RuntimeError('missing GASP database ' + name)
        assets = [a for a in helper.list_pose_search_database_assets(db) if a]
        sources[name] = assets
        used.update(a.split('.')[0] for a in assets)

anim_folder = g.MOTION + '/Anims'
mapping, skipped = {}, []
batch = [library.find_asset_data(p) for p in sorted(used)]
inputs = unreal.IKRetargetBatchOperationInputs()
inputs.set_editor_property('assets_to_retarget', batch)
inputs.set_editor_property('source_mesh', uefn_mesh)
inputs.set_editor_property('target_mesh', grey_mesh)
inputs.set_editor_property('ik_retarget_asset', rtg)
inputs.set_editor_property('prefix', 'GS_')
inputs.set_editor_property('target_path', anim_folder)
inputs.set_editor_property('include_referenced_assets', False)
inputs.set_editor_property('overwrite_existing_files', bool(opts.get('replace')))
made = {str(a.asset_name): str(a.package_name) for a in unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)}
for path in sorted(used):
    name = 'GS_' + path.rsplit('/', 1)[1]
    if name in made:
        mapping[unreal.load_asset(path)] = unreal.load_asset(made[name])
    else:
        skipped.append(path)

schema_path = g.MOTION + '/PSS_GS_Default'
if library.does_asset_exist(schema_path):
    library.delete_asset(schema_path)
schema = library.duplicate_asset(g.GASP_MANNEQUIN + '/Animations/MotionMatchingData/Schemas/PSS_Default', schema_path)
roled = unreal.PoseSearchRoledSkeleton()
roled.set_editor_property('skeleton', skeleton)
schema.set_editor_property('skeletons', [roled])
library.save_loaded_asset(schema)

made_dbs, receipt = [], {'databases': {}, 'skippedClips': skipped, 'retargetedClips': len(mapping)}
for gate, names in GATES.items():
    for name in names:
        new_path = g.MOTION + '/PSD_GS_' + gate + '_' + name[len('PSD_Dense_'):]
        if library.does_asset_exist(new_path):
            library.delete_asset(new_path)
        db = library.duplicate_asset(DENSE + name, new_path)
        replaced = helper.retarget_pose_search_database(db, mapping, schema)
        removed = helper.filter_pose_search_database(db, list(mapping.values()))
        made_dbs.append(db)
        receipt['databases'][new_path] = {'gate': gate, 'source': DENSE + name, 'entries': len(sources[name]),
                                          'replaced': replaced, 'removedUnmapped': removed}

norm_path = g.MOTION + '/PSN_GS_All'
if library.does_asset_exist(norm_path):
    library.delete_asset(norm_path)
norm = unreal.AssetToolsHelpers.get_asset_tools().create_asset('PSN_GS_All', g.MOTION, unreal.PoseSearchNormalizationSet,
                                                                unreal.PoseSearchNormalizationSetFactory())
norm.set_editor_property('databases', made_dbs)
library.save_loaded_asset(norm)
for db in made_dbs:
    db.set_editor_property('normalization_set', norm)
    library.save_loaded_asset(db)

(out / 'motion-databases.json').write_text(json.dumps(receipt, indent=1) + '\n')
ok = all(v['replaced'] > 0 for v in receipt['databases'].values())
g.write_result(out, {'success': ok, 'databases': len(made_dbs), 'clips': len(mapping), 'skipped': len(skipped)})
