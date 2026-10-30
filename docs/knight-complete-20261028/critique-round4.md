# Veyr knight, round 4 critique (2026-10-30)

**Blind critique from the videos only.** I did not read HANDOFF.md, plan-round4.md, round4-metrics.json, commit messages or any implementation notes. I did not grade code and did not launch Blender, Unreal or anything else that uses the GPU. The only evidence is the media in `Local/knight-review-20261028/serve-round4/media/`. The page captions describe the implementation; I ignored them as claims.

## Method and what was measured

- I extracted the frames with ffmpeg and read them as per-view contact sheets (native 360 px views, contrast lifted). Numbers below are pixels in the 360x360 view.
- **Scale.** In the front view at foot depth the checker runs about 15.5 to 17.8 px per 25 cm tile. The floor scroll in `rt-r4-StrafeRunRight` is +11.95 px/frame at 503 cm/s, which gives 0.71 px/cm. So 1 px is about 1.4 cm at the feet. The side view is similar (0.71 to 0.73 px/cm from the backpedal scroll).
- **Foot lock.** On the rt-* clips I tracked the sole band (the lowest 5 rows of the silhouette) and compared its screen velocity with the floor scroll, which I measured by 1-D correlation of floor rows at foot depth. A planted foot should match the floor velocity.
- **Seams.** I compared the wrap step (last frame to frame 0) with the mean in-loop step on the knight region, and checked that the sole positions stay continuous across the wrap.
- **Blinks.** On the fixed-camera rt clips I measured head height, upper-body x, sole positions and the per-step frame difference for freezes.
- **Roll attack.** On the rt clips I measured helmet world velocity (screen x plus the camera move from the floor scroll), sole edges, and the sword centroid speed in the 3/4 view.
- **Sprint-strafe yaw.** In the top views I measured the direction of the most-extended foot from the torso centre: 0 deg is straight back, away from the boss.
- **Limits of the evidence.** These limits are review-material defects in their own right:
  1. At 1080x360 the 25 cm checker aliases into moire in the front and 3/4 views, so foot slip cannot be judged by eye. It had to be measured.
  2. In the roll attack the blade leaves the frame during the strike: it is clipped at the crop edge in the 3/4 view on frames 34-37 and 40, and the side-view tip sits at the crop edge.
  3. There are no rt BEFORE clips for the sprint strafes, so round-3 foot lock on those rows is unproven.

## Scores per row

| Row | AFTER | BEFORE | Verdict |
|---|---|---|---|
| StrafeRunLeft | 7 | 4 | BETTER |
| StrafeRunLeftTwoHand | 7 | 4 | BETTER |
| StrafeRunRight | 7 | 4 | BETTER |
| StrafeRunRightTwoHand | 7 | 4 | BETTER |
| BlinkLeft | 7 | 4 | BETTER |
| BlinkLeftTwoHand | 7 | 4 | BETTER |
| BlinkRight | 7 | 4 | BETTER |
| BlinkRightTwoHand | 7 | 4 | BETTER |
| RollAttack | 5 | 4 | BETTER (still vetoes) |
| StrafeRight (unchanged) | 7 | none | NO-BEFORE |
| StrafeRightTwoHand (unchanged) | 7 | none | NO-BEFORE |
| BackpedalGuard (unchanged) | 7 | none | NO-BEFORE |
| BackpedalGuardTwoHand (unchanged) | 7 | none | NO-BEFORE |
| StrafeLeft (protected) | 7 | none | NO-BEFORE |
| StrafeLeftTwoHand (protected) | 7 | none | NO-BEFORE |

### Evidence, one sentence each

- **StrafeRunLeft.**
  - AFTER: In the top view the trailing heel now kicks back-diagonal (+45 deg at frame 5, sweeping to +13 deg at frame 11; about +30 deg at full extension, frames 7-8), and the free left arm swings forward up-left (frames 6-7). In the rt front view stance soles track the -11.9 px/frame floor to within 1.5-5.4 px over a whole stance (2-8 cm). The wrap step is 0.79x the mean step and sole x is continuous across it (213 -> 202).
  - BEFORE: The heel kick goes straight out to the knight's right (top view frames 9-12, more than 70 deg from straight back, so the detector finds no backward kick at all), which means the legs run with the pelvis about 80 deg off the boss and the free arm hangs.
- **StrafeRunLeftTwoHand.**
  - AFTER: Same lower body as the one-hand clip (kick +45 to +17 deg, frames 5-11; identical sole tracks in rt). The vertical blade stays in both fists, with 19 px of vertical bob in the front view, so the carry is not rigid.
  - BEFORE: Lateral heel kick (no backward-kick frame detected) and the same about 80 deg pelvis.
- **StrafeRunRight.**
  - AFTER: The kick is -38 deg at frame 8, settling to about -22 deg (frames 7-13), and the free arm swings toward the boss at frames 8-9. Stance slip is 3.8 px (frames 2-6) and 5.8 px (frames 11-16), about 5-8 cm.
  - BEFORE: The kick is -59 to -65 deg (frames 10-12), nearly pure lateral.
