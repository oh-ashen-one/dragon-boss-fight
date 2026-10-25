"""Task-scoped native asset import and inspection, registered by project startup."""
from pathlib import Path
import importlib
import json
import hashlib
import unreal
import toolset_registry

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'Unreal/Veyr'
CHARACTERS = ('KnightB', 'DragonV3B')


def require_project():
    if Path(unreal.Paths.project_dir()).resolve() != PROJECT.resolve():
        raise RuntimeError('Veyr integration tool is bound to a different checkout')


def plan_for(character):
    if character not in CHARACTERS:
        raise ValueError('character must be KnightB or DragonV3B')
    return ROOT / 'Local/CustomuseAssets/Integration20261025b' / ('import-plan-' + character + '.json')


def polish_plan_for(character):
    if character not in CHARACTERS:raise ValueError('Unknown character')
    folder=ROOT/'Local/CustomuseAssets/Polish20261025'
    active=json.loads((folder/'active-plans.json').read_text())[character]
    path=Path(active['path']).resolve()
    if not path.is_relative_to(folder.resolve()):raise ValueError('Plan outside owned polish folder')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=active['sha256']:raise ValueError('Active plan hash differs from reviewed plan')
    return path


@unreal.uclass()
class VeyrIntegrationTools(unreal.ToolsetDefinition):
    """Imports hash-locked, owner-approved Veyr animation sets into fresh version folders.
    Inspects the exact native project and active character definitions for verification.
    """

    @toolset_registry.tool_call
    @staticmethod
    def inspect_project() -> dict[str, str]:
        """Returns the bound checkout, current level and active definition asset paths."""
        require_project()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        result = {'project_directory': str(PROJECT), 'engine': unreal.SystemLibrary.get_engine_version(),
                  'world': world.get_path_name() if world else ''}
        for label in ('Knight', 'Dragon'):
            path = '/Game/Characters/Customuse/Runtime/DA_' + label
            definition = unreal.load_asset(path)
            if definition:
                result[label] = definition.get_path_name()
                result[label + '_mesh'] = definition.skeletal_mesh.get_path_name()
                result[label + '_clips'] = ','.join(str(key) for key in definition.clips)
        return result

    @toolset_registry.tool_call
    @staticmethod
    def import_approved_character(character: str) -> unreal.Object:
        """Imports a prepared, hash-verified plan and saves its native character definition.

        Args:
            character: KnightB or DragonV3B. Plan is fixed under the owned private integration folder.
        Returns:
            The saved VeyrVisualDefinition; existing destination folders are never replaced.
        """
        require_project()
        plan = plan_for(character)
        if not plan.is_file():
            raise FileNotFoundError('Prepare the normalized approved import plan first')
        if unreal.EditorLevelLibrary.get_game_world() is not None:
            raise RuntimeError('Stop PIE before importing approved assets')
        import import_customuse
        importlib.reload(import_customuse)
        receipt = import_customuse.run(str(plan))
        result = unreal.load_asset(receipt['definition'])
        if not result:
            raise RuntimeError('Imported definition could not be reloaded')
        return result

    @toolset_registry.tool_call
    @staticmethod
    def create_blink_material() -> unreal.Material:
        """Creates or returns the owned cyan afterimage material; rejects unrelated path collisions."""
        require_project()
        import create_blink_material
        importlib.reload(create_blink_material)
        return create_blink_material.run()

    @toolset_registry.tool_call
    @staticmethod
    def import_polish_character(character: str) -> unreal.Object:
        """Imports the hash-locked current revision into its fresh native version.

        Args:
            character: KnightB or DragonV3B, selected by the private active-plan manifest.
        Returns:
            Saved definition. Existing version folders are never replaced.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before import')
        import import_customuse
        importlib.reload(import_customuse)
        receipt=import_customuse.run(str(polish_plan_for(character)))
        return unreal.load_asset(receipt['definition'])

    @toolset_registry.tool_call
    @staticmethod
    def finalize_polish_character(character: str) -> unreal.Object:
        """Finalizes saved revision rates/materials without reimporting motion.

        Args:
            character: KnightB or DragonV3B from the active-plan manifest.
        Returns:
            The finalized source definition; the old RuntimeApproved slot is preserved.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before finalization')
        import import_customuse
        importlib.reload(import_customuse)
        plan=json.loads(polish_plan_for(character).read_text());plan['runtime_folder']='RuntimePolish'
        receipt=import_customuse.finalize_existing(plan)
        return unreal.load_asset(receipt['definition'])

    @toolset_registry.tool_call
    @staticmethod
    def verify_polish_character_poses(character: str) -> str:
        """Samples the saved current revision without reimporting or changing motion.

        Args:
            character: KnightB or DragonV3B from the hash-locked active manifest.
        Returns:
            JSON report with sampled native poses and transition endpoint checks.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before pose verification')
        import probe_approved_poses
        importlib.reload(probe_approved_poses)
        plan=json.loads(polish_plan_for(character).read_text())
        return json.dumps(probe_approved_poses.run(plan))

    @toolset_registry.tool_call
    @staticmethod
    def activate_polish_character(character: str) -> unreal.Object:
        """Activates the complete current revision in the separate RuntimePolish slot.

        Args:
            character: KnightB or DragonV3B from the active-plan manifest.
        Returns:
            Saved runtime definition. A conflicting existing slot is preserved and rejected.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before activation')
        plan=json.loads(polish_plan_for(character).read_text())
        source_path=f"/Game/Characters/Customuse/{character}/{plan['version']}/DA_{character}"
        source=unreal.load_asset(source_path)
        if not source:raise RuntimeError('Import and finalize the revision first')
        errors=list(source.validate_definition(True))
        if errors:raise RuntimeError('; '.join(errors))
        label='Knight' if character=='KnightB' else 'Dragon';destination='/Game/Characters/Customuse/RuntimePolish/DA_'+label
        existing=unreal.load_asset(destination)
        if existing:
            if unreal.EditorAssetLibrary.get_metadata_tag(existing,'VeyrPolishSourceDefinition')!=source_path:
                raise RuntimeError('Different existing runtime revision; preserved')
            return existing
        result=unreal.EditorAssetLibrary.duplicate_asset(source_path,destination)
        if not result:raise RuntimeError('Definition copy failed')
        unreal.EditorAssetLibrary.set_metadata_tag(result,'VeyrPolishSourceDefinition',source_path)
        if not unreal.EditorAssetLibrary.save_loaded_asset(result,False):raise RuntimeError('Runtime definition save failed')
        return result

    @toolset_registry.tool_call
    @staticmethod
    def import_polish_environment(asset_name: str) -> str:
        """Imports one hash-verified modular Tripo asset and builds its three LODs.

        Args:
            asset_name: Exact name from the fixed private environment import plan.
        Returns:
            JSON with saved mesh path, native LOD counts and import status.
        """
        require_project()
        folder=ROOT/'Local/ArtPass20261025/Tripo'
        plan=json.loads((folder/'import-plan.json').read_text())
        matches=[row for row in plan['assets'] if row['name']==asset_name]
        if len(matches)!=1:raise ValueError('Unknown or duplicate environment asset')
        requests=folder/'requests';requests.mkdir(exist_ok=True)
        path=requests/(asset_name+'-'+matches[0]['version']+'.json');content=json.dumps({'schema':1,'assets':matches},indent=2)
        if path.exists() and path.read_text()!=content:raise RuntimeError('Preserving a different existing import request')
        path.write_text(content)
        import import_tripo_static
        importlib.reload(import_tripo_static)
        result=import_tripo_static.run(path)
        return json.dumps({'success':result['success'],'assets':[{'mesh':row.get('mesh'),'lods':row.get('lods'),'status':row['status']} for row in result['assets']]})

    @toolset_registry.tool_call
    @staticmethod
    def create_polish_fire_materials() -> str:
        """Imports the generated atlas/density textures and saves owned FXv3 materials.

        Returns:
            JSON material paths and source hashes; rendered quality is a separate check.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before material authoring')
        import create_fire_materials_v3
        importlib.reload(create_fire_materials_v3)
        return json.dumps(create_fire_materials_v3.run())

    @toolset_registry.tool_call
    @staticmethod
    def configure_legacy_environment_collision() -> str:
        """Enables geometry collision on the retained project-owned brazier and arch meshes.

        Returns:
            JSON with saved collision LODs and paths. No engine content or material is changed.
        """
        require_project()
        if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before collision configuration')
        subsystem=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        rows=[]
        for name in ('CathedralBrazier','CathedralArch'):
            path=f'/Game/ArtPass/Tripo/{name}_v001/SM_{name}_v001'
            mesh=unreal.load_asset(path)
            if not isinstance(mesh,unreal.StaticMesh):raise RuntimeError('Retained mesh missing: '+path)
            lod=min(2,int(subsystem.get_lod_count(mesh))-1)
            body=mesh.get_editor_property('body_setup')
            if body is None:raise RuntimeError('Retained mesh lacks native BodySetup: '+path)
            mesh.set_editor_property('lod_for_collision',lod)
            body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            for section in range(int(mesh.get_num_sections(lod))):subsystem.enable_section_collision(mesh,True,lod,section)
            if subsystem.get_collision_complexity(mesh)!=unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
                raise RuntimeError('Collision setting did not persist: '+path)
            if not unreal.EditorAssetLibrary.save_loaded_asset(mesh,False):raise RuntimeError('Collision save failed: '+path)
            rows.append({'mesh':path,'collisionLOD':lod,'collision':'complex geometry as simple','runtimeVerified':False})
        return json.dumps(rows)

    @toolset_registry.tool_call
    @staticmethod
    def activate_approved_character(character: str) -> unreal.Object:
        """Copies a fully validated import to the new RuntimeApproved slot, preserving the legacy slot.

        Args:
            character: KnightB or DragonV3B, using the corresponding prepared import plan.
        Returns:
            The saved runtime definition used by the integrated native actor.
        """
        require_project()
        plan=json.loads(plan_for(character).read_text())
        source_path='/Game/Characters/Customuse/'+character+'/'+plan['version']+'/DA_'+character
        source=unreal.load_asset(source_path)
        if not isinstance(source,unreal.VeyrVisualDefinition):
            raise RuntimeError('Complete the approved import before activation')
        errors=list(source.validate_definition(True))
        if errors:raise RuntimeError('Definition is incomplete: '+'; '.join(errors))
        label='Knight' if character=='KnightB' else 'Dragon'
        destination='/Game/Characters/Customuse/RuntimeApproved/DA_'+label
        existing=unreal.load_asset(destination)
        if existing:
            if existing.get_editor_property('source_sha256') != source.get_editor_property('source_sha256'):
                raise RuntimeError('Preserving a different existing approved definition')
            return existing
        result=unreal.EditorAssetLibrary.duplicate_asset(source_path,destination)
        if not result or not unreal.EditorAssetLibrary.save_loaded_asset(result,False):
            raise RuntimeError('Saving the new runtime definition failed')
        return result

    @toolset_registry.tool_call
    @staticmethod
    def start_input_validation(mode: str) -> str:
        """Starts the game's input-only validation in a fresh owned PIE world.

        Args:
            mode: core, controls, integration, collision, stance, guard, healing, avoidance, death, victory, or leg0..leg3.
        Returns:
            Absolute private evidence directory. The game writes completion and captures there.
        """
        require_project()
        allowed={'core','controls','integration','collision','stance','guard','healing','avoidance','death','victory','leg0','leg1','leg2','leg3'}
        if mode not in allowed:raise ValueError('Unknown Veyr validation mode')
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if not world:raise RuntimeError('Start a fresh PIE world first')
        game=unreal.GameplayStatics.get_game_mode(world)
        if not isinstance(game,unreal.VeyrGameMode):raise RuntimeError('The live world is not Veyr')
        import datetime
        output=ROOT/'Evidence'/('pie-'+mode+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        output.mkdir(parents=True,exist_ok=False)
        if not game.start_native_validation(mode,str(output)):
            raise RuntimeError('Validation requires a fresh untouched world and no active replay')
        return str(output)
