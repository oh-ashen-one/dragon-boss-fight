"""Read-only native verification for the owned approval/import tool workflow."""
import unittest
from pathlib import Path
from unittest.mock import patch
import unreal
import veyr_integration_toolset as integration

class VeyrImportContractTests(unittest.TestCase):
    def test_project_identity(self):
        integration.require_project()
        self.assertEqual(Path(unreal.Paths.project_dir()).resolve(),integration.PROJECT.resolve())
    def test_rejects_foreign_project(self):
        with patch.object(integration,'PROJECT',Path('/not-the-owned-project')):
            with self.assertRaises(RuntimeError):integration.require_project()
    def test_rejects_unknown_or_traversal_character(self):
        for name in ('','../KnightB','Other'):
            with self.assertRaises(ValueError):integration.plan_for(name)
    def test_plans_stay_under_owned_source(self):
        for name in integration.CHARACTERS:
            self.assertTrue(integration.plan_for(name).is_relative_to(integration.ROOT/'Local/CustomuseAssets'))
    def test_native_definitions_are_complete(self):
        for name in ('Knight','Dragon'):
            asset=unreal.load_asset('/Game/Characters/Customuse/RuntimeApproved/DA_'+name)
            self.assertIsNotNone(asset)
            self.assertEqual(list(asset.validate_definition(True)),[])
    def test_helper_bones_and_cup_survive_import(self):
        asset=unreal.load_asset('/Game/Characters/Customuse/RuntimeApproved/DA_Knight')
        self.assertIsNotNone(asset)
        names=[str(n) for n in asset.get_imported_bone_names()]
        self.assertIn('WeaponSocket',names);self.assertIn('CupSocket',names)
        self.assertIn('Cup',[str(n) for n in asset.props])
    def test_blink_material_owner_and_opacity(self):
        import create_blink_material
        asset=unreal.load_asset(create_blink_material.PATH)
        self.assertIsNotNone(asset)
        self.assertEqual(unreal.EditorAssetLibrary.get_metadata_tag(asset,'VeyrOwner'),create_blink_material.OWNER)
        self.assertEqual(asset.get_editor_property('blend_mode'),unreal.BlendMode.BLEND_TRANSLUCENT)
