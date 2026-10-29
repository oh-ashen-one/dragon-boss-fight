#!/usr/bin/env python3
"""KnightB v030r (fix round 4): sprint strafes with the swing-plane fix (legs in the pelvis plane, 1H/2H, retimed to the
capsule speed), blinks with two push frames and an animated-idle tail (1H/2H), roll attack with a ramped join, settled
hips and locked contacts. Every other clip is inherited BY REFERENCE from the v030q runtime definition, including the
protected StrafeLeft(2H) and eight staggers (from v030p through v030q) and the round-3 StrafeRight(2H) and backpedals
(their round-3 files are kept: the round-3 seam excess was an MP4 encoder artifact, see plan-round4.md).

Usage: prepare_round4_plan.py            write the plan (refuses to overwrite) and its manifest; does not activate
       prepare_round4_plan.py --check    inputs only (which round-4 GLBs exist), no writes
       prepare_round4_plan.py --activate point active-plans.json at the written plan after re-checking its hash
"""
import copy, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(ROOT / "tools/art/knight_complete"))
ART = ROOT / "Local/FabRigTesting/Exports"; BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
OUT = ROOT / "Local/CustomuseAssets/Knight20261029r4"; PLAN = BASE / "knight-v030r/import-plan-KnightB.json"
PREV = BASE / "knight-v030q/import-plan-KnightB.json"
DOC = ROOT / "docs/knight-complete-20261028/data/import-plan-KnightB-v030r.json"
HIDDEN = (.207, .391)
BLINK_TOTAL = 122.3          # mesh-local cm (298.6 game cm), unchanged since v030p
PROTECTED = ["StrafeLeft", "StrafeLeftTwoHand"] + ["Stagger%s%s" % (d, g) for d in ("Front", "Back", "Left", "Right") for g in ("", "TwoHand")]
KEPT_R3 = ["StrafeRight", "StrafeRightTwoHand", "BackpedalGuard", "BackpedalGuardTwoHand"]
JOBS = []   # key, file, loop, rate, nominal ("prev" = v030q nominal), root ("none" | "prefix:<s>" | "blink:<sign>")
for side in ("Left", "Right"):
    for grip in ("", "TwoHand"):
        JOBS.append(("StrafeRun%s%s" % (side, grip), "Knight_StrafeRun%s%s_v6r" % (side, grip), True, 1.0, "prev", "none"))
        JOBS.append(("Blink%s%s" % (side, grip), "Knight_Blink%s%s_v6c" % (side, grip), False, 1.15, 0.0, "blink:%s" % ("+1" if side == "Left" else "-1")))
JOBS.append(("RollAttack", "Sourced_RollAttack_v6", False, "prev", 0.0, "prefix:1.0"))
assert not set(k for k, *_ in JOBS) & set(PROTECTED + KEPT_R3)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def activate():
    if not PLAN.exists():
        raise SystemExit("plan missing: " + str(PLAN))
    rec = json.loads((OUT / "knight-manifest.json").read_text())
    if rec["planSHA256"] != sha(PLAN):
        raise SystemExit("plan hash differs from the manifest; refusing to activate")
    active = BASE / "active-plans.json"; prior = json.loads(active.read_text())
    prior["KnightB"] = {"path": str(PLAN), "sha256": sha(PLAN)}
    active.write_text(json.dumps(prior, indent=2) + "\n"); print("PLAN_ACTIVE", PLAN)


if "--activate" in sys.argv:
    activate(); sys.exit(0)
if "--check" in sys.argv:
    miss = [n for _, n, *_ in JOBS if not (ART / (n + ".glb")).exists()]
    print("PLAN exists" if PLAN.exists() else "PLAN free", PLAN)
    print("PREV", "ok" if PREV.exists() else "MISSING", PREV)
    for _, n, *_ in JOBS:
        print("INPUT", n, "ok" if (ART / (n + ".glb")).exists() else "missing (authoring not run yet)")
    sys.exit(0 if PREV.exists() else 1)

from normalize_sourced import normalize_file, GLB  # noqa: E402
from measure_locomotion import measure as stance_measure  # noqa: E402
old = json.loads(PREV.read_text())
P3 = {c["name"]: c for c in old["clips"]}
if PLAN.exists():
    raise FileExistsError(PLAN)
canonical = GLB(old["rig"]["file"])
plan = copy.deepcopy(old)
plan.update(version="v030r", replace_runtime_source="/Game/Characters/Customuse/KnightB/v030q/DA_KnightB",
            purpose="Knight fix round 4 (2026-10-29): sprint strafes with the legs in the pelvis plane (heel kick and reach turned with the "
                    "45-degree pelvis), blinks with two push frames and an animated-idle tail, roll attack with a ramped join, settled hips and "
                    "locked contacts; other clips inherited from v030q.")
