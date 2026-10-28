#!/usr/bin/env python3
"""Build the boss move data (moves.json, boxes.json, tempo.json, sounds.json) from sample files.

    python3 tools/movedata/build_moves.py Local/movedata/samples/idle.sample.npz \
        Local/movedata/samples/roar.sample.npz --loop idle --out Data/dragon

Pure numpy; no Blender. Samples come from sample_action.py (rig-scale Unreal cm). This script applies the
game scale (default from the rig map: the presentation's component scale) so every number in the JSON is
in game units: centimetres, seconds (clip time), degrees, metres per second. Frames are 24 fps.

Actor frame: x forward along the dragon's nose, y to its right, z up, origin = the rig origin on the floor
under the dragon at frame 0, carried along the root track. Positions "in the actor frame at that moment"
have the track position and yaw of that frame removed.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

DEFAULTS = {
    "threshold_mps": 5.0,        # a part is hot while it moves at least this fast
    "exit_ratio": 0.9,           # ...and stays hot until it drops under threshold * exit_ratio
    "min_frames": 2,             # shorter runs are noise
    "merge_gap_frames": 1,       # runs separated by at most this many cold frames merge
    "plant_tol_cm": 4.0,         # foot is down within this height of its own floor
    "plant_speed_cms": 120.0,    # ...and moving slower than this horizontally
    "lift_cm": 8.0,              # foot is up above this height
    "max_hover_cm": 15.0,        # a foot whose lowest point never comes within this of the floor never plants
    "slide_cms": 15.0,           # a planted foot sliding faster than this...
    "slide_frames": 4,           # ...for this many frames is a slide
    "shock_min_mps": 3.0,        # a touchdown at least this fast is a floor shock
    "shock_radius_base_cm": 150.0,
    "shock_radius_per_mps": 20.0,
    "shock_radius_max_cm": 450.0,
    "body_down_cm": 4.0,
    "body_lift_cm": 8.0,
    "body_contact_min_mps": 1.0,
    "capsule_cover": 0.75,       # each hurt capsule aims to hold this share of its part's vertices
    "track_every": 6,            # boxes.json reference track: capsule centres every Nth frame
}

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rel(p):
    """Repository-relative path when the file lives in this repository (keeps the JSON machine-neutral)."""
    p = str(p)
    if os.path.isabs(p) and os.path.commonpath([p, REPO]) == REPO:
        return os.path.relpath(p, REPO)
    return p


UNITS = ("Unreal: cm, s (clip time), deg, m/s; x forward, y right, z up, yaw deg (+ toward +y). "
         "Blender (x, y, z) m = (100 x, -100 y, 100 z) cm at rig scale, then x game_scale.")


# ----------------------------------------------------------------------------- sample loading

def load_sample(path):
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    for k, v in list(d.items()):
        if v.dtype.kind == "U":
            d[k] = v.tolist() if v.ndim else str(v)
    d["rig_map"] = json.loads(d["rig_map"])
    d["path"] = path
    return d


def r1(x, nd=1):
    """Round numbers (or nested lists) for compact JSON."""
    if isinstance(x, (list, tuple, np.ndarray)):
        return [r1(v, nd) for v in x]
    v = float(x)
    return round(v, nd) if math.isfinite(v) else None


# ----------------------------------------------------------------------------- kinematics

def speed_mps(pos_cm, fps):
    """Per-frame speed (m/s) of a point track (n, 3) in cm, central differences."""
    pos_cm = np.asarray(pos_cm, dtype=np.float64)
    if len(pos_cm) < 2:
        return np.zeros(len(pos_cm))
    return np.linalg.norm(np.gradient(pos_cm, axis=0), axis=1) * fps / 100.0


def hspeed_cms(pos_cm, fps):
    pos_cm = np.asarray(pos_cm, dtype=np.float64)
    if len(pos_cm) < 2:
        return np.zeros(len(pos_cm))
    return np.linalg.norm(np.gradient(pos_cm[:, :2], axis=0), axis=1) * fps


def runs(mask):
    """[(first, last)] inclusive index runs where mask is True."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1)); start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def find_windows(speed, fps, threshold, exit_ratio=0.9, min_frames=2, merge_gap=1):
    """Hot windows of one part from its speed curve (m/s per frame).

    A window opens where speed reaches `threshold` and closes when it drops under threshold*exit_ratio.
    t0/t1 are interpolated to the crossing between frames; peak_t is refined with a parabola through the
    peak frame and its neighbours. Returns dicts with f0, f1 (inclusive frames), t0, t1, peak_t, peak_v,
    peak_f.
    """
    s = np.asarray(speed, dtype=np.float64)
    n = len(s)
    lo = threshold * exit_ratio
    spans, i = [], 0
    while i < n:
        if s[i] >= threshold:
            j = i
            while j + 1 < n and s[j + 1] >= lo:
                j += 1
            spans.append([i, j]); i = j + 1
        else:
            i += 1
    merged = []
    for sp in spans:
        if merged and sp[0] - merged[-1][1] - 1 <= merge_gap:
            merged[-1][1] = sp[1]
        else:
            merged.append(sp)
    out = []
    dt = 1.0 / fps
    for f0, f1 in merged:
        if f1 - f0 + 1 < min_frames:
            continue
        t0 = f0 * dt
        if f0 > 0 and s[f0] > s[f0 - 1]:
            t0 = (f0 - 1 + np.clip((threshold - s[f0 - 1]) / (s[f0] - s[f0 - 1]), 0, 1)) * dt
        t1 = f1 * dt
        if f1 + 1 < n and s[f1] > s[f1 + 1]:
            t1 = (f1 + np.clip((s[f1] - lo) / (s[f1] - s[f1 + 1]), 0, 1)) * dt
        pf = f0 + int(np.argmax(s[f0:f1 + 1]))
        pt, pv = float(pf), float(s[pf])
        if 0 < pf < n - 1 and s[pf] > s[pf - 1] and s[pf] > s[pf + 1]:
            a, b, c = s[pf - 1], s[pf], s[pf + 1]
            den = a - 2 * b + c
            if den < 0:
                off = 0.5 * (a - c) / den
                if abs(off) <= 1:
                    pt = pf + off
                    pv = b - 0.25 * (a - c) * off
        out.append({"f0": f0, "f1": f1, "t0": t0, "t1": t1, "peak_f": pf, "peak_t": pt * dt, "peak_v": pv})
    return out


