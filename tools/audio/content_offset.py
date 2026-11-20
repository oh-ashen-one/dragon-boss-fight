#!/usr/bin/env python3
"""Film audio offset from content, for a run captured with the audio tap (-VeyrAudioTap=<dir>).

    python3 tools/audio/content_offset.py <Evidence/native-*/unreal-*> <VeyrTap-N-cues.json> [--seconds 30] [--world-index 0]

Why: the master recording drops time while the game stalls (about 0.4 s in the first seconds of a capture, more at later stalls), so
the clock-based offset (recording start time against video start time) put sync-test clicks 0.2 to 0.5 s away from their white frames.
Chain used here: master time <- tap time (onset-envelope correlation of the tap's own mix against the master, per 10 s block),
tap time -> game time (the tap's per-frame trace), game time -> video time (the frame manifest: requestedGameSeconds -> wallSeconds).
Prints the median (master time - video time) over the first --seconds; the last line is the number alone (mux_film.py reads it).
Verified on a -VeyrSyncTest run: click minus white frame -3.5 ms median, 10 of 10 within 12 ms (clock alignment: -336 to +505 ms).
"""
import argparse, json, sys, wave
from pathlib import Path
import numpy as np

SR = 48000


def rdwav(p):
    w = wave.open(str(p)); assert w.getframerate() == SR and w.getsampwidth() == 2, f'{p}: expected 48 kHz 16-bit'
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, w.getnchannels()).astype(float) / 32768


def onset_env(x, h):
    n = int(SR * h); k = len(x) // n
    return np.maximum(np.diff(10 * np.log10((x.mean(1)[:k * n].reshape(k, n) ** 2).mean(1) + 1e-10)), 0)


def best_lag(er, et, lo, hi, a0=0, length=None):
    y = et[a0:a0 + length] if length else et; b = (-1.0, 0)
    if y.std() == 0: return b
    for l in range(lo, hi + 1):
        s = a0 + l
        if length:
            if s < 0 or s + length > len(er): continue
            x = er[s:s + length]
        else:
            x, yy = (er[l:], et) if l >= 0 else (er, et[-l:]); n = min(len(x), len(yy)); x, y = x[:n], yy[:n]
            if n < 400: continue
        if x.std() == 0: continue
        c = np.corrcoef(x, y)[0, 1]
        if c > b[0]: b = (c, l)
    return b


def lag_map(real, tap, block=10.0, search=3.0):
    """Recording time minus tap time as a function of tap time (global 50 ms search, then per 10 s block at 10 ms within +-3 s)."""
    c, l = best_lag(onset_env(real, .05), onset_env(tap, .05), -600, 600); g = l * .05
    h = .01; er, et = onset_env(real, h), onset_env(tap, h); B = int(block / h); S = int(search / h); ts, ls = [], []
    for c0 in range(0, len(et) - B, B // 2):
        cc, ll = best_lag(er, et, int(g / h) - S, int(g / h) + S, c0, B)
        ts.append((c0 + B / 2) * h); ls.append(ll * h if cc > .3 else np.nan)
    ts, ls = np.array(ts), np.array(ls); ok = ~np.isnan(ls)
    if not ok.any(): return lambda t: g
    ls = np.interp(ts, ts[ok], ls[ok]); med = np.array([np.median(ls[max(0, i - 1):i + 2]) for i in range(len(ls))])
    return lambda t: float(np.interp(t, ts, med))


def content_offset(run, cues, seconds=30.0, world_index=0):
    run = Path(run); d = json.loads(Path(cues).read_text())
    wavs = sorted((run.parent / 'master-audio').glob('*.wav')); wav = wavs[min(world_index, len(wavs) - 1)]
    mix = Path(cues).with_name(Path(cues).name.replace('-cues.json', '-mix.wav'))
    lag = lag_map(rdwav(wav), rdwav(mix))
    tr = d.get('trace') or {}
    tt, tg = np.array(tr.get('t', [])), np.array(tr.get('gameT', []))
    assert len(tt) > 10, 'tap has no per-frame trace'
    fr = [json.loads(l) for l in (run / 'native-video/frames.jsonl').read_text().splitlines() if l.strip()]
    fr = [f for f in fr if f.get('type') == 'frame' and f.get('worldIndex', 0) == world_index and 'requestedGameSeconds' in f]
    g = np.array([f['requestedGameSeconds'] for f in fr]); v = np.array([f['wallSeconds'] for f in fr])
    # sample the first --seconds of tap time where the trace and the video overlap
    t0 = tt[np.searchsorted(tg, g[0])] if tg[-1] > g[0] else tt[0]
    ts = np.arange(t0 + 1.0, min(tt[-1], t0 + seconds), .25)
    offs = [t + lag(t) - float(np.interp(np.interp(t, tt, tg), g, v)) for t in ts]
    return float(np.median(offs)), float(np.percentile(offs, 10)), float(np.percentile(offs, 90)), len(offs)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run'); ap.add_argument('cues'); ap.add_argument('--seconds', type=float, default=30.0); ap.add_argument('--world-index', type=int, default=0)
    a = ap.parse_args()
    m, p10, p90, n = content_offset(a.run, a.cues, a.seconds, a.world_index)
    print(f'{n} samples: master minus video time median {m:+.3f} s (p10 {p10:+.3f}, p90 {p90:+.3f})')
    print(f'{m:.4f}')
