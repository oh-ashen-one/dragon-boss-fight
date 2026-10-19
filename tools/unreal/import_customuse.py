"""Owner-run UE 5.8 Python import; this script never launches an editor.

Call run('/absolute/private/plan.json') through the owned native editor Python
tool, or set VEYR_CUSTOMUSE_IMPORT_PLAN when running this file as a script.
Build VeyrVisualDefinition first. Interchange must already be available.

Plan schema (all sources remain under Local/CustomuseAssets):
  character: KnightB or DragonV3B; version: a fresh identifier, e.g. v001
  rig: {file: absolute GLB, sha256: exact digest}
  bones: {head: bone name or {bone: name, translation_cm:[x,y,z]}, ...}
  required_bones: [head, ...]
  required_clips: [Idle, Walk, ...]
  target_height_cm: optional positive height; otherwise mesh_scale defaults 1
  mesh_translation_cm: [0,0,0]; mesh_rotation_deg: [pitch,yaw,roll]
  root_motion_bone: e.g. Hips; clips: [{name, file, sha256, loop,
      start_seconds:0, end_seconds:-1, impact_seconds:-1,
      root_motion_policy: preserve|lock_root}]

Knight's animated walk export is its canonical mesh/skeleton. The earlier raw
rig has different names/units and is provenance only. A rig file may contain
animation; its clips are ignored during mesh import. Clip skin names, hierarchy,
geometry scale and inverse binds must match that canonical file before import.
lock_root requires the expected bone to be the actual imported root; it locks
all root translation (including vertical bob) to the first animation frame.
This is a reviewed option, not a claim that the resulting gait is accepted.

Only native Interchange performs imports. AssetTools creates a new definition
data asset without importing or invoking an import-settings dialog. Automated
imports prohibit replacement/dialogs and use an explicit transient pipeline.
Partial imports are preserved on failure; use a new version for the next attempt.
Receipts are private Local/CustomuseImports records, never public asset sources.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "Unreal/Veyr"
SOURCE_ROOT = ROOT / "Local/CustomuseAssets"


def inspect_glb(entry):
    path = Path(entry["file"]).resolve()
    if path.suffix.lower() != ".glb" or not path.is_relative_to(SOURCE_ROOT.resolve()):
        raise ValueError("Source must be a private GLB under Local/CustomuseAssets")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if entry.get("sha256") != digest:
        raise ValueError("Source digest mismatch: " + path.name)
    if len(data) < 28 or struct.unpack_from("<III", data) != (0x46546C67, 2, len(data)):
        raise ValueError("Invalid GLB header: " + path.name)
    size, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise ValueError("GLB JSON chunk missing")
    gltf = json.loads(data[20:20 + size])
    offset = 20 + size
    binary_size, binary_kind = struct.unpack_from("<II", data, offset)
    if binary_kind != 0x004E4942:
        raise ValueError("Embedded GLB binary chunk missing")
    binary = data[offset + 8:offset + 8 + binary_size]
    if len(gltf.get("skins", [])) != 1:
        raise ValueError("Exactly one source skin is required")
    skin = gltf["skins"][0]
    parents = {child: index for index, node in enumerate(gltf["nodes"]) for child in node.get("children", [])}
    joints = skin["joints"]
    names = [gltf["nodes"][index].get("name", "") for index in joints]
    if not all(names) or len(set(names)) != len(names):
        raise ValueError("Source joint names must be nonempty and unique")
    hierarchy = []
    for index in joints:
        parent = parents.get(index)
        while parent is not None and parent not in joints:
            parent = parents.get(parent)
        hierarchy.append(gltf["nodes"][parent]["name"] if parent is not None else None)
    accessor = gltf["accessors"][skin["inverseBindMatrices"]]
    if accessor["componentType"] != 5126 or accessor["type"] != "MAT4" or "sparse" in accessor:
        raise ValueError("Expected dense float inverse-bind matrices")
    view = gltf["bufferViews"][accessor["bufferView"]]
    base = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = view.get("byteStride", 64)
    inverse_binds = [value for index in range(accessor["count"])
                     for value in struct.unpack_from("<16f", binary, base + index * stride)]
    if accessor["count"] != len(joints) or not all(math.isfinite(v) for v in inverse_binds):
        raise ValueError("Invalid inverse-bind matrices")
    bounds = []
    for mesh in gltf.get("meshes", []):
        for primitive in mesh["primitives"]:
            positions = gltf["accessors"][primitive["attributes"]["POSITION"]]
            bounds.append([positions.get("min"), positions.get("max")])
    return {"file": str(path), "sha256": digest, "jointNames": names,
            "jointParents": hierarchy, "inverseBinds": inverse_binds, "positionBounds": bounds,
            "animationCount": len(gltf.get("animations", []))}


def compatible(canonical, clip):
    if canonical["jointNames"] != clip["jointNames"] or canonical["jointParents"] != clip["jointParents"]:
        raise ValueError("Clip joint names/hierarchy differ from canonical export; explicit normalization is required")
    for field in ("inverseBinds", "positionBounds"):
        def flat(value):
            if isinstance(value, list):
                return [number for item in value for number in flat(item)]
            return [value]
        left, right = flat(canonical[field]), flat(clip[field])
        if len(left) != len(right) or any(a is None or b is None or abs(a - b) > 1.e-4 for a, b in zip(left, right)):
            raise ValueError("Clip bind pose/units differ from canonical export: " + field)
    if clip["animationCount"] != 1:
        raise ValueError("Each named clip file must contain exactly one animation")


def run(plan_file):
    import unreal
    plan = json.loads(Path(plan_file).read_text())
    character, version = plan["character"], plan["version"]
    if character not in ("KnightB", "DragonV3B") or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", version):
        raise ValueError("Invalid character/version")
    if not plan.get("bones"):
        raise ValueError("Measured bone mapping is required")
    canonical = inspect_glb(plan["rig"])
    checked_clips = []
    names = set()
    for clip in plan.get("clips", []):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", clip["name"]) or clip["name"] in names:
            raise ValueError("Clip keys must be safe unique names")
        names.add(clip["name"])
        if clip.get("root_motion_policy", "preserve") not in ("preserve", "lock_root"):
            raise ValueError("Unknown root-motion policy")
        checked = inspect_glb(clip)
        compatible(canonical, checked)
        checked_clips.append((clip, checked))
    destination = f"/Game/Characters/Customuse/{character}/{version}"
    folder = PROJECT / "Content/Characters/Customuse" / character / version
    if folder.exists() or unreal.EditorAssetLibrary.does_directory_exist(destination):
        raise ValueError("Version destination already exists; replacement is prohibited")
    for class_name in ("VeyrVisualDefinition", "VeyrVisualClip", "VeyrVisualBoneTarget",
                       "InterchangeManager", "InterchangeGenericAssetsPipeline", "ImportAssetParameters"):
        if not hasattr(unreal, class_name):
            raise RuntimeError("Required reflected class unavailable: " + class_name)
    if Path(unreal.Paths.project_dir()).resolve() != PROJECT.resolve():
        raise RuntimeError("Connected editor is not the intended Veyr project")
    receipt_dir = ROOT / "Local/CustomuseImports"
    receipt_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_path = receipt_dir / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".json")
    receipt = {"success": False, "destination": destination, "sourceSHA256": canonical["sha256"],
               "sourceFile": canonical["file"], "steps": [], "nativePresentationVerified": False,
               "status": "Import foundation only; gameplay, deformation and visual acceptance pending"}
    manager = unreal.InterchangeManager.get_interchange_manager_scripted()

    def save_receipt():
        with os.fdopen(os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
            json.dump(receipt, stream, indent=2)
            stream.write("\n")

    def import_one(source, target, skeleton=None):
        pipeline = unreal.InterchangeGenericAssetsPipeline()
        common = pipeline.get_editor_property("common_skeletal_meshes_and_animations_properties")
        common.set_editor_property("import_only_animations", skeleton is not None)
        common.set_editor_property("try_auto_select_skeleton", False)
        common.set_editor_property("use_t0_as_ref_pose", False)
        if skeleton is not None:
            common.set_editor_property("skeleton", skeleton)
        mesh = pipeline.get_editor_property("mesh_pipeline")
        mesh.set_editor_property("import_skeletal_meshes", skeleton is None)
        mesh.set_editor_property("import_static_meshes", False)
        mesh.set_editor_property("update_skeleton_reference_pose", False)
        pipeline.get_editor_property("animation_pipeline").set_editor_property("import_animations", skeleton is not None)
        materials = pipeline.get_editor_property("material_pipeline")
        materials.set_editor_property("import_materials", skeleton is None)
        materials.set_editor_property("reuse_existing_materials", False)
        materials.get_editor_property("texture_pipeline").set_editor_property("import_textures", skeleton is None)
        params = unreal.ImportAssetParameters()
        params.set_editor_property("is_automated", True)
        params.set_editor_property("force_show_dialog", False)
        params.set_editor_property("replace_existing", False)
        params.set_editor_property("follow_redirectors", False)
        params.set_editor_property("override_pipelines", [unreal.SoftObjectPath(pipeline.get_path_name())])
        data = unreal.InterchangeManager.create_source_data(source["file"])
        result = manager.import_asset(target, data, params)
        # Verified live UE 5.8 Python binding: Array[Object] on success,
        # None on failure (the C++ bool/out-array is adapted by the binding).
        ok = result is not None
        objects = list(result) if result is not None else []
        step = {"destination": target, "sourceSHA256": source["sha256"], "nativeSuccess": bool(ok),
                "objects": [{"path": obj.get_path_name(), "class": obj.get_class().get_name()} for obj in objects]}
        receipt["steps"].append(step)
        save_receipt()
        if not ok or not objects:
            raise RuntimeError("Native Interchange failed or returned no assets; inspect owned editor log and partial receipt")
        for obj in objects:
            if not obj.get_path_name().startswith(destination + "/"):
                raise RuntimeError("Import unexpectedly returned an asset outside the version folder")
            if not unreal.EditorAssetLibrary.save_loaded_asset(obj, False):
                raise RuntimeError("Saving imported asset failed: " + obj.get_path_name())
        return objects

    save_receipt()
    try:
        objects = import_one(canonical, destination + "/Rig")
        meshes = [obj for obj in objects if isinstance(obj, unreal.SkeletalMesh)]
        if len(meshes) != 1:
            raise RuntimeError("Expected exactly one imported skeletal mesh")
        mesh = meshes[0]
        skeleton = mesh.get_editor_property("skeleton")
        if skeleton is None:
            raise RuntimeError("Imported mesh has no skeleton")
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.VeyrVisualDefinition)
        definition = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "DA_" + character, destination, unreal.VeyrVisualDefinition, factory)
        if definition is None:
            raise RuntimeError("Visual definition creation failed")
        definition.set_editor_property("skeletal_mesh", mesh)
        definition.set_editor_property("source_sha256", canonical["sha256"])
        imported_names = [str(name) for name in definition.get_imported_bone_names()]
        receipt["importedBoneNames"] = imported_names
        def resolve_bone(source_name):
            if source_name in imported_names:
                return source_name
            normalize = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
            candidates = [name for name in imported_names if normalize(name) == normalize(source_name)]
            if len(candidates) != 1:
                raise ValueError("Cannot uniquely resolve imported bone: " + source_name)
            return candidates[0]
        targets = {}
        for key, specification in plan["bones"].items():
            name = specification if isinstance(specification, str) else specification["bone"]
            target = unreal.VeyrVisualBoneTarget()
            target.set_editor_property("bone_name", resolve_bone(name))
            if isinstance(specification, dict):
                offset = specification.get("translation_cm", [0, 0, 0])
                if len(offset) != 3 or not all(math.isfinite(float(value)) for value in offset):
                    raise ValueError("Bone-local target offset must contain three finite values")
                transform = unreal.Transform()
                transform.translation = unreal.Vector(*offset)
                rotation = specification.get("rotation_quat_xyzw", [0, 0, 0, 1])
                if len(rotation) != 4 or not all(math.isfinite(float(value)) for value in rotation):
                    raise ValueError("Bone-local rotation must contain four finite quaternion values")
                length = math.sqrt(sum(float(value)**2 for value in rotation))
                if abs(length-1) > .001:
                    raise ValueError("Bone-local quaternion must be normalized")
                transform.rotation = unreal.Quat(*rotation)
                target.set_editor_property("local_offset", transform)
            targets[key] = target
        definition.set_editor_property("bone_targets", targets)
        definition.set_editor_property("required_bone_targets", plan.get("required_bones", list(targets)))
        definition.set_editor_property("required_clips", plan.get("required_clips", []))
        origin = definition.get_imported_bounds_origin()
        extent = definition.get_imported_bounds_extent()
        height = float(extent.z) * 2
        scale = float(plan.get("mesh_scale", 1))
        if "target_height_cm" in plan:
            scale = float(plan["target_height_cm"]) / height if height > 0 else 0
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Invalid imported height or requested scale")
        # UE 5.8 exposes native math structs directly, not Make/BreakTransform.
        transform = unreal.Transform()
        transform.translation = unreal.Vector(*plan.get("mesh_translation_cm", [0, 0, 0]))
        pitch, yaw, roll = plan.get("mesh_rotation_deg", [0, 0, 0])
        transform.rotation = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll).quaternion()
        transform.scale3d = unreal.Vector(scale, scale, scale)
        definition.set_editor_property("mesh_relative_transform", transform)
        receipt["importedHeightCm"] = height
        receipt["componentScale"] = scale
        receipt["importedBounds"] = {"origin": [origin.x, origin.y, origin.z], "extent": [extent.x, extent.y, extent.z]}
        reference = {}
        for name, pose in definition.get_imported_reference_bone_transforms().items():
            location, rotation, bone_scale = pose.translation, pose.rotation, pose.scale3d
            reference[str(name)] = {"positionCm": [location.x, location.y, location.z],
                                    "rotationQuaternion": [rotation.x, rotation.y, rotation.z, rotation.w],
                                    "scale": [bone_scale.x, bone_scale.y, bone_scale.z]}
        receipt["importedReferenceBones"] = reference
        clips = {}
        for specification, source in checked_clips:
            imported = import_one(source, destination + "/Animations/" + specification["name"], skeleton)
            sequences = [obj for obj in imported if isinstance(obj, unreal.AnimSequence)]
            if len(sequences) != 1 or sequences[0].get_editor_property("skeleton") != skeleton:
                raise RuntimeError("Clip did not bind exclusively to the canonical skeleton")
            sequence = sequences[0]
            root_policy = specification.get("root_motion_policy", "preserve")
            if root_policy not in ("preserve", "lock_root"):
                raise ValueError("Unknown root-motion policy")
            sequence.set_editor_property("enable_root_motion", False)
            sequence.set_editor_property("force_root_lock", root_policy == "lock_root")
            if root_policy == "lock_root":
                expected = plan.get("root_motion_bone")
                if not expected or not imported_names or resolve_bone(expected) != imported_names[0]:
                    raise ValueError("Root lock requires the expected imported root, not a guessed pelvis/extra scene root")
                sequence.set_editor_property("enable_root_motion", False)
                sequence.set_editor_property("force_root_lock", True)
                sequence.set_editor_property("root_motion_root_lock", unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
            if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
                raise RuntimeError("Saving explicit root-motion policy failed")
            entry = unreal.VeyrVisualClip()
            entry.set_editor_property("sequence", sequence)
            for field, default in (("start_seconds", 0), ("end_seconds", -1), ("impact_seconds", -1), ("loop", False)):
                entry.set_editor_property(field, specification.get(field, default))
            clips[specification["name"]] = entry
            receipt.setdefault("clipLengthsSeconds", {})[specification["name"]] = float(sequence.get_editor_property("sequence_length"))
        definition.set_editor_property("clips", clips)
        errors = list(definition.validate_definition(False))
        receipt["definitionErrors"] = errors
        receipt["completeMovesetErrors"] = list(definition.validate_definition(True))
        if errors:
            raise RuntimeError("Imported definition validation failed: " + "; ".join(errors))
        if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
            raise RuntimeError("Saving visual definition failed")
        receipt["definition"] = definition.get_path_name()
        receipt["success"] = True
    except Exception as error:
        receipt["error"] = str(error)
        receipt["partialAssetsPreserved"] = True
        save_receipt()
        raise
    save_receipt()
    unreal.log("VEYR_CUSTOMUSE_IMPORT_RECEIPT " + str(receipt_path))
    return receipt


if __name__ == "__main__":
    plan = os.environ.get("VEYR_CUSTOMUSE_IMPORT_PLAN")
    if not plan:
        raise RuntimeError("Provide VEYR_CUSTOMUSE_IMPORT_PLAN or call run(private_plan_path)")
    run(plan)