def track_from_root(root_mat, scale):
    """Per-frame [x_cm, y_cm, yaw_deg] of the track bone relative to frame 0 (Unreal actor frame of frame 0)."""
    R0 = root_mat[0, :3, :3]
    p0 = root_mat[0, :3, 3]
    yaw = []
    for m in root_mat:
        f = (m[:3, :3] @ R0.T) @ np.array([1.0, 0.0, 0.0])
        yaw.append(math.atan2(f[1], f[0]))
    yaw = np.degrees(np.unwrap(np.array(yaw)))
    xy = (root_mat[:, :2, 3] - p0[:2]) * scale
    return np.column_stack([xy, yaw])


def to_actor(pos, track):
    """World (rig) positions (n, ..., 3) -> actor frame of each frame, given track (n, 3) [x, y, yaw]."""
    pos = np.asarray(pos, dtype=np.float64)
    out = pos.copy()
    yaw = np.radians(track[:, 2])
    c, s = np.cos(-yaw), np.sin(-yaw)
    shape = (len(track),) + (1,) * (pos.ndim - 2)
    c = c.reshape(shape); s = s.reshape(shape)
    dx = pos[..., 0] - track[:, 0].reshape(shape)
    dy = pos[..., 1] - track[:, 1].reshape(shape)
    out[..., 0] = c * dx - s * dy
    out[..., 1] = s * dx + c * dy
    return out


