#!/usr/bin/env python3
"""Flag film frames where the camera sits inside the dragon (quality goal A2, 2026-11-18).

Inside the dragon the renderer shows the mesh's back faces: large, smooth, pale-pink/tan planes
(lit skin interior with no scale detail), usually with the see-through tunnel's dithered black ring.
Normal arena frames have pink-ish areas too (sand, the tapestry), but those are textured. The
classifier splits each frame (scaled to 320x180) into 10x10 blocks and counts "interior" blocks:
>=80 % skin-hued pixels and a low luminance spread. Frames above --inside are INSIDE, above --graze
GRAZE (the near plane cutting the skin). Calibrated on build16 at 4 fps (inside/clipping 82.6-84.4 s and 107.6-109.1 s; no other hits, fire
breath excluded by hue).

  python3 tools/unreal/inside_mesh_frames.py FILM.mp4 [--fps 4] [--json OUT.json]
  python3 tools/unreal/inside_mesh_frames.py --self-test
Exit code 1 when any INSIDE frame is found (0 otherwise), so it can gate a film.
"""
import argparse, json, subprocess, sys
import numpy as np

W, H, B = 320, 180, 10


def interior_share(rgb):
    a = rgb.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    s = d / np.maximum(mx, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    # Salmon/tan skin interior (~17 deg); dragon fire (orange-yellow, 28-45 deg) is excluded.
    skin = (h > 5) & (h < 28) & (s > 0.18) & (s < 0.65) & (mx > 0.5)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    hh, ww = (a.shape[0] // B) * B, (a.shape[1] // B) * B
    sk = skin[:hh, :ww].reshape(hh // B, B, ww // B, B).mean(axis=(1, 3))
    lu = lum[:hh, :ww].reshape(hh // B, B, ww // B, B)
    spread = lu.std(axis=(1, 3))
    interior = (sk >= 0.8) & (spread < 0.045)
    return float(interior.mean())


def frames(path, fps):
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'fps={fps},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        yield (n + 0.5) / fps, np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        n += 1
    p.wait()


def classify(share, inside, graze):
    return 'INSIDE' if share >= inside else 'GRAZE' if share >= graze else 'ok'


def self_test():
    rng = np.random.default_rng(7)
    # Synthetic back-face frame: smooth salmon gradient over 70 % of the image plus a dithered black disc.
    y, x = np.mgrid[0:H, 0:W]
    inside = np.zeros((H, W, 3), np.float32)
    shade = 0.75 + 0.15 * (x / W)
    inside[...] = np.stack([shade * 235, shade * 160, shade * 130], -1)
    disc = (x - 120) ** 2 + (y - 80) ** 2 < 45 ** 2
    inside[disc] = np.where(rng.random((disc.sum(), 1)) < 0.5, 20, 200)
    inside[:, 230:] = rng.integers(40, 120, (H, W - 230, 3))   # arena visible through the edge
    # Textured tan sand / tapestry: same hues, high per-block spread.
    tex = np.stack([210 * np.ones((H, W)), 150 * np.ones((H, W)), 110 * np.ones((H, W))], -1)
    tex *= (0.55 + 0.45 * rng.random((H, W, 1)))
    # Dragon fire: bright orange-yellow smooth plume.
    fire = np.zeros((H, W, 3), np.float32); fire[...] = [250, 170, 60]
    # Grey cobbles and dark scales.
    normal = rng.integers(30, 140, (H, W, 3)).astype(np.float32)
    # Grazing: a smooth skin band across the top fifth.
    graze = normal.copy(); graze[:20, :120] = [225, 155, 125]
    cases = {'inside': (inside, 'INSIDE'), 'textured_sand': (tex, 'ok'), 'cobbles': (normal, 'ok'), 'fire': (fire, 'ok'), 'graze': (graze, 'GRAZE')}
    ok = True
    for name, (img, want) in cases.items():
        share = interior_share(np.clip(img, 0, 255).astype(np.uint8))
        got = classify(share, 0.05, 0.013)
        print(f'{name:14s} share {share:.3f} -> {got} (want {want})')
        ok &= got == want
    print('SELF_TEST', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('film', nargs='?')
    ap.add_argument('--fps', type=float, default=4)
    ap.add_argument('--inside', type=float, default=0.05, help='interior block share for INSIDE')
    ap.add_argument('--graze', type=float, default=0.013, help='interior block share for GRAZE (fire smoke reaches 0.012)')
    ap.add_argument('--json')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.film:
        ap.error('film required')
    rows = []
    for t, img in frames(a.film, a.fps):
        share = interior_share(img)
        rows.append({'t': round(t, 3), 'interiorShare': round(share, 4), 'class': classify(share, a.inside, a.graze)})
    flagged = [r for r in rows if r['class'] != 'ok']
    for r in flagged:
        print(f"{r['t']:8.2f}s {r['class']:6s} {r['interiorShare']:.3f}")
    summary = {'film': a.film, 'fps': a.fps, 'frames': len(rows), 'inside': sum(r['class'] == 'INSIDE' for r in rows),
               'graze': sum(r['class'] == 'GRAZE' for r in rows), 'thresholds': {'inside': a.inside, 'graze': a.graze}}
    print('INSIDE_MESH_FRAMES', json.dumps(summary))
    if a.json:
        with open(a.json, 'w') as f:
            json.dump({**summary, 'rows': rows}, f, indent=1)
    return 1 if summary['inside'] else 0


if __name__ == '__main__':
    sys.exit(main())
