"""CPU stand-in for the review renders: project the dumped mesh (dump_verts.py) through the exact review cameras of
render_clip_v3.py (G = ground, T = tall, K = extra tall; lens 50 mm, sensor 36 mm, 960x540) and rasterise it.
No Blender, no GPU. Masks are exact silhouettes; `gray` is a synthetic shaded image (per-face pseudo-random albedo, the review
sun, background plate) used only for the critic's per-frame-change family of metrics, calibrated against the critic's render numbers.
"""
import numpy as np, cv2, math, os
W, H = 960, 540
F_PX = 50.0 / 36.0 * W
CAMS = {
    "G": ((0.0, 0.0, 0.24), {"front": (2.30, 0.00, 0.50), "left": (0.00, 2.30, 0.40), "threequarter": (1.65, 1.65, 0.80)}),
    "T": ((0.0, 0.0, 0.40), {"front": (3.10, 0.00, 0.55), "left": (0.00, 3.10, 0.45), "threequarter": (2.20, 2.20, 0.95)}),
    "K": ((0.0, 0.0, 0.62), {"front": (4.20, 0.00, 0.70), "left": (0.00, 4.20, 0.65), "threequarter": (3.00, 3.00, 1.15)}),
}
def cam(group, view):
    tgt, d = CAMS[group]; p = np.array(d[view], float); t = np.array(tgt, float)
    zc = p - t; zc /= np.linalg.norm(zc)                     # camera +Z points away from the target (-Z looks at it)
    up = np.array([0, 0, 1.0]); yc = up - up.dot(zc) * zc; yc /= np.linalg.norm(yc)
    xc = np.cross(yc, zc)
    return p, np.stack([xc, yc, zc])                         # rows = camera axes in world
def project(V, group, view):
    p, R = cam(group, view)
    c = (V - p) @ R.T
    z = -c[..., 2]
    x = W / 2 + F_PX * c[..., 0] / z; y = H / 2 - F_PX * c[..., 1] / z
    return np.stack([x, y], -1), z
def load(path):
    z = np.load(path, allow_pickle=True)
    d = {k: z[k] for k in z.files}
    d["V"] = d["v"].astype(np.float32) * 1e-4
    names = [str(s) for s in d["groups"]]
    g = d["vgroup"]
    d["vname"] = np.array([names[i] if i >= 0 else "none" for i in g])
    d["bones"] = [str(b) for b in d["bones"]]
    tri = d["tri"]
    wv = np.char.startswith(d["vname"], "VeyrWing")
    d["wing_tri"] = wv[tri].all(1)
    return d
def bone(d, name, tail=False):
    return (d["bone_tail"] if tail else d["bone_head"])[:, d["bones"].index(name)]
_rng = np.random.default_rng(7)
_ALB = {}
SUN = None
def _sun():
    global SUN
    if SUN is None:
        ax, ay, az = math.radians(50), math.radians(10), math.radians(35)
        Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
        Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
        Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
        SUN = -(Rz @ Ry @ Rx @ np.array([0, 0, -1.0]))      # direction towards the sun
    return SUN
_BG = {}
def plate(group, view):
    k = (group, view)
    if k not in _BG:
        f = os.environ.get("CRITIC_PLATES", "") + f"/bg_{group}_{view}.npy"
        _BG[k] = np.load(f).astype(np.float32) if os.path.exists(f) else np.full((H, W), 140.0, np.float32)
    return _BG[k]
