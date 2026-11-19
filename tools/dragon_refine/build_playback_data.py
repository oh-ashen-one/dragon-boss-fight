#!/usr/bin/env python3
"""F1/F4 (2026-11-18): build Data/dragon/playback.json from the cut specs and the Blender playback measurements.

Inputs (local, not in git): the cut specs `spec_*.json` and per-clip measurements written by
`measure_playback_tracks.py` (one JSON per cut .blend). Output (in git, derived numbers only):
`Data/dragon/playback.json` (next to the reference-style tempo.json of the data-move layer, which stays a stub) with, per imported video2rig clip stem,
  - `bake`: the source frame shown at every baked 30 Hz frame (the exact remap cut_v2r_move.py baked in),
  - `holds`: source-frame spans where the fit is nearly still (fastest non-wing bone under HOLD_DPS at authored speed),
  - `track_cm` / `track_yaw_deg`: tripo__Spine_0 planar offset and yaw from frame 0 per baked frame, mesh space
    (Blender x*100, -y*100; yaw negated), the same convention as the TurnLeft root samples,
and per move the tempo block the game reads (rates, hold compression, recovery exit, gaps, chain entry).

python3 tools/dragon_refine/build_playback_data.py --specs DIR --measure DIR [--out Data/dragon/playback.json]
"""
import argparse
import json
import math
from pathlib import Path

HOLD_DPS = 45.0       # fastest-bone speed at authored playback under which a span is a held pose
HOLD_MIN_FRAMES = 6   # source frames (0.25 s at 24 fps)

# clip stem -> (spec file, measured blend stem, mirrored-from-measure, move key)
CLIPS = {
    'Claw0': ('spec_claw_v3.json', 'Dragon_claw_v2r_cut_v3_mirror', False, 'claw'),
    'Claw1': ('spec_claw_v3.json', 'Dragon_claw_v2r_cut_v3', False, 'claw'),
    'Stomp2': ('spec_stomp_v3.json', 'Dragon_stomp_v2r_cut_v3_mirror', False, 'stomp'),
    'Stomp3': ('spec_stomp_v3.json', 'Dragon_stomp_v2r_cut_v3', False, 'stomp'),
    'Tail': ('spec_tail_v3.json', 'Dragon_tail_v2r_cut_v3', False, 'tail'),
    'Bite': ('spec_bite_v3.json', 'Dragon_bite_v2r_cut_v3', False, 'bite'),
    'Fire': ('spec_fire_v3.json', 'Dragon_fire_v2r_cut_v3', False, 'fire'),
    'Buckle0': ('spec_buckle_v3.json', 'Dragon_buckle_v2r_cut_v3', True, 'buckle'),
    'Buckle1': ('spec_buckle_v3.json', 'Dragon_buckle_v2r_cut_v3', False, 'buckle'),
    'Buckle2': ('spec_hind_buckle_v3.json', 'Dragon_hind_buckle_v2r_cut_v3', True, 'buckle'),
    'Buckle3': ('spec_hind_buckle_v3.json', 'Dragon_hind_buckle_v2r_cut_v3', False, 'buckle'),
    'Collapse': ('spec_collapse.json', 'Dragon_collapse_v2r_cut_v1', False, 'collapse'),
    'Exposed': ('spec_exposed.json', 'Dragon_exposed_v2r_cut_v1', False, 'exposed'),
    'Rise': ('spec_rise_v3.json', 'Dragon_rise_v2r_cut_v3', False, 'rise'),
    'TurnLeft': ('spec_turn_v3.json', 'Dragon_turn_v2r_cut_v3', False, 'turn'),
    'Walk': ('spec_walk_v3.json', 'Dragon_walk_v2r_cut_v3', False, 'walk'),
    'IdleOpen': ('spec_idle_w55.json', 'Dragon_idle_w55_cut', False, 'idle'),
}

