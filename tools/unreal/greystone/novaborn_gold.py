"""E3 skin step: the owner's pick (Local/knight-candidates/greystone-owner-pick-20261118.png) is the NOVABORN skin
(black armour, angular shield, tabard, energy blade) with its energy glow gold instead of blue. Identified 2026-11-19
from the editor thumbnails embedded in the five skin meshes (Default = spiky bronze, Dragonlord = green,
Novaborn = black with blue energy, Tough = bronze/teal with round shield, WhiteTiger = gold/white).

This NullRHI step never edits the Epic pack. It:
1. lists every material slot of Greystone_Novaborn with its vector, scalar and texture parameter names and defaults
   (novaborn-materials.json) - the evidence for which parameter carries the blue energy;
2. for each slot whose material exposes a glow/energy colour vector parameter (names matching GLOW below), makes a
   MaterialInstanceConstant of ours under /Game/Characters/Greystone/Runtime/Skin with that colour turned gold at the
   same luminance (hue from the owner's pick: warm gold, RGB 1.00, 0.62, 0.20 before scaling);
3. duplicates the mesh to /Game/Characters/Greystone/Runtime/SK_Greystone_NovabornGold with those instances.
If no colour parameter exists (the blue is baked into a texture or a constant), step 2 changes nothing, the receipt
says so, and the trial shows Novaborn's own blue energy; a gold version then needs a material copy (follow-up).
"""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
lib = unreal.MaterialEditingLibrary
assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
# First run (skin-20261119T084938Z) matched 'rim' inside GrimeTint and missed the energy blade's lightswordA/B.
# Now: emissive colours and the light-sword colours only; eyes and hair keep their own (owner pick shows neither glowing).
def is_glow(name):
    n = name.lower()
    return ('emissive' in n or n.startswith('lightsword')) and 'grime' not in n and not n.startswith('ult')
SKIP_MATERIAL = ('eye', 'hair', 'mouth', 'eyelash')
GOLD = (1.0, 0.62, 0.20)
# 2026-11-19 trial film: at the source glow's own luminance the gold read flat, saturated yellow, and the blade edge was
# the brightest thing on screen. The owner's pick shows a soft amber rim. Default now: a warmer amber at a fraction of
# the source luminance per parameter family; `--set legacyGold=true` restores the first version (same hue, same luminance).
AMBER = (1.0, 0.42, 0.10)
STRENGTH = (('fullbody_emissive', 0.35),   # armour and shield rim light
            ('emissive_color', 0.12),      # sword head / weapon edge (was the brightest thing on screen)
            ('lightsword', 0.50))          # energy blade colours (already near 1.0)
folder = g.RUNTIME + '/Skin'
source = unreal.load_asset(g.NOVABORN_MESH)
assert source, 'Novaborn mesh missing: ' + g.NOVABORN_MESH


def base_material(mi):
    m = mi
    while isinstance(m, unreal.MaterialInstance):
        m = m.get_editor_property('parent')
    return m


slots = source.get_editor_property('materials')
report, new_slots, changed = [], [], 0
for index, slot in enumerate(slots):
    mi = slot.get_editor_property('material_interface')
    row = {'slot': index, 'name': str(slot.get_editor_property('material_slot_name')), 'material': mi.get_path_name() if mi else None}
    if mi:
        vectors = [str(n) for n in lib.get_vector_parameter_names(mi)]
        scalars = [str(n) for n in lib.get_scalar_parameter_names(mi)]
        textures = [str(n) for n in lib.get_texture_parameter_names(mi)]
        defaults = {}
        for n in vectors:
            try:
                c = lib.get_material_default_vector_parameter_value(base_material(mi), n) if not isinstance(mi, unreal.MaterialInstance) \
                    else lib.get_material_instance_vector_parameter_value(mi, n)
                defaults[n] = [c.r, c.g, c.b, c.a]
            except Exception as error:
                defaults[n] = str(error)
        row.update(vectors=vectors, scalars=scalars, textures=textures, vectorDefaults=defaults)
        skip = any(k in mi.get_name().lower() for k in SKIP_MATERIAL)
        glow = [] if skip else [n for n in vectors if is_glow(n) and isinstance(defaults.get(n), list)]
        row['glowParameters'] = glow
        if glow:
            name = 'MI_GS_NovabornGold_' + str(index)
            path = folder + '/' + name
            # Rewrite in place when it exists: DA_Greystone references the mesh that uses these (unattended deletes of
            # referenced assets fail, as DA_Greystone's did on 2026-11-19).
            mic = unreal.load_asset(path) if assets.does_asset_exist(path) else \
                tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            lib.set_material_instance_parent(mic, mi)
            row['gold'] = {}
            legacy = bool(job.get('options', job).get('legacyGold'))
            hue = GOLD if legacy else AMBER
            for n in glow:
                r, gg, b, a = defaults[n]
                lum = 0.2126 * r + 0.7152 * gg + 0.0722 * b
                hue_lum = 0.2126 * hue[0] + 0.7152 * hue[1] + 0.0722 * hue[2]
                k = lum / hue_lum if hue_lum else 1.0
                if not legacy:
                    k *= next((f for key, f in STRENGTH if n.lower().startswith(key)), 1.0)
                value = unreal.LinearColor(hue[0] * k, hue[1] * k, hue[2] * k, a)
                lib.set_material_instance_vector_parameter_value(mic, n, value)
                row['gold'][n] = [value.r, value.g, value.b, value.a]
            lib.update_material_instance(mic)
            assets.save_loaded_asset(mic)
            slot.set_editor_property('material_interface', mic)
            row['instance'] = path
            changed += 1
    report.append(row)
    new_slots.append(slot)

mesh_path = g.RUNTIME + '/SK_Greystone_NovabornGold'
mesh = unreal.load_asset(mesh_path) if assets.does_asset_exist(mesh_path) else assets.duplicate_asset(g.NOVABORN_MESH, mesh_path)
mesh.set_editor_property('materials', new_slots)
assets.save_loaded_asset(mesh)
skeleton = mesh.get_editor_property('skeleton')
(out / 'novaborn-materials.json').write_text(json.dumps({'source': g.NOVABORN_MESH, 'mesh': mesh_path,
    'skeleton': skeleton.get_path_name() if skeleton else None, 'slotsChanged': changed, 'slots': report}, indent=1) + '\n')
g.write_result(out, {'success': True, 'slotsChanged': changed, 'mesh': mesh_path,
                     'sameSkeleton': bool(skeleton) and skeleton.get_path_name().split('.')[0] == g.GREYSTONE_SKELETON})
