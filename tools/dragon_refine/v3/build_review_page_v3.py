#!/usr/bin/env python3
"""Build Local/dragon-review-20261029/serve/ : per move, the Seedance source clip, the hand-keyed before (where one exists),
the raw video2rig fit and the refined Action, three angles. No server is started. Run on the Studio."""
import os, shutil, html, json
ROOT = __import__("os").environ.get("LOCAL_ROOT", str(__import__("pathlib").Path(__file__).resolve().parents[3] / "Local"))
AB = f"{ROOT}/ab-idle-20261028"
OUT = f"{ROOT}/dragon-review-20261029/serve"
CLIPS = f"{ROOT}/video2rig/dragon/clips"
os.makedirs(OUT, exist_ok=True)
copied, missing = {}, []
def put(src, dst):
    if not os.path.exists(src):
        missing.append(src); return None
    if not os.path.exists(f"{OUT}/{dst}") or os.path.getmtime(src) > os.path.getmtime(f"{OUT}/{dst}"):
        shutil.copy2(src, f"{OUT}/{dst}")
    copied[dst] = os.path.getsize(f"{OUT}/{dst}")
    return dst
def three(label, prefix):
    return {a: put(f"{AB}/video/clip_{label}_{a}.mp4", f"{prefix}_{a}.mp4") for a in ("threequarter", "front", "left")}
ANG = [("threequarter", "Three-quarter"), ("front", "Front"), ("left", "Left")]
RV = f"{ROOT}/dragon-review-20261029/video"
ROUND1 = {   # key: (label, caption)
 "roar": ("RS3", "Round 1 (roar_sd_v3): ends on the shared stance; wings flared in the hold (front span to 1.20x idle, one wing 1.255x; the rig tears the membrane past that); 0.35 cm head and chest tremor through the hold"),
 "collapse": ("CO3", "Round 1 (collapse_v3): the -Y wing clears the floor by an elbow fold (11.7 deg) and a 3 deg root lift (was a 9 deg root lift)"),
 "death": ("DE3", "Round 1 (death_v3): all motion damped to zero by frame 120 and held (nothing moves after 110)"),
 "bite": ("BI3", "Round 1 (bite_v3): jaw opens to 38 deg by frame 36 and snaps shut at 46; the frozen hold is compressed 32 to 12 frames and the recovery lengthened 30 to 40; shared stance at both ends"),
 "claw_swipe": ("CS3", "Round 1 (claw_swipe_v3): keys at container time (no 4-frame stutter); shared stance at both ends"),
 "stagger": ("ST3", "Round 1 (stagger_v3): 12 dead frames trimmed, recoil starts at frame 2; catch-step foot lifts 3 cm instead of dragging; shared stance"),
 "land": ("LA3", "Round 1 (land2_v3): ballistic arc on Spine_0, touchdown at frame 74 to 75 (was 84 to 86), feet put on the floor by IK, camera re-framed so the hop stays in shot"),
 "rise": ("RI3", "Round 1 (rise_v3, recovery from stance: starts and ends standing; a lying-start get-up needs a new clip): keys at container time, shared stance"),
}