def twist_deg(local_quat):
    """Axial twist (deg) of each bone about its own Y axis from basis quaternions (n, B, 4) w,x,y,z."""
    w, y = local_quat[..., 0], local_quat[..., 2]
    t = np.degrees(2.0 * np.arctan2(y, w))
    return (t + 180.0) % 360.0 - 180.0


# ----------------------------------------------------------------------------- contacts and stances

def floor_states(h, hs, down, lift, speed_cap=None):
    """Down/up state per frame with hysteresis. h = height above floor (cm), hs = horizontal speed (cm/s)."""
    n = len(h)
    st = np.zeros(n, dtype=bool)
    cur = h[0] <= down and (speed_cap is None or hs[0] < speed_cap)
    for i in range(n):
        if cur:
            if h[i] > lift:
                cur = False
        else:
            if h[i] <= down and (speed_cap is None or hs[i] < speed_cap):
                cur = True
        st[i] = cur
    return st


def foot_analysis(name, bone, low_z, sole_pos, track, fps, cfg, move_floor):
    """Stances, step contacts and slides of one foot. low_z: lowest-vertex height (cm, game); sole_pos: (n,3)."""
    n = len(low_z)
    fmin = float(low_z.min())
    if fmin > move_floor + cfg["max_hover_cm"]:
        return {"stances": [], "contacts": [], "slides": 0, "never_planted": True, "floor_cm": None}
    h = low_z - fmin
    hs = hspeed_cms(sole_pos, fps)
    down = floor_states(h, hs, cfg["plant_tol_cm"], cfg["lift_cm"], cfg["plant_speed_cms"])
    sp = speed_mps(sole_pos, fps)
    act = to_actor(sole_pos, track)
    stances, contacts, slides = [], [], 0
    for a, b in runs(down):
        if b - a + 1 < 2:
            continue
        d = np.linalg.norm(sole_pos[a:b + 1, :2] - sole_pos[a, :2], axis=1)
        sl = [r for r in runs(hs[a:b + 1] > cfg["slide_cms"]) if r[1] - r[0] + 1 >= cfg["slide_frames"]]
        slides += len(sl)
        stances.append({"foot": name, "bone": bone, "f0": a, "f1": b, "t0": r1(a / fps, 3), "t1": r1(b / fps, 3),
                        "frames": b - a + 1, "at": r1(act[a]), "drift_cm": r1(d.max(), 2),
                        "slides": len(sl)})
        if a > 0:  # a touchdown, not the starting stance
            v = float(sp[max(0, a - 3):a + 1].max())
            contacts.append({"t": r1(a / fps, 3), "frame": a, "bone": bone, "kind": "step", "speed": r1(v, 2),
                             "at": r1(act[a])})
    return {"stances": stances, "contacts": contacts, "slides": slides, "never_planted": False,
            "floor_cm": r1(fmin, 2)}


def body_contacts(name, low_pos, track, fps, cfg, move_floor):
    h = low_pos[:, 2] - move_floor
    down = floor_states(h, np.zeros(len(h)), cfg["body_down_cm"], cfg["body_lift_cm"])
    sp = speed_mps(low_pos, fps)
    act = to_actor(low_pos, track)
    out = []
    for a, b in runs(down):
        if a == 0:
            continue
        v = float(sp[max(0, a - 3):a + 1].max())
        if v >= cfg["body_contact_min_mps"]:
            out.append({"t": r1(a / fps, 3), "frame": a, "bone": name, "kind": "body", "speed": r1(v, 2),
                        "at": r1(act[a])})
    return out


def shock_radius(speed, cfg):
    return min(cfg["shock_radius_max_cm"], cfg["shock_radius_base_cm"] + cfg["shock_radius_per_mps"] * speed)


# ----------------------------------------------------------------------------- one move

