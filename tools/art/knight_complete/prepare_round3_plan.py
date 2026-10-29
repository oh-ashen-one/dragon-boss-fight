#!/usr/bin/env python3
"""KnightB v030q (fix round 3): real blinks (1H+2H), sprint strafes with a 45-degree pelvis and a swinging free arm,
seam-fixed StrafeRight(2H) and backpedals, raised 1H/2H backpedal guard, roll-attack exit (straight blade recovery,
lifted steps). Every other clip, including StrafeLeft(2H) and the eight staggers, is inherited BY REFERENCE from the
v030p runtime definition (their GLBs and .uassets are not re-imported). Rig and mesh variants are referenced only.

Usage: prepare_round3_plan.py            write the plan (refuses to overwrite) and its manifest; does not activate
       prepare_round3_plan.py --activate point active-plans.json at the written plan after re-checking its hash
"""
import copy, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(ROOT / "tools/art/knight_complete"))
ART = ROOT / "Local/FabRigTesting/Exports"; BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
OUT = ROOT / "Local/CustomuseAssets/Knight20261029r3"; PLAN = BASE / "knight-v030q/import-plan-KnightB.json"
DOC = ROOT / "docs/knight-complete-20261028/data/import-plan-KnightB-v030q.json"
HIDDEN = (.207, .391)        # blink hidden window in clip seconds (0.18-0.34 s of action time at rate 1.15)
BLINK_TOTAL = 122.3          # mesh-local cm (298.6 game cm), unchanged from v030p
PROTECTED = ["StrafeLeft", "StrafeLeftTwoHand"] + ["Stagger%s%s" % (d, g) for d in ("Front", "Back", "Left", "Right") for g in ("", "TwoHand")]


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

from normalize_sourced import normalize_file, GLB  # noqa: E402
from measure_locomotion import measure as stance_measure  # noqa: E402
old = json.loads((BASE / "knight-v030p/import-plan-KnightB.json").read_text())
P2 = {c["name"]: c for c in old["clips"]}
# key, file, loop, rate, nominal ("stance" = measured), root ("none" | "prefix:<s>" | "blink:<sign>")
JOBS = []
for side in ("Left", "Right"):
    for grip in ("", "TwoHand"):
        if side == "Right":
            # same stance motion as v030p (only re-phased and loop-closed): keep the v030p nominal, no in-game speed change
            JOBS.append(("Strafe%s%s" % (side, grip), "Knight_Strafe%s%s_v5c" % (side, grip), True, 1.0, "v030p", "none"))
        # retimed so the clip's stance-foot speed matches the v030p capsule nominal (owner rule: never slow the character)
        JOBS.append(("StrafeRun%s%s" % (side, grip), "Knight_StrafeRun%s%s_v5r" % (side, grip), True, 1.0, "v030p", "none"))
        JOBS.append(("Blink%s%s" % (side, grip), "Knight_Blink%s%s_v5c" % (side, grip), False, 1.15, 0.0, "blink:%s" % ("+1" if side == "Left" else "-1")))
JOBS.append(("BackpedalGuard", "Knight_BackpedalGuard_v5c", True, 1.0, 59.95, "none"))
JOBS.append(("BackpedalGuardTwoHand", "Knight_BackpedalGuardTwoHand_v5c", True, 1.0, 59.95, "none"))
JOBS.append(("RollAttack", "Sourced_RollAttack_v5", False, P2["RollAttack"]["gameplay_play_rate"], 0.0, "prefix:1.0"))
assert not set(k for k, *_ in JOBS) & set(PROTECTED)
if PLAN.exists():
    raise FileExistsError(PLAN)
canonical = GLB(old["rig"]["file"])
plan = copy.deepcopy(old)
plan.update(version="v030q", replace_runtime_source="/Game/Characters/Customuse/KnightB/v030p/DA_KnightB",
            purpose="Knight fix round 3 (2026-10-29): real blinks (launch crouch, hidden-window travel, landing to idle), sprint strafes with a "
                    "45-degree pelvis and free-arm swing, loop seams, raised backpedal guard, roll-attack exit; other clips inherited from v030p.")
