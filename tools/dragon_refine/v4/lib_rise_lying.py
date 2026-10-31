"""Rise-from-lying refine, numpy only (runs inside Blender's python and on the CPU, no bpy, no scipy, no cv2).

* motion files of video2rig (`<project>/out/<clip>.npz`: bones, root, quaternions [N,B,4] (w,x,y,z) = the pose-bone basis of every
  bone, root_location [N,3] = the root bone's location in bone space, times) and the rig exported next to it (`rig/rig.json`,
  `rig/mesh.npz`);
* the Euler view video2rig fitted in: basis = Rx(a) Ry(b) Rz(c) per fitted bone in its own rest frame (b = the twist about the bone);
* the stages of the refine (trim + ease, knee relax, wing clean, blend into the idle pose) as pure functions on [N,B,4] arrays;
* a CPU linear-blend skinner (same maths as video2rig/rig.py skin, checked against it) with a dump in the format of dump_verts.py,
  so measure_rise_lying.py can score a clip without Blender.
Quaternions are (w, x, y, z) as Blender's pose bones and the rest of tools/dragon_refine.
"""
import json, math
from pathlib import Path
import numpy as np

# ---------------------------------------------------------------- quaternions / Euler
def qnorm(q): return q / np.linalg.norm(q, axis=-1, keepdims=True)
def qmul(a, b):
    a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]; w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)
def qconj(q): return np.asarray(q, float) * np.array([1.0, -1.0, -1.0, -1.0])
def qangle_deg(a, b):
    """angle (degrees) of the rotation taking a to b; works on broadcastable [...,4]"""
    d = np.abs(np.sum(qnorm(np.asarray(a, float)) * qnorm(np.asarray(b, float)), -1))
    return np.degrees(2.0 * np.arccos(np.clip(d, 0.0, 1.0)))
def hemi(q):
    """each key on the same hemisphere as the one before; q [N,...,4] along axis 0"""
    q = np.array(q, float)
    for i in range(1, len(q)):
        s = np.sum(q[i] * q[i - 1], -1, keepdims=True)
        q[i] = np.where(s < 0, -q[i], q[i])
    return q
def nlerp(a, b, w):
    a = np.asarray(a, float); b = np.asarray(b, float); w = np.asarray(w, float)
    while w.ndim < a.ndim: w = w[..., None]
    s = np.sum(a * b, -1, keepdims=True); b = np.where(s < 0, -b, b)
    return qnorm((1 - w) * a + w * b)
def sstep(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)
def q_axis(axis, ang):
    ang = np.asarray(ang, float); h = ang / 2
    out = np.zeros(ang.shape + (4,)); out[..., 0] = np.cos(h)
    out[..., 1 + axis] = np.sin(h); return out
def q_from_eul(a, b, c):
    """Rx(a) Ry(b) Rz(c) (radians) -> quaternion"""
    return qnorm(qmul(qmul(q_axis(0, a), q_axis(1, b)), q_axis(2, c)))
