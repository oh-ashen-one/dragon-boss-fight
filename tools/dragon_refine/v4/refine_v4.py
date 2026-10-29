"""Fix round 2 (v4): corrections on top of the round-1 (v3) Actions, from Local/dragon-review-20261029/critique-round2.md.
Opens the v3 blend, copies its Action to <move>_v4, applies the move's recipe and saves a NEW blend (never the input).
Usage: blender -b --factory-startup <v3.blend> --python refine_v4.py -- <move> <out.blend> <report.json> [key=value ...]
moves: air_hover, air_fire_down, air_land, takeoff3, roar, collapse, bite, land2, rise
"""
import bpy, sys, json, math, os
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import lib_anim as L
import lib_v4 as V
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
OUT_ACTION = {"roar": "roar_v4"}.get(MOVE, MOVE + "_v4")
A = bpy.data.objects.get("Armature") or next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act3 = A.animation_data.action
act = act3.copy(); act.name = OUT_ACTION
A.animation_data.action = act
if act.slots: A.animation_data.action_slot = act.slots[0]
REP = {"move": MOVE, "source_blend": str(SRC), "source_action": act3.name, "out_action": OUT_ACTION, "options": opt}
bpy.data.actions.remove(act3)
clip = V.Clip(A, M, act)
STP = V.load_pose_npz(STANCE); HOV = V.load_pose_npz(HOVER)
P = O("period", 26.0)                   # beat period, frames (critic band 18-30); not a multiple of 4, or the beat aliases into the 4-frame saw
BOB = O("bob_cm", 4.0) / 100            # body bob peak-to-peak (world)
BEAT = dict(root_bias=O("root_bias", -3.0), root_amp=O("root_amp", 37.0), outer_bias=O("outer_bias", 15.0), outer_amp=O("outer_amp", 35.0),
            outer_lag=O("outer_lag", 0.06))   # degrees: root -40..+34, outer -20..+50 (the stroke bottom keeps the wing above the back line)
NONWING = [b for b in clip.bones_q() if b not in WING_BONES]
STP_Z = 0.211                           # Spine_0 head height at the shared stance (m), measured on idle_v2 frame 0
KER = [1, 2, 2, 2, 1]                   # zeros at 1/4 and 1/2 cycles per frame: removes the source's 4-frame cadence

def pin_ends(pose_s, pose_e, Ws, We, bones=None):
    """offset-blend the first Ws / last We frames onto poses (the move's own motion rides on a decaying offset)"""
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

def wings_from(pose, keep_residual=True, cyclic=False):
    """wing base = a static pose (hover / stance) times the fit's own high-pass wing detail (drift removed)"""
    clip.lowpass(WING_BONES, KER, cyclic=cyclic)
    res = clip.residual(WING_BONES, sigma=6.0) if keep_residual else {}
    for b in WING_BONES:
        base = np.tile(pose[b][0], (clip.N, 1))
        clip.ch[b]["q"] = V.fix_hemi(np.array([V.qmul(res[b][f], base[f]) for f in range(clip.N)]) if b in res else base)

LEAD = O("bob_lead", -0.05)              # cycles: phase of the bob table against the beat (best coupling on the K raster grid, bob_table.py)
BOB_TABLE = O("bob_table", str(Path(__file__).resolve().parent / "bob_table_K.npz"))
if BOB_TABLE != "theta":                 # body vertical velocity proportional to the visible wing-tip height (measured, folded over the beat)
    _bt = np.load(BOB_TABLE); _U, _Z = _bt["U"], _bt["Z"]
else:                                    # older shape: double integral of the wing angle velocity
    _U, _Z = V.periodic_bob(V.beat_theta, P)
def bob_shape(u):
    return np.interp(np.mod(np.asarray(u, float) + LEAD, 1.0), _U, _Z, period=1.0)
def zfun_of(ufun, envfun=lambda t: np.ones_like(t)):
    return lambda t: BOB * envfun(np.asarray(t, float)) * bob_shape(ufun(np.asarray(t, float)))
