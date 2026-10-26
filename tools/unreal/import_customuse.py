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


def source_morph_curves(filename):
    """Read dense normalized glTF weight channels without changing authored values."""
    raw=Path(filename).read_bytes();length=struct.unpack_from('<I',raw,12)[0]
    gltf=json.loads(raw[20:20+length]);binary=raw[28+length:]
    def values(index):
        accessor=gltf['accessors'][index]
        if accessor['componentType'] != 5126 or 'sparse' in accessor:
            raise ValueError('Normalize source morph channels to dense float before import')
        view=gltf['bufferViews'][accessor['bufferView']]
        start=view.get('byteOffset',0)+accessor.get('byteOffset',0)
        stride=view.get('byteStride',4)
        return [struct.unpack_from('<f',binary,start+i*stride)[0] for i in range(accessor['count'])]
    result={}
    for animation in gltf.get('animations',[]):
        for channel in animation['channels']:
            if channel['target']['path'] != 'weights':continue
            node=gltf['nodes'][channel['target']['node']];mesh=gltf['meshes'][node['mesh']]
            names=mesh.get('extras',{}).get('targetNames',[])
            sampler=animation['samplers'][channel['sampler']]
            if sampler.get('interpolation','LINEAR') != 'LINEAR':
                raise ValueError('Corrective channel needs explicit linear-normalized source')
            times=values(sampler['input']);weights=values(sampler['output'])
            if not names or len(weights) != len(times)*len(names):raise ValueError('Invalid normalized corrective channel')
            for i,name in enumerate(names):result[name]=(times,weights[i::len(names)])
    return result


def prepare_rigid_prop(mesh):
    """Preserve full rigid geometry on the ordinary material path, including translucent echoes."""
    import unreal
    subsystem=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    settings=subsystem.get_nanite_settings(mesh)
    before=bool(settings.get_editor_property('enabled'))
    if before:
        settings.set_editor_property('enabled',False)
        subsystem.set_nanite_settings(mesh,settings,True)
    after=bool(subsystem.get_nanite_settings(mesh).get_editor_property('enabled'))
    if after:raise RuntimeError('Rigid prop still uses Nanite: '+mesh.get_path_name())
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh,False):raise RuntimeError('Could not save rigid prop material-path settings')
    return {'mesh':mesh.get_path_name(),'naniteBefore':before,'naniteAfter':after,'reason':'Small rigid props and translucent blink weapon echoes use original LOD0 materials'}


def prepare_validation_settings():
    """Apply reversible per-process validation settings, without editing assets."""
    import unreal
    # Per-process test settings only; do not save or change shared editor preferences.
    settings=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
    settings_path=ROOT/'Local/native-validation-settings.json'
    if not settings_path.exists():
        settings_path.write_text(json.dumps({'throttle_cpu_when_not_foreground':settings.get_editor_property('bThrottleCPUWhenNotForeground')},indent=2)+'\n')
    settings.set_editor_property('bThrottleCPUWhenNotForeground',False,unreal.PropertyAccessChangeNotifyMode.NEVER)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    for command in ('t.MaxFPS 60','t.IdleWhenNotForeground 0','r.ScreenPercentage 100','r.Editor.Viewport.OverridePIEScreenPercentage 0'):
        unreal.SystemLibrary.execute_console_command(world,command)


def _clip_map(definition):
    return {str(k):v for k,v in definition.clips.items()}

def guard_signature(definition):
    clip=_clip_map(definition).get('GuardTwoHand')
    if not clip:raise RuntimeError('Original two-hand guard is missing')
    return {'sequence':clip.sequence.get_path_name(),'weapon':clip.weapon_mesh.get_path_name() if clip.weapon_mesh else None,'source':clip.approved_source_sha256,'start':float(clip.start_seconds),'end':float(clip.end_seconds),'rate':float(clip.gameplay_play_rate),'loop':bool(clip.loop)}

