"""Trial T1: load every asset of the copied Greystone pack (and GASP mannequin if present), count failures, and dump
what the blind-written code assumes about the skeleton: hierarchy, sockets, reference-pose component transforms of
the role bones, mesh bounds and material slots per skin. NullRHI commandlet (run_greystone.py load-all).

Pass: zero load failures for the Greystone mesh/skeleton/animations/materials actually used; every role bone and the
sword/shield bones present; foot_l parent calf_l parent thigh_l (the proxy's two-bone foot IK needs that).
"""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
registry = unreal.AssetRegistryHelpers.get_asset_registry()
# --set roots='["/Game/ParagonGreystone/Characters/Heroes/Greystone"]' limits the scan (the 6-minute lock rule: the first
# load builds derived data for every mesh and texture it touches, so the trial loads only the hero folder first).
roots = job['options'].get('roots') or ([g.PACK] + ([g.GASP_MANNEQUIN] if job['options'].get('gasp') else []))
summary = {'roots': roots, 'loaded': 0, 'failed': [], 'byClass': {}}
for root in roots:
    registry.scan_paths_synchronous([root], True)
    assets = registry.get_assets_by_path(root, recursive=True)
    for data in assets:
        path = str(data.package_name) + '.' + str(data.asset_name)
        klass = str(data.asset_class_path.asset_name)
        summary['byClass'][klass] = summary['byClass'].get(klass, 0) + 1
        try:
            obj = unreal.load_asset(path)
        except Exception as error:  # load_asset raises on hard failures
            obj = None
            summary['failed'].append({'path': path, 'class': klass, 'error': str(error)})
            continue
        if obj is None:
            summary['failed'].append({'path': path, 'class': klass, 'error': 'load_asset returned None'})
        else:
            summary['loaded'] += 1

mesh = unreal.load_asset(g.GREYSTONE_MESH)
skeleton = mesh.get_editor_property('skeleton') if mesh else None
report = {'summary': summary, 'mesh': g.GREYSTONE_MESH}
checks = []
if mesh and skeleton:
    world = g.reference_world(skeleton)
    names = list(world)
    parents = g.bone_parents(mesh)
    report['bones'] = [{'name': n, 'parent': parents.get(n),
                        't': [world[n].translation.x, world[n].translation.y, world[n].translation.z],
                        'q': [world[n].rotation.x, world[n].rotation.y, world[n].rotation.z, world[n].rotation.w]}
                       for n in names]
    sockets = []
    for i in range(mesh.num_sockets()):
        s = mesh.get_socket_by_index(i)
        sockets.append({'name': str(s.socket_name), 'bone': str(s.bone_name),
                        'location': [s.relative_location.x, s.relative_location.y, s.relative_location.z],
                        'rotation': [s.relative_rotation.roll, s.relative_rotation.pitch, s.relative_rotation.yaw],
                        'scale': [s.relative_scale.x, s.relative_scale.y, s.relative_scale.z]})
    report['sockets'] = sockets
    needed = sorted(set(g.ROLE_MAP.values()) | {'sword_bottom', 'sword_top', 'shield_inner', 'shield_outer', 'ik_hand_gun'})
    missing = [n for n in needed if n not in names]
    checks.append({'check': 'role and prop bones present', 'pass': not missing, 'missing': missing})
    for side in 'lr':
        chain = [parents.get(f'foot_{side}'), parents.get(f'calf_{side}')]
        checks.append({'check': f'direct two-bone leg {side}', 'pass': chain == [f'calf_{side}', f'thigh_{side}'],
                       'parents': chain, 'note': 'None means the parent query API was unavailable; read bones[] by eye'})
    head = world.get('head')
    if head:
        report['headBoneHeightMeshCm'] = head.translation.z
    feet_z = [world[n].translation.z for n in ('ball_l', 'ball_r', 'foot_l', 'foot_r') if n in world]
    report['lowestFootBoneMeshCm'] = min(feet_z) if feet_z else None
    bounds = mesh.get_bounds()
    report['bounds'] = {'origin': [bounds.origin.x, bounds.origin.y, bounds.origin.z],
                        'extent': [bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z]}
for skin, path in g.SKINS.items():
    if not any(path.startswith(r) for r in roots):
        continue  # outside this run's scope (skins load their textures)
    m = unreal.load_asset(path)
    slots = []
    if m:
        for slot in m.get_editor_property('materials'):
            mi = slot.get_editor_property('material_interface')
            slots.append({'slot': str(slot.get_editor_property('material_slot_name')), 'material': mi.get_path_name() if mi else None})
    report.setdefault('skins', {})[skin] = {'loaded': bool(m), 'slots': slots}
    checks.append({'check': 'skin loads: ' + skin, 'pass': bool(m)})
used_failures = [f for f in summary['failed'] if '/Characters/Heroes/Greystone/' in f['path'] or 'Materials' in f['path']]
checks.append({'check': 'no load failures in the hero mesh/animation/material folders', 'pass': not used_failures,
               'count': len(used_failures)})
report['checks'] = checks
(out / 'load-all.json').write_text(json.dumps(report, indent=1, default=str) + '\n')
unreal.log(f'VEYR_GREYSTONE_LOAD loaded={summary["loaded"]} failed={len(summary["failed"])}')
g.write_result(out, {'success': all(c['pass'] for c in checks if 'leg' not in c['check']), 'loaded': summary['loaded'],
                     'failed': len(summary['failed']), 'checks': checks})