def build_move(d, cfg, part_thresholds, loop=False, scale=None):
    rig = d["rig_map"]
    scale = float(scale if scale is not None else rig.get("game_scale", 1.0))
    fps = float(d["fps"])
    n = len(d["times"])
    names = d["part_names"]
    P = d["parts"] * scale
    pidx = {nm: i for i, nm in enumerate(names)}
    bones = d["bone_names"]
    bidx = {nm: i for i, nm in enumerate(bones)}

    track_bone = rig.get("track_bone", rig.get("root_bone"))
    if track_bone == d.get("root_name", track_bone):
        tm = d["root_mat"]
    else:
        tm = np.zeros((n, 4, 4)); tm[:, :3, :3] = d["rots"][:, bidx[track_bone]]
        tm[:, :3, 3] = d["heads"][:, bidx[track_bone]]
    track = track_from_root(tm, scale)

    # windows on every listed part
    windows, attacks, part_tracks = [], [], {}
    specs = [(p, s, True) for p, s in rig.get("attack_parts", {}).items()] + \
            [(p, s, False) for p, s in rig.get("window_only_parts", {}).items()]
    for part, spec, is_attack in specs:
        pos = P[:, pidx[spec["point"]]]
        sp = speed_mps(pos, fps)
        thr = float(part_thresholds.get(part, spec.get("threshold_mps", cfg["threshold_mps"])))
        act = to_actor(pos, track)
        if is_attack:
            part_tracks[part] = [r1(list(act[i]) + [sp[i]]) for i in range(n)]
        for w in find_windows(sp, fps, thr, cfg["exit_ratio"], cfg["min_frames"], cfg["merge_gap_frames"]):
            at = act[w["peak_f"]]
            rec = {"part": part, "t0": r1(w["t0"], 3), "t1": r1(w["t1"], 3), "peak_t": r1(w["peak_t"], 3),
                   "peak_v": r1(w["peak_v"], 2), "at_peak": r1(at)}
            # a window that peaks on the clip's first frame is motion carried in from before the move
            # (the pose was already moving at frame 0), not a blow: keep it in windows only
            carry_in = w["peak_f"] == 0
            windows.append(dict(rec, point=spec["point"], f0=w["f0"], f1=w["f1"], threshold=thr, carry_in=carry_in))
            if is_attack and not carry_in:
                attacks.append(rec)
    attacks.sort(key=lambda a: (a["t0"], a["part"]))
    windows.sort(key=lambda a: (a["t0"], a["part"]))

    # feet: lowest vertex height for planting, vertex-tracked sole centroid for drift
    lows = d["lows"] * scale
    lidx = {nm: i for i, nm in enumerate(d["low_names"])}
    feet = rig["feet"]
    foot_low = {f: lows[:, lidx["foot_" + f], 2] for f in feet}
    move_floor = float(min(v.min() for v in foot_low.values()))
    stances, contacts, slides, feet_q = [], [], 0, {}
    for f, spec in feet.items():
        sole = P[:, pidx["sole_" + f]]
        fa = foot_analysis(f, spec["bone"], foot_low[f], sole, track, fps, cfg, move_floor)
        stances += fa["stances"]; contacts += fa["contacts"]; slides += fa["slides"]
        feet_q[f] = {"lowest_cm": r1(foot_low[f].min(), 2), "above_floor_cm": r1(foot_low[f].min() - move_floor, 2),
                     "height_range_cm": r1(np.ptp(foot_low[f]), 2), "never_planted": fa["never_planted"],
                     "max_drift_cm": r1(max([s["drift_cm"] for s in fa["stances"]] or [0.0]), 2)}
    for name in rig.get("body_low", {}):
        contacts += body_contacts(name, lows[:, lidx[name]], track, fps, cfg, move_floor)
    contacts.sort(key=lambda c: c["t"])
    shocks = [{"t": c["t"], "bone": c["bone"], "at": [c["at"][0], c["at"][1], 0.0], "speed": c["speed"],
               "radius": r1(shock_radius(c["speed"], cfg))}
              for c in contacts if c["speed"] is not None and c["speed"] >= cfg["shock_min_mps"]]

    # quality numbers
    tw = twist_deg(d["local_quat"])
    bi, fi = np.unravel_index(np.argmax(np.abs(tw).T), (tw.shape[1], tw.shape[0]))
    twist_jump = np.abs(np.diff(tw, axis=0)) if n > 1 else np.zeros((1, tw.shape[1]))
    twist_jump = np.minimum(twist_jump, 360 - twist_jump)
    jb, jf = np.unravel_index(np.argmax(twist_jump.T), (twist_jump.shape[1], twist_jump.shape[0]))
    heads = d["heads"] * scale
    body = heads[:, bidx[rig["body_bone"]]]
    steps = np.linalg.norm(np.diff(heads, axis=0), axis=2).max(axis=1) if n > 1 else np.zeros(1)
    seam = float(np.linalg.norm(heads[-1] - heads[0], axis=1).max())
    toes_under = float(max(0.0, -min(v.min() for v in foot_low.values())))
    mesh_h = (d["mesh_max"][:, 2] - d["mesh_min"][:, 2]) * scale
    quality = {
        "slides": slides,
        "max_stance_drift_cm": r1(max([s["drift_cm"] for s in stances] or [0.0]), 2),
        "toes_under_floor_cm": r1(toes_under, 2),
        "floor_cm": r1(move_floor, 2),
        "feet": feet_q,
        "max_twist_deg": r1(abs(tw[fi, bi]), 1), "max_twist_bone": bones[bi], "max_twist_frame": int(fi),
        "max_twist_jump_deg": r1(twist_jump[jf, jb], 1), "max_twist_jump_bone": bones[jb],
        "root_moved_cm": r1(np.linalg.norm(track[:, :2], axis=1).max(), 2),
        "body_bone": rig["body_bone"],
        "body_offset_cm": r1(np.linalg.norm(body[:, :2] - body[0, :2], axis=1).max(), 2),
        "body_bob_cm": r1(np.ptp(body[:, 2]), 2),
        "seam_jump_cm": r1(seam, 2),
        "seam_vs_median_step": r1(seam / max(1e-6, float(np.median(steps))), 2),
        "mesh_height_cm": [r1(mesh_h.min()), r1(mesh_h.max())],
    }

    act_soles = {f: to_actor(P[:, pidx["sole_" + f]], track) for f in feet}
    move = {
        "duration": r1((n - 1) / fps, 4),
        "frames": n,
        "loop": bool(loop),
        "track": [r1(t, 2) for t in track],
        "attacks": attacks,
        "shocks": shocks,
        "contacts": contacts,
        "stances": stances,
        "quality": quality,
        "source": {"blend": rel(d["blend"]),
                   "blend_md5": d["blend_md5"], "action": d["action"],
                   "frame_range": [int(x) for x in d["frame_range"]], "sample": os.path.basename(d["path"])},
        "span": [0.0, r1((n - 1) / fps, 4)],
        "tempo": [],
        "end": r1(track[-1], 2),
        "heading_change_deg": r1(track[-1, 2], 2),
        "stance_start_cm": {f: r1(v[0][:2]) for f, v in act_soles.items()},
        "stance_end_cm": {f: r1(v[-1][:2]) for f, v in act_soles.items()},
        "windows": windows,
        "parts": part_tracks,
    }
    return move, track


