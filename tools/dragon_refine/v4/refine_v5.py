"""Fix round 3 (v5): corrections on top of the round-2 (v4) Actions, from Local/dragon-review-20261029/critique-round3.md
("What fix round 3 must do"). Opens the v4 blend, copies its Action to <move>_v5, applies the move's recipe and saves a NEW blend
(never the input). Where a v4 layer has to be undone rather than added to (air_land's pop, bite's hard time warp, roar's
periodic tremor), the recipe re-reads the v3 channels and re-applies the corrected v4 layers; every report says so.
Usage: blender -b --factory-startup <v4.blend> --python refine_v5.py -- <move> <out.blend> <report.json> [key=value ...] [dump=<npz>]
moves: collapse, rise, air_land, roar, bite, land2, air_hover, air_fire_down
"""
import bpy, sys, json, math, os, runpy
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import lib_anim as L
import lib_v4 as V
import lib_v5 as L5
from lib_v4 import S0, WING_BONES, WB, TAIL, NECK_HEAD, LEG_BONES

args = sys.argv[sys.argv.index("--") + 1:]
MOVE, OUT_BLEND, OUT_JSON = args[0], Path(args[1]), Path(args[2])
opt = dict(a.split("=", 1) for a in args[3:])
def O(k, d): return type(d)(opt[k]) if k in opt else d
REPO = Path(os.environ.get("VEYR_REPO", HERE.parent.parent.parent))
DR = REPO / "Local/video2rig/dragon"
STANCE = Path(opt.get("stance", DR / "refine/v3/stance.npz"))
HOVER = Path(opt.get("hover", DR / "refine/v3/stance_hover.npz"))
SRC = Path(bpy.data.filepath).resolve()
assert OUT_BLEND.resolve() != SRC and not OUT_BLEND.exists(), "refusing to overwrite"
OUT_ACTION = MOVE + "_v5"
A = bpy.data.objects.get("Armature") or next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act4 = A.animation_data.action
act = act4.copy(); act.name = OUT_ACTION
A.animation_data.action = act
if act.slots: A.animation_data.action_slot = act.slots[0]
REP = {"move": MOVE, "source_blend": str(SRC), "source_action": act4.name, "out_action": OUT_ACTION, "options": opt}
bpy.data.actions.remove(act4)
clip = V.Clip(A, M, act)
CH4 = {b_: {k_: v_.copy() for k_, v_ in d_.items()} for b_, d_ in clip.ch.items()}   # the input (v4) Action's channels
STP = V.load_pose_npz(STANCE); HOV = V.load_pose_npz(HOVER)
NONWING = [b for b in clip.bones_q() if b not in WING_BONES]
STP_Z = 0.211
KER = [1, 2, 2, 2, 1]
P = 26.0
BOB = 0.04
BEAT = dict(root_bias=-3.0, root_amp=37.0, outer_bias=15.0, outer_amp=35.0, outer_lag=0.06)   # the v4 beat (lib_v4.wing_beat)
MW = A.matrix_world.copy()
REP["armature_matrix_is_identity"] = bool(all(abs(MW[i][j] - (1.0 if i == j else 0.0)) < 1e-6 for i in range(4) for j in range(4)))

# ---------------- shared pieces (as refine_v4) ----------------
_bt = np.load(HERE / "bob_table_K.npz"); _U, _Z = _bt["U"], _bt["Z"]
def bob_shape(u): return np.interp(np.mod(np.asarray(u, float) - 0.05, 1.0), _U, _Z, period=1.0)
def zfun_of(ufun, envfun=lambda t: np.ones_like(t), bob=BOB):
    return lambda t: bob * envfun(np.asarray(t, float)) * bob_shape(ufun(np.asarray(t, float)))
def apply_bob(zf, extra=None, tail_gain=0.2):
    N = clip.N; t = np.arange(N, dtype=float)
    d = np.zeros((N, 3)); d[:, 2] = zf(t)
    if extra is not None: d += extra
    clip.offset_body(d)
    V.tail_follow(clip, zf, gains=tuple(tail_gain * g for g in (-5.0, -7.0, -9.0)), lags=(1, 2, 3))
    return d
def plant_to(T, W, sib_ref=0):
    return clip.plant({b: T[b] for b in L.FEET}, {b: W[b] for b in L.FEET}, sib_ref=sib_ref)
def arm_dz(dz):
    """world vertical offset as an armature-space vector"""
    return MW.inverted().to_3x3() @ Vector((0.0, 0.0, dz))
def floor_lift(frames=None, floor=0.0015, fade_in=0):
    N = clip.N; clip.apply()
    foot_groups = sum(L5.FOOT_GROUPS.values(), [])
    idx = np.where(~np.isin(clip.dom, foot_groups) & ~np.char.startswith(clip.dom.astype(str), "VeyrWing"))[0]
    need = np.zeros(N)
    for f in (range(N) if frames is None else frames): need[f] = max(0.0, floor - float(clip.verts(f, idx)[:, 2].min()))
    mx = np.array([need[max(0, i - 3):i + 4].max() for i in range(N)])
    g = np.exp(-.5 * (np.arange(-6, 7) / 2.0) ** 2); g /= g.sum()
    lift = np.maximum(np.convolve(np.pad(mx, 6, mode="edge"), g, mode="valid"), need)
    if fade_in: lift = lift * V.sstep(np.arange(N) / float(fade_in))       # frame 0 stays exactly the previous clip's last frame
    d = np.zeros((N, 3)); d[:, 2] = lift
    if lift.max() > 1e-5: clip.offset_body(d)
    return float(lift.max())
def tail_floor(frames, bone="bone_18", floor=0.002, fade_in=0):
    """per-frame pitch of the tail root (rest Y axis) that lifts any below-floor tail back onto the floor; smoothed"""
    N = clip.N; clip.apply()
    tix = clip.idx_of(["bone_18", "tripo::Tail_0", "tripo::Tail_1", "tripo::Tail_2"])
    def tz(f, a):
        PR = L5.PoseProbe(clip, f); PR.set({bone: [0.0, a, 0.0]}); z = float(PR.verts(tix)[:, 2].min()); PR.close(); return z
    sgn = None; ang = np.zeros(N)
    for f in frames:
        z0 = tz(f, 0.0)
        if z0 >= floor: continue
        if sgn is None: sgn = 1.0 if tz(f, 10.0) > tz(f, -10.0) else -1.0
        lo, hi = 0.0, 60.0
        if tz(f, sgn * hi) < floor: ang[f] = sgn * hi; continue
        for _ in range(10):
            mid = (lo + hi) / 2
            if tz(f, sgn * mid) < floor: lo = mid
            else: hi = mid
        ang[f] = sgn * hi
    if not np.any(ang): return {"max_deg": 0.0}
    mx = np.array([ang[max(0, i - 3):i + 4][np.argmax(np.abs(ang[max(0, i - 3):i + 4]))] for i in range(N)])
    g = np.exp(-.5 * (np.arange(-6, 7) / 2.5) ** 2); g /= g.sum()
    sm = np.convolve(np.pad(mx, 6, mode="edge"), g, mode="valid")
    sm = np.where(np.abs(sm) >= np.abs(ang), sm, ang)
    if fade_in: sm = sm * V.sstep(np.arange(N) / float(fade_in))
    v = np.zeros((N, 3)); v[:, 1] = sm; clip.add_rot(bone, v); clip.apply()
    return {"max_deg": round(float(np.abs(sm).max()), 1), "frames": [int(np.argmax(np.abs(sm) > 0.1)), int(N - 1 - np.argmax(np.abs(sm[::-1]) > 0.1))]}
def stance_feet_plant(weight=None):
    feet = list(L.FEET); MATS = clip.mats(feet)
    return plant_to({b: [MATS[b][0]] * clip.N for b in feet}, {b: (np.ones(clip.N) if weight is None else weight) for b in feet})
