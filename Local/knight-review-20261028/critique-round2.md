# Veyr knight animation, round 2: blind critique

Date: 2026-10-29. Critic: Opus 5.5, working blind. I did not read `critique.md`, `critique-round1.md` or any handoff. Everything here comes from the r1-/r2- MP4s in `serve/media/` and the clip layout in `serve/index.html`. The page's metrics and its "simulated slip" table are the builder's own numbers, so I don't count them as evidence. Where I quote them, I say so.

## Method

- I decoded all 44 videos (1080x360, 30 fps, three 360 px panels: front, side, three-quarter). Contact strips were made at 1.0-2.5x with every frame, R2 stacked over R1. Scratch evidence is in `/private/tmp/claude-501/-Users-darkeatermidir/9556d3ac-39d0-4de9-861d-d9bd72588e42/scratchpad/kr2/` (`s2/*.png`, `z_*.png`, `sf2.png`, `stab_r2.png`).
- **Floor motion.** Phase correlation on floor patches away from the knight. For every strafe, sprint strafe and blink, in both rounds, the floor's net motion over the clip is about 0 px (it sways about 1 px with the camera following the hips). **These renders have no root translation.** World-space foot skate against the capsule therefore cannot be seen for strafes or blinks. The roll attack is the only clip with floor motion, and only from f24 onward.
- **Loop seams.** I measured the mean absolute pixel difference of the last-to-first frame step against the in-cycle frame steps, on knight-only crops, split into head/chest, hips/sword and legs/feet bands. For reference, compression noise on a static pose is about 0.8-1.0.
- **Facing.** Read by eye from the front panel (front = toward the boss).
- **Blink vs sprint.** Per-frame image difference between `r2-BlinkLeft` and `r2-StrafeRunLeft`.
- **Roll exit.** I stabilised the side view to the floor using cumulative floor shift and tracked the greave/sabaton blobs in world-x.
- Scale: the knight is about 155 px tall in the panel, so 1 px is roughly 1.2 cm.

## Round 1 findings: verification

| R1 finding | R2 status | Evidence |
|---|---|---|
| Mirrored clips flipped body facing (sprint strafe right, blinks) | **FIXED** | R1 StrafeRunRight and BlinkRight front panel: the knight is turned roughly 60-90° toward screen-left for all 17-18 frames. R2: the breastplate is square to the camera in every frame, and the sword stays in the right hand on the mirrored side. |
| Sword socket hung off root during blends | **UNPROVEN, so it fails** | No blend was rendered. The "0.0 cm after" slip table on the page is a builder simulation, not footage. Inside the clips, the sword stays attached to the hand in every frame I inspected. |
| Lock-on strafes faced away from boss | **FIXED** | R1 StrafeLeft/Right (1H and 2H) are turned roughly 45° off the boss through the whole cycle. In R2 the chest faces the camera in every frame. |
| Blink clips foot-skated | **UNPROVEN, so it fails, and the blink is now just the sprint cycle** | The floor is static in both rounds (r1 temporal floor std 0.05, r2 0.4), so the claimed "root carries 90% of foot speed" fix can't be seen. Even taken at face value, it is an admitted 10% residual skate. |
| Roll-attack exit slid | **IMPROVED-BUT-SHORT** | Details in the RollAttack section below. |

## Per-clip verdicts

### Lock-on walk strafe

- **StrafeLeft: MEETS. Beats R1.**
  - Chest stays on the boss for all 28 frames.
  - Cycle is now 28 frames, matching the right-hand clip (R1 had 32 vs 28).
  - Loop seam is clean: 1.63 vs in-cycle mean 1.51 and max 2.40.
  - Style note: a deep, hunched, bow-legged gait (wide straddle at f7-f14). The builder's own metrics say hips sit 15-26 cm below idle and the head bobs 16 cm, which is more than the 9.9 cm of the sprint.
- **StrafeRight: IMPROVED-BUT-SHORT. Beats R1.**
  - Facing is fixed.
  - Loop seam f27 to f0 is 2.43, larger than any in-cycle step (max 2.18 at f15). In the hips/sword band it is 5.49 vs a max of 4.91. The diff map shows the whole body and the blade outline shifting at the seam, with no camera jump (horizon steady to 0.01 px). Expect a small hitch once per cycle.
- **StrafeLeftTwoHand: MEETS. Beats R1.**
  - Same legs as the 1H clip.
  - Blade held near-vertical with the grip directly in front of the visor. From the front it completely hides the helmet. The side view shows a gap of a few px, so there is no proven clipping.