def verify_sourced_definition(plan,definition,check_replacements=True):
    """Verify actual imported bindings/metadata, not just the shared rig hash."""
    import unreal
    if not plan.get('inherit_definition'):return {}
    expected=plan.get('replace_runtime_source')
    baseline=unreal.load_asset(expected)
    if not baseline:raise RuntimeError('Preservation baseline definition missing')
    actual_guard={}
    if plan['character']=='KnightB':
        baseline_guard=guard_signature(baseline);actual_guard=guard_signature(definition)
        if baseline_guard!=actual_guard:raise RuntimeError('Original guard sequence/weapon/timing changed')
        if actual_guard['source']!=plan['preserved_guard']['source_sha256']:raise RuntimeError('Original guard source hash changed')
    baseline_clips=_clip_map(baseline);clips=_clip_map(definition)
    replacements={c['name'] for c in plan['clips']} if check_replacements else set()
    preserved=[]
    for key,old in baseline_clips.items():
        if key in replacements:continue
        new=clips.get(key)
        if not new:raise RuntimeError('Inherited clip missing: '+key)
        for field in ('sequence','mesh_override','weapon_mesh','approved_source_sha256','start_seconds','end_seconds','gameplay_play_rate','loop'):
            if old.get_editor_property(field)!=new.get_editor_property(field):raise RuntimeError('Inherited clip changed: '+key+'/'+field)
        preserved.append(key)
    if not check_replacements:return {'guard':actual_guard,'preservedClips':preserved}
    checked=[]
    for spec in plan['clips']:
        c=clips.get(spec['name'])
        if not c or c.approved_source_sha256!=spec['approved_source_sha256'] or c.approved_source_file!=spec['approved_source_file']:raise RuntimeError('Imported source identity differs: '+spec['name'])
        for field in ('gameplay_play_rate','nominal_speed_cm_per_second','start_seconds','end_seconds','root_sample_rate'):
            if abs(float(c.get_editor_property(field))-float(spec[field]))>.001:raise RuntimeError('Imported metadata differs: '+spec['name']+'/'+field)
        if bool(c.root_motion_removed)!=bool(spec['root_motion_removed']) or bool(c.loop)!=bool(spec['loop']):raise RuntimeError('Imported motion policy differs: '+spec['name'])
        actual=list(c.root_translation_samples_cm);expected_samples=spec['root_translation_samples_cm']
        if len(actual)!=len(expected_samples) or any(max(abs(v.x-p[0]),abs(v.y-p[1]),abs(v.z-p[2]))>.001 for v,p in zip(actual,expected_samples)):raise RuntimeError('Imported root samples differ: '+spec['name'])
        windows=list(c.damage_windows)
        if len(windows)!=len(spec['damage_windows']) or any(max(abs(v.x-p[0]),abs(v.y-p[1]))>1e-5 for v,p in zip(windows,spec['damage_windows'])):raise RuntimeError('Imported strike windows differ: '+spec['name'])
        if abs(c.sequence.get_play_length()-spec['source_duration'])>1./300+.001:raise RuntimeError('Imported sequence duration differs: '+spec['name'])
        checked.append(spec['name'])
    return {'guard':actual_guard,'preservedClips':preserved,'replacementMetadataVerified':checked}

