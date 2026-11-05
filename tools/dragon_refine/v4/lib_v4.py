"""Round-2 (v4) helpers that run inside Blender: channel algebra, wing-beat layer, body bob, pose blends, offset IK planting.
Every edit works on per-frame channel arrays read from the v3 Action (lib_anim.read_channels) and is written back as per-frame keys.
"""
import bpy, math, sys
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector, Quaternion
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lib_anim as L

S0 = "tripo::Spine_0"
WSIDES = ("PosZ", "NegZ")                       # PosZ wing sits at -Y, NegZ at +Y (rig quirk)
WPARTS = ("Root", "Elbow", "Membrane", "Wrist", "Tip")
WB = {s: ["VeyrWing" + s + p for p in WPARTS] for s in WSIDES}
WING_BONES = WB["PosZ"] + WB["NegZ"]
TAIL = ["tripo::Tail_0", "tripo::Tail_1", "tripo::Tail_2"]
NECK_HEAD = ["bone_2", "bone_3", "bone_4", "bone_5", "tripo::Head_0", "tripo::Head_1", "tripo::Head_2", "tripo::Head_3", "bone_36", "bone_37"]
LEG_BONES = sum(L.FEET.values(), []) + ["tripo::1_Left_Limb_1", "tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"]
SIBS = {"bone_9": ["tripo::1_Left_Limb_1"], "bone_14": ["tripo::0_Left_Limb_2", "tripo::0_Left_Limb_3"], "tripo::1_Right_Limb_4": [], "tripo::0_Right_Limb_4": []}

# ---------------- quaternion helpers (w, x, y, z) ----------------
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
    a = np.atleast_2d(a); b = np.atleast_2d(b); w = np.asarray(w, float).reshape(-1, 1)
    out = (1 - w) * a + w * np.where((a * b).sum(1, keepdims=True) < 0, -b, b)
    return out / np.linalg.norm(out, axis=1, keepdims=True)
def fix_hemi(q):
    q = q.copy()
    for i in range(1, len(q)):
        if np.dot(q[i], q[i - 1]) < 0: q[i] = -q[i]
    return q
def sstep(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)
def minjerk(x):
    x = np.clip(x, 0.0, 1.0); return x ** 3 * (10 - 15 * x + 6 * x * x)
def ramp(N, a, b, f=sstep):
    """0 before frame a, 1 after frame b (eased)."""
    t = np.arange(N, dtype=float)
    return f((t - a) / max(1e-9, b - a))

