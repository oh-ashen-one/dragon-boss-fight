# Veyr knight animation, round 3: blind critique

Date: 2026-10-29. Critic: Opus 5.5, working blind. I did not read HANDOFF.md, plan-round3.md, round3-metrics.json or any builder notes. Evidence is limited to the MP4s in `serve-round3/media/`, with `serve-round3/index.html` used only for clip names. Captions are treated as claims, not evidence.

**Verdict: NOT SHIPPABLE (Blender set; engine blend proof pending).**

The main blocker is the sprint strafes. All four still run with the pelvis about 80° off the boss, which is the same as round 2. The backpedal loop seams are also unchanged. The blinks, the sprint-strafe seams and the roll-attack exit are now fixed.

## Method

- **Frames.** I decoded all 46 videos frame by frame. They are 1080x360 at 30 fps, with three 360 px panels: front, side and three-quarter. Scratch evidence is in `/private/tmp/claude-501/-Users-midir/1e99ac11-5966-4ca4-8ec7-273fc683df51/scratchpad/critic-r3/` (`f/<clip>/NNN.png`, `sheets/*.png`).
- **Scale.** In the root-travel (rt) clips, the floor moves at the stated root speed. StrafeLeft at 196 cm/s moves the floor 4.42 px per frame, so 1 px is about 1.48 game cm.
- **Loop seams.** For each loop I compared the last-to-first frame step with the in-cycle steps:
  - Mean absolute difference on a knight crop, shift-compensated with a best integer shift of ±6 px to cancel camera follow.
  - Split into head/chest (top 40%), hips/sword (40-65%) and legs (bottom 35%) bands.
  - Round-3 loops are sampled at even phases, so the wrap should be an ordinary step.
  - Reference: the protected StrafeLeft scores seam/mean of 1.02, 1.10 and 0.95 (front, side, three-quarter). StrafeLeftTwoHand scores 1.00, 1.13 and 0.95. I therefore treat ≤1.15× mean, with no band above its in-cycle maximum, as clean.
- **Foot lock.**
  - In the rt clips, I removed the constant floor velocity and segmented sabaton highlights in the ground band.
  - I then tracked each foot's world-x during contact.
  - For the roll attack, the floor shift was found per frame by brute-force matching on a strip with no knight in it.
- **Waist twist.** There is no top view. To estimate pelvis yaw, I used the apparent horizontal span of the kicked shin at the full-kick frame, measured in all three views. The shin bends in the leg's sagittal plane.
  - If the leg plane is at angle φ to the front image plane, the front span scales as cos φ and the side span as sin φ.
  - I estimated chest yaw from the shoulder-band silhouette widths, front vs side, against the idle pose.
  - Both estimates are ±10-15°.

## Per-item results

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Blink L/R, 1H and 2H | **PASS** | See the blink notes below. |
| 2a | Sword stays in hand (Blender renders) | **PASS, renders only** | Close crops show the handle in the fist, with no gap or detachment, in every frame I checked: BlinkLeft f0/4/8/12/18, StrafeRunRight f0-f12, RollAttack f34-f51, BackpedalGuard f0/f10. Knuckle-level penetration cannot be judged at 360 px. |
| 2b | Foot lock at in-game root speed (Blender renders) | **PASS, renders only** | See the foot-lock notes below. |
| 2c | Engine blend proof (sword socket during blends) | **UNPROVEN, so it fails** | Not part of this set. No engine blend video was provided. |
| 3 | Sprint-strafe twist ≤45°, crossover legs, animated free arm | **FAIL** | Twist is unchanged from r2; the free arm is fixed. See the twist notes below. |
| 3b | Blink twist | **PASS (n/a)** | The blinks are no longer sprint cycles. Chest and pelvis stay on the idle facing in every frame. |
| 4 | StrafeRight seam | **FAIL (marginal), improved** | See the seam table below. |
| 5 | StrafeRightTwoHand seam | **FAIL (marginal), improved** | See the seam table below. |
| 6 | StrafeRunRight / StrafeRunRightTwoHand seams | **PASS** | See the seam table below. Also fixed on StrafeRunLeft (0.83/0.80/0.78) and StrafeRunLeftTwoHand (0.80/0.85/0.78). |
| 7 | BackpedalGuard / BackpedalGuardTwoHand seams | **FAIL, not fixed** | See the seam table below. |
| 7b | BackpedalGuard 1H guard height | **PASS** | Front view, all 22 frames: the grip is at chest height and the blade angles out to screen-left of the helmet, so the visor stays visible. In r2 the blade flat covered the whole helmet. 2H is similar, and the blade only grazes the helmet edge at f9-f15. |
| 8 | RollAttack exit into idle | **PASS on the requested fixes; residual drift** | See the roll-attack notes below. |
| — | Regressions vs r2, new artifacts | **None found that veto** | No mesh tearing, weapon detachment or foot below floor in the sheets checked (front/side/three-quarter on blinks, sprints, backpedals, roll). No speed halving: sprint cadence is 17 frames per cycle (r2: 19), and stance-foot positions advance about 100 px per step, which matches 499 cm/s. One small change in the roll join: see the roll-attack notes. |
| — | Protected clips unchanged | **Partly unverifiable** | r3-StrafeLeft and StrafeLeftTwoHand show the same gait as r2, phase-shifted by the new sampling. Byte identity cannot be proven from video, since the mesh variant and sampling differ. **The eight staggers are not in the round-3 set, so their unchanged status cannot be checked.** |

