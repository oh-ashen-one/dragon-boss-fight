#!/usr/bin/env python3
"""Additive KnightB v030k bank: lock-on strafes (walk+run, both grips) and directional staggers.
Structural normalization only (normalize_sourced.normalize_file); motion comes from the saved
Blender retarget/fit scenes. Inherits every existing clip by reference from RuntimePolish/DA_Knight
(v029). Does not activate anything in Unreal."""
import copy, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"tools/art/integration")); sys.path.insert(0, str(ROOT/"tools/art/knight_complete"))
from normalize_sourced import normalize_file, GLB
from measure_locomotion import measure
ART = ROOT/"Local/FabRigTesting/Exports"; BASE = ROOT/"Local/CustomuseAssets/Polish20261025"
OUT = ROOT/"Local/CustomuseAssets/Knight20261028"; PLAN = BASE/"knight-v030k/import-plan-KnightB.json"
GAME_CM_PER_GLB_M = 240.0  # calibrated: stance-foot median of WalkOneHand v2r2/WalkTwoHand v6r2/Backpedal loop vs their plan nominal speeds (240.2/246.6/239.8)
STAGGER_SECONDS = 0.60     # gameplay length of each directional stagger (existing non-directional Stagger: 0.42 s)
JOBS = []
for side in ("Left", "Right"):
    for grip in ("", "TwoHand"):
        JOBS.append(("Strafe"+side+grip, "Mixamo_Strafe"+side+grip+"_v2", True))
        JOBS.append(("StrafeRun"+side+grip, "Mixamo_StrafeRun"+side+grip+"_v2", True))
for d in ("Front", "Back", "Left", "Right"):
    for grip in ("", "TwoHand"):
        JOBS.append(("Stagger"+d+grip, "Mixamo_Impact"+d+grip+"_v2", False))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run():
    if PLAN.exists(): raise FileExistsError("v030k plan exists; preserve it")
    old = json.loads((BASE/"overhaul-v029/import-plan-KnightB.json").read_text()); canonical = GLB(old["rig"]["file"])
    plan = copy.deepcopy(old)
    plan.update(version="v030k", inherit_definition="/Game/Characters/Customuse/RuntimePolish/DA_Knight",
                replace_runtime_source="/Game/Characters/Customuse/KnightB/v029/DA_KnightB", runtime_folder="RuntimePolish",
                owner_approved=False, owner_requested_revision=True,
                purpose="Knight completion 2026-10-28: Mixamo strafes (walk/run, one/two-hand) for lock-on movement and directional staggers; every v029 clip inherited unchanged.")
    for k in ("finalize_only", "verify_pose_only", "restore_editor_settings"): plan.pop(k, None)
    plan["clips"] = []; plan["mesh_variants"] = {}; rows = []
    for key, name, loop in JOBS:
        f = ART/(name+".glb"); meta = json.loads(f.with_suffix(".json").read_text()); assert sha(f) == meta["sha256"], name
        row = normalize_file(f, canonical, OUT/"knight"/f.name, meta["fps"], None)
        speed = 0.0; rate = 1.0; m = None
        if loop:
            m = measure(row["file"]); speed = round(m["rawStanceSpeedMedian"]*GAME_CM_PER_GLB_M, 2)
        else:
            rate = round(row["duration"]/STAGGER_SECONDS, 4)
        rows.append({**row, "key": key, "sourceFPS": meta.get("sourceFPS", meta["fps"]), "bakeFPS": meta["fps"], "stance": m, "source": meta["source"], "mirrored": meta.get("mirrored", False), "classification": meta.get("classification")})
        plan["mesh_variants"].setdefault(row["mesh_variant"], {"file": row["file"], "sha256": row["sha256"]})
        plan["clips"].append({"name": key, "file": row["file"], "sha256": row["sha256"], "mesh_variant": row["mesh_variant"], "start_seconds": 0, "end_seconds": -1,
            "loop": loop, "gameplay_play_rate": rate, "nominal_speed_cm_per_second": speed, "damage_windows": [], "impact_seconds": -1,
            "weapon_file": "BoatGreatsword_OneHand_v4.glb", "root_motion_policy": "preserve", "root_motion_removed": False,
            "root_sample_rate": row["rootSampleRate"], "root_translation_samples_cm": row["rootTranslationSamplesCm"], "root_yaw_samples_degrees": [],
            "source_duration": row["duration"], "approved_source_file": f.name, "approved_source_sha256": row["sourceSHA256"]})
        print("NORMALIZED", key, "speed", speed, "rate", rate, "err", row["canonicalReconstructionMaxMatrixError"], flush=True)
    plan["integration_notes"] = dict(plan.get("integration_notes", {}), knightCompletion20261028={
        "sources": "Mixamo Sword and Shield Pack: strafe x4, impact x3 (+1 mirrored). Retargeted with fab_rig_testing/retarget.py, weapon fitted with fit_weapon.py (walk carry, one- and two-hand).",
        "nominalSpeed": "stance-foot median x %.0f game cm per glTF metre" % GAME_CM_PER_GLB_M, "staggerSeconds": STAGGER_SECONDS})
    PLAN.parent.mkdir(parents=True, exist_ok=True); PLAN.write_text(json.dumps(plan, indent=2)+"\n")
    sys.path.insert(0, str(ROOT/"tools/unreal")); import import_customuse
    canon = import_customuse.inspect_glb(plan["rig"])
    for c in plan["clips"]:
        v = plan["mesh_variants"].get(c["mesh_variant"])
        import_customuse.compatible(import_customuse.inspect_glb(v) if v else canon, import_customuse.inspect_glb(c))
    (OUT/"knight-manifest.json").write_text(json.dumps({"version": "v030k", "plan": str(PLAN), "planSHA256": sha(PLAN), "clips": rows}, indent=2)+"\n")
    active = BASE/"active-plans.json"; prior = json.loads(active.read_text()); (OUT/"previous-active-plans.json").write_text(json.dumps(prior, indent=2)+"\n")
    prior["KnightB"] = {"path": str(PLAN), "sha256": sha(PLAN)}
    d = Path(prior["DragonV3B"]["path"]); prior["DragonV3B"]["sha256"] = sha(d)  # path rewritten during restore
    active.write_text(json.dumps(prior, indent=2)+"\n"); print("PLAN_READY", PLAN, flush=True)
if __name__ == "__main__": run()