def pin_ends(pose_s, pose_e, Ws, We, bones=None):
    N = clip.N
    for b in (bones or list(clip.ch)):
        d = clip.ch[b]
        if b not in pose_s: continue
        if "q" in d:
            q = d["q"]
            if Ws:
                d0 = V.qmul(V.qinv(q[0]), pose_s[b][0])
                for f in range(min(Ws, N)): q[f] = V.qmul(q[f], V.qpow(d0, 1 - float(V.sstep(f / Ws))))
            if We and pose_e is not None:
                d1 = V.qmul(V.qinv(q[-1]), pose_e[b][0])
                for f in range(max(0, N - We), N): q[f] = V.qmul(q[f], V.qpow(d1, float(V.sstep((f - (N - We)) / max(1, We - 1)))))
            d["q"] = V.fix_hemi(q)
        if "l" in d and pose_s[b][1] is not None:
            l = d["l"]
            if Ws:
                l0 = pose_s[b][1] - l[0]
                for f in range(min(Ws, N)): l[f] = l[f] + l0 * (1 - float(V.sstep(f / Ws)))
            if We and pose_e is not None:
                l1 = pose_e[b][1] - l[-1]
                for f in range(max(0, N - We), N): l[f] = l[f] + l1 * float(V.sstep((f - (N - We)) / max(1, We - 1)))
def wings_from(pose, cyclic=False):
    clip.lowpass(WING_BONES, KER, cyclic=cyclic)
    res = clip.residual(WING_BONES, sigma=6.0)
    for b in WING_BONES:
        base = np.tile(pose[b][0], (clip.N, 1))
        clip.ch[b]["q"] = V.fix_hemi(np.array([V.qmul(res[b][f], base[f]) for f in range(clip.N)]) if b in res else base)
def side_sign(side): return 1.0 if side == "NegZ" else -1.0          # +X rotation raises the NegZ wing, -X the PosZ wing
def body_track():
    clip.apply(); return clip.heads([S0])[S0]
def step_ratio(x, k=3, lo=1e-4):
    """largest per-frame step of a 3D track over the median of its +-k neighbouring steps (critic pop rule in bone space)"""
    s = np.linalg.norm(np.diff(x, axis=0), axis=1); best = (0.0, -1)
    for i in range(len(s)):
        nb = np.r_[s[max(0, i - k):i], s[i + 1:i + 1 + k]]; md = float(np.median(nb))
        best = max(best, (float(s[i] / max(md, lo)), i))
    return {"ratio": round(best[0], 2), "step": best[1], "max_step_cm": round(float(s.max() * 100), 3)}

def finish():
    clip.apply()
    REP["final"] = {"action": act.name, "frames": clip.N, "duration_s": round((clip.N - 1) / 24, 3)}
    if MOVE == "air_hover":                     # loop = frames 0..N-2 (frame N-1 duplicates frame 0)
        act.use_frame_range = True; act.frame_start = 0; act.frame_end = clip.N - 2; act.use_cyclic = True
        clip.sc.frame_end = clip.N - 2
        REP["final"]["loop_frames"] = [0, clip.N - 2]; REP["final"]["note"] = f"frame {clip.N - 1} duplicates frame 0 (kept as a key for interpolation, outside the Action range)"
    act.use_fake_user = True
    OUT_JSON.write_text(json.dumps(REP, indent=1, default=float))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
    print("SAVED", OUT_BLEND, json.dumps(REP["final"]), flush=True)
    if "dump" in opt:                          # CPU measurement dump of the saved Action (same process: one gpu_slot run per step)
        sys.argv = [sys.argv[0], "--", OUT_ACTION, opt["dump"]]
        runpy.run_path(str(HERE / "dump_verts.py"), run_name="__main__")

