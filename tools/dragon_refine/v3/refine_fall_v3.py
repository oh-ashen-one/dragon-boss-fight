"""Refine a video2rig dragon FALL (collapse / death): a one-shot that ends lying on the floor, no loop, no trim.
Usage: blender -b --factory-startup <import.blend> --python refine_fall.py -- <out.blend> <report.json> <in_action> <out_action> [key=value ...]
  keys: stand_end=<frame> settle=<frame> release=<frames> ramp=<frames> tail_flat=1|0 wing_lift=1|0 floor=<cm>
Input is never saved over. Steps (each measured before/after):
  0 phases from the Spine_0 height (stand, fall, lying)
  1 wings: lift a wing root about the body's long axis until no wing vertex is under the floor (fit puts the -Y wing 4.8 cm under)
  2 tail: blend to the rest (straight back) pose through the fall, set its pitch so it lies on the floor; local Gaussian on spikes
  3 feet: temporary IK, bake: planted at the frame-0 pose while standing (faded out after the drop starts), planted at the
    lying pose from the settle frame on; the fit's own legs carry the fall in between
  4 verify: nothing outside tail / wing roots / legs changed
"""
import bpy, sys, json, math
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector, Quaternion
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import lib_anim as L

args = sys.argv[sys.argv.index("--") + 1:]
OUT_BLEND, OUT_JSON, IN_ACTION, OUT_ACTION = Path(args[0]), Path(args[1]), args[2], args[3]
opt = dict(a.split("=") for a in args[4:])
SRC = Path(bpy.data.filepath).resolve()
assert OUT_BLEND.resolve() != SRC and not OUT_BLEND.exists(), "refusing to overwrite"
sc = bpy.context.scene
A = bpy.data.objects["Armature"]
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act = A.animation_data.action
assert act.name == IN_ACTION, act.name
f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
N = f1 - f0 + 1
REP = {"source_blend": str(SRC), "n_frames": N}
FRAMES = list(range(N))
ch = L.read_channels(act, FRAMES)
ch0 = {b: {k: v.copy() for k, v in d.items()} for b, d in ch.items()}
bones_q = [b for b in ch if "q" in ch[b]]
S0 = "tripo::Spine_0"
FLOOR = float(opt.get("floor", 0.15)) / 100.0       # target lowest vertex height (m)

def apply():
    L.write_channels(act, ch, N)
    sc.frame_start, sc.frame_end = 0, N - 1
def fix_hemi(q):
    for i in range(1, len(q)):
        if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
    return q
def nlerp(a, b, w):
    w = np.asarray(w).reshape(-1, 1)
    out = (1 - w) * a + w * np.where((a * b).sum(1, keepdims=True) < 0, -b, b)
    return out / np.linalg.norm(out, axis=1, keepdims=True)
def sstep(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)
def gauss(v, sig=2.0, hw=6):
    g = np.exp(-.5 * (np.arange(-hw, hw + 1) / sig) ** 2); g /= g.sum()
    return np.convolve(np.pad(v, hw, mode="edge"), g, mode="valid")
def basis_from(Pmat, pb, Bmat):
    b = pb.bone
    rel = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
    Pm = Pmat if b.parent else Matrix.Identity(4)
    return rel.inverted() @ Pm.inverted() @ Bmat
def eval_pose(f):
    return A.evaluated_get(L.frame_eval(sc, f))

names = {g.index: g.name for g in M.vertex_groups}
dom = np.array([names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else "none" for v in M.data.vertices])
def idx_of(prefixes):
    return np.where(np.array([any(s.startswith(p) for p in prefixes) for s in dom]))[0]
def coords(f, idx):
    return L.mesh_coords(M, sc, [f], idx)[0]
def zmin_groups(frames):
    out = {}
    groups = {"wing_PosZ(-Y)": idx_of(["VeyrWingPosZ"]), "wing_NegZ(+Y)": idx_of(["VeyrWingNegZ"]),
              "tail": idx_of(["tripo::Tail", "bone_18"]),
              "feet": idx_of(["bone_9", "bone_14", "tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4", "tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"]),
              "all": np.arange(len(dom))}
    groups["body+head"] = np.setdiff1d(groups["all"], np.concatenate([groups["wing_PosZ(-Y)"], groups["wing_NegZ(+Y)"], groups["tail"], groups["feet"]]))
    for k, idx in groups.items():
        out[k] = [float(coords(f, idx)[:, 2].min()) * 100 for f in frames]
    return out

