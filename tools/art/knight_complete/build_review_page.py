#!/usr/bin/env python3
"""Encode rendered review frames (front | side | three-quarter, 30 fps real time) and write
serve/index.html in the style of the dragon before/after page. Usage: build_review_page.py REVIEW_DIR [--serve DIR]
--serve (round 3): write the page and media into DIR (e.g. ../serve-round3) instead of REVIEW_DIR/serve, copy
rangeserver.py next to it, and lazy-load every video (data-src + IntersectionObserver, preload="none").
Round 4 options: --intra encodes every frame as a keyframe (-g 1 -bf 0, crf 12): with the default GOP the loop wrap
compares a P-frame with the I-frame and inflated the round-3 seam numbers by ~0.4x on slow loops (lossless frames: the
backpedal wrap is 1.00x of the mean, the MP4 1.42x). --frames-also DIR (repeatable) looks for a label's frames in DIR
when REVIEW_DIR/frames has none (re-encode round-3 renders without re-rendering). Jobs rendered with a subset of views
(e.g. top only) are stacked from whichever of front/side/threequarter/top exist."""
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(sys.argv[1]).resolve()
LAZY = "--serve" in sys.argv
SERVE = (R / sys.argv[sys.argv.index("--serve") + 1]).resolve() if LAZY else R / "serve"
MEDIA = SERVE / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
INTRA = "--intra" in sys.argv
ALSO = [Path(sys.argv[i + 1]).resolve() for i, a in enumerate(sys.argv) if a == "--frames-also"]
rows = json.loads((R / "rows.json").read_text())
extra = json.loads((R / "extra.json").read_text()) if (R / "extra.json").exists() else {}


def encode(label):
    out = MEDIA / (label + ".mp4")
    if out.exists():
        return "media/" + out.name
    views = []
    for base in [R / "frames"] + ALSO:
        frames = base / label
        views = [v for v in ("front", "side", "threequarter", "top") if (frames / (v + "_0000.png")).exists()]
        if views:
            break
    if not views:
        return None
    cmd = ["ffmpeg", "-loglevel", "error", "-y"]
    for v in views:
        cmd += ["-framerate", "30", "-i", str(frames / (v + "_%04d.png"))]
    if len(views) > 1:
        cmd += ["-filter_complex", "".join("[%d]" % i for i in range(len(views))) + "hstack=inputs=%d" % len(views)]
    cmd += ["-c:v", "libx264"] + (["-crf", "12", "-g", "1", "-bf", "0"] if INTRA else ["-crf", "22"]) + ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "30", str(out)]
    subprocess.run(cmd, check=True)
    return "media/" + out.name


css = ("body{background:#111;color:#eee;font:16px -apple-system,Helvetica,sans-serif;margin:24px}h1,h2{font-weight:600}"
       ".row{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}.card{flex:1 1 440px}video{width:100%;background:#000;border-radius:8px}"
       ".cap{color:#aaa;font-size:14px;margin-top:6px}.none{display:flex;align-items:center;justify-content:center;aspect-ratio:3/1;"
       "background:#1b1b1b;border-radius:8px;color:#777}.tag{display:inline-block;font-size:13px;color:#ccc;border:1px solid #444;"
       "border-radius:4px;padding:1px 6px;margin-left:8px;vertical-align:middle}code{color:#cfc}")


def video(src):
    if LAZY:
        return '<video data-src="%s" preload="none" controls loop muted playsinline></video>' % src
    return '<video src="%s" controls loop muted autoplay playsinline></video>' % src


LAZY_JS = ("<script>(function(){var vs=[].slice.call(document.querySelectorAll('video[data-src]'));"
           "function load(v){if(!v.src){v.src=v.dataset.src;}var p=v.play();if(p&&p.catch)p.catch(function(){});}"
           "function unload(v){if(!v.paused)v.pause();}"
           "if(!('IntersectionObserver' in window)){vs.forEach(load);return;}"
           "var io=new IntersectionObserver(function(es){es.forEach(function(e){e.isIntersecting?load(e.target):unload(e.target);});},{rootMargin:'200px 0px'});"
           "vs.forEach(function(v){io.observe(v);});})();</script>")
parts = ['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veyr knight: before / after</title>',
         '<style>' + css + '</style></head><body>',
         '<h1>%s</h1>' % html.escape(extra.get("title", "Veyr knight, 2026-10-28: completion pass, before / after")),
         '<p>Headless Blender 5.2 workbench renders of the exact GLBs the game imports (normalized clips), same rig, sword, '
         'lights and cameras for both sides. Each video is front | side | three-quarter at 30 fps real time, played at the '
         'in-game rate. Round 1: every view uses one fixed facing taken from the approved 1H idle (front = mesh forward), '
         'loops show exactly one cycle and actions end on their last frame (no frozen tail). Cameras follow the hips over a '
         'checker of 25 game-cm tiles (10.4 cm rig units). Changed rows compare round 0 (critic input) with round 1.</p>']
if extra.get("baseIntro") is not None:
    parts[-1] = "<p>" + extra["baseIntro"] + "</p>"
if extra.get("intro"):
    parts.append("<p>" + extra["intro"] + "</p>")
for r in rows:
    after = encode(r["after"])
    before = encode(r["before"]) if r["before"] else None
    parts.append('<h2>%s<span class="tag">%s</span></h2>' % (html.escape(r["slot"]), html.escape(r["status"])))
    parts.append('<div class="row"><div class="card">')
    parts.append(video(after) if after else '<div class="none">render missing</div>')
    tag = extra.get("afterTag", "AFTER (round 1)") if r.get("changed") else "CURRENT"
    parts.append('<div class="cap">%s: <code>%s</code> at %.2fx. %s</div></div>' % (tag, html.escape(r["afterSource"]), r["afterRate"], html.escape(r["note"])))
    parts.append('<div class="card">')
    if before:
        parts.append(video(before))
        btag = extra.get("beforeTag", "BEFORE (round 0)") if r.get("changed") else "BEFORE (previous slot clip)"
        parts.append('<div class="cap">%s: <code>%s</code> at %.2fx</div></div></div>' % (btag, html.escape(r["beforeSource"]), r["beforeRate"]))
    else:
        parts.append('<div class="none">none</div><div class="cap">BEFORE: none</div></div></div>')
for section in extra.get("sections", []):
    parts.append("<h2>%s</h2>" % html.escape(section["title"]))
    parts.append('<div class="row">')
    for item in section["items"]:
        if item.get("label"):
            item = dict(item, video=encode(item["label"]))
            if not item["video"]:
                parts.append('<div class="card"><div class="none">render missing</div><div class="cap">%s</div></div>' % html.escape(item["caption"]))
                continue
        if item.get("video"):
            parts.append('<div class="card">%s<div class="cap">%s</div></div>' % (video(item["video"]), html.escape(item["caption"])))
        elif item.get("image"):
            parts.append('<div class="card"><img src="%s" style="width:100%%;border-radius:8px"><div class="cap">%s</div></div>'
                         % (item["image"], html.escape(item["caption"])))
        else:
            parts.append('<div class="card"><div class="cap">%s</div></div>' % item["caption"])
    parts.append("</div>")
if LAZY:
    parts.append(LAZY_JS)
    src = R.parent / "serve" / "rangeserver.py"
    if src.exists() and not (SERVE / "rangeserver.py").exists():
        shutil.copy2(src, SERVE / "rangeserver.py")
parts.append("</body></html>")
(SERVE / "index.html").write_text("\n".join(parts) + "\n")
print("PAGE", SERVE / "index.html", len(rows), "rows")
