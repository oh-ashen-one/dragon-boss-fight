# Blendproof planted-foot gate: diagnosis (2026-10-30)

Run diagnosed: `Evidence/native-blendproof-20261030T025205Z/unreal-blendproof-20261030T025228Z-4B0AB676/`
(v030q package, grip lock on). Result was 0/9, every failure `planted_foot_slide_<N>cm_per_frame`. The sword gate
passed everywhere and is not changed. Method: CPU-only reading of `VeyrBlendProof.cpp`, `VeyrKnight.cpp`
(`UpdateImportedPresentation`, `LockOnSpeedCap`, `ApplyAuthoredRootMotion`), `VeyrSingleNodeInstance.cpp`, the
v030q import plan, `blendproof-frames.jsonl` (1380 rows) and the native PNGs. No engine, Blender or GPU was used.
Offline re-scorer: `tools/unreal/blendproof_footgate_rescore.py <run dir> [limit]`.

## 1. What the old gate measured

* **Planted** was decided from height alone, per bone. A toe was planted when its height was at most the
  sequence's idle-stance toe height + 2.5 cm, and an ankle when it was at most the idle ankle height + 2.5 cm. No
  velocity, no per-clip reference, and toe and ankle were judged separately.
* **Slide** was the world-space planar distance (`FVector::Dist2D`) the bone moved between two consecutive samples,
  counted when the bone was planted in both. The unit was cm per frame, with no dt normalisation. The limit was 2 cm per frame.
* **Sampling** has no timing skew. `AVeyrReplay` ticks in `TG_PostPhysics`, after the knight's tick (which runs
  `UpdateImportedPresentation`, an explicit synchronous pose) and after CharacterMovement. Capsule and bones come from
  the same tick. Within a sequence there are no teleports or home resets: setup walks the knight to its start by
  input and is not sampled. The only capsule jumps are the blink carries, and those were already exempt while hidden.
* **Frame-rate dependence.** The run mostly ran at 60 fps (median dt 0.017 s in sequences 1-4 and 0.024-0.034 s in
  sequences 5-9). The dt 0.09-0.124 s frames are capture stalls, and they land on captured video frames. Example: the
  StrafeLeft hitch at t = 3.472 is native frame 43. So a 2 cm/frame limit meant 120 cm/s on normal frames and
  16-20 cm/s on hitch frames, about 6-7x stricter exactly where the video looks. Several legacy "worst" values are hitch
  frames: 35.28 (dt 0.100), 49.66 (dt 0.098), 20.89 (dt 0.092), 43.36 (dt 0.107), 130.83 (dt 0.124).

### Gate defect: low swing feet counted as planted

In steady strafes the swing foot shuffles with its toe 1-2 cm off the floor and its heel up. The gate counted it as
planted. Two reasons:
* The strafe stance is lower than idle. Stance ankle is 13.8-14.0 cm against an idle 18.2 cm. Stance toe is -1.1 cm
  (R) and -4.6 cm (L) against an idle 4.6 cm.
* Toe and ankle were judged separately.

Example, StrafeLeft t = 3.54-3.61 (rows 86-90, all dt 1/60):

| foot | toe height | ankle height | world travel per frame | speed |
| --- | --- | --- | --- | --- |
| R (stance) | about -1 cm | about 14 cm | 0.04-0.33 cm | 2-20 cm/s |
| L (swing) | 1.2-4.7 cm | 19.4-25.1 cm | 13.0-14.0 cm | about 800 cm/s |

The stance foot is locked. The swing foot was scored as "planted slide" on every step. This produced 124 of
StrafeLeft's over-limit frames.

## 2. True foot motion, reconstructed from the jsonl

### Steady locomotion (no blend): the clips do not slide

Planted means toe and ankle both low against a per-clip reference. "Drift along travel" is the planted foot's
velocity component in the capsule's travel direction. If the nominal speed did not match the capsule speed, this
would read a large fraction of the capsule speed.

