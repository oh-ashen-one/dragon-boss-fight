#!/usr/bin/env python3
"""Rebuild the KnightB v030s plan so it imports on top of the runtime's actual source (v030q): round 4 (v030r) was authored,
rendered and critiqued but never imported, so v030s must carry the round-4 sprint strafes (v6r) itself and take the
round-5 blinks (v7c) and roll attack (v7) from the prepared v030s plan. Rewrites the plan, its manifest hash and the docs copy."""
import copy, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; BASE = ROOT / "Local/CustomuseAssets/Polish20261025"
PLAN = BASE / "knight-v030s/import-plan-KnightB.json"; R = BASE / "knight-v030r/import-plan-KnightB.json"
MAN = ROOT / "Local/CustomuseAssets/Knight20261030r5/knight-manifest.json"
DOC = ROOT / "docs/knight-complete-20261028/data/import-plan-KnightB-v030s.json"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
s = json.loads(PLAN.read_text()); r = json.loads(R.read_text())
assert s["replace_runtime_source"].endswith("/v030r/DA_KnightB") and r["replace_runtime_source"].endswith("/v030q/DA_KnightB")
assert set(s["mesh_variants"]) == set(r["mesh_variants"]) and s["rig"]["sha256"] == r["rig"]["sha256"]
r5 = {c["name"]: c for c in s["clips"]}
sprints = [c for c in r["clips"] if c["name"].startswith("StrafeRun")]
assert len(sprints) == 4 and set(r5) == {"BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand", "RollAttack"}
for c in sprints + list(r5.values()):
    assert sha(c["file"]) == c["sha256"], c["name"]
m = copy.deepcopy(s); m["replace_runtime_source"] = r["replace_runtime_source"]
m["clips"] = sprints + [r5[k] for k in ("BlinkLeft", "BlinkLeftTwoHand", "BlinkRight", "BlinkRightTwoHand", "RollAttack")]
m["purpose"] = s["purpose"].replace("other clips inherited from v030r", "round-4 sprint strafes (v6r) carried in this plan because v030r was never imported; other clips inherited from v030q")
notes = m.setdefault("integration_notes", {}); notes["knightFixRound4"] = r.get("integration_notes", {}).get("knightFixRound4", "see plan-round4.md")
notes["knightFixRound5"]["inheritedByReference"] = [x for x in notes["knightFixRound5"]["inheritedByReference"] if "StrafeRun" not in x] + ["(every clip not listed, from v030q)"]
notes["v030rNeverImported"] = "round 4 (v030r) was critiqued NOT SHIPPABLE (roll attack) and never imported; its sprint strafes ship here"
PLAN.write_text(json.dumps(m, indent=2) + "\n"); DOC.write_text(PLAN.read_text())
man = json.loads(MAN.read_text()); man["planSHA256"] = sha(PLAN); man["version"] = "v030s"; man["carriedFromV030r"] = [c["name"] for c in sprints]
MAN.write_text(json.dumps(man, indent=2) + "\n")
print("MERGED", PLAN, sha(PLAN)); print("clips:", [(c["name"], Path(c["file"]).name) for c in m["clips"]]); print("replace_runtime_source:", m["replace_runtime_source"])
