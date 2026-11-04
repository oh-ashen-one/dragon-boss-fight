"""Read-only native inventory for the intro's first-use weapon/pose transitions.

Run with PythonScriptCommandlet -nullrhi. No asset is saved or modified.
"""
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
assert Path(unreal.Paths.project_dir()).resolve() == ROOT/'Unreal/Veyr'
assert '-nullrhi' in unreal.SystemLibrary.get_command_line().lower()
definition = unreal.load_asset('/Game/Characters/Customuse/RuntimePolish/DA_Knight')
assert definition
rows = []
for name, clip in definition.get_editor_property('clips').items():
    mesh = clip.weapon_mesh
    rows.append({'clip': str(name), 'weapon': mesh.get_path_name() if mesh else None,
                 'materials': [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                               for i in range(mesh.get_num_sections(0))] if mesh else [],
                 'sequence': clip.sequence.get_path_name()})
out = ROOT/'Local/Fortress20261103/intro-native-asset-inventory.json'
out.write_text(json.dumps({'clips': rows, 'readOnly': True}, indent=2)+'\n')
unreal.log('VEYR_INTRO_ASSET_INVENTORY_COMPLETE')
