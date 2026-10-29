"""Refine round 1 (v3) for a dragon move that stands on its feet: shared stance, retiming, wing flare, jaw, tremor, ballistic arc,
step-aware foot planting. Starts from the RAW import blend (never from v2) and never saves over its input.
Usage: blender -b --factory-startup <import.blend> --python refine_v3.py -- <out.blend> <report.json> <in_action> <out_action> [key=value ...]
keys (all optional):
  stance=<npz>         idle_v2 frame-0 channels (dump_stance.py): re-pose the first Ws and last We frames onto it (offset blend,
                       velocity matched: the move's own motion is added on top of a decaying offset). Ws=12 We=12 (We=0: leave the end)
  trim=1|0             trim a still tail (default 1);  trim_start=auto|<n>  drop the dead frames at the start, keeping 2 before the first move
  warp=a-b:c-d,...     piecewise retiming: source frames a..b become new frames c..d (contiguous, start at 0)
  limit=1.27           clamp the wings to this multiple of the frame-0 lateral extent
  flare=1.255 flare_a= flare_b= flare_in=10 flare_out=12   wing flare to this multiple over frames a..b (flare_wings_v3 OPEN pose, scaled)
  jaw=38 jaw_a= jaw_b= jaw_c= jaw_d=   VeyrJaw opens to this many degrees: closed at a, open at b, held to c, shut at d
  tremor=0.35 tremor_a= tremor_b=      head/chest tremor amplitude in cm at the head, over frames a..b
  ballistic=1          replace the airborne Spine_0 height by a parabola through the take-off and touchdown heights
  floor_lift=1         raise Spine_0 where a non-wing, non-foot vertex is under the floor
  plant=auto|all       feet: auto = per-foot stretches (grounded, slow) planted on the floor, short gaps are steps with a lift arc, long gaps free
  dz=1.5 vthr=0.35 step_lift=3.0 step_max_gap=20   (cm, cm per frame, cm, frames)
  stance_feet=1        the first and last planted stretch use the stance's foot poses
"""
import bpy, sys, json, math
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector, Quaternion
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import lib_anim as L

args = sys.argv[sys.argv.index("--") + 1:]
OUT_BLEND, OUT_JSON, IN_ACTION, OUT_ACTION = Path(args[0]), Path(args[1]), args[2], args[3]
opt = dict(a.split("=", 1) for a in args[4:])
def O(k, d): return type(d)(opt[k]) if k in opt else d
SRC = Path(bpy.data.filepath).resolve()
assert OUT_BLEND.resolve() != SRC and not OUT_BLEND.exists(), "refusing to overwrite"
sc = bpy.context.scene
A = bpy.data.objects["Armature"]
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act = A.animation_data.action
assert act.name == IN_ACTION, act.name
f_a, f_b = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
NF0 = f_b - f_a + 1
REP = {"source_blend": str(SRC), "n_frames_source": NF0, "options": opt}
S0 = "tripo::Spine_0"
FLOOR = 0.15 / 100
DZ = O("dz", 1.5) / 100; VTHR = O("vthr", 0.35) / 100; STEP_LIFT = O("step_lift", 3.0) / 100; STEP_GAP = O("step_max_gap", 20)

# ---------------- helpers ----------------
def qmul(a, b):
    return np.array([a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3], a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
                     a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1], a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]])
def qinv(a): return np.array([a[0], -a[1], -a[2], -a[3]]) / float(np.dot(a, a))
def qpow(d, w):
    d = d / np.linalg.norm(d)
    if d[0] < 0: d = -d
    ang = 2 * math.acos(min(1.0, d[0])); s = math.sqrt(max(0.0, 1 - d[0] ** 2))
    if s < 1e-9: return np.array([1.0, 0, 0, 0])
    ax = d[1:] / s; h = ang * w / 2
    return np.array([math.cos(h), *(ax * math.sin(h))])
def nlerp(a, b, w):
    w = np.asarray(w).reshape(-1, 1)
    out = (1 - w) * a + w * np.where((a * b).sum(1, keepdims=True) < 0, -b, b)
    return out / np.linalg.norm(out, axis=1, keepdims=True)