# ----------------------------------------------------------------------------- hurt capsules

def seg_dist(p, a, b):
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < 1e-12:
        return np.linalg.norm(p - a, axis=-1)
    t = np.clip(((p - a) @ ab) / L2, 0.0, 1.0)
    return np.linalg.norm(p - (a + t[..., None] * ab), axis=-1)


def fit_capsule(pts, shape="capsule", cover=0.75):
    c = pts.mean(0)
    if shape == "sphere":
        r = float(np.quantile(np.linalg.norm(pts - c, axis=1), cover))
        return c.copy(), c.copy(), r
    u = np.linalg.svd(pts - c, full_matrices=False)[2][0]
    s = (pts - c) @ u
    perp = np.linalg.norm((pts - c) - s[:, None] * u, axis=1)
    best = None
    for q in np.arange(0.5, 0.99, 0.02):
        r = float(np.quantile(perp, q))
        lo, hi = np.quantile(s, 0.02) + 0.5 * r, np.quantile(s, 0.98) - 0.5 * r
        if lo > hi:
            lo = hi = 0.5 * (lo + hi)
        a, b = c + lo * u, c + hi * u
        frac = float((seg_dist(pts, a, b) <= r).mean())
        best = (a, b, r)
        if frac >= cover:
            break
    return best


