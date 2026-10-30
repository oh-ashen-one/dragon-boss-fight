"""Rise from lying: the video2rig fit of the Seedance clip -> an Action on the dragon-lying armature, refined (fix round 5 candidate).
Runs inside Blender, headless, through the GPU slot (run_rise_lying.sh):
  blender -b --factory-startup <Local/video2rig/dragon-lying/model.blend> --python refine_rise_lying.py -- <fit.npz> <out.blend> <report.json> [key=value ...]
<fit.npz> is the fit file (work/rise_lying/fit.npz) or the exported motion itself (out/rise_lying.npz); a fit file resolves to the motion next
to it. Steps (every number lands in <report.json>):
  1. import the motion with video2rig's own blender/import_motion.py (Action `rise_lying_fit`, kept with a fake user, as the raw reference);
  2. the numpy stages of lib_rise_lying.numpy_pipeline (the same code the CPU dry run uses): right hind knee relaxed off its joint limit,
     wings cleaned over frames wing_a..wing_b (twist cap, 5-frame smoothing, step cap; `wing_src=` = the solved wings of prep_wings_rl.py),
     opening hold trimmed to hold_s with a 6-frame ease from the collapse end pose, 8-frame blend into the idle_v2 frame-0 pose, floor lift;
  3. Action `rise_lying_v1` written from those channels; the planted feet are locked with IK (lib_v4 Clip.plant), one stretch per foot;
  4. the last frames are pinned to the idle pose (last frame == idle_v2 frame 0 exactly); Blender's evaluated mesh is compared with the
     CPU skinner on a few frames (a convention check); the Action's channels are saved next to the blend (<out>.channels.npz) and the
     mesh dumped for the CPU measure (dump=<npz>).
keys: hold_s=1.25 ease=6 idle_blend=8 wing_a=100 wing_b=134 twist_cap=25 jump_cap=8 relax_margin=6 start=-1 (frame of the raw clip kept first;
      -1 = from the detected push-up) foot_lock=1 lock_low_cm=3 lock_vmax_cm=1.2 lock_snap_cm=2 lock_drift_cm=2 lock_err_max_cm=4 rig=<dir> wing_src=<npz> idle_npz=<npz>
      idle_blend_file=<blend> idle_action=idle_v2 rise_blend=<blend> dump=<npz>
"""
import bpy, sys, json, os, runpy, math, copy
from pathlib import Path
import numpy as np
from mathutils import Vector
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import lib_anim as L
import lib_v4 as V
import lib_v5 as L5
import lib_rise_lying as RL
from lib_v4 import S0

args = sys.argv[sys.argv.index("--") + 1:]
FIT, OUT_BLEND, OUT_JSON = Path(args[0]), Path(args[1]), Path(args[2])
opt = dict(a.split("=", 1) for a in args[3:])
def O(k, d): return type(d)(opt[k]) if k in opt else d
REPO = Path(os.environ.get("VEYR_REPO", HERE.parent.parent.parent))
DR = REPO / "Local/video2rig/dragon"
SRC = Path(bpy.data.filepath).resolve()
assert OUT_BLEND.resolve() != SRC and not OUT_BLEND.exists(), "refusing to overwrite"
OUT_ACTION, RAW_ACTION = "rise_lying_v1", "rise_lying_fit"
proj, clipname = RL.project_of(FIT)
MOTION = RL.resolve_motion(FIT)
RIG_DIR = Path(opt.get("rig", proj / "rig"))
IDLE_BLEND = Path(opt.get("idle_blend_file", DR / "Dragon_Idle_v2r_v2.blend")); IDLE_ACTION = opt.get("idle_action", "idle_v2")
RISE_BLEND = Path(opt.get("rise_blend", DR / "Dragon_Rise_sd_v2r_v5.blend"))
REP = {"source_blend": str(SRC), "fit": str(FIT), "motion": str(MOTION), "out_action": OUT_ACTION, "raw_action": RAW_ACTION, "options": opt}

# ------------------------------------------------------------------ scene objects
M_OBJ = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
ARM = next((mod.object for mod in M_OBJ.modifiers if mod.type == "ARMATURE" and mod.object), None) or next(o for o in bpy.data.objects if o.type == "ARMATURE")
sc = bpy.context.scene; sc.frame_start = 0; sc.render.fps, sc.render.fps_base = 24, 1.0
for t in list(getattr(ARM.animation_data, "nla_tracks", [])): ARM.animation_data.nla_tracks.remove(t)

