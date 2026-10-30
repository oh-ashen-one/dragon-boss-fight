"""Fix round 4 (v6): corrections on top of the round-3 (v5) Actions, from docs/dragon-critique-round4-20261030.md.
Opens the v5 blend, copies its Action to <move>_v6, applies the move's layer and saves a NEW blend (never the input).
Every recipe ADDS to the v5 channels (nothing is re-read from older fits), so all that the critic passed in v5 is kept.
Usage: blender -b --factory-startup <v5.blend> --python refine_v6.py -- <move> <out.blend> <report.json> [key=value ...] [dump=<npz>]
moves: air_land, roar, collapse, bite
"""
import bpy, sys, json, math, os, runpy
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import lib_anim as L
import lib_v4 as V
import lib_v5 as L5
import lib_v6 as L6
from lib_v4 import S0, WING_BONES, TAIL

args = sys.argv[sys.argv.index("--") + 1:]
MOVE, OUT_BLEND, OUT_JSON = args[0], Path(args[1]), Path(args[2])
opt = dict(a.split("=", 1) for a in args[3:])
def O(k, d): return type(d)(opt[k]) if k in opt else d
SRC = Path(bpy.data.filepath).resolve()
assert OUT_BLEND.resolve() != SRC and not OUT_BLEND.exists(), "refusing to overwrite"
OUT_ACTION = MOVE + "_v6"
A = bpy.data.objects.get("Armature") or next(o for o in bpy.data.objects if o.type == "ARMATURE")
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act5 = A.animation_data.action
act = act5.copy(); act.name = OUT_ACTION
A.animation_data.action = act
if act.slots: A.animation_data.action_slot = act.slots[0]
REP = {"move": MOVE, "source_blend": str(SRC), "source_action": act5.name, "out_action": OUT_ACTION, "options": opt}
bpy.data.actions.remove(act5)
clip = V.Clip(A, M, act)
N = clip.N; t = np.arange(N, dtype=float)
FEET = list(L.FEET)
def side_sign(side): return 1.0 if side == "NegZ" else -1.0          # +X rotation raises the NegZ wing, -X the PosZ wing
def env(a, b, c, d):
    """0 before a, eased up to 1 at b, held, eased down to 0 at d"""
    return V.sstep((t - a) / max(1e-6, b - a)) * (1 - V.sstep((t - c) / max(1e-6, d - c)))
def rot(bone, axis, deg):
    v = np.zeros((N, 3)); v[:, axis] = deg; clip.add_rot(bone, v)
def finish():
    clip.apply()
    REP["final"] = {"action": act.name, "frames": clip.N, "duration_s": round((clip.N - 1) / 24, 3)}
    act.use_fake_user = True
    OUT_JSON.write_text(json.dumps(REP, indent=1, default=float))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
    print("SAVED", OUT_BLEND, json.dumps(REP["final"]), flush=True)
    if "dump" in opt:
        sys.argv = [sys.argv[0], "--", OUT_ACTION, opt["dump"]]
        runpy.run_path(str(HERE / "dump_verts.py"), run_name="__main__")

