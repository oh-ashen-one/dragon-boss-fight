#!/usr/bin/env python3
"""Measure dragon skin stretch per clip with the shipped weights or a replacement weight set (2026-11-18).

Every active dragon clip GLB carries the same 71,261-vertex body (identical POSITION / JOINTS_0 /
WEIGHTS_0 / indices). This CPU-skins each clip (linear blend, four influences, the same as the game)
at --fps and reports triangles whose longest edge grows by more than --limit of the body height
against the clip's first frame (the rule the fins diagnosis used) or, with --reference bind, against
the modelled rest mesh (stretch beyond the sculpted size; unfolding a folded wing does not count), grouped by the dominant bones of
the triangle's corners. With --weights NPZ (arrays joints, weights in the GLB's vertex order) the
same clips are skinned with the replacement weights, and the per-frame vertex offset between the
two weight sets is reported (0 at the bind pose by construction).

python3 tools/dragon_refine/skin_stretch.py --clips A.glb B.glb ... [--weights fixed.npz] --json out.json
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sole_points import load, accessor  # noqa: E402


NO_MORPH = False


def quat_mats(q):
    x, y, z, w = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
                     np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
                     np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1)], -2)


class Clip:
    def __init__(self, path):
        self.path = Path(path)
        js, b = load(path)
        self.js = js; nodes = js['nodes']; skin = js['skins'][0]
        self.joints = skin['joints']; self.names = [nodes[j]['name'] for j in self.joints]
        self.ibm = accessor(js, b, skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(np.float64)
        self.parent = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
        order = []; seen = set()
        def visit(i):
            if i in seen: return
            if i in self.parent: visit(self.parent[i])
            seen.add(i); order.append(i)
        for j in range(len(nodes)): visit(j)
        self.order = order
        self.tracks = {}
        anim = js['animations'][0]
        for ch in anim['channels']:
            sm = anim['samplers'][ch['sampler']]
            self.tracks[(ch['target']['node'], ch['target']['path'])] = (accessor(js, b, sm['input']).ravel().astype(np.float64), accessor(js, b, sm['output']).astype(np.float64))
        self.duration = max(v[0].max() for k, v in self.tracks.items() if k[1] != 'weights')
        p = js['meshes'][0]['primitives'][0]
        self.P = accessor(js, b, p['attributes']['POSITION']).astype(np.float64)
        self.J = accessor(js, b, p['attributes']['JOINTS_0']).astype(int)
        self.W = accessor(js, b, p['attributes']['WEIGHTS_0']).astype(np.float64)
        self.I = accessor(js, b, p['indices']).reshape(-1, 3).astype(int)
        # Morph targets (dense here): the game plays only the clip's animated weights (no channel = 0).
        self.D = np.array([accessor(js, b, t['POSITION']).astype(np.float64) for t in p.get('targets', [])])
        mesh_node = next(i for i, n in enumerate(nodes) if n.get('mesh') == 0)
        self.morph = self.tracks.get((mesh_node, 'weights'))
        if NO_MORPH: self.morph = None

    def rest(self, t):
        if self.morph is None or not len(self.D): return self.P
        ts, vs = self.morph; vs = vs.reshape(len(ts), -1)
        i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1)) if len(ts) > 1 else 0
        a = np.clip((t - ts[i - 1]) / max(ts[i] - ts[i - 1], 1e-9), 0, 1) if len(ts) > 1 else 1
        w = vs[i - 1] * (1 - a) + vs[i] * a if len(ts) > 1 else vs[0]
        return self.P + np.tensordot(w, self.D, 1)

    def sample(self, node, path, t, default):
        tr = self.tracks.get((node, path))
        if tr is None: return np.array(default, np.float64)
        ts, vs = tr
        if len(ts) == 1: return vs[0]
        i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1)); a = np.clip((t - ts[i - 1]) / max(ts[i] - ts[i - 1], 1e-9), 0, 1)
        v0, v1 = vs[i - 1], vs[i]
        if path == 'rotation' and np.dot(v0, v1) < 0: v1 = -v1
        v = v0 * (1 - a) + v1 * a
        return v / np.linalg.norm(v) if path == 'rotation' else v

    def world(self, t):
        nodes = self.js['nodes']; W = {}
        for i in self.order:
            n = nodes[i]
            L = np.eye(4)
            L[:3, :3] = quat_mats(self.sample(i, 'rotation', t, n.get('rotation', [0, 0, 0, 1]))) * self.sample(i, 'scale', t, n.get('scale', [1, 1, 1]))[None, :]
            L[:3, 3] = self.sample(i, 'translation', t, n.get('translation', [0, 0, 0]))
            W[i] = W[self.parent[i]] @ L if i in self.parent else L
        return np.array([W[j] for j in self.joints])

    def skin_matrices(self, t):
        return self.world(t) @ self.ibm

    def times(self, fps):
        return np.linspace(0, self.duration, int(self.duration * fps) + 1)


def skin(M, P, J, W):
    Ph = np.c_[P, np.ones(len(P))]
    out = np.zeros((len(P), 3))
    for k in range(J.shape[1]):
        out += W[:, k:k + 1] * np.einsum('nij,nj->ni', M[J[:, k]], Ph)[:, :3]
    return out


def edges(X, I):
    a, b, c = X[I[:, 0]], X[I[:, 1]], X[I[:, 2]]
    return np.stack([np.linalg.norm(a - b, axis=1), np.linalg.norm(b - c, axis=1), np.linalg.norm(c - a, axis=1)], 1)


def measure(clip, J, W, fps, limit, label, reference='frame0'):
    """Worst edge growth per triangle over the clip, against the clip's first frame or the bind pose."""
    height = clip.P[:, 1].max() - clip.P[:, 1].min()
    ts = clip.times(fps)
    ref = None; worst = np.zeros(len(clip.I)); when = np.zeros(len(clip.I))
    for t in ts:
        R = clip.rest(t)
        X = skin(clip.skin_matrices(t), R, J, W)
        E = edges(X, clip.I)
        if reference == 'bind': ref = edges(R, clip.I)  # the sculpted (morphed) shape at this time: skinning stretch only
        elif ref is None: ref = E
        g = (E - ref).max(1); m = g > worst; worst[m] = g[m]; when[m] = t
    dom = J[np.arange(len(J)), W.argmax(1)]
    bad = np.flatnonzero(worst > limit * height)
    groups = Counter(tuple(sorted(set(clip.names[dom[x]] for x in clip.I[i]))) for i in bad)
    top = bad[np.argsort(-worst[bad])][:8]
    return dict(label=label, clip=clip.path.name, duration=round(float(clip.duration), 3), frames=len(ts),
                height=round(float(height), 4), over=int(len(bad)),
                worstPct=round(float(worst.max() / height * 100), 2), worstAt=round(float(when[worst.argmax()]), 3),
                groups=[[n, list(k)] for k, n in groups.most_common(8)],
                top=[dict(pct=round(float(worst[i] / height * 100), 2), t=round(float(when[i]), 3), bones=[clip.names[dom[x]] for x in clip.I[i]]) for i in top]), worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clips', nargs='+', required=True)
    ap.add_argument('--weights', type=Path, help='NPZ with joints/weights (GLB vertex order) to compare')
    ap.add_argument('--fps', type=float, default=15)
    ap.add_argument('--limit', type=float, default=0.02)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--reference', choices=('frame0', 'bind'), default='frame0',
                    help='frame0: growth against the clip\'s first frame (fins diagnosis rule); bind: against the sculpted mesh with the same morph weights at the same time (skinning stretch only)')
    ap.add_argument('--no-morph', action='store_true', help='ignore morph animation (the A123 scratch rule)')
    a = ap.parse_args()
    global NO_MORPH
    NO_MORPH = a.no_morph
    alt = np.load(a.weights) if a.weights else None
    rows = []
    for path in a.clips:
        clip = Clip(path)
        r, wb = measure(clip, clip.J, clip.W, a.fps, a.limit, 'shipped', a.reference); rows.append(r)
        line = f"{clip.path.name:55s} shipped over={r['over']:4d} worst={r['worstPct']:5.2f}% @{r['worstAt']:.2f}"
        if alt is not None:
            J2, W2 = alt['joints'].astype(int), alt['weights'].astype(np.float64)
            r2, wa = measure(clip, J2, W2, a.fps, a.limit, 'fixed', a.reference)
            # Largest vertex offset between the two weight sets over the clip, and the per-triangle new stretch.
            off = 0.0
            for t in clip.times(a.fps)[::3]:
                M = clip.skin_matrices(t)
                R = clip.rest(t); off = max(off, float(np.linalg.norm(skin(M, R, clip.J, clip.W) - skin(M, R, J2, W2), axis=1).max()))
            h = r['height']
            r2['maxVertexOffsetPct'] = round(off / h * 100, 2)
            r2['newlyOver'] = int(np.sum((wa > a.limit * h) & (wb <= a.limit * h)))
            r2['grewMoreThan0p5pct'] = int(np.sum(wa - wb > 0.005 * h))
            rows.append(r2)
            line += f" | fixed over={r2['over']:4d} worst={r2['worstPct']:5.2f}% @{r2['worstAt']:.2f} newlyOver={r2['newlyOver']} offset={r2['maxVertexOffsetPct']}%"
        print(line, flush=True)
    if a.json: a.json.write_text(json.dumps(rows, indent=1) + '\n')


if __name__ == '__main__':
    main()
