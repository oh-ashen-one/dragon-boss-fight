# Move data generator (Veyr dragon)

Measures move data from the dragon's Blender Actions and writes the JSON the boss runtime will read
(`Data/dragon/moves.json`, `boxes.json`, `tempo.json`, `sounds.json`). This is the first runtime piece of the
boss-fight blueprint (shared-brain package `boss-fight-blueprint`, `references/boss-runtime.md` section 2
"The move data contract" and section 11 step 2-3). The file shapes follow the Leshy contract described there.
Nothing in this folder changes C++.

## Commands

```bash
# everything (both usable Actions, one Blender at a time, refuses to start if Blender is already running)
tools/movedata/run_veyr.sh

# one Action -> Local/movedata/samples/<move>.sample.npz (headless)
blender --background --factory-startup Local/video2rig/dragon/Dragon_Roar_sd_v2r_v2.blend \
    --python tools/movedata/sample_action.py -- --action roar_sd_v2 --move roar --out Local/movedata/samples

# samples -> Data/dragon/*.json, prints a human summary
python3 tools/movedata/build_moves.py Local/movedata/samples/idle.sample.npz \
    Local/movedata/samples/roar.sample.npz --loop idle --out Data/dragon \
    [--threshold 5.0] [--part-threshold jaw=4 --part-threshold tail=8] [--scale 21.558172]

# tests (no Blender needed)
python3 -B -m unittest discover -s tools/movedata -p 'test_*.py' -v
```

Samples are 10-13 MB each and stay in `Local/` (gitignored). The JSON is deterministic: rerunning on the same
`.blend` files gives byte-identical output.

## Files

| File | Runs in | Role |
| --- | --- | --- |
| `veyr_rig.json` | both | Part map for this rig: which bones and vertex sets are the jaw, feet, wings, tail, body, hurt capsules; game scale; attack parts. Edit this, not the code, to remap a part. |
| `sample_action.py` | Blender 5.x, `--background --factory-startup` | Assigns the Action, steps it at 24 fps, writes bone heads/tails/rotations/basis quaternions, the root bone transform, named part points, per-frame lowest vertex of each foot and body underside, mesh bounds, a 1-in-8 subsample of the deformed mesh, the rest pose and every rest vertex with its dominant bone. Never saves the `.blend`. |
| `build_moves.py` | Python 3 + numpy | All measuring: track, windows, attacks, contacts, shocks, stances, quality, hurt capsules, coverage. |
| `run_veyr.sh` | bash | The two Veyr Actions end to end. |
| `test_build_moves.py` | unittest | Synthetic point moving fast for 10 frames gives exactly one window with the analytic t0/t1/peak. |

## Units and frames