# ---------------- 0. phases ----------------
H0_, _, _ = L.world_points(A, FRAMES, sc, bones_head=[S0])
sz = H0_[S0][:, 2] * 100
z0 = float(np.median(sz[:10]))
below = np.where(sz < z0 - 1.0)[0]
fall_start = int(below[0]) if len(below) else N - 1
spd, _ = L.rot_speed(ch0, N)
run = np.convolve(np.pad(spd, 4, mode="edge"), np.ones(9) / 9, mode="valid")
med = float(np.median(spd))
STAND_END = int(opt["stand_end"]) if "stand_end" in opt else fall_start + 2
SETTLE = int(opt["settle"]) if "settle" in opt else next((i for i in range(fall_start + 10, N) if run[i] < 0.45), N - 1)
REL = int(opt.get("release", 10)); RAMP = int(opt.get("ramp", 8))
REP["phases"] = {"spine0_z0_cm": round(z0, 2), "fall_start": fall_start, "stand_full_weight_to": STAND_END,
                 "stand_release_frames": REL, "settle": SETTLE, "lying_ramp_frames": RAMP,
                 "spine0_z_lying_cm": round(float(np.median(sz[SETTLE:])), 2)}
print("PHASES", REP["phases"], flush=True)
REP["zmin_cm_before"] = {k: {"standing_f0_30": round(min(v[:30]), 2), "lying_min": round(min(v[SETTLE:]), 2),
                             "lying_frames_under_-0.3": int(sum(1 for z in v[SETTLE:] if z < -0.3))}
                         for k, v in zmin_groups(FRAMES).items()}
print("ZMIN before", json.dumps(REP["zmin_cm_before"]), flush=True)

# ---------------- 0.5 mirror fold: the -Y (PosZ) wing takes the +Y (NegZ) wing's pose (armature-space axis-angle mirrored) ----------------
if int(opt.get("mirror_fold", 0)):
    ma, mb = int(opt.get("mf_a", 85)), int(opt.get("mf_b", 110))
    wmir = sstep((np.arange(N) - ma) / max(1, mb - ma))
    from mathutils import Quaternion as _Q
    for part in ("Root", "Elbow", "Membrane", "Wrist", "Tip"):
        bn, bp = "VeyrWingNegZ" + part, "VeyrWingPosZ" + part
        Rn = A.pose.bones[bn].bone.matrix_local.to_3x3(); Rp = A.pose.bones[bp].bone.matrix_local.to_3x3()
        qn = ch[bn]["q"]; mq = np.zeros_like(qn)
        for f in FRAMES:
            Q = Rn @ _Q(tuple(qn[f])).to_matrix() @ Rn.inverted()
            ax, ang = Q.to_quaternion().to_axis_angle()
            Qm = _Q(Vector((-ax.x, ax.y, -ax.z)), ang) if ang > 1e-9 else _Q()
            mq[f] = np.array((Rp.inverted() @ Qm.to_matrix() @ Rp).to_quaternion())
        ch[bp]["q"] = fix_hemi(nlerp(ch[bp]["q"], fix_hemi(mq), wmir))
    apply()
    REP["mirror_fold"] = {"frames": [ma, mb], "note": "-Y wing blended to the mirrored +Y wing pose"}
    print("MIRROR", json.dumps(REP["mirror_fold"]), flush=True)

