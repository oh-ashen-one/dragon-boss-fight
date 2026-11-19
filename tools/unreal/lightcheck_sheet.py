#!/usr/bin/env python3
"""Build a comparison sheet from lightcheck still folders (and optionally reference frames).

Usage: lightcheck_sheet.py [--max-clip SHARE] OUT.jpg DIR_OR_GLOB [DIR_OR_GLOB ...]
Each argument becomes one row (a lightcheck folder's PNGs in shot order, or a glob of
reference frames). Prints per-image luma stats (mean, median, p5, p95, share < 25, share of
clipped pixels with any channel >= 250, warmth) so before/after and ours/reference can be
compared by number as well as by eye.
--max-clip SHARE: exit 1 if any 05_fire_breath still clips more than SHARE (e.g. 0.04),
the gate for a breath that runs hot.
"""
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageStat

W, H = 384, 216

def frames(arg):
    if os.path.isdir(arg):
        return sorted(glob.glob(os.path.join(arg, '[0-9][0-9]_*.png')))
    return sorted(glob.glob(arg))

def stats(im):
    small = im.convert('RGB').resize((480, 270))
    lum = small.convert('L'); hist = lum.histogram(); n = sum(hist)
    def pct(q):
        c = 0
        for i, v in enumerate(hist):
            c += v
            if c >= q * n:
                return i
    r, g, b = ImageStat.Stat(small).mean
    peak = Image.eval(small, lambda v: 255 if v >= 250 else 0).convert('L').point(lambda v: 255 if v else 0)
    clip = peak.histogram()[255] / n
    return dict(mean=round(ImageStat.Stat(lum).mean[0]), p50=pct(.5), p5=pct(.05), p95=pct(.95),
                dark=round(sum(hist[:25]) / n, 2), clip=round(clip, 3), warm=round((r - b) / max(1, (r + b) / 2), 2))

def main():
    args, max_clip = sys.argv[1:], None
    if args[:1] == ['--max-clip']:
        max_clip, args = float(args[1]), args[2:]
    out, rows = args[0], [frames(a) for a in args[1:]]
    cols = max(len(r) for r in rows)
    sheet = Image.new('RGB', (cols * W, len(rows) * (H + 18)), (12, 12, 12))
    draw = ImageDraw.Draw(sheet); report = {}
    for y, (arg, row) in enumerate(zip(args[1:], rows)):
        report[arg] = {}
        for x, path in enumerate(row):
            im = Image.open(path)
            report[arg][os.path.basename(path)] = stats(im)
            sheet.paste(im.convert('RGB').resize((W, H)), (x * W, y * (H + 18) + 18))
            draw.text((x * W + 4, y * (H + 18) + 3), os.path.basename(path)[:44], fill=(220, 220, 200))
    sheet.save(out, quality=90)
    print(json.dumps(report, indent=1))
    if max_clip is not None:
        hot = [(arg, name, s['clip']) for arg, shots in report.items() for name, s in shots.items()
               if name.startswith('05_fire_breath') and s['clip'] > max_clip]
        for arg, name, clip in hot:
            print(f'BREATH_CLIP_FAIL {arg} {name} clip={clip} > {max_clip}', file=sys.stderr)
        if hot:
            sys.exit(1)

if __name__ == '__main__':
    main()
