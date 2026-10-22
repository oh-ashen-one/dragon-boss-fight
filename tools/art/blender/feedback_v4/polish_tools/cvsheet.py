"""cvsheet.py DIR VIEW OUT [cols] [scale]: contact sheet of critic-view frames with frame labels."""
import sys, glob
from PIL import Image, ImageDraw
D, V, O = sys.argv[1:4]; cols = int(sys.argv[4]) if len(sys.argv) > 4 else 9; sc = float(sys.argv[5]) if len(sys.argv) > 5 else .5
fs = sorted(glob.glob(f"{D}/{V}-full-*.png")); w = int(480 * sc); rows = (len(fs) + cols - 1) // cols
sh = Image.new("RGB", (cols * w, rows * w), (20, 20, 20)); d = ImageDraw.Draw(sh)
for i, fn in enumerate(fs):
    im = Image.open(fn).convert("RGB").resize((w, w)); x, y = (i % cols) * w, (i // cols) * w; sh.paste(im, (x, y)); d.text((x + 4, y + 4), "f%d" % i, fill=(255, 255, 0))
sh.save(O)