# (key, title, source clip, raw label, refined label(s), before, summary, numbers)
MOVES = [
 ("idle", "Idle (3.75 s loop)", None, None, [("R2", "Refined video2rig idle (idle_v2)")],
  {"label": "G3", "caption": "Hand-keyed Dragon_Idle_Blender_v1r3"},
  "MiniMax clip fitted, refined in Blender (loop closed, feet planted). Blind critic round 2: refined 47, hand-keyed 41; both still below the shipped-boss bar.",
  "Check 0.58%; fit miss 1.73 px; seam 0.95x a step; feet 0 cm drift."),
 ("roar", "Roar (5 s)", "roar_sd2", None, [("RS1", "Seedance roar fitted and refined (roar_sd_v2)")],
  None, "Half-open wings, inside the rig's 1.27x limit. The move does not return to stance (engine blend into idle).",
  "Check 1.13%; fit miss 3.30 px, outline 0.76 / 0.85, twist 5.5 deg; feet 1.3 / 5.3 / 0.03 / 0.04 cm to 0."),
 ("collapse", "Collapse (6 s, ends lying flat)", "collapse", "CO0", [("CO1", "Refined (collapse_v2)")], None,
  "Tail was curled sideways by the fit (the side panel crops it): relaid flat. -Y wing was 5 cm under the floor: lifted. Feet planted standing and lying.",
  "Check 1.17%; fit miss 4.72 px, outline 0.75 / 0.83, twist 21.4 deg; lowest point -0.89 to +0.14 cm; tail tip (-8.9, 27.2, 13.9) to (-53.4, 3.6, 1.3) cm."),
 ("death", "Death (7 s, ends on the right flank)", "death", "DE0", [("DE1", "Refined (death_v2)")], None,
  "Weakest fit of the set. Wing roots lifted up to 22 deg, body lifted up to 2.6 cm to clear the floor, feet planted before and after the fall; a leg segment still dips 1.85 cm under the floor in transit.",
  "Check 0.93% / limbs 1.36%; fit miss 7.07 px, outline 0.71 / 0.82, twist 51.7 deg."),
 ("bite", "Bite (5 s, returns to stance)", "bite", "BI0", [("BI1", "Refined (bite_v2)")], {"label": "HBI", "caption": "Hand-keyed Dragon_Bite_Blender_v2"},
  "The fit does not return to stance (8.0 rad off); the last 24 frames are blended onto frame 0. Wings stay under the 1.27x limit (1.18x). Strike reaches 24.2 cm against 24.4 cm of neck.",
  "Check 0.92% / limbs 1.22%; fit miss 3.76 px, outline 0.78 / 0.80, no warnings; feet 5.7 cm to 0."),
 ("claw_swipe", "Claw swipe (5 s, right foreleg)", "claw_swipe", "CS0", [("CS1", "Refined (claw_swipe_v2, reader-78)")], {"label": "HCS", "caption": "Hand-keyed Dragon_ClawSwipe_Blender_v1"},
  "Reader-78 kept over reader-64 (twist 41.8 vs 65.8 deg; reader-64 lifts the hind feet 2.6 cm). Foreleg peak reach 25.1 cm of 30.1. Three feet planted, swinging foot free frames 31 to 105.",
  "Check 0.81% / limbs 0.74%; fit miss 2.63 px, outline 0.77 / 0.88."),
 ("stagger", "Stagger (5 s, returns to stance)", "stagger", "ST0", [("ST1", "Refined (stagger_v2)")], None,
  "Left forefoot takes a 7.75 cm catch-step (free frames 24 to 101), other three feet planted; end blended onto frame 0 over 24 frames.",
  "Check 0.85% / limbs 1.17%; fit miss 4.49 px, outline 0.77 / 0.82, twist 13.5 deg."),
 ("land", "Hop and hard landing (land2, 4.9 s)", "land2", "LA0", [("LA1", "Refined (land2_v2)")], {"label": "HLA", "caption": "Hand-keyed Dragon_Land_Blender_v1r2"},
  "Regenerated clip (the first failed the check, 1.76%). The prompt asked for a knee-high hop; the fit rises 28.9 cm (0.59 body heights). Takeoff frame 39, feet down 84 to 86, landing shock recorded at 3.583 s.",
  "Check 0.86% / limbs 0.88%; fit miss 2.83 px, outline 0.79 / 0.87, twist 40.3 deg; feet planted 0.02 cm."),
 ("rise", "Rise / recovery (5 s)", "rise", "RI0", [("RI1", "Refined (rise_v2)")], None,
  "Rears onto the hind legs mid-clip (forefeet off the floor frames 66 to 105, up to 23.5 cm); hind feet planted throughout. Starts standing: 21 cm mean vertex distance from the collapse's last frame, so the engine has to blend the get-up.",
  "Check 1.17% / limbs 0.99%; fit miss 3.07 px, outline 0.81 / 0.84, twist 62.2 deg."),
 ("idle_look", "Watchful idle (8 s loop)", "idle_look", "IL0", [("R2", "idle_v2 (the existing idle, 3.75 s)"), ("IL1", "idle_look_v2: the look clip alone"), ("IL2", "Layered: idle_v2 body + look head (idle_layered_v2)")], None,
  "Head turns 38 deg toward the dragon's right (the prompt said left; the generator mirrored it) but breathes only 0.3 cm; the layered Action keeps idle_v2's 1.5 cm breathing, tail and wings with 46 deg of head yaw.",
  "Check 1.02% / limbs 0.91%; fit miss 2.00 px, outline 0.84 / 0.92; seam 0.98x / 0.93x."),
 ("takeoff", "Takeoff (no AI version)", None, None, [], {"label": "HTO", "caption": "Hand-keyed Dragon_Takeoff_Blender_v1r2 (the AI versions failed the check twice: 2.14% and 2.41%)"},
  "Airborne moves need a flying start picture and a reader trained on it.", ""),
]
cards = []
for key, title, src, raw, refs, before, summary, nums in MOVES:
    cells = []
    if src:
        p = put(f"{CLIPS}/{src}.mp4", f"source_{src}.mp4")
        if p: cells.append(("Seedance source (front | side panels)", [("", p)]))
    if before:
        if before["label"] == "G3":
            files = {"threequarter": put(f"{AB}/serve/before_handkeyed_threequarter.mp4", "before_idle_threequarter.mp4"),
                     "front": put(f"{AB}/serve/before_handkeyed_front.mp4", "before_idle_front.mp4"),
                     "left": put(f"{AB}/serve/before_handkeyed_left.mp4", "before_idle_left.mp4")}
        else:
            files = three(before["label"], f"before_{key}")
        cells.append(("BEFORE: " + before["caption"], [(a, files[a]) for a, _ in ANG if files.get(a)]))
    if raw:
        f = three(raw, f"raw_{key}")
        cells.append(("Raw video2rig fit", [(a, f[a]) for a, _ in ANG if f.get(a)]))
    for lab, cap in refs:
        if lab == "R2":
            f = {a: put(f"{AB}/serve/after_video2rig_{a}.mp4", f"after_idle_{a}.mp4") for a, _ in ANG}
        else:
            f = three(lab, f"after_{key}_{lab}")
        cells.append(("AFTER: " + cap, [(a, f[a]) for a, _ in ANG if f.get(a)]))
    if key in ROUND1:
        lab, cap = ROUND1[key]
        f = {a: put(f"{RV}/clip_{lab}_{a}.mp4", f"after_{key}_r1_{a}.mp4") for a, _ in ANG}
        cells.append(("ROUND 1: " + cap, [(a, f[a]) for a, _ in ANG if f.get(a)]))
    cards.append((key, title, summary, nums, cells))