def zbuffer(P, z, tri):
    """vectorised point-sampled z-buffer: face id per pixel (pixel centres at integer coordinates, as cv2.fillPoly)"""
    X = P[tri]; Z = z[tri]
    x0 = np.floor(X[..., 0].min(1)).astype(int); x1 = np.ceil(X[..., 0].max(1)).astype(int)
    y0 = np.floor(X[..., 1].min(1)).astype(int); y1 = np.ceil(X[..., 1].max(1)).astype(int)
    ext = np.maximum(x1 - x0, y1 - y0) + 1
    best = np.full(H * W, np.inf, np.float32); fid = np.full(H * W, -1, np.int64)
    np.seterr(divide="ignore", invalid="ignore")
    for K in (4, 8, 16, 32, 64):
        sel = np.where((ext <= K) & (ext > K // 2 if K > 4 else ext <= K))[0]
        if not len(sel): continue
        g = np.arange(K); gx, gy = np.meshgrid(g, g); gx = gx.ravel(); gy = gy.ravel()
        for ch in np.array_split(sel, max(1, len(sel) * K * K // 4_000_000 + 1)):
            px = x0[ch, None] + gx[None]; py = y0[ch, None] + gy[None]
            a, b, c = X[ch, 0], X[ch, 1], X[ch, 2]
            def ef(p, q, x, y): return (q[:, 0:1] - p[:, 0:1]) * (y - p[:, 1:2]) - (q[:, 1:2] - p[:, 1:2]) * (x - p[:, 0:1])
            area = ef(a, b, c[:, 0:1], c[:, 1:2])
            w0 = ef(b, c, px, py) / area; w1 = ef(c, a, px, py) / area; w2 = 1 - w0 - w1
            ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (px >= 0) & (px < W) & (py >= 0) & (py < H) & (np.abs(area) > 1e-9)
            zz = w0 * Z[ch, 0:1] + w1 * Z[ch, 1:2] + w2 * Z[ch, 2:3]
            ti = np.broadcast_to(ch[:, None], px.shape)
            pix = (py * W + px)[ins]; zv = zz[ins].astype(np.float32); tv = ti[ins]
            if not len(pix): continue
            o = np.lexsort((zv, pix)); pix, zv, tv = pix[o], zv[o], tv[o]
            first = np.r_[True, pix[1:] != pix[:-1]]
            pix, zv, tv = pix[first], zv[first], tv[first]
            better = zv < best[pix]
            best[pix[better]] = zv[better]; fid[pix[better]] = tv[better]
    return fid.reshape(H, W), best.reshape(H, W)
def render(d, group, view, frames=None, shaded=True):
    """returns masks [F,H,W] bool, wing masks [F,H,W] bool (visible wing faces), gray [F,H,W] float32 (or None)"""
    V = d["V"]; tri = d["tri"]; nT = len(tri)
    frames = range(len(V)) if frames is None else frames
    if nT not in _ALB: _ALB[nT] = _rng.uniform(0.25, 0.85, nT).astype(np.float32)
    alb = _ALB[nT]; sun = _sun(); bg = plate(group, view)
    p, R = cam(group, view)
    Ms, Ws, Gs = [], [], []
    for i in frames:
        P, z = project(V[i], group, view)
        pts = np.round(P * 16).astype(np.int32)                # 4 fractional bits for cv2 sub-pixel fill
        T = pts[tri]
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, list(T), 1, lineType=cv2.LINE_8, shift=4)
        Ms.append(m.astype(bool))
        if not shaded:
            wm = np.zeros((H, W), np.uint8); cv2.fillPoly(wm, list(T[d["wing_tri"]]), 1, shift=4); Ws.append(wm.astype(bool) & Ms[-1]); continue
        X = V[i][tri]; n = np.cross(X[:, 1] - X[:, 0], X[:, 2] - X[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        cen = X.mean(1); vdir = p - cen; facing = (n * vdir).sum(1)
        n = np.where(facing[:, None] < 0, -n, n)
        lam = np.clip(n @ sun, 0, 1)
        val = (255 * alb * (0.30 + 0.70 * lam)).astype(np.float32)
        fid, _ = zbuffer(P, z, tri)
        cov = fid >= 0
        g = bg.copy(); g[cov] = val[fid[cov]]
        hole = Ms[-1] & ~cov                                    # sub-pixel slivers the sampler missed: nearest covered value
        if hole.any():
            g8 = np.clip(g, 0, 255).astype(np.uint8); g = cv2.inpaint(g8, hole.astype(np.uint8), 2, cv2.INPAINT_TELEA).astype(np.float32)
        idimg = fid
        Gs.append(g)
        Ws.append(cov & d["wing_tri"][np.maximum(idimg, 0)])
    return np.stack(Ms), np.stack(Ws), (np.stack(Gs) if Gs else None)
