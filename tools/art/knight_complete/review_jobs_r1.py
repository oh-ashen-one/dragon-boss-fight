#!/usr/bin/env python3
"""Fix round 1 review jobs: exactly one cycle for loops, no frozen tail, fixed canonical camera.
Changed rows: BEFORE = round 0 clip, AFTER = round 1 clip. Unchanged rows keep slot before/after.
Usage: review_jobs_r1.py OUTDIR"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration"))
from normalize_approved import GLB  # noqa: E402
OUT = Path(sys.argv[1])
K = "Local/CustomuseAssets/Polish20261025/idle-joins/knight/"
KP = "Local/CustomuseAssets/Polish20261025/knight/"
S = "Local/CustomuseAssets/Sourced20261025b/knight/"
B = "Local/CustomuseAssets/Polish20261025/overhaul-v028/knight/"
R0 = "Local/CustomuseAssets/Knight20261028/knight/"
R1 = "Local/CustomuseAssets/Knight20261029/knight/"
DUR = {}
def dur(p):
    if p not in DUR: DUR[p] = GLB(ROOT / p).duration()
    return DUR[p]
def clip(label, path, rate, loop=False):
    d = dur(path)
    return {"label": label, "segments": [{"glb": path, "start": 0, "end": d, "rate": rate, "loop": loop}], "blend": .1, "hold": 0}
jobs, rows = {}, []
def row(slot, status, after, before, note, changed):
    for j in (after, before):
        if j: jobs[j["label"]] = j
    rows.append({"slot": slot, "status": status, "changed": changed, "after": after["label"], "afterSource": after["segments"][-1]["glb"].split("/")[-1],
                 "afterRate": after["segments"][-1]["rate"], "before": before["label"] if before else None,
                 "beforeSource": before["segments"][-1]["glb"].split("/")[-1] if before else None,
                 "beforeRate": before["segments"][-1]["rate"] if before else None, "note": note})
walk = clip("walk-mixamo-v17", S + "Mixamo_Walk_v17.glb", 1.2, True)
walk2 = clip("walk2h-mixamo-v17", S + "Mixamo_WalkTwoHand_v17.glb", 1.2, True)
run = clip("run-fab-v18", S + "Fab_RunOneHand_v18.glb", .725, True)
run2 = clip("run2h-fab-v17", S + "Fab_Run_v17.glb", .725, True)
# Changed this round
row("Roll attack", "rebuilt round 1 (not approved)", clip("r1-rollattack-v3", R1 + "Sourced_RollAttack_v3.glb", 1 / .78),
    clip("r0-rollattack-v2", S + "Sourced_RollAttack_v2.glb", 1 / .78), "0.40 s velocity-matched join (was a 3-frame splice); ends in the 1H idle carry", True)
row("Blink left", "rebuilt round 1 (not approved)", clip("r1-blinkleft-v3", R1 + "Knight_BlinkLeft_v3.glb", 1.15),
    clip("r0-blinkleft-transitR", B + "Sourced_BlinkRight_Transit_v2.glb", 1.15), "Mixamo strafe (3) body, idle carry; correctly named file; v029 root trajectory", True)
row("Blink right", "rebuilt round 1 (not approved)", clip("r1-blinkright-v3", R1 + "Knight_BlinkRight_v3.glb", 1.15),
    clip("r0-blinkright-transitL", B + "Sourced_BlinkLeft_Transit_v2.glb", 1.15), "true sagittal mirror of blink left; root trajectory mirrored", True)
row("Lock-on backpedal (one hand)", "new round 1 (derived from the approved loop)", clip("r1-backpedal-guard", R1 + "Knight_BackpedalGuard_v3c.glb", 100 / 59.95, True),
    clip("r0-backpedal-loop", K + "Backpedal_Blender_loop_v1r3.glb", 100 / 59.95, True), "approved loop legs; +7.0 cm head lean (~10 px); blade raised 27 deg on the leaned chest (+6 cm)", True)
row("Lock-on backpedal (two hand)", "new round 1", clip("r1-backpedal-guard-2h", R1 + "Knight_BackpedalGuardTwoHand_v3c.glb", 100 / 59.95, True),
    clip("r0-backpedal-loop", K + "Backpedal_Blender_loop_v1r3.glb", 100 / 59.95, True), "round 0 fell back to the 1H loop (grip snap)", True)
for side, nom in (("Left", 138.41), ("Right", 155.51)):
    for grip, gl, r0suf in (("", "one hand", ""), ("TwoHand", "two hand", "TwoHand")):
        rate = min(240, nom * 1.2) / nom
        row("Lock-on strafe %s (%s)" % (side.lower(), gl), "rebuilt round 1", clip("r1-strafe-%s%s" % (side.lower(), "-2h" if grip else ""), R1 + "Knight_Strafe%s%s_v3c.glb" % (side, grip), rate, True),
            clip("r0-strafe-%s%s" % (side.lower(), "-2h" if grip else ""), R0 + "Mixamo_Strafe%s%s_v2.glb" % (side, r0suf), rate, True), "idle carry (20% chest follow); cycle starts at narrowest stance", True)
        r1rate = min(580, 440.2 * 1.1) / 440.2
        r0rate = min(580, (411.3 if side == "Left" else 403.99) * 1.1) / (411.3 if side == "Left" else 403.99)
        row("Lock-on sprint strafe %s (%s)" % (side.lower(), gl), "rebuilt round 1", clip("r1-strafe-run-%s%s" % (side.lower(), "-2h" if grip else ""), R1 + "Knight_StrafeRun%s%s_v3c.glb" % (side, grip), r1rate, True),
            clip("r0-strafe-run-%s%s" % (side.lower(), "-2h" if grip else ""), R0 + "Mixamo_StrafeRun%s%s_v2.glb" % (side, r0suf), r0rate, True),
            ("true mirror of sprint strafe left; " if side == "Right" else "") + "nominal 440 cm/s (source travel)", True)
for d in ("Front", "Back", "Left", "Right"):
    for grip, gl in (("", "one hand"), ("TwoHand", "two hand")):
        r1 = R1 + "Knight_Stagger%s%s_v3.glb" % (d, grip)
        row("Stagger %s (%s)" % (d.lower(), gl), "rebuilt round 1", clip("r1-stagger-%s%s" % (d.lower(), "-2h" if grip else ""), r1, dur(r1) / .6),
            clip("r0-stagger-%s%s" % (d.lower(), "-2h" if grip else ""), R0 + "Mixamo_Impact%s%s_v2.glb" % (d, grip), dur(R0 + "Mixamo_Impact%s%s_v2.glb" % (d, grip)) / .6),
            "additive on the approved idle: starts and ends in the idle pose, feet planted%s" % (", lateral x2" if d in ("Left", "Right") else ""), True)
# Unchanged rows (current clip vs the clip it replaced)
row("Walk (one hand)", "owner-selected, unchanged", walk, clip("walk-blender-v2r2", K + "WalkOneHand_Blender_v2r2.glb", 240 / 157.81, True), "", False)
row("Walk (two hand)", "owner-selected, unchanged", walk2, clip("walk2h-blender-v6r2", K + "WalkTwoHand_Blender_v6r2.glb", 240 / 94.55, True), "", False)
row("Run (one hand)", "owner-selected, unchanged", run, clip("run-blender-tripo-r2", K + "RunOneHand_Blender_tripo_r2.glb", 580 / 460.41, True), "", False)
row("Run (two hand)", "owner-selected, unchanged", run2, clip("run2h-blender-polish-v2", KP + "RunTwoHand_Blender_polish_v2.glb", 580 / 460.41, True), "", False)
row("Light attack (one hand)", "owner-selected, unchanged", clip("light-mixamo-v17", S + "Mixamo_Attack_v17.glb", 1.6), clip("light-blackknight-v2r3", KP + "LightAttack_BlackKnightReference_Blender_v2r3.glb", 3.0), "", False)
row("Roll", "owner-selected, unchanged", clip("roll-fab-v17", S + "Fab_Roll_v17.glb", 1 / .78), clip("roll-blender-polish-v2", K + "Roll_Blender_polish_v2.glb", 1.0), "", False)
row("Grip to two hand", "unchanged (ends exactly on the 2H idle)", clip("grip-to-two-polish-v2", K + "GripToTwoHand_Blender_polish_v2.glb", 1.0), None, "", False)
row("Grip to one hand", "unchanged (ends exactly on the 1H idle)", clip("grip-to-one-polish-v2", K + "GripToOneHand_Blender_polish_v2.glb", 1.0), None, "", False)
rs, runf = K + "RunStop_Blender_v1r2.glb", S + "Fab_RunOneHand_v18.glb"
def join(label, blend):
    return {"label": label, "segments": [{"glb": runf, "start": 0, "end": .84, "rate": .725, "loop": True}, {"glb": rs, "start": 0, "end": dur(rs), "rate": 1.0}], "blend": blend, "hold": 0}
row("Run to RunStop join", "unchanged (0.30 s blend)", join("runstop-join-blend030", .30), join("runstop-join-blend010", .10), "", False)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jobs.json").write_text(json.dumps(list(jobs.values()), indent=1) + "\n")
(OUT / "rows.json").write_text(json.dumps(rows, indent=1) + "\n")
print(len(jobs), "jobs", len(rows), "rows")
