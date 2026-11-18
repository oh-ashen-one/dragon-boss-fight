"""Trial T3a: IK rigs and retargeters, modelled on GASP's IK_TwinBlast_Retarget / RTG_UEFN_to_TwinBlast.

Creates under /Game/Characters/Greystone/Rigs:
  IK_Greystone              chains Root, Spine, Neck, Head, Left/RightClavicle, Left/RightArm (goal *HandIK),
                            Left/RightLeg (goal *FootIK), Left/RightToe, fingers where both rigs have them;
                            retarget root pelvis; auto FBIK solver (target side only). Same chain names as TwinBlast,
                            so GASP's retargeter maps by exact name.
  IK_KnightB                the same chains on our KnightB rig (Mixamo names), retarget root Hips.
  RTG_KnightB_to_Greystone  default op stack, chains mapped by exact name, target auto-aligned to the source pose.
  RTG_UEFN_to_Greystone     (only when the GASP mannequin set was copied): a duplicate of RTG_UEFN_to_TwinBlast with
                            its target rig swapped to IK_Greystone - Epic's own source rig, op stack and settings kept.
Sword, shield, cloth, CupSocket and WeaponSocket bones are deliberately in no chain (they keep their parent-local
reference transform; the sword and cup are baked afterwards by retarget_clips.py).

API relied on (read from the installed 5.8.3 headers, IKRigEditor/Public): UIKRigController (GetController,
SetSkeletalMesh, AddRetargetChain, SetRetargetRoot, AddNewGoal, ApplyAutoFBIK), UIKRetargeterController (GetController,
SetIKRig, SetPreviewMesh, AddDefaultOps, AssignIKRigToAllOps, AutoMapChains, AutoAlignAllBones), factories
UIKRigDefinitionFactory / UIKRetargetFactory. Not run yet.
"""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import greystone_common as g

job, out = g.load_job()
tools = unreal.AssetToolsHelpers.get_asset_tools()
library = unreal.EditorAssetLibrary
SRC, TGT = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
receipt = {'rigs': {}, 'retargeters': {}, 'warnings': []}


def fresh(name, folder, klass, factory):
    path = folder + '/' + name
    if library.does_asset_exist(path):
        if not job['options'].get('replace'):
            raise RuntimeError(path + ' exists; pass --set replace=true to rebuild it')
        library.delete_asset(path)
    asset = tools.create_asset(name, folder, klass, factory)
    if not asset:
        raise RuntimeError('could not create ' + path)
    return asset


FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')


def chain_table(kind, names):
    """[(chain, start, end, goal)] for one rig. kind: 'mixamo' or 'paragon'."""
    rows = []
    if kind == 'mixamo':
        side = {'Left': 'Left', 'Right': 'Right'}
        rows += [('Root', 'VeyrRoot', 'VeyrRoot', ''), ('Spine', 'Spine', 'Spine2', ''), ('Neck', 'Neck', 'Neck', ''),
                 ('Head', 'Head', 'Head', '')]
        for s in ('Left', 'Right'):
            rows += [(s + 'Clavicle', s + 'Shoulder', s + 'Shoulder', ''), (s + 'Arm', s + 'Arm', s + 'Hand', s + 'HandIK'),
                     (s + 'Leg', s + 'UpLeg', s + 'Foot', s + 'FootIK'), (s + 'Toe', s + 'ToeBase', s + 'ToeBase', '')]
            for f in FINGERS:
                bones = [b for b in (f'{s}Hand{f}{i}' for i in range(1, 5)) if b in names]
                if len(bones) >= 2:
                    rows.append((s + f, bones[0], bones[-1], ''))
    else:
        rows += [('Root', 'root', 'root', ''), ('Spine', 'spine_01', 'spine_03', ''), ('Neck', 'neck_01', 'neck_02' if 'neck_02' in names else 'neck_01', ''),
                 ('Head', 'head', 'head', '')]
        for s, x in (('Left', 'l'), ('Right', 'r')):
            rows += [(s + 'Clavicle', 'clavicle_' + x, 'clavicle_' + x, ''), (s + 'Arm', 'upperarm_' + x, 'hand_' + x, s + 'HandIK'),
                     (s + 'Leg', 'thigh_' + x, 'foot_' + x, s + 'FootIK'), (s + 'Toe', 'ball_' + x, 'ball_' + x, '')]
            for f in FINGERS:
                bones = [b for b in (f'{f.lower()}_0{i}_{x}' for i in range(1, 4)) if b in names]
                if len(bones) >= 2:
                    rows.append((s + f, bones[0], bones[-1], ''))
    return [r for r in rows if r[1] in names and r[2] in names]