def finalize_existing(plan):
    """Finish the approved native import without reimporting or changing source assets."""
    import unreal
    character,version=plan['character'],plan['version']
    prepare_validation_settings()
    path=f"/Game/Characters/Customuse/{character}/{version}/DA_{character}"
    definition=unreal.load_asset(path)
    if not isinstance(definition,unreal.VeyrVisualDefinition):raise RuntimeError('Native definition missing before finalization')
    errors=list(definition.validate_definition(True))
    if errors:raise RuntimeError('Incomplete import: '+'; '.join(errors))
    clip_entries=dict(definition.clips)
    specifications={str(c['name']).lower():c for c in plan.get('clips',[])}
    for key,clip in clip_entries.items():
        specification=specifications.get(str(key).lower())
        if specification and 'gameplay_play_rate' in specification:
            rate=float(specification['gameplay_play_rate'])
            if not math.isfinite(rate) or not .1<=rate<=4.:raise ValueError('Invalid explicit gameplay play rate')
            clip.set_editor_property('gameplay_play_rate',rate)
    definition.set_editor_property('clips',clip_entries)
    runtime_name='Knight' if character=='KnightB' else 'Dragon'
    runtime_folder=plan.get('runtime_folder','RuntimeApproved')
    if runtime_folder not in ('RuntimeApproved','RuntimePolish'):
        raise ValueError('Unexpected runtime definition namespace')
    runtime=unreal.load_asset('/Game/Characters/Customuse/'+runtime_folder+'/DA_'+runtime_name)
    owns_runtime=runtime and (runtime_folder=='RuntimeApproved' or unreal.EditorAssetLibrary.get_metadata_tag(runtime,'VeyrPolishSourceDefinition')==path)
    if owns_runtime and runtime.source_sha256==definition.source_sha256:
        runtime.set_editor_property('clips',clip_entries)
        unreal.EditorAssetLibrary.save_loaded_asset(runtime,False)
    record={'character':character,'definition':path,'completeClips':len(definition.clips),'materials':[],'sourcedVerification':verify_sourced_definition(plan,definition)}
    if character=='KnightB':
        props={mesh.get_path_name():mesh for mesh in definition.props.values() if mesh}
        for clip in definition.clips.values():
            if clip.weapon_mesh:props[clip.weapon_mesh.get_path_name()]=clip.weapon_mesh
        owned_prefix=f'/Game/Characters/Customuse/{character}/{version}/'
        record['rigidProps']=[prepare_rigid_prop(mesh) for mesh in props.values() if mesh.get_path_name().startswith(owned_prefix)]
        record['inheritedPropsPreserved']=[mesh.get_path_name() for mesh in props.values() if not mesh.get_path_name().startswith(owned_prefix)]
    if character=='DragonV3B':
        import prepare_dragon_visibility_material as visibility
        mesh=definition.skeletal_mesh
        slots=list(mesh.get_editor_property('materials'))
        if len(slots)!=1:raise RuntimeError('Expected the approved single dragon material')
        source=slots[0].get_editor_property('material_interface')
        if unreal.EditorAssetLibrary.get_metadata_tag(source,visibility.TAG_OWNER)==visibility.OWNER:
            material=source
        else:
            result=visibility.run(source.get_path_name())
            material=unreal.load_asset(result['material'])
        meshes={mesh.get_path_name():mesh}
        for clip in definition.clips.values():
            variant=clip.get_editor_property('mesh_override')
            if variant:meshes[variant.get_path_name()]=variant
        for target in meshes.values():
            materials=list(target.get_editor_property('materials'))
            for slot in materials:slot.set_editor_property('material_interface',material)
            target.set_editor_property('materials',materials)
            if not unreal.EditorAssetLibrary.save_loaded_asset(target,False):raise RuntimeError('Could not save approved dragon visibility material binding')
            record['materials'].append({'mesh':target.get_path_name(),'material':material.get_path_name()})
    unreal.EditorAssetLibrary.save_loaded_asset(definition,False)
    receipt=ROOT/'Local/CustomuseImports'/('finalized-'+character+'-'+version+'.json')
    receipt.write_text(json.dumps(record,indent=2)+'\n')
    return record


