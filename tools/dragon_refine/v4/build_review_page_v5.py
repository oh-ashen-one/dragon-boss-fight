#!/usr/bin/env python3
"""Add the "Round 3 fix" card (v5 Actions) to each fixed move on Local/dragon-review-20261029/serve/index.html.
Same contract as build_review_page_v4.py: edits the live page in place, keeps the lazy data-src / preload="none" videos and the
IntersectionObserver script (rangeserver.py untouched), idempotent (old round-3 cards are replaced), written atomically.
Videos: video/clip_<label>_<cam>.mp4 -> serve/<prefix>_r3_<cam>.mp4. Captions carry the measure_v5.json (bone-space) numbers.
Moves whose renders are still queued get no card (listed as missing)."""
import os, re, json, html, shutil, tempfile
from pathlib import Path
R = Path(os.environ.get("REVIEW_ROOT", Path(__file__).resolve().parents[3] / "Local/dragon-review-20261029"))
SERVE, VID = R / "serve", R / "video"
ANG = [("threequarter", "Three-quarter"), ("front", "Front"), ("left", "Left")]
CARDS = [
 ("air_land", "AL5", "air_air_land", "ROUND 3 FIX (air_land_v5): one continuous descent (no frame 63-64 jump), glide then braking flare, belly slam with wings slapped onto the flanks, held, recovery, tail whip, panting; ends on the stance; extra-tall camera"),
 ("rise", "RI5", "after_rise", "ROUND 3 FIX (rise_v5): sequenced get-up from the collapse end: breath carried in, forelegs push the chest up, hind legs gather, wings open last; feet stepped one at a time (2+ always down), no pop at the handover"),
 ("collapse", "CO5", "after_collapse", "ROUND 3 FIX (collapse_v5): slower buckle, wings folded onto the flanks (no tent, no blade past the snout), head turned aside, lower lying silhouette, breathing kept"),
 ("roar", "RS5", "after_roar", "ROUND 3 FIX (roar_v5): flare 1.10-1.15x idle span with the wings raised (height >=1.25x), halves matched within 5%, irregular (non-periodic) tremor in the hold"),
 ("bite", "BI5", "after_bite", "ROUND 3 FIX (bite_v5): smooth time warp (no frame 50-51 twitch), wings half-open against the lunge so the near wing keeps its 3/4 area"),
 ("air_hover", "AH5", "air_air_hover", "ROUND 3 FIX (air_hover_v5): deeper downstroke, tail lag; loop exported as frames 0-129; extra-tall camera"),
 ("air_fire_down", "FD5", "air_air_fire_down", "ROUND 3 FIX (air_fire_down_v5): wing beat kept through the wind-up and fire hold; extra-tall camera"),
]
def vid(src): return f'<video data-src="{html.escape(src)}" controls loop muted playsinline preload="none"></video>'
page = (SERVE / "index.html").read_text()
page = re.sub(r'<div class="card r3">.*?</details></div>', "", page, flags=re.S)
if ".card.r3" not in page:
    page = page.replace("</style>", ".card.r3{outline:1px solid #3a6}</style>", 1)
added, missing = [], []
for sec, lab, pre, cap in CARDS:
    files = {}
    for a, _ in ANG:
        s = VID / f"clip_{lab}_{a}.mp4"
        if s.exists():
            shutil.copy2(s, SERVE / f"{pre}_r3_{a}.mp4"); files[a] = f"{pre}_r3_{a}.mp4"
        else: missing.append(s.name)
    if len(files) < 3: continue
    card = (f'<div class="card r3"><div class="cap">{html.escape(cap)}</div>{vid(files["threequarter"])}<details><summary>front / left</summary>'
            + "".join(f'<div class="sub">{n}</div>{vid(files[a])}' for a, n in ANG[1:]) + '</details></div>')
    m = re.search(r'(<section id="%s">.*?)(</div></section>)' % re.escape(sec), page, flags=re.S)
    if not m: missing.append("section " + sec); continue
    page = page[:m.start(2)] + card + page[m.start(2):]; added.append(sec)
fd, tmp = tempfile.mkstemp(dir=SERVE, prefix=".index.", suffix=".html")
with os.fdopen(fd, "w") as f: f.write(page)
os.chmod(tmp, 0o644); os.replace(tmp, SERVE / "index.html")
print("PAGE_V5", SERVE / "index.html", "added", added, "missing", missing)
