#!/usr/bin/env python3
"""Audio-to-video offset of the capture path, from a short rendered run with -VeyrSyncTest (and a tap for the request times).

    ~/.cache/earshot/venv/bin/python tools/audio/sync_test.py <film.mp4> [--cues VeyrTap-N-cues.json] [--frames native-video/frames.jsonl]

The game draws a full-white overlay (camera fade, 0.1 s) and requests a 3 ms 3 kHz click on the same game frame, ten times 1.1 s
apart, then plays one loud 60 ms 1 kHz tone (arithmetic peak about +3 dBFS on the recorded master) to show whether the master limiter
holds. In the film: the first white frame of each overlay (mean luma), the click onset (3 kHz band envelope crossing half its peak),
offset = click - white. Also, from the tap: request wall time -> the audio render's first pull of the click wave (probe), and from the
frame manifest: the white frame's requested wall time -> its captured wall time (video timestamps are capture times).
"""
import argparse, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt

ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('--cues'); ap.add_argument('--frames'); a = ap.parse_args()
tmp = Path(tempfile.mkdtemp())
# video: per-frame mean luma with presentation times
r = subprocess.run(['ffprobe', '-v', 'error', '-f', 'lavfi', '-i', f"movie={a.film},signalstats", '-show_entries', 'frame=pts_time:frame_tags=lavfi.signalstats.YAVG',
                    '-of', 'json'], capture_output=True, text=True, check=True)
fr = [(float(f['pts_time']), float(f['tags']['lavfi.signalstats.YAVG'])) for f in json.loads(r.stdout)['frames'] if 'tags' in f]
t = np.array([x[0] for x in fr]); y = np.array([x[1] for x in fr])
white = [t[i] for i in range(1, len(y)) if y[i] > 200 and y[i - 1] <= 200]
# audio
wav = tmp / 'a.wav'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.film, '-vn', '-ac', '2', '-ar', '48000', str(wav)], check=True)
w = wave.open(str(wav)); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(float) / 32768
m = x.mean(1); b = sosfilt(butter(4, [2500, 3500], btype='band', fs=sr, output='sos'), m); env = np.abs(b)
print(f'{len(white)} white onsets in the film; video frames {len(t)}, median frame step {np.median(np.diff(t))*1000:.1f} ms')
rows = []
for wt in white:
    i0, i1 = int((wt - .4) * sr), int((wt + .6) * sr)
    seg = env[max(0, i0):i1]
    if len(seg) == 0: continue
    k = int(np.argmax(seg)); pk = seg[k]
    on = next(j for j in range(k, -1, -1) if seg[j] < .5 * pk) if pk > 0 else k
    ct = (max(0, i0) + on) / sr
    # frame step around the white frame: the white could have started up to one frame step before it was captured
    j = int(np.searchsorted(t, wt)); step = t[j] - t[j - 1] if j > 0 else 0
    rows.append((wt, ct, (ct - wt) * 1000, step * 1000, 20 * np.log10(pk + 1e-9)))
for wt, ct, off, step, pk in rows:
    print(f'white {wt:7.3f} s  click {ct:7.3f} s  click - white {off:+6.1f} ms  (previous frame {step:.0f} ms earlier; click 3 kHz peak {pk:.1f} dB)')
if rows:
    offs = np.array([r[2] for r in rows]); print(f'MEDIAN click - white: {np.median(offs):+.1f} ms (min {offs.min():+.1f}, max {offs.max():+.1f}); '
                                                f'the white started between one frame step before and the white frame itself')
# loud tone: peak in the film around the last event
full = np.abs(x).max(1); print(f'film sample peak {20*np.log10(full.max()+1e-9):.2f} dBFS at {np.argmax(full)/sr:.3f} s')
if a.cues:
    d = json.loads(Path(a.cues).read_text()); pulls = d.get('probePulls', [])
    ev = [e for e in d['events'] if e['kind'] in ('syncFlash', 'syncLoudTone')]
    # the sync probes are the last len(ev) probe waves created in event order (hit probes are interleaved: match by time)
    cand = sorted(p for p in pulls if p > 0)
    for e in ev:
        after = [p for p in cand if p >= e['wall'] - 1e-3]
        lat = (after[0] - e['wall']) * 1000 if after else float('nan')
        print(f"{e['kind']:12} frame {e['frame']:.0f} gameT {e['gameT']:.3f} wall {e['wall']:.3f}: first pull {lat:+.1f} ms after the request")
if a.frames:
    fm = [json.loads(l) for l in Path(a.frames).read_text().splitlines() if l.strip()]
    fm = [f for f in fm if f.get('type') == 'frame' and 'requestedWallSeconds' in f]
    lag = np.array([f['wallSeconds'] - f['requestedWallSeconds'] for f in fm])
    print(f'video frames: captured minus requested wall time median {np.median(lag)*1000:.1f} ms (p10 {np.percentile(lag,10)*1000:.1f}, p90 {np.percentile(lag,90)*1000:.1f}); '
          'the film timestamps a frame at its capture time')