- **StrafeRunRightTwoHand.**
  - AFTER: Kick -41 to -21 deg (frames 5-11), grip intact, wrap step 0.99x the mean step.
  - BEFORE: Kick -58 to -64 deg (frames 10-12).
- **BlinkLeft.**
  - AFTER: In the fixed-camera rt front view the crouch bottoms at frame 12 with a 12 px head drop (about 17 cm). Two push frames lean the upper body 15 px toward travel (frames 13-14). Landing compresses 5 px after contact (frames 20-21) and settles by frame 24. The feet hold within 1 px through crouch, push and landing. The last in-place steps are 0.78 and 0.47 (still moving, so no freeze).
  - BEFORE: The crouch is shallower (9 px, bottom at frame 13). There is no landing compression (head rises 114 -> 105 monotonically), and the last in-place step is 0.00, a frozen final frame.
- **BlinkLeftTwoHand.**
  - AFTER: Same timing (top of sword drops 12 px at frame 12), grip stays on the hilt through the crouch in the 3/4 view, and the final steps are 0.79 and 0.50.
  - BEFORE: Final step 0.00 (freeze) and a crouch of only 7 px.
- **BlinkRight.**
  - AFTER: Head drop 11 px at frame 12, lean 10 px toward travel at frame 14, landing dip 5 px (frames 20-21), feet locked to within 1 px.
  - BEFORE: Head drop 10 px, no landing compression, final step 0.00.
- **BlinkRightTwoHand.**
  - AFTER: Sword-top drop 9 px, landing dip 7 px (frames 20-21), final steps 0.80 and 0.51.
  - BEFORE: Final step 0.26 after a 0.31 step (near-freeze) and no landing compression.
- **RollAttack.**
  - AFTER: Across the root stop (frames 23-27) the helmet world velocity now ramps smoothly at 8, 8, 6, 3, 1 px/frame. The last three action frames move the head 1, 1, 0 px. The get-up rear foot holds within about 3 px (frames 24-29). The remaining problems:
    - The lunge front-foot heel slides about 10 px (about 14 cm) during frames 31-37.
    - The rear foot drags forward about 10 px (about 14 cm) during frames 42-45 with no visible lift.
    - The lunge-to-stand recovery snaps in about 4 frames: the front foot covers about 62 px (about 85 cm) between frames 38 and 42, and the sword centroid moves 47 px/frame at frames 43-44, as fast as the downswing.
  - BEFORE: The root stop jolts (helmet velocity 7.3 -> 1 px/frame between frames 24 and 25). The head is still moving 6, 4, 3 px/frame on the last three frames, and the same rear-foot drag (about 12 px) happens at frames 46-49.
- **StrafeRight (unchanged).** In the rt front view the stance sole moves +4.67 px/frame against the +4.6 px/frame floor over 12 frames (locked). The wrap is continuous (sole x 142, 146, 150, 153, 157, 160). The swing foot skims inside the 5-row sole band (under about 7 cm clearance) for about 8 frames (13-20).
- **StrafeRightTwoHand (unchanged).** Same lower body and locks as StrafeRight. The blade is carried horizontally with both fists on the hilt, and its vertical bob is 20 px in the 3/4 view.
- **BackpedalGuard (unchanged).** In the rt side view the stance foot tracks the 2.4 px/frame floor (+2.3 px/frame over frames 13-24). At about 2.7 steps/s with roughly 37 cm steps it reads as a guarded retreat, not a hurry. The reaching foot drifts 7 px inside the sole band at frames 9-11 (a low shuffle on contact). Wrap step ratio 1.05.
- **BackpedalGuardTwoHand (unchanged).** Same lower body and lock as BackpedalGuard. The raised blade holds its angle with 8-15 px of bob, and the wrap is continuous.
- **StrafeLeft (protected).** The stance sole loses about 5 px over 14 frames against the floor (about 7 cm) and the wrap is continuous. The row is locked; this is a note, not a veto.
- **StrafeLeftTwoHand (protected).** Identical lower body to StrafeLeft; same note, not a veto.

## Five most visible defects, ranked

1. **RollAttack, recovery snap, frames 41-46 (side and 3/4 views).** The knight goes from the full lunge to standing in about 4 frames. The front foot travels about 85 cm in about 4 frames, and the sword centroid moves 47 px/frame at frames 43-44, as fast as the strike (53 and 74 px/frame at frames 32-33). It reads as a pop back to idle, not a recovery.
2. **RollAttack, rear-foot drag, frames 42-45 (side view).** The rear foot slides forward about 10 px (about 14 cm) while it stays in the sole band; its left edge goes 161 -> 171. Round 3 had the same drag about 3 frames later.
3. **RollAttack, lunge front-foot heel slide, frames 31-37 (side view).** The heel edge moves about 10 px (about 14 cm) forward while the slash lands. This is better than round 3 (about 25 px) but still visible.
4. **Sprint strafes, swing-foot hook, top views (SRL frames 5-11, SRR frames 7-13).** The heel-kick direction swings 25-40 deg within one flight phase (from 45-60 deg to about 20 deg off straight back). At full extension the leg plane is only about 25-35 deg off the boss, so the legs read close to fore-aft while the body travels laterally. Touchdown also slips 2-4 px/frame on the first contact frame (rt SRR frames 2-3 and 11-12). The clip reads as a diagonal crab-run rather than a clean cross-over.
5. **Blinks, launch with no toe-off, rt frames 13-14 (front and 3/4 views).** Both feet stay locked to within 1 px while the torso leans 10-15 px, and then the knight vanishes. The 5-frame windup (crouch at 11-12, push at 13-14) now reads, but the push is a lean, not a jump. On reappearance the feet are already planted at frame 20.