# =====================================================================================================
def collapse():
    N0 = clip.N
    EX, FA, FL = O("fall_extra", 12), O("fall_a", 52.0), O("fall_len", 34.0)
    Nn = N0 + EX; t = np.arange(Nn, dtype=float)
    sp = 1 - (2.0 * EX / FL) * np.sin(np.pi * np.clip((t - FA) / FL, 0, 1)) ** 2       # slower buckle, impact at full speed
    pos = np.r_[0.0, np.cumsum(sp[:-1])]; pos *= (N0 - 1) / pos[-1]
    clip.resample(pos); N = clip.N
    inv = lambda s: float(np.interp(s, pos, t))
    # lying-pose search on the last frame (fast probe, Action detached): head turned aside and drawn back (the chin stays on the
    # floor), then each wing folded onto its flank, under the back line, behind the jaw and inside the front / 3-4 silhouettes
    from mathutils.kdtree import KDTree
    clip.apply()
    isw = np.char.startswith(clip.dom.astype(str), "VeyrWing"); nw = np.where(~isw)[0]
    headi = clip.idx_of(["VeyrJaw", "bone_5", "bone_4"])
    PR = L5.PoseProbe(clip, N - 1)
    HB = ["bone_3", "bone_4", "bone_5"]
    BACK, ROLL = O("back_search", 0), O("shoulder_roll", 0)
    nwh = np.where(~isw | np.char.endswith(clip.dom.astype(str), "Root"))[0]      # silhouette for the lying search: body + the wing roots (shoulders)
    def head_extra(x):
        ex = {"bone_3": [0.0, x[0], x[1]], "bone_4": [0.0, x[2], x[3]], "bone_5": [0.0, x[4], 0.0]}
        if BACK: ex["tripo::Spine_1"] = [0.0, x[5], 0.0]; ex["bone_18"] = [0.0, -x[5], 0.0]   # hips pitched down onto the floor, tail kept flat
        if ROLL: ex[opt.get("roll_bone", "tripo::Spine_0")] = [roll[0], 0.0, 0.0]                                 # chest rolled level (the fit lies with the +Y shoulder 5 cm high)
        return ex
    feet_all = sum(L5.FOOT_GROUPS.values(), [])
    nf = np.where(~isw & ~np.isin(clip.dom, feet_all + L5.HINDLEGS))[0]       # hind legs are re-planted by IK below
    co0 = PR.verts(); low0 = float(L5.project(co0[nw], "G", "front")[:, 1].max()); zf0 = min(0.002, float(co0[nf, 2].min()))
    def jh(x):
        PR.set(head_extra(x)); co = PR.verts()
        pf = L5.project(co[nwh], "G", "front"); p3 = L5.project(co[nw], "G", "threequarter")
        zh = float(co[headi, 2].min())
        return (float(pf[:, 1].max()) - float(pf[:, 1].min()) + 3000 * max(0.0, 0.003 - zh) + 800 * max(0.0, zh - O("chin_max", 0.035))
                + 2 * max(0.0, O("left3q_min", 190.0) - float(p3[:, 0].min())) + 5000 * max(0.0, zf0 - float(co[nf, 2].min())))
    roll = [0.0]
    if ROLL:                                   # bisection: chest roll that puts the two shoulder (wing-root) joints at the same height
        def sh_dz(a):
            roll[0] = a; PR.set(head_extra([0.0] * 6)); PR.verts(idx=np.arange(1))
            return float(clip.A.pose.bones["VeyrWingNegZRoot"].head[2] - clip.A.pose.bones["VeyrWingPosZRoot"].head[2])
        lo_, hi_ = -40.0, 40.0; flo = sh_dz(lo_)
        for _ in range(14):
            mid = (lo_ + hi_) / 2; fm_ = sh_dz(mid)
            if (fm_ > 0) == (flo > 0): lo_, flo = mid, fm_
            else: hi_ = mid
        roll[0] = O("roll_frac", 0.5) * (lo_ + hi_) / 2; sh_dz(roll[0])
    hx0 = [0.0] * (6 if BACK else 5); j0 = jh(hx0)
    if O("debug_head", 0):
        for k_ in range(len(hx0)):
            for sg_ in (12.0, -12.0):
                x_ = list(hx0); x_[k_] = sg_; PR.set(head_extra(x_)); co_ = PR.verts(); pf_ = L5.project(co_[nw], "G", "front")
                print("DBG", k_, sg_, round(jh(x_), 2), "top", round(float(pf_[:, 1].min()), 1), "low", round(float(pf_[:, 1].max()), 1), "low0", round(low0, 1),
                      "zh", round(float(co_[headi, 2].min()), 4), "zf", round(float(co_[nf, 2].min()), 4), "zf0", round(zf0, 4), flush=True)
    hx, hj, hn = L5.coord_search(jh, hx0, steps=(12.0, 6.0, 3.0), bounds=O("head_bound", 40.0)) if O("head_search", 1) else (np.zeros(len(hx0)), j0, 0)
    PR.set(head_extra(hx)); co = PR.verts()
    ridge = float(co[nw, 2].max()); jaw_x = float(co[headi, 0].max())
    pf_nw = L5.project(co[nw], "G", "front"); top_nw, low_nw = float(pf_nw[:, 1].min()), float(pf_nw[:, 1].max())
    kd = KDTree(len(nw))
    for i, v in enumerate(co[nw]): kd.insert(v, i)
    kd.balance()
    WIDX = {s_: clip.idx_of(["VeyrWing" + s_]) for s_ in V.WSIDES}
    rng = np.random.default_rng(5)
    wsol = {}
    from mathutils import Quaternion
    def vec_of(b_, q_local):
        """armature-rest-axes rotation vector (deg) whose rest_conj is q_local"""
        R3 = clip.A.pose.bones[b_].bone.matrix_local.to_3x3()
        qa = (R3 @ Quaternion([float(v) for v in q_local]).to_matrix() @ R3.inverted()).to_quaternion()
        ax, ang = qa.to_axis_angle(); return [float(v) * math.degrees(ang) for v in ax]
    def compose(v1, v2):
        """rest-axes vector of Q(v2) after Q(v1)"""
        q1 = Quaternion(Vector(v1).normalized(), math.radians(Vector(v1).length)) if Vector(v1).length > 1e-9 else Quaternion()
        q2 = Quaternion(Vector(v2).normalized(), math.radians(Vector(v2).length)) if Vector(v2).length > 1e-9 else Quaternion()
        ax, ang = (q2 @ q1).to_axis_angle(); return [float(v) * math.degrees(ang) for v in ax]
    def mirror_extras(exP):
        """the other wing's fold mirrored through the body's mid-plane (y = 0) in armature space, as extras on this wing's base"""
        PR.set(exP); S = Matrix.Diagonal((1.0, -1.0, 1.0, 1.0)); out = {}
        loc0 = {pt: Vector(clip.A.pose.bones["VeyrWingNegZ" + pt].location) for pt in V.WPARTS}   # pb.matrix also writes a location: restored below
        for pt in V.WPARTS:
            bP, bN = "VeyrWingPosZ" + pt, "VeyrWingNegZ" + pt
            pbP, pbN = clip.A.pose.bones[bP], clip.A.pose.bones[bN]
            AN = S @ (pbP.matrix @ pbP.bone.matrix_local.inverted()) @ S
            pbN.matrix = AN @ pbN.bone.matrix_local; bpy.context.view_layer.update()
            out[bN] = vec_of(bN, V.qmul(np.array(pbN.rotation_quaternion), V.qinv(PR.base[bN])))
        for pt in V.WPARTS: clip.A.pose.bones["VeyrWingNegZ" + pt].location = loc0[pt]
        bpy.context.view_layer.update()
        PR.reset(["VeyrWingPosZ" + pt for pt in V.WPARTS] + ["VeyrWingNegZ" + pt for pt in V.WPARTS])
        return out
    for side in V.WSIDES:
        wi = WIDX[side]; sub = rng.choice(len(wi), min(500, len(wi)), replace=False)
        bn = {"Root": "VeyrWing" + side + "Root", "Elbow": "VeyrWing" + side + "Elbow", "Wrist": "VeyrWing" + side + "Wrist"}
        def wing_extra(x): return {bn["Root"]: [x[0], x[1], x[2]], bn["Elbow"]: [x[3], 0.0, 0.0], bn["Wrist"]: [x[4], 0.0, 0.0]}
        sy = -1.0 if side == "PosZ" else 1.0
        def jterms_ex(ex):
            PR.set(ex); cw = PR.verts(wi)
            pbs = clip.A.pose.bones; el = np.array(pbs["VeyrWing" + side + "Root"].tail); mt = np.array(pbs["VeyrWing" + side + "Membrane"].tail)
            anat = {"elbow_on_flank": 2000 * max(0.0, O("elbow_y_min", 0.13) - sy * el[1]), "fingers_back": 1000 * max(0.0, mt[0] - el[0] + O("fingers_back", 0.03)),
                    "own_side": 2000 * max(0.0, -float((sy * cw[:, 1]).min()) - O("cross_max", 0.03))}
            pf = L5.project(cw, "G", "front"); p3 = L5.project(cw, "G", "threequarter")
            close = float(np.mean([kd.find(cw[k])[2] for k in sub])) * 100
            return {"close": close, "ridge": O("ridge_w", 8000.0) * max(0.0, float(cw[:, 2].max()) - (ridge - O("wing_below_ridge", 0.01))),
                    "clear": 2000 * max(0.0, O("wing_clear", 0.004) - float(cw[:, 2].min())), "jaw": 400 * max(0.0, float(cw[:, 0].max()) - (jaw_x - 0.05)),
                    "forward": 400 * max(0.0, float(cw[:, 0].max()) - O("wing_x_max", 0.36)),
                    "front_top": 3.0 * max(0.0, top_nw + 4 - float(pf[:, 1].min())), "front_low": 1.0 * max(0.0, float(pf[:, 1].max()) - low_nw),
                    "left3q": 1.0 * max(0.0, O("left3q_min", 190.0) - float(p3[:, 0].min())), "lateral": 2000 * max(0.0, float(np.abs(cw[:, 1]).max()) - O("wing_y_max", 0.25)), **anat}
        def rnd_t(t_): return {k_: round(v_, 2) for k_, v_ in t_.items()}
        allb = ["VeyrWing" + side + pt for pt in V.WPARTS]
        x0 = [0.0] * 5; j0w = sum(jterms_ex(wing_extra(x0)).values()); terms0_ = rnd_t(jterms_ex(wing_extra(x0)))
        if side == "NegZ" and "PosZ" in wsol and O("mirror", 1):
            mex = mirror_extras(wsol["PosZ"]["extras"]); PR.reset(allb)
            tm = jterms_ex(mex); PR.reset(allb)
            # small rest-axes trim on top of the mirrored fold (the lying body is not exactly symmetric)
            def ex_of(x):
                ex = dict(mex); ex[bn["Root"]] = compose(mex[bn["Root"]], [x[0], x[1], x[2]])
                ex[bn["Elbow"]] = compose(mex[bn["Elbow"]], [x[3], 0, 0]); ex[bn["Wrist"]] = compose(mex[bn["Wrist"]], [x[4], 0, 0]); return ex
            jm = lambda x: sum(jterms_ex(ex_of(x)).values()) + 0.0005 * float(np.dot(x, x))
            xs_, js_, ns_ = L5.coord_search(jm, [0.0] * 5, steps=(16.0, 8.0, 4.0, 2.0), bounds=O("mirror_trim", 90.0))
            ex_best = ex_of(xs_); terms_ = rnd_t(jterms_ex(ex_best)); PR.reset(allb)
            wsol[side] = {"method": "mirror of PosZ fold + trim", "mirror_terms": rnd_t(tm), "trim_deg": [round(float(v), 1) for v in xs_],
                          "cost_before": round(j0w, 2), "cost_after": round(js_, 2), "terms_before": terms0_, "terms_after": terms_, "evals": ns_,
                          "extras": {k_: [round(float(v), 2) for v in v_] for k_, v_ in ex_best.items()}}
            continue
        jw = lambda x: sum(jterms_ex(wing_extra(x)).values())
        starts = [x0] + ([[-v_ if k in (0, 2, 3, 4) else v_ for k, v_ in enumerate(wsol[o_]["extra_deg"])] for o_ in wsol])
        best = None; ns_ = 0
        for st_ in starts:                   # multi-start: from rest and from the mirror of the other wing's fold
            r_ = L5.coord_search(jw, st_, steps=(32.0, 16.0, 8.0, 4.0, 2.0), bounds=O("wing_bound", 150.0)); ns_ += r_[2]
            if best is None or r_[1] < best[1]: best = r_
        xs_, js_ = best[0], best[1]; terms_ = rnd_t(jterms_ex(wing_extra(xs_)))
        PR.reset(allb)
        wsol[side] = {"extra_deg": [round(float(v), 1) for v in xs_], "cost_before": round(j0w, 2), "cost_after": round(js_, 2), "terms_before": terms0_, "terms_after": terms_, "evals": ns_,
                      "extras": {k_: [float(v) for v in v_] for k_, v_ in wing_extra(xs_).items()}}
    PR.close()
    wa, wb = inv(O("fold_a", 60)), inv(O("fold_b", 84))
    w = V.ramp(N, wa, wb)
    # staggered fold: the hand folds in first (compact wing), then the arm swings down onto the flank
    wE = V.ramp(N, wa, wa + O("fold_hand", 0.6) * (wb - wa)); wR = V.ramp(N, wa + O("fold_arm_lag", 0.3) * (wb - wa), wb)
    for b_, vec in head_extra(hx).items(): clip.add_rot(b_, np.outer(w, vec))
    for side in V.WSIDES:
        for b_, vec in wsol[side]["extras"].items():
            ww = wR if b_.endswith("Root") else wE
            # blend toward the fixed folded rotation (not a delta on the moving source wing, which first swung it up and over)
            q = clip.ch[b_]["q"]; qT = V.qmul(clip.rest_conj(b_, vec), q[-1])
            clip.ch[b_]["q"] = V.fix_hemi(V.nlerp(q, np.tile(qT, (N, 1)), ww))
    clip.apply()
    lift = {"chest_roll_deg": round(roll[0], 2), "head": {"extra_deg": [round(float(v), 1) for v in hx], "front_bbox_px_before": round(j0, 1), "cost_after": round(hj, 1), "evals": hn},
            "ridge_cm": round(ridge * 100, 2), "jaw_x_cm": round(jaw_x * 100, 2), "wings": wsol}
    # feet: soles set down on the floor once lying (the lying pose had them 0.3 to 3.7 cm up), so the get-up starts on four feet
    fl = floor_lift(range(int(wa), N))
    FI = int(round(inv(O("feet_a", 84))))
    fidx = L5.foot_idx(clip); fr = list(range(FI, N))
    low = L5.feet_low(clip, fr, fidx)
    feet = list(L.FEET); MATS = clip.mats(feet)
    T, Wt = {}, {}
    for b in feet:
        T[b] = [None] * N
        for i, f in enumerate(fr):
            Mt = MATS[b][f].copy(); Mt.translation = Mt.translation + arm_dz((O("sole_z", 0.0005) - low[b][i]) if O("feet_bidir", 1) else -max(0.0, low[b][i] - O("sole_z", 0.0005))); T[b][f] = Mt
        Wt[b] = V.ramp(N, FI, FI + O("feet_ease", 10))
    err = plant_to(T, Wt)
    clip.apply()
    lowe = L5.feet_low(clip, [N - 1], fidx)
    co = clip.verts(N - 1); isw = np.char.startswith(clip.dom.astype(str), "VeyrWing")
    REP["collapse"] = {"fall_warp": {"extra_frames": EX, "slow_window_new": [FA, FA + FL], "min_speed": round(float(sp.min()), 3), "frames": N},
                       "lying_pose_search": lift, "settle_frames": [round(wa, 1), round(wb, 1)],
                       "feet_down_from": FI, "ik_err_cm": err, "floor_lift_cm": round(fl * 100, 2),
                       "breath_start_new": round(inv(108), 1), "breath_period": 40,
                       "end_3d": {"top_cm": round(float(co[:, 2].max() * 100), 2), "top_nonwing_cm": round(float(co[~isw, 2].max() * 100), 2),
                                  "wing_top_cm": round(float(co[isw, 2].max() * 100), 2), "wing_min_cm": round(float(co[isw, 2].min() * 100), 2),
                                  "wing_x_max_cm": round(float(co[isw, 0].max() * 100), 2), "nonwing_x_max_cm": round(float(co[~isw, 0].max() * 100), 2),
                                  "feet_low_cm": {L.FOOT_LABEL[b]: round(float(v[0] * 100), 2) for b, v in lowe.items()}},
                       "authored": "slower buckle (time warp), head turned aside and drawn back, wings folded onto the flanks (searched), feet set on the floor", "sourced": "collapse_v4 (fit + v4 breathing)"}

