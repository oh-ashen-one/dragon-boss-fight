#!/usr/bin/env python3
"""Build a comparison sheet from lightcheck still folders (and optionally reference frames).

Usage: lightcheck_sheet.py OUT.jpg DIR_OR_GLOB [DIR_OR_GLOB ...]
Each argument becomes one row (a lightcheck folder's PNGs in shot order, or a glob of
reference frames). Prints per-image luma stats (mean, median, p5, p95, share < 25, warmth)
so before/after and ours/reference can be compared by number as well as by eye.
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
    return dict(mean=round(ImageStat.Stat(lum).mean[0]), p50=pct(.5), p5=pct(.05), p95=pct(.95),
                dark=round(sum(hist[:25]) / n, 2), warm=round((r - b) / max(1, (r + b) / 2), 2))

def main():
    out, rows = sys.argv[1], [frames(a) for a in sys.argv[2:]]
    cols = max(len(r) for r in rows)
    sheet = Image.new('RGB', (cols * W, len(rows) * (H + 18)), (12, 12, 12))
    draw = ImageDraw.Draw(sheet); report = {}
    for y, (arg, row) in enumerate(zip(sys.argv[2:], rows)):
        report[arg] = {}
        for x, path in enumerate(row):
            im = Image.open(path)
            report[arg][os.path.basename(path)] = stats(im)
            sheet.paste(im.convert('RGB').resize((W, H)), (x * W, y * (H + 18) + 18))
            draw.text((x * W + 4, y * (H + 18) + 3), os.path.basename(path)[:44], fill=(220, 220, 200))
    sheet.save(out, quality=90)
    print(json.dumps(report, indent=1))

if __name__ == '__main__':
    main()