plan["clips"] = []; plan["mesh_variants"] = {}; rows = []
(OUT / "knight").mkdir(parents=True, exist_ok=True)
for key, name, loop, rate, nominal, root in JOBS:
    f = ART / (name + ".glb"); meta = json.loads(f.with_suffix(".json").read_text())
    rate = P3[key]["gameplay_play_rate"] if rate == "prev" else rate
    prefix = float(root.split(":")[1]) if root.startswith("prefix") else None
    row = normalize_file(f, canonical, OUT / "knight" / f.name, meta["fps"], prefix)
    samples, removed, srate = row["rootTranslationSamplesCm"], row["bRootMotionRemoved"], row["rootSampleRate"]
    if nominal == "prev":
        nominal = P3[key]["nominal_speed_cm_per_second"]
        stance = round(stance_measure(row["file"])["rawStanceSpeedMedian"] * 240.0, 2)
        print("STANCE_VS_NOMINAL", key, stance, nominal, "residual %+.2f%%" % (100 * (stance / nominal - 1)), flush=True)
    if root.startswith("blink"):
        sign = float(root.split(":")[1]); T = row["duration"]; n = len(samples); srate = (n - 1) / T; samples = []
        for i in range(n):
            t = i / srate; u = max(0.0, min(1.0, (t - HIDDEN[0]) / (HIDDEN[1] - HIDDEN[0]))); u = u * u * (3 - 2 * u)
            samples.append([sign * BLINK_TOTAL * u, 0.0, 0.0])
        removed = True
    if key == "RollAttack":
        prev_end = P3[key]["root_translation_samples_cm"][-1]
        print("ROLL_ROOT_END v030r", samples[-1], "v030q", prev_end, "(the prefix is unchanged by design; should match)", flush=True)
    rows.append({**row, "key": key, "source": name})
    plan["mesh_variants"].setdefault(row["mesh_variant"], {"file": row["file"], "sha256": row["sha256"]})
    windows = P3[key]["damage_windows"] if key == "RollAttack" else []
    plan["clips"].append({"name": key, "file": row["file"], "sha256": row["sha256"], "mesh_variant": row["mesh_variant"], "start_seconds": 0,
        "end_seconds": -1, "loop": loop, "gameplay_play_rate": rate, "nominal_speed_cm_per_second": nominal, "damage_windows": windows,
        "impact_seconds": sum(windows[0]) / 2 if windows else -1, "weapon_file": "BoatGreatsword_OneHand_v4.glb", "root_motion_policy": "preserve",
        "root_motion_removed": removed, "root_sample_rate": srate, "root_translation_samples_cm": samples, "root_yaw_samples_degrees": [],
        "source_duration": row["duration"], "approved_source_file": f.name, "approved_source_sha256": row["sourceSHA256"]})
    print("NORMALIZED", key, row["mesh_variant"], "rate", rate, "nominal", nominal, "err", row["canonicalReconstructionMaxMatrixError"], flush=True)
V = "knight_571e0abbfde2720e"
import numpy as np  # noqa: E402


def corners(path):
    g = GLB(path); _, node = g.body(); pr = g.g["meshes"][node["mesh"]]["primitives"]; assert len(pr) == 1
    i = g.accessor(pr[0]["indices"]).ravel(); a = pr[0]["attributes"]
    return {k: g.accessor(a[k])[i].astype(float) for k in ("POSITION", "TEXCOORD_0")}, [g.g["nodes"][j]["name"] for j in g.g["skins"][0]["joints"]]
REF, REFJ = corners(old["mesh_variants"][V]["file"])
geometry = {}
for vname, vrec in plan["mesh_variants"].items():
    G, J = corners(vrec["file"])
    err = {k: float(np.abs(G[k] - REF[k]).max()) for k in G}
    assert J == REFJ and all(e < 1e-5 for e in err.values()), (vname, err)
    geometry[vname] = {"file": Path(vrec["file"]).name, "cornerMaxAbsDiff": err, "jointsIdentical": True}
print("GEOMETRY_MATCHES_V", json.dumps(geometry), flush=True)
plan["mesh_variants"] = {V: old["mesh_variants"][V]}
for c in plan["clips"]:
    c["mesh_variant"] = V
assert plan["existing_mesh_variants"] == old["existing_mesh_variants"]
plan["integration_notes"] = dict(plan.get("integration_notes", {}), knightFixRound4={
    "note": "see tools/art/knight_complete/build_round4.py and docs/knight-complete-20261028/plan-round4.md",
    "inheritedByReference": PROTECTED + KEPT_R3 + ["(every other clip)"],
    "nominalSpeeds": "every loop keeps its v030q nominal (= v030p; owner rule: never slow the character to fix sliding); the v6c sprint cycles are retimed to match",
    "bodyGeometryCheckAgainstV": geometry, "rollAttackDamageWindows": "unchanged from v030q"})
PLAN.parent.mkdir(parents=True, exist_ok=True); PLAN.write_text(json.dumps(plan, indent=2) + "\n")
sys.path.insert(0, str(ROOT / "tools/unreal")); import import_customuse  # noqa: E402
canon = import_customuse.inspect_glb(plan["rig"])
for c in plan["clips"]:
    v = plan["mesh_variants"].get(c["mesh_variant"])
    import_customuse.compatible(import_customuse.inspect_glb(v) if v else canon, import_customuse.inspect_glb(c))
DOC.write_text(PLAN.read_text())
(OUT / "knight-manifest.json").write_text(json.dumps({"version": "v030r", "plan": str(PLAN), "planSHA256": sha(PLAN), "clips": rows}, indent=2) + "\n")
print("PLAN_WRITTEN (not activated; run with --activate before any import commandlet)", PLAN, sha(PLAN))
