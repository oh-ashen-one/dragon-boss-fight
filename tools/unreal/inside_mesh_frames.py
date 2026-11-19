#!/usr/bin/env python3
"""Flag film frames where the camera sits inside the dragon (quality goal A2, 2026-11-18).

Inside the dragon the renderer shows the mesh's back faces: large, smooth, pale-pink/tan planes
(lit skin interior with no scale detail), usually with the see-through tunnel's dithered black ring.
Normal arena frames have pink-ish areas too (sand, the tapestry), but those are textured. The
classifier splits each frame (scaled to 320x180) into 10x10 blocks and counts "interior" blocks:
>=80 % skin-hued pixels and a low luminance spread. Frames above --inside are INSIDE, above --graze
GRAZE (the near plane cutting the skin). Calibrated on build16 at 4 fps (inside/clipping 82.6-84.4 s and 107.6-109.1 s; no other hits, fire
breath excluded by hue).

  python3 tools/unreal/inside_mesh_frames.py FILM.mp4|RUN/native-video [--fps 12] [--json OUT.json]
  python3 tools/unreal/inside_mesh_frames.py --self-test
Exit code 1 when any INSIDE or PALE frame is found (0 otherwise), so it can gate a film.

PALE (third pass, 2026-11-18): the phase A film showed a second inside look the salmon class missed:
pale grey, low-saturation, flat-shaded facets (the dragon's back faces under the arena light) filling
the screen while the knight is seen through or under them. Cobbles and scales are pale too but carry
fine detail; facets are smooth gradients. Per 32x32 block at 640x360 the ratio of luminance spread to
mean absolute Laplacian is high (>2.2) on facets and about 1 on cobbles. PALE needs >=20 % pale blocks,
a median ratio over them >=1.8 and >=10 % smooth, non-bluish pale blocks below the top third (where
the knight stands; this also rejects cloudy sky). Calibrated on veyr-phaseA-victory.mp4
(flagged by the critic at 35.5, 36.75, 73.5, 79.5 s) against veyr-79fe0bc-baseline-victory.mp4.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

W, H, B = 320, 180, 10
PW, PH, PB = 640, 360, 20


def pale_facets(rgb640):
    """(pale share, median smoothness ratio, smooth pale share) of a 640x360 frame, HUD masked."""
    a = rgb640.astype(np.float32) / 255.0
    lum = a @ np.array([.299, .587, .114], np.float32)
    lap = np.zeros_like(lum)
    lap[1:-1, 1:-1] = np.abs(4 * lum[1:-1, 1:-1] - lum[:-2, 1:-1] - lum[2:, 1:-1] - lum[1:-1, :-2] - lum[1:-1, 2:])
    gy, gx = PH // PB, PW // PB
    blk = a.reshape(gy, PB, gx, PB, 3).mean(axis=(1, 3))
    bl = blk @ np.array([.299, .587, .114], np.float32)
    sat = (blk.max(-1) - blk.min(-1)) / np.maximum(blk.max(-1), 1e-6)
    spread = lum.reshape(gy, PB, gx, PB).std(axis=(1, 3))
    ratio = spread / np.maximum(lap.reshape(gy, PB, gx, PB).mean(axis=(1, 3)), 1e-3)
    keep = np.ones((gy, gx), bool)
    keep[:2, :] = False; keep[11:, :4] = False; keep[9:, 25:] = False   # boss bar, gauge, help text and icons
    pale = (bl > 0.30) & (sat < 0.22) & keep
    # Smooth pale blocks that are not cloudy night sky (bluish), counted below the top third, where the
    # knight stands: facets there cover or crowd him.
    smooth = pale & (ratio > 2.2) & (spread > 0.05) & (blk[..., 2] - blk[..., 0] < 0.06)
    smooth[:gy // 3, :] = False
    med = float(np.median(ratio[pale])) if pale.any() else 0.0
    return float(pale[keep].mean()), med, float(smooth[keep].mean())


def pale_class(pale, med, smooth):
    return pale >= 0.2 and med >= 1.8 and smooth >= 0.10


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


def frames(path, fps, w=W, h=H):
    if Path(path).is_dir():
        yield from native_frames(Path(path).resolve(), fps, w, h)
        return
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'fps={fps},scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        yield (n + 0.5) / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        n += 1
    p.wait()


def native_frames(folder, fps, w, h):
    """A run's native-video folder (frame-NNNNNN.png + frames.jsonl): every k-th PNG, timed by wallSeconds."""
    rows = [json.loads(l) for l in (folder / 'frames.jsonl').read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get('type') == 'frame' and (folder / r['file']).exists()]
    if not rows:
        return
    span = max(rows[-1]['wallSeconds'] - rows[0]['wallSeconds'], 1e-3)
    k = max(1, round(len(rows) / span / fps))
    pick = rows[::k]
    listing = folder.parent / '.inside-mesh-frames.ffconcat'
    listing.write_text('ffconcat version 1.0\n' + ''.join(f"file '{folder / r['file']}'\nduration 1\n" for r in pick))
    try:
        cmd = ['ffmpeg', '-v', 'error', '-safe', '0', '-f', 'concat', '-i', str(listing), '-vf', f'scale={w}:{h}', '-fps_mode', 'passthrough',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        for r in pick:
            buf = p.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            yield r['wallSeconds'], np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        p.wait()
    finally:
        listing.unlink(missing_ok=True)


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
    # Pale facets: flat-shaded grey cells (~60 px, a low-poly mesh seen from inside) against grey cobbles.
    y2, x2 = np.mgrid[0:PH, 0:PW]
    seeds = rng.random((70, 2)) * [PH, PW]
    cell = np.argmin((y2[..., None] - seeds[:, 0]) ** 2 + (x2[..., None] - seeds[:, 1]) ** 2, axis=-1)
    shade = rng.integers(120, 230, 70)[cell].astype(np.float32)
    facets = np.stack([shade, shade + 3, shade + 5], -1)
    stones = np.repeat(np.repeat(rng.integers(90, 190, (PH // 8, PW // 8, 1)), 8, 0), 8, 1).astype(np.float32).repeat(3, -1)
    stones += rng.normal(0, 18, stones.shape)
    for name, img, want in (('pale_facets', facets, True), ('pale_cobbles', stones, False)):
        got = pale_class(*pale_facets(np.clip(img, 0, 255).astype(np.uint8)))
        print(f'{name:14s} pale -> {got} (want {want})')
        ok &= got == want
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
    ap.add_argument('--fps', type=float, default=12, help='sample rate; 12 catches the 0.1-0.3 s pale frames, 4 misses some')
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
    for t, big in frames(a.film, a.fps, PW, PH):
        img = big.reshape(H, 2, W, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
        share = interior_share(img)
        pale, med, smooth = pale_facets(big)
        cls = classify(share, a.inside, a.graze)
        if cls != 'INSIDE' and pale_class(pale, med, smooth):
            cls = 'PALE'
        rows.append({'t': round(t, 3), 'interiorShare': round(share, 4), 'paleShare': round(pale, 3), 'paleSmoothRatio': round(med, 2),
                     'paleSmoothShare': round(smooth, 3), 'class': cls})
    flagged = [r for r in rows if r['class'] != 'ok']
    for r in flagged:
        print(f"{r['t']:8.2f}s {r['class']:6s} {r['interiorShare']:.3f} pale {r['paleShare']:.2f} ratio {r['paleSmoothRatio']:.2f} smooth {r['paleSmoothShare']:.3f}")
    summary = {'film': a.film, 'fps': a.fps, 'frames': len(rows), 'inside': sum(r['class'] == 'INSIDE' for r in rows),
               'pale': sum(r['class'] == 'PALE' for r in rows), 'paleSeconds': [r['t'] for r in rows if r['class'] == 'PALE'],
               'graze': sum(r['class'] == 'GRAZE' for r in rows), 'thresholds': {'inside': a.inside, 'graze': a.graze}}
    print('INSIDE_MESH_FRAMES', json.dumps(summary))
    if a.json:
        with open(a.json, 'w') as f:
            json.dump({**summary, 'rows': rows}, f, indent=1)
    return 1 if summary['inside'] or summary['pale'] else 0


if __name__ == '__main__':
    sys.exit(main())
