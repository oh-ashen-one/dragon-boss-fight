#!/usr/bin/env python3
"""Encode rendered review frames (front | side | three-quarter, 30 fps real time) and write
serve/index.html in the style of the dragon before/after page. Usage: build_review_page.py REVIEW_DIR"""
import html
import json
import subprocess
import sys
from pathlib import Path

R = Path(sys.argv[1]).resolve()
SERVE = R / "serve"
MEDIA = SERVE / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
rows = json.loads((R / "rows.json").read_text())
extra = json.loads((R / "extra.json").read_text()) if (R / "extra.json").exists() else {}


def encode(label):
    out = MEDIA / (label + ".mp4")
    frames = R / "frames" / label
    if out.exists():
        return "media/" + out.name
    if not (frames / "front_0000.png").exists():
        return None
    if not out.exists():
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", "30", "-i", str(frames / "front_%04d.png"),
               "-framerate", "30", "-i", str(frames / "side_%04d.png"), "-framerate", "30", "-i", str(frames / "threequarter_%04d.png"),
               "-filter_complex", "[0][1][2]hstack=inputs=3", "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", "-r", "30", str(out)]
        subprocess.run(cmd, check=True)
    return "media/" + out.name


css = ("body{background:#111;color:#eee;font:16px -apple-system,Helvetica,sans-serif;margin:24px}h1,h2{font-weight:600}"
       ".row{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}.card{flex:1 1 440px}video{width:100%;background:#000;border-radius:8px}"
       ".cap{color:#aaa;font-size:14px;margin-top:6px}.none{display:flex;align-items:center;justify-content:center;aspect-ratio:3/1;"
       "background:#1b1b1b;border-radius:8px;color:#777}.tag{display:inline-block;font-size:13px;color:#ccc;border:1px solid #444;"
       "border-radius:4px;padding:1px 6px;margin-left:8px;vertical-align:middle}code{color:#cfc}")
parts = ['<!doctype html><html><head><meta charset="utf-8"><title>Veyr knight: before / after</title>',
         '<style>' + css + '</style></head><body>',
         '<h1>%s</h1>' % html.escape(extra.get("title", "Veyr knight, 2026-10-28: completion pass, before / after")),
         '<p>Headless Blender 5.2 workbench renders of the exact GLBs the game imports (normalized clips), same rig, sword, '
         'lights and cameras for both sides. Each video is front | side | three-quarter at 30 fps real time, played at the '
         'in-game rate. Round 1: every view uses one fixed facing taken from the approved 1H idle (front = mesh forward), '
         'loops show exactly one cycle and actions end on their last frame (no frozen tail). Cameras follow the hips over a '
         'checker of 25 game-cm tiles (10.4 cm rig units). Changed rows compare round 0 (critic input) with round 1.</p>']
if extra.get("intro"):
    parts.append("<p>" + extra["intro"] + "</p>")
for r in rows:
    after = encode(r["after"])
    before = encode(r["before"]) if r["before"] else None
    parts.append('<h2>%s<span class="tag">%s</span></h2>' % (html.escape(r["slot"]), html.escape(r["status"])))
    parts.append('<div class="row"><div class="card">')
    parts.append('<video src="%s" controls loop muted autoplay playsinline></video>' % after if after else '<div class="none">render missing</div>')
    tag = extra.get("afterTag", "AFTER (round 1)") if r.get("changed") else "CURRENT"
    parts.append('<div class="cap">%s: <code>%s</code> at %.2fx. %s</div></div>' % (tag, html.escape(r["afterSource"]), r["afterRate"], html.escape(r["note"])))
    parts.append('<div class="card">')
    if before:
        parts.append('<video src="%s" controls loop muted autoplay playsinline></video>' % before)
        btag = extra.get("beforeTag", "BEFORE (round 0)") if r.get("changed") else "BEFORE (previous slot clip)"
        parts.append('<div class="cap">%s: <code>%s</code> at %.2fx</div></div></div>' % (btag, html.escape(r["beforeSource"]), r["beforeRate"]))
    else:
        parts.append('<div class="none">none</div><div class="cap">BEFORE: none</div></div></div>')
for section in extra.get("sections", []):
    parts.append("<h2>%s</h2>" % html.escape(section["title"]))
    parts.append('<div class="row">')
    for item in section["items"]:
        if item.get("video"):
            parts.append('<div class="card"><video src="%s" controls loop muted autoplay playsinline></video><div class="cap">%s</div></div>'
                         % (item["video"], html.escape(item["caption"])))
        elif item.get("image"):
            parts.append('<div class="card"><img src="%s" style="width:100%%;border-radius:8px"><div class="cap">%s</div></div>'
                         % (item["image"], html.escape(item["caption"])))
        else:
            parts.append('<div class="card"><div class="cap">%s</div></div>' % item["caption"])
    parts.append("</div>")
parts.append("</body></html>")
(SERVE / "index.html").write_text("\n".join(parts) + "\n")
print("PAGE", SERVE / "index.html", len(rows), "rows")