Also noted: the swing foot skims low in StrafeRight and BackpedalGuard (unchanged rows), and the checker aliases in the review renders (the evidence limit above).

## Round-3 open items

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Sprint-strafe pelvis about 80 deg off the boss; wants a sideways/cross-over run with waist twist capped near 45 deg and the free arm animated | **PARTIALLY FIXED** | The leg plane moved from about 60-90 deg to about 25-35 deg off the boss at full extension (45-60 deg at kick start). The chest stays about 0-30 deg. The free arm now swings in the one-hand clips. The swing path hooks (defect 4), the twist between pelvis and chest is small (about 0-30 deg) rather than near 45, and the cross-over is weak, so it reads as a diagonal crab-run. |
| 2 | Roll-attack exit: about 4 cm/frame hip motion in the last frames, a 12 cm hip pop around frame 23, stand-up foot skate | **PARTIALLY FIXED** | The pop is fixed (helmet world velocity ramps 8, 8, 6, 3, 1 px/frame instead of 7.3 -> 1). End drift is fixed (last three frames 1, 1, 0 px instead of 6, 4, 3). The get-up rear foot is planted (about 3 px, frames 24-29). The stand-up skate on the recovery is **not** fixed: the rear foot still drags about 14 cm (frames 42-45), now inside a 4-frame snap (defects 1-2). |
| 3 | Blink: last-3-frame freeze and a weak crouch/launch | **FIXED** | The last steps are 0.78 and 0.47 (r3: 0.29, 0.00). The crouch is 11-12 px (about 17 cm), bottoming at action frame 3. There are two lean frames toward travel and a 5-7 px landing compression after contact. The residual is defect 5. |
| 4 | Right-side and backpedal loop seams | **FIXED (not visible)** | On every loop the wrap step is 0.72-1.05x the mean in-loop step, and sole positions are continuous across the wrap (StrafeRight 153 -> 157 -> 160; BackpedalGuard 197 -> 200 -> 202). |

## Does the sprint strafe read as a sideways run with the waist twist near 45 deg?

Only partly. The pelvis is no longer turned about 80 deg away from the boss, and the legs now swing in a plane about 25-35 deg off the boss axis (45-60 deg at the start of each kick). That is a large improvement, and with the free arm swinging in the one-hand clips, the clip no longer looks like a forward run turned sideways. The waist twist, though, is not "near 45": the chest sits about 0-30 deg off the boss, so the twist is roughly 0-30 deg. The swing foot also hooks through 25-40 deg during flight. The read is a diagonal crab-run with good foot lock (2-8 cm stance slip at 5 m/s), not a clean cross-over sideways run. Not a veto.

## Does the roll-attack slash still land with reach?

Yes. The slash is a high right-side raise (frames 29-31) into a diagonal cut across the front (frames 32-34), finishing low to the knight's left (frames 35-41).

- At frame 33 the body is about 11 px (about 15 cm) closer to the boss than in round 3 (pelvis proxy 231 vs 220), and the forward-most helmet position is 260 vs 250. Reach is preserved and slightly greater.
- The extra forward travel comes as a visible small step after the get-up (frames 24-28, about 25 cm, rear foot planted). It reads as a deliberate roll-in step, not a short slash.
- **Caveat:** the blade leaves the frame in the side and 3/4 views during the strike (crop edge), so absolute blade reach is unproven on this page. Re-render with a wider frame.

## Verdict

**NOT SHIPPABLE.** The veto row is **RollAttack**: the recovery at frames 41-46 snaps from lunge to idle in about 4 frames and drags the rear foot about 14 cm while it is in contact (defects 1-2). That is the round-3 "stand-up foot skate" moved earlier, not removed.

Every other changed row (the four sprint strafes and four blinks) is a clear improvement at 7/10 and would not block on its own. The unchanged rows (StrafeRight, StrafeRightTwoHand, BackpedalGuard, BackpedalGuardTwoHand) also score 7. The protected rows (StrafeLeft, StrafeLeftTwoHand, staggers) are excluded from the veto list.

### Biggest gap, as a testable instruction

In `rt-RollAttack`, side view, frames 41-50:
- No foot may move more than 2 px (about 3 cm) horizontally while its sole is within 8 px of the ground. Either keep the rear foot planted, or lift it clear by at least 8 px (about 11 cm) and step.
- Spread the lunge-to-stand recovery over at least 8 frames, so that the sword centroid in the 3/4 view never exceeds 25 px/frame after frame 41 (about half the downswing peak).
- Re-render the roll-attack views with the full blade in frame through frames 32-41.
