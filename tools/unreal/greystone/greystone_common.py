"""Shared paths and helpers for the Greystone (quality goal E) editor scripts.

Every script here is written for UE 5.8.3 editor Python and run through run_greystone.py, which launches the
PythonScriptCommandlet (UnrealEditor-Cmd -run=pythonscript) with a job file under Local/. Nothing here was run when
it was written (no engine was available); each script checks its own assumptions and writes them to its receipt.
"""
import hashlib
import json
import os
from pathlib import Path

# The worktree that holds these scripts has no character content (the 6 GB of KnightB assets live in the main
# checkout), so run_greystone.py --project points the steps at the checkout that has it via VEYR_GREYSTONE_PROJECT.
PROJECT = Path(os.environ.get('VEYR_GREYSTONE_PROJECT') or Path(__file__).resolve().parents[3] / 'Unreal/Veyr').resolve()
ROOT = PROJECT.parents[1]
VAULT = Path('/Users/Shared/UnrealEngine/Launcher/VaultCache')
GREYSTONE_VAULT = VAULT / 'ParagonGreystone/data/Content/ParagonGreystone'
GASP_VAULT = VAULT / 'GameAnimationSample_5.8/data/Content'

# Content mount points (both directories are .gitignored: free Epic content, not redistributable).
PACK = '/Game/ParagonGreystone'
GREYSTONE_MESH = PACK + '/Characters/Heroes/Greystone/Meshes/Greystone'
GREYSTONE_SKELETON = PACK + '/Characters/Heroes/Greystone/Meshes/Greystone_Skeleton'
SKINS = {
    'Default': PACK + '/Characters/Heroes/Greystone/Meshes/Greystone',
    'Dragonlord': PACK + '/Characters/Heroes/Greystone/Skins/Dragonlord/Meshes/Greystone_Dragonlord',
    'Novaborn': PACK + '/Characters/Heroes/Greystone/Skins/Novaborn/Meshes/Greystone_Novaborn',
    'Tough': PACK + '/Characters/Heroes/Greystone/Skins/Tough/Meshes/Greystone_Tough',
    'WhiteTiger': PACK + '/Characters/Heroes/Greystone/Skins/WhiteTiger/Meshes/Greystone_WhiteTiger',
}
OURS = '/Game/Characters/Greystone'
RIGS = OURS + '/Rigs'
ANIMS = OURS + '/Anims'
RUNTIME = OURS + '/Runtime'
DEFINITION = RUNTIME + '/DA_Greystone'
MOTION = OURS + '/MotionMatching'
KNIGHT_DEFINITION = '/Game/Characters/Customuse/RuntimePolish/DA_Knight'
GASP_MANNEQUIN = '/Game/Characters/UEFN_Mannequin'
GASP_TWINBLAST_RTG = '/Game/Characters/Paragon/Heroes/TwinBlast/Rigs/RTG_UEFN_to_TwinBlast'

# The 64 clip keys of the active KnightB definition (v050heal); DA_Greystone supplies every one.
KNIGHT_CLIPS = (
    'Backpedal BackpedalGuard BackpedalGuardTwoHand BackpedalStep BlinkLeft BlinkLeftTwoHand BlinkRight '
    'BlinkRightTwoHand Death GripToOneHand GripToTwoHand GuardBreak GuardTwoHand Heal HealSourced HeavyAttack '
    'HeavyAttackAlternate HeavyAttackTwoHand HeavyAttackTwoHandAlternate HeavyAttackTwoHandSourced '
    'HeavyFinisherTwoHandSourced Idle IdleTwoHand LeapAttackSourced LightAttack LightAttackTwoHand LightCombo Roll '
    'RollAttack Run RunAlternate RunOneHandPlanted RunStartTwoHandSourced RunStop RunStopOneHandSourced '
    'RunStopTwoHandSourced RunTwoHand RunTwoHandPlanted RunTwoHandSourced RunningAttackDirect RunningAttackSourced '
    'Stagger StaggerBack StaggerBackTwoHand StaggerFront StaggerFrontTwoHand StaggerLeft StaggerLeftTwoHand '
    'StaggerRight StaggerRightTwoHand StrafeLeft StrafeLeftTwoHand StrafeRight StrafeRightTwoHand StrafeRunLeft '
    'StrafeRunLeftTwoHand StrafeRunRight StrafeRunRightTwoHand TurnLeft90TwoHand TurnRight180QuickTwoHand '
    'TurnRight180TwoHand TurnRight90TwoHand Walk WalkTwoHand').split()
assert len(KNIGHT_CLIPS) == 64

# Native Paragon clips added under extra keys, for the trial film only (never used by gameplay code).
PARAGON_EXTRA = {
    'ParagonIdle': PACK + '/Characters/Heroes/Greystone/Animations/Idle',
    'ParagonJogFwd': PACK + '/Characters/Heroes/Greystone/Animations/Jog_Fwd',
    'ParagonAttackPrimaryA': PACK + '/Characters/Heroes/Greystone/Animations/Attack_PrimaryA',
}

# Bone roles: KnightB (Mixamo) name -> Greystone (Paragon) name. Mirrors VeyrBoneRoles.cpp.
ROLE_MAP = {
    'VeyrRoot': 'root', 'Hips': 'pelvis', 'Spine': 'spine_01', 'Spine1': 'spine_02', 'Spine2': 'spine_03',
    'Neck': 'neck_01', 'Head': 'head',
    'LeftShoulder': 'clavicle_l', 'LeftArm': 'upperarm_l', 'LeftForeArm': 'lowerarm_l', 'LeftHand': 'hand_l',
    'RightShoulder': 'clavicle_r', 'RightArm': 'upperarm_r', 'RightForeArm': 'lowerarm_r', 'RightHand': 'hand_r',
    'LeftUpLeg': 'thigh_l', 'LeftLeg': 'calf_l', 'LeftFoot': 'foot_l', 'LeftToeBase': 'ball_l',
    'RightUpLeg': 'thigh_r', 'RightLeg': 'calf_r', 'RightFoot': 'foot_r', 'RightToeBase': 'ball_r',
}