def rise():
    cb = Path(opt.get("collapse_blend", DR / "Dragon_Collapse_sd_v2r_v5.blend"))
    col = V.action_channels(cb, opt.get("collapse_action", "collapse_v5"))
    nc = len(next(iter(col.values()))["q"])
    LY = L5.pose_at(col, nc - 1)
    r3 = V.action_channels(DR / "Dragon_Rise_sd_v2r_v3.blend", "rise_v3"); n3 = len(next(iter(r3.values()))["q"])
    G, HS, H0 = O("getup", 50), O("handover_src", 21), O("hold_src", 11)
    N = G + (n3 - HS)
    idx = np.clip(np.arange(N) - G + HS, H0, n3 - 1)          # rise_v3 still frames 11..21 under the get-up, then rise_v3 from 21
    L5.replace_channels(clip, {b: {k: v[idx].copy() for k, v in d.items()} for b, d in r3.items()})
    clip.ensure_loc(S0); clip.apply()
    feet = list(L.FEET); MS = clip.mats(feet)                 # standing feet (rise_v3, planted)
    t = np.arange(N, dtype=float)
    def wl(a, b): return 1 - V.ramp(N, a, b, V.minjerk)
    HEADG = ["bone_3", "bone_4", "bone_5", "VeyrJaw"]
    FRONT = ["bone_2"] + L5.FORELEGS
    HIND = ["tripo::Spine_1", "bone_18", "tripo::Spine_2", "tripo::Spine_3"] + L5.HINDLEGS + TAIL
    WINGG = WING_BONES + ["tripo::Head_0", "tripo::Head_1", "tripo::Head_2", "tripo::Head_3", "bone_36", "bone_37"]
    sched = {"head": (HEADG, O("head_a", 3), O("head_b", 24)), "front_push": (FRONT, O("front_a", 8), O("front_b", 28)),
             "hind_gather": (HIND, O("hind_a", 20), O("hind_b", 42)), "wings_fold": (WINGG, O("wing_a", 14), O("wing_b", 46))}
    for nm, (bones, a, b) in sched.items():
        clip.blend_to(LY, wl(a, b), bones=[x for x in bones if x in LY])
    rest = [b for b in LY if not any(b in g[0] for g in sched.values()) and b != S0]
    clip.blend_to(LY, wl(O("hind_a", 20), O("hind_b", 42)), bones=rest)
    # Spine_0: rotation with the forelegs' push (chest up first), height with the hind legs' gather
    clip.blend_to(LY, wl(O("front_a", 8), O("front_b", 28)), bones=[S0], loc=False)
    wh = wl(O("lift_a", 16), O("hind_b", 42))
    clip.ch[S0]["l"] = (1 - wh)[:, None] * clip.ch[S0]["l"] + wh[:, None] * LY[S0][1]
    # balance: wings lift a little (raised, not spread over the floor) while the hind legs gather
    o = O("wing_lift_deg", 10.0) * V.sstep((t - 16) / 10.0) * (1 - V.sstep((t - 30) / 12.0))
    for side in V.WSIDES:
        v = np.zeros((N, 3)); v[:, 0] = side_sign(side) * o; clip.add_rot("VeyrWing" + side + "Root", v)
    # the collapse's breathing carries on through the first frames (exact at frame 0, fading as the get-up takes over)
    a_c, PB = O("breath_a", 114.0), 40.0
    tc = (nc - 1) + t
    br = lambda tt: 0.5 - 0.5 * np.cos(2 * np.pi * (tt - a_c) / PB)
    e = 1 - V.sstep(t / O("breath_fade", 24.0))
    dbr = (br(tc) - br(nc - 1)) * e
    # the lying breath ends near the bottom of an exhale (still for a few frames): one deep gathering breath leads into the push
    dbr = dbr + O("inhale", 0.8) * np.sin(np.pi * np.clip(t / O("inhale_frames", 14.0), 0, 1))
    for bone, deg in (("tripo::Spine_1", 2.2), ("tripo::Spine_2", -1.6), ("bone_2", 2.5), ("bone_5", -1.2)):
        v = np.zeros((N, 3)); v[:, 1] = deg * dbr; clip.add_rot(bone, v)
    for side in V.WSIDES:
        v = np.zeros((N, 3)); v[:, 0] = side_sign(side) * 2.0 * dbr; clip.add_rot("VeyrWing" + side + "Root", v)
    v = np.zeros((N, 3)); v[:, 2] = 3.0 * (np.sin(2 * np.pi * (tc - a_c) / 63.0) - math.sin(2 * math.pi * (nc - 1 - a_c) / 63.0)) * e
    clip.add_rot("tripo::Tail_2", v)
    clip.apply()
    d = np.zeros((N, 3)); d[:, 2] = 0.0035 * dbr; clip.offset_body(d)
    # tail: the chest-first push pitches the body about the hips and would swing the lying tail under the floor; the tail
    # root lifts just enough per frame to keep the tail resting on the floor (searched per frame, smoothed)
    tl = tail_floor(range(0, G + 12), floor=0.0, fade_in=O("tail_fade", 6))
    # feet: lying spots (on the floor) -> standing spots, one foot at a time, never more than two in the air
    ML = clip.mats(feet)
    WIN = {"bone_9": (O("s1a", 10), O("s1b", 18)), "bone_14": (O("s2a", 15), O("s2b", 23)),
           "tripo::1_Right_Limb_4": (O("s3a", 27), O("s3b", 35)), "tripo::0_Right_Limb_4": (O("s4a", 32), O("s4b", 40))}
    LIFT = O("step_lift_cm", 2.5) / 100
    T, W = {}, {}
    for b in feet:
        Pa, Pb = ML[b][0], MS[b][G]; a_, b_ = WIN[b]; T[b] = []
        for f in range(N):
            u = float(np.clip((f - a_) / (b_ - a_), 0, 1)); su = float(V.minjerk(u))
            Mt = Pa.to_quaternion().slerp(Pb.to_quaternion(), su).to_matrix().to_4x4()
            tr = Pa.translation.lerp(Pb.translation, su) + arm_dz(LIFT * math.sin(math.pi * u)); Mt.translation = tr
            T[b].append(Mt if f <= G + 8 else None)
        W[b] = V.ramp(N, 0, 3) * (1 - V.ramp(N, G - 2, G + 8))
    err = plant_to(T, W, sib_ref=G)
    if O("debug_rise", 0):
        clip.apply()
        for f in range(0, G + 10, 3):
            co = clip.verts(f); k = int(np.argmin(co[:, 2])); print("DBGR", f, round(float(co[k, 2]) * 100, 1), clip.dom[k], "S0", np.round(np.array(clip.A.pose.bones[S0].head) * 100, 1), flush=True)
    fl = floor_lift(range(0, G + 10), fade_in=O("lift_fade", 8))
    if fl > 1e-4: err = plant_to(T, W, sib_ref=G)
    REP["rise"] = {"frames": N, "getup_frames": G, "rise_v3_from": HS, "base_under_getup": f"rise_v3 frames {H0}..{HS} (still)",
                   "start": f"collapse_v5 last frame ({cb.name})", "schedule": {k: [v[1], v[2]] for k, v in sched.items()},
                   "body_height": [O("lift_a", 16), O("hind_b", 42)], "foot_steps": WIN, "step_lift_cm": LIFT * 100, "ik_err_cm": err,
                   "floor_lift_cm": round(fl * 100, 2), "tail_floor": tl, "breath_carry": {"from_collapse_breath_start": a_c, "fade_frames": O("breath_fade", 24.0)},
                   "authored": "sequenced get-up: head, forelegs push (chest), hind legs gather (hips), wing lift and fold; feet stepped one at a time by IK",
                   "sourced": "collapse_v5 end pose and breathing, rise_v3 from frame 21 (rear-up and drop)"}