def fix_hemi(q):
    for i in range(1, len(q)):
        if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
    return q
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
def eval_pose(f): return A.evaluated_get(L.frame_eval(sc, f))
names = {g.index: g.name for g in M.vertex_groups}
dom = np.array([names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else "none" for v in M.data.vertices])
def idx_of(prefixes): return np.where(np.array([any(s.startswith(p) for p in prefixes) for s in dom]))[0]
def coords(f, idx): return L.mesh_coords(M, sc, [f], idx)[0]
FOOT_GROUPS = ["bone_9", "bone_14", "tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4", "tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4",
               "tripo::1_Left_Limb_1", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"]
foot_idx = np.where(np.isin(dom, FOOT_GROUPS))[0]
wing_idx = idx_of(["VeyrWing"]); nonwing_nonfoot = np.setdiff1d(np.arange(len(dom)), np.concatenate([wing_idx, foot_idx]))
WING = {"PosZ": (idx_of(["VeyrWingPosZ"]), -1), "NegZ": (idx_of(["VeyrWingNegZ"]), 1)}
WBONES = {s: ["VeyrWing" + s + p for p in ("Root", "Elbow", "Membrane", "Wrist", "Tip")] for s in WING}
def lateral(f, side):
    idx, sg = WING[side]; y = coords(f, idx)[:, 1]
    return float((y.max() if sg > 0 else -y.min()) * 100)
def rest_conj(bone, vec_deg):
    """quaternion of R_rest^-1 Q(vec) R_rest, vec = armature-space axis-angle in degrees"""
    v = Vector(vec_deg); ang = math.radians(v.length)
    if ang < 1e-9: return np.array([1.0, 0, 0, 0])
    R = A.pose.bones[bone].bone.matrix_local.to_3x3()
    return np.array((R.inverted() @ Quaternion(v.normalized(), ang).to_matrix() @ R).to_quaternion())

# ---------------- 0. read ----------------
ch = L.read_channels(act, list(range(NF0)))
bones_q = [b for b in ch if "q" in ch[b]]
def apply():
    L.write_channels(act, ch, N)
    sc.frame_start, sc.frame_end = 0, N - 1
N = NF0
spd, _ = L.rot_speed(ch, NF0)
med0 = float(np.median(spd))
run = np.convolve(np.pad(spd, 4, mode="edge"), np.ones(9) / 9, mode="valid")
live = [i for i in range(len(run)) if run[i] >= 0.4 * med0]
# ---------------- 1. trim ----------------
s0 = 0
ts = opt.get("trim_start", "0")
if ts == "auto": s0 = max(0, live[0] - 2)
elif int(ts) > 0: s0 = int(ts)
s1 = NF0 - 1
if O("trim", 1): s1 = min(NF0 - 1, live[-1] + 1)
for b in ch:
    for k in ch[b]: ch[b][k] = ch[b][k][s0:s1 + 1].copy()
N = s1 - s0 + 1
REP["trim"] = {"start_dropped": s0, "end_kept_source_frame": s1, "frames": N, "median_step_rad": round(med0, 4)}
# ---------------- 2. retime ----------------
if "warp" in opt:
    segs = []
    for part in opt["warp"].split(","):
        a, b = part.split(":"); sa, sb = map(float, a.split("-")); na, nb = map(float, b.split("-")); segs.append((sa, sb, na, nb))
    Nn = int(segs[-1][3]) + 1
    srcpos = np.zeros(Nn)
    for f in range(Nn):
        for sa, sb, na, nb in segs:
            if na - 1e-9 <= f <= nb + 1e-9:
                srcpos[f] = sa + (sb - sa) * (f - na) / max(1e-9, nb - na); break
    i0 = np.clip(np.floor(srcpos).astype(int), 0, N - 1); i1 = np.clip(i0 + 1, 0, N - 1); w = srcpos - np.floor(srcpos)
    for b, d in ch.items():
        for k, v in list(d.items()):
            if k == "q": d[k] = fix_hemi(nlerp(v[i0], v[i1], w))
            else: d[k] = (1 - w)[:, None] * v[i0] + w[:, None] * v[i1]
    REP["warp"] = {"spec": opt["warp"], "frames_before": N, "frames_after": Nn}
    N = Nn
bones_q = [b for b in ch if "q" in ch[b]]
apply()
FRAMES = list(range(N))
spd1, _ = L.rot_speed(ch, N); med1 = float(np.median(spd1))
# raw geometry (before any change): which frames each foot is on the floor, and when the body is airborne
feet = list(L.FEET)
Hraw, _, _ = L.world_points(A, FRAMES, sc, bones_head=feet)
FLOORZ = None
if "floor_feet_npz" in opt:
    _ff = np.load(opt["floor_feet_npz"]); FLOORZ = {b: float(_ff["feet"][i, 0, 2]) for i, b in enumerate(feet)}
zraw0 = FLOORZ if FLOORZ else {b: float(Hraw[b][0, 2]) for b in feet}
def raw_mask(b):
    dz = Hraw[b][:, 2] - zraw0[b]
    m = dz < DZ
    v = np.r_[0, np.linalg.norm(np.diff(Hraw[b][:, :2], axis=0), axis=1)]; v = np.maximum(v, np.r_[v[1:], 0])
    return (m & (v < VTHR)) if O("speed_gate", 1) else m
RAW_MASKS = {b: raw_mask(b) for b in feet}
RAW_AIR = np.all([(Hraw[b][:, 2] - zraw0[b]) > 2 * DZ for b in feet], axis=0)
# ---------------- 3. stance ----------------
stq = stl = None
if "stance" in opt:
    st = np.load(opt["stance"], allow_pickle=True)
    stq = {str(b): q for b, q in zip(st["bones"], st["q"])}; stl = {str(b): l for b, l in zip(st["bones"], st["l"])}
    if "stance_end" in opt:
        se = np.load(opt["stance_end"], allow_pickle=True)
        stq_e = {str(b): q for b, q in zip(se["bones"], se["q"])}; stl_e = {str(b): l for b, l in zip(se["bones"], se["l"])}
    else: stq_e, stl_e = stq, stl
    Ws, We = O("Ws", 12), O("We", 12)
    pre = {b: {k: v.copy() for k, v in d.items()} for b, d in ch.items()}
    def pose_dist_to_stance(f):
        return float(sum(L.qang(ch[b]["q"][f], (stq if f < N // 2 else stq_e)[b]) for b in bones_q if b in stq))
    REP["stance"] = {"pose_dist_start_before_rad": round(pose_dist_to_stance(0), 3), "pose_dist_end_before_rad": round(pose_dist_to_stance(N - 1), 3), "Ws": Ws, "We": We}
    for b, d in ch.items():
        if b not in stq: continue
        if "q" in d:
            q = d["q"]; d0 = qmul(qinv(q[0]), stq[b]); d1 = qmul(qinv(q[-1]), stq_e[b])
            for f in range(min(Ws, N)):
                q[f] = qmul(q[f], qpow(d0, 1 - float(sstep(f / Ws))))
            if We > 0 and opt.get("end_mode", "offset") == "crossfade":
                for f in range(max(0, N - We), N):
                    w = float(sstep((f - (N - We)) / max(1, We - 1)))
                    q[f] = nlerp(q[f:f + 1], stq_e[b][None, :], np.array([w]))[0]
            elif We > 0:
                for f in range(max(0, N - We), N):
                    q[f] = qmul(q[f], qpow(d1, float(sstep((f - (N - We)) / max(1, We - 1)))))
            d["q"] = fix_hemi(q)
        if "l" in d:
            l = d["l"]; l0 = stl[b] - l[0]; l1 = stl_e[b] - l[-1]
            for f in range(min(Ws, N)): l[f] = l[f] + l0 * (1 - float(sstep(f / Ws)))
            if We > 0 and opt.get("end_mode", "offset") == "crossfade":
                for f in range(max(0, N - We), N):
                    w = float(sstep((f - (N - We)) / max(1, We - 1))); l[f] = (1 - w) * l[f] + w * stl_e[b]
            elif We > 0:
                for f in range(max(0, N - We), N): l[f] = l[f] + l1 * float(sstep((f - (N - We)) / max(1, We - 1)))
    apply()
    spd2, _ = L.rot_speed(ch, N)
    REP["stance"].update({"pose_dist_start_after_rad": round(pose_dist_to_stance(0), 6), "pose_dist_end_after_rad": round(pose_dist_to_stance(N - 1), 6) if We > 0 else None,
                          "peak_step_in_start_window_over_median": round(float(spd2[:Ws].max() / med1), 2),
                          "peak_step_in_end_window_over_median": round(float(spd2[max(0, N - We - 1):].max() / med1), 2) if We > 0 else None,
                          "whole_clip_peak_over_median": round(float(spd2.max() / med1), 2)})
    print("STANCE", json.dumps(REP["stance"]), flush=True)

if O("masks_after_stance", 0):
    Hraw, _, _ = L.world_points(A, FRAMES, sc, bones_head=feet)
    RAW_MASKS = {b: raw_mask(b) for b in feet}
    RAW_AIR = np.all([(Hraw[b][:, 2] - zraw0[b]) > 2 * DZ for b in feet], axis=0)
    REP["masks_after_stance"] = True

# ---------------- 3b. pin the root height (air_fire_down: hold the hover root Z; the body pitch stays) ----------------
if O("pin_root_z", 0):
    Hp, _, _ = L.world_points(A, FRAMES, sc, bones_head=[S0]); zp = Hp[S0][:, 2]; z0 = float(zp[0])
    qlp = ch[S0]["l"].copy()
    for f in FRAMES:
        d = z0 - float(zp[f])
        if abs(d) < 1e-6: continue
        Ae = eval_pose(f); pbe = Ae.pose.bones[S0]
        Bm = basis_from(pbe.parent.matrix, A.pose.bones[S0], Matrix.Translation((0, 0, d)) @ pbe.matrix)
        qlp[f] = np.array(Bm.to_translation())
    ch[S0]["l"] = qlp; apply()
    REP["pin_root_z"] = {"hover_z_cm": round(z0 * 100, 2), "z_range_before_cm": [round(float(zp.min()) * 100, 2), round(float(zp.max()) * 100, 2)]}
    print("PIN", json.dumps(REP["pin_root_z"]), flush=True)
# ---------------- 4. wings: clamp ----------------
lat0 = {s: lateral(0, s) for s in WING}
def laterals(frames): return {s: np.array([lateral(f, s) for f in frames]) for s in WING}
lat_before = laterals(FRAMES)
LIMIT = O("limit", 1.27)
wrep = {}
for side, bl in WBONES.items():
    cap = (O("limit_abs_cm", 0.0) if "limit_abs_cm" in opt else LIMIT * lat0[side])
    over = [f for f in FRAMES if lat_before[side][f] > cap]
    if not over: wrep[side] = {"frames_over": 0}; continue
    q0 = {b: ch[b]["q"][0].copy() for b in bl}; qs = {b: ch[b]["q"].copy() for b in bl}
    s_arr = np.ones(N)
    def set_s(f, s):
        for b in bl: ch[b]["q"][f] = nlerp(q0[b][None, :], qs[b][f][None, :], np.array([s]))[0]
    for f in over:
        lo, hi = 0.0, 1.0
        for _ in range(7):
            mid = (lo + hi) / 2; set_s(f, mid); apply()
            if lateral(f, side) > cap: hi = mid
            else: lo = mid
        s_arr[f] = lo
    mn = np.array([s_arr[max(0, i - 3):i + 4].min() for i in range(N)]); sm = np.minimum(gauss(mn, 2.0), s_arr)
    for f in FRAMES: set_s(f, float(sm[f]))
    for b in bl: ch[b]["q"] = fix_hemi(ch[b]["q"])
    apply(); wrep[side] = {"frames_over": len(over), "min_scale": round(float(sm.min()), 3)}
REP["wings_clamp"] = wrep
# ---------------- 5. wings: flare ----------------
OPEN = {"Root": [28.0, 0.0, -5.0], "Elbow": [42.0, 0.0, 0.0], "Membrane": [28.0, 0.0, 0.0], "Wrist": [10.0, 0.0, 0.0], "Tip": [0.0, 0.0, 0.0]}
if "flare" in opt:
    target = O("flare", 1.255); fa, fb = O("flare_a", 40), O("flare_b", 85); fin, fout = O("flare_in", 10), O("flare_out", 12)
    env = sstep((np.arange(N) - (fa - fin)) / fin) * (1 - sstep((np.arange(N) - fb) / fout))
    base = {b: ch[b]["q"].copy() for s in WBONES for b in WBONES[s]}
    if O("flare_base", "fit") == "stance" and stq is not None:       # authored flare on the stance wings (the fit's own wing motion is a few percent)
        base = {b: np.tile(stq[b], (N, 1)) for b in base}
    dxs = {"PosZ": 0.0, "NegZ": 0.0}
    def set_flare(smaxes, frames):
        for side, bl in WBONES.items():
            smax = smaxes[side]
            for part, b in zip(OPEN, bl):
                v = list(OPEN[part])
                if part == "Root": v[0] += dxs[side]
                vec = [x * smax for x in v] if side == "NegZ" else [-v[0] * smax, v[1] * smax, -v[2] * smax]
                for f in frames:
                    vv = [x * env[f] for x in vec]
                    ch[b]["q"][f] = qmul(rest_conj(b, vv), base[b][f])
    fm = (fa + fb) // 2
    smax_cap = O("flare_max", 0.85)
    sm_ = {}
    for side in WING:                                   # the body's roll in the clip tilts one wing: find the Root offset that opens this side most
        best = (-1, 0.0)
        for dx in (-24, -16, -8, 0, 8, 16, 24):
            dxs[side] = float(dx); set_flare({"PosZ": 0.8, "NegZ": 0.8}, [fm]); apply()
            best = max(best, (lateral(fm, side), float(dx)))
        dxs[side] = best[1]
        lo, hi = 0.0, smax_cap
        for _ in range(9):
            mid = (lo + hi) / 2; set_flare({"PosZ": mid, "NegZ": mid}, [fm]); apply()
            if lateral(fm, side) / lat0[side] > target: hi = mid
            else: lo = mid
        sm_[side] = lo
    set_flare(sm_, FRAMES)
    for s in WBONES:
        for b in WBONES[s]: ch[b]["q"] = fix_hemi(ch[b]["q"])
    apply()
    latf = laterals(FRAMES)
    REP["flare"] = {"root_x_offset_deg": dict(dxs), "scale_of_OPEN": {k: round(v, 3) for k, v in sm_.items()}, "target": target, "window": [fa, fb], "peak_lateral_over_frame0": {s: round(float(latf[s].max() / lat0[s]), 3) for s in WING},
                    "span_tip_to_tip_cm_peak": round(float(max(latf["PosZ"] + latf["NegZ"])), 1), "span_frame0_cm": round(lat0["PosZ"] + lat0["NegZ"], 1)}
    print("FLARE", json.dumps(REP["flare"]), flush=True)
# ---------------- 6. jaw ----------------
if "jaw" in opt:
    deg = O("jaw", 38.0); ja, jb, jc, jd = O("jaw_a", 14), O("jaw_b", 34), O("jaw_c", 42), O("jaw_d", 46)
    f = np.arange(N)
    J = sstep((f - ja) / max(1, jb - ja)) * (1 - sstep((f - jc) / max(1, jd - jc)))
    jidx = np.where(dom == "VeyrJaw")[0]
    base = ch["VeyrJaw"]["q"].copy()
    hinge = np.array(A.pose.bones["VeyrJaw"].head)
    def jaw_tip_z(sign, fm):
        ch["VeyrJaw"]["q"][fm] = qmul(rest_conj("VeyrJaw", [0, sign * deg, 0]), base[fm]); apply()
        co = coords(fm, jidx); return float(co[:, 2].min())
    fm = int((jb + jc) // 2)
    zp, zn = jaw_tip_z(1, fm), jaw_tip_z(-1, fm)
    sign = 1 if zp < zn else -1
    for ff in FRAMES:
        ch["VeyrJaw"]["q"][ff] = qmul(rest_conj("VeyrJaw", [0, sign * deg * float(J[ff]), 0]), base[ff])
    ch["VeyrJaw"]["q"] = fix_hemi(ch["VeyrJaw"]["q"]); apply()
    REP["jaw"] = {"deg": deg, "sign": sign, "open_by": jb, "hold_to": jc, "shut_by": jd, "tip_z_cm_at_hold_pos_vs_neg": [round(zp * 100, 2), round(zn * 100, 2)]}
# ---------------- 7. tremor ----------------
if "tremor" in opt:
    amp = O("tremor", 0.35) / 30.0                         # radians at a head 30 cm from the pivot
    ta, tb = O("tremor_a", 46), O("tremor_b", 85)
    f = np.arange(N); env = sstep((f - ta) / 6.0) * (1 - sstep((f - tb) / 6.0))
    rng = np.random.default_rng(3)
    for bone, k in (("bone_5", 1.0), ("bone_3", 0.6), ("bone_2", 0.4)):
        ph = rng.uniform(0, 6.28)
        for ff in FRAMES:
            ang = math.degrees(amp * k * env[ff] * math.sin(2 * math.pi * ff / 2.7 + ph))
            if abs(ang) > 1e-4: ch[bone]["q"][ff] = qmul(rest_conj(bone, [0, ang, 0]), ch[bone]["q"][ff])
        ch[bone]["q"] = fix_hemi(ch[bone]["q"])
    apply(); REP["tremor"] = {"amplitude_cm_at_head": O("tremor", 0.35), "frames": [ta, tb], "period_frames": 2.7}

# ---------------- 8. feet: heights and masks on the geometry so far ----------------
feet = list(L.FEET)
SIBS = {"bone_9": ["tripo::1_Left_Limb_1"], "bone_14": ["tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"], "tripo::1_Right_Limb_4": [], "tripo::0_Right_Limb_4": []}
allsibs = sum(SIBS.values(), [])
H, _, MATS = L.world_points(A, FRAMES, sc, bones_head=feet + [S0], mats=feet + allsibs)
zst = FLOORZ if FLOORZ else {b: float(H[b][0, 2]) for b in feet}                 # foot-bone head height at the stance (on the floor)
def grounded_mask(b, speed_gate=True):
    dz = H[b][:, 2] - zst[b]
    m = dz < DZ
    if speed_gate:
        v = np.r_[0, np.linalg.norm(np.diff(H[b][:, :2], axis=0), axis=1)]
        v = np.maximum(v, np.r_[v[1:], 0])
        m &= v < VTHR
    return m
MASKS = RAW_MASKS
air_all = RAW_AIR
# ---------------- 9. ballistic arc ----------------
if O("ballistic", 0):
    runs, i = [], 0
    while i < N:
        if air_all[i]:
            j = i
            while j + 1 < N and air_all[j + 1]: j += 1
            runs.append((i, j)); i = j + 1
        else: i += 1
    i, j = max(runs, key=lambda r: r[1] - r[0])
    fa, fb = max(0, i - 1), min(N - 1, j + 1)
    z = H[S0][:, 2].copy()
    u = (np.arange(N) - fa) / float(fb - fa)
    lin = z[fa] + (z[fb] - z[fa]) * u
    Hh = float((z[fa:fb + 1] - lin[fa:fb + 1]).max())
    zb = z.copy(); zb[fa:fb + 1] = lin[fa:fb + 1] + 4 * Hh * u[fa:fb + 1] * (1 - u[fa:fb + 1])
    d = zb - z
    ql = ch[S0]["l"].copy()
    for f in range(fa, fb + 1):
        if abs(d[f]) < 1e-6: continue
        Ae = eval_pose(f); pbe = Ae.pose.bones[S0]
        Bm = basis_from(pbe.parent.matrix, A.pose.bones[S0], Matrix.Translation((0, 0, float(d[f]))) @ pbe.matrix)
        ql[f] = np.array(Bm.to_translation())
    ch[S0]["l"] = ql; apply()
    vz = np.diff(z) * 24 / 100; vzb = np.diff(zb) * 24 / 100
    REP["ballistic"] = {"takeoff_frame": fa, "touchdown_frame": fb, "airtime_frames": fb - fa, "apex_excess_cm": round(Hh * 100, 2), "apex_frame_orig": int(np.argmax(z[fa:fb + 1]) + fa),
                        "apex_frame_arc": int((fa + fb) / 2), "peak_z_cm": round(float(zb.max() * 100), 1),
                        "max_vertical_speed_change_per_frame_before_m_s": round(float(np.abs(np.diff(vz[fa:fb])).max()), 3),
                        "max_vertical_speed_change_per_frame_after_m_s": round(float(np.abs(np.diff(vzb[fa:fb])).max()), 3)}
    print("BALLISTIC", json.dumps(REP["ballistic"]), flush=True)
    H, _, MATS = L.world_points(A, FRAMES, sc, bones_head=feet + [S0], mats=feet + allsibs)
# ---------------- 10. floor lift (non-wing, non-foot) ----------------
if O("floor_lift", 0):
    need = np.array([max(0.0, FLOOR - float(coords(f, nonwing_nonfoot)[:, 2].min())) for f in FRAMES])
    mx = np.array([need[max(0, i - 3):i + 4].max() for i in range(N)]); lift = np.maximum(gauss(mx, 2.0), need)
    ql = ch[S0]["l"].copy()
    for f in FRAMES:
        if lift[f] < 1e-5: continue
        Ae = eval_pose(f); pbe = Ae.pose.bones[S0]
        Bm = basis_from(pbe.parent.matrix, A.pose.bones[S0], Matrix.Translation((0, 0, float(lift[f]))) @ pbe.matrix)
        ql[f] = np.array(Bm.to_translation())
    ch[S0]["l"] = ql; apply()
    REP["body_lift"] = {"max_cm": round(float(lift.max()) * 100, 2), "frames": int((lift > 1e-5).sum()), "note": "non-wing, non-foot vertices only; the feet are put on the floor by IK"}
    print("LIFT", json.dumps(REP["body_lift"]), flush=True)
# ---------------- 11. tail ----------------
TAIL = L.TAIL
def tip_speed():
    _, T, _ = L.world_points(A, FRAMES, sc, bones_tail=["tripo::Tail_2"])
    tt = T["tripo::Tail_2"]; return np.r_[np.nan, np.linalg.norm(np.diff(tt, axis=0), axis=1) * 100]
v_before = tip_speed(); med_v = float(np.nanmedian(v_before)); passes = 0; touched = set()
while passes < 8:
    v = tip_speed(); sp = np.where(v > 3 * med_v)[0]
    if not len(sp): break
    region = sorted({f for s in sp for f in range(s - 5, s + 5) if 0 < f < N - 1}); touched |= set(region)
    G = np.exp(-.5 * (np.arange(-4, 5) / 2.0) ** 2); G /= G.sum()
    for b in TAIL:
        qq = ch[b]["q"]; pad = np.pad(qq, ((4, 4), (0, 0)), mode="edge"); out = qq.copy()
        for f in region:
            acc = sum(g * pad[f + 4 + o] for o, g in zip(range(-4, 5), G)); out[f] = acc / np.linalg.norm(acc)
        ch[b]["q"] = out
    apply(); passes += 1
v_after = tip_speed()
REP["tail"] = {"tip_peak_before": round(float(np.nanmax(v_before)), 3), "tip_peak_after": round(float(np.nanmax(v_after)), 3), "passes": passes}
# ---------------- 12. feet: step-aware planting ----------------
PLANT_NONE = opt.get("plant", "auto") == "none"
H, _, MATS = L.world_points(A, FRAMES, sc, bones_head=feet + [S0], mats=feet + allsibs)
mw = A.matrix_world.copy()
stance_feet = O("stance_feet", 1)
def mat_np(m): return np.array(m)
def slerp_m(Ma, Mb, t):
    qa, qb = Ma.to_quaternion(), Mb.to_quaternion(); q = qa.slerp(qb, t)
    out = q.to_matrix().to_4x4(); out.translation = Ma.translation.lerp(Mb.translation, t); return out
targets = {b: [None] * N for b in feet}; weights = {b: np.zeros(N) for b in feet}; plan = {}
for b in feet:
    if opt.get("plant", "auto") == "all": m = np.ones(N, bool)
    elif PLANT_NONE: m = np.zeros(N, bool)
    elif "touch" in opt:
        m = np.zeros(N, bool); m[int(opt["touch"]):] = True
    else: m = MASKS[b]
    # stretches of >= 3 frames
    stretches, i = [], 0
    while i < N:
        if m[i]:
            j = i
            while j + 1 < N and m[j + 1]: j += 1
            if j - i + 1 >= 3 or i == 0 or j == N - 1: stretches.append([i, j])
            i = j + 1
        else: i += 1
    # merge stretches separated by gaps that are not a real step (foot stays within 1.5 cm of both ends' positions and low)
    merged = []
    for s in stretches:
        if merged and s[0] - merged[-1][1] - 1 <= 2: merged[-1][1] = s[1]
        else: merged.append(s)
    stretches = merged
    pose_at = lambda f: MATS[b][f].copy()
    tg = []
    for k, (i, j) in enumerate(stretches):
        mid = (i + j) // 2
        Mt = pose_at(mid)
        if stance_feet and stq is not None and ((i == 0) or (j == N - 1)):
            Mt = pose_at(0 if i == 0 else N - 1)
        Mt = Mt.copy()
        t = Mt.translation.copy(); t.z = (FLOORZ[b] if FLOORZ else MATS[b][0].translation.z)      # on the floor: the stance foot height
        Mt.translation = t
        tg.append(Mt)
        for f in range(i, j + 1): targets[b][f] = Mt; weights[b][f] = 1.0
    steps, free = [], []
    for k in range(len(stretches) - 1):
        ga, gb = stretches[k][1] + 1, stretches[k + 1][0] - 1
        if gb < ga: continue
        gap = gb - ga + 1
        if gap <= STEP_GAP:
            steps.append([ga, gb])
            for f in range(ga, gb + 1):
                u = (f - (ga - 1)) / float(gap + 1); su = float(sstep(u))
                Mt = slerp_m(tg[k], tg[k + 1], su); t = Mt.translation.copy()
                disp = float((tg[k].translation - tg[k + 1].translation).to_2d().length)
                t.z += STEP_LIFT * min(1.0, disp / 0.04) * math.sin(math.pi * u); Mt.translation = t
                targets[b][f] = Mt; weights[b][f] = 1.0
        else: free.append([ga, gb])
    if stretches and stretches[0][0] > 0: free.append([0, stretches[0][0] - 1])
    if stretches and stretches[-1][1] < N - 1: free.append([stretches[-1][1] + 1, N - 1])
    if not stretches: free.append([0, N - 1])
    plan[L.FOOT_LABEL[b]] = {"stretches": stretches, "steps": steps, "free": free}
REP["foot_plan"] = plan
print("PLAN", json.dumps(plan), flush=True)
if "legs_hold_from" in opt:                      # the fit's legs thrash on a deep landing: hold the descent pose until the IK takes over
    hf = int(opt["legs_hold_from"])
    for bn in sum(L.FEET.values(), []) + allsibs:
        if bn in ch and "q" in ch[bn]:
            ch[bn]["q"][hf:] = ch[bn]["q"][hf]
    apply(); REP["legs_hold_from"] = hf
RAMP = int(O("plant_ramp", 0))
if RAMP:
    for b in feet:
        w = weights[b]; on = np.where(w > 0.5)[0]
        if len(on):
            i0 = int(on[0])
            for f in range(max(0, i0 - RAMP), i0): w[f] = max(w[f], float(sstep((f - (i0 - RAMP)) / float(RAMP))))
# soften the weight edges next to free frames
for b in feet:
    w = weights[b]; sm = np.clip(gauss(w, 1.2, 4), 0, 1); weights[b] = np.where(w > 0.5, 1.0, sm)      # planted frames stay 1; free edges ease in
chain_bones = sum(L.FEET.values(), [])
rel_sib = {}
for b in feet:
    for s in SIBS[b]:
        rel_sib[s] = (b, MATS[b][0].inverted() @ MATS[s][0])
empties = {}
for b in feet:
    e = bpy.data.objects.new("IKT_" + b.replace(":", "_"), None); sc.collection.objects.link(e); empties[b] = e
    c = A.pose.bones[b].constraints.new("IK")
    c.name = "TMP_PLANT"; c.target = e; c.use_tail = True; c.use_rotation = True
    c.chain_count = len(L.FEET[b]); c.iterations = 500; c.use_stretch = False
q = {bn: np.zeros((N, 4)) for bn in chain_bones}
sq = {s: np.zeros((N, 4)) for s in allsibs}; sl = {s: np.zeros((N, 3)) for s in allsibs}
err = {b: 0.0 for b in feet}
for f in FRAMES:
    for b in feet:
        Mt = targets[b][f] if targets[b][f] is not None else MATS[b][f]
        tail_w = mw @ (Mt @ Vector((0, A.pose.bones[b].bone.length, 0)))
        R = (mw @ Mt).to_quaternion().to_matrix().to_4x4()
        empties[b].matrix_world = Matrix.Translation(tail_w) @ R
    bpy.context.view_layer.update()
    Ae = eval_pose(f)
    for bn in chain_bones:
        pbe = Ae.pose.bones[bn]; Bm = basis_from(pbe.parent.matrix, pbe, pbe.matrix); q[bn][f] = np.array(Bm.to_quaternion())
    for b in feet:
        Mt = targets[b][f] if targets[b][f] is not None else MATS[b][f]
        if weights[b][f] > 0.99: err[b] = max(err[b], (Ae.pose.bones[b].matrix.to_translation() - Mt.translation).length)
        tmat = {b: Mt}
        for s in SIBS[b]:
            tmat[s] = Mt @ rel_sib[s][1]
        for s in SIBS[b]:
            pbs = A.pose.bones[s]
            Pm = tmat[pbs.parent.name] if pbs.parent.name in tmat else Ae.pose.bones[pbs.parent.name].matrix
            Bm = basis_from(Pm, pbs, tmat[s]); sq[s][f] = np.array(Bm.to_quaternion()); sl[s][f] = np.array(Bm.to_translation())
for b in feet:
    for c in list(A.pose.bones[b].constraints):
        if c.name == "TMP_PLANT": A.pose.bones[b].constraints.remove(c)
for e in empties.values(): bpy.data.objects.remove(e, do_unlink=True)
foot_of = {bn: b for b in feet for bn in L.FEET[b]}
cb = L.channelbag(act)
for bn in chain_bones:
    w = weights[foot_of[bn]]; ch[bn]["q"] = fix_hemi(nlerp(ch[bn]["q"], fix_hemi(q[bn]), w))
for b in feet:
    for s in SIBS[b]:
        w = weights[b]
        base_l = ch[s]["l"] if s in ch and "l" in ch[s] else np.zeros((N, 3))
        base_q = ch[s]["q"] if s in ch and "q" in ch[s] else np.tile(np.array([1.0, 0, 0, 0]), (N, 1))
        ch.setdefault(s, {}); ch[s]["q"] = fix_hemi(nlerp(base_q, fix_hemi(sq[s]), w)); ch[s]["l"] = (1 - w)[:, None] * base_l + w[:, None] * sl[s]
        path = f'pose.bones["{s}"].location'
        for i in range(3):
            if cb.fcurves.find(path, index=i) is None:
                fc = cb.fcurves.new(path, index=i); fc.keyframe_points.add(1); fc.keyframe_points[0].interpolation = "LINEAR"
apply()
Hn, _, _ = L.world_points(A, FRAMES, sc, bones_head=feet + [S0])
REP["ik_max_head_error_cm_on_planted_frames"] = {L.FOOT_LABEL[b]: round(err[b] * 100, 4) for b in feet}
REP["foot_z_above_stance_cm"] = {L.FOOT_LABEL[b]: {"min": round(float((Hn[b][:, 2] - zst[b]).min() * 100), 2), "max": round(float((Hn[b][:, 2] - zst[b]).max() * 100), 2)} for b in feet}
steps_lift = {}
for lab, pl in plan.items():
    b = next(x for x in feet if L.FOOT_LABEL[x] == lab)
    for (ga, gb) in pl["steps"]:
        steps_lift[f"{lab} {ga}-{gb}"] = round(float((Hn[b][ga:gb + 1, 2] - zst[b]).max() * 100), 2)
REP["step_lift_cm_measured"] = steps_lift
sp = Hn[S0][:, 2] * 100
REP["spine0_z_cm"] = {"frame0": round(float(sp[0]), 2), "min": round(float(sp.min()), 2), "max": round(float(sp.max()), 2), "last": round(float(sp[-1]), 2)}
act.name = OUT_ACTION
sc.frame_start, sc.frame_end = 0, N - 1; sc.render.fps, sc.render.fps_base = 24, 1.0
REP["final"] = {"action": act.name, "frames": N, "duration_s": round((N - 1) / 24, 3)}
latF = laterals(FRAMES)
REP["wing_lateral_over_frame0_final"] = {s: round(float(latF[s].max() / lat0[s]), 3) for s in WING}
spdF, _ = L.rot_speed(ch, N)
# 4-frame pulsation depth of the pose speed (moving steps only)
mov = spdF > np.percentile(spdF, 40)
ph = [float(np.median(spdF[(np.arange(len(spdF)) % 4 == k) & mov])) for k in range(4)] if mov.sum() > 8 else [1, 1, 1, 1]
REP["pulsation_mod4_depth_pct"] = round(100 * (max(ph) - min(ph)) / float(np.mean(ph)), 1)
OUT_JSON.write_text(json.dumps(REP, indent=1))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
print("SAVED", OUT_BLEND, json.dumps(REP["final"]), "pulsation", REP["pulsation_mod4_depth_pct"], flush=True)