# ---------------- 0.7 sweep: fold the -Y wing back along the flank (Root about the vertical axis) until its lateral reach is `wing_sweep` cm ----------------
if opt.get("wing_sweep"):
    import math as _m
    from mathutils import Quaternion as _Q
    def _qm(a, b):
        return np.array([a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3], a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
                         a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1], a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]])
    def _cj(bone, vec):
        v = Vector(vec); ang = _m.radians(v.length)
        if ang < 1e-9: return np.array([1.0, 0, 0, 0])
        R = A.pose.bones[bone].bone.matrix_local.to_3x3()
        return np.array((R.inverted() @ _Q(v.normalized(), ang).to_matrix() @ R).to_quaternion())
    rb = "VeyrWingPosZRoot"; widx = idx_of(["VeyrWingPosZ"]); sa, sb = int(opt.get("sweep_a", 85)), int(opt.get("sweep_b", 110))
    base = ch[rb]["q"].copy(); fe = N - 1
    def lat_at(deg):
        ch[rb]["q"][fe] = _qm(_cj(rb, [0, 0, deg]), base[fe]); apply(); return float(-coords(fe, widx)[:, 1].min() * 100)
    tgt = float(opt["wing_sweep"]); l0 = lat_at(0.0)
    sg = 1 if lat_at(30) < lat_at(-30) else -1
    lo, hi = 0.0, 75.0
    if lat_at(sg * hi) > tgt: phi = hi * sg
    else:
        for _ in range(8):
            mid = (lo + hi) / 2
            if lat_at(sg * mid) > tgt: lo = mid
            else: hi = mid
        phi = sg * hi
    ramp = sstep((np.arange(N) - sa) / max(1, sb - sa))
    for f in FRAMES: ch[rb]["q"][f] = _qm(_cj(rb, [0, 0, phi * float(ramp[f])]), base[f])
    ch[rb]["q"] = fix_hemi(ch[rb]["q"]); apply()
    REP["wing_sweep"] = {"root_about_vertical_deg": round(float(phi), 1), "frames": [sa, sb], "lateral_cm_before": round(l0, 1), "target_cm": tgt}
    print("SWEEP", json.dumps(REP["wing_sweep"]), flush=True)

# ---------------- 1. wings ----------------
if int(opt.get("wing_lift", 1)):
    wrep = {}
    for root, pref, sign_guess in (("VeyrWingPosZRoot", "VeyrWingPosZ", -1), ("VeyrWingNegZRoot", "VeyrWingNegZ", 1)):
        idx = idx_of([pref])
        co = [coords(f, idx) for f in FRAMES]
        hh = np.array([np.array(eval_pose(f).pose.bones[root].head) for f in FRAMES])
        theta = np.zeros(N)
        for f in FRAMES:
            c, h = co[f], hh[f]
            if c[:, 2].min() >= FLOOR: continue
            for deg in range(0, 61):
                p = math.radians(deg) * sign_guess
                z = h[2] + (c[:, 1] - h[1]) * math.sin(p) + (c[:, 2] - h[2]) * math.cos(p)
                if z.min() >= FLOOR:
                    theta[f] = deg; break
            else:
                theta[f] = 60
            theta[f] = min(theta[f], float(opt.get("wing_lift_cap", 60)))
        # conservative then smooth: running max (+-3) then Gaussian, so the smoothed curve never drops below the need
        mx = np.array([theta[max(0, i - 3):i + 4].max() for i in range(N)])
        ts = np.maximum(gauss(mx, 2.0), theta)
        wrep[root] = {"max_lift_deg": round(float(ts.max()), 2), "frames_lifted": int((ts > 0.05).sum()),
                      "first_frame": int(np.argmax(ts > 0.05)) if (ts > 0.05).any() else None}
        q = ch[root]["q"].copy()
        for f in FRAMES:
            if ts[f] < 0.05: continue
            Ae = eval_pose(f); pbe = Ae.pose.bones[root]
            h = Vector(pbe.head)
            R = Matrix.Translation(h) @ Matrix.Rotation(math.radians(ts[f]) * sign_guess, 4, "X") @ Matrix.Translation(-h)
            Bm = basis_from(pbe.parent.matrix, A.pose.bones[root], R @ pbe.matrix)
            q[f] = np.array(Bm.to_quaternion())
        ch[root]["q"] = fix_hemi(q)
        apply()
    REP["wings"] = wrep
    print("WINGS", json.dumps(wrep), flush=True)

