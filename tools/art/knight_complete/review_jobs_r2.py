#!/usr/bin/env python3
"""Fix round 2 review jobs: BEFORE = round 1 clip, AFTER = round 2 clip, same fixed camera as round 1.
Rates are the in-game rates from the v030p plan. Usage: review_jobs_r2.py OUTDIR"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
OUT = Path(sys.argv[1])
R1 = "Local/CustomuseAssets/Knight20261029/knight/"
R2 = "Local/CustomuseAssets/Knight20261029r2/knight/"
plan = json.loads((ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030p/import-plan-KnightB.json").read_text())
P = {c["name"]: c for c in plan["clips"]}
r1plan = json.loads((ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030n/import-plan-KnightB.json").read_text())
P1 = {c["name"]: c for c in r1plan["clips"]}
DUR = {}
def dur(p):
    if p not in DUR: DUR[p] = GLB(ROOT / p).duration()
    return DUR[p]
def rate(c):
    if c["loop"]:
        n = c["nominal_speed_cm_per_second"]
        cap = 100.0 if c["name"].startswith("Backpedal") else (min(580, n * 1.1) if "Run" in c["name"] else min(240, n * 1.2))
        return cap / n
    return c["gameplay_play_rate"]
def clip(label, c, folder):
    p = folder + Path(c["file"]).name
    return {"label": label, "segments": [{"glb": p, "start": 0, "end": dur(p), "rate": rate(c), "loop": c["loop"]}], "blend": .1, "hold": 0}
jobs, rows = {}, []
def row(slot, key, key1, note):
    a = clip("r2-" + key, P[key], R2)
    b = clip("r1-" + key1, P1[key1], R1) if key1 in P1 else None
    for j in (a, b):
        if j: jobs[j["label"]] = j
    rows.append({"slot": slot, "status": "rebuilt round 2 (not approved)", "changed": True, "after": a["label"], "afterSource": Path(P[key]["file"]).name,
                 "afterRate": a["segments"][0]["rate"], "before": b["label"] if b else None, "beforeSource": Path(P1[key1]["file"]).name if b else None,
                 "beforeRate": b["segments"][0]["rate"] if b else None, "note": note})
for side in ("Left", "Right"):
    for grip, gl in (("", "one hand"), ("TwoHand", "two hand")):
        row("Lock-on strafe %s (%s)" % (side.lower(), gl), "Strafe%s%s" % (side, grip), "Strafe%s%s" % (side, grip), "forward-gait source (right) or its mirror (left), spine counter-twist: chest faces the boss")
        row("Lock-on sprint strafe %s (%s)" % (side.lower(), gl), "StrafeRun%s%s" % (side, grip), "StrafeRun%s%s" % (side, grip), "forward run strafe (4) or its mirror, chest counter-twisted; ends at idle stance width")
        row("Blink %s (%s)" % (side.lower(), gl), "Blink%s%s" % (side, grip), "Blink%s" % side, "forward run body, chest to the boss; root carries 90% of foot speed while visible" + ("; new 2H clip (before = 1H)" if grip else ""))
for d in ("Front", "Back", "Left", "Right"):
    for grip, gl in (("", "one hand"), ("TwoHand", "two hand")):
        row("Stagger %s (%s)" % (d.lower(), gl), "Stagger%s%s" % (d, grip), "Stagger%s%s" % (d, grip), "blade pitch <= 25 deg (1H) / idle+10 (2H), tip <= 40 cm/frame; first and last frame = idle" + ("; straight-back (mirror-averaged)" if d == "Front" else ""))
row("Lock-on backpedal (one hand)", "BackpedalGuard", "BackpedalGuard", "guard held through the loop: blade +40 deg above the idle carry")
row("Lock-on backpedal (two hand)", "BackpedalGuardTwoHand", "BackpedalGuardTwoHand", "blade angled 22 deg forward of the 2H idle")
row("Roll attack", "RollAttack", "RollAttack", "0.60 s join; sword locked to the hand; two lifted recovery steps")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
print(len(jobs), "jobs", len(rows), "rows")
