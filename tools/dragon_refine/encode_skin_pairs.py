"""Encode matched before/after turntable frame folders into side-by-side and separate MP4 clips (2026-11-19).

python3 encode_skin_pairs.py --frames DIR --out DIR --pair before_takeoff after_takeoff takeoff [--pair ...] [--fps 30]
Each pair writes <name>_before.mp4, <name>_after.mp4 and <name>_side_by_side.mp4 (before left, after right).
Needs ffmpeg on PATH. Frames are PNGs named 0000.png ... from render_skin_turntable.py.
"""
import argparse, subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--frames', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--pair', nargs=3, action='append', required=True, metavar=('BEFORE', 'AFTER', 'NAME'))
ap.add_argument('--fps', type=int, default=30)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
enc = ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-movflags', '+faststart']
for before, after, name in a.pair:
    nb = len(list((a.frames / before).glob('*.png'))); na = len(list((a.frames / after).glob('*.png')))
    assert nb == na and nb > 0, (before, nb, after, na)
    src = lambda t: ['-framerate', str(a.fps), '-i', str(a.frames / t / '%04d.png')]
    for t, tag in ((before, 'before'), (after, 'after')):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *src(t), *enc, str(a.out / f'{name}_{tag}.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *src(before), *src(after),
                    '-filter_complex', '[0:v][1:v]hstack=inputs=2', *enc, str(a.out / f'{name}_side_by_side.mp4')], check=True)
    print('ENCODED', name, nb, 'frames')
