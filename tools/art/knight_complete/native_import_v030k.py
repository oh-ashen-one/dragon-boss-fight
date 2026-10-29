"""Headless UE 5.8 Python commandlet driver for the knight completion bank (v030k).

Run (no renderer, no listener):
  UnrealEditor-Cmd Veyr.uproject -run=pythonscript -script=<this file> -nullrhi -unattended
    -NoZenAutoLaunch -notraceserver -DDC=(EnginePak=InstalledEnginePak,Local)
Steps: import the hash-locked active KnightB plan into KnightB/v030k (never replaces), verify that
every inherited v029 clip and the original guard are unchanged, then promote it into
RuntimePolish/DA_Knight exactly like VeyrIntegrationTools.activate_polish_character.
Writes Local/CustomuseImports/knight-v030k-activation.json."""
import hashlib
import json
import sys
import traceback
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/unreal"))
import import_customuse  # noqa: E402

OUT = ROOT / "Local/CustomuseImports/knight-v030k-activation.json"
record = {"success": False, "steps": []}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n")


def plan_path():
    folder = ROOT / "Local/CustomuseAssets/Polish20261025"
    active = json.loads((folder / "active-plans.json").read_text())["KnightB"]
    path = Path(active["path"]).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != active["sha256"]:
        raise RuntimeError("Active KnightB plan hash differs from reviewed plan")
    return path


def main():
    path = plan_path()
    plan = json.loads(path.read_text())
    record["plan"] = str(path)
    record["version"] = plan["version"]
    source_path = f"/Game/Characters/Customuse/KnightB/{plan['version']}/DA_KnightB"
    runtime_path = "/Game/Characters/Customuse/RuntimePolish/DA_Knight"
    before = unreal.load_asset(runtime_path)
    record["runtimeSourceBefore"] = unreal.EditorAssetLibrary.get_metadata_tag(before, "VeyrPolishSourceDefinition")
    record["runtimeClipsBefore"] = sorted(str(k) for k in before.clips.keys())
    if not unreal.EditorAssetLibrary.does_asset_exist(source_path):
        receipt = import_customuse.run(str(path))
        record["steps"].append({"import": receipt.get("definition"), "success": receipt.get("success")})
        save()
    source = unreal.load_asset(source_path)
    if not source:
        raise RuntimeError("Imported definition missing")
    record["sourcedVerification"] = import_customuse.verify_sourced_definition(plan, source)
    errors = list(source.validate_definition(True))
    if errors:
        raise RuntimeError("; ".join(errors))
    existing = unreal.load_asset(runtime_path)
    previous = unreal.EditorAssetLibrary.get_metadata_tag(existing, "VeyrPolishSourceDefinition")
    if previous != source_path:
        if previous != plan["replace_runtime_source"]:
            raise RuntimeError("Different existing runtime revision; preserved: " + str(previous))
        for field in ("skeletal_mesh", "mesh_relative_transform", "clips", "props", "bone_targets", "required_clips",
                      "required_bone_targets", "source_sha256", "native_presentation_verified"):
            existing.set_editor_property(field, source.get_editor_property(field))
        unreal.EditorAssetLibrary.set_metadata_tag(existing, "VeyrPreviousSourceDefinition", previous)
        unreal.EditorAssetLibrary.set_metadata_tag(existing, "VeyrPolishSourceDefinition", source_path)
        if not unreal.EditorAssetLibrary.save_loaded_asset(existing, False):
            raise RuntimeError("Runtime promotion save failed")
        record["steps"].append({"promoted": runtime_path, "from": previous, "to": source_path})
    runtime = unreal.load_asset(runtime_path)
    record["runtimeVerification"] = import_customuse.verify_sourced_definition(plan, runtime)
    clips = {str(k): v for k, v in runtime.clips.items()}
    record["runtimeClipsAfter"] = sorted(clips)
    record["newClips"] = {}
    for spec in plan["clips"]:
        c = clips[spec["name"]]
        record["newClips"][spec["name"]] = {
            "sequence": c.sequence.get_path_name(), "playLength": float(c.sequence.get_play_length()),
            "gameplayPlayRate": float(c.gameplay_play_rate), "nominalSpeed": float(c.nominal_speed_cm_per_second),
            "loop": bool(c.loop), "weapon": c.weapon_mesh.get_path_name() if c.weapon_mesh else None,
            "meshOverride": c.mesh_override.get_path_name() if c.mesh_override else None,
            "approvedSourceFile": c.approved_source_file}
    record["guard"] = import_customuse.guard_signature(runtime)
    record["success"] = True


try:
    main()
except Exception as error:  # record and re-raise so the commandlet exits non-zero
    record["error"] = str(error)
    record["traceback"] = traceback.format_exc()
    save()
    unreal.log_error("VEYR_KNIGHT_V030K_FAILED " + str(error))
    raise
save()
unreal.log("VEYR_KNIGHT_V030K_ACTIVATED " + str(OUT))