def air_land():
    ch3 = V.action_channels(DR / "Dragon_AirLand_sd_v2r_v3.blend", "air_land_v3")
    L5.replace_channels(clip, ch3); clip.ensure_loc(S0)
    N = clip.N; assert N == 145
    C = O("contact", 92)
    clip.lowpass(NONWING + WING_BONES, KER)
    wings_from(HOV)
    pin_ends(HOV, None, 10, 0)
    t = np.arange(N, dtype=float)
    idle = V.action_channels(DR / "Dragon_Idle_v2r_v2.blend", "idle_v2")
    stp = STP
    body = [b for b in NONWING if b not in LEG_BONES]
    clip.blend_to(stp, V.ramp(N, 60, 84), bones=LEG_BONES)
    clip.blend_to(stp, V.ramp(N, 66, C - 2), bones=body)
    k0 = 89 - (N - 1 - (C + 20))
    sidx = np.clip(k0 + (np.arange(N) - (C + 20)), 0, 89)
    seq = {b: (idle[b]["q"][sidx], idle[b]["l"][sidx] if "l" in idle[b] else None) for b in idle if "q" in idle[b]}
    clip.blend_to(seq, V.ramp(N, C + O("seq_a", 12), C + O("seq_b", 30)), bones=NONWING)
    # slam: spine, neck, head and tail go most of the way to the lying pose for a beat, then recover
    LY = L5.pose_at(V.action_channels(Path(opt.get("collapse_blend", DR / "Dragon_Collapse_sd_v2r_v5.blend")), "collapse_v5"), -1)
    SA, SH, SR = O("slam_amt", 0.75), O("slam_hold", 10), O("slam_rise", 18)
    SL = O("slam_lead", 0)                    # the braked feet read as down a few frames before the authored contact C
    ws = SA * V.sstep((t - (C - 1 - SL + (1 if SL else 0))) / 5.0) * (1 - V.sstep((t - (C + 4 + SH)) / SR))
    slam_b = [S0, "tripo::Spine_1", "tripo::Spine_2", "tripo::Spine_3", "bone_18", "bone_2", "bone_3", "bone_4", "bone_5", "VeyrJaw"] + TAIL
    clip.blend_to(LY, ws, bones=[b for b in slam_b if b in LY], loc=False)
    # wings: beats to the last upstroke top at C-12, braking flare opens through the 12 frames before contact and holds,
    # then the wings fold onto the flanks as the body slams
    # last beat tops out at TOP, the wings hold raised (glide) to FS, then the braking flare unfolds them over FS..C-3
    TOP = O("top", C - 12); FS = C - O("flare_len", 12 if "top" not in opt else 10)
    xs = 0.45 * math.acos(O("flare_theta", 0.0)) / math.pi
    fl_u = V.sstep((t - FS) / (C - 3 - FS))
    u = np.where(t <= TOP, t / P, TOP / P + xs * fl_u)
    V.wing_beat(clip, u, np.ones(N), **BEAT)
    fe = O("flare_extra_deg", 10.0) * fl_u * (1 - V.sstep((t - C) / 6.0))   # elbows open wider in the flare
    for side in V.WSIDES:
        v = np.zeros((N, 3)); v[:, 0] = side_sign(side) * fe; clip.add_rot("VeyrWing" + side + "Elbow", v)
    clip.apply()
    clip.blend_to(stp, V.ramp(N, C + 1, C + O("fold_frames", 9)), bones=WING_BONES)
    # slam: the wings slap down onto the flanks (the collapse's folded wings) with the body, held, then lift back to the stance
    wsl = O("wing_slam", 1.0) * V.sstep((t - (C - SL)) / O("wing_slam_in", 4.0)) * (1 - V.sstep((t - (C + 4 + SH)) / SR))
    clip.blend_to(LY, wsl, bones=[b_ for b_ in WING_BONES if b_ in LY], loc=False)
    clip.apply()
    # body height: fitted hover to frame tA, then one continuous authored curve (value and speed continuous at tA):
    # descent with a 10-frame brake before contact, slam below the stance, hold, recovery
    zc = clip.body_z(); z_s = float(STP_Z)
    tA = O("desc_a", 46); BR = O("brake_frames", 12); ACC = O("accel_frames", 14); DROP = O("brake", 0.6)
    s0 = max(0.0, float(zc[tA - 1] - zc[tA]))
    fr = np.arange(tA + 1, C + 1, dtype=float)
    acc = V.sstep((fr - tA) / ACC); brk = 1 - DROP * V.sstep((fr - (C - BR)) / BR)
    Dz = float(zc[tA] - z_s)
    A_ = (s0 * (1 - acc) * brk).sum(); B_ = (acc * brk).sum(); smax = (Dz - A_) / B_
    s = (s0 + (smax - s0) * acc) * brk
    base = np.full(N, np.nan); base[:tA + 1] = zc[:tA + 1]
    base[tA + 1:C + 1] = zc[tA] - np.cumsum(s)
    sc_ = float(s[-1]); depth = O("slam_cm", 7.0) / 100; TS = O("slam_frames", 5)
    for i in range(1, TS + 1): base[C + i] = z_s - depth * float(L5.hermite(i / TS, sc_ * TS / depth))
    H1 = C + TS + SH
    base[C + TS + 1:H1 + 1] = z_s - depth
    for i in range(1, SR + 1): base[H1 + i] = z_s - depth * (1 - float(V.minjerk(i / SR)))
    E = H1 + SR
    dz = np.where(np.isnan(base), 0.0, base - zc)
    dz[E + 1:] = dz[E] * (1 - V.sstep((t[E + 1:] - E) / 6.0))
    zf = zfun_of(lambda tt: tt / P, lambda tt: 1 - V.sstep((tt - 60) / 18.0))
    ex = np.zeros((N, 3)); ex[:, 2] = dz
    apply_bob(zf, extra=ex)
    # the settled end: AL4's last frame (= the idle stance, IoU 0.995), re-pinned below so the chain into idle stays exact
    END0 = L5.pose_at(CH4, N - 1)
    # tail whip after contact: a lift then slap (pitch) and a sideways lash (yaw), lagging down the chain, damped
    tw = {}
    for b, k, lag in (("tripo::Tail_0", 0.5, 0), ("tripo::Tail_1", 0.8, 2), ("tripo::Tail_2", 1.0, 4)):
        tt = t - C - lag; env = V.sstep(tt / 2.0) * np.exp(-np.maximum(tt, 0) / O("whip_tau", 12.0))
        v = np.zeros((N, 3)); v[:, 1] = O("whip_pitch_deg", 18.0) * k * env * np.sin(2 * np.pi * np.maximum(tt, 0) / O("whip_period", 14.0))
        v[:, 2] = O("whip_yaw_deg", 16.0) * k * env * np.sin(2 * np.pi * np.maximum(tt, 0) / O("whip_period", 14.0) + 0.6)
        clip.add_rot(b, v); tw[b] = [k, lag]
    # panting in the end hold (2 breaths, zero at the last frame so the clip still ends on the stance)
    PBr = O("pant_period", 26.0); tb = (N - 1) - 2 * PBr
    pe = V.sstep((t - (E - 6)) / 10.0) * (t >= tb)
    pb = (0.5 - 0.5 * np.cos(2 * np.pi * (t - tb) / PBr)) * pe
    for bone, deg in (("tripo::Spine_1", O("pant_spine_deg", 3.0)), ("tripo::Spine_2", -0.7 * O("pant_spine_deg", 3.0)), ("bone_2", O("pant_neck_deg", 3.5)),
                      ("bone_5", -0.5 * O("pant_neck_deg", 3.5))):
        v = np.zeros((N, 3)); v[:, 1] = deg * pb; clip.add_rot(bone, v)
    for side in V.WSIDES:
        v = np.zeros((N, 3)); v[:, 0] = side_sign(side) * O("pant_wing_deg", 3.0) * pb; clip.add_rot("VeyrWing" + side + "Root", v)
    # the last frames land exactly on the settled stance (the chain into idle; whip residue and rounding removed)
    clip.blend_to(END0, V.ramp(N, N - 1 - O("end_pin", 8), N - 1), bones=list(END0), loc=True)
    clip.apply()
    d = np.zeros((N, 3)); d[:, 2] = O("pant_cm", 0.6) / 100 * pb; clip.offset_body(d)
    tlf = tail_floor(range(C - 4, N - 14), floor=0.0)                     # the slammed, whipping tail rests on the floor, never through it
    # feet: IK eases onto the end stance feet over the frames before contact, planted after
    feet = list(L.FEET); MATS = clip.mats(feet); EZ = O("contact_ease", 6)
    T, W = {}, {}
    for b in feet:
        tg = MATS[b][N - 1]; T[b] = []; W[b] = np.zeros(N)
        for f in range(N):
            if f < C - EZ: T[b].append(None); continue
            s_ = float(V.sstep((f - (C - EZ)) / float(EZ))) if f < C else 1.0
            Mt = MATS[b][f].to_quaternion().slerp(tg.to_quaternion(), s_).to_matrix().to_4x4()
            Mt.translation = MATS[b][f].translation.lerp(tg.translation, s_)
            T[b].append(Mt); W[b][f] = 1.0
    err = plant_to(T, W)
    tr = body_track()
    REP["land"] = {"contact": C, "descent_from": tA, "accel_frames": ACC, "brake_window": [C - BR, C], "brake_speed_drop": DROP,
                   "speed_cm_per_frame": {"at_tA": round(s0 * 100, 3), "max": round(smax * 100, 3), "at_contact": round(sc_ * 100, 3)},
                   "slam": {"amount_to_lying": SA, "depth_cm": depth * 100, "frames_to_bottom": TS, "hold": SH, "rise": SR, "recovered_by": E},
                   "flare": {"top": TOP, "flare_start": FS, "theta": O("flare_theta", 0.0), "elbow_extra_deg": O("flare_extra_deg", 10.0), "fold": [C + 1, C + O("fold_frames", 9)]},
                   "tail_whip": tw, "tail_floor": tlf, "wing_slam": {"amount": O("wing_slam", 1.0), "in_frames": O("wing_slam_in", 4.0)}, "pant": {"period": PBr, "from": tb}, "ik_err_cm": err, "root_step_3d": step_ratio(tr),
                   "fix_of_v4_pop": "v4 zeroed the authored height correction before frame 64 (dz[:a0] = 0): a 10.5 cm one-frame jump; v5 builds one continuous curve from the fit's height and speed at frame tA",
                   "sourced": "air_land_v3 (fit) hover and descent poses to ~66, idle_v2 end frames for the settle, collapse_v5 end pose as the slam target",
                   "authored": "descent speed curve, braking flare, slam + hold + recovery, wing fold, tail whip, end panting, IK contact"}

