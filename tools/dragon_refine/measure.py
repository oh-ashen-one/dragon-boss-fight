"""Measure an idle Action: rotation speed profile, seam, feet, tail tip, wings.
Usage: blender -b --factory-startup <file.blend> --python measure.py -- <action_name> <out.json>
"""
import bpy, sys, json, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import lib_anim as L

args = sys.argv[sys.argv.index("--") + 1:]
ACT, OUT = args[0], args[1]
sc = bpy.context.scene
A = bpy.data.objects["Armature"] if "Armature" in bpy.data.objects else bpy.data.objects["DragonArmature"]
M = next(o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 10000)
act = bpy.data.actions[ACT]
A.animation_data.action = act
f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
frames = list(range(f0, f1 + 1)); nf = len(frames)
ch = L.read_channels(act, frames)

R = {"action": ACT, "frames": [f0, f1], "n_frames": nf}
spd, per = L.rot_speed(ch, nf, cyclic=True)   # spd[i] = step i->i+1, spd[nf-1] = seam (last->first)
inner = spd[:-1]
med = float(np.median(inner))
R["rot_speed_sum_rad_per_frame"] = [round(float(x), 5) for x in inner]
R["rot_speed_median"] = round(med, 5)
R["seam_step_sum"] = round(float(spd[-1]), 5)
R["seam_ratio_sum"] = round(float(spd[-1]) / med, 3)
# per-bone seam vs that bone's median step (bones that actually move)
pb_ratio = {}
for b, st in per.items():
    m = float(np.median(st[:-1]))
    if m > 1e-4: pb_ratio[b] = (round(float(st[-1]), 5), round(m, 5), round(float(st[-1]) / m, 2))
R["seam_per_bone_(seam,median,ratio)"] = pb_ratio
R["seam_per_bone_max_ratio"] = max(v[2] for v in pb_ratio.values())
# still-tail detection: 9-frame running mean below 40% of clip median
w = 9
run = np.convolve(inner, np.ones(w) / w, mode="same")
still = run < 0.4 * med
start = None
for i in range(len(still) - 1, -1, -1):
    if not still[i]: start = i + 1; break
R["still_tail_start_frame"] = int(start) if start is not None else None
R["running_mean_9"] = [round(float(x), 5) for x in run]
last24 = inner[-24:] if nf > 24 else inner
R["last_second_motion_vs_median"] = round(float(np.median(np.append(last24, spd[-1]))) / med, 3)

# world-space points
feet = list(L.FEET)
sibs = ["tripo::1_Left_Limb_1", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"]
wing_tips = [b.name for b in A.pose.bones if b.name.startswith("VeyrWing") and not b.children]
H, T, _ = L.world_points(A, frames, sc, bones_head=feet + sibs + ["tripo::Spine_0"], bones_tail=feet + sibs + ["tripo::Tail_2"] + wing_tips)
def exc(P):  # max distance from frame-0 position, cm
    return round(float(np.linalg.norm(P - P[0], axis=1).max()) * 100, 3)
R["foot_excursion_cm"] = {L.FOOT_LABEL[b]: {"head": exc(H[b]), "tail": exc(T[b]), "head_z0_cm": round(float(H[b][0, 2]) * 100, 3)} for b in feet}
R["sibling_excursion_cm"] = {b: {"head": exc(H[b]), "tail": exc(T[b])} for b in sibs}
# mesh foot patches
sets, zmin, zmax = L.foot_vertex_sets(M, A, {b: H[b][0] for b in feet}, sc)
R["mesh_height_cm"] = round((zmax - zmin) * 100, 2); R["mesh_zmin_cm"] = round(zmin * 100, 3)
R["mesh_dims_m"] = [round(x, 4) for x in M.dimensions]
fv = {}
for b, idx in sets.items():
    if len(idx) == 0: fv[L.FOOT_LABEL[b]] = None; continue
    C = L.mesh_coords(M, sc, frames, idx)  # [F, V, 3]
    d = np.linalg.norm(C - C[0][None], axis=2)
    fv[L.FOOT_LABEL[b]] = {"n_verts": int(len(idx)), "max_vert_excursion_cm": round(float(d.max()) * 100, 3),
                           "mean_vert_excursion_max_cm": round(float(d.mean(1).max()) * 100, 3),
                           "sole_z_min_over_clip_cm": round(float(C[:, :, 2].min(1).min()) * 100, 3),
                           "sole_z_frame0_cm": round(float(C[0, :, 2].min()) * 100, 3),
                           "sole_z_max_over_clip_cm": round(float(C[:, :, 2].min(1).max()) * 100, 3)}
R["foot_mesh_patch"] = fv
# tail tip speed (cm/frame), cyclic
tt = T["tripo::Tail_2"]
v = np.linalg.norm(np.diff(np.vstack([tt, tt[:1]]), axis=0), axis=1) * 100
R["tail_tip_speed_cm_per_frame"] = {"peak": round(float(v[:-1].max()), 4), "peak_frame": int(v[:-1].argmax()), "median": round(float(np.median(v[:-1])), 4),
    "peak_over_median": round(float(v[:-1].max() / np.median(v[:-1])), 2), "seam": round(float(v[-1]), 4),
    "near_zero_frames(<10%median)": [int(i) for i in np.where(v[:-1] < 0.1 * np.median(v[:-1]))[0]]}
R["tail_tip_speed_series"] = [round(float(x), 4) for x in v]
# wings: tip positions at seam
R["wing_tip_last_vs_first_cm"] = {b: round(float(np.linalg.norm(T[b][-1] - T[b][0])) * 100, 3) for b in wing_tips}
R["wing_tip_median_step_cm"] = {b: round(float(np.median(np.linalg.norm(np.diff(T[b], axis=0), axis=1))) * 100, 3) for b in wing_tips}
R["spine0_range_cm"] = [round(float(x) * 100, 3) for x in (H["tripo::Spine_0"].max(0) - H["tripo::Spine_0"].min(0))]
Path(OUT).write_text(json.dumps(R, indent=1))
brief = {k: v for k, v in R.items() if k not in ("rot_speed_sum_rad_per_frame", "running_mean_9", "seam_per_bone_(seam,median,ratio)", "tail_tip_speed_series")}
print("MEASURE", json.dumps(brief, indent=1))