- **StrafeRightTwoHand: IMPROVED-BUT-SHORT. Beats R1.** Same seam hitch as StrafeRight: 2.31 vs in-cycle max 2.12.

### Lock-on sprint strafe

- **StrafeRunLeft: IMPROVED-BUT-SHORT. Beats R1.**
  - Facing is fixed, but it was done by twisting the spine about 80-90°.
    - In the front panel at f7 and f13, the legs and pelvis run in pure profile while the breastplate is square to the camera.
    - The builder's own metrics agree: knee-vs-travel 9.8° and chest yaw ±14°.
    - It reads as a torso bolted onto a turntable, well past a believable waist twist.
  - The free left arm hangs almost motionless through the whole sprint.
  - Within the render, the stance foot slides about 11 px per frame at a near-constant rate (f10-f16: -10.5, -11, -12, -11, -10, -8.5), which is consistent.
- **StrafeRunRight: IMPROVED-BUT-SHORT. Beats R1.**
  - Same twist and dead arm as StrafeRunLeft.
  - Loop seam 2.84 exceeds the in-cycle max of 2.70. The head/chest band is 3.79 against a 2.55 mean.
- **StrafeRunLeftTwoHand / StrafeRunRightTwoHand: IMPROVED-BUT-SHORT. Both beat R1.**
  - Same twist as the 1H clips.
  - The right-hand clip has a seam hitch: 2.57 vs in-cycle max 2.46.

### Blink

