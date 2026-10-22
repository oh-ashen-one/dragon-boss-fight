"""Contact sheet with frame labels (PIL): labelsheet.py DIR VIEW OUT [cols] [tile] [t0] [fps]
Label = 30 fps sheet frame index of the clip (offset by t0*fps when a strip starts later) and time."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
d = Path(sys.argv[1]); view = sys.argv[2]; out = sys.argv[3]; cols = int(sys.argv[4]) if len(sys.argv) > 4 else 10
tile = int(sys.argv[5]) if len(sys.argv) > 5 else 200; t0 = float(sys.argv[6]) if len(sys.argv) > 6 else 0.; fps = float(sys.argv[7]) if len(sys.argv) > 7 else 30.
files = sorted(d.glob(f"{view}-*.png")); rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tile + 2), rows * (tile + 2)), (34, 34, 34)); dr = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", max(12, tile // 12))
except Exception: font = ImageFont.load_default()
for k, f in enumerate(files):
    i = int(f.stem.split("-")[-1]); im = Image.open(f).convert("RGB").resize((tile, tile))
    x, y = (k % cols) * (tile + 2), (k // cols) * (tile + 2); sheet.paste(im, (x, y))
    fr = round(t0 * fps) + i; dr.rectangle((x, y, x + tile // 2, y + tile // 10 + 4), fill=(0, 0, 0)); dr.text((x + 3, y + 2), f"f{fr} {fr / fps:.2f}s", fill=(255, 230, 120), font=font)
sheet.save(out, quality=88); print(out, len(files))