# =====================================================================================================
def air_land():
    """(1) the wing fold after contact (v5: raised to tucked in 2 frames, 98-100) is re-timed over fold_new frames; the body,
    slam and feet keep v5's timing. (2) the slam hold (v5 front view pixel-identical 106-114) gets a heavy post-impact pant
    (spine, neck, jaw, folded-wing heave) and a sideways tail lash, faded out before v5's end panting and end pin."""
    assert N == 145, N
    M0 = clip.mats(FEET)
    A_, BO, BN, CC = O("fold_a", 96), O("fold_old_b", 104), O("fold_new_b", 110), O("fold_c", 122)
    src = L6.warp_curve(N, A_, BN, BO, CC, lin=O("fold_lin", 0.5))
    L6.retime_bones(clip, WING_BONES, src)
    e = env(O("hold_a", 100), O("hold_b", 104), O("hold_c", 122), O("hold_d", 132))
    PP = O("pant_period", 11.0)
    pb = np.sin(2 * np.pi * (t - O("hold_a", 100)) / PP) * e
    for bone, deg in (("tripo::Spine_1", O("pant_spine_deg", 3.5)), ("tripo::Spine_2", -0.7 * O("pant_spine_deg", 3.5)),
                      ("bone_2", O("pant_neck_deg", 4.5)), ("bone_5", -0.5 * O("pant_neck_deg", 4.5))):
        rot(bone, 1, deg * pb)
    if "VeyrJaw" in clip.ch: rot("VeyrJaw", 1, O("jaw_deg", 4.0) * np.maximum(0, pb))
    for side in ("PosZ", "NegZ"):
        rot("VeyrWing" + side + "Root", 0, side_sign(side) * O("pant_wing_deg", 3.0) * pb)
    tw = {}
    for b, k, lag in (("tripo::Tail_0", 0.4, 0), ("tripo::Tail_1", 0.7, 2), ("tripo::Tail_2", 1.0, 4)):
        tt = t - O("lash_a", 99) - lag
        en = V.sstep(tt / 3.0) * (1 - V.sstep((t - O("hold_c", 122)) / 12.0))
        rot(b, 2, O("lash_yaw_deg", 16.0) * k * en * np.sin(2 * np.pi * np.maximum(tt, 0) / O("lash_period", 16.0)))
        tw[b] = [k, lag]
    clip.apply()
    w = V.ramp(N, 92, 96)
    err = L6.replant(clip, M0, w)
    REP["air_land"] = {"wing_fold_retime": {"new_frames": [A_, BN], "old_frames": [A_, BO], "rejoin": CC, "linear_share": O("fold_lin", 0.5)},
                       "hold_pant": {"window": [O("hold_a", 100), O("hold_b", 104), O("hold_c", 122), O("hold_d", 132)], "period": PP,
                                     "spine_deg": O("pant_spine_deg", 3.5), "neck_deg": O("pant_neck_deg", 4.5), "jaw_deg": O("jaw_deg", 4.0), "wing_deg": O("pant_wing_deg", 3.0)},
                       "tail_lash": {"yaw_deg": O("lash_yaw_deg", 16.0), "period": O("lash_period", 16.0), "bones": tw}, "ik_err_cm": err,
                       "kept_from_v5": "descent, braking flare, body slam + hold + recovery, v5 tail whip, end panting, end stance pin"}

def roar():
    """screen-left (PosZ) wing opened on top of v5 by a searched extra (root raise/sweep, elbow unfold) under v5's own flare
    envelope; target: both half-spans (frame-0-centre definition, the round-4 critic's) equal at span_target"""
    cx0, l0, r0 = O("cx0", 473.6), O("l0", 224.0), O("r0", 732.0)
    fa, fb, fin, fout = 44, 84, 26, 30
    en = V.sstep((t - (fa - fin)) / fin) * (1 - V.sstep((t - fb) / fout))
    HF = [int(x) for x in opt.get("hold_frames", "50,58,66,74,82").split(",")]
    TG = O("span_target", 1.15)
    side = "PosZ"; sg = side_sign(side)
    bR, bE = "VeyrWing" + side + "Root", "VeyrWing" + side + "Elbow"
    def ex_of(x): return {bR: [sg * x[0], 0.0, sg * x[1]], bE: [sg * x[2], 0.0, 0.0]}
    def ev(x):
        Ls, Rs = [], []
        for f in HF:
            PR = L5.PoseProbe(clip, f); PR.set({k: [v * float(en[f]) for v in vec] for k, vec in ex_of(x).items()})
            l_, r_ = L6.halves_f0(PR.verts(), cx0, l0, r0); PR.close(); Ls.append(l_); Rs.append(r_)
        return np.array(Ls), np.array(Rs)
    L0_, R0_ = ev([0, 0, 0])
    def J(x):
        Ls, Rs = ev(x); return 100 * abs(float(Ls.mean()) - TG) + 30 * float(np.abs(Ls - Rs).max()) + 0.002 * float(np.dot(x, x))
    x, jx, nx = L5.coord_search(J, [O("x0_rx", 0.0), O("x0_rz", 0.0), O("x0_e", 0.0)], steps=(8.0, 4.0, 2.0, 1.0), bounds=O("bound", 45.0))
    L1_, R1_ = ev(x)
    for b, vec in ex_of(x).items():
        clip.add_rot(b, np.outer(en, vec))
    clip.apply()
    REP["roar"] = {"wing": side, "extra_deg_rx_rz_e": [round(float(v), 2) for v in x], "cost": round(jx, 3), "evals": nx, "hold_frames": HF,
                   "estimate_vertex_halves": {"before_L_R": [round(float(L0_.mean()), 3), round(float(R0_.mean()), 3)],
                                              "after_L_R": [round(float(L1_.mean()), 3), round(float(R1_.mean()), 3)],
                                              "after_gap_max": round(float(np.abs(L1_ - R1_).max()), 3)},
                   "definition": "half-span about the frame-0 mask centre column cx0 (raster frame 0 of roar_v5: cx0 %.1f, l0 %.0f, r0 %.0f)" % (cx0, l0, r0),
                   "kept_from_v5": "both wings' v5 flare, irregular 9-10 frame tremor, head tremor, breath, tail, feet"}

