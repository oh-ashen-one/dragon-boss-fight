"""Round-3 (v5) helpers that run inside Blender, on top of lib_v4: offset blends that keep a clip's own motion, band-limited
noise for irregular tremor, the review cameras' projection (raster.py constants, numpy only) for in-Blender estimates,
per-foot lowest-vertex heights and a clean replacement of a clip's channels by another Action's."""
import math
import numpy as np
import lib_v4 as V

FOOT_GROUPS = {"bone_9": ["bone_9", "tripo::1_Left_Limb_1"], "bone_14": ["bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"],
               "tripo::1_Right_Limb_4": ["tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4"],
               "tripo::0_Right_Limb_4": ["tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"]}
NECK = ["bone_2", "bone_3", "bone_4", "bone_5"]
HEAD = ["tripo::Head_0", "tripo::Head_1", "tripo::Head_2", "tripo::Head_3", "bone_36", "bone_37", "VeyrJaw"]
FORELEGS = ["bone_6", "bone_7", "tripo::1_Left_Limb_0", "bone_9", "tripo::1_Left_Limb_1",
            "bone_11", "tripo::0_Left_Limb_0", "tripo::0_Left_Limb_1", "bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"]
HINDLEGS = [f"tripo::{s}_Right_Limb_{i}" for s in (0, 1) for i in range(5)]

# ---------------- review cameras (render_clip_v3.py / raster.py constants) ----------------
W_PX, H_PX = 960, 540
F_PX = 50.0 / 36.0 * W_PX
CAMS = {
    "G": ((0.0, 0.0, 0.24), {"front": (2.30, 0.00, 0.50), "left": (0.00, 2.30, 0.40), "threequarter": (1.65, 1.65, 0.80)}),
    "T": ((0.0, 0.0, 0.40), {"front": (3.10, 0.00, 0.55), "left": (0.00, 3.10, 0.45), "threequarter": (2.20, 2.20, 0.95)}),
    "K": ((0.0, 0.0, 0.62), {"front": (4.20, 0.00, 0.70), "left": (0.00, 4.20, 0.65), "threequarter": (3.00, 3.00, 1.15)}),
}
def project(P, group, view):
    tgt, d = CAMS[group]; p = np.array(d[view], float); t = np.array(tgt, float)
    zc = p - t; zc /= np.linalg.norm(zc); up = np.array([0, 0, 1.0]); yc = up - up.dot(zc) * zc; yc /= np.linalg.norm(yc); xc = np.cross(yc, zc)
    c = (np.asarray(P, float) - p) @ np.stack([xc, yc, zc]).T; z = -c[..., 2]
    return np.stack([W_PX / 2 + F_PX * c[..., 0] / z, H_PX / 2 - F_PX * c[..., 1] / z], -1)

# ---------------- channel helpers ----------------
def replace_channels(clip, ch):
    """clip channels <- another Action's channels (same bones); bones/kinds the other Action lacks go to rest"""
    N = len(next(iter(ch.values()))["q"])
    new = {}
    for b, d in clip.ch.items():
        new[b] = {}
        for k in d:
            if b in ch and k in ch[b]: new[b][k] = ch[b][k].copy()
            else: new[b][k] = np.tile([1.0, 0, 0, 0], (N, 1)) if k == "q" else np.zeros((N, 3))
    clip.ch = new; clip.N = N
def offset_to(clip, bones, target, w, ref):
    """right-multiply each bone by the share w[f] of the local offset that takes frame `ref` onto target[b] (the clip's own
    motion rides on top: at weight 1, frame ref equals the target exactly)"""
    for b in bones:
        if b not in clip.ch or "q" not in clip.ch[b] or b not in target: continue
        q = clip.ch[b]["q"]; d = V.qmul(V.qinv(q[ref]), target[b][0])
        for f in range(clip.N):
            if w[f] > 1e-6: q[f] = V.qmul(q[f], V.qpow(d, float(w[f])))
        clip.ch[b]["q"] = V.fix_hemi(q)