# Starting numbers (tuned later against the 16-seed band; see Local/quality-goal/F-notes.md).
# rates multiply authored source speed outside holds (1.0 = the clip's own speed, gate <= 1.25);
# hold_rate compresses held spans; recovery_exit = fraction of the recovery after which the next move may start
# (the rest cross-fades out); gap_scale/gap_add reshape the post-move idle gap; chain_entry = fraction of the next
# wind-up skipped when a blow is chained (entered by cross-fade from the strike).
# root_track: the actor follows the clip's Spine_0 track. Only buckle/collapse/rise travel net; the strikes'
# (collapse stays off: Exposed continues the collapse in absolute clip space, so its travel would count twice)
# in-clip travel returns to the start and their hitbox caches are actor-relative, so they stay in place.
MOVES = {
    # 2026-11-19 band retune (paper, F-notes section 7): rates at the 1.25 ceiling, holds x8, the longer own-speed
    # wind-ups paid back from the recovery (recovery_exit) and the in-string gaps so that each move's
    # wind-up+strike+recovery+gap cycle and each chained wind-up+strike match today's real seconds.
    'claw': dict(windup_rate=1.25, strike_rate=1.25, recovery_rate=1.25, hold_rate=8.0, recovery_exit=0.35, gap_scale=0.72, gap_add=0.0, chain_entry=0.48),
    'stomp': dict(windup_rate=1.25, strike_rate=1.25, recovery_rate=1.25, hold_rate=8.0, recovery_exit=0.25, gap_scale=0.6, gap_add=0.0, chain_entry=0.47),
    'tail': dict(windup_rate=1.25, strike_rate=1.25, recovery_rate=1.25, hold_rate=8.0, recovery_exit=0.2, gap_scale=0.15, gap_add=0.0, chain_entry=0.5),
    'bite': dict(windup_rate=1.25, strike_rate=1.25, recovery_rate=1.25, hold_rate=8.0, recovery_exit=0.4, gap_scale=0.7, gap_add=0.0, chain_entry=0.52),
    'fire': dict(windup_rate=1.25, strike_rate=1.0, recovery_rate=1.25, hold_rate=8.0, recovery_exit=0.5, gap_scale=1.0, gap_add=0.0, chain_entry=0.0),
    'buckle': dict(root_track=True, rate=1.0, hold_rate=2.0),
    'collapse': dict(root_track=False, rate=1.25, hold_rate=2.0),
    'exposed': dict(rate=1.0, hold_rate=1.0),
    'rise': dict(root_track=True, rate=1.16, hold_rate=2.0),
    'turn': dict(rate=1.25, hold_rate=2.0),
    'walk': dict(rate=1.0, hold_rate=1.0),
    'idle': dict(rate=1.0, hold_rate=1.0),
}


def bake_map(spec, src_fps, out_fps=30.0):
    """Source frame at each baked output frame: the same integration and inversion as cut_v2r_move.py."""
    rates, blend = spec['rates'], float(spec.get('blend_frames', 4))

    def rate_at(s):
        for left, right in zip(rates, rates[1:]):
            b = left[1]
            if abs(s - b) < blend / 2:
                u = (s - (b - blend / 2)) / blend
                return left[2] + (right[2] - left[2]) * (0.5 - 0.5 * math.cos(math.pi * u))
        return next((r for f0, f1, r in rates if s < f1), rates[-1][2])
    s0, s1, ds = rates[0][0], rates[-1][1], 0.02
    grid, acc, s = [(s0, 0.0)], 0.0, s0
    while s < s1 - 1e-9:
        step = min(ds, s1 - s)
        acc += step / (src_fps * rate_at(s + step / 2))
        s += step
        grid.append((s, acc))
    duration = grid[-1][1]

    def remap(t):
        t = min(max(t, 0.0), duration)
        lo, hi = 0, len(grid) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if grid[mid][1] < t:
                lo = mid
            else:
                hi = mid
        (sa, ta), (sb, tb) = grid[lo], grid[hi]
        return sa + (sb - sa) * ((t - ta) / max(tb - ta, 1e-12))
    count = int(round(duration * out_fps)) + 1
    return [remap(i / out_fps) for i in range(count)]