def apply_bob(zf, extra=None):
    N = clip.N; t = np.arange(N, dtype=float)
    d = np.zeros((N, 3)); d[:, 2] = zf(t)
    if extra is not None: d += extra
    clip.offset_body(d)
    V.tail_follow(clip, zf, gains=tuple(O("tail_gain", 0.2) * g for g in (-5.0, -7.0, -9.0)), lags=(1, 2, 3))
    return d
def plant_to(Tmats, wts, sib_ref=0):
    feet = list(L.FEET)
    err = clip.plant({b: Tmats[b] for b in feet}, {b: wts[b] for b in feet}, sib_ref=sib_ref)
    return err
def floor_lift(frames=None, floor=0.0015):
    """raise Spine_0 where a non-wing, non-foot vertex is under the floor (smoothed)"""
    N = clip.N; clip.apply()
    foot_groups = ["bone_9", "bone_14", "tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4", "tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4",
                   "tripo::1_Left_Limb_1", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"]
    idx = np.where(~np.isin(clip.dom, foot_groups) & ~np.char.startswith(clip.dom.astype(str), "VeyrWing"))[0]
    fr = range(N) if frames is None else frames
    need = np.zeros(N)
    for f in fr: need[f] = max(0.0, floor - float(clip.verts(f, idx)[:, 2].min()))
    mx = np.array([need[max(0, i - 3):i + 4].max() for i in range(N)])
    g = np.exp(-.5 * (np.arange(-6, 7) / 2.0) ** 2); g /= g.sum()
    lift = np.maximum(np.convolve(np.pad(mx, 6, mode="edge"), g, mode="valid"), need)
    d = np.zeros((N, 3)); d[:, 2] = lift
    if lift.max() > 1e-5: clip.offset_body(d)
    return float(lift.max())

def finish():
    clip.apply()
    REP["final"] = {"action": act.name, "frames": clip.N, "duration_s": round((clip.N - 1) / 24, 3)}
    act.use_fake_user = True
    OUT_JSON.write_text(json.dumps(REP, indent=1, default=float))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
    print("SAVED", OUT_BLEND, json.dumps(REP["final"]), flush=True)

# =====================================================================================================
def air_hover():
    assert clip.N == 121
    NL = O("loop_frames", 131)                           # 5 beats of 26 frames + the loop frame
    clip.lowpass(NONWING + WING_BONES, KER, cyclic=True)
    clip.resample(np.arange(NL) * 120.0 / (NL - 1)); N = clip.N
    wings_from(HOV, cyclic=True)
    REP["retime"] = {"frames_before": 121, "frames_after": N, "speed": round(120.0 / (N - 1), 4), "why": "a whole number of 26-frame beats in the loop"}
    pin_ends(HOV, HOV, 10, 10)                           # frame 0 (= loop frame) is exactly the hover pose before the beat layer
    for b in clip.ch:
        for k in clip.ch[b]: clip.ch[b][k][-1] = clip.ch[b][k][0]
    u = np.arange(N) / P; amp = np.ones(N)
    V.wing_beat(clip, u, amp, **BEAT); clip.apply()
    apply_bob(zfun_of(lambda t: t / P))
    for b in clip.ch:
        for k in clip.ch[b]: clip.ch[b][k][-1] = clip.ch[b][k][0]
    REP["beat"] = {"period": P, "cycles": (N - 1) / P, "bob_cm_p2p": BOB * 100, "bob_lead_cycles": LEAD, "angles": BEAT,
                   "camera_note": "wing tips leave the T camera's frame on the upstroke; review renders use the extra-tall K camera",
                   "phase0": "top of the upstroke at frame 0 (shared by every airborne v4 clip)",
                   "wing_base": "hover_pose_v1 wings x the fit's high-pass wing detail (the fit's 20% span drift removed)",
                   "destutter": "kernel [1,2,2,2,1]/8 on every channel, cyclic"}

def air_fire_down():
    N = clip.N; assert N == 193
    PF = (N - 1) / round((N - 1) / P)                    # 7 beats of 27.4 frames: starts and ends on the hover loop's frame 0
    clip.lowpass(NONWING + WING_BONES, KER)
    wings_from(HOV)
    pin_ends(HOV, HOV, 10, 10)
    u = np.arange(N) / PF
    V.wing_beat(clip, u, np.ones(N), **BEAT); clip.apply()
    apply_bob(zfun_of(lambda t: t / PF))
    REP["beat"] = {"period": PF, "cycles": (N - 1) / PF, "bob_cm_p2p": BOB * 100, "angles": BEAT, "note": "beats continue through the fire hold (80-152)"}

def takeoff3():
    N = clip.N; assert N == 121
    clip.lowpass(NONWING + WING_BONES, KER)
    res = clip.residual(NECK_HEAD + TAIL, sigma=6.0)      # the fit's own head/neck/tail detail, re-used in the air part
    idle = V.action_channels(DR / "Dragon_Idle_v2r_v2.blend", "idle_v2")
    src = np.minimum(np.arange(N), 89)
    for b, d in clip.ch.items():                          # ground phase: the shared stance breathing (idle_v2 from frame 0)
        if b in idle:
            for k in d:
                if k in idle[b]: d[k] = idle[b][k][src].copy()
    t = np.arange(N, dtype=float)
    LIFT_A, LIFT_B = O("rise_a", 43), O("rise_b", 100)
    wA = V.ramp(N, LIFT_A, LIFT_B, V.minjerk)
    body = [b for b in NONWING if b not in LEG_BONES]
    clip.blend_to(HOV, wA, bones=body)
    clip.blend_to(HOV, V.ramp(N, 56, 92), bones=LEG_BONES)
    wr = V.ramp(N, 56, 80) * (1 - V.ramp(N, 100, 112))
    for b, r in res.items():
        q = clip.ch[b]["q"]
        for f in range(N):
            if wr[f] > 1e-4: q[f] = V.qmul(V.qpow(r[f], wr[f]), q[f])
        clip.ch[b]["q"] = V.fix_hemi(q)
    clip.blend_to(HOV, V.ramp(N, 24, 40), bones=WING_BONES)
    PT = O("takeoff_period", 24.0)                      # three 24-frame beats 48 -> 120 (frame 120 = hover frame 0, top of the upstroke)
    T0 = 120 - 3 * PT                                     # 48: top of the wind-up; liftoff falls on the first downstroke (span opening)
    u = (np.maximum(t, T0) - 120) / PT
    amp = np.where(t < T0, V.sstep((t - 26) / (T0 - 26)), 1.0)
    V.wing_beat(clip, u, amp, **BEAT); clip.apply()
    CR = O("crouch_cm", 7.0) / 100
    CA, CB = O("crouch_release", 34), O("crouch_end", 46)
    crouch = np.where(t <= CA, -CR * V.sstep((t - 8) / 16.0), -CR * (1 - V.minjerk((t - CA) / float(CB - CA))))
    ex = np.zeros((N, 3)); ex[:, 2] = crouch
    zf = zfun_of(lambda tt: (tt - 120) / PT, lambda tt: V.sstep((tt - 50) / 18.0))
    apply_bob(zf, extra=ex)
    # feet: planted on the stance until the body is back above the stance height, then released over 5 frames (no pop)
    feet = list(L.FEET); MATS = clip.mats(feet)
    z = clip.body_z(); z0 = float(z[0])
    rel = int(np.argmax((t > O("release_after", 48)) & (z > z0 + 0.001)))
    T = {b: [MATS[b][0]] * N for b in feet}
    w = 1 - V.ramp(N, rel, rel + 5)
    err = plant_to(T, {b: w for b in feet})
    REP["takeoff"] = {"crouch_cm": CR * 100, "crouch_frames": [8, CB], "beat_period": PT, "wing_raise": [26, T0], "feet_release_frame": rel, "release_ramp": 5, "rise_frames": [LIFT_A, LIFT_B],
                      "wind_up_top_frame": T0, "first_downstroke": [T0, T0 + 0.45 * P], "ik_err_cm": err,
                      "sourced": "fit head/neck/tail high-pass detail in the air (56-112), idle_v2 breathing on the ground",
                      "authored": "ground phase, crouch, wind-up, rise curve (min-jerk, no overshoot), stance-to-hover blend, wing beats"}

def air_land():
    N = clip.N; assert N == 145
    C = O("contact", 92)                                 # body reaches the stance height; the feet touch about 2 frames earlier
    clip.lowpass(NONWING + WING_BONES, KER)
    wings_from(HOV)
    pin_ends(HOV, None, 10, 0)
    t = np.arange(N, dtype=float)
    idle = V.action_channels(DR / "Dragon_Idle_v2r_v2.blend", "idle_v2")
    stp = {b: STP[b] for b in STP}
    body = [b for b in NONWING if b not in LEG_BONES]
    clip.blend_to(stp, V.ramp(N, 60, 84), bones=LEG_BONES)
    clip.blend_to(stp, V.ramp(N, 66, C - 2), bones=body)
    k0 = 89 - (N - 1 - (C + 20))                          # the last frames play the end of the idle loop (frame 89 ~ frame 0)
    seq = {b: (idle[b]["q"][np.clip(k0 + (np.arange(N) - (C + 20)), 0, 89)], idle[b]["l"][np.clip(k0 + (np.arange(N) - (C + 20)), 0, 89)] if "l" in idle[b] else None)
           for b in idle if "q" in idle[b]}
    clip.blend_to(seq, V.ramp(N, C + 6, C + 20), bones=NONWING)
    # wings: beats to the top at 78, a slow braking flare to the widest stroke angle at contact, fold to the stance
    TOP = C - O("flare_lead", 14)                         # last upstroke top: the flare opens the span through the 12 frames before contact
    xs = 0.45 * math.acos(O("flare_theta", 0.2)) / math.pi
    u = np.where(t <= TOP, t / P, TOP / P + xs * V.sstep((t - TOP) / (C - 2 - TOP)))
    V.wing_beat(clip, u, np.ones(N), **BEAT); clip.apply()
    clip.blend_to(stp, V.ramp(N, C + 4, C + 28), bones=WING_BONES)
    pin_ends(HOV, stp, 0, 10)
    clip.apply()
    # body height: authored descent with a braking phase, impact compression and recovery
    zc = clip.body_z()
    z_h = float(zc[0]); z_s = float(STP_Z)
    v = np.zeros(N)
    a0, a1 = C - O("accel_frames", 12) - O("brake_frames", 16), C - O("brake_frames", 16)   # peak descent speed before the 12-frame window
    for f in range(N):
        if a0 <= f < a1: v[f] = V.sstep((f - a0) / (a1 - a0))
        elif a1 <= f < C: v[f] = 1 - (1 - O("brake", 0.3)) * V.sstep((f - a1) / (C - a1))
    vmax = (z_h - z_s) / v[:C].sum()
    zd = z_h - np.r_[0, np.cumsum(v * vmax)][:N]
    vc = v[C - 1] * vmax
    prof = np.array([0.85, 0.65, 0.45, 0.25, 0.1])          # legs absorb the landing: a fixed compression depth, fastest at contact
    depth = O("compress_cm", 4.5) / 100; comp = list(depth * prof / prof.sum())
    for i, c in enumerate(comp): zd[C + i] = zd[C + i - 1] - c
    rec = np.arange(C + 5, C + 22)
    zd[rec] = (z_s - depth) + depth * V.minjerk((rec - (C + 5)) / 16.0)
    zd[C + 22:] = np.nan
    dz = np.where(np.isnan(zd), 0.0, zd - zc)
    dz[: a0] = 0.0
    zf = zfun_of(lambda tt: tt / P, lambda tt: 1 - V.sstep((tt - 60) / 18.0))
    ex = np.zeros((N, 3)); ex[:, 2] = dz
    apply_bob(zf, extra=ex)
    # impact follow-through: head dips, tail slaps
    hd = np.zeros((N, 3)); hd[:, 1] = O("head_dip_deg", 8.0) * V.sstep((t - C) / 3.0) * (1 - V.sstep((t - C - 4) / 12.0))
    clip.add_rot("bone_2", hd)
    td = np.zeros((N, 3)); td[:, 1] = -6.0 * V.sstep((t - C) / 4.0) * (1 - V.sstep((t - C - 6) / 12.0))
    clip.add_rot("tripo::Tail_0", td); clip.apply()
    # feet: offset IK eases in over the 4 frames before contact, planted on the stance feet after
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
    REP["land"] = {"contact": C, "brake_window": [a1, C], "brake_speed_ratio": O("brake", 0.3), "contact_ease_frames": EZ, "vmax_cm_per_frame": round(vmax * 100, 3),
                   "contact_speed_cm_per_frame": round(vc * 100, 3), "compression_cm": round(depth * 100, 2), "flare_top": TOP, "ik_err_cm": err,
                   "sourced": "the fit's hover and descent poses (destuttered) to frame 66, idle_v2 end frames for the settle",
                   "authored": "descent speed profile, braking flare, impact compression, head/tail follow-through, wing fold, contact easing"}


OPEN = {"Root": [28.0, 0.0, -5.0], "Elbow": [42.0, 0.0, 0.0], "Membrane": [28.0, 0.0, 0.0], "Wrist": [10.0, 0.0, 0.0], "Tip": [0.0, 0.0, 0.0]}   # v3 flare pose
def lateral(f, side, idx):
    y = clip.verts(f, idx)[:, 1]
    return float(-y.min() if side == "PosZ" else y.max())
def wing_stretch(f, f_ref, edges):
    a = clip.verts(f); b = clip.verts(f_ref)
    la = np.linalg.norm(a[edges[:, 0]] - a[edges[:, 1]], axis=1); lb = np.linalg.norm(b[edges[:, 0]] - b[edges[:, 1]], axis=1)
    r = la / np.maximum(lb, 1e-6)
    return {"p999": round(float(np.percentile(r, 99.9)), 3), "max": round(float(r.max()), 3), "n_over_1.5": int((r > 1.5).sum())}
def wing_edges(side):
    me = clip.M.data
    ev = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get("vertices", ev); ev = ev.reshape(-1, 2)
    isw = np.char.startswith(clip.dom.astype(str), "VeyrWing" + side)
    return ev[isw[ev[:, 0]] & isw[ev[:, 1]]]
def stance_feet_plant(weight=None):
    feet = list(L.FEET); MATS = clip.mats(feet)
    T = {b: [MATS[b][0]] * clip.N for b in feet}
    w = np.ones(clip.N) if weight is None else weight
    return plant_to(T, {b: w for b in feet})

def roar():
    N = clip.N; t = np.arange(N, dtype=float)
    fa, fb, fin, fout = O("flare_a", 44), O("flare_b", 84), O("flare_in", 26), O("flare_out", 30)
    env = V.sstep((t - (fa - fin)) / fin) * (1 - V.sstep((t - fb) / fout))
    for b in WING_BONES: clip.ch[b]["q"] = np.tile(STP[b][0], (N, 1))      # authored flare on the stance wings (v3 flare replaced)
    base = {b: clip.ch[b]["q"].copy() for b in WING_BONES}
    idx = {s: clip.idx_of(["VeyrWing" + s]) for s in V.WSIDES}
    clip.apply(); lat0 = {s: lateral(0, s, idx[s]) for s in V.WSIDES}
    dxs = {s: 0.0 for s in V.WSIDES}; dzs = {s: 0.0 for s in V.WSIDES}
    def set_flare(sc_, frames):
        for side in V.WSIDES:
            for part, b in zip(V.WPARTS, WB[side]):
                v = list(OPEN[part])
                if part == "Root": v[0] += dxs[side]; v[2] += dzs[side]
                vec = [x * sc_[side] for x in v] if side == "NegZ" else [-v[0] * sc_[side], v[1] * sc_[side], -v[2] * sc_[side]]
                for f in frames:
                    clip.ch[b]["q"][f] = V.qmul(clip.rest_conj(b, [x * env[f] for x in vec]), base[b][f])
    hold = list(range(fa + 2, fb - 1, 4))
    TGT = O("flare", 1.25); CAP = O("flare_max", 1.15)
    sm = {}
    for side in V.WSIDES:
        best = (-1, 0.0, 0.0)
        for dx in (-24, -16, -8, 0, 8, 16):
            for dz in (-10, 0, 10):
                dxs[side], dzs[side] = float(dx), float(dz); set_flare({"PosZ": 0.8, "NegZ": 0.8}, hold); clip.apply()
                val = min(lateral(f, side, idx[side]) for f in hold)
                best = max(best, (val, float(dx), float(dz)))
        dxs[side], dzs[side] = best[1], best[2]
        lo, hi = 0.0, CAP
        for _ in range(9):
            mid = (lo + hi) / 2; set_flare({"PosZ": mid, "NegZ": mid}, hold); clip.apply()
            if min(lateral(f, side, idx[side]) for f in hold) / lat0[side] > TGT: hi = mid
            else: lo = mid
        sm[side] = hi if hi < CAP else lo
    set_flare(sm, range(N)); clip.apply()
    lat = {s: [lateral(f, s, idx[s]) / lat0[s] for f in range(N)] for s in V.WSIDES}
    fm = (fa + fb) // 2
    REP["flare"] = {"target": TGT, "window": [fa, fb], "in": fin, "out": fout, "root_offset_deg": {s: [dxs[s], dzs[s]] for s in V.WSIDES},
                    "scale_of_OPEN": sm, "hold_min_lateral_over_f0": {s: round(min(lat[s][fa + 2:fb - 1]), 3) for s in V.WSIDES},
                    "peak_lateral_over_f0": {s: round(max(lat[s]), 3) for s in V.WSIDES},
                    "stretch_at_hold_mid": {s: wing_stretch(fm, 0, wing_edges(s)) for s in V.WSIDES}}
    print("FLARE", json.dumps(REP["flare"]), flush=True)
    # living hold: breath heave, stronger head tremor, wing-tip tremor, tail lash (envelope = the flare hold)
    h = V.sstep((t - (fa - 4)) / 6.0) * (1 - V.sstep((t - fb) / 8.0))
    rng = np.random.default_rng(11)
    heave = np.zeros((N, 3)); heave[:, 2] = O("heave_cm", 0.8) / 100 * h * np.sin(2 * np.pi * t / 18.0)
    TR = O("tremor_deg", 3.4)
    for bone, k in (("bone_5", 1.0), ("bone_3", 0.7), ("bone_2", 0.4)):
        ph = rng.uniform(0, 6.28); v = np.zeros((N, 3))
        v[:, 1] = TR * k * h * np.sin(2 * np.pi * t / 2.7 + ph); v[:, 2] = 0.6 * TR * k * h * np.sin(2 * np.pi * t / 3.3 + ph + 1.0)
        clip.add_rot(bone, v)
    WT = O("wing_tremor_deg", 3.9)
    for side in V.WSIDES:
        ph = rng.uniform(0, 6.28); v = np.zeros((N, 3)); v[:, 0] = WT * h * np.sin(2 * np.pi * t / 3.1 + ph); v[:, 2] = 0.5 * WT * h * np.sin(2 * np.pi * t / 2.6 + ph)
        clip.add_rot("VeyrWing" + side + "Root", v)
    LA = O("tail_lash_deg", 7.0)
    for b, k, lag in (("tripo::Tail_0", 0.6, 0), ("tripo::Tail_1", 1.0, 3), ("tripo::Tail_2", 1.3, 6)):
        v = np.zeros((N, 3)); v[:, 2] = LA * k * h * np.sin(2 * np.pi * (t - lag) / 30.0); clip.add_rot(b, v)
    clip.apply(); clip.offset_body(heave)
    err = stance_feet_plant()
    REP["living_hold"] = {"heave_cm": O("heave_cm", 0.8), "heave_period": 18, "head_tremor_deg": TR, "wing_tremor_deg": WT, "tail_lash_deg": LA, "ik_err_cm": err}

def collapse():
    N = clip.N; t = np.arange(N, dtype=float)
    a = O("breath_a", 108); PB = O("breath_period", 40.0)
    env = V.sstep((t - a) / 12.0)
    br = 0.5 - 0.5 * np.cos(2 * np.pi * (t - a) / PB)
    amp = O("breath_amp", 1.0)
    for bone, deg in (("tripo::Spine_1", 2.2), ("tripo::Spine_2", -1.6), ("bone_2", 2.5), ("bone_5", -1.2)):
        if bone in clip.ch and "q" in clip.ch[bone]:
            v = np.zeros((N, 3)); v[:, 1] = amp * deg * env * br; clip.add_rot(bone, v)
    for side in V.WSIDES:                      # the folded wing lifts a little with each breath
        v = np.zeros((N, 3)); v[:, 0] = (-1 if side == "PosZ" else 1) * amp * 2.0 * env * br; clip.add_rot("VeyrWing" + side + "Root", v)
    v = np.zeros((N, 3)); v[:, 2] = amp * 3.0 * env * np.sin(2 * np.pi * (t - a) / 63.0); clip.add_rot("tripo::Tail_2", v)
    clip.apply()
    d = np.zeros((N, 3)); d[:, 2] = amp * O("breath_cm", 0.35) / 100 * env * br
    clip.offset_body(d)
    lift = floor_lift(range(int(a), N))
    REP["breathing"] = {"from": a, "period": PB, "amp_scale": amp, "spine_deg": [2.2, -1.6], "chest_deg": 2.5, "body_cm": O("breath_cm", 0.35),
                        "floor_lift_cm": round(lift * 100, 2)}

def bite():
    N0 = clip.N
    segs = [(0, 50, 0, 50), (50, 76, 50, O("hold_end", 58)), (76, N0 - 1, O("hold_end", 58), O("hold_end", 58) + (N0 - 1 - 76))]
    Nn = int(segs[-1][3]) + 1; pos = np.zeros(Nn)
    for f in range(Nn):
        for sa, sb, na, nb in segs:
            if na <= f <= nb: pos[f] = sa + (sb - sa) * (f - na) / max(1e-9, nb - na); break
    clip.resample(pos); N = clip.N; t = np.arange(N, dtype=float)
    he = O("hold_end", 58)
    e = V.sstep((t - 30) / 8.0) * (1 - V.sstep((t - he) / 14.0))
    lean = np.zeros((N, 3)); lean[:, 0] = O("lean_cm", 4.0) / 100 * e; lean[:, 2] = -0.4 / 100 * e
    for bone, deg in (("bone_2", O("neck_deg", 8.0)), ("bone_3", O("neck_deg", 8.0) * 0.5)):
        v = np.zeros((N, 3)); v[:, 1] = deg * e; clip.add_rot(bone, v)
    sh = V.sstep((t - 44) / 3.0) * (1 - V.sstep((t - he + 2) / 4.0))
    v = np.zeros((N, 3)); v[:, 2] = O("worry_deg", 4.0) * sh * np.sin(2 * np.pi * (t - 44) / 6.0); clip.add_rot("bone_5", v)
    clip.apply(); clip.offset_body(lean)
    err = stance_feet_plant()
    REP["bite"] = {"warp": segs, "frames": N, "lean_cm": O("lean_cm", 4.0), "neck_deg": O("neck_deg", 8.0), "worry_deg": O("worry_deg", 4.0), "ik_err_cm": err}

def land2():
    N = clip.N; t = np.arange(N, dtype=float)
    if "corr_npz" in opt:                            # centroid correction from the raster (pass 2): world z offsets of the body
        dz = np.load(opt["corr_npz"])["dz"]; d = np.zeros((N, 3)); d[:, 2] = dz[:N]; clip.offset_body(d)
        REP["centroid_correction_cm_max"] = round(float(np.abs(dz).max() * 100), 2)
    feet = list(L.FEET); MATS = clip.mats(feet); H = clip.heads(feet)
    T, W, plan = {}, {}, {}
    E = O("ease", 8)
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
        # cap the foot's vertical speed next to the floor (critic: no single-frame foot change > 8 px in T, about 1.9 cm):
        # the foot leaves the floor and reaches for it at most VZ per frame, so the leg extends early instead of snapping
        VZ = O("foot_vz_cm", 1.4) / 100
        z = np.array([T[b][f].translation.z for f in range(N)])
        zg0, zg1 = float(Pa.translation.z), float(Pb.translation.z)
        for f in range(t0 + 1, t1): z[f] = min(z[f], max(zg0, z[f - 1]) + VZ)
        for f in range(t1 - 1, t0, -1): z[f] = min(z[f], max(zg1, z[f + 1]) + VZ)
        for f in range(t0 + 1, t1): T[b][f].translation.z = float(z[f])
        plan[L.FOOT_LABEL[b]] = [t0, t1]
    err = plant_to(T, W)
    REP["land2"] = {"contact_ease_frames": E, "foot_vz_cap_cm_per_frame": O("foot_vz_cm", 1.4), "air_frames_per_foot": plan, "ik_err_cm": err}

def rise():
    N0 = clip.N
    col = V.action_channels(DR / opt.get("collapse_blend", "Dragon_Collapse_sd_v2r_v4.blend"), opt.get("collapse_action", "collapse_v4"))
    nc = len(next(iter(col.values()))["q"])
    end = {b: (d["q"][nc - 1], d["l"][nc - 1] if "l" in d else None) for b, d in col.items() if "q" in d}
    NP = O("prefix", 44); SKIP = O("skip", 14)       # rise_v3 stands still for its first ~20 frames: start it at SKIP
    src = np.r_[np.zeros(NP, int), np.arange(SKIP, N0)]
    clip.resize(len(src), src); N = clip.N; t = np.arange(N, dtype=float)
    feet = list(L.FEET); MS = clip.mats(feet)          # stance feet (rise_v3 frame SKIP), before the lying blend
    front = ["bone_2", "bone_3", "bone_4", "bone_5", "tripo::Head_0", "tripo::Head_1", "tripo::Head_2", "tripo::Head_3", "bone_36", "bone_37", "VeyrJaw",
             "tripo::Spine_2", "tripo::Spine_3"]
    hind = [b for b in clip.ch if b not in front and b not in WING_BONES]
    wF = 1 - V.ramp(N, 6, 26, V.minjerk); wH = 1 - V.ramp(N, 14, NP, V.minjerk); wW = 1 - V.ramp(N, 10, NP - 4)
    clip.blend_to(end, wF, bones=[b for b in front if b in end])
    clip.blend_to(end, wH, bones=[b for b in hind if b in end])
    clip.blend_to(end, wW, bones=WING_BONES)
    o = V.sstep((t - 14) / 8.0) * (1 - V.sstep((t - 30) / 10.0))     # balance: wings half-open while the body is pushed up
    for side in V.WSIDES:
        for part, b in zip(V.WPARTS, WB[side]):
            v = OPEN[part]; vec = v if side == "NegZ" else [-v[0], v[1], -v[2]]
            clip.add_rot(b, np.outer(o * 0.35, vec))
    clip.apply()
    ML = clip.mats(feet)                                # lying feet at frame 0
    WIN = {"bone_9": (8, 20), "bone_14": (12, 24), "tripo::1_Right_Limb_4": (20, 32), "tripo::0_Right_Limb_4": (24, 36)}
    LIFT = O("step_lift_cm", 3.5) / 100
    T, W = {}, {}
    for b in feet:
        Pa, Pb = ML[b][0], MS[b][NP + 2]; a_, b_ = WIN[b]; T[b] = []
        for f in range(N):
            if f > NP + 2: T[b].append(None); continue
            u = float(np.clip((f - a_) / (b_ - a_), 0, 1)); su = float(V.sstep(u))
            Mt = Pa.to_quaternion().slerp(Pb.to_quaternion(), su).to_matrix().to_4x4()
            tr = Pa.translation.lerp(Pb.translation, su); tr.z += LIFT * math.sin(math.pi * u); Mt.translation = tr
            T[b].append(Mt)
        W[b] = np.where(np.arange(N) <= NP + 2, V.ramp(N, 0, 6), 0.0)     # frame 0 stays the exact collapse end pose
    err = plant_to(T, W, sib_ref=NP + 2)
    lift = floor_lift(range(0, NP + 6))
    if lift > 1e-4: err2 = plant_to(T, W, sib_ref=NP + 2)
    REP["rise"] = {"prefix_frames": NP, "rise_v3_from_frame": SKIP, "frames": N, "start": "collapse_v4 last frame (exact)", "floor_lift_cm": round(lift * 100, 2),
                   "front_rise": [6, 26], "hind_rise": [14, NP], "foot_steps": WIN, "step_lift_cm": LIFT * 100, "ik_err_cm": err,
                   "authored": "lying-to-stance get-up prefix (head and chest first, feet step under the body one by one, wings half-open for balance)",
                   "sourced": "rise_v3 from frame 14 (its first 14 frames stand still)"}

RECIPES = {"air_hover": air_hover, "air_fire_down": air_fire_down, "takeoff3": takeoff3, "air_land": air_land,
           "roar": roar, "collapse": collapse, "bite": bite, "land2": land2, "rise": rise}
RECIPES[MOVE]()
finish()