class Clip:
    """A per-frame channel view of one Action on the armature."""
    def __init__(self, A, M, act, N=None):
        self.A, self.M, self.act, self.sc = A, M, act, bpy.context.scene
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        assert f0 == 0, f0
        self.N = N or (f1 + 1)
        self.ch = L.read_channels(act, list(range(self.N)))
        names = {g.index: g.name for g in M.vertex_groups}
        self.dom = np.array([names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else "none" for v in M.data.vertices])
        self.ensure_loc(S0)
    # ----- keys -----
    def ensure_loc(self, bone):
        cb = L.channelbag(self.act); path = f'pose.bones["{bone}"].location'
        for i in range(3):
            if cb.fcurves.find(path, index=i) is None:
                fc = cb.fcurves.new(path, index=i); fc.keyframe_points.add(1); fc.keyframe_points[0].interpolation = "LINEAR"
        self.ch.setdefault(bone, {})
        if "l" not in self.ch[bone]: self.ch[bone]["l"] = np.zeros((self.N, 3))
    def resize(self, N, src_index):
        """re-sample every channel by integer source indices (len N)."""
        idx = np.asarray(src_index, int)
        for b, d in self.ch.items():
            for k in list(d): d[k] = d[k][idx].copy()
        self.N = N
    def resample(self, srcpos):
        """re-time every channel: new frame i takes source position srcpos[i] (fractional, linear / nlerp)"""
        srcpos = np.asarray(srcpos, float); n = self.N
        i0 = np.clip(np.floor(srcpos).astype(int), 0, n - 1); i1 = np.clip(i0 + 1, 0, n - 1); w = srcpos - np.floor(srcpos)
        for b, d in self.ch.items():
            for k, v in list(d.items()):
                d[k] = fix_hemi(nlerp(v[i0], v[i1], w)) if k == "q" else (1 - w)[:, None] * v[i0] + w[:, None] * v[i1]
        self.N = len(srcpos)
    def apply(self):
        for b, d in self.ch.items():
            if "q" in d: d["q"] = fix_hemi(d["q"] / np.linalg.norm(d["q"], axis=1, keepdims=True))
        L.write_channels(self.act, self.ch, self.N)
        self.sc.frame_start, self.sc.frame_end = 0, self.N - 1
        self.sc.render.fps, self.sc.render.fps_base = 24, 1.0
    def bones_q(self): return [b for b in self.ch if "q" in self.ch[b]]
    # ----- evaluation -----
    def eval(self, f): return self.A.evaluated_get(L.frame_eval(self.sc, f))
    def heads(self, bones, frames=None):
        H, _, _ = L.world_points(self.A, list(range(self.N)) if frames is None else frames, self.sc, bones_head=bones); return H
    def mats(self, bones):
        _, _, M = L.world_points(self.A, list(range(self.N)), self.sc, mats=bones); return M
    def verts(self, f, idx=None):
        dg = L.frame_eval(self.sc, f); Me = self.M.evaluated_get(dg); me = Me.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        mw = np.array(Me.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]; Me.to_mesh_clear()
        return co if idx is None else co[idx]
    def idx_of(self, prefixes):
        return np.where(np.array([any(s.startswith(p) for p in prefixes) for s in self.dom]))[0]
    # ----- rotations in armature-rest axes (conjugated into the bone's local frame) -----
    def rest_conj(self, bone, vec_deg):
        v = Vector(vec_deg); ang = math.radians(v.length)
        if ang < 1e-9: return np.array([1.0, 0, 0, 0])
        R = self.A.pose.bones[bone].bone.matrix_local.to_3x3()
        return np.array((R.inverted() @ Quaternion(v.normalized(), ang).to_matrix() @ R).to_quaternion())
    def add_rot(self, bone, vecs):
        """vecs [N,3] degrees, axis-angle in armature rest axes, pre-multiplied on the local pose rotation"""
        q = self.ch[bone]["q"]
        for f in range(self.N):
            if np.abs(vecs[f]).max() > 1e-6: q[f] = qmul(self.rest_conj(bone, vecs[f]), q[f])
        self.ch[bone]["q"] = fix_hemi(q)
    # ----- world translation of Spine_0 (the body; tripo::Root carries no motion) -----
    def offset_body(self, d):
        """d [N,3] metres in world: move Spine_0's head by d on every frame (rotation unchanged)."""
        self.apply()
        A = self.A; pb = A.pose.bones[S0]; ql = self.ch[S0]["l"].copy()
        for f in range(self.N):
            if np.abs(d[f]).max() < 1e-7: continue
            Ae = self.eval(f); pbe = Ae.pose.bones[S0]
            b = pb.bone; rel = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
            Pm = pbe.parent.matrix if b.parent else Matrix.Identity(4)
            Bm = rel.inverted() @ Pm.inverted() @ (Matrix.Translation(Vector(d[f])) @ pbe.matrix)
            ql[f] = np.array(Bm.to_translation())
        self.ch[S0]["l"] = ql; self.apply()
    def body_z(self):
        return self.heads([S0])[S0][:, 2]
    # ----- pose blending -----
    def blend_to(self, pose, w, bones=None, loc=True):
        """per-frame blend weight w [N] towards pose {bone: (q, l)} (static) or {bone: (q[N], l[N])}"""
        for b in (bones or list(pose)):
            if b not in self.ch or b not in pose: continue
            pq, pl = pose[b]
            if "q" in self.ch[b]:
                tq = pq if np.ndim(pq) == 2 else np.tile(pq, (self.N, 1))
                self.ch[b]["q"] = fix_hemi(nlerp(self.ch[b]["q"], tq, w))
            if loc and "l" in self.ch[b] and pl is not None:
                tl = pl if np.ndim(pl) == 2 else np.tile(pl, (self.N, 1))
                self.ch[b]["l"] = (1 - w)[:, None] * self.ch[b]["l"] + w[:, None] * tl
    def lowpass(self, bones, kernel, cyclic=False, frames=None):
        k = np.asarray(kernel, float); k /= k.sum(); h = len(k) // 2
        for b in bones:
            for kind, v in self.ch.get(b, {}).items():
                if frames is None:
                    x = v[:-1] if cyclic else v
                    p = np.concatenate([x[-h:], x, x[:h]]) if cyclic else np.pad(x, ((h, h), (0, 0)), mode="edge")
                    y = np.stack([np.convolve(p[:, j], k, mode="valid") for j in range(p.shape[1])], 1)
                    if kind == "q": y /= np.linalg.norm(y, axis=1, keepdims=True)
                    if cyclic: y = np.vstack([y, y[:1]])
                    self.ch[b][kind] = fix_hemi(y) if kind == "q" else y
    def residual(self, bones, sigma=6.0):
        """high-pass detail of the fit (channel minus a gaussian low-pass), as per-frame rotation deltas"""
        hw = int(3 * sigma); g = np.exp(-.5 * (np.arange(-hw, hw + 1) / sigma) ** 2); g /= g.sum()
        out = {}
        for b in bones:
            if b not in self.ch or "q" not in self.ch[b]: continue
            q = self.ch[b]["q"]; p = np.pad(q, ((hw, hw), (0, 0)), mode="edge")
            lo = np.stack([np.convolve(p[:, j], g, mode="valid") for j in range(4)], 1); lo /= np.linalg.norm(lo, axis=1, keepdims=True)
            out[b] = np.array([qmul(q[f], qinv(lo[f])) for f in range(self.N)])
        return out
    # ----- feet -----
    def plant(self, targets, weights, sib_ref=0):
        """IK-bake the four feet. targets[foot] = list of armature-space 4x4 Matrix (foot bone pose) or None per frame;
        weights[foot] = [N] blend of the IK solution into the FK pose (0 = FK). Siblings (toes) follow the foot rigidly."""
        A, sc, N = self.A, self.sc, self.N
        self.apply()
        feet = list(L.FEET); allsibs = sum(SIBS.values(), [])
        MATS = self.mats(feet + allsibs)
        rel_sib = {s: (b, MATS[b][sib_ref].inverted() @ MATS[s][sib_ref]) for b in feet for s in SIBS[b]}
        mw = A.matrix_world.copy()
        empties = {}
        for b in feet:
            e = bpy.data.objects.new("IKT_" + b.replace(":", "_"), None); sc.collection.objects.link(e); empties[b] = e
            c = A.pose.bones[b].constraints.new("IK"); c.name = "TMP_PLANT"; c.target = e; c.use_tail = True; c.use_rotation = True
            c.chain_count = len(L.FEET[b]); c.iterations = 500; c.use_stretch = False
        chain = sum(L.FEET.values(), [])
        q = {bn: np.zeros((N, 4)) for bn in chain}; sq = {s: np.zeros((N, 4)) for s in allsibs}; sl = {s: np.zeros((N, 3)) for s in allsibs}
        err = {b: 0.0 for b in feet}
        def basis_from(Pmat, pb, Bmat):
            bb = pb.bone; rel = (bb.parent.matrix_local.inverted() @ bb.matrix_local) if bb.parent else bb.matrix_local
            Pm = Pmat if bb.parent else Matrix.Identity(4)
            return rel.inverted() @ Pm.inverted() @ Bmat
        for f in range(N):
            for b in feet:
                Mt = targets[b][f] if targets[b][f] is not None else MATS[b][f]
                tail_w = mw @ (Mt @ Vector((0, A.pose.bones[b].bone.length, 0)))
                empties[b].matrix_world = Matrix.Translation(tail_w) @ (mw @ Mt).to_quaternion().to_matrix().to_4x4()
            bpy.context.view_layer.update()
            Ae = self.eval(f)
            for bn in chain:
                pbe = Ae.pose.bones[bn]; q[bn][f] = np.array(basis_from(pbe.parent.matrix, pbe, pbe.matrix).to_quaternion())
            for b in feet:
                Mt = targets[b][f] if targets[b][f] is not None else MATS[b][f]
                if weights[b][f] > 0.99: err[b] = max(err[b], (Ae.pose.bones[b].matrix.to_translation() - Mt.translation).length)
                tm = {b: Mt}
                for s in SIBS[b]: tm[s] = Mt @ rel_sib[s][1]
                for s in SIBS[b]:
                    pbs = A.pose.bones[s]; Pm = tm[pbs.parent.name] if pbs.parent.name in tm else Ae.pose.bones[pbs.parent.name].matrix
                    Bm = basis_from(Pm, pbs, tm[s]); sq[s][f] = np.array(Bm.to_quaternion()); sl[s][f] = np.array(Bm.to_translation())
        for b in feet:
            for c in list(A.pose.bones[b].constraints):
                if c.name == "TMP_PLANT": A.pose.bones[b].constraints.remove(c)
        for e in empties.values(): bpy.data.objects.remove(e, do_unlink=True)
        foot_of = {bn: b for b in feet for bn in L.FEET[b]}
        for bn in chain:
            self.ch[bn]["q"] = fix_hemi(nlerp(self.ch[bn]["q"], fix_hemi(q[bn]), weights[foot_of[bn]]))
        for b in feet:
            for s in SIBS[b]:
                w = weights[b]; self.ensure_loc(s)
                bq = self.ch[s]["q"] if "q" in self.ch[s] else np.tile([1.0, 0, 0, 0], (N, 1))
                self.ch[s]["q"] = fix_hemi(nlerp(bq, fix_hemi(sq[s]), w)); self.ch[s]["l"] = (1 - w)[:, None] * self.ch[s]["l"] + w[:, None] * sl[s]
        self.apply()
        return {L.FOOT_LABEL[b]: round(err[b] * 100, 3) for b in feet}

