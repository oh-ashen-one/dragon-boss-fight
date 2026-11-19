#!/usr/bin/env python3
"""Fit the dragon camera proxy: one oriented box per bone, per mesh variant (camera fourth pass, 2026-11-19).

Input: the binary written by the editor commandlet VeyrCameraProxyExport (LOD0 render vertices, four skin
influences per vertex, triangles and the reference pose of the base dragon mesh and every clip mesh variant).
That file is character content and stays local (git-ignored).

Output: Unreal/Veyr/Source/Veyr/VeyrDragonCameraProxy.inl, derived numbers only: for each mesh variant and
bone, a box in that bone's reference space (centre, rotation, half extents, imported cm) that holds every
vertex weighted to the bone at or above --threshold (and every vertex whose largest weight is that bone).
The runtime moves the boxes with the evaluated bones and inflates them by a margin x dragon scale; the
in-game proof (-VeyrCameraProxyProof, audit) skins every vertex and reports the worst distance outside.

python3 tools/dragon_refine/camera_proxy.py --skin <DragonTrueSkin.bin> --output Unreal/Veyr/Source/Veyr/VeyrDragonCameraProxy.inl
"""
import argparse, json, struct
from pathlib import Path
import numpy as np


def read_skin(path):
    b = Path(path).read_bytes(); o = 0
    def u32():
        nonlocal o; v = struct.unpack_from('<I', b, o)[0]; o += 4; return v
    def string():
        nonlocal o; n = u32(); s = b[o:o + n].decode(); o += n; return s
    assert b[:4] == b'VTS1'; o = 4
    meshes = []
    for _ in range(u32()):
        name = string(); nb = u32(); bones = []
        for _ in range(nb):
            bn = string(); parent = struct.unpack('<i', struct.pack('<I', u32()))[0]
            vals = struct.unpack_from('<10f', b, o); o += 40
            bones.append((bn, parent, np.array(vals[0:3]), np.array(vals[3:7]), np.array(vals[7:10])))
        nv = u32()
        P = np.frombuffer(b, '<f4', nv * 3, o).reshape(nv, 3).astype(np.float64); o += nv * 12
        rec = np.dtype([('b', '<u2'), ('w', '<f4')])
        inf = np.frombuffer(b, rec, nv * 4, o).reshape(nv, 4); o += nv * 4 * 6
        ni = u32(); I = np.frombuffer(b, '<u4', ni, o).reshape(-1, 3); o += ni * 4
        meshes.append(dict(name=name, bones=bones, P=P, J=inf['b'].astype(int), W=inf['w'].astype(np.float64), I=I))
    return meshes


def qrot(q, v):
    """Rotate row vectors v by quaternion q=(x,y,z,w) (Unreal convention)."""
    x, y, z, w = q; u = np.array([x, y, z])
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def inv_transform(bone, P):
    _, _, T, Q, S = bone
    qi = np.array([-Q[0], -Q[1], -Q[2], Q[3]])
    return qrot(qi, P - T) / S


def rot_matrix_to_quat(R):
    """Columns of R are the box axes in bone space; returns (x,y,z,w) with R = rotation of the quaternion."""
    m = R; tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2; w = .25 * s; x = (m[2, 1] - m[1, 2]) / s; y = (m[0, 2] - m[2, 0]) / s; z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2; w = (m[2, 1] - m[1, 2]) / s; x = .25 * s; y = (m[0, 1] + m[1, 0]) / s; z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2; w = (m[0, 2] - m[2, 0]) / s; x = (m[0, 1] + m[1, 0]) / s; y = .25 * s; z = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2; w = (m[1, 0] - m[0, 1]) / s; x = (m[0, 2] + m[2, 0]) / s; y = (m[1, 2] + m[2, 1]) / s; z = .25 * s
    q = np.array([x, y, z, w]); return q / np.linalg.norm(q)


def fit_obb(X):
    """Small-volume oriented box: PCA axes, then rotating-calipers style 1-degree searches about each axis."""
    c = X.mean(0)
    if len(X) < 4:
        R = np.eye(3)
    else:
        _, _, Vt = np.linalg.svd(X - c, full_matrices=False); R = Vt.T
    if np.linalg.det(R) < 0: R[:, 2] *= -1
    def vol(R):
        L = (X - c) @ R; return np.prod(L.max(0) - L.min(0) + 1e-9)
    best = vol(R)
    angles = np.radians(np.arange(-45, 45.01, 1.0))
    for _ in range(3):
        improved = False
        for k in range(3):
            i, j = [a for a in range(3) if a != k]
            for a in angles:
                ca, sa = np.cos(a), np.sin(a)
                Rn = R.copy(); Rn[:, i] = ca * R[:, i] + sa * R[:, j]; Rn[:, j] = -sa * R[:, i] + ca * R[:, j]
                v = vol(Rn)
                if v < best * 0.999: best, R, improved = v, Rn, True
        if not improved: break
    L = (X - c) @ R; lo, hi = L.min(0), L.max(0)
    centre = c + R @ ((lo + hi) / 2); half = (hi - lo) / 2
    return centre, R, half