def build_rig(name, mesh, kind, root_bone, fbik):
    rig = fresh(name, g.RIGS, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    if not c.set_skeletal_mesh(mesh):
        raise RuntimeError(name + ': mesh rejected')
    names = set(g.bone_parents(mesh))
    table = chain_table(kind, names)
    for chain, start, end, goal in table:
        goal_name = ''
        if goal:
            goal_name = str(c.add_new_goal(goal, end))
        made = c.add_retarget_chain(chain, start, end, goal_name)
        if str(made) in ('None', ''):
            receipt['warnings'].append(f'{name}: chain {chain} {start}->{end} rejected')
    c.set_retarget_root(root_bone)
    if fbik:
        try:
            if not c.apply_auto_fbik():
                receipt['warnings'].append(name + ': ApplyAutoFBIK returned false (FK-only retarget)')
        except Exception as error:
            receipt['warnings'].append(f'{name}: ApplyAutoFBIK unavailable ({error})')
    library.save_loaded_asset(rig)
    receipt['rigs'][name] = {'chains': [list(r) for r in table], 'retargetRoot': root_bone,
                             'expectedChainsMissing': sorted({'Spine', 'Neck', 'Head', 'LeftArm', 'RightArm', 'LeftLeg', 'RightLeg'} - {r[0] for r in table})}
    return rig


knight_definition = unreal.load_asset(g.KNIGHT_DEFINITION)
knight_mesh = knight_definition.get_editor_property('skeletal_mesh')
greystone_mesh = unreal.load_asset(g.GREYSTONE_MESH)
assert knight_mesh and greystone_mesh, 'KnightB definition or Greystone mesh missing'
ik_greystone = build_rig('IK_Greystone', greystone_mesh, 'paragon', 'pelvis', True)
ik_knight = build_rig('IK_KnightB', knight_mesh, 'mixamo', 'Hips', False)

rtg = fresh('RTG_KnightB_to_Greystone', g.RIGS, unreal.IKRetargeter, unreal.IKRetargetFactory())
c = unreal.IKRetargeterController.get_controller(rtg)
c.set_ik_rig(SRC, ik_knight)
c.set_ik_rig(TGT, ik_greystone)
c.set_preview_mesh(SRC, knight_mesh)
c.set_preview_mesh(TGT, greystone_mesh)
c.add_default_ops()
c.assign_ik_rig_to_all_ops(SRC, ik_knight)
c.assign_ik_rig_to_all_ops(TGT, ik_greystone)
c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
# Pose the target to the source's reference pose (KnightB A/T pose vs Greystone A pose), chain by chain.
c.auto_align_all_bones(TGT, unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
mapped = {}
for chain in receipt['rigs']['IK_Greystone']['chains']:
    mapped[chain[0]] = str(c.get_source_chain(chain[0]))
core = {'Root', 'Spine', 'Neck', 'Head', 'LeftClavicle', 'RightClavicle', 'LeftArm', 'RightArm', 'LeftLeg', 'RightLeg', 'LeftToe', 'RightToe'}
receipt['retargeters']['RTG_KnightB_to_Greystone'] = {'ops': c.get_num_retarget_ops(), 'chainMap': mapped,
                                                      'unmapped': sorted(k for k, v in mapped.items() if v in ('None', '') and k in core),
                                                      'unmappedFingers': sorted(k for k, v in mapped.items() if v in ('None', '') and k not in core)}
library.save_loaded_asset(rtg)

if library.does_asset_exist(g.GASP_TWINBLAST_RTG):
    path = g.RIGS + '/RTG_UEFN_to_Greystone'
    if library.does_asset_exist(path):
        library.delete_asset(path)
    gasp = library.duplicate_asset(g.GASP_TWINBLAST_RTG, path)
    gc = unreal.IKRetargeterController.get_controller(gasp)
    gc.set_ik_rig(TGT, ik_greystone)
    gc.set_preview_mesh(TGT, greystone_mesh)
    gc.assign_ik_rig_to_all_ops(TGT, ik_greystone)
    gc.auto_map_chains(unreal.AutoMapChainType.EXACT, False)  # keep Epic's mapping where names already match
    gc.auto_align_all_bones(TGT, unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
    source_rig = gc.get_ik_rig(SRC)
    receipt['retargeters']['RTG_UEFN_to_Greystone'] = {'template': g.GASP_TWINBLAST_RTG, 'ops': gc.get_num_retarget_ops(),
                                                       'source': source_rig.get_path_name() if source_rig else None}
    library.save_loaded_asset(gasp)
else:
    receipt['warnings'].append('GASP TwinBlast retargeter not copied (copy_pack.py --gasp): UEFN->Greystone skipped')

(out / 'rigs.json').write_text(json.dumps(receipt, indent=1) + '\n')
ok = not receipt['rigs']['IK_Greystone']['expectedChainsMissing'] and not receipt['rigs']['IK_KnightB']['expectedChainsMissing'] \
    and not receipt['retargeters']['RTG_KnightB_to_Greystone']['unmapped']
g.write_result(out, {'success': ok, 'warnings': receipt['warnings']})
