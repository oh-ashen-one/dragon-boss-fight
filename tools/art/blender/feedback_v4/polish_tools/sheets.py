"""usage: python3 sheets.py LABEL_or_DIR -> contact sheets in <dir>/sheets (PIL, labels = 30fps frame); pages of 25 frames."""
import sys, glob, os, string
from PIL import Image, ImageDraw, ImageFont
D = sys.argv[1] if sys.argv[1].startswith("/") else "/Users/midir/veyr-review-fable-20261021/Local/Blender/feedback-v4-20261021/renders/" + sys.argv[1]; O = D + "/sheets"; os.makedirs(O, exist_ok=True)
for f in glob.glob(O + "/*.png"): os.remove(f)
try: font = ImageFont.load_default(size=22)
except TypeError: font = ImageFont.load_default()
def sheet(files, cols, tw, th, out):
    rows = (len(files) + cols - 1) // cols; im = Image.new("RGB", (cols * tw, rows * th), (25, 25, 25)); d = ImageDraw.Draw(im)
    for i, fn in enumerate(files):
        t = Image.open(fn).convert("RGB").resize((tw, th)); x, y = (i % cols) * tw, (i // cols) * th; im.paste(t, (x, y))
        d.text((x + 4, y + 2), "f%d" % int(fn.rsplit("-", 1)[1][:4]), fill=(255, 255, 0), font=font)
    im.save(out)
def paged(fs, per):
    n = max(1, (len(fs) + per - 1) // per); per = (len(fs) + n - 1) // n
    return [fs[i * per:(i + 1) * per] for i in range(n)]
for v in ("front", "side", "threequarter"):
    for k, page in enumerate(paged(sorted(glob.glob(f"{D}/{v}-full-*.png")), 25)):
        if page: sheet(page, 5, 420, 420, f"{O}/{v}-{string.ascii_uppercase[k]}.png")
for v in ("side", "front"):
    for k, page in enumerate(paged(sorted(glob.glob(f"{D}/feet-{v}-*.png")), 40)):
        if page: sheet(page, 4, 480, 160, f"{O}/feet-{v}-{string.ascii_uppercase[k]}.png")
print(sorted(os.listdir(O)))