def build_boxes(samples, cfg, scale=None):
    d0 = samples[0]
    rig = d0["rig_map"]
    scale = float(scale if scale is not None else rig.get("game_scale", 1.0))
    bones = d0["bone_names"]
    bidx = {nm: i for i, nm in enumerate(bones)}
    vr = d0["vert_rest"].astype(np.float64) * scale
    vb = d0["vert_bone"]
    rest_h = d0["rest_heads"] * scale
    rest_r = d0["rest_rots"]
    parts, caps = {}, []
    inside_rest = np.zeros(len(vr), dtype=bool)
    for name, spec in rig["hurt"].items():
        ids = [bidx[b] for b in spec["bones"]]
        m = np.isin(vb, ids)
        pts = vr[m]
        a, b, r = fit_capsule(pts, spec.get("shape", "capsule"), spec.get("cover", cfg["capsule_cover"]))
        bi = bidx[spec["bone"]]
        R, h = rest_r[bi], rest_h[bi]
        a_b, b_b = R.T @ (a - h), R.T @ (b - h)
        inside = seg_dist(vr, a, b) <= r
        inside_rest |= inside
        rec = {"bone": spec["bone"], "kind": spec["kind"], "damage": spec["damage"],
               "a": r1(a), "b": r1(b), "radius": r1(r),
               "a_bone": r1(a_b), "b_bone": r1(b_b),
               "vertices": int(m.sum()), "cover": r1(float(inside[m].mean()), 3)}
        if "leg" in spec:
            rec["leg"] = spec["leg"]
        parts[name] = rec
        caps.append((name, bi, a_b, b_b, r))

    total = len(vr)
    moves_cover, tracks = {}, {}
    sub_bone = vb[d0["sub_idx"]]
    for d in samples:
        mv = d["move"]
        heads = d["heads"] * scale
        rots = d["rots"]
        sub = d["sub_pos"].astype(np.float64) * scale
        track = d["_track"]
        fr, tr = [], {}
        for f in range(len(heads)):
            inside = np.zeros(sub.shape[1], dtype=bool)
            cents = {}
            for name, bi, a_b, b_b, r in caps:
                A = rots[f, bi] @ a_b + heads[f, bi]
                Bp = rots[f, bi] @ b_b + heads[f, bi]
                inside |= seg_dist(sub[f], A, Bp) <= r
                cents[name] = 0.5 * (A + Bp)
            fr.append(float(inside[sub_bone >= 0].mean()))
            if f % cfg["track_every"] == 0:
                ca = {k: to_actor(v[None, :], track[f:f + 1])[0] for k, v in cents.items()}
                tr[str(f + 1)] = {k: r1(v) for k, v in ca.items()}
        moves_cover[mv] = {"min": r1(min(fr), 3), "mean": r1(float(np.mean(fr)), 3)}
        tracks[mv] = tr

    toes = {}
    pidx = {nm: i for i, nm in enumerate(d0["part_names"])}
    for f, spec in rig["feet"].items():
        ids = [bidx[b] for b in spec["bones"]]
        m = np.isin(vb, ids)
        tip = d0["rest_parts"][pidx["toe_" + f]] * scale
        toes[f] = {"bone": spec["bone"], "bones": spec["bones"], "tip": r1(tip),
                   "stand": r1(float(vr[m][:, 2].min()) if m.any() else float(d0["rest_parts"][pidx["sole_" + f]][2] * scale), 2),
                   "drop": 0.0}
    return {
        "units": UNITS + " a/b: segment ends in the mesh rest pose, component space (Leshy convention); "
                 "a_bone/b_bone: the same ends relative to the bone's rest head in the bone's rest frame "
                 "(Blender bone axes in Unreal handedness). Game scale applied; radius in cm.",
        "game_scale": scale,
        "rest_cover": r1(float(inside_rest.mean()), 3),
        "moves_cover": moves_cover,
        "parts": parts,
        "toes": toes,
        "tracks": tracks,
        "mesh_vertices": int(total),
        "mesh_height_cm": r1(float(d0.get("mesh_height_cm", np.ptp(d0["vert_rest"][:, 2]))) * scale, 1),
        "source": {"blend": rel(d0["blend"]), "blend_md5": d0["blend_md5"]},
    }