# ---------------- 1a. fold at the elbow (not the root): the -Y wing's remaining floor penetration, solved on the Elbow chain ----------------
if int(opt.get("elbow_fold", 0)):
    import math as _m
    from mathutils import Quaternion as _Q
    def _qmul(a, b):
        return np.array([a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3], a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
                         a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1], a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]])
    def _conj(bone, vec):
        v = Vector(vec); ang = _m.radians(v.length)
        if ang < 1e-9: return np.array([1.0, 0, 0, 0])
        R = A.pose.bones[bone].bone.matrix_local.to_3x3()
        return np.array((R.inverted() @ _Q(v.normalized(), ang).to_matrix() @ R).to_quaternion())
    fold_rep = {}
    for side in ("PosZ", "NegZ"):
        eb = "VeyrWing" + side + "Elbow"; widx = idx_of(["VeyrWing" + side])
        base = ch[eb]["q"].copy(); phi = np.zeros(N); sign = None
        for f in range(fall_start, N):
            if float(coords(f, widx)[:, 2].min()) >= FLOOR: continue
            def lowz(deg):
                ch[eb]["q"][f] = _qmul(_conj(eb, [deg, 0, 0]), base[f]); apply(); return float(coords(f, widx)[:, 2].min())
            if sign is None:
                sign = 1 if lowz(30) > lowz(-30) else -1
            lo, hi = 0.0, 75.0
            if lowz(sign * hi) < FLOOR: phi[f] = hi * sign; continue
            for _ in range(7):
                mid = (lo + hi) / 2
                if lowz(sign * mid) >= FLOOR: hi = mid
                else: lo = mid
            phi[f] = sign * hi
        if np.abs(phi).max() > 0:
            mx = np.array([phi[max(0, i - 3):i + 4][np.argmax(np.abs(phi[max(0, i - 3):i + 4]))] for i in range(N)])
            ph = np.sign(mx) * np.maximum(np.abs(gauss(mx, 2.0)), np.abs(phi))
        else: ph = phi
        for f in FRAMES:
            ch[eb]["q"][f] = _qmul(_conj(eb, [float(ph[f]), 0, 0]), base[f]) if abs(ph[f]) > 1e-3 else base[f]
        ch[eb]["q"] = fix_hemi(ch[eb]["q"]); apply()
        fold_rep[side] = {"elbow_fold_max_deg": round(float(np.abs(ph).max()), 1), "frames": int((np.abs(ph) > 1e-3).sum())}
    REP["elbow_fold"] = fold_rep; print("ELBOWFOLD", json.dumps(fold_rep), flush=True)

# ---------------- 1b. body lift: nothing but the wings may be under the floor once the fall starts ----------------
if int(opt.get("body_lift", 1)):
    nonwing = np.setdiff1d(np.arange(len(dom)), idx_of(["VeyrWing"]))
    need = np.zeros(N)
    for f in range(fall_start, N):
        zm = float(coords(f, nonwing)[:, 2].min())
        need[f] = max(0.0, FLOOR - zm)
    mx = np.array([need[max(0, i - 3):i + 4].max() for i in range(N)])
    lift = np.maximum(gauss(mx, 2.0), need)
    lift[:fall_start] = 0.0
    ql = ch[S0]["l"].copy() if "l" in ch[S0] else None
    assert ql is not None, "Spine_0 has no location channel"
    for f in FRAMES:
        if lift[f] < 1e-5: continue
        Ae = eval_pose(f); pbe = Ae.pose.bones[S0]
        Bm = basis_from(pbe.parent.matrix, A.pose.bones[S0], Matrix.Translation((0, 0, float(lift[f]))) @ pbe.matrix)
        ql[f] = np.array(Bm.to_translation())
    ch[S0]["l"] = ql
    apply()
    REP["body_lift"] = {"max_cm": round(float(lift.max()) * 100, 2), "frames_lifted": int((lift > 1e-5).sum()),
                        "rule": "Spine_0 raised in world Z so the lowest non-wing vertex is at the floor (+0.15 cm)"}
    print("LIFT", json.dumps(REP["body_lift"]), flush=True)

# ---------------- 2. tail ----------------
TAIL = L.TAIL
tail_idx = idx_of(["tripo::Tail"])
def tip_speed():
    _, T, _ = L.world_points(A, FRAMES, sc, bones_tail=["tripo::Tail_2"])
    tt = T["tripo::Tail_2"]
    return np.r_[np.nan, np.linalg.norm(np.diff(tt, axis=0), axis=1) * 100], tt
