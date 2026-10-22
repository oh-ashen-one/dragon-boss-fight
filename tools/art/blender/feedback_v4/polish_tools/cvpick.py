"""cvpick.py DIR OUT FRAMES(comma) VIEWS(comma) [crop]: rows=views, cols=frames, cropped to the figure region."""
import sys
from PIL import Image, ImageDraw
D, O, F, V = sys.argv[1:5]; F = [int(x) for x in F.split(",")]; V = V.split(","); cr = (90, 0, 390, 400)
w, h = cr[2] - cr[0], cr[3] - cr[1]; sh = Image.new("RGB", (len(F) * w, len(V) * h), (20, 20, 20)); d = ImageDraw.Draw(sh)
for j, v in enumerate(V):
    for i, f in enumerate(F):
        im = Image.open(f"{D}/{v}-full-{f:04d}.png").convert("RGB").crop(cr); sh.paste(im, (i * w, j * h)); d.text((i * w + 4, j * h + 4), f"{v[:5]} f{f}", fill=(255, 255, 0))
sh.save(O)