def pose_at(ch, f):
    return {b: (d["q"][f].copy(), d["l"][f].copy() if "l" in d else None) for b, d in ch.items() if "q" in d}
def smooth_noise(N, sigma, seed, hp_sigma=None):
    """unit-std gaussian-smoothed white noise (irregular, no fixed period); hp_sigma removes the slow drift"""
    rng = np.random.default_rng(seed); x = rng.standard_normal(N + 80)
    def g(x, s):
        h = int(4 * s) + 1; k = np.exp(-.5 * (np.arange(-h, h + 1) / s) ** 2); k /= k.sum(); return np.convolve(x, k, "same")
    y = g(x, sigma)
    if hp_sigma: y = y - g(y, hp_sigma)
    y = y[40:40 + N]; return (y - y.mean()) / (y.std() + 1e-12)
def hermite(u, m0, m1=0.0):
    """cubic from 0 (slope m0, in units of the whole span) to 1 (slope m1), u in [0, 1]"""
    u = np.clip(u, 0, 1); return (u ** 3 - 2 * u ** 2 + u) * m0 + (-2 * u ** 3 + 3 * u ** 2) + (u ** 3 - u ** 2) * m1

# ---------------- mesh measurements ----------------
def foot_idx(clip):
    return {b: np.where(np.isin(clip.dom, g))[0] for b, g in FOOT_GROUPS.items()}
def feet_low(clip, frames, fidx=None):
    fidx = fidx or foot_idx(clip); out = {b: [] for b in fidx}
    for f in frames:
        co = clip.verts(f)
        for b, ix in fidx.items(): out[b].append(float(co[ix, 2].min()))
    return {b: np.array(v) for b, v in out.items()}

# ---------------- fast single-frame pose probe (action detached; for searches) ----------------
class PoseProbe:
    """Evaluate the mesh for one frame's channels with per-bone extra rotations (armature-rest axes, degrees), without
    rewriting the Action: the Action is detached while probing and re-attached by close()."""
    def __init__(self, clip, f):
        import bpy
        self.bpy, self.clip, self.f = bpy, clip, f
        self.A = clip.A; self.act = self.A.animation_data.action; self.slot = getattr(self.A.animation_data, "action_slot", None)
        self.A.animation_data.action = None
        self.base = {}
        for b, d in clip.ch.items():
            pb = self.A.pose.bones[b]
            if "q" in d: pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = d["q"][f]; self.base[b] = np.array(d["q"][f])
            if "l" in d: pb.location = d["l"][f]
    def set(self, extra):
        for b, vec in extra.items():
            self.A.pose.bones[b].rotation_quaternion = V.qmul(self.clip.rest_conj(b, vec), self.base[b])
    def reset(self, bones):
        for b in bones: self.A.pose.bones[b].rotation_quaternion = self.base[b]
    def verts(self, idx=None):
        bpy = self.bpy; bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        Me = self.clip.M.evaluated_get(dg); me = Me.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        mw = np.array(Me.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]; Me.to_mesh_clear()
        return co if idx is None else co[idx]
    def close(self):
        self.A.animation_data.action = self.act
        if self.slot is not None and self.act.slots: self.A.animation_data.action_slot = self.act.slots[0]
def coord_search(fun, x0, steps=(16.0, 8.0, 4.0, 2.0), bounds=60.0):
    """coordinate descent on a small parameter vector (degrees)"""
    x = np.array(x0, float); fx = fun(x); n = 0
    for st in steps:
        improved = True
        while improved:
            improved = False
            for i in range(len(x)):
                for sgn in (1, -1):
                    y = x.copy(); y[i] += sgn * st
                    if abs(y[i]) > bounds: continue
                    fy = fun(y); n += 1
                    if fy < fx - 1e-6: x, fx, improved = y, fy, True
    return x, fx, n
