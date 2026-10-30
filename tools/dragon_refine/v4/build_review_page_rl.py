#!/usr/bin/env python3
"""Add the "Rise from lying" section to Local/dragon-review-20261029/serve/index.html (right after "Rise / recovery").
Same contract as build_review_page_v5.py: edits the live page in place, keeps the lazy data-src / preload="none" videos and the
IntersectionObserver script (rangeserver.py untouched), idempotent (an old rise_lying section and nav link are replaced), written atomically.
Cards: the Seedance clip (front | side panels), the raw video2rig fit film, the authored rise v5 (already served as after_rise_r3_*), and the refined
Action `rise_lying_v1` (video/clip_RL1_<cam>.mp4 -> serve/after_rise_lying_RL1_<cam>.mp4). Captions carry refine_rl/measure.json numbers when present.
A refined card is only written when all three camera videos exist (else the section lists what is still missing)."""
import os, re, json, html, shutil, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
R = Path(os.environ.get("REVIEW_ROOT", REPO / "Local/dragon-review-20261029"))
SERVE, VID = R / "serve", R / "video"
PRJ = REPO / "Local/video2rig/dragon-lying"
ANG = [("threequarter", "Three-quarter"), ("front", "Front"), ("left", "Left")]
LAB, PRE = "RL1", "after_rise_lying"
def vid(src): return f'<video data-src="{html.escape(src)}" controls loop muted playsinline preload="none"></video>'
page = (SERVE / "index.html").read_text()
page = re.sub(r'<section id="rise_lying">.*?</section>', "", page, flags=re.S)
page = page.replace(' <a href="#rise_lying">Rise from lying</a>', "")
missing = []
def copy_in(src, name):
    if Path(src).exists(): shutil.copy2(src, SERVE / name); return name
    missing.append(str(src)); return None
src_clip = copy_in(REPO / "Local/video2rig/dragon/clips/rise_lying.mp4", "source_rise_lying.mp4")
raw_film = copy_in(PRJ / "work/rise_lying/review.mp4", "raw_rise_lying_review.mp4")
files = {}
for a, _ in ANG:
    s = VID / f"clip_{LAB}_{a}.mp4"
    if s.exists(): shutil.copy2(s, SERVE / f"{PRE}_{LAB}_{a}.mp4"); files[a] = f"{PRE}_{LAB}_{a}.mp4"
    else: missing.append(s.name)
num = ""
mj = PRJ / "refine_rl/measure.json"
if mj.exists():
    m = json.loads(mj.read_text()).get("rise_lying", {}); bits = []
    if "hold_s" in m: bits.append(f"opening hold {m['hold_s']} s")
    if "channels" in m: bits.append(f"wing twist max {max(m['channels']['wing_twist_max_deg'].values()):.1f} deg, wing step max {m['channels']['wing_euler_step_max_deg']['deg']:.1f} deg/frame")
    if "last_vs_idle" in m: bits.append(f"last frame vs idle {m['last_vs_idle']['max_vertex_mm']:.2f} mm")
    if "silhouette_vs_source" in m and "wing_window" in m["silhouette_vs_source"]:
        ww = m["silhouette_vs_source"]["wing_window"]; bits.append(f"wing-window outline match vs the clip {ww['front']['raw_fit']:.2f}/{ww['side']['raw_fit']:.2f} raw -> {ww['front']['action']:.2f}/{ww['side']['action']:.2f}")
    if bits: num = '<p class="num">' + html.escape("; ".join(bits)) + "</p>"
cards = []
if src_clip: cards.append(f'<div class="card wide"><div class="cap">Seedance clip (rise_lying, 6 s; front | side panels)</div>{vid(src_clip)}</div>')
if raw_film: cards.append(f'<div class="card wide"><div class="cap">Raw video2rig fit on the lying rig (review film: clip | model)</div>{vid(raw_film)}</div>')
if (SERVE / "after_rise_r3_threequarter.mp4").exists():
    cards.append(f'<div class="card"><div class="cap">Authored rise v5 (the A/B reference)</div>{vid("after_rise_r3_threequarter.mp4")}</div>')
if len(files) == 3:
    cap = ("Rise from lying (rise_lying_v1): the clip's four beats kept (still, push-up, wing-spread shake, settle); opening hold trimmed to ~1.25 s with an ease from "
           "the collapse end pose; wing twist capped at 25 deg and steps at 8 deg per frame; right hind knee off its limit; feet locked; ends on the idle pose")
    cards.append(f'<div class="card"><div class="cap">{html.escape(cap)}</div>{vid(files["threequarter"])}<details><summary>front / left</summary>'
                 + "".join(f'<div class="sub">{n}</div>{vid(files[a])}' for a, n in ANG[1:]) + "</details></div>")
sec = ('<section id="rise_lying"><h2>Rise from lying (4.2 s)</h2><p class="sum">Starts on the collapse end pose, lies still ~1.25 s, pushes up forelegs first, '
       'flares the wings, settles into the idle pose (hand-off to the idle loop).</p>' + num + '<div class="row">' + "".join(cards) + "</div></section>")
m_ = re.search(r'(<section id="rise">.*?</section>)', page, flags=re.S)
if not m_: raise SystemExit("section id=rise not found in the page")
page = page[:m_.end()] + sec + page[m_.end():]
page = page.replace('<a href="#rise">Rise / recovery</a>', '<a href="#rise">Rise / recovery</a> <a href="#rise_lying">Rise from lying</a>', 1)
fd, tmp = tempfile.mkstemp(dir=SERVE, prefix=".index.", suffix=".html")
with os.fdopen(fd, "w") as f: f.write(page)
os.chmod(tmp, 0o644); os.replace(tmp, SERVE / "index.html")
print("PAGE_RL", SERVE / "index.html", "refined card", "yes" if len(files) == 3 else "no", "missing", missing)
