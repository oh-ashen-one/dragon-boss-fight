"""Locomotion audit on the evaluated deform rig/mesh. Ground in-place convention: planted
vertices must move at -SPEED (rig units/frame) along +X world and not at all in Y.
Globals: ARM, MESH, RANGE, SPEED (u/frame, 0 for turn), YAW_RATE (deg/frame about origin, for turn), REPORT."""
import bpy, json, math
import numpy as np
from mathutils.bvhtree import BVHTree
from pathlib import Path
W = Path('/Users/midir/veyr-review-fable-20261021/Local/Blender/dragon-v1-20261021')
CM = 2155.818
s = bpy.context.scene
arm = bpy.data.objects[globals().get('ARM', 'DRAGON_DEFORM')]; me = bpy.data.objects[globals().get('MESH', 'DRAGON_MESH')]
F0, F1 = globals().get('RANGE', (0, 84)); SPEED = globals().get('SPEED', 0.0); YAWR = math.radians(globals().get('YAW_RATE', 0.0))
LOOP = globals().get('LOOP', True)
LEGACY = {'tripo::Head_0','tripo::Head_1','tripo::Head_2','tripo::Head_3','bone_36','bone_37'}
bones = [b.name for b in arm.data.bones if b.name not in LEGACY]
m = me.data; gi = {g.index: g.name for g in me.vertex_groups}; nv = len(m.vertices)
Wt = {}
for v in m.vertices:
    for g in v.groups: Wt.setdefault(gi[g.group], np.zeros(nv))[v.index] = g.weight
def wsum(names): return sum((Wt.get(n, np.zeros(nv)) for n in names), np.zeros(nv))
rest = np.array([v.co for v in m.vertices])
FEET = {'FL': ['tripo::1_Left_Limb_1','bone_9'], 'FR': ['tripo::0_Left_Limb_2','tripo::0_Left_Limb_3','bone_14'],
        'HL': ['tripo::1_Right_Limb_2','tripo::1_Right_Limb_3','tripo::1_Right_Limb_4'], 'HR': ['tripo::0_Right_Limb_2','tripo::0_Right_Limb_3','tripo::0_Right_Limb_4']}
foot = {k: np.where((wsum(v) > 0.6) & (rest[:,2] < 0.03))[0] for k, v in FEET.items()}
wingR = wsum([b for b in bones if b.startswith('VeyrWingPosZ')]) > 0.5
wingL = wsum([b for b in bones if b.startswith('VeyrWingNegZ')]) > 0.5
neck = wsum(['bone_3','bone_4','bone_5','VeyrJaw']) > 0.5
tail = wsum(['bone_18','tripo::Tail_0','tripo::Tail_1','tripo::Tail_2']) > 0.5
legs = wsum(sum(FEET.values(), []) + ['bone_7','tripo::1_Left_Limb_0','tripo::0_Left_Limb_0','tripo::0_Left_Limb_1','tripo::1_Right_Limb_0','tripo::1_Right_Limb_1','tripo::0_Right_Limb_0','tripo::0_Right_Limb_1']) > 0.5
body = ~(wingR | wingL | neck | tail | legs)
polys = [list(p.vertices) for p in m.polygons]
def region_polys(mask): return [i for i, p in enumerate(polys) if all(mask[j] for j in p)]
REG = {'wingR': region_polys(wingR), 'wingL': region_polys(wingL), 'neck': region_polys(neck), 'body': region_polys(body), 'tail': region_polys(tail), 'legs': region_polys(legs)}
PAIRS = [('wingR','body'),('wingL','body'),('wingR','neck'),('wingL','neck'),('neck','body'),('wingR','wingL'),('tail','body'),('wingR','legs'),('wingL','legs')]
def eval_verts():
    dg = bpy.context.evaluated_depsgraph_get(); ev = me.evaluated_get(dg); mm = ev.to_mesh()
    a = np.empty(len(mm.vertices)*3); mm.vertices.foreach_get('co', a); ev.to_mesh_clear()
    return (np.array(me.matrix_world) @ np.c_[a.reshape(-1,3), np.ones(nv)].T).T[:, :3]
_key = np.round(rest/1e-5).astype(np.int64); _, _rep = np.unique(_key, axis=0, return_inverse=True); _rep = _rep.ravel()
rpolys = [set(_rep[p]) for p in polys]
def overlaps(V):
    trees = {k: BVHTree.FromPolygons(V.tolist(), [polys[i] for i in REG[k]]) for k in REG}
    o = {a+'/'+b: sum(1 for i, j in trees[a].overlap(trees[b]) if not (set(polys[REG[a][i]]) & set(polys[REG[b][j]]))) for a, b in PAIRS}
    for w in ('wingR', 'wingL'):   # membrane self-intersection (welded adjacency)
        o[w+'/self'] = sum(1 for i, j in trees[w].overlap(trees[w]) if i < j and not (rpolys[REG[w][i]] & rpolys[REG[w][j]]))
    return o
frames = list(range(F0, F1+1))
mats, locq, lengths, FV, inter, gmin = [], [], [], {k: [] for k in FEET}, {}, []
finite = True
for f in frames:
    s.frame_set(f)
    M = np.array([np.array(arm.matrix_world @ arm.pose.bones[b].matrix) for b in bones]); finite &= bool(np.isfinite(M).all()); mats.append(M)
    lq = []
    for b in bones:
        pb = arm.pose.bones[b]; lm = pb.matrix if pb.parent is None else pb.parent.matrix.inverted() @ pb.matrix
        q = lm.to_quaternion(); lq.append([q.w, q.x, q.y, q.z])
    locq.append(lq)
    lengths.append([(arm.pose.bones[b].tail - arm.pose.bones[b].head).length for b in bones])
    V = eval_verts(); finite &= bool(np.isfinite(V).all())
    if f == F0: V0 = V
    if f == F1: V1 = V
    for k in FEET: FV[k].append(V[foot[k]])
    gmin.append(float(V[:,2].min()))
    if (f - F0) % 3 == 0: inter[f] = overlaps(V)