v_before, tt_before = tip_speed()
trep = {"tip_xyz_cm_lying_before": np.round(tt_before[-1] * 100, 1).tolist()}
if int(opt.get("tail_flat", 1)):
    wT = sstep((np.arange(N) - fall_start) / max(1, SETTLE - fall_start))
    for b in TAIL:
        ident = np.tile(np.array([1.0, 0, 0, 0]), (N, 1))
        ch[b]["q"] = fix_hemi(nlerp(ch0[b]["q"], ident, wT))
    apply()
    # pitch of Tail_0 about the world Y axis through its head so the lying tail rests on the floor
    def tail_zmin(f): return float(coords(f, tail_idx)[:, 2].min())
    lying = list(range(SETTLE, N, 3))
    def zmin_after(deg, f):
        Ae = eval_pose(f); pbe = Ae.pose.bones["tripo::Tail_0"]; h = Vector(pbe.head)
        co = coords(f, tail_idx)
        p = math.radians(deg)
        # rotation about world Y by p: z' = h_z + (x-h_x)(-sin p) + (z-h_z)cos p ; x' similarly
        zz = h[2] - (co[:, 0] - h[0]) * math.sin(p) + (co[:, 2] - h[2]) * math.cos(p)
        return float(zz.min())
    best = []
    for f in lying:
        cand = [(abs(zmin_after(d, f) - FLOOR), d) for d in range(-40, 41, 2)]
        best.append(min(cand)[1])
    pitch = float(np.median(best))
    trep["pitch_deg_about_Y"] = pitch
    q = ch["tripo::Tail_0"]["q"].copy()
    for f in FRAMES:
        a = pitch * wT[f]
        if abs(a) < 0.05: continue
        Ae = eval_pose(f); pbe = Ae.pose.bones["tripo::Tail_0"]; h = Vector(pbe.head)
        R = Matrix.Translation(h) @ Matrix.Rotation(math.radians(a), 4, "Y") @ Matrix.Translation(-h)
        Bm = basis_from(pbe.parent.matrix, A.pose.bones["tripo::Tail_0"], R @ pbe.matrix)
        q[f] = np.array(Bm.to_quaternion())
    ch["tripo::Tail_0"]["q"] = fix_hemi(q)
    apply()
v1, tt1 = tip_speed()
med_v = float(np.nanmedian(v1))
touched, passes = set(), 0
while passes < 6:
    v, _ = tip_speed()
    sp = np.where(v > 4 * med_v)[0]
    if not len(sp): break
    region = sorted({f for s in sp for f in range(s - 4, s + 4) if 0 < f < N - 1})
    touched |= set(region)
    SIG, HW = 2.0, 4
    G = np.exp(-.5 * (np.arange(-HW, HW + 1) / SIG) ** 2); G /= G.sum()
    for b in TAIL:
        qq = ch[b]["q"]; pad = np.pad(qq, ((HW, HW), (0, 0)), mode="edge"); out = qq.copy()
        for f in region:
            acc = sum(g * pad[f + HW + o] for o, g in zip(range(-HW, HW + 1), G)); out[f] = acc / np.linalg.norm(acc)
        ch[b]["q"] = out
    apply(); passes += 1
v_after, tt_after = tip_speed()
trep.update({"tip_xyz_cm_lying_after": np.round(tt_after[-1] * 100, 1).tolist(),
             "tip_peak_cm_per_frame_before": round(float(np.nanmax(v_before)), 3), "tip_peak_frame_before": int(np.nanargmax(v_before)),
             "tip_median_before": round(float(np.nanmedian(v_before)), 3),
             "tip_peak_cm_per_frame_after_flat": round(float(np.nanmax(v1)), 3),
             "spike_rule": "tip speed > 4x median after the flat-tail step", "gauss_passes": passes, "frames_touched": len(touched),
             "tip_peak_cm_per_frame_final": round(float(np.nanmax(v_after)), 3), "tip_peak_frame_final": int(np.nanargmax(v_after)),
             "peak_over_median_before": round(float(np.nanmax(v_before) / np.nanmedian(v_before)), 2),
             "peak_over_median_final": round(float(np.nanmax(v_after) / np.nanmedian(v_after)), 2)})
REP["tail"] = trep
print("TAIL", json.dumps(trep), flush=True)

# ---------------- 2.5 freeze: damp all motion to zero by frame `freeze` and hold ----------------
if "freeze" in opt:
    fz, fr_ = int(opt["freeze"]), int(opt.get("freeze_ramp", 10))
    for b, d in ch.items():
        for k, v in d.items():
            hold = v[fz].copy()
            for f in range(max(0, fz - fr_), N):
                w = 1.0 if f >= fz else float(sstep((f - (fz - fr_)) / fr_))
                if k == "q":
                    q = nlerp(v[f:f + 1], hold[None, :], np.array([w]))[0]; v[f] = q
                else:
                    v[f] = (1 - w) * v[f] + w * hold
        if "q" in d: d["q"] = fix_hemi(d["q"])
    apply(); REP["freeze"] = {"from_frame": fz, "ramp": fr_}
    print("FREEZE", json.dumps(REP["freeze"]), flush=True)