def kmeans(X, k, iters=12):
    """Plain k-means seeded with farthest points (deterministic)."""
    sel = [0]; d = np.linalg.norm(X - X[0], axis=1)
    for _ in range(k - 1):
        i = int(np.argmax(d)); sel.append(i); d = np.minimum(d, np.linalg.norm(X - X[i], axis=1))
    C = X[sel].copy()
    for _ in range(iters):
        lab = np.linalg.norm(X[:, None, :] - C[None], axis=2).argmin(1)
        for j in range(k):
            if (lab == j).any(): C[j] = X[lab == j].mean(0)
    return lab


def fit_boxes(X, max_split, gain):
    """One box, or up to max_split boxes when splitting the bone's vertices cuts the total volume by >= gain each step
    (a curved membrane or a long bent part becomes thin slabs instead of one blob)."""
    best = [fit_obb(X)]; best_vol = np.prod(best[0][2])
    for k in range(2, max_split + 1):
        if len(X) < 8 * k: break
        lab = kmeans(X, k)
        if any((lab == j).sum() < 4 for j in range(k)): continue
        boxes = [fit_obb(X[lab == j]) for j in range(k)]
        vol = sum(np.prod(b[2]) for b in boxes)
        if vol <= best_vol * (1 - gain): best, best_vol = boxes, vol
        else: break
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--skin', required=True); ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--threshold', type=float, default=0.1)
    ap.add_argument('--report', type=Path)
    ap.add_argument('--max-split', type=int, default=4); ap.add_argument('--split-gain', type=float, default=0.3)
    a = ap.parse_args()
    meshes = read_skin(a.skin)
    lines = ['// Generated by tools/dragon_refine/camera_proxy.py from the shipped dragon meshes (camera fourth pass).',
             '// Derived measurements only: per mesh variant and bone, one oriented box in the bone\'s reference',
             '// space (imported cm): centre, rotation (x,y,z,w), half extents. Every vertex weighted >= the threshold',
             f'// to a bone (or dominated by it) lies inside that bone\'s box at rest. Threshold {a.threshold}.',
             'struct FVeyrProxyBoxSource { const TCHAR* Bone; float C[3]; float Q[4]; float H[3]; };',
             'struct FVeyrProxyMeshSource { const TCHAR* Mesh; int32 First; int32 Count; };',
             'static const FVeyrProxyBoxSource GVeyrProxyBoxes[] = {']
    mesh_lines = []; report = {'threshold': a.threshold, 'meshes': []}; first = 0
    for m in meshes:
        bones, P, J, W = m['bones'], m['P'], m['J'], m['W']
        dominant = J[np.arange(len(P)), W.argmax(1)]
        count = 0; rows = []
        for bi, bone in enumerate(bones):
            mask = (dominant == bi) | ((J == bi) & (W >= a.threshold)).any(1)
            if mask.sum() == 0: continue
            X = inv_transform(bone, P[mask])
            for c, R, h in fit_boxes(X, a.max_split, a.split_gain):
                h = np.maximum(h, 0.01)
                q = rot_matrix_to_quat(R)
                lines.append(f'    {{TEXT("{bone[0]}"), {{{c[0]:.4f}f, {c[1]:.4f}f, {c[2]:.4f}f}}, {{{q[0]:.6f}f, {q[1]:.6f}f, {q[2]:.6f}f, {q[3]:.6f}f}}, {{{h[0]:.4f}f, {h[1]:.4f}f, {h[2]:.4f}f}}}},')
                hs = sorted(h)
                rows.append({'bone': bone[0], 'verts': int(mask.sum()), 'half': [round(float(x), 3) for x in h], 'thin': round(float(hs[0]), 3),
                             'mid': round(float(hs[1]), 3), 'long': round(float(hs[2]), 3), 'volume': round(float(8 * np.prod(h)), 2)})
                count += 1
        mesh_lines.append(f'    {{TEXT("{m["name"]}"), {first}, {count}}},'); first += count
        rows.sort(key=lambda r: -r['thin'])
        report['meshes'].append({'mesh': m['name'], 'verts': len(P), 'tris': len(m['I']), 'boxes': count,
                                 'restExtent': [round(float(x), 2) for x in (P.max(0) - P.min(0))],
                                 'fattest': rows[:6], 'wings': [r for r in rows if 'Wing' in r['bone']]})
    lines.append('};'); lines.append('static const FVeyrProxyMeshSource GVeyrProxyMeshes[] = {'); lines += mesh_lines; lines.append('};')
    a.output.write_text('\n'.join(lines) + '\n')
    text = json.dumps(report, indent=1)
    if a.report: a.report.write_text(text)
    for m in report['meshes']:
        print(m['mesh'], 'verts', m['verts'], 'tris', m['tris'], 'boxes', m['boxes'], 'rest extent (imported cm)', m['restExtent'])
        for r in m['fattest'][:3]: print('   fattest', r['bone'], 'half', r['half'], 'verts', r['verts'])
        for r in m['wings']: print('   wing', r['bone'], 'half', r['half'])


if __name__ == '__main__':
    main()