# extra: roar older clips from the first page
for dst, src in (("roar_after_threequarter.mp4", "roar_seedance_threequarter.mp4"), ("roar_after_front.mp4", "roar_seedance_front.mp4"), ("roar_after_left.mp4", "roar_seedance_left.mp4"), ("roar_source.mp4", "roar_seedance_source.mp4"), ("roar_minimax_handflared_threequarter.mp4", "roar_minimax_handflared_threequarter.mp4")):
    put(f"{AB}/serve/{src}", dst)
def vid(src, cls=""):
    return f'<video data-src="{html.escape(src)}" controls loop muted playsinline preload="none" {cls}></video>'
body = []
for key, title, summary, nums, cells in cards:
    h = [f'<section id="{key}"><h2>{html.escape(title)}</h2><p class="sum">{html.escape(summary)}</p><p class="num">{html.escape(nums)}</p><div class="row">']
    for cap, vids in cells:
        if key == "roar" and cap.startswith("AFTER"):
            vids = [("threequarter", "roar_after_threequarter.mp4"), ("front", "roar_after_front.mp4"), ("left", "roar_after_left.mp4")]
        if len(vids) == 1 and vids[0][0] == "":
            h.append(f'<div class="card wide"><div class="cap">{html.escape(cap)}</div>{vid(vids[0][1])}</div>')
        else:
            main = vids[0]
            inner = f'<div class="cap">{html.escape(cap)}</div>{vid(main[1])}'
            if len(vids) > 1:
                inner += '<details><summary>front / left</summary>' + "".join(f'<div class="sub">{dict(ANG)[a]}</div>{vid(v)}' for a, v in vids[1:]) + '</details>'
            h.append(f'<div class="card">{inner}</div>')
    if key == "roar":
        h.append(f'<div class="card"><div class="cap">Earlier MiniMax roar, wing flare hand-keyed to the rig limit</div>{vid("roar_minimax_handflared_threequarter.mp4")}</div>')
    h.append("</div></section>")
    body.append("".join(h))