- **BlinkLeft: IMPROVED-BUT-SHORT on facing; foot skate UNPROVEN.**
  - Facing beats R1.
  - The body animation is literally the StrafeRunLeft cycle. Each blink frame best-matches the same-index StrafeRunLeft frame with a mean difference of 0.57-1.21, which is noise level.
  - There is no launch crouch, no burst and no landing.
  - It starts and ends mid-stride with one leg kicked back (f0 and f17). Both ends are about 3.9 away from idle, about two full frame-steps of pose change. The 0.10 s idle-to-blink and blink-to-idle blends will pop between idle and mid-sprint.
  - Ankle width at the end is 67.6 vs 61.5 at the start (builder's metrics).
- **BlinkRight: IMPROVED-BUT-SHORT; foot skate UNPROVEN.**
  - Same issues as BlinkLeft.
  - It inherits the StrafeRunRight twist.
  - First-to-last difference is 2.55, larger than any in-clip step.
- **BlinkLeftTwoHand / BlinkRightTwoHand:** new clips with no R1 2H to compare, so they can't beat R1. **IMPROVED-BUT-SHORT** relative to the 1H R1 blink, with the same defects as the 1H blinks.

### Stagger

All eight staggers are rated **MEETS** as light hit-reacts, and all **beat R1**.

- **StaggerFront (1H and 2H):**
  - Upper body snaps back (head peak f6-f9). The blade stays low: 1H pitch is 6-22° in the builder's metrics, and in my frames it stays below the waist. In R1 the blade whips up about 45° and the torso spins.
  - Feet are locked.
  - First frame equals idle. The last frame differs from the first by 1.15, which is compression-level with diffuse diff and no structure.
- **StaggerBack (1H and 2H):** forward hunch. Close to R1 but calmer.
- **StaggerLeft / StaggerRight (1H and 2H):**
  - Torso twists about 50° away from the hit side, which is directionally correct.
  - R1's blade flail is gone. In R1 StaggerRight f4-f10 the blade was thrown overhead past the helmet.
  - StaggerRight 1H f5-f9: the sword folds across the belly. No clipping is provable at this resolution.
- Design note for all staggers: the feet never move (ankles 61.9/61.9) and the root does not move. These are flinches, not poise-break staggers. That's fine if a separate heavy stagger exists.

### Lock-on backpedal

- **BackpedalGuard: IMPROVED-BUT-SHORT. Beats R1 on intent: R1 had no guard and the blade was level.**
  - The blade is raised only at the wrist, with the hand still at the hip. From the boss-facing view the flat of the blade covers the whole helmet.
  - Loop seam: every band exceeds its in-cycle max.
    - Legs: 1.32 vs 1.14.
    - Hips/sword: 1.86 vs 1.64.
    - Whole knight: 1.56 vs 1.48.
- **BackpedalGuardTwoHand: IMPROVED-BUT-SHORT. Beats R1.** Seam 1.58 vs in-cycle max 1.50, in every band.

### Roll attack

**RollAttack: IMPROVED-BUT-SHORT. Marginally beats R1.**

- **Exit.** I stabilised the side view to the floor.
  - The rear foot is planted at world-x 157 from f36 to f46. That part is good.
  - The front foot then jumps about 33 px (about 40 cm) back between f45 and f46. In one frame it reads as a snap rather than a step.
  - The rear foot then drifts +20 px (about 25 cm) from f46 to f50. Its sole rises only about 6 px (about 7 cm) at f47-f48, then it lands at f48 still travelling.
  - R1 over the same span: the rear foot drifts +25 px with the sole at ground level throughout (ybot 265-270), a pure slide.
  - R2 adds a token lift but still glides about 25 cm into the final pose.
  - The hips travel 40 px back over f41-f50 (floor shift goes from -42 to -2), so the body is pulled back onto the start spot while the feet catch up.
- **Roll.** The floor is static from f0 to f23. The dive (airborne and prone at f4, about 70 px above the floor) and the forward roll (f5-f17) happen with no translation in the render. Whether the game moves the capsule is unproven.
- **Recovery.** After the slash lands (f33-f35), the blade swings back up to about 60° (f43-f46) before dropping to the carry (f47-f50). It reads as a second wind-up, not a recovery.
- **Sword.** Stays in the hand throughout. During the roll it stays level and pointing forward (f4-f16) and doesn't follow the body's rotation, which is plausible only with an extended arm.

## Overall verdict

**Round 2 is not shippable for a playable character.**

It fixes the two most visible R1 defects: facing on mirrored clips, and strafes facing away from the boss. Staggers improved clearly. But:

- The blinks are now a relabelled sprint-strafe loop with no blink motion. They start and end mid-stride, which guarantees a pop on both blends.
- Every sprint and blink reaches "chest to boss" with an anatomically implausible 80-90° waist twist.
- The two hand-attachment and skate fixes (blend socket and blink skate) have **no visual evidence at all**. The renders strip root translation and no blend was rendered. They fail as unproven.
- The roll-attack exit still glides about 25 cm on the planted foot and snaps the lead foot about 40 cm in one frame.
- Every right-side loop and both backpedals have a measurable seam hitch.

Ship-ready subset if the owner wants a partial merge: StrafeLeft and StrafeLeftTwoHand, plus the eight staggers.

## Remaining fixes, ranked

1. **BlinkLeft/Right (1H and 2H):** these are the sprint-strafe cycle frame for frame. Author a real blink:
   - Launch crouch of at least 3 frames from the idle stance.
   - A vanish window.
   - A reappear landing that settles to idle stance width.
   - First and last frames within compression noise (≤1.0) of idle.
2. **Blend socket and blink skate:** provide visual evidence.
   - Render actual engine blends (idle to strafe, strafe to idle, idle 2H to blink 2H, blink to idle, roll end to idle) with the sword visible.
   - Render the blinks and strafes with root translation over the checker, so foot lock against the floor can be measured.
   - Until then both stay failed.
3. **StrafeRun* and Blink*:** pelvis-to-chest yaw is about 80-90° (legs in profile, breastplate frontal, front panel f7 and f13).
   - Cap the waist twist at about 45°.
   - Use a lateral or crossover sprint source for the legs.
   - Animate the free arm; it is static through the whole cycle.
4. **RollAttack exit:**
   - f45-f46: the lead foot moves about 40 cm in one frame. Make it a lifted step of at least 3 frames.
   - f46-f50: the rear foot slides about 25 cm with about 7 cm of lift. Lock it in place, or give it a full lifted step.
   - f42-f46: remove the blade's return to about 60° pitch. Recover straight from the slash to the carry.
5. **StrafeRight, StrafeRightTwoHand, StrafeRunRight, StrafeRunRightTwoHand, BlinkRight, BackpedalGuard, BackpedalGuardTwoHand:** the last-to-first step exceeds every in-cycle step (StrafeRight hips/sword band 5.49 vs max 4.91). Re-key the cycle ends so the seam step is at or below the in-cycle mean.
6. **RollAttack roll (f0-f23):** zero floor travel in the render. Confirm in engine that root motion carries the dive and roll distance and that the feet don't hover or skate.
7. **BackpedalGuard 1H:** the guard is just a wrist roll with the hand left at the hip, and the blade flat covers the whole helmet from the boss's view. Raise the hand to chest height, or angle the blade off the face line.
8. **StrafeLeft/Right walk:** deep hunched crouch, with hips 15-26 cm low and a 16 cm head bob (builder's metrics). A heavy knight's lock-on walk should bob less than its sprint, not more.
9. **Staggers:** feet are locked in all eight. Acceptable as light hit-reacts; add a foot-recovery step if these double as heavy staggers.
