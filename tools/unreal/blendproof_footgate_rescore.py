#!/usr/bin/env python3
"""Re-score a blendproof run's planted-foot gate offline (CPU only, reads blendproof-frames.jsonl).

Mirrors the 2026-10-30 foot gate in Unreal/Veyr/Source/Veyr/VeyrBlendProof.cpp:
  * contact reference per (clip, foot, bone) = 10th percentile of that clip's unblended heights, never above idle;
    while blending, the looser of source and target; clips with < 5 unblended frames use the idle reference
  * planted = toe AND ankle within 2.5 cm of the reference, in both frames of a pair
  * slide = max(toe, ankle) world planar travel / game time over a contiguous planted window >= 1/30 s
  * pairs touching the blink hidden window, zero dt and capsule teleports (> 2500 cm/s) break the window
Also prints the steady-locomotion stance check (planted-foot drift along the travel direction vs capsule speed),
which separates clip-speed mismatch from blend artefacts.

usage: blendproof_footgate_rescore.py <run dir containing blendproof-frames.jsonl> [limit_cm_per_s=60]
"""
import collections
import json
import math
import statistics
import sys
from pathlib import Path

MARGIN = 2.5
WINDOW = 1 / 30
TELEPORT = 2500.0
BONES = ("toeHeightCm", "ankleHeightCm")


def load(run):
    seqs = collections.OrderedDict()
    for line in (Path(run) / "blendproof-frames.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            seqs.setdefault(row["sequence"], []).append(row)
    return seqs


def references(frames):
    t0 = frames[0]["t"]
    idle = {(b, s): statistics.median([f[b][s] for f in frames if f["phase"] == "pre_idle" and f["t"] - t0 >= .3])
            for b in BONES for s in range(2)}
    by = collections.defaultdict(list)
    for f in frames:
        if not f["blending"]:
            by[f["clip"]].append(f)
    ref = {}
    for clip, rows in by.items():
        if len(rows) < 5:
            continue
        for b in BONES:
            for s in range(2):
                v = sorted(r[b][s] for r in rows)
                ref[(clip, b, s)] = min(idle[(b, s)], v[len(v) // 10])
    return idle, ref


def score(frames):
    idle, ref = references(frames)

    def planted(f, s):
        for b in BONES:
            r = ref.get((f["clip"], b, s), idle[(b, s)])
            if f["blending"]:
                r = max(r, ref.get((f["blendFrom"], b, s), idle[(b, s)]))
            if f[b][s] > r + MARGIN:
                return False
        return True

    out = []
    for s in range(2):
        win = []
        for i in range(1, len(frames)):
            f, p = frames[i], frames[i - 1]
            dt = f["dt"]
            ok = (not (f["blinkHidden"] or p["blinkHidden"]) and dt > 1e-3 and f["capsuleTravelCm"] / dt <= TELEPORT
                  and planted(f, s) and planted(p, s))
            if not ok:
                win = []
                continue
            win.append((max(f["toeTravelCm"][s], f["ankleTravelCm"][s]), dt, f, p))
            while len(win) > 1 and sum(w[1] for w in win[1:]) >= WINDOW:
                win.pop(0)
            span = sum(w[1] for w in win)
            if span < WINDOW - 1e-4:
                continue
            cm = sum(w[0] for w in win)
            kind = "transition" if any(w[2]["blending"] or w[3]["blending"] for w in win) else "steady"
            out.append(dict(v=cm / span, cm=cm, span=span, t=f["t"], foot="LR"[s], phase=f["phase"], clip=f["clip"],
                            src=f["blendFrom"] if f["blending"] else "", alpha=f["blendAlpha"], action=f["action"], kind=kind))
    return sorted(out, key=lambda r: -r["v"])


def stance_drift(frames):
    """Steady loop frames: planted-foot velocity component along the capsule's travel direction (cm/s)."""
    idle, ref = references(frames)
    along, speed, caps = [], [], []
    for i in range(1, len(frames)):
        f, p = frames[i], frames[i - 1]
        if f["blending"] or p["blending"] or f["clip"] != p["clip"] or not f["clip"].startswith(("Strafe", "Backpedal")):
            continue
        dt = f["dt"]
        cd = (f["capsule"][0] - p["capsule"][0], f["capsule"][1] - p["capsule"][1])
        cv = math.hypot(*cd) / dt
        if cv < 20:
            continue
        u = (cd[0] / (cv * dt), cd[1] / (cv * dt))
        for s in range(2):
            if not all(g[b][s] <= ref.get((g["clip"], b, s), idle[(b, s)]) + MARGIN for g in (f, p) for b in BONES):
                continue
            k = "LR"[s]
            d = [(f["ankle" + k][j] - p["ankle" + k][j] + f["toe" + k][j] - p["toe" + k][j]) / 2 for j in (0, 1)]
            along.append((d[0] * u[0] + d[1] * u[1]) / dt)
            speed.append(math.hypot(*d) / dt)
            caps.append(cv)
    if not along:
        return None
    return dict(pairs=len(along), capsule=statistics.median(caps), along=statistics.median(along),
                median=statistics.median(speed), p90=sorted(speed)[int(.9 * len(speed))])


def main():
    run = sys.argv[1]
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    passed = 0
    seqs = load(run)
    for name, frames in seqs.items():
        rows = score(frames)
        worst = rows[0] if rows else None
        steady = max([r["v"] for r in rows if r["kind"] == "steady"], default=0.0)
        trans = max([r["v"] for r in rows if r["kind"] == "transition"], default=0.0)
        ok = (worst["v"] if worst else 0.0) <= limit
        passed += ok
        print(f"{name:18s} {'PASS' if ok else 'FAIL'} max {worst['v'] if worst else 0:7.1f} cm/s  steady {steady:7.1f}  transition {trans:7.1f}")
        if worst:
            print(f"    worst t={worst['t']:.2f} {worst['foot']} {worst['cm']:.1f} cm in {worst['span']:.3f} s {worst['kind']} "
                  f"{worst['phase']} clip={worst['clip']}{' from=' + worst['src'] if worst['src'] else ''} a={worst['alpha']:.2f}")
        drift = stance_drift(frames)
        if drift:
            print(f"    steady stance: capsule {drift['capsule']:.0f} cm/s, planted-foot speed median {drift['median']:.1f} "
                  f"p90 {drift['p90']:.1f} cm/s, drift along travel {drift['along']:+.1f} cm/s over {drift['pairs']} pairs")
    print(f"passed {passed}/{len(seqs)} at {limit:.0f} cm/s")


if __name__ == "__main__":
    main()