AIRDIR = f"{ROOT}/video2rig/dragon-air"
AIRS = [
 ("air_hover", "Hover idle (air_hover, 5 s loop)", "air_hover", "AH0", "AH1", "Start picture = the hover pose. The fit does not return to the start pose (7.2 rad off): the last 24 frames are blended back onto hover_pose_v1. The wings barely beat in the fit.",
  "Check WARN (no panel check with perspective cameras; centroid proxy: 0.14% of height median). Fit: median miss 2.57 px, outline 0.74 / 0.88, max twist 26.4 deg, no warnings."),
 ("air_land", "Descent and hard landing (air_land, 6 s)", "air_land", "AL0", "AL1", "Start hover, end ground picture. The fit's landing frames thrash (leg bones flip 100 to 180 deg a frame, outline down to 0.30), so the touchdown is authored: legs held from frame 84, all four feet planted by IK on the floor from frame 90, the last 40 frames crossfaded onto the standing stance.",
  "Check WARN (start pose covers frame 0 only 0.83). Fit: median miss 4.84 px, outline 0.66 / 0.71, max twist 77 deg, 297 deg bone flip at frame 106."),
 ("takeoff3", "Takeoff (takeoff3, 5 s)", "takeoff3", "TK0", "TK1", "Start ground picture, end hover picture. Wings clamped to the 1.27x limit (19 frames on one wing). The fit rises to 115 cm and settles to the hover height (63.8 cm): the rise overshoots the hover.",
  "Check WARN (start pose covers frame 0 only 0.55 / 0.46 because the project start pose is the hover). Fit: median miss 5.53 px, outline 0.61 / 0.70, max twist 69 deg, 112 spikes smoothed."),
 ("air_fire_down", "Aerial fire pose (air_fire_down, 8 s)", "air_fire_down", "FD0", "FD1", "Body pitches nose-down in the fit (hip-to-chest line from +21 deg to -8 deg, frames 72 to 160) and the pitch is kept; the root height is pinned to the hover height (the fit sank 7.5 cm); the jaw (not fitted) is authored open 40 deg from frame 80 to 160 for the Niagara window; ends blended onto the hover pose.",
  "Check WARN (no panel check). Fit: median miss 4.31 px, outline 0.81 / 0.83, max twist 31 deg, no warnings."),
]
put(f"{AIRDIR}/start/start.png", "air_hover_start_picture.png"); put(f"{AIRDIR}/start-ground/start.png", "air_ground_start_picture.png")
air_html = ['<section id="airborne"><h2>Airborne (hover start picture, perspective cameras, airborne reader)</h2><p class="sum">The ground start picture cannot carry airborne moves (land and takeoff failed the check three times), so these use a hover start picture with the floor and its shadow visible, and a reader trained on it (held-out median 7.31 px front / 6.68 px side). The review renders use the tall camera.</p>'
            f'<div class="row"><div class="card"><div class="cap">Hover start picture</div><img src="air_hover_start_picture.png" style="width:100%;border-radius:6px"></div><div class="card"><div class="cap">Ground start picture, same cameras</div><img src="air_ground_start_picture.png" style="width:100%;border-radius:6px"></div></div></section>']