- Unreal axes: x forward (the dragon's nose), y right, z up; yaw in degrees, positive toward +y.
- Blender metres to Unreal cm: `(x, y, z) m -> (100 x, -100 y, 100 z) cm` (the rig faces +X in Blender).
- **Game scale.** The rig is about 48.7 cm tall in Blender; the game shows it about 1050 cm tall (the presentation
  component scale `21.558172` in `VeyrDragon.cpp`). Samples are at rig scale; `build_moves.py` multiplies every
  length by `game_scale` (rig map, or `--scale`) so the JSON is in game centimetres and speeds are real game
  metres per second. A 5 m/s threshold at rig scale would find nothing. `game_scale` is written into both files;
  if the component scale changes, rebuild with `--scale` (or divide in C++).
- Time: clip seconds, 24 fps frames, `duration = (frames - 1) / 24`.
- Actor frame: origin = the rig origin on the floor under the dragon at frame 0, carried along the root track.
  "In the actor frame at that moment" = the track's position and yaw at that frame removed. The C++ must add
  its own mesh-in-actor offset and yaw (the imported presentation is translated and rotated inside the actor).
- Bone names are Blender names (`tripo::Root`, `bone_5`, `VeyrJaw`). The Unreal skeleton keeps the glTF names;
  check the imported names before binding.

## moves.json

Top level: `fps`, `units`, `game_scale`, `actor_frame`, `generator`, `settings` (every threshold used),
`part_thresholds_mps`, `idle_stance_cm` (sole xy per foot at idle frame 0), `moves`.

Per move. Fields the C++ is meant to read (Leshy contract):

| Field | Shape / units | Meaning |
| --- | --- | --- |
| `duration` | s | `(frames - 1) / 24` |
| `loop` | bool | `--loop` moves (idle). Loops should never hurt (Leshy rule), even if they have attacks. |
| `track` | `[[x_cm, y_cm, yaw_deg], ...]` per frame, starts `[0,0,0]` | Track bone (rig map `track_bone`, `tripo::Root`) planar position and cumulative yaw relative to frame 0. |
| `attacks` | `[{part, t0, t1, peak_t, peak_v, at_peak}]` | Hot windows of attack parts. `t0`/`t1` clip s (interpolated crossings), `peak_t` clip s (parabola-refined), `peak_v` m/s, `at_peak` cm in the actor frame at the peak. |
| `shocks` | `[{t, bone, at, speed, radius}]` | Touchdowns of a foot or body underside at `shock_min_mps` or faster. `at` actor frame, z = 0. `radius` cm = min(450, 150 + 20 x speed). |
| `contacts` | `[{t, frame, bone, kind, speed, at}]` | Every touchdown: `step` (foot) or `body` (chest, belly, hips, head, tail underside). Speed m/s over the 3 frames before touchdown. |

Fields for QA and the move gate (not needed by the playback):

| Field | Meaning |
| --- | --- |
| `stances` | Per foot runs on the floor: `foot, bone, f0, f1, t0, t1, frames, at, drift_cm, slides`. |
| `quality` | `slides`, `max_stance_drift_cm`, `toes_under_floor_cm` (below Blender z = 0), `floor_cm` (lowest foot point over the move), `feet{lowest_cm, above_floor_cm, height_range_cm, never_planted, max_drift_cm}`, `max_twist_deg/bone/frame` (axial twist of a bone's basis rotation vs rest), `max_twist_jump_deg/bone` (largest one-frame twist change), `root_moved_cm`, `body_offset_cm`/`body_bob_cm` (`tripo::Spine_0` head), `seam_jump_cm`/`seam_vs_median_step` (last frame vs first; under ~1.5 means the loop closes), `mesh_height_cm` range. |
| `windows` | Every hot run on every listed part (attack parts plus `window_only_parts`: head, wing tips), with `point`, `f0`, `f1`, `threshold`, `carry_in`. |
| `parts` | Per attack part per frame `[x, y, z, speed]`, actor frame cm and m/s. |
| `source`, `span`, `tempo`, `end`, `heading_change_deg`, `stance_start_cm`, `stance_end_cm` | Provenance (blend path, md5, Action, frame range) and Leshy-style bookkeeping. |

### How each number is measured

- **Speed** of a point: central differences of its world position, game cm per frame x 24 / 100 = m/s.
- **Windows**: open where speed reaches the threshold (default **5 m/s**, `--threshold`, per part
  `--part-threshold PART=MPS` or `threshold_mps` in the rig map), close when it drops under threshold x 0.9;
  runs shorter than 2 frames are dropped, runs 1 frame apart merge. A window that peaks on frame 0 is motion
  carried in from before the clip (`carry_in: true`); it stays in `windows` but never becomes an attack.
- **Attack parts** (rig map `attack_parts`): `jaw` = VeyrJaw tail, `paw_fl/fr/hl/hr` = vertex-tracked toe tips,
  `wing_l/r` = membrane trailing tips (`VeyrWing{NegZ,PosZ}Membrane` tail; NegZ is the left wing), `tail` =
  `tripo::Tail_2` tail. Every attack-part window becomes an attack: there is no hand curation yet. Leshy's data
  drops some windows by design (no jaw window on a roar); do that in a curation step, not by editing the JSON.
- **Feet**: the height of each foot is its lowest skinned vertex each frame (game cm). A foot's own floor is its
  lowest height over the move (unless that is more than 15 cm above the lowest foot: never planted). Down within
  4 cm of its floor and under 120 cm/s horizontally; up above 8 cm (Leshy foot-lock numbers). Drift and slides use
  the centroid of the 32 lowest rest vertices of the foot (stable xy); a slide = over 15 cm/s for 4+ frames.
- **Track**: the rig map `track_bone`. On this rig `tripo::Root` never moves; the video2rig fit carries the
  body's motion on `tripo::Spine_0` location keys, which `quality.body_offset_cm` reports.

## boxes.json

`units`, `game_scale`, `rest_cover` (share of all mesh vertices inside some capsule at rest), `moves_cover`
`{move: {min, mean}}` (same, per frame on the 1-in-8 subsample with capsules riding their bones), `parts`, `toes`,
`tracks`, `mesh_vertices`, `mesh_height_cm`, `source`.

`parts{name: {bone, kind, damage, a, b, radius, a_bone, b_bone, vertices, cover, leg?}}` for head, neck, chest,
belly, hips, `leg_fl/fr/hl/hr` (`leg` = the C++ leg index 0 FL, 1 FR, 2 HL, 3 HR), `wing_l/r`, tail.

- Fit: the part's vertices = those whose strongest weight is one of the part's bones (rig map `hurt`). Capsule
  axis = principal axis of those rest vertices; radius = the smallest perpendicular-distance quantile that puts
  75% of the part's vertices inside; ends at the 2nd/98th percentile along the axis, pulled in by half a radius.
  `shape: sphere` (chest) gives a == b.
- `a`, `b`: segment ends in the mesh rest pose, component space, game cm (Leshy convention). Convert them into
  the bone's frame at load with the imported rest pose (divide by `game_scale` first if the rest pose is in mesh
  units), which is immune to importer bone-axis changes. `a_bone`, `b_bone`: the same ends relative to the
  bone's rest head in its Blender rest frame (Unreal handedness); valid only if the imported bone axes match.
- `damage`: incoming-blow multipliers, defaults head 1.5, neck/body 1.0, legs 0.8, tail 0.7, wings 0.5 (Leshy
  pattern plus the current C++ leg/tail/head ratios). Tune in the rig map.
- `toes{fl,fr,hl,hr: {bone, bones, tip, stand, drop}}`: toe tip and lowest sole point at rest, game cm; `drop` 0.
- `tracks{move: {"1","7",...: {part: [x,y,z]}}}`: capsule centres every 6th frame (1-based keys), actor frame, for
  the move gate's capsule check.

## tempo.json and sounds.json (stubs)

`tempo.json`: every move `[[0, 99, 1.0]]`. `sounds.json`: `dir` `/Game/Veyr/Audio/Dragon` (does not exist yet),
`moves{move: []}`, `steps: []`. Same shapes as the Leshy files so the loader can be written now.

## What the C++ will read (not changed yet)

The plan for `AVeyrDragon` (today it hard-codes moves, leg radii 60-75 cm, the 19 solid capsules, head
exposure and a fixed wind-up/active/recovery timing in `VeyrDragon.h/.cpp`):

1. Load `Data/dragon/moves.json`, `boxes.json`, `tempo.json`, `sounds.json` at BeginPlay (an index
   `Data/dragon.json` naming the clip assets per move is still to be written once the Actions are imported).
2. Per move: `duration`, `loop`, `track` (root motion by the actor, 24 fps, linear interpolation), `attacks`
   (hit test per tick over the clip-time interval, one hit per window, `peak_v` as hit speed), `shocks`,
   `contacts` (footfall sound, dust tier by `speed`). Loops never hurt.
3. `boxes.parts`: one query-only capsule per part on `bone`, from `a`/`b`/`radius`, `damage` as the multiplier;
   the four `leg` capsules replace the hard-coded leg radii and feed the per-leg stagger.
4. `tempo.json` rates and `sounds.json` events once they hold data.
5. The move gate reads `stances`, `quality` and `boxes.tracks`.

## Limits on this rig (what the schema cannot express)

- **No root motion in the source.** `tripo::Root` is static; travel and lurch live on `tripo::Spine_0`. The
  track is all zeros for idle and roar (correct for in-place moves). A travelling move needs `track_bone`
  pointed at a bone that carries the travel, or a Root bake in Blender, before its track means anything.
- **Wings are plates, not tubes.** One capsule per wing (radius about 2 m) covers 75% of the membrane only by
  also covering air in front of and behind it. Several capsules per wing, or a box shape, would be needed for
  honest wing hits; the schema has capsules and spheres only.
- **One capsule per leg** spans shoulder to foot (6.4 to 6.7 m on the front legs). The current C++ uses
  lower-leg capsules; split into upper/lower parts in the rig map if the leg stagger needs it.
- **No curation.** A roar's jaw and wing windows become attacks because they move fast; whether a roar should
  hurt is a design call the generator does not make.
- **Feet hover in the roar.** The roar's lowest foot is 18 cm above Blender z = 0 and the front-left foot 9.7 cm
  above that for the whole clip; the refinement pinned the feet where the fit put them. Fix in Blender (lower
  the pins) before the foot-lock gate, which assumes planted feet at stand height.
