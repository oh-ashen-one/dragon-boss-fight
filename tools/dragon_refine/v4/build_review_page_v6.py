#!/usr/bin/env python3
"""Add the "Round 4 fix" card (v6 Actions) to each fixed move on Local/dragon-review-20261029/serve/index.html.
Same contract as build_review_page_v4.py: edits the live page in place, keeps the lazy data-src / preload="none" videos and the
IntersectionObserver script (rangeserver.py untouched), idempotent (old round-4 cards are replaced), written atomically.
Videos: video/clip_<label>_<cam>.mp4 -> serve/<prefix>_r4_<cam>.mp4. Captions carry the measure_v6.json (bone-space) numbers.
Moves whose renders are still queued get no card (listed as missing)."""
import os, re, json, html, shutil, tempfile
from pathlib import Path
R = Path(os.environ.get("REVIEW_ROOT", Path(__file__).resolve().parents[3] / "Local/dragon-review-20261029"))
SERVE, VID = R / "serve", R / "video"
ANG = [("threequarter", "Three-quarter"), ("front", "Front"), ("left", "Left")]
CARDS = [
 ("air_land", "AL6", "air_air_land", "ROUND 4 FIX (air_land_v6): wing fold after contact spread over 14 frames (v5 snapped shut in 2), panting + tail lash in the slam hold; extra-tall camera"),
 ("roar", "RS6", "after_roar", "ROUND 4 FIX (roar_v6): screen-left wing opened so both half-spans match (frame-0 centre), hold span 1.10-1.12x idle, irregular 9-10 frame tremor kept"),
 ("collapse", "CO6", "after_collapse", "ROUND 4 FIX (collapse_v6): flatter lying silhouette (hips and screen-right wing lowered, front height <=0.50 of standing), stronger non-synchronous breathing"),
 ("bite", "BI6", "after_bite", "ROUND 4 FIX (bite_v6): near wing held open through the strike (3/4 upper-left area >=0.7 of frame 0 at 44-50); everything else from v5"),
]
def vid(src): return f'<video data-src="{html.escape(src)}" controls loop muted playsinline preload="none"></video>'
page = (SERVE / "index.html").read_text()
page = re.sub(r'<div class="card r4">.*?</details></div>', "", page, flags=re.S)
if ".card.r4" not in page:
    page = page.replace("</style>", ".card.r4{outline:1px solid #a63}</style>", 1)
added, missing = [], []
for sec, lab, pre, cap in CARDS:
    files = {}
    for a, _ in ANG:
        s = VID / f"clip_{lab}_{a}.mp4"
        if s.exists():
            shutil.copy2(s, SERVE / f"{pre}_r4_{a}.mp4"); files[a] = f"{pre}_r4_{a}.mp4"
        else: missing.append(s.name)
    if len(files) < 3: continue
    card = (f'<div class="card r4"><div class="cap">{html.escape(cap)}</div>{vid(files["threequarter"])}<details><summary>front / left</summary>'
            + "".join(f'<div class="sub">{n}</div>{vid(files[a])}' for a, n in ANG[1:]) + '</details></div>')
    m = re.search(r'(<section id="%s">.*?)(</div></section>)' % re.escape(sec), page, flags=re.S)
    if not m: missing.append("section " + sec); continue
    page = page[:m.start(2)] + card + page[m.start(2):]; added.append(sec)
fd, tmp = tempfile.mkstemp(dir=SERVE, prefix=".index.", suffix=".html")
with os.fdopen(fd, "w") as f: f.write(page)
os.chmod(tmp, 0o644); os.replace(tmp, SERVE / "index.html")
print("PAGE_V6", SERVE / "index.html", "added", added, "missing", missing)