for key, title, srcc, raw, ref, summ, nums in AIRS:
    cells = []
    p = put(f"{AIRDIR}/clips/{srcc}.mp4", f"air_source_{srcc}.mp4")
    if p: cells.append(("Seedance source (front | side panels)", [("", p)]))
    for lab, cap in ((raw, "Raw video2rig fit"), (ref, "Refined (v3 pipeline)")):
        f = {a: put(f"{RV}/clip_{lab}_{a}.mp4", f"air_{key}_{lab}_{a}.mp4") for a, _ in ANG}
        if any(f.values()): cells.append((cap, [(a, f[a]) for a, _ in ANG if f.get(a)]))
    h = [f'<section id="{key}"><h2>{html.escape(title)}</h2><p class="sum">{html.escape(summ)}</p><p class="num">{html.escape(nums)}</p><div class="row">']
    for cap, vids in cells:
        if len(vids) == 1 and vids[0][0] == "":
            h.append(f'<div class="card wide"><div class="cap">{html.escape(cap)}</div>{vid(vids[0][1])}</div>')
        else:
            inner = f'<div class="cap">{html.escape(cap)}</div>{vid(vids[0][1])}'
            if len(vids) > 1:
                inner += '<details><summary>front / left</summary>' + "".join(f'<div class="sub">{dict(ANG)[a]}</div>{vid(v)}' for a, v in vids[1:]) + '</details>'
            h.append(f'<div class="card">{inner}</div>')
    h.append("</div></section>"); air_html.append("".join(h))
body.extend(air_html)
nav = " ".join(f'<a href="#{k}">{html.escape(t.split(" (")[0])}</a>' for k, t, *_ in cards) + ' <a href="#airborne">Airborne</a>'
page = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veyr dragon moves: before / raw / after (2026-10-29)</title>
<style>:root{{--bg:#111;--fg:#eee;--mut:#aaa;--card:#1b1b1b}}body{{background:var(--bg);color:var(--fg);font:16px -apple-system,Helvetica,sans-serif;margin:0 16px 48px}}
h1{{font-weight:600;margin:24px 0 4px}}h2{{font-weight:600;margin:0 0 4px}}nav{{display:flex;flex-wrap:wrap;gap:8px 14px;margin:12px 0 20px}}nav a{{color:#9cf;text-decoration:none;font-size:14px}}
section{{margin:0 0 36px;padding-top:16px;border-top:1px solid #333}}.sum{{margin:4px 0;color:#ddd;max-width:900px}}.num{{margin:2px 0 12px;color:var(--mut);font-size:14px;max-width:900px}}
.row{{display:flex;gap:16px;flex-wrap:wrap}}.card{{flex:1 1 360px;max-width:520px;background:var(--card);border-radius:8px;padding:8px}}.card.wide{{flex:1 1 440px;max-width:640px}}
video{{width:100%;background:#000;border-radius:6px;display:block}}.cap{{color:var(--mut);font-size:13px;margin:2px 0 6px}}.sub{{color:var(--mut);font-size:12px;margin:8px 0 2px}}details{{margin-top:8px}}summary{{color:#9cf;font-size:13px;cursor:pointer}}
.note{{color:var(--mut);font-size:14px;max-width:900px}}</style></head><body>
<h1>Veyr dragon moves: source, before, raw fit, after</h1>
<p class="note">Same rig, mesh, cameras and lighting for every render (the ab-idle-20261028 set-up). BEFORE = the hand-keyed Blender move where one exists; RAW = the video2rig fit straight from the clip (feet may slide, wings may clip the floor); AFTER = the scripted refinement. Seedance 2.5 clips from the rig's own start picture. Videos are muted and loop; serve with rangeserver.py (Safari needs byte ranges). Takeoff and the first land failed the check and are not fitted.</p>
<nav>{nav}</nav>{"".join(body)}<script>
// Chrome stops loading media past about 75 elements per page: a video gets its src only while it is near the viewport.
(function () {{
  var io = new IntersectionObserver(function (entries) {{
    entries.forEach(function (e) {{
      var v = e.target;
      if (e.isIntersecting) {{ if (!v.getAttribute('src')) {{ v.src = v.dataset.src; v.load(); }} }}
      else if (v.getAttribute('src')) {{ v.pause(); v.removeAttribute('src'); v.load(); }}
    }});
  }}, {{rootMargin: '400px 0px'}});
  document.querySelectorAll('video[data-src]').forEach(function (v) {{ io.observe(v); }});
}})();
</script></body></html>'''
open(f"{OUT}/index.html", "w").write(page)
shutil.copy2(f"{AB}/rangeserver.py", f"{OUT}/rangeserver.py")
json.dump({"files": copied, "missing": missing}, open(f"{OUT}/../manifest.json", "w"), indent=1)
print("PAGE", OUT, len(copied), "files", "missing:", len(missing))
for m in missing: print("MISSING", m)