OPEN = {"Root": [28.0, 0.0, -5.0], "Elbow": [42.0, 0.0, 0.0], "Membrane": [28.0, 0.0, 0.0], "Wrist": [10.0, 0.0, 0.0], "Tip": [0.0, 0.0, 0.0]}
def roar():
    N = clip.N; t = np.arange(N, dtype=float)
    ch3 = V.action_channels(DR / "Dragon_Roar_sd_v2r_v3.blend", "roar_sd_v3")
    for b in ("bone_5", "bone_3", "bone_2"): clip.ch[b]["q"] = ch3[b]["q"][:N].copy()    # v4's periodic head tremor removed
    fa, fb, fin, fout = 44, 84, 26, 30                                                   # v4 timing kept
    env = V.sstep((t - (fa - fin)) / fin) * (1 - V.sstep((t - fb) / fout))
    for b in WING_BONES: clip.ch[b]["q"] = np.tile(STP[b][0], (N, 1))
    base = {b: clip.ch[b]["q"].copy() for b in WING_BONES}
    # flare per wing: root raise rx and sweep rz, elbow unfold e (membrane and wrist follow the elbow, as the v3 OPEN pose)
    prm = {"PosZ": [O("rx_PosZ", 16.8), O("rz_PosZ", 4.2), O("e_PosZ", 35.0), O("w_PosZ", 0.0)], "NegZ": [O("rx_NegZ", 13.8), O("rz_NegZ", -17.2), O("e_NegZ", 48.0), O("w_NegZ", 0.0)]}   # start: v4's
    def vecs(side, x):
        rx, rz, e = x[:3]; w = x[3] if len(x) > 3 else 0.0
        out = {"Root": [rx, 0.0, rz], "Elbow": [e, 0.0, 0.0], "Membrane": [e * 28 / 42, 0.0, 0.0], "Wrist": [e * 10 / 42 + w, 0.0, 0.0], "Tip": [0.5 * w, 0.0, 0.0]}
        return {WB[side][i]: (out[pt] if side == "NegZ" else [-out[pt][0], out[pt][1], -out[pt][2]]) for i, pt in enumerate(V.WPARTS)}
    def set_flare(frames):
        for side in V.WSIDES:
            for b, vec in vecs(side, prm[side]).items():
                for f in frames: clip.ch[b]["q"][f] = V.qmul(clip.rest_conj(b, [x * env[f] for x in vec]), base[b][f])
    # critic's front-view numbers estimated from the vertices (G front projection), as ratios to frame 0:
    # half-span = body centre (median column of rows 330-440) to the wing's outermost column above row 330; height = bbox
    clip.apply()
    widx = {s_: clip.idx_of(["VeyrWing" + s_]) for s_ in V.WSIDES}
    def stats(co):
        p = L5.project(co, "G", "front"); x, y = p[:, 0], p[:, 1]
        band = (y >= 330) & (y < 440); cx = float(np.median(x[band])); low = float(y.max())
        out = {}
        for s_ in V.WSIDES:
            px = p[widx[s_]]; up = px[:, 1] < 330
            half = (cx - float(px[up, 0].min())) if s_ == "PosZ" else (float(px[up, 0].max()) - cx)
            out[s_] = (half, low - float(y.min()), low - float(px[:, 1].min()))     # height = whole silhouette bbox (critic's definition); own wing top
        return out
    st0 = stats(clip.verts(0))
    fm = (fa + fb) // 2
    TGT, HT = O("span_target", 1.12), O("height_target", 1.31)
    HF = [fa + 6, fm, fb - 6]                                                            # hold frames the estimate averages over
    # one shared change of v4's per-wing flare (so the two wings keep v4's matched look): raise, sweep, unfold;
    # then a small per-wing unfold trim so both halves land on the same span
    clip_h0 = (lambda p_: float(p_[:, 1].max() - p_[:, 1].min()))(L5.project(clip.verts(0), "G", "front"))
    P0 = {s_: list(prm[s_]) for s_ in V.WSIDES}
    def both(dx, trim=None):
        ex = {}
        for s_ in V.WSIDES:
            x = [P0[s_][i] + dx[i] for i in range(4)]
            if trim: x[2] += trim[s_]
            ex.update(vecs(s_, x))
        acc = {s_: np.zeros(2) for s_ in V.WSIDES}
        for f_ in HF:
            PR = L5.PoseProbe(clip, f_); PR.set(ex); st = stats(PR.verts()); PR.close()
            for s_ in V.WSIDES: acc[s_] += [st[s_][0] / st0[s_][0], st[s_][1] / clip_h0]
        return {s_: tuple(acc[s_] / len(HF)) for s_ in V.WSIDES}
    def J(dx):
        r = both(dx); h = max(r[s_][1] for s_ in V.WSIDES)
        return sum(100 * abs(r[s_][0] - TGT) for s_ in V.WSIDES) + 100 * max(0.0, HT - h) + 0.0005 * float(np.dot(dx, dx))
    dx, jx, nx = L5.coord_search(J, [O("d_rx", 0.0), O("d_rz", 0.0), O("d_e", 0.0), O("d_w", 0.0)], steps=(8.0, 4.0, 2.0, 1.0), bounds=90.0) if O("search", 1) else (np.zeros(4), 0.0, 0)
    if O("per_side", 0):
        # each wing on its own: same half-span AND the same raised wing-top height (a mirrored silhouette although the two
        # wings' rest poses differ)
        def side_eval(side, x):
            ex = vecs(side, list(x)); acc = np.zeros(2)
            for f_ in HF:
                PR = L5.PoseProbe(clip, f_); PR.set(ex); st = stats(PR.verts()); PR.close()
                acc += [st[side][0] / st0[side][0], st[side][2] / clip_h0]
            return acc / len(HF)
        HW = O("wing_height_target", 1.27); ps = {}
        for s_ in V.WSIDES:
            Js = lambda x, s_=s_: (lambda r_: 100 * abs(r_[0] - O('tgt_' + s_, TGT)) + 100 * abs(r_[1] - O('wht_' + s_, HW)))(side_eval(s_, x)) + 0.0005 * float(np.dot(np.subtract(x, prm[s_]), np.subtract(x, prm[s_])))
            xs, js, ns = L5.coord_search(Js, prm[s_], steps=(8.0, 4.0, 2.0, 1.0), bounds=120.0)
            prm[s_] = [float(v) for v in xs]; ps[s_] = {"cost": round(js, 3), "evals": ns, "estimate": [round(float(v), 3) for v in side_eval(s_, xs)]}
        P0 = {s_: list(prm[s_]) for s_ in V.WSIDES}; dx = np.zeros(4); REP["roar_per_side_search"] = ps
    trim = {s_: 0.0 for s_ in V.WSIDES}
    for s_ in ([] if O("per_side", 0) else V.WSIDES):
        lo, hi = -15.0, 15.0
        for _ in range(9):
            mid = (lo + hi) / 2; trim[s_] = mid; r = both(dx, trim)[s_][0]
            if r > TGT: hi = mid
            else: lo = mid
        trim[s_] = (lo + hi) / 2
    r = both(dx, trim)
    for s_ in V.WSIDES: prm[s_] = [P0[s_][0] + dx[0], P0[s_][1] + dx[1], P0[s_][2] + dx[2] + trim[s_], P0[s_][3] + dx[3]]
    search = {"shared_delta_rx_rz_e": [float(v) for v in dx], "trim_e": trim, "cost": round(jx, 3), "evals": nx,
              "estimate": {s_: {"half_span": round(r[s_][0], 3), "wing_top_height_ratio": round(r[s_][1], 3)} for s_ in V.WSIDES}}
    set_flare(range(N)); clip.apply()
    st = stats(clip.verts(fm))
    REP["flare"] = {"target_half_span": TGT, "height_target": HT, "params_rx_rz_e_deg": prm, "search": search,
                    "estimate_at_hold_mid": {s_: round(st[s_][0] / st0[s_][0], 3) for s_ in V.WSIDES}}
    print("FLARE", json.dumps(REP["flare"]), flush=True)
    # irregular tremor: band-limited noise (no fixed period) on the head and both wing roots, same hold envelope as v4
    hE = V.sstep((t - (fa - 4)) / 6.0) * (1 - V.sstep((t - fb) / 8.0))
    TR, WT, SG = O("tremor_deg", 2.6), O("wing_tremor_deg", 3.2), O("noise_sigma", 1.1)
    seed = O("seed", 3)
    for i, (bone, k) in enumerate((("bone_5", 1.0), ("bone_3", 0.7), ("bone_2", 0.4))):
        v = np.zeros((N, 3)); v[:, 1] = TR * k * hE * L5.smooth_noise(N, SG, seed + i, hp_sigma=6.0)
        v[:, 2] = O("head_yaw_k", 0.3) * TR * k * hE * L5.smooth_noise(N, SG, seed + 10 + i, hp_sigma=6.0); clip.add_rot(bone, v)
    # wings: a shared mirrored component (both wings shiver together, so the halves stay matched) plus a smaller own part
    RHO = O("wing_corr", 0.8)
    sh_x, sh_z = L5.smooth_noise(N, SG, seed + 40, hp_sigma=6.0), L5.smooth_noise(N, SG, seed + 41, hp_sigma=6.0)
    WK = {"PosZ": O("wt_PosZ", 0.68), "NegZ": O("wt_NegZ", 1.35)}                      # per-wing gain: same tip shiver in pixels
    for j, side in enumerate(V.WSIDES):
        own_x, own_z = L5.smooth_noise(N, SG, seed + 20 + j, hp_sigma=6.0), L5.smooth_noise(N, SG, seed + 30 + j, hp_sigma=6.0)
        nx_ = RHO * sh_x + math.sqrt(1 - RHO ** 2) * own_x; nz_ = RHO * sh_z + math.sqrt(1 - RHO ** 2) * own_z
        v = np.zeros((N, 3)); v[:, 0] = side_sign(side) * WK[side] * WT * hE * nx_
        v[:, 2] = side_sign(side) * 0.5 * WK[side] * WT * hE * nz_; clip.add_rot("VeyrWing" + side + "Root", v)
    clip.apply()
    REP["living_hold"] = {"tremor": "gaussian-smoothed white noise (sigma %.2f frames, drift removed at sigma 6), seed %d" % (SG, seed),
                          "head_tremor_deg": TR, "wing_tremor_deg": WT, "kept_from_v4": "breath heave 0.8 cm / 18 frames, tail lash 7 deg / 30 frames, planted feet",
                          "removed_from_v4": "sinusoidal head tremor (periods 2.7 / 3.3 frames) and wing tremor (3.1 / 2.6 frames): the critic's 4-frame buzz"}

