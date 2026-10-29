# Knight fix round 4 (2026-10-29): plan, evidence and GPU-phase commands

**Status: preparation only.** Nothing has been authored, rendered or imported. No Blender, Unreal, game build or
gpu_slot launch was made. The GPU belongs to another session by owner order. All the numbers below come from pure
CPython/numpy analysis of the existing round-3 GLBs and the lossless round-3 render PNGs. For the seam diagnosis, CPU
libx264 re-encodes of those existing PNGs were also made in the scratchpad. They are not shipped, and no new content
was rendered.

Targets come from `critique-round3.md`. The round-4 runtime would be **KnightB v030r**:
- It changes 9 clips: StrafeRun{Left,Right}(2H), Blink{Left,Right}(2H) and RollAttack.
- Every other clip is inherited **by reference** from the v030q definition. That includes the protected
  StrafeLeft(2H), the eight staggers, StrafeRight(2H) and both backpedals.

Scripts (all in `tools/art/knight_complete/`):

| Script | Role |
| --- | --- |
| `build_round4.py` | Headless Blender stages. `--dry` runs under plain CPython. |
| `r4_core.py` | Shared pure-python math and every round-4 tunable. |
| `measure_round4.py` | `OUT.json`, `retime-args` and `predict` modes. |
| `prepare_round4_plan.py` | Plan v030r. Has `--check` and `--activate`. |
| `review_jobs_r4.py` | Review job list. |
| `render_review.py` | Gains a `views` / `top` option. |
| `build_review_page.py` | Gains `--intra` and `--frames-also`. |
| `author_round4.sh`, `render_round4.sh` | The two GPU-phase drivers. |

## 1. Sprint strafes: the pelvis reads ~80 deg off the boss (target: legs within ~45 deg, side span >= 0.6x front)

**Why round 3 reported 45 deg.** `measure_round3` "pelvis" is the facing of the hip-joint line. On the v030q
`_v5r` clips that line really is 45.0 deg (range 40.9-47.2), and the Hips bone is turned 47.5 / -42.3 deg.

The critic read the **legs**. `measure_round4.pelvis_vs_boss` measures the leg plane directly from bone transforms:
- The hip-knee-ankle plane of the swinging leg sits at **52.6-60.9 deg** (mean over the swing frames).
- At the full kick it sits at **59.6-63.4 deg**.
- The kicked shin spans 45-48 cm in the front view but only 16-24 cm in the side view: **side/front = 0.35-0.54**.

So the thighs and shins still swing along the travel line, which is lateral, and that reads as a sideways sprint.

Cause: round 3 turned the hips and the knee pole, but the IK ankle targets kept the source foot paths, which run along
the travel direction.

**Change (`bodies` stage).**
- While a foot is off the ground (swing weight `w` from ankle and toe clearance, 0 on stance), its ankle target is
  rotated about the hip's vertical axis by `w x theta`.
- `theta` = pelvis yaw - travel yaw = -44.8 deg (Left) / +44.3 deg (Right), from the prediction.
- The foot turns with the ankle target.
- The knee pole goes from 60 % pelvis-forward on stance to 100 % in the swing.
- Stance frames keep the sourced ankle path, so the foot lock and stance speed are unchanged.
- A gate refuses to export unless both full-kick leg planes are <= 52 deg, side/front >= 0.8 and the stance ankle
  error <= 1 cm. On failure it writes `round4-bodies-report.json`.
- After that the stages run as in round 3: fit, cycles (loop closure), then a retime to the unchanged v030q capsule
  nominal (453.4 / 456.9 cm/s; never slow the character).

**Frames.** About 50 of the 74-76 frames at 120 Hz per leg have w > 0.5. The full kick is at f57 / f14 (Left run) and
f13 / f55 (Right run).