# ------------------------------------------------------------------ 1. import the fit (video2rig's own script)
IMPORT = Path(opt.get("import_motion", "/Users/midir/video2rig/blender/import_motion.py"))
assert IMPORT.exists(), f"video2rig import script missing: {IMPORT}"
keep_argv = sys.argv
sys.argv = [str(IMPORT), "--", "--motion", str(MOTION), "--armature", ARM.name, "--action", RAW_ACTION]
runpy.run_path(str(IMPORT), run_name="__main__")
sys.argv = keep_argv
raw = bpy.data.actions[RAW_ACTION]; raw.use_fake_user = True
if raw.slots: ARM.animation_data.action_slot = raw.slots[0]
act = raw.copy(); act.name = OUT_ACTION
ARM.animation_data.action = act
if act.slots: ARM.animation_data.action_slot = act.slots[0]
clip = V.Clip(ARM, M_OBJ, act)

# ------------------------------------------------------------------ 2. numpy stages
m = RL.Motion(MOTION); rig = RL.RigCPU(RIG_DIR)
assert clip.N == m.N, f"imported Action has {clip.N} frames, the motion {m.N}"
MW = ARM.matrix_world.copy(); REP["armature_matrix_is_identity"] = bool(all(abs(MW[i][j] - (1.0 if i == j else 0.0)) < 1e-6 for i in range(4) for j in range(4)))
assert m.bones == [b.name for b in ARM.pose.bones] or set(m.bones) <= {b.name for b in ARM.pose.bones}, "motion bones are not the armature's"
sq, sl = RL.start_pose_of(m, rig)
if "idle_npz" in opt: idle = RL.load_pose_npz(opt["idle_npz"]); REP["idle_source"] = opt["idle_npz"]
else:
    ch_idle = V.action_channels(IDLE_BLEND, IDLE_ACTION, [0]); idle = {b: (d["q"][0], d["l"][0] if "l" in d else None) for b, d in ch_idle.items() if "q" in d}
    REP["idle_source"] = f"{IDLE_BLEND.name}:{IDLE_ACTION} frame 0"
idle_q = RL.pose_array(idle, m.bones, sq); idle_loc = np.asarray(idle[S0][1], float)
overrides = None
if opt.get("wing_src") and Path(opt["wing_src"]).exists():
    z = np.load(opt["wing_src"], allow_pickle=True); overrides = {str(b): z["euler"][:, i] for i, b in enumerate(z["bones"])}
    REP["wing_src"] = {"file": opt["wing_src"], "iou_window_mean": {k: np.round(z[k][int(z["window"][0]):int(z["window"][1]) + 1].mean(0), 4).tolist() for k in ("iou_raw", "iou_heur", "iou_final")}}
else: REP["wing_src"] = None
kw = {k: type(RL.DEFAULTS[k])(v) for k, v in opt.items() if k in RL.DEFAULTS}
mf, rep_np = RL.numpy_pipeline(m, rig, idle_q, idle_loc, overrides=overrides, **kw)
REP["cli_options"] = opt; REP.update(rep_np); N = mf.N

# ------------------------------------------------------------------ 3. write Action rise_lying_v1
L5.replace_channels(clip, RL.to_ch(mf)); clip.ensure_loc(S0); clip.apply()
fidx = L5.foot_idx(clip)
def sole_report(tag):
    low = L5.feet_low(clip, range(clip.N), fidx)
    return {k: {"min_cm": round(float(v.min() * 100), 3), "max_cm": round(float(v.max() * 100), 3)} for k, v in low.items()}
REP["feet_low_before_lock"] = sole_report("before")