def load_pose_npz(path):
    z = np.load(path, allow_pickle=True)
    return {str(b): (q, l) for b, q, l in zip(z["bones"], z["q"], z["l"])}
def action_channels(blend, action, frames=None):
    """read another blend's Action channels (appended as a temporary datablock, removed afterwards)"""
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.actions = [action]
    a = dst.actions[0]
    f1 = int(round(a.frame_range[1]))
    ch = L.read_channels(a, list(range(f1 + 1)) if frames is None else frames)
    bpy.data.actions.remove(a)
    return ch

# ---------------- wing beat ----------------
def beat_theta(u, down_frac=0.45):
    """u = beat phase in cycles (float array). +1 = top of the upstroke (u integer), -1 = bottom of the downstroke (u frac = down_frac).
    The downstroke is the faster stroke (down_frac of the cycle). C1 at both turn-arounds."""
    x = np.mod(u, 1.0)
    return np.where(x < down_frac, np.cos(np.pi * x / down_frac), -np.cos(np.pi * (x - down_frac) / (1 - down_frac)))
def periodic_bob(theta_fn, P, n=None):
    """body height (zero mean, unit peak-to-peak) for one beat cycle sampled at P frames: body upward acceleration is
    proportional to the wings' downward angular velocity (lift on the downstroke), integrated twice as a periodic signal."""
    n = n or int(P * 16)
    u = np.arange(n) / n; th = theta_fn(u)
    vel = np.gradient(th) * n                     # d theta / d cycle
    acc = -vel                                    # downstroke (theta falling) pushes the body up
    A = np.fft.rfft(acc); k = np.arange(len(A)); k[0] = 1
    Z = A / (-(2 * np.pi * k) ** 2); Z[0] = 0
    z = np.fft.irfft(Z, n)
    z /= (z.max() - z.min())
    return u, z
