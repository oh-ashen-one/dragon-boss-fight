#!/usr/bin/env python3
"""Compute the corrected dragon skin weights (wing-root rings + left front paw) for the shared body (2026-11-18).

Inputs are the shipped clip GLBs (all carry the same 71,261-vertex body). Steps:
 1. measure skinning stretch (skin_stretch.py, bind reference, morphs included) over every clip;
 2. seed = vertices of triangles over --limit that touch a VeyrWing*Root-dominant corner; region = seed + --rings;
 3. fit region weights over sampled frames of every clip (skin_fit.py: convex stretch hinge + smoothness +
    stay-near-shipped + neutral-pose anchor on the idle clip), then on each vertex's best four joints;
 4. leg-0 paw toe weights from the mirrored leg-1 layout (skin_paw.py, --toe-share);
 5. write NPZ (joints/weights/names, GLB vertex order) and a JSON report of the fit.
No bones, geometry, UVs or morphs change.

python3 tools/dragon_refine/dragon_skin_fix.py --rig Dragon_Takeoff_DangleJoin_v2.glb --clips A.glb ... \
    --output fixed.npz --report fit.json
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skin_stretch as ss, skin_fit as sf, skin_paw as sp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rig', required=True); ap.add_argument('--clips', nargs='+', required=True)
    ap.add_argument('--output', type=Path, required=True); ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--limit', type=float, default=0.02); ap.add_argument('--rings', type=int, default=6)
    ap.add_argument('--fps', type=float, default=4); ap.add_argument('--smooth', type=float, default=0.05)
    ap.add_argument('--iterations', type=int, default=240); ap.add_argument('--toe-share', type=float, default=0.5)
    ap.add_argument('--no-paw', action='store_true'); ap.add_argument('--no-wings', action='store_true')
    a = ap.parse_args()
    rig = ss.Clip(a.rig); clips = [ss.Clip(f) for f in a.clips]
    for c in clips:
        assert np.array_equal(c.P, rig.P) and np.array_equal(c.J, rig.J) and np.array_equal(c.W, rig.W), c.path
    h = rig.P[:, 1].max() - rig.P[:, 1].min(); names = rig.names
    report = dict(rig=str(a.rig), clips=[str(c.path) for c in clips], args={k: v for k, v in vars(a).items() if k not in ('clips',)}, heightGltf=float(h))
    J, W = rig.J.copy(), rig.W.copy()
    if not a.no_wings:
        roots = [names.index('VeyrWingNegZRoot'), names.index('VeyrWingPosZRoot')]
        dom = rig.J[np.arange(len(rig.J)), rig.W.argmax(1)]
        worst = np.zeros(len(rig.I))
        for c in clips:
            _, w = ss.measure(c, rig.J, rig.W, 15, a.limit, 'shipped', 'bind'); worst = np.maximum(worst, w)
        bad = np.flatnonzero((worst > a.limit * h) & np.isin(dom[rig.I], roots).any(1))
        seeds = np.unique(rig.I[bad].ravel())
        fit = sf.Fit(rig, rig.J, rig.W, seeds, rings=a.rings, candidates=8)
        ct = [(c, c.times(a.fps)) for c in clips]
        fit.frames(ct)
        off = 0; neutral = []
        for c, ts in ct:
            if 'idle' in c.path.name.lower(): neutral += list(range(off, off + len(ts), 4))
            off += len(ts)
        t0 = time.time()
        w = fit.solve(h, smooth=a.smooth, stay=0.002, iterations=a.iterations, lr=0.02, neutral=neutral)
        w = fit.solve(h, smooth=a.smooth, stay=0.002, iterations=a.iterations // 2, lr=0.01, mask=fit.four(w), w0=w, neutral=neutral)
        J2, W2 = fit.result(w)
        keep = ~fit.free[fit.inv]; J2[keep] = rig.J[keep]; W2[keep] = rig.W[keep]
        J, W = J2, W2
        report['wings'] = dict(seedTriangles=int(len(bad)), seedVertices=int(len(seeds)), regionWeldedVertices=int(len(fit.R)),
                               changedVertices=int((~keep).sum()), frames=int(fit.Y.shape[0]), neutralFrames=len(neutral),
                               seconds=round(time.time() - t0, 1), last=fit.last)
    if not a.no_paw:
        J, W, info = sp.paw_weights(rig.P, J.astype(int), W.astype(np.float64), names, toe_scale=a.toe_share)
        report['paw'] = info
    np.savez(a.output, joints=J.astype(np.uint16), weights=W.astype(np.float32), names=np.array(names))
    a.report.write_text(json.dumps(report, indent=1) + '\n')
    print('WROTE', a.output, json.dumps(report.get('wings', {})), json.dumps(report.get('paw', {})))


if __name__ == '__main__':
    main()