| clip | capsule | planted-foot speed median / p90 | drift along travel |
| --- | --- | --- | --- |
| StrafeLeft | 196 cm/s | 16.9 / 27.7 cm/s | +6.3 cm/s (3 %) |
| StrafeRightTwoHand | 191 cm/s | 13.7 / 19.9 cm/s | +0.9 cm/s (0 %) |
| BackpedalGuard | 100 cm/s | 1.9 / 8.8 cm/s | -1.6 cm/s (2 %) |
| StrafeRunLeft | 499 cm/s | 49 / 115 cm/s | -6.3 cm/s (1 %) |
| StrafeRunRight | 503 cm/s | 69 / 96 cm/s | -51 cm/s (only 4 pairs) |

`PresentationLocomotionTime` advances by speed / nominal, and `LockOnSpeedCap` keeps the capsule at or below
1.2x (walk) or 1.1x (run) of nominal. That holds the stance foot still. **The `nominal_speed_cm_per_second` values in
the import plan are right; nothing needs changing there.** The leftovers are contact onset and push-off slips:
* walk strafes: windowed maxima 67-92 cm/s, about 1.5 cm per frame for 2 frames at heel strike
* runs: 140 cm/s toe slip at push-off, 2.2 cm per frame for about 5 frames

### Where the planted foot really skates

These numbers are dt-normalised, toe and ankle both planted, over a window of at least 1/30 s.

| sequence | true worst slide | what happens | real? |
| --- | --- | --- | --- |
| StrafeLeft_1H | 544 cm/s, start blend | Idle to StrafeLeft crossfade, 0.30 s (`LockOnBlendSeconds`). The capsule reaches 196 cm/s in 4 frames. The source pose is a frozen Idle snapshot (`CaptureTransitionSource`), so its feet ride with the capsule, while the strafe clip's swing is mixed in at reduced lift. The R foot sweeps about 70 cm at 1-5 cm height over 0.13 s. The stop blend (StrafeLeft to Idle, capsule already at 0 cm/s) lands the L foot from 13 cm while it glides about 45 cm at up to 300 cm/s, and the R stance foot slides about 1 cm per frame (60 cm/s) into the idle stance. | yes: transition |
| StrafeRunLeft_1H | 1204 cm/s, stop | Releasing sprint downshifts StrafeRunLeft to StrafeLeft with a 0.10 s blend while the capsule brakes 499 to 102 cm/s in 3 frames. The normalised-phase remap puts the walk's feet in a different place. The L foot moves 21, 19 and 17 cm on consecutive 1/60 s frames, and its toe goes 9.8 cm under the floor. | yes: transition |
| BlinkLeft_1H | 126 cm/s | At action time 0.38-0.40 s, after the knight reappears, the L foot dips 6 cm into the floor (toe -3.1 cm, ankle 10.7 cm against idle 17 cm) and shifts 4.2 cm over 2 frames. The legacy worst (3.14 cm at dt 0.101, post-idle) is only 31 cm/s. Separately, on the first visible frame (0.35 s) the capsule still carries 1.83 cm; that pair is exempt because it touches the hidden window. | yes, small |
| StrafeRight_2H | 611 cm/s, start blend | Same start-crossfade sweep with the L foot. The legacy 49.66 cm is the same event at a 0.098 s hitch (507 cm/s). The stop blend reaches 187 cm/s. | yes: transition |
| BlinkRight_2H | 47 cm/s | Post-idle settle | no (passes) |
| RollAttack_1H | 1058 cm/s, 1st Roll frame | The first Roll tick renders blend alpha 0, which is still the frozen Idle pose. The authored root carry has already moved the capsule 130 cm in that 0.124 s hitch (about 17 cm at 60 fps). Separately, in the slash (action time 0.91-1.19 s, capsule stationary, root path constant after source 1.08 s) the L foot moves +58 cm along the roll direction with its toe at 0.6-3.4 cm and ankle at about 16 cm, and the R foot moves -27 cm: 160-290 cm/s. That motion is in the sourced `Sourced_RollAttack_v5` clip itself. | yes: 1-frame transition pop + clip slide |
| BackpedalGuard_1H | 157 cm/s, start blend | Idle to BackpedalGuard crossfade. Steady stance is only 31 cm/s. | yes, mild |
| StrafeRunRight_1H | 406 cm/s, stop | Releasing at 503 cm/s with both feet airborne (toe 12-15 cm). The capsule stops in about 0.1 s, then the StrafeRight (1 frame) to Idle crossfade brings both feet down while they travel 35-46 cm per 0.1 s, about 110 cm in total. | yes: transition |
| BlinkRight_1H | 54 cm/s | Post-idle settle | no (passes) |

