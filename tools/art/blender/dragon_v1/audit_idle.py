"""Audit the idle on the evaluated deform rig/mesh in Blender. Units reported in game cm
(1 rig unit = 2155.818 cm) and degrees. Usage: set ARM (armature object) and RANGE before exec."""
import bpy, json, math
import numpy as np
from mathutils.bvhtree import BVHTree
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
CM = 2155.818
s = bpy.context.scene
arm = bpy.data.objects[globals().get('ARM', 'DRAGON_DEFORM')]
me = bpy.data.objects[globals().get('MESH', 'DRAGON_MESH')]
F0, F1 = globals().get('RANGE', (0, 180))
LEGACY = {'tripo::Head_0','tripo::Head_1','tripo::Head_2','tripo::Head_3','bone_36','bone_37'}
bones = [b.name for b in arm.data.bones if b.name not in LEGACY]
m = me.data
gi = {g.index: g.name for g in me.vertex_groups}
nv = len(m.vertices)
Wt = {}
for v in m.vertices:
    for g in v.groups: Wt.setdefault(gi[g.group], np.zeros(nv))[v.index] = g.weight
def wsum(names): return sum((Wt.get(n, np.zeros(nv)) for n in names), np.zeros(nv))
rest = np.array([v.co for v in m.vertices])
FEET = {'FL': ['tripo::1_Left_Limb_1','bone_9'], 'FR': ['tripo::0_Left_Limb_2','tripo::0_Left_Limb_3','bone_14'],
        'HL': ['tripo::1_Right_Limb_2','tripo::1_Right_Limb_3','tripo::1_Right_Limb_4'], 'HR': ['tripo::0_Right_Limb_2','tripo::0_Right_Limb_3','tripo::0_Right_Limb_4']}
foot_mask = {}
for k, v in FEET.items():
    mk = (wsum(v) > 0.6) & (rest[:,2] < 0.03)
    zmin = rest[mk, 2].min()
    foot_mask[k] = mk & (rest[:, 2] < zmin + 0.003)   # contact band: lowest 6.5 cm of each foot
wing_names = [b for b in bones if b.startswith('VeyrWing')]
wingR = wsum([b for b in wing_names if 'PosZ' in b]) > 0.5
wingL = wsum([b for b in wing_names if 'NegZ' in b]) > 0.5
neck = wsum(['bone_3','bone_4','bone_5','VeyrJaw']) > 0.5
tail = wsum(['bone_18','tripo::Tail_0','tripo::Tail_1','tripo::Tail_2']) > 0.5
body = ~(wingR | wingL | neck | tail)
polys = [list(p.vertices) for p in m.polygons]
def region_polys(mask): return [i for i, p in enumerate(polys) if all(mask[j] for j in p)]
REG = {'wingR': region_polys(wingR), 'wingL': region_polys(wingL), 'neck': region_polys(neck), 'body': region_polys(body), 'tail': region_polys(tail)}
PAIRS = [('wingR','body'),('wingL','body'),('wingR','neck'),('wingL','neck'),('neck','body'),('wingR','wingL'),('tail','body')]
def eval_verts():
    dg = bpy.context.evaluated_depsgraph_get(); ev = me.evaluated_get(dg); mm = ev.to_mesh()
    a = np.empty(len(mm.vertices)*3); mm.vertices.foreach_get('co', a); ev.to_mesh_clear()
    return (np.array(me.matrix_world) @ np.c_[a.reshape(-1,3), np.ones(nv)].T).T[:, :3]
def overlaps(V):
    trees = {k: BVHTree.FromPolygons(V.tolist(), [polys[i] for i in REG[k]]) for k in REG}
    out = {}
    for a, b in PAIRS:
        pa, pb = REG[a], REG[b]
        prs = trees[a].overlap(trees[b])
        out[a+'/'+b] = sum(1 for i, j in prs if not (set(polys[pa[i]]) & set(polys[pb[j]])))
    return out
frames = list(range(F0, F1+1))
mats, locq, Vs_feet, ground_min, finite = [], [], {k: [] for k in FEET}, [], True
lengths = []
inter = {}
s.frame_set(F0)
for f in frames:
    s.frame_set(f)
    M = np.array([np.array(arm.matrix_world @ arm.pose.bones[b].matrix) for b in bones])
    finite &= bool(np.isfinite(M).all())
    mats.append(M)
    lq = []
    for b in bones:
        pb = arm.pose.bones[b]
        lm = pb.matrix if pb.parent is None else pb.parent.matrix.inverted() @ pb.matrix
        q = lm.to_quaternion(); lq.append([q.w, q.x, q.y, q.z])
    locq.append(lq)
    heads = {b: np.array((arm.matrix_world @ arm.pose.bones[b].head)) for b in bones}
    tails = {b: np.array((arm.matrix_world @ arm.pose.bones[b].tail)) for b in bones}
    lengths.append([np.linalg.norm(tails[b]-heads[b]) for b in bones])
    V = eval_verts()
    finite &= bool(np.isfinite(V).all())
    if f == F0: V0 = V
    if f == F1: V1 = V
    for k in FEET: Vs_feet[k].append(V[foot_mask[k]])
    ground_min.append(float(V[:,2].min()))
    if (f - F0) % 5 == 0: inter[f] = overlaps(V)