def bite():
    """near-wing threat flare during the strike: a searched extra on both wings (mirrored root raise, sweep and elbow unfold)
    under a strike envelope, maximising the 3/4 view's upper-left zone area (frame-0 centre quadrant) at frames 44-50"""
    zx, zy = O("zone_x", 414.5), O("zone_y", 288.4)
    en = env(O("env_a", 30), O("env_b", 40), O("env_c", 58), O("env_d", 70))
    HF = [int(x) for x in opt.get("frames", "44,47,50").split(",")]
    PR = L5.PoseProbe(clip, 0); a0 = L6.cell_area(L5.project(PR.verts(), "G", "threequarter"), (zx, zy)); PR.close()
    sides = opt.get("sides", "PosZ,NegZ").split(",")
    def ex_of(x, s=1.0):
        ex = {}
        for side in sides:
            sg = side_sign(side)
            ex["VeyrWing" + side + "Root"] = [sg * x[0] * s, 0.0, sg * x[1] * s]; ex["VeyrWing" + side + "Elbow"] = [sg * x[2] * s, 0.0, 0.0]
        return ex
    def ev(x):
        r = []
        for f in HF:
            PR = L5.PoseProbe(clip, f); PR.set(ex_of(x, float(en[f])))
            r.append(L6.cell_area(L5.project(PR.verts(), "G", "threequarter"), (zx, zy)) / a0); PR.close()
        return np.array(r)
    r0_ = ev([0, 0, 0]); TG = O("area_target", 0.82)
    def J(x):
        r = ev(x); return 100 * max(0.0, TG - float(r.min())) + 0.01 * float(np.dot(x, x))
    x, jx, nx = L5.coord_search(J, [0.0, 0.0, 0.0], steps=(16.0, 8.0, 4.0), bounds=O("bound", 40.0))
    r1_ = ev(x)
    for b, vec in ex_of(x).items():
        clip.add_rot(b, np.outer(en, vec))
    clip.apply()
    REP["bite"] = {"extra_deg_rx_rz_e": [round(float(v), 2) for v in x], "sides": sides, "envelope": [O("env_a", 30), O("env_b", 40), O("env_c", 58), O("env_d", 70)],
                   "zone": [zx, zy], "zone_area_estimate": {"frames": HF, "before": [round(float(v), 3) for v in r0_], "after": [round(float(v), 3) for v in r1_]},
                   "cost": round(jx, 3), "evals": nx, "kept_from_v5": "time warp, reach, lean, worry shake, wing hold, feet"}