def run(plan_file):
    import unreal
    plan = json.loads(Path(plan_file).read_text())
    character, version = plan["character"], plan["version"]
    if plan.get("verify_render_policy_only"):
        import importlib, probe_render_policy
        importlib.reload(probe_render_policy)
        probe_render_policy.run()
        return {'definition':'/Game/Characters/Customuse/DragonV3B/v026/DA_DragonV3B'}
    if plan.get("print_skin_cache_only"):
        subsystem=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world=subsystem.get_game_world() or subsystem.get_editor_world()
        if not world:raise RuntimeError('Skin Cache diagnostics require an owned world')
        # Arm a bounded render-frame window before starting PIE. The import
        # entry point deliberately refuses to run during a live play session.
        unreal.SystemLibrary.execute_console_command(world,'r.SkinCache.PrintMemorySummary 240')
        return {'definition':'/Game/Characters/Customuse/RuntimePolish/DA_Dragon'}
    if plan.get("inspect_dirty_content_only"):
        packages=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        (ROOT/'Local/native-dirty-content.json').write_text(json.dumps([p.get_path_name() for p in packages],indent=2)+'\n')
        return {'definition':f'/Game/Characters/Customuse/{character}/{version}/DA_{character}'}
    if plan.get("prepare_validation_settings_only"):
        prepare_validation_settings()
        return {'definition':f'/Game/Characters/Customuse/{character}/{version}/DA_{character}'}
    if plan.get("restore_editor_settings"):
        import unreal
        settings_file=ROOT/'Local/native-validation-settings.json'
        if settings_file.exists():
            original=json.loads(settings_file.read_text())
            settings=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
            settings.set_editor_property('bThrottleCPUWhenNotForeground',original['throttle_cpu_when_not_foreground'],unreal.PropertyAccessChangeNotifyMode.NEVER)
        if plan.get("quit_owned_editor_after_restore"):
            if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():raise RuntimeError('Preserving dirty content; inspect and save before shutdown')
            if unreal.EditorLevelLibrary.get_game_world() is not None:raise RuntimeError('Stop PIE before normal owned-editor shutdown')
            unreal.SystemLibrary.quit_editor()
        return {'definition':f'/Game/Characters/Customuse/{character}/{version}/DA_{character}'}
    if plan.get("verify_pose_only"):
        import probe_approved_poses
        return probe_approved_poses.run(plan)
    if plan.get("finalize_only"):
        return finalize_existing(plan)
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
        variant_spec = plan.get("mesh_variants", {}).get(clip.get("mesh_variant"))
        compatible(inspect_glb(variant_spec) if variant_spec else canonical, checked)
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

    def import_one(source, target, skeleton=None, static=False, mesh_variant=False):
        pipeline = unreal.InterchangeGenericAssetsPipeline()
        common = pipeline.get_editor_property("common_skeletal_meshes_and_animations_properties")
        common.set_editor_property("import_only_animations", skeleton is not None and not mesh_variant)
        common.set_editor_property("try_auto_select_skeleton", False)
        common.set_editor_property("use_t0_as_ref_pose", False)
        if skeleton is not None:
            common.set_editor_property("skeleton", skeleton)
        mesh = pipeline.get_editor_property("mesh_pipeline")
        mesh.set_editor_property("import_skeletal_meshes", (skeleton is None or mesh_variant) and not static)
        mesh.set_editor_property("import_static_meshes", static)
        mesh.set_editor_property("import_morph_targets", True)
        mesh.set_editor_property("merge_morph_targets_with_same_name", False)
        mesh.set_editor_property("update_skeleton_reference_pose", False)
        animation_pipeline = pipeline.get_editor_property("animation_pipeline")
        animation_pipeline.set_editor_property("import_animations", skeleton is not None and not mesh_variant)
        animation_pipeline.set_editor_property("custom_bone_animation_sample_rate", 300)
        animation_pipeline.set_editor_property("frame_alignment", unreal.InterchangeFrameAlignment.SNAP_TO_CEILING)
        materials = pipeline.get_editor_property("material_pipeline")
        materials.set_editor_property("import_materials", skeleton is None or mesh_variant)
        materials.set_editor_property("reuse_existing_materials", False)
        materials.get_editor_property("texture_pipeline").set_editor_property("import_textures", skeleton is None or mesh_variant)
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
        inherited=None
        if plan.get('inherit_definition'):
            inherited=unreal.load_asset(plan['inherit_definition'])
            if not isinstance(inherited,unreal.VeyrVisualDefinition):raise RuntimeError('Inherited native definition missing')
            if unreal.EditorAssetLibrary.get_metadata_tag(inherited,'VeyrPolishSourceDefinition')!=plan.get('replace_runtime_source'):raise RuntimeError('Unexpected inherited runtime version')
            receipt['preservedBaseline']=verify_sourced_definition(plan,inherited,False)
            inherited_skeleton=inherited.skeletal_mesh.get_editor_property('skeleton')
            objects=import_one(canonical,destination+'/Rig',inherited_skeleton,mesh_variant=True)
            receipt['inheritedDefinition']=inherited.get_path_name()
        else:
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
        mesh_variants = {}
        for variant_name, variant in plan.get("mesh_variants", {}).items():
            variant_checked = inspect_glb(variant)
            if variant_checked["jointNames"] != canonical["jointNames"] or variant_checked["jointParents"] != canonical["jointParents"]:
                raise RuntimeError("Mesh variant changed the canonical bone layout")
            objects = import_one(variant, destination + "/MeshVariants/" + variant_name, skeleton, mesh_variant=True)
            variants = [obj for obj in objects if isinstance(obj, unreal.SkeletalMesh)]
            if len(variants) != 1 or variants[0].get_editor_property("skeleton") != skeleton:
                raise RuntimeError("Variant did not bind to the shared skeleton: " + variant_name)
            mesh_variants[variant_name] = variants[0]
        props_by_file = {}
        for filename, prop in plan.get("props", {}).items():
            source_path = Path(prop["file"]).resolve()
            if not source_path.is_relative_to(SOURCE_ROOT.resolve()) or hashlib.sha256(source_path.read_bytes()).hexdigest() != prop["sha256"]:
                raise ValueError("Static prop provenance mismatch: " + filename)
            imported = import_one(prop, destination + "/Props/" + Path(filename).stem, static=True)
            static_meshes = [obj for obj in imported if isinstance(obj, unreal.StaticMesh)]
            if len(static_meshes) != 1:
                raise RuntimeError("Expected one rigid approved prop: " + filename)
            prepare_rigid_prop(static_meshes[0])
            props_by_file[filename] = static_meshes[0]
        if props_by_file:
            definition.set_editor_property("props", {"Cup": props_by_file["DrinkingCup.glb"]} if "DrinkingCup.glb" in props_by_file else {})
        clips = _clip_map(inherited) if inherited else {}
        imported_sequences = {}
        for specification, source in checked_clips:
            # Phase aliases share the same native sequence; only trim windows differ.
            sequence = imported_sequences.get(source["sha256"])
            if sequence is None:
                imported = import_one(source, destination + "/Animations/" + specification["name"], skeleton)
                sequences = [obj for obj in imported if isinstance(obj, unreal.AnimSequence)]
                compatible_sequences = [obj for obj in sequences if obj.get_editor_property("skeleton") == skeleton]
                if not compatible_sequences:
                    raise RuntimeError("Clip did not bind to the canonical skeleton")
                track_counts = {obj.get_path_name(): len(unreal.AnimationLibrary.get_animation_track_names(obj)) for obj in compatible_sequences}
                sequence = max(compatible_sequences, key=lambda obj: track_counts[obj.get_path_name()])
                if track_counts[sequence.get_path_name()] == 0:
                    raise RuntimeError("Imported action has no bone tracks")
                # glTF Interchange may emit an additional morph-only sequence and
                # duplicate/default curves on the skeletal sequence. Reconstruct
                # float curves from the exact approved normalized weight channel.
                merged_curves = []
                existing_curves = {str(n) for n in unreal.AnimationLibrary.get_animation_curve_names(sequence, unreal.RawCurveTrackTypes.RCT_FLOAT)}
                for curve_name, (times, values) in source_morph_curves(source["file"]).items():
                    if curve_name in existing_curves:
                        unreal.AnimationLibrary.remove_curve(sequence, curve_name, False)
                    unreal.AnimationLibrary.add_curve(sequence, curve_name, unreal.RawCurveTrackTypes.RCT_FLOAT, False)
                    unreal.AnimationLibrary.add_float_curve_keys(sequence, curve_name, times, values)
                    unreal.AnimationLibrary.set_curve_meta_data_morph_target(skeleton, curve_name, True)
                    actual_times, actual_values = unreal.AnimationLibrary.get_float_keys(sequence, curve_name)
                    if len(actual_values) != len(values) or max((abs(a-b) for a,b in zip(actual_values,values)), default=0.) > 1.e-6:
                        raise RuntimeError("Native corrective curve differs from approved source: " + curve_name)
                    merged_curves.append(curve_name)
                receipt.setdefault("nativeAnimationMerges", {})[specification["name"]] = {"boneTrackCounts": track_counts, "selectedSequence": sequence.get_path_name(), "mergedCurves": merged_curves, "curveSource": "exact approved GLB weights"}
                imported_sequences[source["sha256"]] = sequence
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
            if specification.get("mesh_variant"):
                entry.set_editor_property("mesh_override", mesh_variants[specification["mesh_variant"]])
            for field, default in (("start_seconds", 0), ("end_seconds", -1), ("impact_seconds", -1), ("loop", False)):
                entry.set_editor_property(field, specification.get(field, default))
            if specification.get("approved_source_file"):
                entry.set_editor_property("approved_source_file", specification["approved_source_file"])
                entry.set_editor_property("approved_source_sha256", specification.get("approved_source_sha256", ""))
                entry.set_editor_property("damage_windows", [unreal.Vector2D(*window) for window in specification.get("damage_windows", [])])
                entry.set_editor_property("nominal_speed_cm_per_second", specification.get("nominal_speed_cm_per_second", 0.0))
                entry.set_editor_property("gameplay_play_rate", specification.get("gameplay_play_rate", 1.0))
                entry.set_editor_property("root_translation_samples_cm", [unreal.Vector(*point) for point in specification.get("root_translation_samples_cm", [])])
                entry.set_editor_property("root_yaw_samples_degrees", specification.get("root_yaw_samples_degrees", []))
                entry.set_editor_property("root_sample_rate", specification.get("root_sample_rate", 60.0))
                entry.set_editor_property("root_motion_removed", specification.get("root_motion_removed", False))
                if specification.get("weapon_file"):
                    entry.set_editor_property("weapon_mesh", props_by_file[specification["weapon_file"]])
            clips[specification["name"]] = entry
            receipt.setdefault("clipLengthsSeconds", {})[specification["name"]] = float(sequence.get_editor_property("sequence_length"))
        definition.set_editor_property("clips", clips)
        receipt['sourcedVerification']=verify_sourced_definition(plan,definition)
        receipt["morphTargets"] = [str(name) for name in definition.get_imported_morph_target_names()]
        receipt["clipCurveRanges"] = {}
        for key, entry in clips.items():
            curve_names = list(unreal.AnimationLibrary.get_animation_curve_names(entry.sequence, unreal.RawCurveTrackTypes.RCT_FLOAT))
            ranges = {}
            for curve_name in curve_names:
                times, values = unreal.AnimationLibrary.get_float_keys(entry.sequence, curve_name)
                if values:ranges[str(curve_name)] = [min(values), max(values), len(values)]
            receipt["clipCurveRanges"][str(key)] = ranges
        if character == "DragonV3B":
            raw=Path(canonical['file']).read_bytes()
            length=struct.unpack_from('<I',raw,12)[0]
            document=json.loads(raw[20:20+length])
            body=next(node for node in document['nodes'] if 'skin' in node and 'mesh' in node)
            expected=list(document['meshes'][body['mesh']].get('extras',{}).get('targetNames',[]))
            receipt['expectedMorphTargets']=expected
            if len(expected)<8 or set(receipt['morphTargets'])!=set(expected):
                raise RuntimeError('Dragon native morph identities differ from the complete source union')
            for specification,checked in checked_clips:
                ranges=receipt['clipCurveRanges'].get(specification['name'],{})
                for name,(_,values) in source_morph_curves(checked['file']).items():
                    if not values or max(abs(v) for v in values)<=.00001:continue
                    actual=ranges.get(name)
                    if actual is None or abs(actual[0]-min(values))>.0001 or abs(actual[1]-max(values))>.0001:
                        raise RuntimeError('Dragon corrective curve range differs from source: '+specification['name']+'/'+name)
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
