#!/usr/bin/env python3
"""Add the airborne annotations to Data/dragon/moves.json (run after build_moves.py by run_veyr.sh; deterministic).
air_fire_down: the active window is the jaws-open-pointing-down hold. Frames come from the refinement (jaw envelope: open by frame 80, shut from 160, 24 fps):
the gameplay window for the Niagara fire is t0 to t1."""
import json, sys
path = sys.argv[1] if len(sys.argv) > 1 else "Data/dragon/moves.json"
d = json.load(open(path))
M = d["moves"]
AIR = {"air_hover": "hover loop at the hover pose height", "air_land": "descent from hover to the ground stance (touchdown frame 90)",
       "air_takeoff": "ground stance to hover pose", "air_fire_down": "hover, body pitched nose-down, jaws open pointing down"}
for k, note in AIR.items():
    if k in M:
        M[k]["airborne"] = True; M[k]["air_note"] = note
        M[k]["floor_metrics_valid"] = False   # build_moves infers the floor from the lowest foot: shocks, contacts, stances and floor figures are not meaningful while airborne
if "air_fire_down" in M:
    fps = float(d.get("fps", 24))
    M["air_fire_down"]["annotations"] = [{"name": "fire_down_hold", "t0": round(80 / fps, 3), "t1": round(160 / fps, 3),
        "frames": [80, 160], "note": "jaws open to 40 deg and the head pointing down; Niagara fire timed on this window (refine jaw envelope: open by 80, shut from 160)"}]
if "air_land" in M:
    fps = float(d.get("fps", 24))
    M["air_land"]["annotations"] = [{"name": "touchdown", "t0": round(90 / fps, 3), "t1": round(90 / fps, 3), "frames": [90, 90], "note": "feet planted by IK from frame 90 (authored; the fit's landing frames are unreliable)"}]
json.dump(d, open(path, "w"), indent=1)
print("ANNOTATED", [k for k in AIR if k in M])