def q_to_mat(q):
    q = qnorm(np.asarray(q, float)); w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    R = np.empty(q.shape[:-1] + (3, 3))
    R[..., 0, 0] = 1 - 2 * (y * y + z * z); R[..., 0, 1] = 2 * (x * y - z * w); R[..., 0, 2] = 2 * (x * z + y * w)
    R[..., 1, 0] = 2 * (x * y + z * w); R[..., 1, 1] = 1 - 2 * (x * x + z * z); R[..., 1, 2] = 2 * (y * z - x * w)
    R[..., 2, 0] = 2 * (x * z - y * w); R[..., 2, 1] = 2 * (y * z + x * w); R[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return R
def mat_to_q(R):
    R = np.asarray(R, float); sh = R.shape[:-2]; R = R.reshape(-1, 3, 3); out = np.zeros((len(R), 4))
    for i, m in enumerate(R):
        t = m[0, 0] + m[1, 1] + m[2, 2]
        if t > 0:
            s = math.sqrt(t + 1.0) * 2; q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2; q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
        elif m[1, 1] > m[2, 2]:
            s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2; q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
        else:
            s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2; q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
        out[i] = q
    return qnorm(out).reshape(sh + (4,))
def q_to_eul(q):
    """quaternion -> (a, b, c) radians with R = Rx(a) Ry(b) Rz(c), b in [-90, 90] deg; [N,3] unwrapped along axis 0 for 2-D input"""
    R = q_to_mat(q)
    b = np.arcsin(np.clip(R[..., 0, 2], -1, 1)); a = np.arctan2(-R[..., 1, 2], R[..., 2, 2]); c = np.arctan2(-R[..., 0, 1], R[..., 0, 0])
    e = np.stack([a, b, c], -1)
    return np.unwrap(e, axis=0) if e.ndim == 2 and len(e) > 1 else e

# ---------------------------------------------------------------- files
def project_of(fit_path):
    """<project>/work/<clip>/fit.npz -> (project dir, clip name)"""
    p = Path(fit_path).resolve()
    return p.parents[2], p.parent.name
def resolve_motion(path):
    """The motion npz (bones/quaternions/root_location): the file itself, or, for a fit.npz (params), the motion video2rig exported
    from it next to it (<project>/out/<clip>.npz)."""
    p = Path(path).resolve(); z = np.load(p, allow_pickle=True)
    if "quaternions" in z.files: return p
    proj, clip = project_of(p)
    for cand in (proj / "out" / f"{clip}.npz", ):
        if cand.exists(): return cand
    raise SystemExit(f"{p}: a fit (params) file and no exported motion at {proj}/out/{clip}.npz (run video2rig run first)")
class Motion:
    def __init__(self, path):
        z = np.load(resolve_motion(path), allow_pickle=True)
        self.path = str(resolve_motion(path)); self.bones = [str(b) for b in z["bones"]]; self.root = str(z["root"])
        self.q = hemi(z["quaternions"].astype(float)); self.loc = z["root_location"].astype(float); self.times = z["times"].astype(float)
        self.armature_world = z["armature_world"].astype(float)
        self.ri = self.bones.index(self.root); self.N = len(self.q)
    def idx(self, b): return self.bones.index(b)
    def copy(self):
        m = object.__new__(Motion); m.__dict__.update(self.__dict__); m.q = self.q.copy(); m.loc = self.loc.copy(); return m
    def fitted(self, tol=1e-9):
        """bones whose basis moves at all (the others hold the start pose)"""
        return [b for j, b in enumerate(self.bones) if np.abs(self.q[:, j] - self.q[0, j]).max() > tol]
def to_ch(m):
    """Motion -> {bone: {'q': [N,4], 'l': [N,3] (root only)}} (the Blender-side channel dict of lib_v4.Clip)"""
    ch = {b: {"q": m.q[:, j].copy()} for j, b in enumerate(m.bones)}
    ch[m.root]["l"] = m.loc.copy(); return ch
def from_ch(ch, bones, root):
    q = np.stack([ch[b]["q"] for b in bones], 1); return hemi(q), np.asarray(ch[root]["l"], float)

# ---------------------------------------------------------------- CPU rig
class RigCPU:
    """forward kinematics + linear blend skinning of the exported rig (rig/rig.json + rig/mesh.npz), numpy only"""
    def __init__(self, rig_dir, bones=None):
        rig_dir = Path(rig_dir); d = json.loads((rig_dir / "rig.json").read_text())
        self.names = [b["name"] for b in d["bones"]]; self.nb = len(self.names)
        self.parents = np.array([-1 if b["parent"] is None else self.names.index(b["parent"]) for b in d["bones"]])
        rest = np.array([b["rest"] for b in d["bones"]], float)
        self.rest_rot, self.rest_head = rest[:, :3, :3], rest[:, :3, 3]; self.length = np.array([b["length"] for b in d["bones"]])
        rl = np.array([np.linalg.inv(rest[self.parents[j]]) @ rest[j] if self.parents[j] >= 0 else rest[j] for j in range(self.nb)])
        self.Rrl, self.trl = rl[:, :3, :3], rl[:, :3, 3]
        self.start = {n: np.array(v, float) for n, v in d["start_pose"].items()}
        self.world = np.array(d["armature_world"], float)
        self.mesh = np.load(rig_dir / "mesh.npz"); self.verts = self.mesh["verts"]; self.tris = self.mesh["tris"]
        self.idx = self.mesh["idx"]; self.wts = self.mesh["wts"]
        self.dom = self.idx[np.arange(len(self.idx)), np.argmax(self.wts, 1)]
        self.root_default = "tripo::Spine_0"
        self.order = [self.names.index(b) for b in bones] if bones else list(range(self.nb))
    def start_q(self):
        """start pose (the collapse end pose baked into model.blend) as [B,4] in rig order, and the root location in bone space"""
        q = np.stack([mat_to_q(self.start[n][:3, :3]) for n in self.names]); return q, self.start[self.root_default][:3, 3].copy()
    def fk(self, q, loc, root=None):
        """q [B,4] in rig order (w,x,y,z), loc [3] the root's bone-space location -> world (armature-space) rotation G [B,3,3] and head P [B,3]"""
        root = self.names.index(root or self.root_default); Rb = q_to_mat(q)
        G = np.zeros((self.nb, 3, 3)); P = np.zeros((self.nb, 3))
        for j in range(self.nb):
            par = self.parents[j]
            if par < 0: Gj = self.Rrl[j].copy(); Pj = self.trl[j].copy()
            else: Gj = G[par] @ self.Rrl[j]; Pj = P[par] + G[par] @ self.trl[j]
            if j == root:
                frame = (G[par] if par >= 0 else np.eye(3)) @ self.Rrl[j]; Pj = Pj + frame @ loc
            G[j] = Gj @ Rb[j]; P[j] = Pj
        return G, P
    def skin(self, q, loc, sel=None):
        G, P = self.fk(q, loc)
        Mk = np.einsum("nij,nkj->nik", G, self.rest_rot); tk = P - np.einsum("nij,nj->ni", Mk, self.rest_head)
        idx, wts, rest = (self.idx, self.wts, self.verts) if sel is None else (self.idx[sel], self.wts[sel], self.verts[sel])
        out = (np.einsum("vkij,vj->vki", Mk[idx], rest) + tk[idx]) * wts[:, :, None]
        out = out.sum(1)
        return out @ self.world[:3, :3].T + self.world[:3, 3]
    def heads_tails(self, q, loc):
        G, P = self.fk(q, loc); Tl = P + G[:, :, 1] * self.length[:, None]
        w = self.world; return P @ w[:3, :3].T + w[:3, 3], Tl @ w[:3, :3].T + w[:3, 3]
def reorder(m, rig):
    """Motion arrays in the rig's bone order"""
    j = [m.bones.index(n) for n in rig.names]; return m.q[:, j]
def cpu_dump(rig, m, out_npz, q=None, loc=None, every=1):
    """a dump_verts.py-format npz from channel arrays (no Blender): v [F,V,3] int16 in 0.1 mm, tri, vgroup, groups (bone names), frames,
    bones, bone_head / bone_tail [F,B,3], fps"""
    q = reorder(m, rig) if q is None else q; loc = m.loc if loc is None else loc
    frames = list(range(0, len(q), every)); V = np.empty((len(frames), len(rig.verts), 3), np.int16)
    BH = np.empty((len(frames), rig.nb, 3), np.float32); BT = np.empty_like(BH)
    for i, f in enumerate(frames):
        V[i] = np.round(rig.skin(q[f], loc[f]) * 1e4).astype(np.int16); BH[i], BT[i] = rig.heads_tails(q[f], loc[f])
    np.savez_compressed(out_npz, v=V, tri=rig.tris.astype(np.int32), vgroup=rig.dom.astype(np.int16), groups=np.array(rig.names),
                        frames=np.array(frames), bones=np.array(rig.names), bone_head=BH, bone_tail=BT, fps=np.array(24.0))
    return out_npz

# ---------------------------------------------------------------- analysis helpers
def push_start(m, rig, rise_cm=0.8, run=4, first=30):
    """End of the opening hold: the first frame (>= `first`) from which the mean height of the body (wings left out; every 7th vertex)
    stays `rise_cm` above its median over frames 0..first for `run` frames. Returns (frame, centroid height track [N])."""
    names = np.array(rig.names)[rig.dom]; sel = np.where(~np.char.startswith(names, "VeyrWing"))[0][::7]; q = reorder(m, rig)
    zc = np.array([rig.skin(q[f], m.loc[f], sel=sel)[:, 2].mean() for f in range(m.N)]); ref = float(np.median(zc[:first]))
    for i in range(first, m.N - run):
        if np.all(zc[i:i + run] > ref + rise_cm / 100.0): return i, zc
    return first, zc
def wing_bones(m): return [b for b in m.bones if b.startswith("VeyrWing")]
def twist_deg(m, bones=None):
    """max |b| (degrees) of every bone's Euler twist (excluding the root's rotation vector)"""
    out = {}
    for b in bones or m.bones:
        if b == m.root: continue
        out[b] = float(np.degrees(np.abs(q_to_eul(m.q[:, m.idx(b)])[:, 1]).max()))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
def euler_jump_deg(m, bones, frames=None):
    """biggest per-frame change of any Euler channel of the given bones: (deg, bone, frame f meaning f-1 -> f)"""
    best = (0.0, "", 0)
    for b in bones:
        e = np.degrees(q_to_eul(m.q[:, m.idx(b)])); d = np.abs(np.diff(e, axis=0))
        if frames is not None: d = d[[f - 1 for f in frames if 1 <= f < m.N]]
        if d.size:
            k = np.unravel_index(int(np.argmax(d)), d.shape); fr = (frames[k[0]] if frames is not None else k[0] + 1)
            if d.max() > best[0]: best = (float(d.max()), b, int(fr))
    return best

# ---------------------------------------------------------------- stages (pure functions on Motion copies)
def stage_trim_ease(m, start, ease=6, start_pose=None):
    """drop frames 0..start-1 (the opening hold's head) and ease the first `ease` frames from the collapse end pose (`start_pose` =
    (q [B,4] in m's bone order, loc [3])) onto the clip's pose at `start`; new frame 0 is the start pose exactly"""
    o = m.copy(); o.q = m.q[start:].copy(); o.loc = m.loc[start:].copy(); o.times = m.times[start:] - m.times[start]; o.N = len(o.q)
    if start_pose is not None and ease > 0:
        sq, sl = start_pose; w = sstep(np.arange(ease + 1) / float(ease))     # 0 at frame 0, 1 at frame `ease`
        for f in range(ease):
            o.q[f] = nlerp(sq, m.q[start + f], w[f]); o.loc[f] = (1 - w[f]) * sl + w[f] * m.loc[start + f]
    o.q = hemi(o.q); return o
def soft_cap(x, cap, knee):
    """identity up to `knee`, then a smooth saturation that reaches `cap` at infinity (knee < cap); sign kept"""
    s = np.sign(x); ax = np.abs(x); room = cap - knee
    return s * np.where(ax <= knee, ax, knee + room * np.tanh((ax - knee) / room))
def smooth_window(x, win, a, b, ramp):
    """smooth x [N] or [N,k] with a `win`-frame binomial window only inside [a, b] (blend weights ramp over `ramp` frames at both edges)"""
    n = len(x); k = np.array([1, 4, 6, 4, 1], float) if win == 5 else np.ones(win)
    k /= k.sum(); h = len(k) // 2; p = np.pad(x, [(h, h)] + [(0, 0)] * (x.ndim - 1), mode="edge")
    y = np.stack([np.convolve(p[:, j], k, mode="valid") for j in range(x.shape[1])], 1) if x.ndim == 2 else np.convolve(p, k, mode="valid")
    t = np.arange(n); w = np.clip(np.minimum((t - a + 1) / max(1, ramp), (b - t + 1) / max(1, ramp)), 0, 1); w = sstep(w)
    if x.ndim == 2: w = w[:, None]
    return (1 - w) * x + w * y
def relax_jumps(x, cap, a, b, iters=600):
    """smallest change that leaves no step over `cap` between frames a..b: a violating pair moves towards each other by half the excess
    (the whole excess on the pair's free end when the other is frame a or b, which stay where they are); x [N] or [N,k], any unit"""
    x = np.array(x, float)
    for _ in range(iters):
        worst = 0.0
        for i in range(max(a, 0), min(b, len(x) - 1)):
            d = x[i + 1] - x[i]; ex = np.maximum(np.abs(d) - cap, 0.0) * np.sign(d)
            if not np.any(ex): continue
            worst = max(worst, float(np.abs(ex).max()))
            lo_fixed, hi_fixed = i == a, i + 1 == b
            if lo_fixed and hi_fixed: continue
            if lo_fixed: x[i + 1] = x[i + 1] - ex
            elif hi_fixed: x[i] = x[i] + ex
            else: x[i] = x[i] + 0.5 * ex; x[i + 1] = x[i + 1] - 0.5 * ex
        if worst < 1e-6: break
    return x
def stage_wing_clean(m, a, b, twist_cap=25.0, knee=15.0, smooth=5, jump_cap=8.0, ramp=6, overrides=None):
    """frames a..b (clip indices): twist of the wing roots (Euler b) soft-capped to `twist_cap` deg, all wing channels smoothed with a
    `smooth`-frame window, no wing Euler step over `jump_cap` deg inside [a-ramp, b+ramp]. `overrides` {bone: Euler [N,3] radians}
    replaces the fitted Euler channels of those bones in a..b (the silhouette-solved wings of prep_wings_rl.py) before the cap."""
    o = m.copy(); rep = {"window": [a, b], "twist_cap_deg": twist_cap, "knee_deg": knee, "smooth_frames": smooth, "jump_cap_deg": jump_cap, "bones": {}}
    for bn in wing_bones(m):
        j = m.idx(bn); e = np.degrees(q_to_eul(m.q[:, j])); e0 = e.copy()
        if overrides and bn in overrides:
            ov = np.degrees(overrides[bn]); lo, hi = max(a, 0), min(b, m.N - 1); wgt = sstep(np.clip(np.minimum(np.arange(m.N) - lo + 1, hi - np.arange(m.N) + 1) / max(1, ramp), 0, 1))[:, None]
            e = (1 - wgt) * e + wgt * ov
        if bn.endswith("Root"):
            e[:, 1] = soft_cap(e[:, 1], twist_cap, knee)
        e = smooth_window(e, smooth, a, b, ramp)
        e = relax_jumps(e, jump_cap, max(0, a - ramp), min(m.N - 1, b + ramp))
        if bn.endswith("Root"): e[:, 1] = np.clip(e[:, 1], -twist_cap, twist_cap)
        o.q[:, j] = q_from_eul(*np.radians(e).T)
        rep["bones"][bn] = {"max_twist_before": round(float(np.abs(e0[a:b + 1, 1]).max()), 1), "max_twist_after": round(float(np.abs(e[a:b + 1, 1]).max()), 1),
                            "max_step_before": round(float(np.abs(np.diff(e0[max(0, a - ramp):b + ramp + 1], axis=0)).max()), 1),
                            "max_step_after": round(float(np.abs(np.diff(e[max(0, a - ramp):b + ramp + 1], axis=0)).max()), 1)}
    o.q = hemi(o.q); return o, rep
def find_plateaus(x, tol=0.15, min_len=8):
    """runs (start, end inclusive, value) where x stays within tol of its own max or min for min_len+ frames (a clamp at a joint limit)"""
    out = []
    for kind, ext in (("max", np.max(x)), ("min", np.min(x))):
        at = np.abs(x - ext) <= tol; i = 0
        while i < len(x):
            if at[i]:
                j = i
                while j + 1 < len(x) and at[j + 1]: j += 1
                if j - i + 1 >= min_len: out.append((i, j, float(ext), kind))
                i = j + 1
            else: i += 1
    return out
def stage_relax_limit(m, bones, margin=6.0, tol=0.15, min_len=8, smooth=5):
    """pull a bone's Euler channel off a joint limit: where it sits clamped at its own extreme for min_len+ frames, move it `margin`
    degrees to the interior (eased in and out), smoothing the result. Returns the Motion and a report per bone/channel."""
    o = m.copy(); rep = {}
    for bn in bones:
        if bn not in m.bones: continue
        j = m.idx(bn); e = np.degrees(q_to_eul(m.q[:, j])); changed = False
        for ax in (0, 1, 2):
            x = e[:, ax]
            if np.ptp(x) < 10.0: continue                     # a channel that barely moves has no limit to sit on
            for (s0, s1, val, kind) in find_plateaus(x, tol, min_len):
                n_pl = s1 - s0 + 1
                if n_pl < min_len: continue
                pl = np.zeros(len(x)); pl[np.abs(x - val) <= tol] = 1.0
                pl = np.convolve(pl, np.ones(5) / 5, mode="same")
                x2 = x + (-margin if kind == "max" else margin) * pl
                e[:, ax] = x2; x = x2; changed = True
                rep.setdefault(bn, []).append({"axis": "xyz"[ax], "kind": kind, "limit_deg": round(val, 2), "frames_at_limit": int(n_pl), "moved_deg": margin})
        if changed:
            e = smooth_window(e, smooth, 0, m.N - 1, 1)
            o.q[:, j] = q_from_eul(*np.radians(e).T)
    o.q = hemi(o.q); return o, rep
def stage_idle_blend(m, idle_q, idle_loc, n=8, n_wing=None, exact_last=True):
    """blend the last n frames into the idle pose (idle_q [B,4] in m's bone order, idle_loc [3]); the wing bones start folding into the idle
    wing pose earlier, over the last n_wing frames (the clip's fit folds the wings the other way round than the idle's fold: up to 176 deg
    apart on the elbow, so they get the longer window); the last frame equals the idle pose exactly. Returns (Motion, weights [N], wing weights [N])"""
    o = m.copy(); N = m.N; n_wing = n if n_wing is None else max(n, int(n_wing))
    def ramp(k):
        w = sstep((np.arange(N) - (N - k) + 1) / float(k)) if k > 0 else np.zeros(N)
        w[:max(N - k, 0)] = 0.0
        if exact_last: w[-1] = 1.0
        return w
    w, ww = ramp(n), ramp(n_wing)
    for j, b in enumerate(m.bones):
        wj = ww if b.startswith("VeyrWing") else w
        o.q[:, j] = nlerp(m.q[:, j], np.tile(idle_q[j], (N, 1)), wj)
    o.loc = (1 - w)[:, None] * m.loc + w[:, None] * np.asarray(idle_loc)[None]
    o.q = hemi(o.q); return o, w, ww
def pose_distance(q_a, q_b, bones):
    """per-bone rotation angle (deg) between two poses [B,4]; dict {bone: deg}"""
    d = qangle_deg(q_a, q_b); return {b: float(d[i]) for i, b in enumerate(bones)}
def load_pose_npz(path):
    """dragon/refine/v3/stance.npz (bones, q, l): the idle_v2 frame-0 channels"""
    z = np.load(path, allow_pickle=True); return {str(b): (q.astype(float), l.astype(float)) for b, q, l in zip(z["bones"], z["q"], z["l"])}
def pose_array(pose, bones, fallback_q):
    """{bone: (q, l)} -> [B,4] in `bones` order (bones the pose lacks keep fallback_q[j])"""
    return np.stack([pose[b][0] if b in pose else fallback_q[j] for j, b in enumerate(bones)])

# ---------------------------------------------------------------- floor lift (CPU skin: the same mesh Blender evaluates, checked against d_idle_v2.npz to 0.3 mm)
def _lift_vertices(rig):
    """vertices that must clear the floor: everything but the feet (planted by IK later) and the wings (they may touch / rest)"""
    names = np.array(rig.names)[rig.dom]
    foot = np.isin(names, ["bone_9", "tripo::1_Left_Limb_1", "bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3",
                           "tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4", "tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"])
    return np.where(~foot & ~np.char.startswith(names, "VeyrWing"))[0][::3]
def _foot_vertices(rig):
    names = np.array(rig.names)[rig.dom]
    foot = np.isin(names, ["bone_9", "tripo::1_Left_Limb_1", "bone_14", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3",
                           "tripo::1_Right_Limb_3", "tripo::1_Right_Limb_4", "tripo::0_Right_Limb_3", "tripo::0_Right_Limb_4"])
    return np.where(foot)[0][::2]
def stage_floor_lift(m, rig, floor=0.0015, fade_out=8, sigma=2.0, feet_floor=None):
    """raise the body (root location) on frames where a non-foot, non-wing vertex is under `floor`; smoothed, faded to 0 over the
    last `fade_out` frames so the clip still ends exactly on the idle pose. Returns (Motion, lift [N] metres)"""
    o = m.copy(); q = reorder(m, rig); sel = _lift_vertices(rig); need = np.zeros(m.N)
    for f in range(m.N): need[f] = max(0.0, floor - float(rig.skin(q[f], m.loc[f], sel=sel)[:, 2].min()))
    if feet_floor is not None:                      # 2026-10-31: the feet too (the idle blend dips a hind foot ~0.9 cm), with their own tolerance
        fsel = _foot_vertices(rig)
        for f in range(m.N): need[f] = max(need[f], feet_floor - float(rig.skin(q[f], m.loc[f], sel=fsel)[:, 2].min()))
    mx = np.array([need[max(0, i - 3):i + 4].max() for i in range(m.N)])
    k = np.exp(-.5 * (np.arange(-6, 7) / sigma) ** 2); k /= k.sum()
    lift = np.maximum(np.convolve(np.pad(mx, 6, mode="edge"), k, mode="valid"), need)
    if fade_out: lift = lift * (1 - sstep((np.arange(m.N) - (m.N - 1 - fade_out)) / float(fade_out)))
    ri = rig.names.index(rig.root_default); par = rig.parents[ri]
    for f in range(m.N):
        if lift[f] < 1e-7: continue
        G, _ = rig.fk(q[f], m.loc[f]); frame = (G[par] if par >= 0 else np.eye(3)) @ rig.Rrl[ri]
        o.loc[f] = m.loc[f] + frame.T @ np.array([0.0, 0.0, lift[f]])
    return o, lift
def start_pose_of(m, rig):
    sq, sl = rig.start_q(); j = [rig.names.index(b) for b in m.bones]; return sq[j], sl

# ---------------------------------------------------------------- the whole numpy side as one function (used by the Blender script and the CPU dry run)
DEFAULTS = dict(hold_s=1.25, ease=6, lead=4, idle_blend=8, wing_blend=16, wing_a=100, wing_b=134, twist_cap=25.0, knee=15.0, smooth=5, jump_cap=8.0, wing_ramp=6,
                relax_bones="tripo::0_Right_Limb_2,tripo::1_Right_Limb_2", relax_margin=6.0, floor=0.0055, start=-1, floor_fade=3, feet_floor=-0.001)
def numpy_pipeline(m, rig, idle_q, idle_loc, overrides=None, **kw):
    """m: raw Motion (145 frames), idle_q [B,4] / idle_loc [3] the idle_v2 frame-0 channels in m's bone order, overrides = solved wing Euler
    ({bone: [N,3] rad} of prep_wings_rl.py) or None. Order: knee relax -> wing clean (clip frames) -> trim + ease -> idle blend -> floor lift.
    Returns (Motion, report dict)"""
    p = dict(DEFAULTS); p.update(kw); rep = {"options": p}
    m1, rep["relax_limit"] = stage_relax_limit(m, [b for b in str(p["relax_bones"]).split(",") if b], margin=float(p["relax_margin"]))
    m2, rep["wing_clean"] = stage_wing_clean(m1, int(p["wing_a"]), int(p["wing_b"]), twist_cap=float(p["twist_cap"]), knee=float(p["knee"]),
                                             smooth=int(p["smooth"]), jump_cap=float(p["jump_cap"]), ramp=int(p["wing_ramp"]), overrides=overrides)
    if int(p["start"]) >= 0: start = int(p["start"]); ps = None
    else:
        ps, _ = push_start(m, rig); start = max(0, ps - int(p["lead"]) - int(round(float(p["hold_s"]) * 24)))
    rep["trim"] = {"push_start_frame": ps, "start": start, "kept_frames": m.N - start, "hold_frames_kept": int(round(float(p["hold_s"]) * 24)), "ease_frames": int(p["ease"])}
    m3 = stage_trim_ease(m2, start, int(p["ease"]), start_pose_of(m, rig))
    m4, w, ww = stage_idle_blend(m3, idle_q, idle_loc, int(p["idle_blend"]), int(p["wing_blend"]))
    rep["idle_blend"] = {"frames": int(p["idle_blend"]), "from_frame": int(m4.N - int(p["idle_blend"])), "wing_frames": max(int(p["idle_blend"]), int(p["wing_blend"])),
                         "wing_from_frame": int(m4.N - max(int(p["idle_blend"]), int(p["wing_blend"])))}
    m5, lift = stage_floor_lift(m4, rig, float(p["floor"]), fade_out=int(p["floor_fade"]), feet_floor=float(p["feet_floor"]))
    rep["floor_lift_cm_max"] = round(float(lift.max() * 100), 3)
    return m5, rep

# ---------------------------------------------------------------- planted-foot stretches
def foot_runs(low, vel, lo, vmax, gap=2, min_len=5):
    ok = (low < lo) & (vel < vmax); n = len(ok)
    for i in range(n):                                                  # close gaps of up to `gap` frames
        if not ok[i]:
            j = i
            while j < n and not ok[j]: j += 1
            if j < n and i > 0 and ok[i - 1] and j - i <= gap: ok[i:j] = True
    runs, i = [], 0
    while i < n:
        if ok[i]:
            j = i
            while j + 1 < n and ok[j + 1]: j += 1
            if j - i + 1 >= min_len: runs.append((i, j))
            i = j + 1
        else: i += 1
    return runs

def split_runs(h, runs, drift):
    """cut each planted stretch into segments inside which the foot head h [N,3] stays within `drift` metres of the segment's running mean
    (a stretch of slow creep becomes a few pins instead of one pin the body walks away from)"""
    segs = []
    for r0, r1 in runs:
        s = r0
        for f in range(r0 + 1, r1 + 2):
            if f > r1 or np.linalg.norm(h[f] - h[s:f].mean(0)) > drift: segs.append((s, f - 1)); s = f
    return segs

# ---------------------------------------------------------------- CPU entry points (no Blender)
def _info(fit):
    m = Motion(fit); proj, clip = project_of(fit); rig = RigCPU(proj / "rig")
    print(f"motion {m.path}\n  {m.N} frames at 24 fps (times {m.times[0]:.3f}..{m.times[-1]:.3f} s), {len(m.bones)} bones, root {m.root}")
    print("  bones:", ", ".join(m.bones)); print(f"  fitted ({len(m.fitted())}): not fitted -> {[b for b in m.bones if b not in m.fitted()]}")
    ps, zc = push_start(m, rig); print(f"  hold: body height flat to frame {ps - 4}, push-up onset ~{ps - 4} (centroid +0.8 cm at {ps}); keeps from {ps - 4 - 30} for hold_s=1.25")
    print("  max Euler twist (deg):", {b: round(v, 1) for b, v in list(twist_deg(m).items())[:5]})
    for bn in ("tripo::0_Right_Limb_2",):
        e = np.degrees(q_to_eul(m.q[:, m.idx(bn)]))
        for ax in range(3):
            if np.ptp(e[:, ax]) >= 10.0: print(f"  {bn} {'xyz'[ax]}: range {e[:, ax].min():.1f}..{e[:, ax].max():.1f} deg, plateaus {[(a, b, round(v, 1), k) for a, b, v, k in find_plateaus(e[:, ax])]}")
    wb = wing_bones(m); print("  biggest wing Euler step:", euler_jump_deg(m, wb))
def _kv(argv): return {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if "=" in a}
if __name__ == "__main__":
    import sys
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "info": _info(argv[0])
    elif cmd == "dump":                                  # dump <fit> <out.npz> : CPU dump of the raw fit
        m = Motion(argv[0]); proj, _ = project_of(argv[0]); cpu_dump(RigCPU(proj / "rig"), m, argv[1]); print("DUMPED", argv[1], m.N, "frames")
    elif cmd == "dry":                                   # dry <fit> <outdir> [key=value]: the numpy stages + CPU dump, report json
        fit, outdir, kv = argv[0], Path(argv[1]), _kv(argv[2:]); outdir.mkdir(parents=True, exist_ok=True)
        m = Motion(fit); proj, _ = project_of(fit); rig = RigCPU(proj / "rig"); sq, sl = start_pose_of(m, rig)
        idle = load_pose_npz(kv.get("idle_npz", "../dragon/refine/v3/stance.npz")); iq = pose_array(idle, m.bones, sq); il = idle["tripo::Spine_0"][1]
        ov = None
        if kv.get("wing_src") and Path(kv["wing_src"]).exists():
            z = np.load(kv["wing_src"], allow_pickle=True); ov = {str(b): z["euler"][:, i] for i, b in enumerate(z["bones"])}
        p = {k: type(DEFAULTS[k])(v) for k, v in kv.items() if k in DEFAULTS}
        mf, rep = numpy_pipeline(m, rig, iq, il, overrides=ov, **p)
        cpu_dump(rig, mf, outdir / "d_rise_lying_cpu.npz")
        np.savez_compressed(outdir / "rise_lying_cpu.channels.npz", bones=np.array(m.bones), q=mf.q, loc=mf.loc, idle_q=iq, idle_loc=il, start_q=sq, start_loc=sl)
        (outdir / "dry_report.json").write_text(json.dumps(rep, indent=1, default=float)); print("DRY", outdir, "frames", mf.N, json.dumps(rep["trim"]))
