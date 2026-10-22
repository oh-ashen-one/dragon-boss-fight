"""Search per-joint wing fold rotations (Root sweep/tilt/roll, Wrist fan+twist, Elbow fan+out-of-plane, Membrane fan)
against geometric targets on the evaluated mesh in the idle crouch: nothing above the back line, joints/wrists inside
body half-width +15%, membrane above the legs (z >= 0.11), not inside the body, no edge tearing (stretch) or crushing."""
import bpy, math, json, random
import numpy as np
from mathutils import Quaternion, Vector
exec(open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/anim_common.py').read())
src = open('/Users/midir/veyr-review-fable-20261021/tools/art/blender/dragon_v1/audit_loco.py').read().split('frames = list(range(F0, F1+1))')[0]
g = {}; exec(src, g)
for t in ad.nla_tracks: t.mute = True
key = bpy.data.objects['DRAGON_MESH'].data.shape_keys
if key.animation_data: key.animation_data.action = None
for kb in key.key_blocks[1:]: kb.value = 0.0
def reset():
    for pb in P: pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.scale=(1,1,1)
    P['C_tripo::Spine_0'].location = local_v('C_tripo::Spine_0', Vector((0,0,-0.0105)))
    P['C_tripo::Spine_0'].rotation_quaternion = local_q('C_tripo::Spine_0', PITCH_UP(-0.7))
    for k_, z in GROUND.items(): P[k_].location = local_v(k_, Vector((0,0,z)))
reset(); bpy.context.view_layer.update()
V0 = g['eval_verts']()
D = bpy.data.objects['DRAGON_DEFORM']
wingw = g['wsum']([b.name for b in D.data.bones if b.name.startswith('VeyrWing')])
SIDE = globals().get('SIDE', 'R'); sg = -1 if SIDE == 'R' else 1
wmask = g['wingR'] if SIDE == 'R' else g['wingL']
widx = np.where(wmask)[0]
body = np.where(wingw < 0.2)[0]
# body envelopes in the crouch: top line z(x) and lateral half-width per (x,z) cell on this side
bx = V0[body]; xb = np.clip(((bx[:,0]+0.6)/0.02).astype(int), 0, 79)
top = np.full(80, -1.0); np.maximum.at(top, xb, bx[:,2])
for i in range(1, 79):
    if top[i] < 0: top[i] = max(top[i-1], top[i+1])
side_b = bx[bx[:,1]*sg > 0]
cx = np.clip(((side_b[:,0]+0.6)/0.015).astype(int), 0, 99); cz = np.clip((side_b[:,2]/0.015).astype(int), 0, 49)
env = np.zeros((100, 50)); np.maximum.at(env, (cx, cz), np.abs(side_b[:,1]))
HALF = 0.193                                   # body half-width +15% (front view ~390 px body)
edges = np.array([e.vertices[:] for e in bpy.data.objects['DRAGON_MESH'].data.edges])
em = wmask[edges[:,0]] & wmask[edges[:,1]]; we = edges[em]
L0 = np.linalg.norm(g['rest'][we[:,0]] - g['rest'][we[:,1]], axis=1); okL = L0 > 1e-5
jb = {n: f'C_VeyrWing{"PosZ" if SIDE=="R" else "NegZ"}{n}' for n in ('Root','Wrist','Elbow','Membrane','Tip')}
def oop_axis(part):
    b = B[jb[part]]; d = (b.tail_local - b.head_local).normalized(); return d.cross(Vector((1, 0, 0))).normalized()
def apply(p):
    reset()
    def q(ax, d): return Quaternion(wing_side_axis(ax, SIDE), math.radians(d))
    P[jb['Root']].rotation_quaternion = local_q(jb['Root'], q((1,0,0), p[2]) @ q((0,1,0), p[1]) @ q((0,0,1), p[0]))
    P[jb['Wrist']].rotation_quaternion = local_q(jb['Wrist'], q((1,0,0), p[3]) @ Quaternion(oop_axis('Wrist') if SIDE=='R' else mirror_axis(oop_axis('Wrist')), math.radians(p[4])))
    P[jb['Elbow']].rotation_quaternion = local_q(jb['Elbow'], q((1,0,0), p[5]) @ Quaternion(oop_axis('Elbow') if SIDE=='R' else mirror_axis(oop_axis('Elbow')), math.radians(p[6])))
    P[jb['Membrane']].rotation_quaternion = local_q(jb['Membrane'], q((1,0,0), p[7]))
    bpy.context.view_layer.update()
def score(p, detail=False):
    apply(p); V = g['eval_verts'](); w = V[widx]
    xi = np.clip(((w[:,0]+0.6)/0.02).astype(int), 0, 79)
    above = np.clip(w[:,2] - (top[xi] - 0.004), 0, None)
    wide = np.clip(np.abs(w[:,1]) - HALF, 0, None)
    low = np.clip(0.11 - w[:,2], 0, None)
    fwd = np.clip(w[:,0] - globals().get('XFRONT', 0.27), 0, None)
    cxi = np.clip(((w[:,0]+0.6)/0.015).astype(int), 0, 99); czi = np.clip((w[:,2]/0.015).astype(int), 0, 49)
    inside = np.clip(env[cxi, czi] + 0.004 - np.abs(w[:,1]), 0, None) * (w[:,1]*sg > 0)
    L = np.linalg.norm(V[we[:,0]] - V[we[:,1]], axis=1)[okL] / L0[okL]
    tear = float((L > 1.6).mean()); crush = float((L < 0.35).mean())
    jw = np.array(D.matrix_world @ D.pose.bones[jb['Root'][2:]].tail)
    s_ = 400*above.mean() + 30*above.max() + 400*wide.mean() + 30*wide.max() + 300*low.mean() + 600*fwd.mean() + 40*fwd.max() + globals().get('W_IN', 3000)*inside.mean() + 30*float((inside > 0).mean()) + globals().get('W_TEAR', 60)*tear + 8*crush \
         + 40*max(0, abs(jw[1]) - HALF) + 40*max(0, jw[2] - (top[int((jw[0]+0.6)/0.02)] - 0.01))
    if detail:
        return {'score': float(s_), 'above_max': float(above.max()), 'above_frac': float((above > 0).mean()), 'wide_max': float(wide.max()), 'low_frac': float((low > 0).mean()), 'fwd_max': float(fwd.max()), 'fwd_frac': float((fwd > 0).mean()),
                'inside_frac': float((inside > 0).mean()), 'tear_frac': tear, 'crush_frac': crush, 'wrist_joint': [round(float(v), 3) for v in jw],
                'wing_y_max': float(np.abs(w[:,1]).max()), 'wing_z': [float(w[:,2].min()), float(w[:,2].max())]}
    return float(s_)
random.seed(int(globals().get('SEED', 1)))
best = list(globals().get('START', [-72, -40, 0, 145, 0, -25, 0, -15])); bs = score(best)
LIM = [(-120, 0), (-80, 20), (-40, 40), (60, 170), (-40, 40), (-80, 20), (-40, 40), (-60, 20)]
step = [12, 10, 10, 15, 10, 12, 10, 10]
for it in range(int(globals().get('ITERS', 160))):
    c = best[:]
    for _ in range(random.choice((1, 1, 2, 3))):
        i = random.randrange(8); c[i] = min(LIM[i][1], max(LIM[i][0], c[i] + random.gauss(0, step[i])))
    sc = score(c)
    if sc < bs: best, bs = c, sc
    if it % 40 == 39: step = [max(2, s_*0.7) for s_ in step]
det = score(best, detail=True)
for t in ad.nla_tracks: t.mute = False
print('RES', json.dumps({'side': SIDE, 'best': [round(v, 1) for v in best], 'detail': det}))
