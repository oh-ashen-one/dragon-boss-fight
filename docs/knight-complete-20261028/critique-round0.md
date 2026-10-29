# Veyr knight completion pass: independent critique (2026-10-28)

Reference: Can It Code UE 5.8 boss-fight hero (z1mgtUvTdqg), a shipped-quality, weighty, readable third-person melee hero.
Evidence used: the 40 unique videos in `serve/media/` (all frames extracted, 1080x360, 3 x 360 px panels: front | side | 3/4), the 15 screenshots in `serve/ingame/`, and the critic brief (used only for what to compare). I did not read the builder notes, HANDOFF or commits.

## Method and scale

- Every frame of every clip was extracted. Contact sheets: 6 to 10 frames per clip, plus zooms at 2x to 5x for hands, feet and joins.
- **Foot contact:** I tracked bright sabaton blobs within 3 px of each clip's ground line, then linked them into stance segments. Because the clips are in-place, a correctly planted foot moves at a constant speed. Slip is measured as variance or spikes in that speed (px/frame).
- **Seams and pops:** mean absolute frame difference over rows 0 to 300. A seam is the last-to-first difference compared with the median and max in-cycle step. A pop is any step at or above 1.8x the clip median.
- **Sword-tip speed:** in the side view, the farthest non-sky pixel from the hip.
- **Scale:** I derived it from the page's own speeds. Walk stance is 5.1 px/frame at 240 cm/s (1.57 cm/px). Run stance is 12.0 px/frame at 580 cm/s (1.61 cm/px). Strafe stance is 2.9 px/frame against a nominal 138 cm/s (1.59 cm/px). I use 1.6 cm/px throughout.
- **Checker:** the "25 cm checker" claim does not hold up. Tile edges repeat every 43 px at foot depth, which is about 68 cm at this scale.
- **Resolution limit:** the knight is about 172 px tall and the hands are about 8 px. Grip claims (palms on the hilt, knuckle crossing) cannot be verified at this size. That part of the weapon axis is unproven and is scored down.

## Scores (AFTER, 1-10)

Axes: W = weight/groundedness, R = readability of intent, C = contact/foot planting, Wp = weapon handling, T = transition (seam or join), S = silhouette. "Before" is the 0-10 score for the previous slot occupant.

