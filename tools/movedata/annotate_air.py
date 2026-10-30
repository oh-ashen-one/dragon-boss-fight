#!/usr/bin/env python3
"""Add the airborne annotations to Data/dragon/moves.json (run after build_moves.py by run_veyr.sh; deterministic).
air_fire_down: the active window is the jaws-open-pointing-down hold. Frames come from the refinement (jaw envelope: open by frame 80, shut from 160, 24 fps):
the gameplay window for the Niagara fire is t0 to t1."""
import json, sys
path = sys.argv[1] if len(sys.argv) > 1 else "Data/dragon/moves.json"
d = json.load(open(path))
M = d["moves"]
AIR = {"air_hover": "hover loop at the hover pose height", "air_land": "descent from hover to the ground stance (touchdown frame in the touchdown annotation)",
       "air_takeoff": "ground stance to hover pose", "air_fire_down": "hover, body pitched nose-down, jaws open pointing down"}
for k, note in AIR.items():
    if k in M:
        M[k]["airborne"] = True; M[k]["air_note"] = note
        M[k]["floor_metrics_valid"] = False   # build_moves infers the floor from the lowest foot: shocks, contacts, stances and floor figures are not meaningful while airborne
if "air_fire_down" in M:
    fps = float(d.get("fps", 24))
    M["air_fire_down"]["annotations"] = [{"name": "fire_down_hold", "t0": round(80 / fps, 3), "t1": round(160 / fps, 3),
        "frames": [80, 160], "note": "jaws open to 40 deg and the head pointing down; Niagara fire timed on this window (refine jaw envelope: open by 80, shut from 160)"}]
# fix round 3 (air_land_v5): authored contact C = 100 (glide, braking flare over 86-97, feet eased onto the floor over 94-100,
# slam from 97); the v4 Action planted its feet at 90
TOUCHDOWN_BY_ACTION = {"air_land_v5": 100, "air_land_v4": 90}
if "air_land" in M:
    fps = float(d.get("fps", 24))
    TOUCHDOWN = TOUCHDOWN_BY_ACTION.get(M["air_land"].get("source", {}).get("action"), 100)
    M["air_land"]["annotations"] = [{"name": "touchdown", "t0": round(TOUCHDOWN / fps, 3), "t1": round(TOUCHDOWN / fps, 3), "frames": [TOUCHDOWN, TOUCHDOWN],
        "note": "feet planted by IK from this frame (authored; the slam and wing slap start 3 frames earlier, as the braked feet reach the floor)"}]
if "air_hover" in M:
    # fix round 3: the hover loop is frames 0..129; frame 130 duplicated frame 0 (the critic's seam double)
    fps = float(d.get("fps", 24)); mv = M["air_hover"]
    mv["loop_frames"] = [0, 129]; mv["loop_duration_s"] = round(130 / fps, 4)
    mv["loop_note"] = "play frames 0-129 cyclically; the sampled Action runs 0-130 and frame 130 equals frame 0, so it must not be played twice"
json.dump(d, open(path, "w"), indent=1)
print("ANNOTATED", [k for k in AIR if k in M])