# ----------------------------------------------------------------------------- main

def dumps(obj, ind=0):
    """JSON with objects indented and lists of numbers kept on one line (diffable, compact)."""
    pad, pad1 = " " * ind, " " * (ind + 1)
    scalar = lambda v: not isinstance(v, (dict, list))
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [pad1 + json.dumps(str(k)) + ": " + dumps(v, ind + 1) for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list):
        if all(scalar(v) for v in obj):
            return "[" + ", ".join(json.dumps(v) for v in obj) + "]"
        return "[\n" + ",\n".join(pad1 + dumps(v, ind + 1) for v in obj) + "\n" + pad + "]"
    return json.dumps(obj)


def parse_part_thresholds(items):
    out = {}
    for it in items or []:
        k, v = it.split("=")
        out[k.strip()] = float(v)
    return out


def build_all(sample_paths, out_dir, threshold=None, part_thresholds=None, loops=(), scale=None, cfg=None):
    cfg = dict(DEFAULTS, **(cfg or {}))
    if threshold is not None:
        cfg["threshold_mps"] = threshold
    samples = [load_sample(p) for p in sample_paths]
    moves = {}
    for d in samples:
        mv, track = build_move(d, cfg, part_thresholds or {}, loop=d["move"] in loops, scale=scale)
        d["_track"] = track
        moves[d["move"]] = mv
    rig = samples[0]["rig_map"]
    gscale = float(scale if scale is not None else rig.get("game_scale", 1.0))
    idle = moves.get("idle")
    doc = {
        "fps": float(samples[0]["fps"]),
        "units": UNITS,
        "game_scale": gscale,
        "actor_frame": "x forward along the dragon's nose, y right, z up; origin = rig origin on the floor at frame 0, "
                       "moved by the track. The C++ adds its own mesh-in-actor offset and yaw.",
        "generator": "tools/movedata/build_moves.py",
        "settings": cfg,
        "part_thresholds_mps": part_thresholds or {},
        "idle_stance_cm": idle["stance_start_cm"] if idle else None,
        "moves": moves,
    }
    boxes = build_boxes(samples, cfg, scale=scale)
    tempo = {"_about": "Per move [[from_clip_s, to_clip_s, rate], ...]; 99 = to the end; outside every phase plays at 1.0. "
                       "Stub: everything plays at its own pace until tuned.",
             **{m: [[0.0, 99.0, 1.0]] for m in moves}}
    sounds = {"_about": "Per move [{sound, t (clip s), volume, at: voice|body}]; steps = footfall sample names. "
                        "Stub: no events yet; the Seedance clip audio is the voice candidate. The dir does not exist yet.",
              "dir": "/Game/Veyr/Audio/Dragon", "moves": {m: [] for m in moves}, "steps": []}
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for name, obj in (("moves.json", doc), ("boxes.json", boxes), ("tempo.json", tempo), ("sounds.json", sounds)):
        p = os.path.join(out_dir, name)
        with open(p, "w") as f:
            f.write(dumps(obj) + "\n")
        files[name] = p
    return doc, boxes, files