Two questions from the brief, answered:
* *Does Idle play while the capsule is still moving?* No. Idle is selected only at 8 cm/s or below, and the data show
  0.00 cm capsule travel on every Idle-start frame. The capsule brakes from full speed to 0 in 0.05-0.1 s. The stop
  crossfade, not the capsule, then moves the feet.
* *Does the gate measure something else?* Partly. Of the problems listed in the brief, the low-swing-foot false
  positive and the missing dt normalisation are real gate defects. There are no time-skewed samples, no teleports
  and no home resets. The blink hidden-window exemption already worked.

## 3. What a human sees

The capture is 12.8 fps (`achievedCaptureFPS`), so a 0.13-0.3 s glide is only 2-4 video frames. Two of them were
checked against the 25 cm proof checker:
* **StrafeLeft stop** (native frames 73-76, `native-video/frame-000073.png` to `frame-000076.png` in the run folder): the stance changes from
  mid-stride to the idle stance between frames 74 and 75 while the capsule is stopped. The near foot moves about one
  checker cell with no visible lift. A viewer would read this as the feet gliding into idle.
* **StrafeLeft start** (frames 41-44): the legs cross with low foot clearance. At this capture rate it reads as a
  shuffle step, not a clear skate.

Steady strafe frames (for example frame 56) show a locked stance foot. Only the 4 frames listed above were
inspected; the roll and run-stop frames were not. Judge them from the numbers until a 60 fps capture exists.

## 4. Gate patch (on this branch, edit only, not built)

Changed files:
* `Unreal/Veyr/Source/Veyr/VeyrBlendProof.cpp`, `.h`: the gate.
* `tools/unreal/blendproof_encode.py`: the overlay shows cm/s.
* `docs/knight-complete-20261028/blendproof.md`: the gate description.

A `-fsyntax-only` compile of `VeyrBlendProof.cpp` with both the Shipping and Editor-Development UBT response files
reported 0 errors and 0 warnings.

* **Contact reference.** Per (clip, foot, bone): the 10th percentile of that clip's unblended heights in the
  sequence, never above idle. While blending, the looser of the source and target references is used. A clip with
  fewer than 5 unblended frames uses idle.
* **Planted.** Toe AND ankle within 2.5 cm of that reference, in both frames of a pair.
* **Slide.** max(toe, ankle) world planar travel ÷ game time, summed over a contiguous planted window of at least
  1/30 s. The result is in cm/s and does not depend on the frame rate.
* **Exclusions.** Pairs touching the blink hidden window, zero-dt pairs, invalid samples, and capsule speed above
  2500 cm/s (teleport or reset). Any of these breaks the window.