def bite():
    ch3 = V.action_channels(DR / "Dragon_Bite_sd_v2r_v3.blend", "bite_v3")
    L5.replace_channels(clip, ch3); clip.ensure_loc(S0)
    N0 = clip.N                                            # 111
    # v4 squeezed source 50-76 into 8 frames with a hard speed switch at frame 50 (the critic's 50-51 twitch);
    # v5: the same 18 frames are removed by a smooth speed hump that starts after the strike peak
    EX = 18.0; WA, WL = O("warp_a", 48.0), O("warp_len", 26.0)
    Nn = int(round(N0 - EX)); t = np.arange(Nn, dtype=float)
    k = 2 * EX / WL
    sp = 1 + k * np.sin(np.pi * np.clip((t - WA) / WL, 0, 1)) ** 2
    pos = np.r_[0.0, np.cumsum(sp[:-1])]; pos *= (N0 - 1) / pos[-1]
    clip.resample(pos); N = clip.N
    he = O("hold_end", 58)
    e = V.sstep((t - 30) / 8.0) * (1 - V.sstep((t - he) / 14.0))
    lean = np.zeros((N, 3)); lean[:, 0] = 0.04 * e; lean[:, 2] = -0.004 * e
    for bone, deg in (("bone_2", 8.0), ("bone_3", 4.0)):
        v = np.zeros((N, 3)); v[:, 1] = deg * e; clip.add_rot(bone, v)
    sh = V.sstep((t - 44) / 3.0) * (1 - V.sstep((t - he + 2) / 4.0))
    v = np.zeros((N, 3)); v[:, 2] = O("worry_deg", 4.0) * sh * np.sin(2 * np.pi * (t - 44) / 6.0); clip.add_rot("bone_5", v)
    # wings: the fit's near wing folds edge-on during the strike (thin hook in the 3/4 view): held nearer the stance fold
    ww = O("wing_hold", 0.7) * V.sstep((t - 34) / 8.0) * (1 - V.sstep((t - 64) / 10.0))
    clip.blend_to(STP, ww, bones=WING_BONES)
    # and half-opened against the forward pitch of the lunge (a threat flare), so the near wing keeps its 3/4 area
    wf = V.sstep((t - 34) / 8.0) * (1 - V.sstep((t - 64) / 10.0))
    for side in V.WSIDES:
        sg = side_sign(side)
        v = np.zeros((N, 3)); v[:, 0] = sg * O("flare_rx", 0.0) * wf; v[:, 2] = sg * O("flare_rz", 0.0) * wf; clip.add_rot("VeyrWing" + side + "Root", v)
        v = np.zeros((N, 3)); v[:, 0] = sg * O("flare_e", 0.0) * wf; clip.add_rot("VeyrWing" + side + "Elbow", v)
    clip.apply(); clip.offset_body(lean)
    err = stance_feet_plant()
    REP["bite"] = {"warp": {"removed_frames": EX, "hump_new_frames": [WA, WA + WL], "peak_speed": round(float(sp.max()), 3), "frames": N},
                   "lean_cm": 4.0, "neck_deg": 8.0, "worry_deg": O("worry_deg", 4.0), "wing_hold_to_stance": O("wing_hold", 0.7), "wing_flare_deg": {"root_rx": O("flare_rx", 0.0), "root_rz": O("flare_rz", 0.0), "elbow": O("flare_e", 0.0)}, "ik_err_cm": err,
                   "note": "re-read bite_v3 and re-applied the v4 layers with a C1 time warp (v4's was piecewise linear)"}