def summary(doc, boxes):
    lines = []
    for name, mv in doc["moves"].items():
        q = mv["quality"]
        tr = np.array(mv["track"])
        lines.append("MOVE %s: %.3f s, %d frames%s" % (name, mv["duration"], mv["frames"], " (loop)" if mv["loop"] else ""))
        lines.append("  track extent: x %.1f..%.1f cm, y %.1f..%.1f cm, yaw %.1f..%.1f deg; root moved %.2f cm; "
                     "body (%s) offset %.1f cm, bob %.1f cm"
                     % (tr[:, 0].min(), tr[:, 0].max(), tr[:, 1].min(), tr[:, 1].max(), tr[:, 2].min(), tr[:, 2].max(),
                        q["root_moved_cm"], q["body_bone"], q["body_offset_cm"], q["body_bob_cm"]))
        if mv["attacks"]:
            lines.append("  attacks (part: t0-t1 s, peak at t / m/s, at_peak cm):")
            for a in mv["attacks"]:
                lines.append("    %-7s %.3f-%.3f  peak %.3f / %.2f  at %s" % (a["part"], a["t0"], a["t1"], a["peak_t"], a["peak_v"], a["at_peak"]))
        else:
            lines.append("  attacks: none")
        keyset = {(a["part"], a["t0"]) for a in mv["attacks"]}
        wo = [w for w in mv["windows"] if (w["part"], w["t0"]) not in keyset]
        if wo:
            lines.append("  windows not used as attacks: " + ", ".join("%s %.3f-%.3f (%.1f m/s%s)" % (
                w["part"], w["t0"], w["t1"], w["peak_v"], ", carried in" if w["carry_in"] else "") for w in wo))
        lines.append("  shocks: %d, contacts: %d %s" % (len(mv["shocks"]), len(mv["contacts"]),
                     [(c["kind"], c["bone"], c["t"], c["speed"]) for c in mv["contacts"]] if mv["contacts"] else ""))
        for s in mv["stances"]:
            lines.append("  stance %s: frames %d-%d (%.3f-%.3f s), drift %.2f cm, slides %d"
                         % (s["foot"], s["f0"], s["f1"], s["t0"], s["t1"], s["drift_cm"], s["slides"]))
        lines.append("  quality: slides %d, max drift %.2f cm, toes under floor %.2f cm, floor %.2f cm, feet above floor %s, "
                     "max twist %.1f deg (%s), max twist jump %.1f deg, seam %.1f cm = %.2fx median step"
                     % (q["slides"], q["max_stance_drift_cm"], q["toes_under_floor_cm"], q["floor_cm"],
                        {f: v["above_floor_cm"] for f, v in q["feet"].items()}, q["max_twist_deg"], q["max_twist_bone"],
                        q["max_twist_jump_deg"], q["seam_jump_cm"], q["seam_vs_median_step"]))
    lines.append("BOXES: %d capsules, rest cover %.3f, per move %s" % (len(boxes["parts"]), boxes["rest_cover"], boxes["moves_cover"]))
    for k, p in boxes["parts"].items():
        lines.append("  %-7s %-22s %-5s r %6.1f cm  len %6.1f cm  cover %.2f  verts %d"
                     % (k, p["bone"], p["kind"], p["radius"], float(np.linalg.norm(np.subtract(p["b"], p["a"]))), p["cover"], p["vertices"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("samples", nargs="+")
    ap.add_argument("--out", default="Data/dragon")
    ap.add_argument("--threshold", type=float, default=None, help="m/s (default %.1f)" % DEFAULTS["threshold_mps"])
    ap.add_argument("--part-threshold", action="append", metavar="PART=MPS", help="per-part override, repeatable")
    ap.add_argument("--loop", action="append", default=[], help="move name that loops (idle)")
    ap.add_argument("--scale", type=float, default=None, help="game scale (default: rig map game_scale)")
    a = ap.parse_args(argv)
    doc, boxes, files = build_all(a.samples, a.out, a.threshold, parse_part_thresholds(a.part_threshold), a.loop, a.scale)
    print(summary(doc, boxes))
    for k, p in files.items():
        print("WROTE %s %d bytes" % (p, os.path.getsize(p)))


if __name__ == "__main__":
    sys.exit(main())