### Item 1: Blink

- **Launch crouch.** In rt-r3-BlinkLeft (fixed camera, front panel), the head top goes 108 → 108 → 110 → 116 → 118 px over f9-f13. That is a three-frame descent of about 10 px, roughly 15 game cm.
- **Push.** f14 is the only visible push frame before the knight vanishes.
- **Vanish window.** The knight is gone f15-f19, five frames or 0.17 s, with 0 changed pixels.
- **Reappear and settle.** The knight reappears at f20 already crouched (head 114) and rises to idle height by f23 (105, versus the idle's 105 at the new spot).
- **First and last frames.** In-place r3 first vs last frame differs by 0.86-0.94 MAD across the three panels in all four blinks. That is within the ≤1.0 compression-noise target. r2 was 1.37-2.35.
- **Sliding.** The feet do not slide on visible frames:
  - Launch: right sabaton edge stays at x = 115 from f0 to f14.
  - Landing: feet stay at world x 241-296 from f20 to f39.
  - The root moves only while the knight is hidden.
- Defects are listed under remaining fixes 5 and 6.

### Item 2b: Foot lock

Stance-foot world-x drift during contact, from the rt clips:

- **StrafeLeft (protected):** ±1 px. Stances at 192-209 (f0-f14), 272-289 (f11-f22), 319-336 (f27-f43), 399-416 (f39-f50).
- **StrafeRight:** ±1 px. Stances at 158-175 (f0-f12) and 72-91 (f10-f20).
- **StrafeRunLeft:**
  - Stances at 218-219 (f1-f6), 318-326 (f10-f16), 524-531 (f28-f34): ±4 px or better.
  - One toe-off drift: 419 to 424 over f22-f25 (+5 px, about 7 cm).
- **StrafeRunRight:** ±4 px. Stances at 125-133 (f4-f8), 27-30 (f10-f15), -79 to -72 (f21-f24), -171 to -168 (f27-f32).
- **BackpedalGuard (side view):** ±2 px. Stances at 139-163 (f11-f25) and 94-118 (f33-f41).
- **2H variants:** matching numbers.

### Item 3: Sprint-strafe twist

The waist twist is **unchanged from r2**:

- **Leg plane.** StrafeRunLeft f10, kicked shin horizontal span:
  - r3: front about 35 px, side about 6 px, three-quarter about 30 px. That puts the leg plane about 10° from the front image plane.
  - r2: about 35 px front, small in the side view.
  - At f2 the stride plane reads 12-20° in r3. The stance feet in the side view separate by only 17-27 px against 73-93 px in the front view.
- **Implied pelvis.** About 70-80° off the boss in both rounds, not the 45° the caption claims.
- **Chest.** Shoulder-band widths give 13-16° mean chest yaw in both rounds (r3 StrafeRunLeft 15.6°, StrafeRunRight 13.1°).
- **Apparent twist.** About 55-65°, against the 45° cap.

The **free arm is fixed**. In r3 StrafeRunLeft and StrafeRunRight (front-view arm crops f0-f16), the left fist tucks at f0-f3, swings out and down at f5-f11 and returns at f13-f16. In r2 it hangs in the same place in all 19 frames. The swing amplitude is modest, about 10-15 px by eye.

### Items 4-7: Loop seams

Whole-knight seam step against the in-cycle mean and maximum. Ratios are seam/mean, with values given as front / side / three-quarter.

| Clip | r3 seam (mean, max) | r3 ratio | r2 ratio | Verdict and band detail |
|---|---|---|---|---|
| StrafeRight | F 1.81 (1.62, 2.17)<br>S 1.85 (1.43, 2.01)<br>Q 1.89 (1.75, 2.16) | 1.12 / **1.29** / 1.08 | 1.59 / 1.62 / 1.56 | **FAIL (marginal), improved.** In r2 the seam exceeded the in-cycle max in every view. Now it is within the max, but still 1.29× mean in the side view. Side-view bands: hips/sword 3.41 vs mean 2.60; legs 1.77 vs mean 1.29. |
| StrafeRightTwoHand | F 1.28 (1.25, 1.76)<br>S 1.18 (0.99, 1.37)<br>Q 1.19 (1.12, 1.46) | 1.02 / **1.19** / 1.06 | 1.52 / 1.49 / 1.52 | **FAIL (marginal), improved.** Side-view legs band 1.89 vs mean 1.33 (1.42×). |
| StrafeRunRight | 1.93 / 1.74 / 1.93 | 0.80 / 0.81 / 0.85 | 1.25 / 1.41 / 1.35 | **PASS.** In r2 the seam exceeded the max in all views. No band exceeds its max in r3. |
| StrafeRunRightTwoHand | 1.55 / 1.03 / 1.31 | 0.81 / 0.73 / 0.86 | — | **PASS.** |
| BackpedalGuard | F 1.39 (0.98, 1.45)<br>S 1.41 (0.94, 1.38)<br>Q 1.14 (0.82, 1.17) | **1.42 / 1.50 / 1.39** | 1.48 / 1.42 / 1.43 | **FAIL, not fixed.** The side view exceeds the in-cycle max. The legs band exceeds its max in all three views: 1.24 vs 1.14, 1.73 vs 1.36, 1.24 vs 1.14. |
| BackpedalGuardTwoHand | F 1.24 (0.95, 1.43)<br>S 1.24 (0.86, 1.26)<br>Q 1.17 (0.86, 1.31) | **1.31 / 1.44 / 1.36** | — | **FAIL, not fixed.** The legs band exceeds its max in all three views: 1.19 vs 1.11, 1.66 vs 1.32, 1.29 vs 1.22. |

- **Camera check.** Floor shift at the backpedal wrap is -0.3, 0.0 and -0.3 px (front, side, three-quarter), the same as an ordinary step. The excess is therefore pose, not camera.
- **Caption.** The caption says "loop seam re-keyed", but the backpedal numbers are effectively the r2 numbers.

### Item 8: Roll-attack exit

What is fixed, from the floor-stabilised side view:

- **Blade.** It goes from the slash (f34, horizontal) to low-forward (f42) to the horizontal carry (f44-f51), with no second wind-up. In r2 the blade climbed to about 60° at f44-f46.
- **Front foot.** Planted at world x 229-243 from f30 to f41. It then takes a lifted step back over f42-f46: the sole rises 4-9 px (about 6-13 cm) and the foot travels about 50 px over 5 frames. In r2 this was a one-frame snap of about 40 cm.
- **Rear foot.** Locked at 154-178 from f35 to f45. It then takes a lifted step over f47-f49: the sole rises about 7-9 px and the foot moves 15-20 px forward. It lands at f50-f51 under the hips. In r2 this was a 25 cm glide with 7 cm of lift.

The residual drift is listed under remaining fix 4.

## Remaining fixes, most visible first

1. **StrafeRunLeft, StrafeRunRight and both 2H variants: the pelvis still runs about 80° off the boss.**
   - The leg/knee plane is about 10° from the front image plane: StrafeRunLeft f10 kicked-shin span is 35 px front against 6 px side.
   - With the chest at about 15°, the apparent twist is about 65°, the same as r2.
   - The caption's "pelvis 45°, twist ≤38°" is not visible in the render.
   - **Testable target:** at the full-kick frame, the kicked shin's horizontal span in the side view should be at least 0.6× its span in the front view. That corresponds to a leg plane of at least 30-45°. Currently the ratio is 0.17.
2. **BackpedalGuard and BackpedalGuardTwoHand: the loop seam is unchanged from r2.**
   - The legs band at the wrap exceeds its in-cycle maximum in all three views.
   - Worst case is the side view: 1.73 vs 1.36 (1H) and 1.66 vs 1.32 (2H).
   - The whole-knight seam is 1.3-1.5× the in-cycle mean.
   - **Target:** re-key the leg channels at the cycle ends so that the seam is at most 1.15× the mean in every view and no band exceeds its maximum.
3. **StrafeRight and StrafeRightTwoHand: the seam is improved but still above the protected left clip.**
   - Side-view ratio is 1.29× (1H) and 1.19× (2H), against 1.10 and 1.13 on the protected left clips.
   - The side-view legs band is 1.37× (1H) and 1.42× (2H) the in-cycle mean.
   - **Target:** at most 1.15× in every view.
4. **RollAttack exit and join.**
   - **End velocity:** the hips are still travelling backward at 3 px (about 4 game cm) per frame through the last three frames (floor shift f48-f51 is 3, 3, 3). The clip ends without settling, so the transition into idle will stop dead. Ease the root and hips to zero over at least 3 frames before the end.
   - **f23 join:** the hips jump 8 px (about 12 cm) in one frame, while r2 spread the same jump over two frames (6 + 3). The caption says the join was unchanged.
   - **Get-up, f18-f22 (unchanged from r2):** the root is static while a low foot (sole 262-265) moves from world x 210 to 163, about 47 px. This reads as a skate; foot depth makes it ambiguous from this render alone. The roll's root travel is still unproven, as in r2.
5. **Blink end hold.**
   - The last three frames of every blink are identical (in-place steps 0.01, 0.01). The step before that is 0.97, so motion stops dead with no ease-out.
   - In the rt version this shows as a 0.13 s freeze (f25-f28) before idle resumes.
   - The idle restart step at f28→f29 is 361 changed px in BlinkLeftTwoHand (front view), against idle steps of 20-100.
   - **Fix:** ease out the last 3 frames instead of holding.
6. **Blink read.** These are notes, not vetoes.
   - Only one visible push frame (rt f14) sits between the crouch bottom and the vanish.
   - The crouch dips about 15 game cm and the landing arrives already crouched, so there is no impact compression.
   - Without VFX this reads as a small hop-and-vanish. Consider a two-frame lean and push toward the travel direction.
7. **Engine proof, carried over from r2 and still failed.**
   - Render the actual engine blends with the sword visible: idle to strafe, strafe to idle, idle 2H to blink 2H, blink to idle, roll end to idle.
   - The Blender renders do show good foot lock, but they cannot show socket behaviour during blends.
8. **Staggers (carried over from r2, design).** All eight are locked-feet flinches. A foot-recovery step is needed if they double as heavy staggers. They were not re-rendered in r3, so their unchanged status is unverified.

## Not judgeable from these renders

- **Engine side.** I cannot judge:
  - sword-socket behaviour during engine blends;
  - in-engine blend pops, including the 0.10 s blink blends;
  - whether root motion is extracted correctly in engine.
- **Byte identity.** Whether StrafeLeft, StrafeLeftTwoHand and the eight staggers are byte-identical. The staggers are absent from the set, and the two left strafes were re-rendered with a different mesh variant and sampling.
- **Fine contact.** Knuckle-level grip penetration, at 360 px per panel.
- **Roll get-up.** Whether the f18-f22 foot is skating or slightly lifted. The side camera gives no depth separation between near and far feet.
- **Pelvis yaw.** Accurate to ±10-15° only, since there is no top view. The conclusion (well above 45°) holds across both frames measured, f2 and f10.
- **Blink VFX.** Not rendered, so the vanish read cannot be judged.
