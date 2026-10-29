# Knight fix round 3 (2026-10-29): what was sourced, what was authored, numbers

Runtime version **KnightB v030q** (not activated, not imported, not owner-approved). It covers 13 re-authored clips:
StrafeRight(2H), StrafeRunLeft/Right(2H), BlinkLeft/Right(2H), BackpedalGuard(2H) and RollAttack. Every other clip,
including the protected StrafeLeft(2H) and the eight staggers, is inherited **by reference** from the v030p runtime
definition (`inherit_definition`), so the importer never touches their GLBs or `.uasset`s.

- Plan: `Local/CustomuseAssets/Polish20261025/knight-v030q/import-plan-KnightB.json` (copy in `data/import-plan-KnightB-v030q.json`;
  the sha256 is in `Local/CustomuseAssets/Knight20261029r3/knight-manifest.json`). The sprint strafes use the retimed
  `Knight_StrafeRun*_v5r` clips.
- Authoring driver: `tools/art/knight_complete/build_round3.py`. It runs headless Blender 5.2 with `--factory-startup`,
  and each stage saves an editable `.blend` next to each GLB in `Local/FabRigTesting/Exports`.
- Metrics: `data/round3-metrics.json` (`tools/art/knight_complete/measure_round3.py`). All numbers below are pose
  space on the normalized GLBs the game imports, glTF mesh space, game cm = rig m x 240, sampled at 30 fps of game
  time at the in-game rate. Loops are sampled at evenly spaced phases. r2 is the v030p clip.