mats = np.array(mats); locq = np.array(locq); lengths = np.array(lengths)
# rest-pose intersection baseline
for pb in arm.pose.bones: pass
rest_lengths = np.array([arm.data.bones[b].length for b in bones])
len_dev = np.abs(lengths - rest_lengths[None]) / rest_lengths[None]
scaled = [bones[i] for i in np.where(len_dev.max(0) > 1e-4)[0]]
# seam
seam_bone_pos = float(np.abs(mats[0][:, :3, 3] - mats[-1][:, :3, 3]).max()) * CM
dq = np.abs(np.sum(locq[0]*locq[-1], axis=1)).clip(0, 1)
seam_rot = float(np.degrees(2*np.arccos(dq)).max())
seam_mesh = float(np.linalg.norm(V0 - V1, axis=1).max()) * CM
def ang(qa, qb): return np.degrees(2*np.arccos(np.abs(np.sum(qa*qb, axis=-1)).clip(0, 1)))
steps = ang(locq[1:], locq[:-1])                  # per-frame local rotation per bone
vel_seam = float(np.abs(steps[0] - steps[-1]).max())
acc = np.abs(np.diff(steps, axis=0))
# wrap-around accel across seam
pos = mats[:, :, :3, 3] * CM
vel = np.diff(pos, axis=0)
seam_vel_mismatch = float(np.linalg.norm(vel[0] - vel[-1], axis=1).max())
accel = np.linalg.norm(np.diff(vel, axis=0), axis=2)
feet = {}
for k in FEET:
    A = np.array(Vs_feet[k]) * CM  # frames x n x 3
    drift = np.linalg.norm(A - A[0][None], axis=2)
    feet[k] = {'contact_verts': int(A.shape[1]), 'bind_min_z_cm': float(rest[foot_mask[k], 2].min()*CM), 'max_drift_cm': float(drift.max()), 'min_z_cm': float(A[:, :, 2].min()),
               'lowest_vertex_z_range_cm': [float(A[:, :, 2].min(1).min()), float(A[:, :, 2].min(1).max())]}
names = list(inter[frames[0]].keys())
inter_tab = {n: [inter[f][n] for f in sorted(inter)] for n in names}
rep = {
 'frames': [F0, F1], 'fps': s.render.fps, 'finite': finite,
 'loop_seam': {'max_bone_world_pos_delta_cm': seam_bone_pos, 'max_bone_local_rot_delta_deg': seam_rot, 'max_mesh_vertex_delta_cm': seam_mesh,
               'max_rot_velocity_mismatch_deg_per_frame': vel_seam, 'seam_joint_second_difference_cm_per_frame2': seam_vel_mismatch,
               'note': 'second difference across the seam compared with max_joint_accel_cm_per_frame2 inside the clip'},
 'pops': {'max_local_rot_step_deg_per_frame': float(steps.max()), 'worst_bone': bones[int(np.unravel_index(steps.argmax(), steps.shape)[1])],
          'max_rot_accel_deg_per_frame2': float(acc.max()), 'max_joint_accel_cm_per_frame2': float(accel.max()),
          'worst_accel_bone': bones[int(np.unravel_index(accel.argmax(), accel.shape)[1])]},
 'bone_length': {'max_rel_change_unscaled_bones': float(np.delete(len_dev, [bones.index(b) for b in scaled], axis=1).max()) if len(scaled) < len(bones) else None,
                 'bones_with_intentional_scale': {b: float(len_dev[:, bones.index(b)].max()) for b in scaled}},
 'feet': feet, 'mesh_min_z_cm': float(min(ground_min)) * CM,
 'self_intersection_nonadjacent_tri_pairs': {'sample_frames': sorted(inter), 'by_pair_max': {n: max(v) for n, v in inter_tab.items()},
                                             'by_pair_min': {n: min(v) for n, v in inter_tab.items()},
                                             'frames_with_any': [f for f in sorted(inter) if any(inter[f].values())]},
}
# rest baseline for intersections: mute constraints temporarily
mute = [(c, c.mute) for pb in arm.pose.bones for c in pb.constraints]
for c, _ in mute: c.mute = True
bpy.context.view_layer.update(); rest_int = overlaps(eval_verts())
for c, mu in mute: c.mute = mu
bpy.context.view_layer.update()
rep['self_intersection_nonadjacent_tri_pairs']['bind_pose'] = rest_int
name = globals().get('REPORT', 'audit_idle_v1.json')
(W/'reports'/name).write_text(json.dumps(rep, indent=1))
print(json.dumps(rep))
