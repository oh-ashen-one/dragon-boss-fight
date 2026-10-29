#!/usr/bin/env python3
"""Fix round 4 review jobs. AFTER = round-4 clip (v030r plan), BEFORE = round-3 clip (v030q plan). Round-3 frames are NOT
re-rendered: build_review_page.py --frames-also Local/knight-review-20261028/r3/frames re-encodes them (all-intra, like
the round-4 videos, so the loop wrap is not a P-frame vs I-frame comparison).

Renders only what is new:
  r4-<clip>            in-place, front | side | three-quarter, even phase sampling, mesh variant V (as round 3)
  top-r4-<clip>        top view (boss at the top, knight's right on the right) of the sprint strafes and blinks, so the
                       pelvis / leg-plane yaw is readable; top-r3-StrafeRun* as the BEFORE
  rt-r4-<clip>         root travel at in-game speed: sprints (camera follows the root), blinks (fixed camera, hidden window
                       not drawn), RollAttack with the plan's root track (camera follows the root: the floor scrolls under
                       planted feet, so the roll get-up / lunge contacts are judged in world space, not in place);
                       rt-r3-RollAttack as its BEFORE (round 3 never rendered the roll with its root track)
Unchanged rows (StrafeRight(2H), BackpedalGuard(2H): kept v030q files; StrafeLeft(2H): protected) reuse their r3 frames.

Usage: review_jobs_r4.py REVIEW_DIR   (writes jobs.json, rows.json, extra.json)"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
OUT = Path(sys.argv[1]).resolve()
BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
P4 = {c["name"]: c for c in json.loads((BASE / "knight-v030r/import-plan-KnightB.json").read_text())["clips"]}
plan3 = json.loads((BASE / "knight-v030q/import-plan-KnightB.json").read_text()); P3 = {c["name"]: c for c in plan3["clips"]}
plan2 = json.loads((BASE / "knight-v030p/import-plan-KnightB.json").read_text()); P2 = {c["name"]: c for c in plan2["clips"]}
V = "knight_571e0abbfde2720e"
DISPLAY = str(Path(plan2["mesh_variants"][V]["file"]).relative_to(ROOT))
IDLE = {"": "Local/CustomuseAssets/Polish20261025/knight/IdleOneHand_Blender_v2r4.glb", "TwoHand": "Local/CustomuseAssets/Polish20261025/knight/IdleTwoHand_Blender_v2r4.glb"}
HIDDEN = [.207, .391]
DUR = {}


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


def dur(p):
    if p not in DUR:
        DUR[p] = GLB(ROOT / p).duration()
    return DUR[p]


def cap(c):
    n = c["nominal_speed_cm_per_second"]
    return 100.0 if c["name"].startswith("Backpedal") else (min(580, n * 1.1) if "Run" in c["name"] else min(240, n * 1.2))


def rate(c):
    return cap(c) / c["nominal_speed_cm_per_second"] if c["loop"] else c["gameplay_play_rate"]


def inplace(label, c, views=None):
    p = rel(c["file"])
    j = {"label": label, "segments": [{"glb": p, "start": 0, "end": dur(p), "rate": rate(c), "loop": c["loop"], "even": True}],
         "blend": .1, "hold": 0, "display": DISPLAY}
    if views:
        j["views"] = views
    return j


def travel(label, c, cycles=2):
    p = rel(c["file"]); name = c["name"]; v = cap(c)
    vel = [0.0, -v] if name.startswith("Backpedal") else ([v, 0.0] if "Left" in name else [-v, 0.0])
    return {"label": label, "camera": "root", "display": DISPLAY, "blend": .1, "hold": 0,
            "segments": [{"glb": p, "start": 0, "end": dur(p) * cycles, "rate": rate(c), "loop": True, "even": True, "root": {"velocityGameCmS": vel}}]}


def blink(label, c):
    p = rel(c["file"]); idle = IDLE["TwoHand" if "TwoHand" in c["name"] else ""]
    return {"label": label, "camera": "fixed", "display": DISPLAY, "blend": .1, "hold": 0, "segments": [
        {"glb": idle, "start": 0, "end": .3, "rate": 1.0, "loop": True},
        {"glb": p, "start": 0, "end": dur(p), "rate": rate(c), "loop": False, "even": True, "hide": HIDDEN,
         "root": {"samplesCm": c["root_translation_samples_cm"], "rate": c["root_sample_rate"]}},
        {"glb": idle, "start": 0, "end": .4, "rate": 1.0, "loop": True}]}


def roll_travel(label, c):
    p = rel(c["file"])
    return {"label": label, "camera": "root", "display": DISPLAY, "blend": .1, "hold": 0, "segments": [
        {"glb": p, "start": 0, "end": dur(p), "rate": rate(c), "loop": False, "even": True,
         "root": {"samplesCm": c["root_translation_samples_cm"], "rate": c["root_sample_rate"]}},
        {"glb": IDLE[""], "start": 0, "end": .4, "rate": 1.0, "loop": True}]}


jobs, rows, sections = {}, [], []
NOTES = {
    "StrafeRun": "swing-plane fix: in the air each ankle target turns about the hip with the 45-degree pelvis, so the heel kick and "
                 "reach lie in the pelvis plane (knee pole = pelvis forward); stance path, speed and seam method unchanged",
    "Blink": "crouch bottom at rendered frame 3, two visible push frames (lean 19 deg, hips 11 cm toward travel), landing compresses "
             "after contact, last 0.20 s blend into the idle's own motion (no frozen frames)",
    "RollAttack": "world hips speed ramps down over 4 frames after the root-prefix end; hips settle to rest 3 frames before the end; "
                  "get-up/lunge contacts locked in world space; toes kept above the idle toe height",
}
for name, c in P4.items():
    key = next(k for k in NOTES if name.startswith(k))
    a = inplace("r4-" + name, c); jobs[a["label"]] = a
    rows.append({"slot": name, "status": "round 4 (not approved)", "changed": True, "after": a["label"], "afterSource": Path(c["file"]).name,
                 "afterRate": rate(c), "before": "r3-" + name, "beforeSource": Path(P3[name]["file"]).name, "beforeRate": rate(P3[name]), "note": NOTES[key]})
for name in ("StrafeRight", "StrafeRightTwoHand", "BackpedalGuard", "BackpedalGuardTwoHand"):
    rows.append({"slot": name, "status": "unchanged since round 3 (v030q file kept)", "changed": False, "after": "r3-" + name,
                 "afterSource": Path(P3[name]["file"]).name, "afterRate": rate(P3[name]), "before": None, "beforeSource": None, "beforeRate": None,
                 "note": "round-3 render re-encoded all-intra; on the lossless frames the loop wrap is an ordinary step (see plan-round4.md)"})
for name in ("StrafeLeft", "StrafeLeftTwoHand"):
    rows.append({"slot": name, "status": "unchanged (protected, byte-identical, inherited)", "changed": False, "after": "r3-" + name,
                 "afterSource": Path(P2[name]["file"]).name, "afterRate": rate(P2[name]), "before": None, "beforeSource": None, "beforeRate": None,
                 "note": "round-3 render re-encoded all-intra (reference for the seam method)"})
items = []
for name in ("StrafeRunLeft", "StrafeRunLeftTwoHand", "StrafeRunRight", "StrafeRunRightTwoHand", "BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand"):
    j = inplace("top-r4-" + name, P4[name], ["top"]); jobs[j["label"]] = j
    items.append({"label": j["label"], "caption": "r4 %s, top view (boss at the top, knight's right on the right), in place" % name})
    if name.startswith("StrafeRun"):
        j = inplace("top-r3-" + name, P3[name], ["top"]); jobs[j["label"]] = j
        items.append({"label": j["label"], "caption": "r3 %s, top view (BEFORE)" % name})
sections.append({"title": "Top views: pelvis and leg-plane yaw (round 4, sprint strafes with the round-3 BEFORE)", "items": items})
items = []
for name in ("StrafeLeft", "StrafeLeftTwoHand", "StrafeRight", "StrafeRightTwoHand", "StrafeRunLeft", "StrafeRunLeftTwoHand", "StrafeRunRight",
             "StrafeRunRightTwoHand", "BackpedalGuard", "BackpedalGuardTwoHand"):
    if name in P4:
        j = travel("rt-r4-" + name, P4[name]); jobs[j["label"]] = j; lab, c = j["label"], P4[name]
    else:
        lab, c = "rt-r3-" + name, P3.get(name) or P2[name]
    items.append({"label": lab, "caption": "%s (%s) at %.0f game cm/s (rate %.3f), camera follows the root: planted feet should stay fixed on the 25 cm grid"
                  % (name, "round 4" if name in P4 else "unchanged, round-3 render", cap(c), rate(c))})
sections.append({"title": "Root travel at in-game speed: strafes, sprint strafes, backpedals", "items": items})
items = []
for lab, P in (("r4", P4), ("r3", P3)):
    for name in ("BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand"):
        label = "rt-%s-%s" % (lab, name)
        if lab == "r4":
            j = blink(label, P[name]); jobs[label] = j
        items.append({"label": label, "caption": "%s %s: idle 0.3 s, blink at %.2fx, idle 0.4 s; knight hidden 0.18-0.34 s of action time; fixed camera"
                      % (lab, name, rate(P[name]))})
sections.append({"title": "Blinks with root travel, hidden window not drawn (round 4, then round 3)", "items": items})
items = []
for lab, P in (("r4", P4), ("r3", P3)):
    j = roll_travel("rt-%s-RollAttack" % lab, P["RollAttack"]); jobs[j["label"]] = j
    items.append({"label": j["label"], "caption": "%s RollAttack with its root track at %.3fx, then idle 0.4 s; camera follows the root, so during the roll "
                  "the floor scrolls and after the 1.0 s prefix the body's own motion is visible against a still floor" % (lab, rate(P["RollAttack"]))})
sections.append({"title": "Roll attack with root travel (world-space feet; round 4, then round 3)", "items": items})
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
(OUT / "extra.json").write_text(json.dumps({
    "title": "Veyr knight, fix round 4 (2026-10-29): round 4 vs round 3",
    "intro": "Round 4 renders: mesh variant V, loops sampled at evenly spaced phases, actions end on their last frame. Every video on this "
             "page (round 3 re-encoded from its lossless frames) is encoded all-intra, so the loop wrap is compared like any other step. "
             "Top views show the pelvis and leg plane from above. Nothing here is approved.",
    "baseIntro": "Headless Blender workbench renders of the exact GLBs the game imports (normalized clips), same rig, sword, lights and "
                 "cameras on both sides. Each in-place video is front | side | three-quarter at 30 fps real time, played at the in-game rate, "
                 "one fixed facing taken from the approved 1H idle (front = mesh forward). In-place rows: the camera follows the hips over a "
                 "checker of 25 game-cm tiles, loops show exactly one cycle. Changed rows compare round 4 (left) with round 3 (right).",
    "afterTag": "AFTER (round 4)", "beforeTag": "BEFORE (round 3)", "sections": sections}, indent=1) + "\n")
print(len(jobs), "jobs to render", len(rows), "rows", sum(len(s["items"]) for s in sections), "section items")
