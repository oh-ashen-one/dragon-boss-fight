#!/usr/bin/env python3
"""RunStop join audit: run loop (any phase) -> RunStop with the in-game frozen-source local-space
linear blend (UVeyrSingleNodeInstance: BlendTwoPosesTogetherInPlace, alpha = t / BlendSeconds).
Metrics on all shared skin joints plus a sword-tip point on WeaponSocket, in game centimetres.
Usage: measure_runstop.py OUT.json RUN.glb RUN_GAMEPLAY_RATE RUNSTOP.glb [BLEND_SECONDS ...] [--offset SECONDS]"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from normalize_approved import GLB

CM = 240.0  # game cm per glTF metre (calibrated in measure_locomotion / prepare_knight_plan)
HZ = 120
TIP = np.array([0, 1.0, 0, 1.0])  # one rig unit along WeaponSocket +Y (blade axis of the fitted carries)


def locals_at(g, t, names):
    w, _ = g.sample(float(t))
    out = {}
    for n in names:
        i = g.names[n]
        p = g.parents.get(i)
        out[n] = (np.linalg.inv(w[p]) @ w[i]) if p is not None else w[i]
    return out, w


def compose(g, loc, names, base_world):
    W = {}

    def world(n):
        if n in W:
            return W[n]
        i = g.names[n]
        p = g.parents.get(i)
        pn = g.g["nodes"][p].get("name") if p is not None else None
        pw = world(pn) if pn in loc else (base_world[p] if p is not None else np.eye(4))
        W[n] = pw @ loc[n]
        return W[n]

    for n in names:
        world(n)
    return W


def split(m):
    s = np.linalg.norm(m[:3, :3], axis=0)
    return m[:3, 3], Rotation.from_matrix(m[:3, :3] / s), s


def blend(a, b, alpha):
    out = {}
    for n in a:
        ta, ra, sa = split(a[n])
        tb, rb, sb = split(b[n])
        r = Slerp([0, 1], Rotation.concatenate([ra, rb]))([alpha])[0]
        m = np.eye(4)
        m[:3, :3] = r.as_matrix() * (sa * (1 - alpha) + sb * alpha)
        m[:3, 3] = ta * (1 - alpha) + tb * alpha
        out[n] = m
    return out


def points(W, names):
    P = [W[n][:3, 3] for n in names]
    P.append((W["WeaponSocket"] @ TIP)[:3])
    return np.array(P)


def pose_points(g, t, names):
    loc, w = locals_at(g, t, names)
    return points(compose(g, loc, names, w), names)


def clip_peak_speed(g, rate, names, start, end):
    prev, peak = None, 0.0
    for t in np.arange(start, end, 1 / HZ):
        P = pose_points(g, t, names)
        if prev is not None:
            peak = max(peak, float(np.linalg.norm(P - prev, axis=1).max()) * HZ * rate * CM)
        prev = P
    return peak


def run(out, run_glb, run_rate, stop_glb, blends, offset=0.0):
    R, S = GLB(run_glb), GLB(stop_glb)
    names = [n for n in S.skin_names() if n in R.names]
    rd, sd = R.duration(), S.duration()
    s0, sw0 = locals_at(S, offset, names)
    S0 = points(compose(S, s0, names, sw0), names)
    phases = np.linspace(0, rd, 25)[:-1]
    run_peak = clip_peak_speed(R, run_rate, names, 0, rd)
    stop_peak = clip_peak_speed(S, 1.0, names, offset, sd)
    rows = []
    for p in phases:
        rl, rw = locals_at(R, p, names)
        RP = points(compose(R, rl, names, rw), names)
        gap = np.linalg.norm(RP - S0, axis=1) * CM
        ang = 0.0
        for n in names:
            _, ra, _ = split(rl[n])
            _, rb, _ = split(s0[n])
            ang = max(ang, float(np.degrees((ra.inv() * rb).magnitude())))
        row = {"runPhaseSeconds": round(float(p), 4), "maxPointGapCm": round(float(gap.max()), 2),
               "swordTipGapCm": round(float(gap[-1]), 2), "maxLocalRotationGapDeg": round(ang, 1)}
        for B in blends:
            prev, peak = None, 0.0
            for t in np.arange(0, B + 0.05, 1 / HZ):
                sl, sw = locals_at(S, min(offset + t, sd), names)
                alpha = min(1.0, t / B)
                P = points(compose(S, blend(rl, sl, alpha), names, sw), names)
                if prev is not None:
                    peak = max(peak, float(np.linalg.norm(P - prev, axis=1).max()) * HZ * CM)
                prev = P
            row["blend%.2fPeakSpeedCmS" % B] = round(peak, 1)
        rows.append(row)
    ref = max(run_peak, stop_peak)
    summary = {"run": Path(run_glb).name, "runGameplayRate": run_rate, "runStop": Path(stop_glb).name,
               "runStopStartOffsetSeconds": offset,
               "runPeakPointSpeedCmS": round(run_peak, 1), "runStopPeakPointSpeedCmS": round(stop_peak, 1),
               "clipPeakReferenceCmS": round(ref, 1),
               "maxPointGapCm": {"max": max(r["maxPointGapCm"] for r in rows),
                                 "median": float(np.median([r["maxPointGapCm"] for r in rows]))},
               "maxLocalRotationGapDeg": {"max": max(r["maxLocalRotationGapDeg"] for r in rows),
                                          "median": float(np.median([r["maxLocalRotationGapDeg"] for r in rows]))}}
    for B in blends:
        k = "blend%.2fPeakSpeedCmS" % B
        v = [r[k] for r in rows]
        summary[k] = {"max": max(v), "median": float(np.median(v)),
                      "phasesOverClipPeak": int(sum(x > ref for x in v)), "phases": len(v)}
    Path(out).write_text(json.dumps({"summary": summary, "phases": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    offset = 0.0
    if "--offset" in a:
        i = a.index("--offset")
        offset = float(a[i + 1])
        del a[i:i + 2]
    run(a[0], a[1], float(a[2]), a[3], [float(x) for x in a[4:]] or [0.10], offset)