**Prediction (`measure_round4.py predict`, r4_core math on the v030q data, no Blender):**
- Full-kick plane 46.0-46.5 deg.
- Side/front 0.85-0.98 (r3: 0.35-0.54).
- Stance ankle shift <= 0.47 cm.
- Ankle separation in the scratch prototype: 25 -> 32 cm.

**Measured later in `round4-metrics.json`:**
- `pelvisVsBoss`: `legPlaneOffBossDeg` and per-leg `fullKick.planeYaw` <= 52, `sideOverFront` >= 0.6,
  `hipLineYaw` ~45.
- `feetMinSeparationCm` (r3: 29.4 / 30.1).
- Seams and twist (m3).
- `STANCE_VS_NOMINAL` residual (in the prepare log).
- Review: top views (`top-r4-*` vs `top-r3-*`, boss at the top) and root travel at capsule speed (`rt-r4-*`).

## 2 and 3. Backpedal seams "unchanged", walk StrafeRight wrap 1.29 / 1.19: I disagree. It is the MP4 encoder.

**The fix reached the rendered clip.** The v030q plan, the render job and the file agree:
`Knight_BackpedalGuard_v5c.glb` with the 0.525 s cycle shift. Its bone-space side-view legs seam is 2.91 cm against
an in-cycle mean of 3.14 cm.

**The critic's own seam method** (shift-compensated MAD on the knight crop, bands), now `measure_round4.seam_lossless`,
gives (seam / mean of all in-cycle steps):

| clip | lossless render PNGs (front / side / 3/4) | review MP4 (round 3) | same PNGs, default GOP | same PNGs, all-intra crf 12 |
| --- | --- | --- | --- | --- |
| BackpedalGuard | **1.00 / 0.99 / 0.97** (legs seam <= mean) | 1.42 / 1.49 / 1.40 | 1.42 / 1.48 / 1.41 | 1.09 / 1.09 / 1.08 |
| BackpedalGuardTwoHand | 0.95 / 0.98 / 0.94 | | | |
| StrafeRight | **0.75 / 0.90 / 0.79** | 1.11 / 1.30 / 1.08 | | 0.84 / 0.98 / 0.87 |
| StrafeRightTwoHand | 0.68 / 0.77 / 0.75 | | | |
| StrafeLeft (protected, never changed) | 0.63 / 0.70 / 0.58 | 1.03 / 1.10 / 0.95 | | |

**What causes the excess.** Re-encoding the same PNGs with the page's default libx264 GOP reproduces the critic's
numbers to within 0.01. The wrap step compares the last frame, a P-frame far from a keyframe, with frame 0, which is
an I-frame. The quality jump counts as motion. Even the protected, untouched StrafeLeft gets about 0.4x of excess.

**Change.**
- No re-author. StrafeRight(2H) and both backpedals stay the v030q files, and `measure_round4` checks that their
  sha is identical.
- Every round-4 page video is encoded all-intra (`--intra`: `-g 1 -bf 0`, crf 12).
- The round-3 BEFOREs and the unchanged rows are re-encoded the same way from their lossless PNGs
  (`--frames-also .../r3/frames`, no re-render). The critic therefore compares like with like.
- `measure_round4` reports both `seamLossless` and `seamPixelsIntra`.

If the critic still sees a wrap snap on the all-intra videos, the next step is a bone-space seam re-author. The current
numbers do not justify one.

## 4. Roll attack: hips moving over the last 3 frames, a 12 cm hip jump at f23, a skate at f18-22

