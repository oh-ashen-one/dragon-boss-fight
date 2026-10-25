"""Task-scoped native asset import and inspection, registered by project startup."""
from pathlib import Path
import importlib
import json
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
    return ROOT / 'Local/CustomuseAssets/Integration20261025' / ('import-plan-' + character + '.json')


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