mats = np.array(mats); locq = np.array(locq); lengths = np.array(lengths)
rest_len = np.array([arm.data.bones[b].length for b in bones]); dev = np.abs(lengths - rest_len) / rest_len
scaled = [bones[i] for i in np.where(dev.max(0) > 1e-4)[0]]
steps = np.degrees(2*np.arccos(np.abs(np.sum(locq[1:]*locq[:-1], axis=2)).clip(0, 1)))
pos = mats[:, :, :3, 3] * CM; vel = np.diff(pos, axis=0); accel = np.linalg.norm(np.diff(vel, axis=0), axis=2)
CONTACT = 0.0005  # 1.08 cm
feet = {}; down = np.zeros(len(frames), int)
for k in FEET:
    A = np.array(FV[k])                                   # frames x n x 3 (units)
    inc = A[:, :, 2] < CONTACT
    down += inc.any(1)
    # expected ground motion of a planted point between f and f+1
    slips = []; acc = {}
    for i in range(len(frames)-1):
        both = inc[i] & inc[i+1]
        if not both.any(): continue
        p0, p1 = A[i, both], A[i+1, both]
        c, sn = math.cos(-YAWR), math.sin(-YAWR)
        exp = np.c_[p0[:,0]*c - p0[:,1]*sn - SPEED, p0[:,0]*sn + p0[:,1]*c]
        d = (p1[:, :2] - exp) * CM
        slips.append(np.linalg.norm(d, axis=1).max())
    # accumulated slip of each vertex over each continuous contact run
    runmax = 0.
    for j in range(A.shape[1]):
        tot = np.zeros(2)
        for i in range(len(frames)-1):
            if inc[i, j] and inc[i+1, j]:
                p0 = A[i, j]; c, sn = math.cos(-YAWR), math.sin(-YAWR)
                e = np.array([p0[0]*c - p0[1]*sn - SPEED, p0[0]*sn + p0[1]*c])
                tot += (A[i+1, j, :2] - e) * CM; runmax = max(runmax, float(np.linalg.norm(tot)))
            else: tot[:] = 0
    feet[k] = {'contact_frames': int(inc.any(1).sum()), 'max_per_frame_slip_cm': float(max(slips) if slips else 0.),
               'p95_per_frame_slip_cm': float(np.percentile(slips, 95) if slips else 0.), 'max_accumulated_slip_cm': runmax,
               'min_z_cm': float(A[:, :, 2].min()*CM)}
names = list(next(iter(inter.values())).keys())
mute = [(c, c.mute) for pb in arm.pose.bones for c in pb.constraints]
for c, _ in mute: c.mute = True
bpy.context.view_layer.update(); bind_int = overlaps(eval_verts())
for c, mu in mute: c.mute = mu
bpy.context.view_layer.update()
rep = {'frames': [F0, F1], 'fps': s.render.fps, 'finite': finite,
 'loop_seam': ({'max_bone_world_pos_delta_cm': float(np.abs(mats[0][:, :3, 3]-mats[-1][:, :3, 3]).max()*CM),
               'max_bone_local_rot_delta_deg': float(np.degrees(2*np.arccos(np.abs(np.sum(locq[0]*locq[-1], axis=1)).clip(0,1))).max()),
               'max_mesh_vertex_delta_cm': float(np.linalg.norm(V0-V1, axis=1).max()*CM),
               'seam_joint_second_difference_cm_per_frame2': float(np.linalg.norm(vel[0]-vel[-1], axis=1).max())} if LOOP else None),
 'pops': {'max_local_rot_step_deg_per_frame': float(steps.max()), 'worst_bone': bones[int(np.unravel_index(steps.argmax(), steps.shape)[1])],
          'worst_frame': int(frames[np.unravel_index(steps.argmax(), steps.shape)[0]]),
          'top5_bones_deg_per_frame': sorted(((round(float(steps[:, j].max()), 2), bones[j]) for j in range(len(bones))), reverse=True)[:5],
          'max_rot_accel_deg_per_frame2': float(np.abs(np.diff(steps, axis=0)).max()), 'max_joint_accel_cm_per_frame2': float(accel.max()),
          'worst_accel_bone': bones[int(np.unravel_index(accel.argmax(), accel.shape)[1])]},
 'bone_length': {'max_rel_change_unscaled': float(np.delete(dev, [bones.index(b) for b in scaled], axis=1).max()),
                 'intentional_scale': {b: float(dev[:, bones.index(b)].max()) for b in scaled}},
 'feet': feet, 'feet_down_histogram': {int(n): int((down == n).sum()) for n in sorted(set(down.tolist()))},
 'mesh_min_z_cm': float(min(gmin))*CM,
 'self_intersection': {'every': 3, 'max': {n: max(inter[f][n] for f in inter) for n in names},
                       'frames_with_any': [f for f in sorted(inter) if any(inter[f].values())], 'bind_pose': bind_int}}
(W/'reports'/globals().get('REPORT', 'audit_walk.json')).write_text(json.dumps(rep, indent=1))
print('RES', json.dumps(rep))
