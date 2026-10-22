"""Acceptance test (critic's rewind test): no frame of segment B may be within mean absolute pixel difference THRESH of
ANY frame of segment A, in every view. Usage:
  python3 frame_similarity.py RENDER_DIR A0:A1 B0:B1 [THRESH=2.5] [--full]
By default frames are first brought to the critic's sheet scale (224 px tile, ~145 px figure): a square around the figure
of side 350 px (figure ~227 px in our 500 px renders) is resized to 224 px. --full compares whole 500 px frames (stricter).
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
args = [a for a in sys.argv[1:] if not a.startswith("--")]; full = "--full" in sys.argv
d = Path(args[0]); a0, a1 = map(int, args[1].split(":")); b0, b1 = map(int, args[2].split(":")); th = float(args[3]) if len(args) > 3 else 2.5
def load(p):
    im = Image.open(p).convert("L")
    if not full:
        w, h = im.size; cx, cy, half = w // 2, int(h * .554), 175
        im = im.crop((cx - half, cy - half, cx + half, cy + half)).resize((224, 224), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32)
out = {}
for view in ("front", "side", "threequarter", "rear"):
    fa = {i: load(d / f"{view}-{i:04d}.png") for i in range(a0, a1 + 1) if (d / f"{view}-{i:04d}.png").exists()}
    fb = {i: load(d / f"{view}-{i:04d}.png") for i in range(b0, b1 + 1) if (d / f"{view}-{i:04d}.png").exists()}
    if not fa or not fb: continue
    worst = min(((float(np.abs(x - y).mean()), j, i) for j, y in fb.items() for i, x in fa.items()))
    out[view] = {"minMeanAbsDiff": round(worst[0], 2), "lightB_frame": worst[1], "lightA_frame": worst[2], "pass": worst[0] >= th}
print({"scale": "full-500px" if full else "critic-224px-tile", **out}); sys.exit(0 if out and all(v["pass"] for v in out.values()) else 1)
