"""Flight metrics on the evaluated deform rig + mesh of the open scene (frames F0..F1):
 feet: per leg, min foot-vertex z minus belly (body-region min z), as a fraction of body height (body-region z extent at rest);
 wingtip: angle (deg) of the outermost wing vertex below/above the shoulder in front view (+ up), per side;
 bob: side-view vertical travel (cm) of the chest (Spine_0 head) vs the head (bone_5 tail);
 tail: tail tip z vs hip (Spine_1 head) z (cm); root z (cm). Globals: RANGE, OUT(optional json path)."""
import bpy, json, math
import numpy as np
CM = 2155.818
s = bpy.context.scene; arm = bpy.data.objects['DRAGON_DEFORM']; me = bpy.data.objects['DRAGON_MESH']
F0, F1 = globals().get('RANGE', (0, 60))
m = me.data; gi = {g.index: g.name for g in me.vertex_groups}; nv = len(m.vertices)
Wt = {}
for v in m.vertices:
    for g in v.groups: Wt.setdefault(gi[g.group], np.zeros(nv))[v.index] = g.weight
def wsum(names): return sum((Wt.get(n, np.zeros(nv)) for n in names), np.zeros(nv))
rest = np.array([v.co for v in m.vertices])
bones = [b.name for b in arm.data.bones]
FEET = {'FL': ['tripo::1_Left_Limb_1', 'bone_9'], 'FR': ['tripo::0_Left_Limb_2', 'tripo::0_Left_Limb_3', 'bone_14'],
        'HL': ['tripo::1_Right_Limb_2', 'tripo::1_Right_Limb_3', 'tripo::1_Right_Limb_4'], 'HR': ['tripo::0_Right_Limb_2', 'tripo::0_Right_Limb_3', 'tripo::0_Right_Limb_4']}
foot = {k: np.where((wsum(v) > 0.6) & (rest[:, 2] < 0.03))[0] for k, v in FEET.items()}
wingR = np.where(wsum([b for b in bones if b.startswith('VeyrWingPosZ')]) > 0.5)[0]; wingL = np.where(wsum([b for b in bones if b.startswith('VeyrWingNegZ')]) > 0.5)[0]
neck = wsum(['bone_3', 'bone_4', 'bone_5', 'VeyrJaw']) > 0.5; tail = wsum(['bone_18', 'tripo::Tail_0', 'tripo::Tail_1', 'tripo::Tail_2']) > 0.5
legs = wsum(sum(FEET.values(), []) + ['bone_7', 'tripo::1_Left_Limb_0', 'tripo::0_Left_Limb_0', 'tripo::0_Left_Limb_1', 'tripo::1_Right_Limb_0', 'tripo::1_Right_Limb_1', 'tripo::0_Right_Limb_0', 'tripo::0_Right_Limb_1']) > 0.5
wmask = np.zeros(nv, bool); wmask[wingR] = True; wmask[wingL] = True
body = np.where(~(wmask | neck | tail | legs))[0]
H = float(rest[body, 2].max() - rest[body, 2].min())
def ev():
    dg = bpy.context.evaluated_depsgraph_get(); e = me.evaluated_get(dg); mm = e.to_mesh(); a = np.empty(len(mm.vertices) * 3); mm.vertices.foreach_get('co', a); e.to_mesh_clear()
    return (np.array(me.matrix_world) @ np.c_[a.reshape(-1, 3), np.ones(nv)].T).T[:, :3]
def bw(n, tail_=False):
    pb = arm.pose.bones[n]; return np.array(arm.matrix_world @ (pb.tail if tail_ else pb.head))
out = {'t': [], 'feet': {k: [] for k in FEET}, 'tipR': [], 'tipL': [], 'chestZ': [], 'headZ': [], 'headX': [], 'chestX': [], 'tailZ': [], 'hipZ': [], 'rootZ': [], 'belly': [], 'meshMinZ': []}
for f in range(F0, F1 + 1):
    s.frame_set(f); V = ev(); belly = V[body, 2].min()
    out['t'].append(f); out['belly'].append(round(float(belly) * CM, 1)); out['meshMinZ'].append(round(float(V[:, 2].min()) * CM, 1))
    for k in FEET: out['feet'][k].append(round(float((V[foot[k], 2].min() - belly) / H), 3))
    for side, idx, sh in (('tipR', wingR, 'VeyrWingPosZRoot'), ('tipL', wingL, 'VeyrWingNegZRoot')):
        S_ = bw(sh); lat = np.abs(V[idx, 1] - S_[1]); j = idx[int(lat.argmax())]; d = V[j] - S_
        out[side].append(round(math.degrees(math.atan2(d[2], abs(d[1]))), 1))
    c = bw('tripo::Spine_0'); h = bw('bone_5', True); tt = bw('tripo::Tail_2', True); hp = bw('tripo::Spine_1')
    out['chestZ'].append(round(float(c[2]) * CM, 1)); out['chestX'].append(round(float(c[0]) * CM, 1)); out['headZ'].append(round(float(h[2]) * CM, 1)); out['headX'].append(round(float(h[0]) * CM, 1))
    out['tailZ'].append(round(float(tt[2]) * CM, 1)); out['hipZ'].append(round(float(hp[2]) * CM, 1)); out['rootZ'].append(round(float(bw('tripo::Root')[2]) * CM, 1))
rng = lambda a: round(max(a) - min(a), 1)
summ = {'bodyHeightCm': round(H * CM, 1), 'feetMinFrac': {k: min(v) for k, v in out['feet'].items()}, 'tipMinDeg': [min(out['tipR']), min(out['tipL'])],
        'chestBobCm': rng(out['chestZ']), 'headBobCm': rng(out['headZ']), 'headXrangeCm': rng(out['headX']), 'chestXrangeCm': rng(out['chestX']), 'meshMinZcm': min(out['meshMinZ'])}
if globals().get('OUT'): open(OUT, 'w').write(json.dumps({'summary': summ, 'series': out}))
print('RES', json.dumps(summ if not globals().get('FULL') else {'summary': summ, 'series': out}))
