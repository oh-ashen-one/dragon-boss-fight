#!/usr/bin/env python3
"""Fix round 3 review jobs. AFTER = round-3 clip (v030q plan), BEFORE = round-2 clip (v030p plan, the MP4 the critic
judged, reused from serve/media). Rates are the in-game rates. Round-3 renders sample loops at evenly spaced phases
(the wrap step equals every other step) and draw mesh variant V (the body the engine draws for every clip).

Also writes root-travel jobs at in-game speed: every lock-on strafe (incl. the protected StrafeLeft(2H)), sprint strafe
and backpedal moves at its capsule speed for two cycles with the camera following the root (the floor grid scrolls
under planted feet); every blink plays idle -> blink -> idle with the plan's root track (about 300 game cm, all inside
the hidden window) and the knight not drawn in the game's hidden window, fixed camera. Round-2 blinks get the same.

Usage: review_jobs_r3.py REVIEW_DIR (writes jobs.json, rows.json, extra.json; copies the round-2 MP4s into
       REVIEW_DIR/../serve-round3/media so they are not re-rendered)"""
import json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
OUT = Path(sys.argv[1]).resolve()
SERVE = OUT.parent / "serve-round3"; MEDIA = SERVE / "media"; OLD = OUT.parent / "serve/media"
BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
P3 = {c["name"]: c for c in json.loads((BASE / "knight-v030q/import-plan-KnightB.json").read_text())["clips"]}
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


def inplace(label, c):
    p = rel(c["file"])
    return {"label": label, "segments": [{"glb": p, "start": 0, "end": dur(p), "rate": rate(c), "loop": c["loop"], "even": True}],
            "blend": .1, "hold": 0, "display": DISPLAY}


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


jobs, rows, sections = {}, [], []
NOTES = {
    "StrafeRight": "seam re-keyed: loop closed and cycle start moved to a slow phase (pose seam/mean <= 0.92 in all bands); left clip unchanged (owner: byte-identical)",
    "StrafeRun": "Mixamo strafe run (4) turned so the pelvis is 45 deg off the boss, chest within 18 deg of the boss, twist <= 38 deg; knees on the sourced pole; 1H free arm swings",
    "Blink": "idle -> launch crouch (Mixamo crouch frames, 3 game frames down) -> push -> hidden 0.18-0.34 s (root travels) -> landing crouch -> exact idle; 0.70 s clip",
    "BackpedalGuard": "guard raised to chest height, blade out to the right of the helmet (front view); loop seam re-keyed",
    "RollAttack": "roll and 0.60 s join unchanged; after the slash the arm returns straight to the carry (no second wind-up); two lifted recovery steps, other foot locked",
}
for name, c in P3.items():
    key = next(k for k in NOTES if name.startswith(k))
    a = inplace("r3-" + name, c); jobs[a["label"]] = a
    before = "r2-" + name
    if (OLD / (before + ".mp4")).exists():
        MEDIA.mkdir(parents=True, exist_ok=True)
        if not (MEDIA / (before + ".mp4")).exists():
            shutil.copy2(OLD / (before + ".mp4"), MEDIA / (before + ".mp4"))
    rows.append({"slot": name, "status": "round 3 (not approved)", "changed": True, "after": a["label"], "afterSource": Path(c["file"]).name,
                 "afterRate": rate(c), "before": before, "beforeSource": Path(P2[name]["file"]).name, "beforeRate": rate(P2[name]), "note": NOTES[key]})
for grip in ("", "TwoHand"):
    j = {"label": "r3-Idle" + grip, "segments": [{"glb": IDLE[grip], "start": 0, "end": dur(IDLE[grip]), "rate": 1.0, "loop": True, "even": True}],
         "blend": .1, "hold": 0, "display": DISPLAY}
    jobs[j["label"]] = j
for name in ("StrafeLeft", "StrafeLeftTwoHand"):  # protected: inherited by reference, never re-exported
    a = inplace("r3-" + name, P2[name]); jobs[a["label"]] = a
    rows.append({"slot": name, "status": "unchanged (protected, byte-identical, inherited from v030p)", "changed": False, "after": a["label"],
                 "afterSource": Path(P2[name]["file"]).name, "afterRate": rate(P2[name]), "before": None, "beforeSource": None, "beforeRate": None,
                 "note": "same file as round 2, rendered with even phase sampling and mesh V"})
items = []
order = ["StrafeLeft", "StrafeLeftTwoHand", "StrafeRight", "StrafeRightTwoHand", "StrafeRunLeft", "StrafeRunLeftTwoHand", "StrafeRunRight",
         "StrafeRunRightTwoHand", "BackpedalGuard", "BackpedalGuardTwoHand"]
for name in order:
    c = P3.get(name) or P2[name]; j = travel("rt-r3-" + name, c); jobs[j["label"]] = j
    items.append({"label": j["label"], "caption": "%s%s at %.0f game cm/s (rate %.3f), camera follows the root: planted feet should stay fixed on the 25 cm grid"
                  % (name, " (protected, unchanged)" if name not in P3 else "", cap(c), rate(c))})
sections.append({"title": "Root travel at in-game speed: strafes, sprint strafes, backpedals (round 3)", "items": items})
items = []
for lab, P in (("r3", P3), ("r2", P2)):
    for name in ("BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand"):
        j = blink("rt-%s-%s" % (lab, name), P[name]); jobs[j["label"]] = j
        tot = P[name]["root_translation_samples_cm"][-1][0]
        items.append({"label": j["label"], "caption": "%s %s: idle 0.3 s, blink at %.2fx, idle 0.4 s; root %.1f mesh cm (~%.0f game cm); knight hidden 0.18-0.34 s of action time; fixed camera"
                      % (lab, name, rate(P[name]), tot, abs(tot) * 2.44)})
sections.append({"title": "Blinks with root travel, hidden window not drawn (round 3, then round 2)", "items": items})
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
(OUT / "extra.json").write_text(json.dumps({
    "title": "Veyr knight, fix round 3 (2026-10-29): round 3 vs round 2",
    "intro": "Round 3 renders: mesh variant V (the body the engine draws), loops sampled at evenly spaced phases so the loop "
             "wrap is an ordinary step, actions end on their last frame. Round 2 videos are the exact MP4s the round-2 critic judged. "
             "Root-travel sections move the knight at in-game speed. Nothing here is approved.",
    "baseIntro": "Headless Blender workbench renders of the exact GLBs the game imports (normalized clips), same rig, sword, lights and "
                 "cameras on both sides. Each video is front | side | three-quarter at 30 fps real time, played at the in-game rate, "
                 "one fixed facing taken from the approved 1H idle (front = mesh forward). In-place rows: the camera follows the hips "
                 "over a checker of 25 game-cm tiles, loops show exactly one cycle. Changed rows compare round 3 (left) with round 2 (right).",
    "afterTag": "AFTER (round 3)", "beforeTag": "BEFORE (round 2)", "sections": sections}, indent=1) + "\n")
print(len(jobs), "jobs", len(rows), "rows", sum(len(s["items"]) for s in sections), "travel items")
