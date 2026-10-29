#!/usr/bin/env python3
"""Stance-foot speed and direction of in-place locomotion GLBs (glTF metres, mesh space).
Usage: measure_locomotion.py OUT.json GLB... ; prints raw m/s; calibrate to game cm/s separately."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from normalize_approved import GLB
def measure(path, rate=120):
    g = GLB(path); T = g.duration(); n = max(2, int(round(T * rate))); ts = np.linspace(0, T, n + 1)
    feet = {s: g.names[s + "Foot"] for s in ("Left", "Right")}; toes = {s: g.names[s + "ToeBase"] for s in ("Left", "Right")}
    P = {s: [] for s in feet}
    for t in ts:
        w, _ = g.sample(float(t))
        for s in feet: P[s].append((w[feet[s]][:3, 3] + w[toes[s]][:3, 3]) / 2)
    P = {s: np.array(v) for s, v in P.items()}
    floor = min(P[s][:, 1].min() for s in P)
    speeds, dirs = [], []
    for i in range(len(ts) - 1):
        s = min(P, key=lambda k: P[k][i, 1])
        if P[s][i, 1] - floor > 0.02: continue          # airborne / both feet high
        v = (P[s][i + 1] - P[s][i]) * rate; v[1] = 0
        sp = float(np.linalg.norm(v))
        if sp < 1e-4: continue
        speeds.append(sp); dirs.append(-v / sp)          # body moves opposite to the planted foot
    d = np.mean(dirs, axis=0) if dirs else np.zeros(3)
    return {"file": Path(path).name, "duration": T, "stanceSamples": len(speeds), "rawStanceSpeedMedian": float(np.median(speeds)) if speeds else 0.0,
            "rawStanceSpeedMean": float(np.mean(speeds)) if speeds else 0.0, "bodyDirectionMeshXZ": [round(float(d[0]), 3), round(float(d[2]), 3)]}
if __name__ == "__main__":
    rows = [measure(p) for p in sys.argv[2:]]
    Path(sys.argv[1]).write_text(json.dumps(rows, indent=1) + "\n")
    for r in rows: print(r)