def lock_feet():
    """pin every planted foot stretch (low < lock_low_cm, slower than lock_vmax_cm per frame) with IK: the foot keeps the pose of the segment's
    median frame (segments cut when the foot creeps more than lock_drift_cm), sole snapped to the floor when within lock_snap_cm of it, 3-frame
    ramps at the ends and a 4-frame cross-fade between segments. A foot whose IK misses by more than lock_err_max_cm is dropped from the lock
    and the rest are solved again. (v5 rise / land2 idiom: Clip.plant)"""
    snap = {b: {k: v.copy() for k, v in d.items()} for b, d in clip.ch.items()}
    feet = list(L.FEET); H = clip.heads(feet); MATS = clip.mats(feet); low = L5.feet_low(clip, range(clip.N), fidx)
    LOW, VMAX, SNAP, DRIFT, SOLE, RAMP = O("lock_low_cm", 3.0) / 100, O("lock_vmax_cm", 1.2) / 100, O("lock_snap_cm", 2.0) / 100, O("lock_drift_cm", 2.0) / 100, 0.0005, 3
    N = clip.N; T, W, plan = {}, {}, {}
    for b in feet:
        h = H[b]; vel = np.zeros(N); vel[1:-1] = np.linalg.norm(h[2:] - h[:-2], axis=1) / 2; vel[0], vel[-1] = vel[1], vel[-2]
        runs = RL.foot_runs(low[b], vel, LOW, VMAX); segs = RL.split_runs(h, runs, DRIFT)
        T[b] = [None] * N; W[b] = np.zeros(N); plan[L.FOOT_LABEL[b]] = {"runs": runs, "segments": len(segs)}
        pins = []
        for (s0, s1) in segs:
            mean = h[s0:s1 + 1].mean(0); fm = s0 + int(np.argmin(np.linalg.norm(h[s0:s1 + 1] - mean, axis=1))); Mt = MATS[b][fm].copy()
            if low[b][fm] < SNAP: Mt.translation = Mt.translation + MW.inverted().to_3x3() @ Vector((0.0, 0.0, SOLE - low[b][fm]))     # sole on the floor
            pins.append((s0, s1, Mt))
        for i, (s0, s1, Mt) in enumerate(pins):
            for f in range(s0, s1 + 1): T[b][f] = Mt
        for i in range(len(pins) - 1):                                   # cross-fade between neighbouring segments of one stretch
            (a0, a1, Ma), (b0, b1, Mb) = pins[i], pins[i + 1]
            if b0 == a1 + 1:
                for f in range(max(a0, a1 - 1), min(b1, b0 + 1) + 1):
                    u = float(V.sstep((f - (a1 - 1)) / 3.0)); T[b][f] = Ma.lerp(Mb, u)
        for (r0, r1) in runs:
            for f in range(max(0, r0 - RAMP), min(N, r1 + RAMP + 1)):
                if T[b][f] is None: T[b][f] = T[b][r0] if f < r0 else T[b][r1]
                u = 1.0
                if f < r0: u = float(V.sstep((f - (r0 - RAMP) + 1) / (RAMP + 1)))
                elif f > r1: u = float(V.sstep(((r1 + RAMP) - f + 1) / (RAMP + 1)))
                W[b][f] = max(W[b][f], u)
    if not any(W[b].any() for b in feet): return {"locked": False, "reason": "no planted stretch", "stretches": plan}
    dropped = []; label_of = {L.FOOT_LABEL[b]: b for b in feet}; err = {}
    for attempt in range(4):
        err = clip.plant(T, W)
        bad = [label_of[k] for k, v in err.items() if v > O("lock_err_max_cm", 4.0)]
        if not bad: break
        clip.ch = {b: {k: v.copy() for k, v in d.items()} for b, d in snap.items()}; clip.apply()
        for b in bad: W[b] = np.zeros(N); dropped.append(L.FOOT_LABEL[b])
        if not any(W[b].any() for b in feet): return {"locked": False, "reason": f"IK error over {O('lock_err_max_cm', 4.0)} cm on every foot; channels restored", "dropped": dropped, "ik_err_cm": err, "stretches": plan}
    return {"locked": True, "ik_err_cm": err, "dropped_feet": dropped, "stretches": plan}
REP["foot_lock"] = lock_feet() if O("foot_lock", 1) else {"locked": False, "reason": "foot_lock=0"}

