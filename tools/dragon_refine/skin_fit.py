#!/usr/bin/env python3
"""Fit smoother, shared dragon skin weights in a region so the skin stops stretching (2026-11-18).

Pure NumPy; runs inside Blender (author_dragon_skin.py) or on its own. Skeleton, mesh, morphs and
clips are untouched: only per-vertex joint weights change, inside a region grown from the triangles
that stretch.

For a vertex v with candidate joints c, the skinned position is linear in its weights:
x_v(t) = sum_c w_vc * (M_c(t) p_v(t)). An edge's length is therefore convex in the weights, and so is
the squared stretch hinge max(0, |x_a - x_b| - (1 + margin) * L_rest)^2. The objective (convex) is
    sum over sampled frames of every clip of the stretch hinge on region edges
  + smooth * sum over region edges |w_a - w_b|^2            (weights vary smoothly, shared by neighbours)
  + stay * sum over region vertices |w_v - w0_v|^2           (stay near the shipped weights)
  + rest_pose * sum over neutral frames |x_v(w) - x_v(w0)|^2 (the idle look does not move)
minimised by projected gradient descent (momentum) on the probability simplex, first with up to --candidates joints per
vertex (union of the joints its neighbourhood already uses), then again on each vertex's best four.
UV-seam twins are welded so they share one weight vector.
"""
import numpy as np

from skin_smooth import weld, dense, adjacency, ring_distance


def project_simplex(V, mask):
    """Euclidean projection of each row onto {w >= 0, sum w = 1, w = 0 where mask is False}."""
    X = np.where(mask, V, -1e9)
    U = -np.sort(-X, axis=1)
    css = np.cumsum(np.where(U > -1e8, U, 0), axis=1) - 1
    k = np.arange(1, V.shape[1] + 1)
    cond = (U - css / k > 0) & (U > -1e8)
    rho = cond.shape[1] - 1 - np.argmax(cond[:, ::-1], axis=1)
    theta = css[np.arange(len(V)), rho] / (rho + 1)
    return np.where(mask, np.maximum(V - theta[:, None], 0), 0)