| Row | W | R | C | Wp | T | S | Verdict | Before | Biggest measurable gap (instruction) |
|---|---|---|---|---|---|---|---|---|---|
| Walk 1H | 5 | 7 | 8 | 3 | 6 | 4 | APPROACHES | 4 | The blade is held horizontal at the hip, pointing forward like a lance, with no visible pitch change over 55 frames (side view). Tilt the tip down 30-45° to trail beside the right leg and add 5-10° of lag per step. The seam step is 1.71, against an in-cycle max of 1.47. |
| Walk 2H | 6 | 7 | 8 | 5 | 6 | 6 | APPROACHES | 5 | The blade base covers the helmet visor in the 3/4 view at f1 and f23. Move the carry 15-20 px (screen) outboard over the right pauldron. Seam: 1.79 vs max 1.55. |
| Run 1H | 7 | 7 | 6 | 4 | 6 | 6 | APPROACHES | 5 | The one-hand blade is held vertically in front of the face and hides 100% of the helmet in the front view (f1, f10, f28). Stance speed is uneven: the landing frame moves 5 px (f20→21) against 12 px mid-stance, and f24→25 spikes to 17 px. Fix the landing so the foot hits at stance speed (≤±2 px/frame). |
| Run 2H | 7 | 7 | 6 | 7 | 6 | 7 | APPROACHES | 5 | Same legs as Run 1H, so the same contact numbers: landing at 5-6 px/frame against 12-13 px, and a 16 px spike at f24→25. Seam: 2.51 vs max 2.41. |
| Light attack (1H) | 7 | 8 | 7 | 5 | 4 | 7 | APPROACHES | 5 | f1 and f27 are a vertical-blade guard, about 90° of pitch away from the horizontal 1H locomotion carry, so every entry and exit blend sweeps the 2 m blade. Author the start and end in the 1H carry, or add a 4-6 frame lead-in and lead-out. |
| Roll | 3 | 6 | 4 | 6 | 6 | 5 | FAILS | 4 | The body flies horizontally about 50 px (about 80 cm) above the floor at f5-f7, then lands on the helmet at f9-f11 (side view). Replace it with a low shoulder roll: the lowest body point should be ≤10 px above the floor before contact, and contact should be on the right shoulder, not the head. |
| Roll attack | 4 | 6 | 5 | 5 | 2 | 6 | FAILS | 5 | There is a one-frame splice at f25→f26. The blade goes from horizontal to vertical overhead, and the tip moves about 127 px (about 2 m) in 33 ms (front view). The step diff is 4.4, 1.9x the median. Replace it with an authored or crossfaded transition of at least 8 frames (≥0.25 s). The clip also ends in the 2H guard, not the 1H carry. |
| Blink left | 4 | 5 | 6 | 4 | 6 | 4 | APPROACHES | 3 | The legs are the sprint-strafe-left cycle (front stance -6..-7 px/frame): correct direction, but there is no anticipation, crouch or burst. The tempo matches a jog (17 frames). Add a 3-4 frame crouch-load and a push-off frame with the stance foot at ≥2x locomotion speed. |
| Blink right | 3 | 3 | 3 | 4 | 6 | 4 | FAILS | 3 | The side-view stance foot moves fore-aft at -10..-13 px/frame, while the front-view lateral motion runs -9, -8 (f2-f4, i.e. leftward) and then +3..+4. The legs run forward and start in the wrong direction. Use a lateral cycle: lateral ≥8 px/frame, fore-aft ≤1.5 px/frame, with the first frames moving toward the knight's right. |
| Grip to two hand | 3 | 7 | 9 | 5 | 5 | 5 | APPROACHES | none | Arms only: 0 px of foot or hip motion over 15 frames, and a symmetric ease with no anticipation or settle. It ends with the blade vertical in front of the face, but the 2H locomotion carry is tilted over the right shoulder. Make the end pose match the 2H walk frame and add a 2-3 px hip dip with the catch. |
| Grip to one hand | 3 | 7 | 9 | 6 | 5 | 5 | APPROACHES | none | It is the exact reverse of Grip to two hand (the per-frame diff series mirrors it). Same fix: add weight shift and settle. |
| Backpedal (1H, used for both grips) | 4 | 5 | 8 | 4 | 6 | 4 | APPROACHES | 1 | The stance is clean (+2.3 px/frame, sd 0.45, about 110 cm/s; claimed 100). Cadence is 84 steps/min, so it is not hurried, but it is not a guard either: torso lean is 0 px (head x 185-187, against +13 px in the walk) and the blade sits at the hip. Raise the blade to a guard and add ≥8 px of forward lean. There is no 2H version (see pipeline). Seam: 1.57 vs max 1.35. |
| Strafe L 1H | 6 | 7 | 6 | 3 | 7 | 5 | APPROACHES | 1 | Lateral stance runs -2..-4 px/frame, but the planted foot drifts 5 px in depth (y 268→273) during f6-f24 (front view). Hold the stance-foot y within ±1 px. Same lance carry as Walk 1H. |
| Strafe R 1H | 6 | 7 | 6 | 3 | 8 | 5 | APPROACHES | 1 | Planted-foot depth drift of 5 px (y 267→272) at f43-f54 (front view). Same lance carry. |
| Strafe L 2H | 6 | 7 | 6 | 5 | 6 | 6 | APPROACHES | 1 | Same legs as 1H; depth drift of 5 px. The blade covers the helmet in the front view. Seam: 1.63 vs max 1.53. |
| Strafe R 2H | 6 | 7 | 6 | 5 | 8 | 6 | APPROACHES | 1 | Same legs as 1H; depth drift of 5-6 px (f15-f29). |
| Sprint strafe L 1H / 2H | 6 | 6 | 5 | 4 / 5 | 7 | 5 | APPROACHES | 1 | Lateral stance is -6.5 px/frame, about 312 cm/s, against a nominal 411 (-24%). That is about 99 cm/s of skate if the capsule moves at the nominal speed. Raise the play rate or the stride by 1.3x. |
| Sprint strafe R 1H / 2H | 5 | 3 | 2 | 4 / 5 | 7 | 5 | FAILS | 1 | Side-view stance runs -8..-12 px/frame fore-aft, while front-view lateral is only +2..+5 px/frame. The travel axis is about 22° off forward, not 90°, so a lateral capsule move skates the feet about 480 cm/s fore-aft. Replace it with a true lateral sprint cycle (about 8.4 px/frame lateral at 404 cm/s). |
| Stagger front 1H / 2H | 6 | 7 | 5 | 4 | 4 | 6 | APPROACHES | 3 | The hit reads: head 32 px back and 15 px down, recovered by f18. But f1 is a wide stance (feet 117 px apart, against about 35 px in locomotion), and the 1H blade lies across the body (about 90° of yaw off the forward carry); the 2H blade is vertical in front of the face. The right foot slides out 9 px and back with no lift (f1→f9→f17). Match f1 and the last frame to the locomotion carry and stance, and plant that foot. |
| Stagger back 1H / 2H | 6 | 7 | 7 | 4 | 4 | 6 | APPROACHES | 3 | Reads as a hit from behind: head 19 px forward and 16 px down. Feet hold within 4 px. Entry pose has the same wide stance and the same blade offset as Stagger front. |
| Stagger left 1H / 2H | 5 | 5 | 7 | 3 | 4 | 5 | APPROACHES | 3 | The direction is correct (head 16 px toward the knight's right), but the amplitude is half the front stagger and the clip starts crouched (head y 129, against 112-115 for front/back). The 2H version starts with the blade over the left shoulder, the opposite side from the 2H carry. Double the lateral displacement to ≥30 px and start from the carry pose. |
| Stagger right 1H / 2H | 5 | 5 | 8 | 6 | 6 | 5 | APPROACHES | 3 | The mirror is correct in direction (head +16 px toward the knight's left), and the sword stays in the right hand. Its f1 carry matches locomotion, which means it is not a true mirror of the left (whose sword pose differs). Amplitude is 16 px; raise it to ≥30 px. |
| Run → RunStop join (0.30 s) | 5 | 6 | 6 | 6 | 8 | 6 | APPROACHES | 4 | The join is fixed. Peak side-view tip speed during the blend falls from 36.4 px/frame at 0.10 s (f36→37) to 8.5 px/frame at 0.30 s, and the step diff falls from 3.5 (2.3x median) to 2.0. The stop itself goes from a +24 px forward lean to -6 px in 9 frames (f35→f44): 580 cm/s to upright in 0.3 s. Extend the brake so the lean returns over ≥12 frames, with one planted braking step ≥40 px ahead of the hips. |

## Pipeline defects (separate from animation quality)

1. **Roll-attack splice (FAIL):** the roll prefix and the slash are joined with no blend, at f25→f26 (described in the table).
2. **Missing 2H backpedal:** the in-game screenshot `frame-0023-..._falls_back_to_one_hand_backpedal.png` shows 2H lock-on back falling back to the 1H clip. That snaps the sword from the upright 2H carry to the hip carry.
3. **Blink file/direction cross-mapping:** BlinkLeft plays `Sourced_BlinkRight_Transit_v2` and BlinkRight plays `..._BlinkLeft_...`. The blink-right legs also run forward (see table). This is a naming hazard as well as a motion error.
4. **Suspected armor material/lighting fault in game:** in `frame-0002-lockon_back_one_hand.png` the armor reads as near-white chrome. Torso mean luma is 77.6, against 42.0 in frame-0023 and 49.9-50.7 in frames 0029-0030, and 11.6% of pixels are above 200 (3.4-4.8% elsewhere). Verify the material and exposure.
5. **Scale label:** the "25 cm checker" is about 68 cm at the scale implied by the page's own speeds. Either the label is wrong or the render is not at game scale. Absolute slip in centimetres therefore depends on my speed-derived scale.
6. **Review-media holds:** clips are padded with 8-9 frozen frames on the review page:
   - light attack f28-36
   - roll f23-31
   - roll attack f51-59
   - staggers f18-26
   - grips f15-23
   - blinks f17/18-25/26

   This is not a game defect, but the looping players hide the exit pose snapping back to f1.
7. **Not found:** no white or untextured mesh in the renders, no missing sword (the blade vanishes in the 3/4 view at light-attack f16-18, but that is occlusion; it is visible in the front view), and no T-pose frames. Neither the sampled frames nor the per-frame diff spikes show any. Pops above 1.8x median occur only at the roll-attack splice, inside attack swings, and in the old stagger at f1→f2 (6.8x).
8. **Clipping:** unverified at this resolution. The blade overlaps the helmet in 2D in walk 2H (3/4 view f1, f23), grip-to-two f13-15, both runs and the 2H strafes (front view). The depth separation cannot be confirmed from 8 px detail.
9. **In-game screenshots:** the stagger-lab frames (0029-0035) crop the knight at the belt, and the run was at about 16 fps. They show which clip was selected, not how the stagger looks.

## Overall verdict

**FAILS the shipped bar.** None of the 23 rows meets it. Four rows are not shippable as they stand: Roll attack (splice), Sprint strafe right in both grips (wrong travel axis), Blink right (wrong axis and direction), and Roll (an 80 cm airborne dive that lands on the head for an 8-ft armored knight). Every lock-on row improves on BEFORE, which was the forward walk or run with the knight turned away from the boss. The forward walks and runs have clean stance speed (sd 0.3-0.7 px/frame for the walk) and are better than before. Weapon-pose continuity across clips is the systemic weakness: four different 1H blade orientations and three different 2H orientations appear on first frames.

## Top 5 fixes (ranked)

1. **Roll attack:** remove the one-frame splice at f25→f26 (tip jump of about 127 px, about 2 m in 33 ms). Use a transition of at least 8 frames, and end in the 1H carry.
2. **Sprint strafe right (1H and 2H) and Blink right:** replace the forward-running legs. Today the side-view stance runs -8..-13 px/frame fore-aft against +2..+5 lateral. Target ≥8 px/frame lateral and ≤1.5 px/frame fore-aft, with the first frames moving toward the knight's right. Also raise sprint strafe left by 1.3x (it runs at 312 cm/s against 411).
3. **Stagger entry/exit poses:** make f1 and the last frame match the locomotion carry and stance.
   - Feet are 117 px apart today, against about 35 px.
   - The 1H blade lies across the body at about 90° of yaw off the forward carry.
   - The 2H blade is vertical in front of the face (front and back staggers) or over the left shoulder (left stagger).
   - Also remove the 9 px slide-and-return of the right foot in stagger-front, and double the left/right displacement from 16 px to ≥30 px.
4. **Roll:** keep it low. Today the body is about 50 px (about 80 cm) airborne at f5-f7 and lands on the helmet at f9-f11. Aim for a shoulder contact with the lowest body point ≤10 px above the floor before it.
5. **One canonical carry per grip:** every 1H and 2H clip's first and last frame should be within 15° of blade angle of that carry.
   - The 1H walk, strafe, backpedal and blink clips use a horizontal forward "lance".
   - The light attack starts and ends in a vertical guard.
   - Grip-to-two ends blade-in-front-of-face, while the 2H walk carries over the right shoulder.
   - Tilt the 1H carry tip down 30-45° with 5-10° of step lag. Then author the missing 2H backpedal and give the backpedal a raised guard with ≥8 px of forward lean.
