#!/usr/bin/env python3
"""Fix round 5 review jobs. AFTER = round-5 clip (v030s plan), BEFORE = round-4 clip (v030r plan), both rendered here with
the SAME round-5 framing (labels r5-* and r4h-*), so the pair is like for like:
  RollAttack  res 810 px per view, ortho 3.2 rig m (1.5x the round-4 pixel density, 0.95 game cm/px) so the whole blade
              stays in frame through the strike (round 4 clipped it at 2.1 m) and the 25 cm checker does not alias
  blinks      res 540, ortho 2.1 (1.5x the round-4 density, 0.93 game cm/px)
Rows: in place (front | side | three-quarter). Sections: RollAttack with its root track (camera on the root), blinks with
root travel (fixed camera, hidden window not drawn), blink top views. No other clip changed in round 5.

Usage: review_jobs_r5.py REVIEW_DIR   (writes jobs.json, rows.json, extra.json)"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
OUT = Path(sys.argv[1]).resolve()
BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
P5 = {c["name"]: c for c in json.loads((BASE / "knight-v030s/import-plan-KnightB.json").read_text())["clips"]}
P4 = {c["name"]: c for c in json.loads((BASE / "knight-v030r/import-plan-KnightB.json").read_text())["clips"]}
plan2 = json.loads((BASE / "knight-v030p/import-plan-KnightB.json").read_text())
V = "knight_571e0abbfde2720e"
DISPLAY = str(Path(plan2["mesh_variants"][V]["file"]).relative_to(ROOT))
IDLE = {"": "Local/CustomuseAssets/Polish20261025/knight/IdleOneHand_Blender_v2r4.glb", "TwoHand": "Local/CustomuseAssets/Polish20261025/knight/IdleTwoHand_Blender_v2r4.glb"}
HIDDEN = [.207, .391]
FRAME = {"RollAttack": {"res": 810, "ortho": 3.2}, "Blink": {"res": 540, "ortho": 2.1}}
DUR = {}


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


def dur(p):
    if p not in DUR:
        DUR[p] = GLB(ROOT / p).duration()
    return DUR[p]


def fr(name):
    return FRAME["RollAttack" if name == "RollAttack" else "Blink"]


def inplace(label, c, views=None):
    p = rel(c["file"])
    j = dict({"label": label, "segments": [{"glb": p, "start": 0, "end": dur(p), "rate": c["gameplay_play_rate"], "loop": False, "even": True}],
              "blend": .1, "hold": 0, "display": DISPLAY}, **fr(c["name"]))
    if views:
        j["views"] = views
    return j


def blink(label, c):
    p = rel(c["file"]); idle = IDLE["TwoHand" if "TwoHand" in c["name"] else ""]
    return dict({"label": label, "camera": "fixed", "display": DISPLAY, "blend": .1, "hold": 0, "segments": [
        {"glb": idle, "start": 0, "end": .3, "rate": 1.0, "loop": True},
        {"glb": p, "start": 0, "end": dur(p), "rate": c["gameplay_play_rate"], "loop": False, "even": True, "hide": HIDDEN,
         "root": {"samplesCm": c["root_translation_samples_cm"], "rate": c["root_sample_rate"]}},
        {"glb": idle, "start": 0, "end": .4, "rate": 1.0, "loop": True}]}, **fr(c["name"]))


def roll_travel(label, c):
    p = rel(c["file"])
    return dict({"label": label, "camera": "root", "display": DISPLAY, "blend": .1, "hold": 0, "segments": [
        {"glb": p, "start": 0, "end": dur(p), "rate": c["gameplay_play_rate"], "loop": False, "even": True,
         "root": {"samplesCm": c["root_translation_samples_cm"], "rate": c["root_sample_rate"]}},
        {"glb": IDLE[""], "start": 0, "end": .4, "rate": 1.0, "loop": True}]}, **FRAME["RollAttack"])


NOTES = {
    "RollAttack": "rear foot lands from the roll on its final spot and never moves; front foot: lifted lunge step that lands with the "
                  "strike (rendered f32) and stays locked through the slash, then a lifted step back that moves only while it is >= ~14 cm "
                  "up; one recovery f36-f51 (body, arm, blade sweep, hips on one ramped profile, retimed by arc length). 0.95 game cm/px",
    "Blink": "round-4 clip with only the legs changed: feet re-planted on every key (round 4 dipped 6-12 cm into the floor between "
             "keys) and a heel lift about the planted toes on the two push frames (toe-off; trailing foot ~8 cm, leading ~4.5 cm). 0.93 game cm/px",
}
jobs, rows, sections = {}, [], []
for name in ("RollAttack", "BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand"):
    a = inplace("r5-" + name, P5[name]); b = inplace("r4h-" + name, P4[name]); jobs[a["label"]] = a; jobs[b["label"]] = b
    rows.append({"slot": name, "status": "round 5 (not approved)", "changed": True, "after": a["label"], "afterSource": Path(P5[name]["file"]).name,
                 "afterRate": P5[name]["gameplay_play_rate"], "before": b["label"], "beforeSource": Path(P4[name]["file"]).name,
                 "beforeRate": P4[name]["gameplay_play_rate"], "note": NOTES["RollAttack" if name == "RollAttack" else "Blink"]})
items = []
for lab, P in (("r5", P5), ("r4h", P4)):
    j = roll_travel("rt-%s-RollAttack" % lab, P["RollAttack"]); jobs[j["label"]] = j
    items.append({"label": j["label"], "caption": "%s RollAttack with its root track at %.3fx, then idle 0.4 s; camera on the root (after the 1.0 s "
                  "prefix the floor stands still, so any foot motion is real). Frame k = clip k x 0.0427 s, as the round-4 critique numbered it; "
                  "810 px per view over 3.2 rig m (0.95 game cm/px)" % ("round 5" if lab == "r5" else "round 4 (re-rendered with the round-5 framing)",
                                                                       P["RollAttack"]["gameplay_play_rate"])})
sections.append({"title": "Roll attack with root travel: round 5, then round 4 (same framing, whole blade in frame)", "items": items})
items = []
for lab, P in (("r5", P5), ("r4h", P4)):
    for name in ("BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand"):
        j = blink("rt-%s-%s" % (lab, name), P[name]); jobs[j["label"]] = j
        items.append({"label": j["label"], "caption": "%s %s: idle 0.3 s, blink at %.2fx, idle 0.4 s; hidden 0.18-0.34 s of action time; fixed camera; "
                      "push frames = video frames 13-14" % ("round 5" if lab == "r5" else "round 4", name, P[name]["gameplay_play_rate"])})
sections.append({"title": "Blinks with root travel (round 5, then round 4, same framing)", "items": items})
items = []
for lab, P in (("r5", P5), ("r4h", P4)):
    for name in ("BlinkLeft", "BlinkRight"):
        j = inplace("top-%s-%s" % (lab, name), P[name], ["top"]); jobs[j["label"]] = j
        items.append({"label": j["label"], "caption": "%s %s, top view (boss at the top), in place" % ("round 5" if lab == "r5" else "round 4", name)})
sections.append({"title": "Blink top views", "items": items})
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
(OUT / "extra.json").write_text(json.dumps({
    "title": "Veyr knight, fix round 5 (2026-10-30): round 5 vs round 4",
    "intro": "Only RollAttack and the four blinks changed in round 5 (every other clip is inherited unchanged from round 4). Both sides of "
             "every pair are rendered here with the same round-5 camera: RollAttack at 810 px per view over 3.2 rig m so the whole blade "
             "stays in frame, blinks at 540 px over 2.1 rig m, i.e. 1.5x the round-4 pixel density. All videos all-intra. Nothing here is approved.",
    "baseIntro": "Headless Blender workbench renders of the exact GLBs the game imports (normalized clips), same rig, sword, lights and "
                 "cameras on both sides. Each in-place video is front | side | three-quarter at 30 fps real time, played at the in-game rate, "
                 "one fixed facing taken from the approved 1H idle (front = mesh forward), camera on the hips over a checker of 25 game-cm "
                 "tiles. Changed rows compare round 5 (left) with round 4 (right).",
    "afterTag": "AFTER (round 5)", "beforeTag": "BEFORE (round 4)", "sections": sections}, indent=1) + "\n")
print(len(jobs), "jobs to render", len(rows), "rows", sum(len(s["items"]) for s in sections), "section items")
