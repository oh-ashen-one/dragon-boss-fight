#!/usr/bin/env python3
"""KnightB v030n (fix round 1): replaces this pass's strafes/staggers, adds guarded backpedals, rebuilds
BlinkLeft/BlinkRight (true mirror) and RollAttack (blended join, 1H idle end). Everything else is inherited
by reference from RuntimePolish/DA_Knight (v030m). Rig and mesh variants are referenced, never re-imported."""
import copy, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/integration")); sys.path.insert(0, str(ROOT / "tools/art/knight_complete"))
from normalize_sourced import normalize_file, GLB
ART = ROOT / "Local/FabRigTesting/Exports"; BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
OUT = ROOT / "Local/CustomuseAssets/Knight20261029"; PLAN = BASE / "knight-v030n/import-plan-KnightB.json"
STAGGER_SECONDS = .60
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old = json.loads((BASE / "knight-v030m/import-plan-KnightB.json").read_text())
v029 = json.loads((BASE / "overhaul-v029/import-plan-KnightB.json").read_text())
v027 = json.loads((BASE / "sourced-v027b/import-plan-KnightB.json").read_text())
blink_samples = {c["name"]: c for c in v029["clips"]}["BlinkLeft"]
ra027 = {c["name"]: c for c in v027["clips"]}["RollAttack"]
# key, file, loop, rate, nominal, windows, root ("none"|"prefix:<s>"|"blink:<sign>")
JOBS = []
for side, nom in (("Left", 138.41), ("Right", 155.51)):
    for grip in ("", "TwoHand"):
        JOBS.append(("Strafe%s%s" % (side, grip), "Knight_Strafe%s%s_v3c" % (side, grip), True, 1.0, nom, [], "none"))
        JOBS.append(("StrafeRun%s%s" % (side, grip), "Knight_StrafeRun%s%s_v3c" % (side, grip), True, 1.0, 440.2, [], "none"))
for d in ("Front", "Back", "Left", "Right"):
    for grip in ("", "TwoHand"):
        JOBS.append(("Stagger%s%s" % (d, grip), "Knight_Stagger%s%s_v3" % (d, grip), False, None, 0.0, [], "none"))
JOBS.append(("BackpedalGuard", "Knight_BackpedalGuard_v3c", True, 1.0, 59.95, [], "none"))
JOBS.append(("BackpedalGuardTwoHand", "Knight_BackpedalGuardTwoHand_v3c", True, 1.0, 59.95, [], "none"))
JOBS.append(("BlinkLeft", "Knight_BlinkLeft_v3", False, 1.15, 0.0, [], "blink:+1"))
JOBS.append(("BlinkRight", "Knight_BlinkRight_v3", False, 1.15, 0.0, [], "blink:-1"))
JOBS.append(("RollAttack", "Sourced_RollAttack_v3", False, ra027["gameplay_play_rate"], 0.0, ra027["damage_windows"], "prefix:1.0"))
if PLAN.exists(): raise FileExistsError(PLAN)
canonical = GLB(old["rig"]["file"])
plan = copy.deepcopy(old)
plan.update(version="v030n", replace_runtime_source="/Game/Characters/Customuse/KnightB/v030m/DA_KnightB",
            purpose="Knight fix round 1 (2026-10-29): idle-carry strafes and staggers, guarded backpedals, mirrored blink right, blended roll attack; other clips inherited from v030m.")
plan["clips"] = []; plan["mesh_variants"] = {}; rows = []
for key, name, loop, rate, nominal, windows, root in JOBS:
    f = ART / (name + ".glb"); meta = json.loads(f.with_suffix(".json").read_text())
    prefix = float(root.split(":")[1]) if root.startswith("prefix") else (meta["duration"] if root.startswith("blink") else None)
    row = normalize_file(f, canonical, OUT / "knight" / f.name, meta["fps"], prefix)
    samples, removed, srate = row["rootTranslationSamplesCm"], row["bRootMotionRemoved"], row["rootSampleRate"]
    if root.startswith("blink"):
        # Reuse the authored v029 blink transit root trajectory (fast during the hidden window); right = x mirrored.
        sign = float(root.split(":")[1])
        ref = blink_samples["root_translation_samples_cm"]
        assert len(ref) == len(samples), (len(ref), len(samples))
        samples = [[sign * p[0], p[1], p[2]] for p in ref]; removed = True; srate = blink_samples["root_sample_rate"]
    if rate is None:
        rate = round(row["duration"] / STAGGER_SECONDS, 4)
    rows.append({**row, "key": key, "source": name})
    plan["mesh_variants"].setdefault(row["mesh_variant"], {"file": row["file"], "sha256": row["sha256"]})
    plan["clips"].append({"name": key, "file": row["file"], "sha256": row["sha256"], "mesh_variant": row["mesh_variant"], "start_seconds": 0,
        "end_seconds": -1, "loop": loop, "gameplay_play_rate": rate, "nominal_speed_cm_per_second": nominal, "damage_windows": windows,
        "impact_seconds": sum(windows[0]) / 2 if windows else -1, "weapon_file": "BoatGreatsword_OneHand_v4.glb", "root_motion_policy": "preserve",
        "root_motion_removed": removed, "root_sample_rate": srate, "root_translation_samples_cm": samples, "root_yaw_samples_degrees": [],
        "source_duration": row["duration"], "approved_source_file": f.name, "approved_source_sha256": row["sourceSHA256"]})
    print("NORMALIZED", key, row["mesh_variant"], "rate", rate, "err", row["canonicalReconstructionMaxMatrixError"], flush=True)
# Body: every new clip references the sourced-locomotion variant (Blender round trips re-encode the body; see notes).
V = "knight_571e0abbfde2720e"
assert V in plan["mesh_variants"]
for c in plan["clips"]:
    c["mesh_variant"] = V
plan["mesh_variants"] = {V: plan["mesh_variants"][V]}
# Reference already-imported, identical mesh variants (same decoded geometry/skin/material hash).
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
print("VARIANTS", plan["mesh_variants"].keys(), "existing", existing, "missing", missing)
plan["integration_notes"] = dict(plan.get("integration_notes", {}), knightFixRound1={"staggerSeconds": STAGGER_SECONDS,
    "runStrafeNominal": "440.2 cm/s from source hips travel (3.479 m/s x retarget 0.5272 x 240); planted-toe check 446-458",
    "blinks": "Knight_BlinkLeft_v3 = Mixamo strafe (3) with travel; Knight_BlinkRight_v3 = its sagittal mirror; root samples = v029 BlinkLeft transit (right: x negated)"})
PLAN.parent.mkdir(parents=True, exist_ok=True); PLAN.write_text(json.dumps(plan, indent=2) + "\n")
sys.path.insert(0, str(ROOT / "tools/unreal")); import import_customuse
canon = import_customuse.inspect_glb(plan["rig"])
for c in plan["clips"]:
    v = plan["mesh_variants"].get(c["mesh_variant"])
    import_customuse.compatible(import_customuse.inspect_glb(v) if v else canon, import_customuse.inspect_glb(c))
(OUT / "knight-manifest.json").write_text(json.dumps({"version": "v030n", "plan": str(PLAN), "planSHA256": sha(PLAN), "clips": rows}, indent=2) + "\n")
if not missing:
    active = BASE / "active-plans.json"; prior = json.loads(active.read_text()); prior["KnightB"] = {"path": str(PLAN), "sha256": sha(PLAN)}
    active.write_text(json.dumps(prior, indent=2) + "\n"); print("PLAN_READY", PLAN)
else:
    print("PLAN_WRITTEN_NOT_ACTIVATED missing variants", missing)