# ------------------------------------------------------------------ 4. pin the end to the idle pose, floor, checks
IDLE_POSE = {b: (idle[b][0], idle[b][1]) for b in idle if b in clip.ch}
wend = np.zeros(clip.N); NB = 4
for i in range(NB + 1): wend[clip.N - 1 - i] = float(V.sstep((NB - i) / float(NB)))          # 1 on the last frame, 0 four frames before
clip.blend_to(IDLE_POSE, wend, bones=[b for b in IDLE_POSE if "q" in clip.ch[b]]); clip.apply()
REP["feet_low_after_lock"] = sole_report("after")
fin_q = np.stack([clip.ch[b]["q"] for b in m.bones], 1); fin_loc = np.asarray(clip.ch[S0]["l"], float)
mfin = m.copy(); mfin.q, mfin.loc, mfin.N = RL.hemi(fin_q), fin_loc, clip.N
qr = RL.reorder(mfin, rig); X = {f: rig.skin(qr[f], mfin.loc[f]) for f in (0, clip.N // 2, clip.N - 1)}
chk = {}
for f in X:
    co = clip.verts(f); chk[f] = round(float(np.abs(co - X[f]).max() * 1000), 3)
REP["blender_vs_cpu_skin_max_mm"] = chk
Xi = rig.skin(RL.pose_array(idle, rig.names, sq[[m.bones.index(n) for n in rig.names]]), idle_loc)
REP["last_frame_vs_idle"] = {"max_vertex_mm": round(float(np.abs(X[clip.N - 1] - Xi).max() * 1000), 3),
                             "max_bone_deg": round(float(RL.qangle_deg(mfin.q[-1], idle_q).max()), 4)}
REP["first_frame_vs_collapse_end"] = {"max_bone_deg": round(float(RL.qangle_deg(mfin.q[0], sq).max()), 4), "root_loc_diff_mm": round(float(np.abs(mfin.loc[0] - sl).max() * 1000), 3)}
REP["wing_twist_max_deg"] = {b: round(v, 1) for b, v in list(RL.twist_deg(mfin, RL.wing_bones(mfin)).items())[:4]}
_j = RL.euler_jump_deg(mfin, RL.wing_bones(mfin)); REP["biggest_wing_step_deg"] = {"deg": round(_j[0], 2), "bone": _j[1], "frame": _j[2]}
if RISE_BLEND.exists() and not opt.get("skip_rise_ref"):
    try:
        rv = V.action_channels(RISE_BLEND, "rise_v5"); n5 = len(next(iter(rv.values()))["q"]); p5 = L5.pose_at(rv, n5 - 1)
        REP["last_frame_vs_rise_v5_end_deg"] = {"max": round(float(RL.qangle_deg(mfin.q[-1], RL.pose_array(p5, m.bones, sq)).max()), 2),
                                                 "mean": round(float(RL.qangle_deg(mfin.q[-1], RL.pose_array(p5, m.bones, sq)).mean()), 2)}
    except Exception as e: REP["last_frame_vs_rise_v5_end_deg"] = f"unavailable: {e!r}"
REP["final"] = {"action": act.name, "frames": clip.N, "duration_s": round((clip.N - 1) / 24, 3), "raw_frames": m.N}
act.use_fake_user = True
np.savez_compressed(str(OUT_BLEND) + ".channels.npz", bones=np.array(m.bones), q=mfin.q, loc=mfin.loc, idle_q=idle_q, idle_loc=idle_loc, start_q=sq, start_loc=sl)
OUT_JSON.write_text(json.dumps(REP, indent=1, default=float))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True, copy=False)
print("SAVED", OUT_BLEND, json.dumps(REP["final"]), flush=True)
print("CHECK blender_vs_cpu_mm", chk, "last_vs_idle", REP["last_frame_vs_idle"], "foot_lock", REP["foot_lock"].get("locked"), REP["foot_lock"].get("reason", ""), flush=True)
if "dump" in opt:
    # CPU measurement dump of the saved Action (dump_verts.py format), taken from THIS armature / mesh (model.blend may carry more than one armature)
    me = M_OBJ.data; me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    names = [g.name for g in M_OBJ.vertex_groups]
    vg = np.array([max(v.groups, key=lambda g: g.weight).group if len(v.groups) else -1 for v in me.vertices], np.int16)
    bones = [b.name for b in ARM.pose.bones]; frames = list(range(clip.N))
    Vv = np.empty((len(frames), len(me.vertices), 3), np.int16); BH = np.empty((len(frames), len(bones), 3), np.float32); BT = np.empty_like(BH)
    ARM.animation_data.action = act
    if act.slots: ARM.animation_data.action_slot = act.slots[0]
    for i, f in enumerate(frames):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); Me = M_OBJ.evaluated_get(dg); m2 = Me.to_mesh()
        co = np.empty(len(m2.vertices) * 3, np.float32); m2.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        mw = np.array(Me.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]; Vv[i] = np.round(co * 1e4).astype(np.int16); Me.to_mesh_clear()
        Ae = ARM.evaluated_get(dg); aw = Ae.matrix_world
        for j, b in enumerate(bones): pb = Ae.pose.bones[b]; BH[i, j] = tuple(aw @ pb.head); BT[i, j] = tuple(aw @ pb.tail)
    np.savez_compressed(opt["dump"], v=Vv, tri=tri, vgroup=vg, groups=np.array(names), frames=np.array(frames), bones=np.array(bones), bone_head=BH, bone_tail=BT,
                        fps=np.array(sc.render.fps / sc.render.fps_base))
    print("DUMPED", OUT_ACTION, opt["dump"], len(frames), "frames", flush=True)