def collapse():
    """(1) lying pose: a searched extra on the hips (Spine_1 pitch), tail root counter-pitch and the screen-right (NegZ)
    wing (root raise/sweep/twist, elbow, wrist) flattens the front silhouette top; blended in over the fall, feet re-planted
    on v5's lying feet. (2) lying breath: stronger, non-synchronous layers (breath 40 f, tail sway 27 f, head drift 33 f)
    so no lying frame is still; every layer is zero at the last frame (the rise chain starts from it)."""
    from mathutils.kdtree import KDTree
    M0 = clip.mats(FEET)
    f = N - 1; clip.apply()
    isw = np.char.startswith(clip.dom.astype(str), "VeyrWing")
    feet_all = sum(L5.FOOT_GROUPS.values(), [])
    nf = np.where(~isw & ~np.isin(clip.dom, feet_all + L5.HINDLEGS + L5.FORELEGS))[0]
    wN = clip.idx_of(["VeyrWingNegZ"]); wP = clip.idx_of(["VeyrWingPosZ"])
    PR = L5.PoseProbe(clip, f); co0 = PR.verts()
    p0 = L5.project(co0, "G", "front"); low0 = float(p0[:, 1].max()); zf0 = float(co0[nf, 2].min())
    kd = KDTree(len(nf))
    for i, v in enumerate(co0[nf]): kd.insert(v, i)
    kd.balance()
    sub = np.random.default_rng(3).choice(len(wN), min(400, len(wN)), replace=False)
    cw0 = co0[wN]; d0 = float(np.mean([kd.find(cw0[k])[2] for k in sub]))
    H0 = O("stand_h", 317.98)
    def ex_of(x):
        return {"tripo::Spine_1": [0.0, x[0], 0.0], "bone_18": [0.0, -x[0], 0.0],
                "VeyrWingNegZRoot": [x[1], x[2], x[3]], "VeyrWingNegZElbow": [x[4], 0.0, 0.0], "VeyrWingNegZWrist": [x[5], 0.0, 0.0]}
    def terms(x):
        PR.set(ex_of(x)); co = PR.verts(); p = L5.project(co, "G", "front")
        h = (float(p[:, 1].max()) - float(p[:, 1].min())) / H0
        cw = co[wN]; dd = float(np.mean([kd.find(cw[k])[2] for k in sub]))
        return {"h": h, "floor_body": 3000 * max(0.0, zf0 - 0.001 - float(co[nf, 2].min())), "wing_floor": 3000 * max(0.0, 0.003 - float(cw[:, 2].min())),
                "wing_lateral": 2000 * max(0.0, float(np.abs(cw[:, 1]).max()) - O("wing_y_max", 0.27)), "wing_off_body": 200 * max(0.0, dd - d0 - 0.01),
                "low": 0.01 * max(0.0, float(p[:, 1].max()) - low0)}
    def J(x):
        tm = terms(x); return 100 * tm["h"] + sum(v for k, v in tm.items() if k != "h") + 0.001 * float(np.dot(x, x))
    t0 = terms([0.0] * 6)
    x, jx, nx = L5.coord_search(J, [0.0] * 6, steps=(16.0, 8.0, 4.0, 2.0, 1.0), bounds=O("bound", 60.0))
    t1 = terms(x); PR.close()
    wl = V.ramp(N, O("lie_a", 74), O("lie_b", 96))
    for b, vec in ex_of(x).items():
        clip.add_rot(b, np.outer(wl, vec))
    # breathing: three non-synchronous layers, all zero at the last frame
    eb = V.sstep((t - (N - 1 - O("breath_len", 60))) / 14.0)
    tz = t - (N - 1)
    br = np.sin(2 * np.pi * tz / O("breath_period", 40.0)) * eb
    for bone, deg in (("tripo::Spine_1", O("breath_spine_deg", 2.4)), ("tripo::Spine_2", -0.7 * O("breath_spine_deg", 2.4)), ("bone_2", O("breath_neck_deg", 2.5))):
        rot(bone, 1, deg * br)
    for side in ("PosZ", "NegZ"):
        rot("VeyrWing" + side + "Root", 0, side_sign(side) * O("breath_wing_deg", 3.5) * br)
    ts = np.sin(2 * np.pi * tz / O("tail_period", 27.0)) * eb
    rot("tripo::Tail_1", 2, 0.6 * O("tail_deg", 5.0) * ts); rot("tripo::Tail_2", 2, O("tail_deg", 5.0) * ts)
    hd = np.sin(2 * np.pi * tz / O("head_period", 33.0)) * eb
    rot("bone_5", 2, O("head_deg", 2.0) * hd); rot("bone_4", 1, 0.5 * O("head_deg", 2.0) * hd)
    clip.apply()
    w = V.ramp(N, O("lie_a", 74) - 4, O("lie_a", 74))
    err = L6.replant(clip, M0, w)
    rnd = lambda d_: {k: round(float(v), 4) for k, v in d_.items()}
    REP["collapse"] = {"lying_search": {"extra_deg": {k: [round(float(c), 2) for c in v] for k, v in ex_of(x).items()}, "cost": round(jx, 3), "evals": nx,
                                        "terms_before": rnd(t0), "terms_after": rnd(t1)},
                       "lying_blend": [O("lie_a", 74), O("lie_b", 96)],
                       "breath_layers": {"breath": [O("breath_period", 40.0), O("breath_spine_deg", 2.4), O("breath_neck_deg", 2.5), O("breath_wing_deg", 3.5)],
                                         "tail": [O("tail_period", 27.0), O("tail_deg", 5.0)], "head": [O("head_period", 33.0), O("head_deg", 2.0)],
                                         "from_frame": N - 1 - O("breath_len", 60), "zero_at_last_frame": True},
                       "ik_err_cm": err, "kept_from_v5": "slow buckle, head aside, PosZ wing fold, v5 breathing (the new layers add to it)"}

RECIPES = {"air_land": air_land, "roar": roar, "bite": bite, "collapse": collapse}
RECIPES[MOVE]()
finish()