# ---------------- 3. feet ----------------
feet = list(L.FEET)
SIBS = {"bone_9": ["tripo::1_Left_Limb_1"], "bone_14": ["tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"],
        "tripo::1_Right_Limb_4": [], "tripo::0_Right_Limb_4": []}
allsibs = sum(SIBS.values(), [])
mats = feet + allsibs
TF = min(N - 1, SETTLE + 6)                       # frame whose lying foot pose becomes the plant target
_, _, MA = L.world_points(A, [0], sc, mats=mats)
_, _, MC = L.world_points(A, [TF], sc, mats=mats)
def feet_excursion(frames, ref):
    H, T, _ = L.world_points(A, list(frames), sc, bones_head=feet)
    return {L.FOOT_LABEL[b]: round(float(np.linalg.norm(H[b] - H[b][ref - list(frames)[0]], axis=1).max()) * 100, 3) for b in feet}
REP["feet_excursion_before_cm"] = {"standing_0_to_stand_end": feet_excursion(range(0, STAND_END + 1), 0),
                                   "lying_settle_to_end": feet_excursion(range(SETTLE, N), SETTLE)}
print("FEET before", REP["feet_excursion_before_cm"], flush=True)

mw = A.matrix_world.copy()
chain_bones = sum(L.FEET.values(), [])
def bake(targets):
    empties = []
    for b in feet:
        e = bpy.data.objects.new("IKT_" + b.replace(":", "_"), None); sc.collection.objects.link(e)
        Mt = targets[b]
        tail_w = mw @ (Mt @ Vector((0, A.pose.bones[b].bone.length, 0)))
        R = (mw @ Mt).to_quaternion().to_matrix().to_4x4()
        e.matrix_world = Matrix.Translation(tail_w) @ R
        empties.append(e)
        c = A.pose.bones[b].constraints.new("IK")
        c.name = "TMP_PLANT"; c.target = e; c.use_tail = True; c.use_rotation = True
        c.chain_count = len(L.FEET[b]); c.iterations = 500; c.use_stretch = False
    bpy.context.view_layer.update()
    q = {bn: np.zeros((N, 4)) for bn in chain_bones}; l = {bn: np.zeros((N, 3)) for bn in chain_bones}
    sq = {s: np.zeros((N, 4)) for s in allsibs}; sl = {s: np.zeros((N, 3)) for s in allsibs}
    err = {b: 0.0 for b in feet}
    for f in FRAMES:
        Ae = eval_pose(f)
        for bn in chain_bones:
            pbe = Ae.pose.bones[bn]
            Bm = basis_from(pbe.parent.matrix, pbe, pbe.matrix)
            q[bn][f] = np.array(Bm.to_quaternion()); l[bn][f] = np.array(Bm.to_translation())
        for b in feet:
            err[b] = max(err[b], (Ae.pose.bones[b].matrix.to_translation() - targets[b].to_translation()).length)
            for s in SIBS[b]:
                pbs = A.pose.bones[s]
                Pm = targets[pbs.parent.name] if pbs.parent.name in targets else Ae.pose.bones[pbs.parent.name].matrix
                Bm = basis_from(Pm, pbs, targets[s])
                sq[s][f] = np.array(Bm.to_quaternion()); sl[s][f] = np.array(Bm.to_translation())
    for b in feet:
        for c in list(A.pose.bones[b].constraints):
            if c.name == "TMP_PLANT": A.pose.bones[b].constraints.remove(c)
    for e in empties: bpy.data.objects.remove(e, do_unlink=True)
    return q, l, sq, sl, err
tA = {b: MA[b][0].copy() for b in mats}
tC = {b: MC[b][0].copy() for b in mats}
qA, lA, sqA, slA, eA = bake(tA)
qC, lC, sqC, slC, eC = bake(tC)
REP["ik_solver_max_head_error_cm"] = {"stand": {L.FOOT_LABEL[b]: round(e * 100, 4) for b, e in eA.items()},
                                      "lying": {L.FOOT_LABEL[b]: round(e * 100, 4) for b, e in eC.items()}}
# weights
fr = np.arange(N)
wA = 1.0 - sstep((fr - STAND_END) / max(1, REL))             # 1 until stand_end, 0 after the release
wC = sstep((fr - (SETTLE - RAMP)) / max(1, RAMP))             # 0 until settle-ramp, 1 at settle
wA = np.where(fr > SETTLE, 0.0, wA)
sib_all_q = {}
cb = L.channelbag(act)
def mix(base, a, c):
    return nlerp(nlerp(base, a, wA), c, wC)
