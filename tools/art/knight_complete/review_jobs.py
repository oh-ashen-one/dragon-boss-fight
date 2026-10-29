#!/usr/bin/env python3
"""Write the knight review job list and the page manifest (rows: slot, after, before).
Rates are in-game playback rates: locomotion = movement speed / measured nominal speed,
actions = GameplayPlayRate from the active plans. Usage: review_jobs.py OUTDIR"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402

OUT = Path(sys.argv[1])
K = "Local/CustomuseAssets/Polish20261025/idle-joins/knight/"
KP = "Local/CustomuseAssets/Polish20261025/knight/"
S = "Local/CustomuseAssets/Sourced20261025b/knight/"
B = "Local/CustomuseAssets/Polish20261025/overhaul-v028/knight/"
N = "Local/CustomuseAssets/Knight20261028/knight/"
plan = json.loads((ROOT / "Local/CustomuseAssets/Polish20261025/knight-v030k/import-plan-KnightB.json").read_text())
newspec = {c["name"]: c for c in plan["clips"]}
DUR = {}


def dur(path):
    if path not in DUR:
        DUR[path] = GLB(ROOT / path).duration()
    return DUR[path]


def clip(label, path, rate, loop=False, cycles=2, hold=0.25):
    d = dur(path)
    if loop:
        return {"label": label, "segments": [{"glb": path, "start": 0, "end": d * cycles, "rate": rate, "loop": True}], "blend": .1, "hold": 0}
    return {"label": label, "segments": [{"glb": path, "start": 0, "end": d, "rate": rate}], "blend": .1, "hold": hold}


jobs, rows = {}, []


def row(slot, status, after, before, note):
    for j in (after, before):
        if j:
            jobs[j["label"]] = j
    rows.append({"slot": slot, "status": status, "after": after["label"], "afterSource": after["segments"][-1]["glb"].split("/")[-1],
                 "afterRate": after["segments"][-1]["rate"], "before": before["label"] if before else None,
                 "beforeSource": before["segments"][-1]["glb"].split("/")[-1] if before else None,
                 "beforeRate": before["segments"][-1]["rate"] if before else None, "note": note})


walk = clip("walk-mixamo-v17", S + "Mixamo_Walk_v17.glb", 240 / 200, True)
walk2 = clip("walk2h-mixamo-v17", S + "Mixamo_WalkTwoHand_v17.glb", 240 / 200, True)
run = clip("run-fab-v18", S + "Fab_RunOneHand_v18.glb", 580 / 800, True)
run2 = clip("run2h-fab-v17", S + "Fab_Run_v17.glb", 580 / 800, True)
row("Walk (one hand)", "owner-selected, not recorded as accepted", walk, clip("walk-blender-v2r2", K + "WalkOneHand_Blender_v2r2.glb", 240 / 157.81, True), "240 cm/s")
row("Walk (two hand)", "owner-selected, not recorded as accepted", walk2, clip("walk2h-blender-v6r2", K + "WalkTwoHand_Blender_v6r2.glb", 240 / 94.55, True), "240 cm/s")
row("Run (one hand)", "owner-selected, not recorded as accepted", run, clip("run-blender-tripo-r2", K + "RunOneHand_Blender_tripo_r2.glb", 580 / 460.41, True), "580 cm/s")
row("Run (two hand)", "owner-selected, not recorded as accepted", run2, clip("run2h-blender-polish-v2", KP + "RunTwoHand_Blender_polish_v2.glb", 580 / 460.41, True), "580 cm/s")
row("Light attack (one hand)", "owner-selected, not recorded as accepted", clip("light-mixamo-v17", S + "Mixamo_Attack_v17.glb", 1.6),
    clip("light-blackknight-v2r3", KP + "LightAttack_BlackKnightReference_Blender_v2r3.glb", 3.0), "gameplay rate 1.6 (before 3.0)")
row("Roll", "owner-selected, not recorded as accepted", clip("roll-fab-v17", S + "Fab_Roll_v17.glb", 1 / .78), clip("roll-blender-polish-v2", K + "Roll_Blender_polish_v2.glb", 1.0), "0.78 s in game")
row("Roll attack", "derived, not recorded as accepted", clip("rollattack-sourced-v2", S + "Sourced_RollAttack_v2.glb", 1 / .78),
    clip("rollattack-blender-polish-v2", K + "RollAttack_Blender_polish_v2.glb", 1.0), "roll prefix plus slash")
row("Blink left", "unapproved", clip("blinkleft-transit-v2", B + "Sourced_BlinkRight_Transit_v2.glb", 1.15), clip("blinkleft-blender-v4r2", KP + "StrafeLeft_Blender_v4r2.glb", 1.0),
    "v029 maps BlinkLeft to the file named Sourced_BlinkRight_Transit_v2 (native axis); camera follows the hips, travel not shown")
row("Blink right", "unapproved", clip("blinkright-transit-v2", B + "Sourced_BlinkLeft_Transit_v2.glb", 1.15), clip("blinkright-blender-v4r2", KP + "StrafeRight_Blender_v4r2.glb", 1.0),
    "v029 maps BlinkRight to Sourced_BlinkLeft_Transit_v2")
row("Grip to two hand", "unapproved", clip("grip-to-two-polish-v2", K + "GripToTwoHand_Blender_polish_v2.glb", 1.0), None, "no earlier clip available")
row("Grip to one hand", "unapproved", clip("grip-to-one-polish-v2", K + "GripToOneHand_Blender_polish_v2.glb", 1.0), None, "no earlier clip available")
row("Lock-on backpedal", "clip approved; wiring new", clip("backpedal-loop-v1r3", K + "Backpedal_Blender_loop_v1r3.glb", 100 / 59.95, True),
    walk, "before: the forward walk played (knight turned away); after: 100 cm/s, 1.67x")
for side in ("Left", "Right"):
    for grip, gl in (("", "one hand"), ("TwoHand", "two hand")):
        key = "Strafe" + side + grip
        spec = newspec[key]
        rate = min(240.0, spec["nominal_speed_cm_per_second"] * 1.2) / spec["nominal_speed_cm_per_second"]
        row("Lock-on strafe %s (%s)" % (side.lower(), gl), "new", clip("strafe-%s%s" % (side.lower(), "-2h" if grip else ""), N + Path(spec["file"]).name, rate, True),
            walk2 if grip else walk, "nominal %.0f cm/s; before: forward walk" % spec["nominal_speed_cm_per_second"])
        key = "StrafeRun" + side + grip
        spec = newspec[key]
        rate = min(580.0, spec["nominal_speed_cm_per_second"] * 1.1) / spec["nominal_speed_cm_per_second"]
        row("Lock-on sprint strafe %s (%s)" % (side.lower(), gl), "new", clip("strafe-run-%s%s" % (side.lower(), "-2h" if grip else ""), N + Path(spec["file"]).name, rate, True),
            run2 if grip else run, "nominal %.0f cm/s; before: forward run" % spec["nominal_speed_cm_per_second"])
stagger_before = clip("stagger-blender-v2r5", K + "Stagger_Blender_v2r5.glb", 1.0)
for d in ("Front", "Back", "Left", "Right"):
    for grip, gl in (("", "one hand"), ("TwoHand", "two hand")):
        spec = newspec["Stagger" + d + grip]
        row("Stagger %s (%s)" % (d.lower(), gl), "new", clip("stagger-%s%s" % (d.lower(), "-2h" if grip else ""), N + Path(spec["file"]).name, spec["gameplay_play_rate"]),
            stagger_before, "hit from the %s; %.2f s in game (default Stagger 0.42 s)%s" % (d.lower(), dur(N + Path(spec["file"]).name) / spec["gameplay_play_rate"],
                                                                                            "; mirrored copy of the left impact" if d == "Right" else ""))
rs = K + "RunStop_Blender_v1r2.glb"
runf = S + "Fab_RunOneHand_v18.glb"


def join(label, blend):
    return {"label": label, "segments": [{"glb": runf, "start": 0, "end": .84, "rate": 580 / 800, "loop": True},
                                         {"glb": rs, "start": 0, "end": dur(rs), "rate": 1.0}], "blend": blend, "hold": .3}


row("Run to RunStop join", "measured; blend changed", join("runstop-join-blend030", .30), join("runstop-join-blend010", .10),
    "Fab run at 0.725x released after 1.16 s (cycle phase %.2f of %.2f s); before 0.10 s blend, after 0.30 s" % (.84 % dur(runf), dur(runf)))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
print(len(jobs), "jobs", len(rows), "rows")