class Fit:
    def __init__(self, clip, J, W, seed_vertices, rings=4, candidates=8):
        self.clip = clip
        P, I = clip.P, clip.I
        self.inv = weld(P); n = self.inv.max() + 1; self.n = n
        nj = len(clip.names)
        Dv = dense(J, W, nj)
        D = np.zeros((n, nj)); c = np.zeros(n)
        np.add.at(D, self.inv, Dv); np.add.at(c, self.inv, 1); D /= c[:, None]
        self.D0 = D
        self.rep = np.zeros(n, int); self.rep[self.inv] = np.arange(len(P))  # one original vertex per welded vertex
        e = adjacency(I, self.inv, n); self.e_all = e
        seed = np.zeros(n, bool); seed[self.inv[seed_vertices]] = True
        dist = ring_distance(seed, e, rings)
        self.free = dist <= rings
        R = np.flatnonzero(self.free); self.R = R
        # candidate joints: those the vertex's 3-ring neighbourhood already uses, strongest first
        near = ring_distance(self.free, e, 3) <= 3
        local = np.zeros(n); local[R] = 1
        acc = D.copy()
        for _ in range(3):
            S = acc.copy(); np.add.at(S, e[:, 0], acc[e[:, 1]]); np.add.at(S, e[:, 1], acc[e[:, 0]]); acc = S
        acc = acc[R] + 1e3 * D[R]  # always keep the joints the vertex already has
        order = np.argsort(-acc, axis=1)[:, :candidates]
        self.cand = order
        self.cmask = np.take_along_axis(acc, order, 1) > 1e-6
        # edges touching the region; endpoints outside stay fixed
        touch = self.free[e[:, 0]] | self.free[e[:, 1]]
        self.e = e[touch]
        self.pos = -np.ones(n, int); self.pos[R] = np.arange(len(R))
        self.near_unused = near

    def frames(self, clips_times):
        """clips_times: list of (Clip, times). Precompute candidate-joint positions for region and fixed endpoints."""
        R = self.R; e = self.e
        ends = np.unique(e.ravel()); fixed = ends[~self.free[ends]]
        self.fixed = fixed; self.fpos = -np.ones(self.n, int); self.fpos[fixed] = np.arange(len(fixed))
        Y, F, L = [], [], []
        for clip, times in clips_times:
            for t in times:
                M = clip.skin_matrices(t)[:, :3, :]  # (joints, 3, 4)
                rest = clip.rest(t)
                pr = np.c_[rest[self.rep[R]], np.ones(len(R))]
                Y.append(np.einsum('vcij,vj->vci', M[self.cand], pr).astype(np.float32))
                pf = np.c_[rest[self.rep[fixed]], np.ones(len(fixed))]
                Dfix = self.D0[fixed]
                F.append(np.einsum('vk,kij,vj->vi', Dfix, M, pf).astype(np.float32))
                a, b = e[:, 0], e[:, 1]
                L.append(np.linalg.norm(rest[self.rep[a]] - rest[self.rep[b]], axis=1).astype(np.float32))
        self.Y = np.array(Y); self.F = np.array(F); self.L = np.array(L)

    def positions(self, w):
        Xr = np.einsum('fvci,vc->fvi', self.Y, w)
        return Xr

    def endpoint(self, Xr, idx):
        out = np.empty((Xr.shape[0], len(idx), 3), np.float32)
        inr = self.free[idx]
        out[:, inr] = Xr[:, self.pos[idx[inr]]]
        out[:, ~inr] = self.F[:, self.fpos[idx[~inr]]]
        return out

    def solve(self, height, margin=0.0, smooth=2.0, stay=0.02, iterations=600, lr=0.02, mask=None, w0=None, neutral=()):
        R = self.R; e = self.e
        if mask is None: mask = self.cmask
        W0 = np.take_along_axis(self.D0[R], self.cand, 1)
        w = project_simplex(W0 if w0 is None else w0, mask)
        a, b = e[:, 0], e[:, 1]
        ra, rb = self.free[a], self.free[b]
        inner = ra & rb
        m1 = np.zeros(2); m2 = np.zeros(2)
        mt = np.zeros_like(w); vt = np.zeros_like(w)
        scale = 1.0 / (height * height)
        # neutral-pose anchor: positions at the neutral frames with the shipped weights
        Xn0 = self.positions(W0)[list(neutral)] if len(neutral) else None
        # joint-space smoothness only between region vertices that share candidate joints: map to dense joints
        nj = self.D0.shape[1]
        for it in range(iterations):
            Xr = self.positions(w)
            xa = self.endpoint(Xr, a); xb = self.endpoint(Xr, b)
            d = xa - xb; ln = np.linalg.norm(d, axis=2) + 1e-12
            h = np.maximum(ln - (1 + margin) * self.L, 0)
            u = d / ln[..., None]
            gx = (2 * scale / Xr.shape[0]) * h[..., None] * u  # dLoss/dxa ; dLoss/dxb = -gx (mean over frames)
            G = np.zeros((Xr.shape[0], len(R), 3), np.float32)
            np.add.at(G, (slice(None), self.pos[a[ra]]), gx[:, ra])
            np.add.at(G, (slice(None), self.pos[b[rb]]), -gx[:, rb])
            grad = np.einsum('fvi,fvci->vc', G, self.Y)
            if Xn0 is not None:
                Gn = 2 * scale * 10.0 / len(neutral) * (Xr[list(neutral)] - Xn0)
                grad += np.einsum('fvi,fvci->vc', Gn, self.Y[list(neutral)])
            # smoothness in dense joint space
            Dw = np.zeros((len(R), nj)); np.put_along_axis(Dw, self.cand, w, 1)
            ia, ib = self.pos[a[inner]], self.pos[b[inner]]
            diff = Dw[ia] - Dw[ib]
            Gd = np.zeros_like(Dw); np.add.at(Gd, ia, 2 * smooth * diff); np.add.at(Gd, ib, -2 * smooth * diff)
            grad += np.take_along_axis(Gd, self.cand, 1)
            grad += 2 * stay * (w - W0)
            # plain projected gradient with momentum: per-coordinate (Adam-style) scaling would turn the
            # step into a near-uniform shift that the simplex projection removes.
            # The step is scaled globally so the largest single weight change is lr (decaying), which keeps the
            # direction and is independent of how many frames the loss sums.
            mt = 0.8 * mt + grad
            rate = lr * (1 - 0.9 * it / max(iterations - 1, 1))
            w = project_simplex(w - rate * mt / max(float(np.abs(mt).max()), 1e-12), mask)
            if it % 100 == 0 or it == iterations - 1:
                self.last = dict(it=it, stretchLoss=float((h * h).sum() * scale), worstPct=float(h.max() / height * 100) if margin == 0 else None)
        return w

    def four(self, w):
        """Keep each vertex's four strongest candidates."""
        keep = np.zeros_like(self.cmask)
        top = np.argsort(-w, axis=1)[:, :4]
        np.put_along_axis(keep, top, True, 1)
        return keep & self.cmask & (w > 1e-4) | (keep & (w == w.max(1, keepdims=True)))

    def result(self, w):
        """New (J, W) in the original vertex order: region from w, the rest untouched."""
        D = self.D0.copy()
        Dw = np.zeros((len(self.R), D.shape[1])); np.put_along_axis(Dw, self.cand, w, 1)
        D[self.R] = Dw
        Dv = D[self.inv]
        order = np.argsort(-Dv, axis=1)[:, :4]
        W = np.take_along_axis(Dv, order, 1); W[W < 1e-5] = 0
        W = W / W.sum(1, keepdims=True)
        J = np.where(W > 0, order, 0)
        return J.astype(np.uint16), W.astype(np.float32)