- Pixel metrics (the critic's seam method and first/last-vs-idle) are filled in by the render step below. They are
  **not measured yet**, because the GPU slot was closed by the stream window.

## Per fix

### 1. Blinks: BlinkLeft/Right, 1H and 2H (rebuilt)

**Sourced:**
- Mixamo "sword and shield crouch" (`Mixamo_Crouch_v1`, retargeted). Frames 0-9 are added as deltas at 0.60 gain on
  the 1H/2H approved idle frame 0. They play forward for the launch and reversed for the landing.
- The Mixamo jump sources were surveyed by `analyze_round3_sources.py` and rejected. They start from a 1.0-leg-wide
  stance and have a 6 cm anticipation dip and no landing absorption.

**Authored (keys in `BLINK_KEYS`):**
- lateral hip push
- lean into travel
- pelvis yaw (the spine counters 85%)
- free-hand lead in the 1H clips
- timing around the game's hidden window: clip 0.207-0.391 s = action 0.18-0.34 s at rate 1.15

Feet are IK-planted on the idle stance throughout. The root track is 0 while the knight is visible and smoothsteps
122.3 mesh cm (about 298 game cm, the same as v030p) inside the hidden window. Clip length is 0.70 s. The first and
last frames are pinned to the exact idle.

| | r3 | r2 |
|---|---|---|
| launch crouch | -15.0 cm, reached in 3 frames (4 frames below -2 cm before hiding) | none |
| landing | -13.5 cm, settles to exact idle by 0.62 s | none |
| first/last vs idle (pose) | 0.00 / 0.00 cm | 38.7 / 35.4 cm |
| ankle width first/last | 61.9 / 61.9 cm (idle 61.9) | 61.5-62.3 |
| twist max | 10.4° (L), 19.5° (R) | 87.5°, 92.8° |
| chest max | 6.5°, 3.6° | 13.9°, 13.7° |
| visible root step | 0.000 cm | 6.5 cm per frame |
| 1H free-hand swing | 15.8 / 21.7 cm | 8.7 / 9.4 cm |

Afterimage poses (captured at clip 0.184 and 0.391): departure hips -11.0 cm with the chest on the boss; arrival
-14.8 cm.

### 3. Sprint strafes: StrafeRunLeft/Right, 1H and 2H (rebuilt)

**Sourced:**
- legs and timing: Mixamo "strafe (4)" forward run (`Mixamo_StrafeRunRight_v1`) and its sagittal mirror (`..LeftM_v1`),
  the same sources as r2
- the ankle paths come from the source, so the stride, contacts and cross-over pattern are the source's

**Authored:**
- The whole body is turned about the hips so the pelvis is 45° off the boss, about 45° off travel. A solver picks the
  pelvis/chest split under twist ≤44° and chest ≤18°.
- The spine (30/35/35%) brings the chest to 11° plus 50% of the source shoulder swing.
- The feet turn half the hip turn.
- Ankles are held on the source foot paths by an explicit-pole two-bone IK:
  - pole = the sourced knee direction turned with the hips, plus 5 cm of pelvis-forward, smoothed ±2 frames
  - 98% reach clamp
  - the thigh is rolled so the knee hinge stays anatomical
- The hips drop that keeps reach ≤98% is dilated ±3 frames, smoothed, and made equal for both steps (4-6 cm, a
  2 cm bob per step).
- 1H clips: the free left hand counter-swings with the feet (7.5 cm of amplitude in the chest frame, plus lift and
  forward).

An earlier r3 build (before this pole) flipped a near-straight knee: knee-vs-travel was 144-149°. It was found and
rebuilt.

| | r3 L / R | r2 L / R |
|---|---|---|
| pelvis-to-chest twist max | 37.7° / 37.7° | 87.6° / 92.9° |
| chest to boss max | 17.9° / 17.9° | 13.8° / 13.7° |
| pelvis off travel (mean) | 41.8° / 41.2° | 12.4° / 7.1° |
| knee vs travel (max) | 45.1° / 47.5°; frame-to-frame knee yaw change ≤4° | 9.7° / 9.8° |
| feet min separation (ankles/toes) | 25.2/28.3, 25.7/29.2 cm | 25.4/28.9, 25.8/28.8 cm |
| 1H free-arm swing | 27.7 / 36.7 cm | 8.7 / 9.5 cm |
| seam / mean (head-chest, hips-sword, legs) | .68 .48 .80 / .70 .53 .80 | .63 .63 .88 / 1.27 1.25 1.15 |

**Speed (rule-driven, owner rule "never slow the character to fix sliding"):**
- The lock-on sprint capsule speeds stay at v030p: nominal 453.4 (L) and 456.9 (R), cap min(580, 1.1 x nominal) =
  498.7 / 502.6 game cm/s.
- The authored cycles (`_v5c`, 0.70 s) had a stance-foot speed of only 410.7 / 404.4 cm/s. That would have skated
  about 10%, which is the critic's "stance foot slides ~11 px per frame" in r2.
- The `retime` stage therefore resamples each cycle with the same poses and phase order into fewer 120 Hz frames:
  84 -> 76 frames (0.633 s) for L and 84 -> 74 (0.617 s) for R.
- Measured stance-foot speed after the retime is 453.66 / 458.3 cm/s: **residual skate +0.06% / +0.31%**.
- The seam, twist, chest, knee and free-arm numbers above are re-measured on the retimed `_v5r` clips.
- Blinks do not share the sprint legs (they are built on the idle), so their travel and timing are unchanged.

### 4. RollAttack exit (rebuilt, `Sourced_RollAttack_v5`)

Unchanged from r2: the roll (Fab_Roll_v17), the 0.60 s join, the slash (Mixamo_Attack_v17) and the damage window
[1.36, 1.576] clip s.

**Authored:**
- From 1.60 s the right-arm chain and grip slerp from their 1.60 s locals to the idle carry, over 1.60-2.10 s. There is
  no second wind-up.
- A wrist correction about the horizontal axis (≤21.2°, zero at both ends) makes the blade pitch rise monotonically.
- Two sequential recovery steps on linear time: the lead foot over 0.19 s, then the rear foot over 0.19 s. Each foot is
  locked while the other steps.

| rendered frames (rate 1.282) | r3 | r2 |
|---|---|---|
| lead (left) foot | lifted f42-f46: lift 3.5, 12.0, 15.0, 11.1, 2.2 cm; max 28 cm per frame | 41 cm in one frame at f46 |
| rear (right) foot | locked f43-f46, lifted f47-f50 (9.4-14.0 cm) | 9 cm slide with 13.9 cm lift |
| blade pitch f38-f51 | -1.3 rising monotonically to 7.6° (max rise 1.2° per frame) | rose to 50.4° at f46 |
| last frame vs idle | 0.0 cm | 0.0 cm |

### 5. Loop seams (re-keyed: StrafeRight(2H), StrafeRunRight(2H), both backpedals)

**Authored (no new motion):**
- loop closure: the end-to-start residual is spread linearly, max 0.04°
- cycle start moved to the phase whose one-render-frame step is ≤0.80 (else ≤0.92) of the in-cycle mean in every band,
  nearest the idle ankle width

The renders now sample loops at evenly spaced phases, so the wrap is an ordinary step.

| seam / mean (head-chest, hips-sword, legs) | r3 | r2 |
|---|---|---|
| StrafeRight | .88 .80 .91 | .87 1.03 1.08 |
| StrafeRightTwoHand | .88 .74 .91 | .87 1.00 1.08 |
| StrafeRunRight(2H) | see item 3 | 1.27 1.25 1.15 |
| BackpedalGuard | .96 .93 .94 | 1.61 1.61 .73 |
| BackpedalGuardTwoHand | .96 .98 .94 | 1.61 1.59 .73 |

The BlinkRight seam is moot: its first and last frames are now the exact idle (item 1). The StrafeRight(2H) stance
motion is the r2 motion, so it keeps the v030p nominal (159.7) and there is no speed change. Its measured stance speed
is 155.5, so the residual is -2.6%, the same as r2.

### 7. BackpedalGuard 1H, and 2H kept consistent (re-fit)

**Sourced:** the approved backpedal loop body (`Knight_BackpedalGuardBody_v4`, from Backpedal_Blender_loop_v1r3), unchanged.

**Authored:** the hilt (`guard_hilt`):
- the hand sits in front of the right pectoral (1H 7 cm below the Spine2 joint, 2H 12 cm)
- the blade is aimed up, forward and out to the knight's right

| | 1H r3 | 1H r2 | 2H r3 | 2H r2 |
|---|---|---|---|---|
| hand minus chest height | -7.2 cm | -24.1 cm | -12.0 cm | -11.1 cm |
| helmet covered from the boss view | 0.00 | 0.75 | 0.00 | 0.75 |
| blade frontal angle from vertical | 28-31° | 15-21° | 32-34° | 5-13° |

## Not fixed, and why

- **Item 8 (walk-strafe crouch depth and head bob):** deferred to the owner. It conflicts with the instruction that
  StrafeLeft(2H) stay byte-identical. StrafeRight(2H) keeps the same crouch, so left and right stay symmetric. Its
  pelvis-to-chest twist (80.9°) is unchanged and outside item 3's scope (sprints and blinks).
- **Protected StrafeLeft(2H) seams** with even phase sampling are 1.18 / 0.99-1.05 / 0.89. These cannot be re-keyed
  without breaking byte-identity.
- **Items 2 and 6** (engine blend proof and the roll root motion in engine) belong to the other agent. **Item 9** was
  skipped by owner decision.
- **Sprint loop start width** is 91-92 cm (idle 62). No phase near idle width met the seam ratio, and the game blends
  idle↔sprint over 0.1 s.
- **Afterimages** are not drawn in the review renders. Their poses are reported in the metrics.
- **The pixel numbers and the visual check** of every changed clip are pending the renders below.

## Byte-identical check

`data/round3-protected-sha256-before.txt` (30 files) holds the Exports GLB, the normalized r2 GLB and the v030p
`.uasset` for StrafeLeft, StrafeLeftTwoHand and the eight staggers, recorded before any round-3 work.
`measure_round3.py` re-hashes them: **all 30 identical** (`byteIdenticalAll: true` in `data/round3-metrics.json`).

## Commands for the orchestrator

Renders (the GPU slot was closed by the stream window, 0 capture slots until 13:30 ET). This one script makes the
jobs, renders through the slot (`--timeout 3600`), encodes the lazy-loading page and rewrites the metrics with pixels:

```
cd /Users/midir/veyr-knight-20261028 && tools/art/knight_complete/render_round3.sh
```

The script runs these steps:
```
python3 tools/art/knight_complete/review_jobs_r3.py Local/knight-review-20261028/r3
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r3-render --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/render_review.py -- Local/knight-review-20261028/r3/jobs.json Local/knight-review-20261028/r3
python3 tools/art/knight_complete/build_review_page.py Local/knight-review-20261028/r3 --serve ../serve-round3
python3 tools/art/knight_complete/measure_round3.py docs/knight-complete-20261028/data/round3-metrics.json
```

The render covers 35 jobs, about 1,400 frames x 3 views:
- 13 changed clips, the two idles and StrafeLeft(2H), in place, on mesh V with even phase sampling
- 10 root-travel loops at capsule speed, with the camera following the root
- 8 blink travel renders (r3 and r2): idle, then the blink with its root track and the hidden window not drawn, then
  idle, on a fixed camera

Every job was dry-run (`--dry`: sampled and posed, nothing rendered). Serve the page with:
`python3 Local/knight-review-20261028/serve-round3/rangeserver.py Local/knight-review-20261028/serve-round3 <port>`.
`serve/` stays round 2.

Import: **done 2026-10-29** (orchestrator instruction). Only RuntimePolish/DA_Knight changed among the pre-existing
Customuse assets; 14 new assets were added under KnightB/v030q; the 30 protected files are identical. The
`-script` path must be absolute:
```
python3 tools/art/knight_complete/prepare_round3_plan.py --activate
"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" /Users/midir/veyr-knight-20261028/Unreal/Veyr/Veyr.uproject -run=pythonscript -script=/Users/midir/veyr-knight-20261028/tools/art/knight_complete/native_import_v030k.py -nullrhi -unattended -NoZenAutoLaunch -notraceserver
```