plan["clips"] = []; plan["mesh_variants"] = {}; rows = []
for key, name, loop, rate, nominal, root in JOBS:
    f = ART / (name + ".glb"); meta = json.loads(f.with_suffix(".json").read_text())
    prefix = float(root.split(":")[1]) if root.startswith("prefix") else None
    row = normalize_file(f, canonical, OUT / "knight" / f.name, meta["fps"], prefix)
    samples, removed, srate = row["rootTranslationSamplesCm"], row["bRootMotionRemoved"], row["rootSampleRate"]
    if nominal == "v030p":
        nominal = P2[key]["nominal_speed_cm_per_second"]
        stance = round(stance_measure(row["file"])["rawStanceSpeedMedian"] * 240.0, 2)
        print("STANCE_VS_NOMINAL", key, stance, nominal, "residual %+.2f%%" % (100 * (stance / nominal - 1)), flush=True)
    if nominal == "stance":
        nominal = round(stance_measure(row["file"])["rawStanceSpeedMedian"] * 240.0, 2)
    if root.startswith("blink"):
        # Feet are planted on the idle stance whenever the knight is visible, so the root does not move then (no skate);
        # the whole blink distance is covered inside the hidden window with a smoothstep profile. Right = negative x.
        sign = float(root.split(":")[1]); T = row["duration"]; n = len(samples); srate = (n - 1) / T; samples = []
        for i in range(n):
            t = i / srate; u = max(0.0, min(1.0, (t - HIDDEN[0]) / (HIDDEN[1] - HIDDEN[0]))); u = u * u * (3 - 2 * u)
            samples.append([sign * BLINK_TOTAL * u, 0.0, 0.0])
        removed = True
        print("BLINK_ROOT", key, {"visibleRootSpeed": 0.0, "hiddenMeanSpeedMeshCmPerClipS": round(BLINK_TOTAL / (HIDDEN[1] - HIDDEN[0]), 1), "total": BLINK_TOTAL}, flush=True)
    rows.append({**row, "key": key, "source": name})
    plan["mesh_variants"].setdefault(row["mesh_variant"], {"file": row["file"], "sha256": row["sha256"]})
    windows = P2[key]["damage_windows"] if key == "RollAttack" else []
    plan["clips"].append({"name": key, "file": row["file"], "sha256": row["sha256"], "mesh_variant": row["mesh_variant"], "start_seconds": 0,
        "end_seconds": -1, "loop": loop, "gameplay_play_rate": rate, "nominal_speed_cm_per_second": nominal, "damage_windows": windows,
        "impact_seconds": sum(windows[0]) / 2 if windows else -1, "weapon_file": "BoatGreatsword_OneHand_v4.glb", "root_motion_policy": "preserve",
        "root_motion_removed": removed, "root_sample_rate": srate, "root_translation_samples_cm": samples, "root_yaw_samples_degrees": [],
        "source_duration": row["duration"], "approved_source_file": f.name, "approved_source_sha256": row["sourceSHA256"]})
    print("NORMALIZED", key, row["mesh_variant"], "rate", rate, "nominal", nominal, "err", row["canonicalReconstructionMaxMatrixError"], flush=True)
# Body: every new clip references the sourced-locomotion variant already imported (as v030p).
V = "knight_571e0abbfde2720e"
import numpy as np  # noqa: E402


def corners(path):
    g = GLB(path); _, node = g.body(); pr = g.g["meshes"][node["mesh"]]["primitives"]; assert len(pr) == 1
    i = g.accessor(pr[0]["indices"]).ravel(); a = pr[0]["attributes"]
    return {k: g.accessor(a[k])[i].astype(float) for k in ("POSITION", "TEXCOORD_0")}, [g.g["nodes"][j]["name"] for j in g.g["skins"][0]["joints"]]
# Blender round trips re-split vertices, so the variant hash differs; the engine draws variant V (already imported) for
# every clip. Check that each new clip's body has V's triangles corner for corner (positions, UVs) and V's joint list.
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
content = ROOT / "Unreal/Veyr/Content/Characters/Customuse/KnightB"
existing = {}
for v in plan["mesh_variants"]:
    hits = sorted(content.glob("v0*/MeshVariants/%s/*.uasset" % v))
    meshes = [h for h in hits if not h.stem.endswith("_PhysicsAsset") and not h.stem.startswith(("Image", "tripo_material", "Weathered"))]
    if meshes:
        m = meshes[-1]
        existing[v] = "/Game/Characters/Customuse/KnightB/%s/MeshVariants/%s/%s" % (m.parts[-4], v, m.stem)
plan["existing_mesh_variants"] = existing
missing = [v for v in plan["mesh_variants"] if v not in existing]
assert not missing, missing
assert existing == old["existing_mesh_variants"], (existing, old["existing_mesh_variants"])
plan["integration_notes"] = dict(plan.get("integration_notes", {}), knightFixRound3={
    "note": "see tools/art/knight_complete/build_round3.py and docs/knight-complete-20261028/plan-round3.md",
    "inheritedByReference": PROTECTED, "blinkRoot": "zero while visible (feet planted), smoothstep over the hidden window 0.207-0.391 clip s, 122.3 mesh cm",
    "nominalSpeeds": "every loop keeps its v030p nominal (capsule speeds unchanged; owner rule: never slow the character to fix sliding); the sprint cycles are retimed (84 -> 76 / 74 frames at 120 Hz) so their stance-toe speed matches 453.4 / 456.9", "bodyGeometryCheckAgainstV": geometry, "rollAttackDamageWindows": "unchanged from v030p"})
PLAN.parent.mkdir(parents=True, exist_ok=True); PLAN.write_text(json.dumps(plan, indent=2) + "\n")
sys.path.insert(0, str(ROOT / "tools/unreal")); import import_customuse  # noqa: E402
canon = import_customuse.inspect_glb(plan["rig"])
for c in plan["clips"]:
    v = plan["mesh_variants"].get(c["mesh_variant"])
    import_customuse.compatible(import_customuse.inspect_glb(v) if v else canon, import_customuse.inspect_glb(c))
DOC.write_text(PLAN.read_text())
(OUT / "knight-manifest.json").write_text(json.dumps({"version": "v030q", "plan": str(PLAN), "planSHA256": sha(PLAN), "clips": rows}, indent=2) + "\n")
print("PLAN_WRITTEN (not activated; run with --activate before the import commandlet)", PLAN, sha(PLAN))