def land2():
    ch3 = V.action_channels(DR / "Dragon_Land2_sd_v2r_v3.blend", "land2_v3")
    L5.replace_channels(clip, ch3); clip.ensure_loc(S0)
    N = clip.N
    dz = np.load(opt["corr_npz"])["dz"]; d = np.zeros((N, 3)); d[:, 2] = dz[:N]; clip.offset_body(d)
    REP["centroid_correction_cm_max"] = round(float(np.abs(dz).max() * 100), 2)
    feet = list(L.FEET); MATS = clip.mats(feet); H = clip.heads(feet)
    T, W, plan = {}, {}, {}
    E = O("ease", 8); VZ = O("foot_vz_cm", 1.4) / 100
    for b in feet:
        z = H[b][:, 2]; z0 = float(z[0]); grounded = z < z0 + 0.003
        air = np.where(~grounded)[0]
        if not len(air): T[b] = [None] * N; W[b] = np.zeros(N); continue
        t0, t1 = int(air[0]) - 1, int(air[-1]) + 1
        Pa, Pb = MATS[b][t0].copy(), MATS[b][min(t1, N - 1)].copy()
        T[b] = []; W[b] = np.ones(N)
        for f in range(N):
            if f <= t0: T[b].append(Pa); continue
            if f >= t1: T[b].append(Pb); continue
            s0 = float(V.sstep((f - t0) / E)); s1 = float(V.sstep((t1 - f) / E))
            Mt = MATS[b][f]
            q = Pa.to_quaternion().slerp(Mt.to_quaternion(), s0); q = Pb.to_quaternion().slerp(q, s1)
            tr = Pb.translation.lerp(Pa.translation.lerp(Mt.translation, s0), s1)
            Mx = q.to_matrix().to_4x4(); Mx.translation = tr; T[b].append(Mx)
        z = np.array([T[b][f].translation.z for f in range(N)])
        zg0, zg1 = float(Pa.translation.z), float(Pb.translation.z)
        for f in range(t0 + 1, t1): z[f] = min(z[f], max(zg0, z[f - 1]) + VZ)
        for f in range(t1 - 1, t0, -1): z[f] = min(z[f], max(zg1, z[f + 1]) + VZ)
        for f in range(t0 + 1, t1): T[b][f].translation.z = float(z[f])
        plan[L.FOOT_LABEL[b]] = [t0, t1]
    err = plant_to(T, W)
    REP["land2"] = {"corr_npz": opt["corr_npz"], "contact_ease_frames": E, "foot_vz_cap_cm_per_frame": VZ * 100, "air_frames_per_foot": plan, "ik_err_cm": err,
                    "note": "v4 recipe re-run on land2_v3 with a third centroid pass (higher apex)"}

def air_hover():
    N = clip.N; assert N == 131, N
    t = np.arange(N, dtype=float); u = t / P
    # deeper downstroke: the stroke bottom goes down by DD degrees at the root (top of the upstroke unchanged), the outer chain follows
    DD, DO = O("down_root_deg", 18.0), O("down_outer_deg", 10.0)
    V.wing_beat(clip, u, np.ones(N), root_bias=-DD / 2, root_amp=DD / 2, outer_bias=-DO / 2, outer_amp=DO / 2, outer_lag=BEAT["outer_lag"])
    clip.apply()
    # tail lag: a second, stronger and later follow of the body bob (periodic in the loop), plus a slow sideways sway
    zf = zfun_of(lambda tt: tt / P)
    G3 = O("tail_gain", 1.0)
    V.tail_follow(clip, zf, gains=tuple(G3 * g for g in (-4.0, -6.0, -8.0)), lags=(2, 4, 6))
    SW = O("tail_sway_deg", 5.0)
    for b, k, lag in (("tripo::Tail_0", 0.4, 0), ("tripo::Tail_1", 0.7, 3), ("tripo::Tail_2", 1.0, 6)):
        v = np.zeros((N, 3)); v[:, 2] = SW * k * np.sin(2 * np.pi * (t - lag) / (N - 1) * 2); clip.add_rot(b, v)
    for b in clip.ch:
        for kk in clip.ch[b]: clip.ch[b][kk][-1] = clip.ch[b][kk][0]
    REP["hover"] = {"downstroke_extra_deg": {"root": DD, "outer": DO}, "tail_follow2": {"gain": G3, "lags": [2, 4, 6]}, "tail_sway_deg": SW,
                    "loop": "Action frame range 0..129 (frame 130 = frame 0)"}

def air_fire_down():
    N = clip.N; assert N == 193
    t = np.arange(N, dtype=float)
    PF = (N - 1) / round((N - 1) / P)
    u = t / PF
    # the wind-up (33-66) pitches the body and sweeps the wings fore-aft, and the stroke reads as a fan: add stroke amplitude there
    WA_, WB_ = O("wind_a", 26.0), O("wind_b", 74.0)
    env = V.sstep((t - WA_) / 8.0) * (1 - V.sstep((t - (WB_ - 8)) / 8.0))
    EXR, EXO = O("wind_root_amp", 16.0), O("wind_outer_amp", 12.0)
    V.wing_beat(clip, u, env, root_bias=0.0, root_amp=EXR, outer_bias=0.0, outer_amp=EXO, outer_lag=BEAT["outer_lag"])
    REP["fire_down"] = {"wind_up_extra_amp_deg": {"root": EXR, "outer": EXO, "window": [WA_, WB_]}, "period": PF}

RECIPES = {"collapse": collapse, "rise": rise, "air_land": air_land, "roar": roar, "bite": bite, "land2": land2,
           "air_hover": air_hover, "air_fire_down": air_fire_down}
RECIPES[MOVE]()
finish()
