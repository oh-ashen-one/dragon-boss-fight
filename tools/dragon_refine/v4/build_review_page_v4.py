#!/usr/bin/env python3
"""Add the "Round 2 fix" card (v4 Actions) to each move on Local/dragon-review-20261029/serve/index.html.
Edits the live page in place (keeps the lazy data-src + IntersectionObserver script and rangeserver.py), idempotent
(old round-2 cards are replaced), written atomically (temp file + os.replace) because the page is served while it changes.
Videos: video/clip_<label>_<cam>.mp4 -> serve/<prefix>_r2_<cam>.mp4. Captions carry the measure_v4.json numbers."""
import os, re, json, html, shutil, tempfile
from pathlib import Path
R = Path(os.environ.get("REVIEW_ROOT", Path(__file__).resolve().parents[3] / "Local/dragon-review-20261029"))
SERVE, VID = R / "serve", R / "video"
MJ = json.load(open(R / "measure_v4.json")) if (R / "measure_v4.json").exists() else {}
ANG = [("threequarter", "Three-quarter"), ("front", "Front"), ("left", "Left")]
# section id on the page, label, served prefix, caption
CARDS = [
 ("roar", "RS4", "after_roar", "ROUND 2 FIX (roar_v4): both wings flared to the rig limit and matched, slower open and close, living hold (breath heave, head and wing-tip tremor, tail lash)"),
 ("collapse", "CO4", "after_collapse", "ROUND 2 FIX (collapse_v4): breathing while lying (spine, chest, folded wings, tail, 40-frame breaths)"),
 ("bite", "BI4", "after_bite", "ROUND 2 FIX (bite_v4): full-reach freeze cut to a short worry-shake, lean into the strike"),
 ("land", "LA4", "after_land", "ROUND 2 FIX (land2_v4): feet eased on and off the floor by IK over 8 frames at takeoff and touchdown"),
 ("rise", "RI4", "after_rise", "ROUND 2 FIX (rise_v4): starts on the collapse's last frame, authored get-up (head and chest first, feet step under the body), then the sourced rise"),
 ("air_hover", "AH4", "air_air_hover", "ROUND 2 FIX (air_hover_v4): procedural wing beats (26-frame period, 5 per loop), body bob riding the wings, de-stuttered loop; extra-tall camera"),
 ("takeoff3", "TK4", "air_takeoff3", "ROUND 2 FIX (takeoff3_v4): feet down to frame ~54, crouch, wind-up, liftoff on a downstroke, rise ends at the hover height; extra-tall camera"),
 ("air_land", "AL4", "air_air_land", "ROUND 2 FIX (air_land_v4): beats until the flare, braking flare before contact, impact compression, IK-eased contact, ends on the stance; extra-tall camera"),
 ("air_fire_down", "FD4", "air_air_fire_down", "ROUND 2 FIX (air_fire_down_v4): wing beats continue through the fire hold; extra-tall camera"),
]
def vid(src): return f'<video data-src="{html.escape(src)}" controls loop muted playsinline preload="none"></video>'
page = (SERVE / "index.html").read_text()
page = re.sub(r'<div class="card r2">.*?</details></div>', "", page, flags=re.S)
added, missing = [], []
for sec, lab, pre, cap in CARDS:
    files = {}
    for a, _ in ANG:
        s = VID / f"clip_{lab}_{a}.mp4"
        if s.exists():
            shutil.copy2(s, SERVE / f"{pre}_r2_{a}.mp4"); files[a] = f"{pre}_r2_{a}.mp4"
        else: missing.append(str(s))
    if len(files) < 3: continue
    card = (f'<div class="card r2"><div class="cap">{html.escape(cap)}</div>{vid(files["threequarter"])}<details><summary>front / left</summary>'
            + "".join(f'<div class="sub">{n}</div>{vid(files[a])}' for a, n in ANG[1:]) + '</details></div>')
    m = re.search(r'(<section id="%s">.*?)(</div></section>)' % re.escape(sec), page, flags=re.S)
    if not m: missing.append("section " + sec); continue
    page = page[:m.start(2)] + card + page[m.start(2):]; added.append(sec)
fd, tmp = tempfile.mkstemp(dir=SERVE, prefix=".index.", suffix=".html")
with os.fdopen(fd, "w") as f: f.write(page)
os.chmod(tmp, 0o644); os.replace(tmp, SERVE / "index.html")
print("PAGE_V4", SERVE / "index.html", "added", added, "missing", missing)