**World-space measurement** (pose plus the plan's root track, game cm per rendered frame at rate 1.282) on v030q:
- Speeds at f21-26: 15.0, 14.8, 13.7, **4.3, 0.8**, 1.1. The root prefix ends at clip 1.0 s (rendered f23) and the
  body stops within two frames.
- The in-place renders follow the hips without moving the floor with the root. As a result:
  - during the roll (f18-22) planted feet seem to skate
  - the stop reads as a 12 cm jump
- Last 3 frames: **4.45, 4.18, 2.14** (critic: ~4).
- World contact slide inside contacts:
  - Left: 2.0 and 4.1 cm/frame.
  - Right: 4.8 and 4.2 cm/frame.
- The toe joints sink to -0.15 / 0.49 cm. The idle's toe is at 3.3 cm.

**Changes (`rollattack` stage; tunables in `r4_core`):**
- (a) Over 1.00-1.17 s (`JOIN_DECEL_S`, 4 rendered frames) the world hips velocity is re-integrated so that it
  smoothly blends into the slash's own velocity. The offset is carried to the outro.
- (b) The outro starts at 1.62 s, which is after the damage window [1.36, 1.576]; the windows are unchanged.
  - The hips follow a Hermite path to the final position.
  - They are at rest at 2.07 s and held for the last 0.13 s (about 3 frames).
  - The blend target is the animated idle.
- (c) From 0.62 s to 1.62 s every detected contact (local floor, speed < 100 cm/s) is locked horizontally in world
  space. Heel and toe roll are kept. Swings between contacts get >= 5 cm of lift.
- (d) The two recovery steps run 1.62-2.01 s and finish before the settle.
- (e) Feet are pitched so that the toe joint stays >= 3.3 cm.

**Prediction** (`measure_round4.py predict`, the same math on the v030q paths):
- Join speeds f22-26: 13.7, **10.8, 5.4, 1.2**, 0.6. The largest drop per frame falls from 9.4 to 5.4.
- Last 4 frames: 0.5, **0.0, 0.0, 0.0**.
- Slide inside the cleaned contacts: 0.0. The pre-outro contacts are Left 0.643-0.757 and 1.467-1.62 s, Right
  0.767-1.013 and 1.473-1.62 s.

**Consequence to review:** carrying the roll's momentum puts the slash **15.2 cm further toward the boss**. This is the
offset carried at the join. Gameplay reach for the damage window grows by that amount. If that is unwanted, the
fallback is to keep the ramp but blend the carried offset back to zero over the attack's wind-up.

**Measured later (`rollWorld`):** hips world speed per frame, join `maxSpeedDropPerFrame` < 6, `last3` < 1 cm,
contact slide < 1 cm/frame, min toe >= ~3.0 cm. Review: `rt-r4-RollAttack` against `rt-r3-RollAttack`; both are
rendered with the root track and the camera on the root, so the floor scrolls during the roll and stands still after
1.0 s.

## 5. Blinks: last 3 frames identical (ease-out); optional second push frame and deeper crouch

**Round 3, bone-space measurement:**
- The last rendered steps are 0.08, 0.00, 0.00 cm mean joint motion. Round 3 held the static idle from 0.62 s.
- The animated idle itself moves 0.07-0.15 cm per frame.
- On the lossless PNGs the last steps change 23 and 0 pixels. The idle's own steps change 167-380 pixels.

**Change:**
- The cycles stage pins frame 0 to the exact idle.
- From 0.50 s to 0.70 s it blends (smootherstep) into the **animated** idle, timed so that it reaches idle frame 0
  exactly at the clip end. Weights on rendered frames 13-18: 0, .08, .35, .70, .95, 1.0. There is no frozen hold, and
  the idle's own motion continues across the switch.
- New keys (`r4_core.BLINK_KEYS_R4`, rate 1.15, 19 rendered frames):
  - Crouch bottom at 0.115 s (rendered f3, 3 descent frames).
  - **Two visible push frames**, f4 and f5. Lean goes 6.5 -> 18.8 deg and the hips shift 2.1 -> 11.1 cm toward
    travel, before the hidden window at 0.207 s (f6-f10).
  - Gain 0.60 -> 0.75 for a deeper crouch (r3 launch depth -15.0 cm).
  - The landing arrives shallow (f11) and compresses to the full squat by 0.46 s (f12), then rises to idle by 0.66 s.
- `build_round4.py --dry` prints this timeline and checks push >= 2 and descent >= 3.

**Measured later:**
- `blinkTail.frozenTrailingSteps` = 0 (bone) and `blinkTailPng.frozenTrailingSteps` = 0.
- `lastVsIdleFrame0Cm` ~0.
- `blinkCrouch.launchDepthCm` deeper than -15.0.
- Review rows `r4-Blink*`, `top-r4-Blink*`, and `rt-r4-Blink*` against `rt-r3-Blink*`.

## Protected and kept files

- `measure_round4` re-hashes the 30 protected files against `data/round3-protected-sha256-before.txt`
  (`byteIdenticalAll`).
- It also checks that the v030r plan's StrafeRight(2H) and backpedal sha equal v030q and the file on disk
  (`keptRound3IdenticalAll`).
- The protected clips are never inputs to any stage.
- The CPU check (2026-10-29) gives `byteIdenticalAll: true`.

## GPU phase: exact commands, in order (only after the orchestrator says "GPU is yours")

```
cd /Users/midir/veyr-knight-20261028
~/.cache/gpu-slot/bin/gpu_slot.sh status                      # a free capture slot, no PAUSED, no manual STREAMING
tools/art/knight_complete/author_round4.sh                    # authoring, about 5 Blender stages, each via gpu_slot capture
tools/art/knight_complete/render_round4.sh                    # review renders via gpu_slot, all-intra page, metrics
```

`author_round4.sh` runs these steps (logs in `Local/knight-review-20261028/r4/logs/`):
```
python3 tools/art/knight_complete/build_round4.py --dry
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-bodies --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/build_round4.py -- bodies
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-fit    --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/build_round4.py -- fit
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-cycles --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/build_round4.py -- cycles
python3 tools/art/knight_complete/measure_round4.py retime-args          # prints Knight_StrafeRun*_v6r=NOMINAL@SPEED x4
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-retime --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/build_round4.py -- retime <the 4 args>
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-rollattack --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/build_round4.py -- rollattack
python3 tools/art/knight_complete/prepare_round4_plan.py --check
python3 tools/art/knight_complete/prepare_round4_plan.py               # writes v030r plan + manifest; NOT activated
```

`render_round4.sh` runs these steps:
```
python3 tools/art/knight_complete/review_jobs_r4.py Local/knight-review-20261028/r4          # 31 jobs
~/.cache/gpu-slot/bin/gpu_slot.sh capture --label knight-r4-render --timeout 3600 -- blender --background --factory-startup --python tools/art/knight_complete/render_review.py -- Local/knight-review-20261028/r4/jobs.json Local/knight-review-20261028/r4
python3 tools/art/knight_complete/build_review_page.py Local/knight-review-20261028/r4 --serve ../serve-round4 --intra --frames-also Local/knight-review-20261028/r3/frames
python3 tools/art/knight_complete/measure_round4.py docs/knight-complete-20261028/data/round4-metrics.json
```

Serve the page with `python3 Local/knight-review-20261028/serve-round4/rangeserver.py Local/knight-review-20261028/serve-round4 <port>`.

Behaviour on problems:
- gpu_slot exit 75 (slot not acquired) stops the script, with no retry and no bypass.
- A sprint `GATE_FAIL` stops the chain before export. Read `Local/FabRigTesting/Exports/round4-bodies-report.json`;
  `--force` only after review.

Only after a passing critique and owner/orchestrator approval:
1. `python3 tools/art/knight_complete/prepare_round4_plan.py --activate`
2. The round-3 import commandlet, with an absolute `-script` path:
   `"/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" /Users/midir/veyr-knight-20261028/Unreal/Veyr/Veyr.uproject -run=pythonscript -script=/Users/midir/veyr-knight-20261028/tools/art/knight_complete/native_import_v030k.py -nullrhi -unattended -NoZenAutoLaunch -notraceserver`.
   It is an Unreal process and goes through the slot protocol.