* **Limit.** **60 cm/s**, which is 2 cm per 1/30 s source frame (the old "2 cm" intent at the clips' own rate).
* **Reporting.**
  * Fail reason: `planted_foot_slide_<N>cm_per_s_<steady|transition>`.
  * `feet` gains `maxSteadySlideCmPerSecond`, `maxTransitionSlideCmPerSecond` and `teleportPairsExcluded`.
  * Per-frame rows gain `footPlanted` and `footSlideCmPerSecond`.
  * Roll phases report cm/s.
  * The old figure is kept as `legacy*` and is not gated.
* **Unchanged.** Sword gate, travel gates and sequence driving.

### Current data under the patched gate (60 cm/s): 2/9 pass

| # | sequence | legacy cm/frame | new max cm/s | steady | transition | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | StrafeLeft_1H | 35.28 | 544 | 92 | 544 | FAIL transition |
| 2 | StrafeRunLeft_1H | 21.47 | 1204 | 140 | 1204 | FAIL transition |
| 3 | BlinkLeft_1H | 3.14 | 126 | 126 | 60 | FAIL steady (foot dip) |
| 4 | StrafeRight_2H | 49.66 | 611 | 67 | 611 | FAIL transition |
| 5 | BlinkRight_2H | 5.36 | 47 | 3 | 47 | PASS |
| 6 | RollAttack_1H | 130.83 | 1058 | 278 | 1058 | FAIL transition (+ slash clip) |
| 7 | BackpedalGuard_1H | 12.38 | 157 | 31 | 157 | FAIL transition |
| 8 | StrafeRunRight_1H | 43.36 | 406 | 65 | 406 | FAIL transition |
| 9 | BlinkRight_1H | 3.74 | 54 | 1 | 54 | PASS |

At 150 cm/s the result is 3/9 (BlinkLeft also passes). The remaining failures are real, so the limit choice does not
change the conclusion.

## 5. Where the fixes belong (not in the gate, not in nominal speeds)

1. **Lock-on start and stop crossfades** (seq 1, 4, 7 start; seq 1, 2, 8 stop). These are blends from a frozen pose
   while the capsule accelerates or brakes in 0.05-0.1 s. Options, in engine:
   * foot-phase-matched entry, starting the loop at the phase where the leading foot is planted
   * stance-foot IK or foot lock during `bTransitionLockOnEdge` blends
   * a strafe stop clip or a softer braking deceleration so the feet are not already mid-air when the stop blend begins
2. **Run-to-walk downshift on sprint release** (seq 2). Sync the normalised phase by foot contacts rather than by
   duration, or blend run to idle directly when the input is neutral.
3. **Roll first frame** (seq 6). The transition's first rendered frame has alpha 0 while the root carry has already
   moved the capsule. Either start alpha at dt/BlendSeconds or delay the authored root carry by one tick.
4. **RollAttack slash** (seq 6). The feet slide 58 cm and 27 cm in the sourced clip with the root fixed. Fix the
   clip in Blender with foot locks, or move the slash lunge into the root path so the carry happens there. Check the
   source clip at 30 fps first.
5. **BlinkLeft foot dip** (seq 3). A 2-frame pop at action time 0.38-0.40 s, 6 cm into the floor. Clip-side.

No clip needs a `nominal_speed_cm_per_second` or `gameplay_play_rate` change. Steady stance drift along travel is
3 % or less of capsule speed for every strafe and backpedal measured.

## 6. "Before" run (`-VeyrNoWeaponGripLock`)

Run: `Evidence/native-blendproof-20261030T030659Z/unreal-blendproof-20261030T030718Z-3BD10306/`. The setup reports
`weaponGripLockEnabled` = false. The gpu_slot release line reports `contaminated=true` (one ML GPU client was present).

**Sword.** With the grip lock off, the sword gate fails in 6 of 9 sequences, as expected:
* StrafeLeft: hand-space error 9.13 cm
* StrafeRunLeft: excess 2.61 cm, hand-space error 6.19 cm
* StrafeRight_2H: hand-space error 8.07 cm
* BackpedalGuard: excess 18.56 cm, hand-space error 38.90 cm
* StrafeRunRight: excess 9.84 cm, hand-space error 15.65 cm
* BlinkRight_2H: excess 1.95 cm, which is under the 2 cm limit

With the lock on (the run diagnosed above), every sequence was at or below 0.02 cm. The lock is what makes the sword
gate pass.

**Feet.** The foot numbers barely move without the lock. The grip-lock extra sample does not touch the frozen
transition source, so this is expected. Patched gate, 60 cm/s: **1/9 pass**.

| sequence | max cm/s, lock on | max cm/s, lock off | worst (lock off) |
| --- | --- | --- | --- |
| StrafeLeft_1H | 544 | 538 | start blend |
| StrafeRunLeft_1H | 1204 | 1140 | sprint-release downshift |
| BlinkLeft_1H | 126 | 135 | foot dip, steady |
| StrafeRight_2H | 611 | 580 | start blend |
| BlinkRight_2H | 47 | 66 | alpha-0 settle, post-idle |
| RollAttack_1H | 1058 | 243 | first Roll frame at dt 0.062 (slash steady 171) |
| BackpedalGuard_1H | 157 | 183 | start blend |
| StrafeRunRight_1H | 406 | 558 | stop |
| BlinkRight_1H | 54 | 55 | post-idle |

Steady-stance drift along travel is again 1-5 % of capsule speed (StrafeRunRight: 3 pairs only). The RollAttack
first-frame pop scales with that frame's dt: 130.8 cm in 0.124 s with the lock on, 15.2 cm in 0.062 s without it.
This confirms it is the alpha-0 frame carrying the frozen Idle pose, not a sustained slide.
