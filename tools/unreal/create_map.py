"""Run with Unreal's PythonScript commandlet in a fresh, null-RHI process.

Creates only the project-owned blank encounter map. Runtime C++ populates it.
Never duplicates /Engine/Maps/Entry: its transient model references are unsafe.
"""
import unreal

MAP = "/Game/Maps/VeyrArena"
if unreal.EditorAssetLibrary.does_asset_exist(MAP):
    unreal.log("VEYR_MAP_EXISTS " + MAP)
else:
    editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not editor.new_level(MAP):
        raise RuntimeError("Could not create project-owned Veyr map")
    if not editor.save_current_level():
        raise RuntimeError("Could not save project-owned Veyr map")
    unreal.log("VEYR_MAP_CREATED " + MAP)