def wing_beat(clip, u, amp, root_bias=-9.0, root_amp=41.0, outer_bias=11.5, outer_amp=36.5, outer_lag=0.08):
    """add the beat to both wings. u [N] phase in cycles, amp [N] 0..1 envelope. Root rotates about the body's long axis
    (armature X) at the shoulder; elbow and wrist chains add an outer flex that lags by outer_lag cycles (whip)."""
    th = beat_theta(u); tho = beat_theta(u - outer_lag)
    r = amp * (root_bias + root_amp * th); o = amp * (outer_bias + outer_amp * tho)
    for side in WSIDES:
        sg = -1.0 if side == "PosZ" else 1.0      # positive = up for this wing
        vr = np.zeros((clip.N, 3)); vr[:, 0] = sg * r
        clip.add_rot("VeyrWing" + side + "Root", vr)
        vo = np.zeros((clip.N, 3)); vo[:, 0] = sg * o
        for part in ("Elbow", "Wrist"):
            clip.add_rot("VeyrWing" + side + part, vo)
    return th
def tail_follow(clip, zfun, gains=(-2.0, -2.8, -3.6), lags=(1, 2, 3), scale=0.02):
    """tail pitches against the body bob with a growing lag (inertia). zfun(t frames array) -> body offset in metres (defined for
    any t, so lagged frames before 0 exist); gains in degrees per `scale` metres"""
    N = clip.N
    for b, g, lag in zip(TAIL, gains, lags):
        zz = zfun(np.arange(N, dtype=float) - lag)
        v = np.zeros((N, 3)); v[:, 1] = g * zz / scale
        clip.add_rot(b, v)
