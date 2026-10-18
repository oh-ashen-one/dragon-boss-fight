"""Author original breath sprite materials inside the verified, owned UE editor.

Run via runpy.run_path(this_file, run_name='__main__') through native editor
Python. This script never launches an editor, imports textures, or deletes assets.
Re-running reuses only matching owned recipe assets; collisions fail closed.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "Unreal/Veyr"
DESTINATION = "/Game/Veyr/FX/v2"
OWNER = "Veyr.original-breath-materials.v1"
RECIPES = {
    "M_VeyrBreathCore": {"blend": "additive", "color": [1.0, 0.78, 0.40, 1.0], "brightness": 6.0, "edge_power": 2.8},
    "M_VeyrBreathFlame": {"blend": "additive", "color": [1.0, 0.12, 0.012, 1.0], "brightness": 3.0, "edge_power": 1.8},
    "M_VeyrBreathSmoke": {"blend": "translucent", "color": [0.10, 0.085, 0.075, 1.0], "brightness": 0.5, "edge_power": 2.2},
}
GRAPH_VERSION = "radial-uv-single-gradient-noise-depthfade-35-instance-alpha-seed-v1"
TAG_OWNER = "VeyrFXOwner"
TAG_RECIPE = "VeyrFXRecipeSHA256"
TAG_COUNT = "VeyrFXExpressionCount"
LIB = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary


def enum_value(enum, *names):
    for name in names:
        value = getattr(enum, name, None)
        if value is not None:
            return value
    raise RuntimeError("Required native enum unavailable: " + "/".join(names))


def recipe_hash(recipe):
    return hashlib.sha256(json.dumps({"graph": GRAPH_VERSION, "settings": recipe}, sort_keys=True).encode()).hexdigest()


def expected_blend(recipe):
    return unreal.BlendMode.BLEND_ADDITIVE if recipe["blend"] == "additive" else unreal.BlendMode.BLEND_TRANSLUCENT


def validate_owned(material, recipe):
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Existing path is not a Material; refusing overwrite")
    if str(ASSETS.get_metadata_tag(material, TAG_OWNER)) != OWNER or str(ASSETS.get_metadata_tag(material, TAG_RECIPE)) != recipe_hash(recipe):
        raise RuntimeError("Existing material lacks matching owned recipe; refusing overwrite")
    if material.get_editor_property("blend_mode") != expected_blend(recipe):
        raise RuntimeError("Existing material blend mode differs; refusing modification")
    if material.get_editor_property("shading_model") != unreal.MaterialShadingModel.MSM_UNLIT:
        raise RuntimeError("Existing material is not unlit; refusing modification")
    if material.get_editor_property("disable_depth_test") or not material.get_editor_property("two_sided"):
        raise RuntimeError("Existing material depth/sidedness settings differ; refusing modification")
    if not material.get_editor_property("used_with_instanced_static_meshes"):
        raise RuntimeError("Existing material is not marked for instanced meshes; refusing modification")
    if str(LIB.get_num_material_expressions(material)) != str(ASSETS.get_metadata_tag(material, TAG_COUNT)):
        raise RuntimeError("Existing expression count differs from generated receipt; refusing modification")


def create_graph(material, recipe):
    count = 0

    def node(kind, **properties):
        nonlocal count
        expression = LIB.create_material_expression(material, getattr(unreal, kind), -1400 + (count % 5) * 230, (count // 5) * 190)
        if expression is None:
            raise RuntimeError("Native expression creation failed: " + kind)
        expression.set_editor_property("desc", "Veyr original breath / " + str(count))
        count += 1
        for key, value in properties.items():
            expression.set_editor_property(key, value)
        return expression

    def link(source, target, pin):
        names = [str(name) for name in LIB.get_material_expression_input_names(target)]
        # UE exposes anonymous single inputs as NAME_None. An empty pin name
        # selects that one verified input in MaterialEditingLibrary.
        actual_pin = "" if pin == "Input" and names in (["None"], [""]) else pin
        if (actual_pin and actual_pin not in names) or not LIB.connect_material_expressions(source, "", target, actual_pin):
            raise RuntimeError("Native material connection failed: " + pin + "; available=" + str(names))

    def multiply(a, b):
        result = node("MaterialExpressionMultiply")
        link(a, result, "A"); link(b, result, "B")
        return result

    material.set_editor_property("blend_mode", expected_blend(recipe))
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("disable_depth_test", False)
    material.set_editor_property("used_with_instanced_static_meshes", True)

    uv = node("MaterialExpressionTextureCoordinate")
    center = node("MaterialExpressionConstant2Vector", r=0.5, g=0.5)
    distance = node("MaterialExpressionDistance")
    link(uv, distance, "A"); link(center, distance, "B")
    twice_radius = multiply(distance, node("MaterialExpressionConstant", r=2.0))
    inverse = node("MaterialExpressionOneMinus"); link(twice_radius, inverse, "Input")
    saturated = node("MaterialExpressionSaturate"); link(inverse, saturated, "Input")
    radial = node("MaterialExpressionPower", const_exponent=recipe["edge_power"])
    link(saturated, radial, "Base")

    alpha_data = node("MaterialExpressionPerInstanceCustomData", data_index=0, const_default_value=0.0)
    alpha = node("MaterialExpressionVertexInterpolator"); link(alpha_data, alpha, "VS")
    seed_data = node("MaterialExpressionPerInstanceCustomData", data_index=1, const_default_value=0.0)
    seed = node("MaterialExpressionVertexInterpolator"); link(seed_data, seed, "VS")
    uv3 = node("MaterialExpressionAppendVector"); link(uv, uv3, "A"); link(seed, uv3, "B")
    noise = node("MaterialExpressionNoise", scale=6.0, quality=1, levels=1, output_min=0.45, output_max=1.0,
                 noise_function=enum_value(unreal.NoiseFunction, "NOISEFUNCTION_GRADIENT_ALU", "GRADIENT_ALU"))
    link(uv3, noise, "World Position")
    opacity = multiply(multiply(radial, noise), alpha)
    fade = node("MaterialExpressionDepthFade", fade_distance_default=35.0)
    link(opacity, fade, "Opacity")
    tint = node("MaterialExpressionVectorParameter", parameter_name="Tint", default_value=unreal.LinearColor(*recipe["color"]))
    brightness = node("MaterialExpressionScalarParameter", parameter_name="Brightness", default_value=recipe["brightness"])
    emissive = multiply(tint, brightness)
    if not LIB.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError("Emissive connection failed")
    if not LIB.connect_material_property(fade, "", unreal.MaterialProperty.MP_OPACITY):
        raise RuntimeError("Opacity connection failed")
    LIB.layout_material_expressions(material)
    return count


def main():
    if Path(unreal.Paths.project_dir()).resolve() != PROJECT.resolve():
        raise RuntimeError("Refusing to author FX in a different Unreal project")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt_dir = ROOT / "Local" / ("fx-materials-" + stamp)
    receipt_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt_file = receipt_dir / "receipt.json"
    receipt = {"owner": OWNER, "graphVersion": GRAPH_VERSION, "materials": [], "success": False,
               "originalMathGraph": True, "externalTextures": False, "nativeRenderedAcceptance": False}

    def save():
        temporary = receipt_file.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
        temporary.replace(receipt_file)

    save()
    try:
        # Preflight all collisions before creating any new asset.
        for name, recipe in RECIPES.items():
            path = DESTINATION + "/" + name
            if ASSETS.does_asset_exist(path):
                validate_owned(ASSETS.load_asset(path), recipe)
        for name, recipe in RECIPES.items():
            path = DESTINATION + "/" + name
            reused = ASSETS.does_asset_exist(path)
            entry = {"path": path, "recipeSHA256": recipe_hash(recipe), "reused": reused, "saved": False}
            receipt["materials"].append(entry); save()
            if reused:
                material = ASSETS.load_asset(path)
            else:
                material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, DESTINATION, unreal.Material, unreal.MaterialFactoryNew())
                if material is None or material.get_path_name() != path + "." + name:
                    raise RuntimeError("Native material creation returned an unexpected path: " + path)
                entry["expressionCount"] = create_graph(material, recipe)
            errors = list(LIB.recompile_material(material))
            entry["compileErrors"] = [str(error) for error in errors]
            if errors:
                raise RuntimeError("Native material compilation failed: " + path)
            if not reused:
                ASSETS.set_metadata_tag(material, TAG_OWNER, OWNER)
                ASSETS.set_metadata_tag(material, TAG_RECIPE, recipe_hash(recipe))
                ASSETS.set_metadata_tag(material, TAG_COUNT, str(LIB.get_num_material_expressions(material)))
            if not ASSETS.save_loaded_asset(material, False):
                raise RuntimeError("Native material save failed: " + path)
            loaded = ASSETS.load_asset(path)
            if loaded is None or loaded.get_path_name() != material.get_path_name():
                raise RuntimeError("Saved material resolved through an unexpected redirector")
            validate_owned(loaded, recipe)
            entry["savedObjectPath"] = loaded.get_path_name()
            entry["saved"] = True; save()
        receipt["success"] = True
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        save()
        unreal.log("VEYR_FX_MATERIAL_RECEIPT " + str(receipt_file))


if __name__ == "__main__":
    main()