for bn in chain_bones:
    ch[bn]["q"] = fix_hemi(mix(ch[bn]["q"], qA[bn], qC[bn]))
for s in allsibs:
    base_l = ch[s]["l"] if s in ch and "l" in ch[s] else np.zeros((N, 3))
    base_q = ch[s]["q"] if s in ch and "q" in ch[s] else np.tile(np.array([1.0, 0, 0, 0]), (N, 1))
    ch.setdefault(s, {})
    ch[s]["q"] = fix_hemi(mix(base_q, sqA[s], sqC[s]))
    ch[s]["l"] = (1 - wC)[:, None] * ((1 - wA)[:, None] * base_l + wA[:, None] * slA[s]) + wC[:, None] * slC[s]
    path = f'pose.bones["{s}"].location'
    for i in range(3):
        if cb.fcurves.find(path, index=i) is None:
            fc = cb.fcurves.new(path, index=i); fc.keyframe_points.add(1); fc.keyframe_points[0].interpolation = "LINEAR"
apply()
REP["feet_excursion_after_cm"] = {"standing_0_to_stand_end": feet_excursion(range(0, STAND_END + 1), 0),
                                  "lying_settle_to_end": feet_excursion(range(SETTLE, N), SETTLE)}
print("FEET after", REP["feet_excursion_after_cm"], json.dumps(REP["ik_solver_max_head_error_cm"]), flush=True)
REP["leg_chain_max_rotation_change_deg"] = {L.FOOT_LABEL[b]: round(float(np.degrees(max(L.qang(ch[bn]["q"][f], ch0[bn]["q"][f]) for bn in L.FEET[b] for f in FRAMES))), 2) for b in feet}

# ---------------- 4. verify ----------------
changed = set(TAIL) | set(chain_bones) | set(allsibs) | {"VeyrWingPosZRoot", "VeyrWingNegZRoot"}
fin = L.read_channels(act, FRAMES)
worst, werr = None, 0.0
for b in fin:
    if b in changed or "q" not in fin[b]: continue
    e = max(L.qang(fin[b]["q"][f], ch0[b]["q"][f]) for f in FRAMES)
    if e > werr: werr, worst = e, b
REP["untouched_check"] = {"max_rotation_diff_deg_outside_tail_wing_roots_legs": round(float(np.degrees(werr)), 6), "worst_bone": worst}
if not (opt.get("mirror_fold") or opt.get("elbow_fold") or opt.get("wing_sweep") or "freeze" in opt):
    assert werr < 1e-4, (worst, werr)
REP["zmin_cm_after"] = {k: {"standing_f0_30": round(min(v[:30]), 2), "lying_min": round(min(v[SETTLE:]), 2),
                            "lying_frames_under_-0.3": int(sum(1 for z in v[SETTLE:] if z < -0.3)), "overall_min": round(min(v), 2)}
                        for k, v in zmin_groups(FRAMES).items()}
print("ZMIN after", json.dumps(REP["zmin_cm_after"]), flush=True)
Hs, Ts, _ = L.world_points(A, FRAMES, sc, bones_head=[S0, "bone_5"], bones_tail=["tripo::Tail_2"])
REP["end_pose"] = {"spine0_cm": np.round(Hs[S0][-1] * 100, 1).tolist(), "head_bone5_cm": np.round(Hs["bone_5"][-1] * 100, 1).tolist(),
                   "tail_tip_cm": np.round(Ts["tripo::Tail_2"][-1] * 100, 1).tolist(),
                   "last_second_rot_speed_vs_median": round(float(L.rot_speed({b: {"q": ch[b]["q"][-24:]} for b in bones_q}, 24)[0].mean() / med), 3)}
act.name = OUT_ACTION
sc.frame_start, sc.frame_end = 0, N - 1
sc.render.fps, sc.render.fps_base = 24, 1.0
REP["final"] = {"action": act.name, "frame_range": list(act.frame_range), "fps": 24, "duration_s": round((N - 1) / 24, 3), "cyclic": False}
OUT_JSON.write_text(json.dumps(REP, indent=1))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
print("SAVED", OUT_BLEND, json.dumps(REP["final"]), flush=True)