def find_holds(bake, frames, src_fps):
    slow = []
    for i in range(1, min(len(bake), len(frames))):
        ds = bake[i] - bake[i - 1]
        speed = frames[i]['step_deg'] / max(ds / src_fps, 1e-6)
        slow.append((bake[i - 1], bake[i], speed < HOLD_DPS))
    spans, cur = [], None
    for a, b, s in slow:
        if s:
            cur = [a, b] if cur is None else [cur[0], b]
        elif cur is not None:
            spans.append(cur); cur = None
    if cur is not None:
        spans.append(cur)
    return [[round(a, 2), round(b, 2)] for a, b in spans if b - a >= HOLD_MIN_FRAMES]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--specs', type=Path, required=True)
    ap.add_argument('--measure', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[2] / 'Data/dragon/playback.json')
    a = ap.parse_args()
    clips = {}
    for stem, (spec_name, measured, mirror, move) in CLIPS.items():
        spec = json.loads((a.specs / spec_name).read_text())
        m = json.loads((a.measure / (measured + '.json')).read_text())
        src_fps = 24.0
        bake = bake_map(spec, src_fps, float(spec.get('output_fps', 30)))
        frames = m['frames']
        if len(frames) != len(bake):
            raise SystemExit(f'{stem}: measured {len(frames)} frames, bake map {len(bake)}')
        r0, y0 = frames[0]['root'], frames[0]['yaw']
        sign = -1.0 if mirror else 1.0
        track = [[round(100 * (f['root'][0] - r0[0]), 3), round(-100 * sign * (f['root'][1] - r0[1]), 3)] for f in frames]
        yaw = [round(-sign * math.degrees(f['yaw'] - y0), 3) for f in frames]
        trims = spec.get('trim_source_frames', {})
        clips[stem] = dict(move=move, src_fps=src_fps, out_fps=float(spec.get('output_fps', 30)),
                           bake=[round(s, 3) for s in bake], holds=find_holds(bake, frames, src_fps),
                           trims_src=[trims['windup_end'], trims['active_end']] if trims else [],
                           track_cm=track, track_yaw_deg=yaw)
    out = {
        '_about': ('F1/F4 dragon clip playback (2026-11-18). Generated by tools/dragon_refine/build_playback_data.py; '
                   'edit the "moves", "fades", "turn" and "foot_lock" blocks by hand to tune without a rebuild. Rates multiply '
                   'the clip\'s authored (source video) speed; 1.0 plays it as generated. Holds are source-frame spans the '
                   'fit holds still; only they may run faster than 1.25. -VeyrLegacyClipTempo restores the old timing.'),
        'version': 1,
        'phase2_rate': 1.12, 'phase2_max_rate': 1.25, 'phase2_recovery_exit_scale': 0.5,
        'phase2_gap_scale': 0.6, 'phase2_chain_entry_add': 0.1,
        'fades': {'default': 0.35, 'roar': 0.6, 'flight_active': 0.2, 'rise_to_idle': 0.4, 'dead': 0.35},
        'turn': {'track_rate_dps': 90.0, 'track_lead_seconds': 0.06},
        'foot_lock': {'plant_height_cm': 4.0, 'plant_speed_cms': 120.0, 'release_height_cm': 8.0, 'drag_release_cm': 30.0,
                      'slip_cm': 30.0, 'release_seconds': 0.12, 'step_seconds': 0.3, 'step_lift_cm': 18.0},
        'moves': MOVES,
        'clips': clips,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + '\n')
    # Packaged builds do not stage Data/: the same data is compiled in; the loose file only overrides it in a checkout.
    compact = json.dumps(out, separators=(',', ':'))
    chunks = [compact[i:i + 8000] for i in range(0, len(compact), 8000)]
    inl = a.out.parents[2] / 'Unreal/Veyr/Source/Veyr/VeyrDragonPlaybackData.inl'
    inl.write_text('// Generated by tools/dragon_refine/build_playback_data.py from Data/dragon/playback.json. Do not edit.\n'
                   '#pragma once\nstatic const TCHAR* const GVeyrDragonPlaybackJson[] = {\n' +
                   ''.join('    TEXT(R"VEYRJSON(' + c + ')VEYRJSON"),\n' for c in chunks) + '};\n')
    print('wrote', inl, len(compact), 'bytes in', len(chunks), 'chunks')
    # Report: real seconds per phase today vs with these numbers.
    def real(stem, s0, s1, rate, hold_rate):
        c = clips[stem]; t = 0.0; bk = c['bake']
        for i in range(1, len(bk)):
            a_, b_ = max(bk[i - 1], s0), min(bk[i], s1)
            if b_ <= a_:
                continue
            mid = (a_ + b_) / 2
            r = hold_rate if any(h[0] <= mid <= h[1] for h in c['holds']) else rate
            t += (b_ - a_) / (c['src_fps'] * r)
        return t
    for stem, c in clips.items():
        mv = MOVES[c['move']]
        if c['trims_src']:
            w, x = c['trims_src']
            ph = [(c['bake'][0], w, mv['windup_rate']), (w, x, mv['strike_rate']), (x, c['bake'][-1], mv['recovery_rate'])]
        else:
            ph = [(c['bake'][0], c['bake'][-1], mv['rate'])]
        print(stem, 'holds', c['holds'], 'phases', [round(real(stem, s0, s1, r, mv['hold_rate']), 3) for s0, s1, r in ph],
              'net track cm', c['track_cm'][-1], 'max', round(max(math.hypot(*p) for p in c['track_cm']), 1), 'yaw', c['track_yaw_deg'][-1])
    print('wrote', a.out)


if __name__ == '__main__':
    main()
