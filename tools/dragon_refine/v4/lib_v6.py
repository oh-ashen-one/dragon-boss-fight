"""Round-4 (v6) helpers that run inside Blender, on top of lib_v4 / lib_v5: per-bone time warps (retime one bone set
without touching the rest of the clip), occupied-cell area of projected vertices (a fast in-Blender stand-in for a mask
area inside a screen zone), the round-4 critic's frame-0-centre half-spans, and a feet re-plant onto the input Action's
own foot positions after layers are added on top of it."""
import numpy as np
import lib_v4 as V
import lib_v5 as L5
import lib_anim as L

def retime_bones(clip, bones, src):
    """bones' channels at new frame f <- the same channels sampled at (fractional) old frame src[f] (nlerp / lerp)"""
    N = clip.N; src = np.clip(np.asarray(src, float), 0, N - 1)
    i0 = np.floor(src).astype(int); i1 = np.minimum(i0 + 1, N - 1); fr = (src - i0)[:, None]
    for b in bones:
        if b not in clip.ch: continue
        d = clip.ch[b]
        if "q" in d:
            q = d["q"]; qa, qb = q[i0], q[i1]
            qb = np.where((qa * qb).sum(1, keepdims=True) < 0, -qb, qb)
            qn = (1 - fr) * qa + fr * qb; d["q"] = V.fix_hemi(qn / np.linalg.norm(qn, axis=1, keepdims=True))
        if "l" in d:
            l = d["l"]; d["l"] = (1 - fr) * l[i0] + fr * l[i1]

def warp_curve(N, a, b_new, b_old, c, lin=0.5):
    """old-frame index for each new frame: identity before a; new a..b_new -> old a..b_old with an eased curve (zero end
    slopes mixed with a linear share `lin` so the middle speed stays low); new b_new..c -> old b_old..c linearly; identity after c"""
    t = np.arange(N, dtype=float); src = t.copy()
    u = np.clip((t - a) / (b_new - a), 0, 1); s = lin * u + (1 - lin) * V.sstep(u)
    m1 = (t >= a) & (t <= b_new); src[m1] = a + (b_old - a) * s[m1]
    m2 = (t > b_new) & (t < c); src[m2] = b_old + (c - b_old) * (t[m2] - b_new) / (c - b_new)
    return src

def cell_area(p, zone=None, cell=2.0):
    """number of occupied cell x cell px cells of projected points p [n,2]; zone = (xmax, ymax): only x < xmax, y < ymax"""
    if zone is not None:
        k = (p[:, 0] < zone[0]) & (p[:, 1] < zone[1]); p = p[k]
    if not len(p): return 0
    c = np.floor(p / cell).astype(np.int64); return len(np.unique(c[:, 0] * 100000 + c[:, 1]))

def halves_f0(co, cx0, l0, r0, group="G", view="front"):
    """round-4 critic: half-spans about the FRAME-0 body centre (cx0 = frame-0 mask mean column), as ratios of frame 0"""
    x = L5.project(co, group, view)[:, 0]
    return (cx0 - float(x.min())) / (cx0 - l0), (float(x.max()) - cx0) / (r0 - cx0)

def replant(clip, mats0, w):
    """IK the four feet back onto their input-Action positions mats0 with weight w[N] (after layers moved the body)"""
    feet = list(L.FEET)
    T = {b: [mats0[b][f] if w[f] > 0 else None for f in range(clip.N)] for b in feet}
    return clip.plant(T, {b: np.asarray(w, float) for b in feet})
