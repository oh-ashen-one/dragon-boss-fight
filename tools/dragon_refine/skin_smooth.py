#!/usr/bin/env python3
"""Smooth and share dragon skin weights in a chosen region (2026-11-18). Pure NumPy, so the same code runs
inside Blender (author_dragon_skin.py) and on its own for measurement.

The body is split along UV seams (colocated twin vertices); the region graph welds twins by position,
so a seam never opens and twins always end with identical weights. Inside the region the 52-joint
weight vectors are relaxed toward the harmonic (Laplace) solution with the region's outer ring held
fixed, so the change blends continuously into the untouched skin; then each vertex keeps its four
largest influences and is renormalized (UE and glTF take four).
"""
import numpy as np


def weld(P, decimals=6):
    key = np.round(P, decimals)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.ravel()


def dense(J, W, n_joints):
    D = np.zeros((len(J), n_joints))
    for k in range(J.shape[1]):
        np.add.at(D, (np.arange(len(J)), J[:, k]), W[:, k])
    return D


def sparse4(D):
    order = np.argsort(-D, axis=1)[:, :4]
    W = np.take_along_axis(D, order, 1)
    W[W < 1e-4] = 0
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
    J = np.where(W > 0, order, 0)
    # deterministic layout: descending weight, unused slots joint 0 weight 0
    return J.astype(np.uint16), W.astype(np.float32)


def adjacency(I, inv, n):
    e = np.concatenate([I[:, [0, 1]], I[:, [1, 2]], I[:, [2, 0]]])
    e = inv[e]
    e = e[e[:, 0] != e[:, 1]]
    e = np.unique(np.sort(e, 1), axis=0)
    return e


def neighbours_mean(D, e, n):
    S = np.zeros_like(D); c = np.zeros(n)
    np.add.at(S, e[:, 0], D[e[:, 1]]); np.add.at(S, e[:, 1], D[e[:, 0]])
    np.add.at(c, e[:, 0], 1); np.add.at(c, e[:, 1], 1)
    return S / np.maximum(c, 1)[:, None]


def dilate(mask, e, rings):
    m = mask.copy()
    for _ in range(rings):
        nb = m.copy(); nb[e[m[e[:, 0]], 1]] = True; nb[e[m[e[:, 1]], 0]] = True
        m = nb
    return m


def ring_distance(mask, e, limit):
    """Graph rings from the seed set (0 inside), capped at limit+1."""
    d = np.full(len(mask), limit + 1); d[mask] = 0; cur = mask.copy()
    for r in range(1, limit + 1):
        nb = cur.copy(); nb[e[cur[e[:, 0]], 1]] = True; nb[e[cur[e[:, 1]], 0]] = True
        new = nb & (d > limit); d[new] = r; cur = nb
    return d


def smooth_region(P, I, J, W, n_joints, seed_vertices, rings=6, iterations=200, lam=0.5, falloff=True):
    """Return new (J, W) in the original vertex order. seed_vertices: indices (original order)."""
    inv = weld(P); n = inv.max() + 1
    Dv = dense(J, W, n_joints)
    # welded weights: average the twins (they should already agree)
    D = np.zeros((n, n_joints)); c = np.zeros(n)
    np.add.at(D, inv, Dv); np.add.at(c, inv, 1); D /= c[:, None]
    e = adjacency(I, inv, n)
    seed = np.zeros(n, bool); seed[inv[seed_vertices]] = True
    dist = ring_distance(seed, e, rings)
    free = dist <= rings                       # vertices that may change
    # per-vertex blend strength: full at the seeds, fading to 0 at the outer ring (smooth hand-off)
    s = np.clip(1 - dist / (rings + 1), 0, 1) if falloff else free.astype(float)
    s = s * s * (3 - 2 * s)
    D0 = D.copy()
    for _ in range(iterations):
        M = neighbours_mean(D, e, n)
        D = np.where(free[:, None], D + lam * s[:, None] * (M - D), D0)
    D = D / np.maximum(D.sum(1, keepdims=True), 1e-12)
    J2, W2 = sparse4(D[inv])
    changed = np.flatnonzero(free[inv])
    keep = ~free[inv]
    J2[keep] = J[keep]; W2[keep] = W[keep]
    return J2, W2, dict(welded=int(n), seeds=int(seed.sum()), free=int(free.sum()), changedVertices=int(len(changed)))