TARGET_HEIGHT_CM = 244.0


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load_job():
    """The runner passes the job file through VEYR_GREYSTONE_JOB; it must live under Local/."""
    path = Path(os.environ['VEYR_GREYSTONE_JOB']).resolve()
    assert path.is_relative_to((ROOT / 'Local').resolve()), 'job must live under Local/'
    job = json.loads(path.read_text())
    out = Path(job['reportDirectory']).resolve()
    assert out.is_relative_to((ROOT / 'Local').resolve())
    return job, out


def write_result(out, payload):
    (Path(out) / 'result.json').write_text(json.dumps(payload, indent=2, default=str) + '\n')


def package_file(asset_path):
    """/Game/X/Y -> Content/X/Y.uasset on disk (for receipts)."""
    assert asset_path.startswith('/Game/')
    return PROJECT / 'Content' / (asset_path[len('/Game/'):] + '.uasset')


def bone_parents(mesh):
    """{bone: parent or None} via a transient SkeletalMeshComponent (USkinnedMeshComponent::GetParentBone/GetBoneName
    are BlueprintCallable; neither needs registration). Editor Python only."""
    import unreal
    component = unreal.new_object(unreal.SkeletalMeshComponent)
    component.set_skinned_asset_and_update(mesh)
    parents = {}
    for i in range(component.get_num_bones()):
        name = str(component.get_bone_name(i))
        parent = str(component.get_parent_bone(name))
        parents[name] = None if parent in ('None', '') else parent
    return parents


def reference_world(skeleton_or_mesh):
    """{bone: unreal.Transform} reference pose, component space."""
    import unreal
    skeleton = skeleton_or_mesh.get_editor_property('skeleton') if isinstance(skeleton_or_mesh, unreal.SkeletalMesh) else skeleton_or_mesh
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    return {str(n): unreal.AnimPoseExtensions.get_bone_pose(pose, n, unreal.AnimPoseSpaces.WORLD)
            for n in unreal.AnimPoseExtensions.get_bone_names(pose)}


def socket_world(mesh, socket_name, world):
    """Reference-pose component transform of a mesh or skeleton socket (None if missing)."""
    import unreal
    found = mesh.find_socket_and_index(socket_name)
    socket = found[0] if isinstance(found, tuple) else found
    if not socket:
        return None
    local = unreal.Transform(socket.relative_location, socket.relative_rotation, socket.relative_scale)
    return local * world[str(socket.bone_name)]


# ---- plain-Python rigid math in Unreal's conventions (so no reliance on operator bindings) ----
# Quaternions are (x, y, z, w); q1*q2 rotates by q2 first (FQuat::operator*). Transforms are (q, t, s) with uniform s;
# compose(A, B) == FTransform A*B (A first, then B): rotation qB*qA, translation qB.rotate(sB*tA)+tB.

def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by, aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw, aw*bw - ax*bx - ay*by - az*bz)


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def qrot(q, v):
    x, y, z, w = q
    p = qmul(qmul(q, (v[0], v[1], v[2], 0.0)), (-x, -y, -z, w))
    return (p[0], p[1], p[2])


def qnorm(q):
    n = sum(c*c for c in q) ** .5 or 1.0
    return tuple(c/n for c in q)


def qbetween(a, b):
    """Shortest-arc rotation taking unit vector a onto unit vector b."""
    ax, ay, az = a; bx, by, bz = b
    d = ax*bx + ay*by + az*bz
    if d < -0.999999:
        axis = (0.0, -az, ay) if abs(ax) < .9 else (-ay, ax, 0.0)
        n = sum(c*c for c in axis) ** .5
        return (axis[0]/n, axis[1]/n, axis[2]/n, 0.0)
    c = (ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx)
    return qnorm((c[0], c[1], c[2], 1.0 + d))


def vnorm(v):
    n = sum(c*c for c in v) ** .5 or 1.0
    return tuple(c/n for c in v)


def vsub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def vadd(a, b):
    return tuple(x + y for x, y in zip(a, b))


def vscale(v, k):
    return tuple(x*k for x in v)


def compose(a, b):
    qa, ta, sa = a; qb, tb, sb = b
    return (qnorm(qmul(qb, qa)), vadd(qrot(qb, vscale(ta, sb)), tb), sa*sb)


def tinv(a):
    q, t, s = a
    qi = qinv(q)
    return (qi, vscale(qrot(qi, t), -1.0/s), 1.0/s)


def relative(a, parent):
    """a expressed in parent's frame: a * inverse(parent)."""
    return compose(a, tinv(parent))


def from_unreal(t):
    q = t.rotation; v = t.translation; s = t.scale3d
    return ((q.x, q.y, q.z, q.w), (v.x, v.y, v.z), (s.x + s.y + s.z) / 3.0)


def to_unreal(t):
    import unreal
    q, v, s = t
    return unreal.Transform(unreal.Vector(*v), unreal.Quat(*q).rotator(), unreal.Vector(s, s, s))


def angle_deg(q):
    import math
    return math.degrees(2.0 * math.acos(min(1.0, abs(q[3]))))
