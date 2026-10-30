# Veyr dragon: critique round 3

Date: 2026-10-30. This is a blind critique based on the videos only. Critic: Opus 5.5.

I used only the rendered MP4s in `video/` (`clip_<LABEL>_<view>.mp4`) and the Seedance sources in `serve/`. I read `index.html` only to map columns to files. Checksums confirm that `after_*_r2` = label 4 and `after_*_r1` = label 3. I did not read HANDOFF, commits, refine code or captions.

The bar is a shipped AAA boss. The use case is engine Actions viewed by the player at 5 to 20 m.

## Method

- **Tooling.** The scripts are in `/private/tmp/claude-501/-Users-midir/1e99ac11-5966-4ca4-8ec7-273fc683df51/scratchpad/critic-dragon-r3/py/` and the evidence sheets are in `.../critic-dragon-r3/sheets/`.
- **Segmentation and metrics.** Segmentation, the background plates and the metric definitions are the round-2 critic's (plate ratio, chroma and shadow rejection, `critic.py` functions). I checked the overlays by eye (`sheets/ov1.png`).
- **Cameras.** I matched plates for every clip:
  - The ground clips are on the G camera (1 BH = 315 px front, 6.0 px/cm).
  - LA3 and LA4 are on the T camera (1 BH = 227 px left).
  - **All four label-4 airborne clips moved to the K camera** (1 BH = 158 px left; TK4 frame-0 standing height measures 158 px). AH1, AL1 and FD1 were on T, so I compare across rounds in BH units only.
- **Pop scan.** A frame is a pop when its step change d is above 2.0 and above 2.2 times the median of the ±3 neighbouring steps. I scanned every clip and view this way.
- **Body bob.** I track a chest patch with sub-pixel NCC (front view, NCC at least 0.5). Silhouette centroids are contaminated by the dark wing-arm bones, so I do not use them for bob.
- **Wing-body coupling.** This is |corr| between the wing-top velocity and the chest acceleration, both 5-frame smoothed, with the wing leading by 0 to 4 frames. The sign is ignored, as instructed.
- **Source scale.** For the Seedance sources I measured silhouette height and width on the split-screen panels (dark or chroma threshold).

## Scores and verdicts

| Clip | Score /10 | One-line evidence | vs previous column | Use as Action |
|---|---|---|---|---|
| Roar RS4 | 6 | Front frame 66: wings open to 1.26x idle span (636 px = 2.02 BH). The hold is now alive (d 6 to 8.8 against 0.6 to 1.1 in RS3), but the screen-left half-span averages 1.29x and the screen-right 1.19x. | BETTER | NOT SHIPPABLE |
| Collapse CO4 | 5 | Frame 144, front: the end silhouette is still 0.69 of standing height (source 0.47). The far wing is tented and the near wing still spikes past the snout in the 3/4 view (leftmost x 85, same as CO3). Only a breath was added. | SAME | NOT SHIPPABLE |
| Bite BI4 | 7 | Left view: reach 75 px = 12.5 cm (was 9.2), held 4 frames (was 35). The clip returns to stance with no pop (exit IoU 0.988 / 0.992, seam 0.47 / 0.66). | BETTER | SHIPPABLE |
| Rise RI4 | 5 | Frame 0 now equals the collapse end (IoU 0.986 / 0.993 / 0.990), but the get-up is a whole-body blend that pops at frame 43 to 44 in all views (consecutive IoU 0.883 against 0.996 around it). | BETTER | NOT SHIPPABLE |
| Land2 LA4 | 6 | Left view: touchdown at frame 74 with 6 to 8 px/frame approach steps (was a 22 px snap). Arc a_down / a_up = 0.93. The hop is only 0.42 BH (source 0.53, LA3 0.57). | BETTER | SHIPPABLE |
| Air hover AH4 | 7 | A real beat at last: front wing-top 0.58 BH peak-to-peak, period 26.2 frames; chest bob 0.13 BH; coupling 0.94 with the wing leading 1 frame; saw 0.026. But the downstroke stops at horizontal and the tail is rigid (tip moves 9 px = 0.06 BH). | NO-BEFORE | SHIPPABLE |
| Takeoff3 TK4 | 7 | Feet planted ≤1 px until frame 51, crouch 0.12 BH front, lift-off on a downstroke (span +66% over frames 48 to 54). Peak-to-end hover height 1.06 (feet 124 px against 117 px). The end matches AH4 frame 0 (IoU 0.986 / 0.992 / 0.984). | NO-BEFORE | SHIPPABLE |
| Air land AL4 | 3 | Frame 63 to 64, all three views: the whole dragon teleports up 35 px (0.22 BH) in one frame (d 16.4 against 4.0 around it). The landing then compresses only 0.06 BH (source belly-slam 0.44), and the clip freezes for frames 118 to 144. | NO-BEFORE | NOT SHIPPABLE |
| Air fire-down FD4 | 6 | The hold now beats (left d 1.83 against FD1's 0.46). The jaw aim is steady over frames 84 to 152 (jaw x peak-to-peak 4 px, y 15 px = 0.09 BH). But the wing-top barely moves (≤16 px) during the frames 33 to 66 wind-up. | NO-BEFORE | SHIPPABLE |

Airborne verdicts are NO-BEFORE, as instructed. For information only, every label-4 airborne clip beats the label-1 column that round 2 failed (that column had no wing beats, a stuttering hover and a levitating takeoff), except AL4, which gained a pop.

## Task 1: ground clips, round-2 defects re-checked

### Roar (RS4 vs RS3 vs Seedance source)

| Round-2 defect | RS3 | RS4 | Status |
|---|---|---|---|
| Dead hold (target change ≥1.2) | d 0.6 to 1.1 | d 6.2 to 8.8 over frames 45 to 86; wing tops undulate 22 to 28 px | FIXED |
| Tremor 1.5 to 3 px | 0.7 / 1.6 px | wing-tip high-pass std 1.65 / 3.11 px | FIXED, with a new risk (below) |
| Flare opens over ≥8 frames, closes over ≥10 | 3 / 13 (my 10-90% measure) | opens 10 frames (32 to 42), closes 11 frames (88 to 99) | FIXED |
| Both wings ≥1.22x idle half-span, within 5% | L 1.32 / R 1.08 (hold mean) | L 1.29 / R 1.19 (hold mean), gap mean 0.10, max 0.20 | PARTIAL: right wing still short, gap twice the limit |

The wings are oversized against the approved source:
- RS4 peaks at a 1.26x idle front span: 636 px, which is 2.02 standing heights.
- The approved Seedance roar source goes from 440 to 482 px (1.10x) at rest-height 265, so it peaks at 1.82 standing heights.
- The source lifts its wings up rather than out: silhouette height 1.28x. RS4 matches that height (1.29x), so its 14% extra lateral spread is all oversize.
- Round 2's ≥1.22x target pulled the clip toward the oversized, fanned look the owner rejected earlier. My recommendation is to reverse that target and follow the source (see the fix list).

Membrane checks:
- **No tears.** The enclosed hole fraction of the wing area is 0.021 to 0.028 at full flare against 0.036 to 0.039 at rest. The holes are the tattered texture and do not open up when stretched.
- **No body interpenetration.** I found none at frames 45, 66 and 78 in the front and 3/4 crops (`sheets/rs4_f66.png`, `rs4_3q_head.png`).
- **Possible tail contact.** In the 3/4 view at frame 78 the near wing's trailing finger touches the curled tail tip. Depth cannot be resolved from the video.

Feet and seams:
- Feet are planted within 1 px in both views.
- Entry IoU is 0.993 / 0.997 and exit IoU 0.986 / 0.992; the seam is 0.43 / 0.60 steps.

New risk: the hold's motion is a regular 4-frame (6 Hz) buzz.
- Left-view saw is 0.249 over frames 40 to 90 (period 3.75 frames). The rest of the clip measures 0.07 to 0.09, and idle measures 0.032.
- That is above the 0.2 level at which stepping shows by eye. It will read as mechanical vibration rather than strain.

### Collapse (CO4 vs CO3 vs source)

| Round-2 defect | CO4 | Status |
|---|---|---|
| Dead lying hold | d 0.43 / 0.60 / 0.55 over frames 110 to 144 (CO3 0.19 to 0.23); centroid breathes 2.2 to 2.4 px on a 45-frame period | FIXED |
| Fall reads light (0.6 to 0.8 s) | fall window and peak identical to CO3 (frames 63 to 81, peak d 10.0 at frame 73) | NOT FIXED |
| Not lying flat: wings tented | end height 217 / 316 = 0.69 front (CO3 0.69), 0.59 left; source end is 159 / 337 = 0.47 front and 0.45 side | NOT FIXED |
| Spindle wing | 3/4 frame 144: the dragon's right wing still projects forward-left past the snout as a rigid blade (leftmost x 85; CO3 82). Left view: wing digits stick out ahead of the head | NOT FIXED |

The tail lies straight along the floor with a slight lift at the tip (left view, frame 144), which matches the source's flat tail. I see no tail defect.

Apart from the breath, CO4 renders pixel-identically to CO3: same end silhouette and same per-frame d up to frame 110.

### Bite (BI4 vs BI3 vs source)

| Round-2 defect | BI3 | BI4 | Status |
|---|---|---|---|
| Full-reach freeze ≤10 frames | 35 frames within 3 px of full reach (frames 49 to 83) | 4 frames (47 to 50) | FIXED |
| Reach ≥12 cm | 55 px = 9.2 cm | 75 px = 12.5 cm | FIXED |
| Returns to stance without a pop | n/a | last 5 steps 1.38, 1.06, 0.81, 0.62, 0.27 (front); exit IoU 0.988 / 0.992; seam 0.47 / 0.66 steps | FIXED |
| Jaw open at the strike | open at frames 36 to 40 | open at frame 40 (front crop, red gape) | KEPT |

New and remaining issues:
- **Velocity hitch at frames 50 to 51.** d jumps 2.0 to 4.7 (front), 1.4 to 3.8 (left) and 1.6 to 4.7 (3/4) after the strike has decelerated. The snout recoils 8 px in 2 frames, then stalls for 6 frames (frames 51 to 56, d 0.7 to 0.9) before the recovery. It reads as a twitch.
- **The near wing collapses into a thin hook in the 3/4 view** over frames 44 to 62. Wing pixels drop to 0.39 to 0.48 of frame 0. This is the round-1 defect, still present (`sheets/bi4_mid.png`).
- **The clip is 18 frames shorter** (93 against 111).

### Rise (RI4 vs RI3)

Get-up chain:
- **Fixed.** RI4 frame 0 against CO4's last frame gives IoU 0.986 (front), 0.993 (left) and 0.990 (3/4). The mean grey difference is 0.37 to 0.40.
- **Distance from lying to standing.** RI4 frame 0 against the idle stance is 0.130 / 0.265, the same as the collapse end. The top row is 267 px (front) against 135 px standing, so the get-up covers 0.42 BH of rise.

The get-up (frames 8 to 42, 1.4 s) is a pose blend, not a get-up:
- Every limb and both wings move at once along a single bell-shaped speed curve: d rises 0.4 to 5.3 and falls back to 0.3.
- There is no forelimb plant-and-push, no hind-leg gather and no weight shift.
- **The body floats.** Over frames 21 to 30 the lowest row reaches 418 to 419 against the 424 floor row, and no foot is in contact in the left view (`contact.py`): the whole dragon floats about 1 cm for 10 frames.
- **The wing sweeps like a blade.** Over frames 18 to 22 (front) the dragon's right wing sweeps flat across the floor like a blade (`sheets/ri_getup2.png`).

The handover to the old rise pops:
- Frame 43 to 44 changes by d 4.6 / 2.9 / 3.3 against 0.1 to 0.3 on either side.
- Consecutive-frame IoU is 0.883 (front) and 0.926 (left), against 0.994 to 0.999 around it.
- Wings, head and body all jump (`sheets/ri_pop.png`).
- After the pop, RI4 frames 44 onward replay RI3 from about frame 14 (IoU 0.987 to 0.994).

Dead frames:
- **Start.** Frames 0 to 7 have d ≤0.1, so the collapse's breathing stops dead on the chain.
- **Middle.** Frames 44 to 50 freeze again (d 0.1 to 0.4) before the rear-up.

The remainder (rear-up and drop) is RI3's, so its stutter fix is kept (saw 0.031 / 0.041) and it ends on stance (exit IoU 0.983 / 0.992).

### Land2 (LA4 vs LA3 vs source; T camera)

| Round-2 defect | LA3 | LA4 | Status |
|---|---|---|---|
| Touchdown snap ≤8 px/frame | 437 to 459: 22 px in 1 frame at frame 74 | 435, 443, 449, 451, 459: steps of 8, 6, 2 and 8 px; touchdown frame 74 (source 75 to 76) | FIXED |
| Take-off snap ≤8 px | 24 px at frame 39 | hind foot leaves 17 px in 1 frame at frame 40 to 41, with body speed 11 px/frame (1.5x) | PARTIAL |
| Ballistic: a_down / a_up 0.8 to 1.25 | 2.06 (left) | 0.93 (left) | FIXED in the side view |

On the side-view ballistics:
- The descent still has a 12-frame constant-speed stretch (3 to 5 px/frame, frames 59 to 70, left view).
- The body speeds up to 14 px/frame at contact, so the body falls faster after the feet land than in the air.
- In the front view the fitted ratio is 0.35.

Hop height and compression:

| Measure | LA4 | LA3 | Source |
|---|---|---|---|
| Hop height (feet above floor) | 98 px = 0.42 BH | 0.57 BH | 0.53 BH (141 / 264 px) |
| Pre-jump crouch (top drop) | 0.14 H | 0.14 H | 0.17 |
| Post-touchdown compression | 0.17 H | n/a | 0.21 |

- The hop is 20% lower than the source.
- The crouch and the post-touchdown compression are both slightly weaker than the source.
- The wings ride folded through the hop. The front-view span series is identical to LA3.

## Task 2: airborne clips, first critique (K camera)

### Air hover AH4 (131 frames)

Beat and coupling:
- **Wing beat.** Front wing-top peak-to-peak is 92 px = 0.58 BH, with a period of 26.2 frames (0.92 Hz). Left view: 104 px = 0.66 BH.
- **Stroke timing.** The downstroke takes 42% of the cycle.
- **Bob.** The chest track moves 20.4 px = 0.13 BH, on the same 26.2-frame period.
- **Coupling.** |r| = 0.94 with the wing leading by 1 frame. The body phase is 65° after the wing's, against 90° for an ideal lift response.

Loop seam:
- Frame 130 is a near-duplicate of frame 0 (difference 1.02 grey, 0.12 steps).
- The real seam, frame 129 to frame 0, is 0.73 (front) and 1.08 (left) steps. Both are within the 1.2 limit.
- **Engine note.** The Action range must be frames 0 to 129. Playing all 131 frames in a loop doubles one frame per cycle.

Stability:
- Saw is 0.026 / 0.021 (AH1 was 0.23 / 0.34).
- The span does not drift: frames 0 and 130 both measure 199 px.
- Body area stays within 0.91 to 1.07 of frame 0, periodic with the beat, so no limb grows or shrinks.

Remaining issues:
- **Shallow downstroke.** The downstroke ends at about horizontal (front frame 13). The tips never go below the shoulder line, so the stroke reads as fanning, not lifting.
- **Rigid tail and legs.** The tail tip moves 9 px (0.06 BH) and the legs hang static.
- **Phase drift.** Same-phase frames drift slightly (frame 0 against frames 26 and 52: IoU 0.90 / 0.95 front) because the period is not an integer.

### Takeoff3 TK4 (121 frames)

Ground phase and lift-off:
- **Planted ground phase.** Frames 0 to 50 keep the feet within 1 px (front contacts 424 to 456 and 506 to 536 constant). The tail touches the floor over frames 18 to 30.
- **Crouch.** 19 px = 0.12 BH (front) and 13 px = 0.08 BH (left), frames 24 to 27.
- **Lift-off on a downstroke.** The feet leave at frames 50 to 53. Wing-top is 254 at frame 48 and 318 at frame 57 (downward), and the span grows 194 to 323 px between frames 48 and 54. This matches the source's crouch until frame 44 and launch at frame 48.

Overshoot and end:
- **No overshoot.** Feet peak 124 px above the floor at about frame 93 and end at 117 px: ratio 1.06, overshoot ≤5 px (0.03 BH).
- **Lands in the hover band.** AH4's hover band is 349 to 358 px lowest row, and TK4 settles inside it. The earlier TK1 peaked 2.2x the hover height, so that defect is gone.
- **End pose.** The end matches AH4 frame 0: IoU 0.986 / 0.992 / 0.984.

Beat and stability:
- Coupling over frames 60 to 120 is |r| = 0.86, wing leading 2 frames.
- The flight beat period is 20 to 24 frames, a little faster than the hover.
- Saw is 0.073 / 0.023, and there are no pops.

Remaining issue: lift-off is a soft ease, not a push.
- The lowest row rises 1, 3, 2, 1, 2, 1, 2, 2, 3, 3 px/frame over frames 50 to 60, against a 13 px pre-jump crouch.
- The body does not spring. The wings lift a body that drifts up.

### Air land AL4 (145 frames)

Blocker: a whole-body teleport at frame 63 to 64.
- In all three views the dragon jumps up about 35 px (0.22 BH) in one frame.
- The front lowest row goes 389 to 353 and the left 384 to 350. d is 16.4 / 14.8 / 12.0 against 1.5 to 4.0 around it.
- The head, wings and hind legs all change pose at the same frame (`sheets/al4_pop.png`).
- This is a splice or blend-boundary error. It shows at any distance.

Descent and braking:
- **No braking flare.** The wings stop beating and fold by about frame 75: wing-top settles at 326 to 328 from frame 105.
- The span grows only at or after contact (198 px at frame 78 to 306 px at frame 96).
- Descent speed falls from 8 to 5 px/frame over the last 6 frames (-37%). The target was ≥40% over 12 frames together with a span flare.

Touchdown:
- The feet reach the floor at frames 90 to 93, matching the source's frame 90.
- The approach is about 5 px/frame with no snap, and the feet stay planted afterwards (0 to 3 px).

The landing does not read as a hard landing:
- **Weak compression.** The body compresses 9 px = 0.06 BH (left centroid 404 to 413 to 401). The source slams belly-down: side silhouette top 394 to 496, which is 0.44 of standing height, held for frames 96 to 114.
- **Small leg bend.** The knees bend slightly at frames 95 to 99.
- **No tail response.** The tail does not react: it already lies flat before contact.

End of clip:
- Frames 118 to 144 are dead, at d 0.2 to 0.3 (1.1 s).
- The end stance against the K-camera standing stance (TK4 frame 0) is IoU 0.974 / 0.984 / 0.979, up from AL1's 0.951 / 0.957.
- Body area is 1.00 to 1.02 of the stance, so nothing grows.

### Air fire-down FD4 (193 frames)

Beats, coupling and aim:
- **Beats through the attack.** Front wing-top period is 27.6 frames, peak-to-peak 0.86 BH.
- **Coupling.** Over the hold (frames 80 to 192), |r| = 0.88 with the wing leading 1 frame. Chest bob is 0.15 BH.
- **Pose stability is good.** Over frames 84 to 152 the jaw (front lowest row) moves 15 px vertically (0.09 BH) and 4 px horizontally. The fire aim is steady while the body rides the beats.

Ends and stability:
- The clip starts on AH4 frame 0 (0.995 / 0.992) and ends on it (0.985 / 0.986 / 0.987).
- Frame 192 is a near-duplicate of frame 0 (0.91 grey).
- Saw is 0.013 / 0.006, and there are no pops.
- Body area stays within 0.80 to 1.08 of frame 0, periodic, so nothing grows.

Remaining issues:
- **Wind-up with still wings.** Over frames 33 to 66 the front wing-top moves only 146 to 162 px, and the left view only 158 to 170. The wings sweep fore and aft (span 188 to 318) but stop flapping vertically for 1.4 s while the dragon holds altitude.
- **Attack silhouette shrinks.** Over frames 84 to 170 the front wing area is 0.38 to 0.48 of frame 0: the wings sit in a narrow edge-on V, so the attack pose's silhouette narrows.
- **No interpenetration.** In the 3/4 view at frames 96 and 124, the near wingtip hangs below the belly without crossing it.

## Five most visible defects (ranked)

1. **AL4 frame 63 to 64 teleport.** The whole body jumps up 35 px (0.22 BH) in one frame, in all views (d 16.4 against 4.0).
2. **RI4 get-up.**
   - The pose blend floats the body about 1 cm with no foot contact for frames 21 to 30.
   - It sweeps a flat wing over the floor at frames 18 to 22.
   - It pops at frame 43 to 44 (consecutive IoU 0.883 against 0.996).
3. **CO4 end pose, which stays on screen for the whole down-state.**
   - It is 0.69 of standing height against the source's 0.47.
   - The far wing is tented, and in the 3/4 view the near wing projects past the snout as a rigid blade.
4. **AL4 is not a hard landing.**
   - It compresses 0.06 BH against the source's 0.44 belly slam.
   - There is no braking flare and the tail does not react.
   - It ends in a 1.1 s frozen hold.
5. **RS4 wing spread.**
   - It is 1.26x idle (2.02 BH) against the approved source's 1.10x (1.82 BH).
   - The two halves differ by 10 points (1.29 / 1.19).
   - The hold buzzes on a regular 4-frame cycle (left saw 0.25).

Secondary issues:
- **Bite.** Frame 50 to 51 recoil twitch; the 3/4 near wing collapses into a hook over frames 44 to 62.
- **Land2.** The hop is 20% lower than the source (0.42 against 0.53 BH). The hind foot leaves the ground with a 17 px one-frame step. The late descent runs at constant speed.
- **Hover.** The downstroke stops at horizontal, the tail is rigid (0.06 BH) and frame 130 duplicates frame 0.
- **Fire-down.** 1.4 s of non-flapping wind-up (frames 33 to 66).
- **Takeoff.** Soft-eased lift-off (1 to 3 px/frame) with no leg push.
- **Chain mismatch.** CO4 breathes but RI4's first 8 frames are frozen.

## What fix round 3 must do (testable)

1. **AL4.**
   - Remove the frame 63 to 64 discontinuity: no step above 2.2x its ±3-frame neighbours, and consecutive IoU ≥0.97.
   - Author a braking flare: span +30% and descent speed -40% over the 12 frames before contact.
   - Author the source's hard landing: body top drop ≥0.3 of standing height within 6 frames of contact, held ≥8 frames, then rise. The tail should whip down or out after contact.
   - Keep the breathing in frames 118 to 144 (d ≥0.4).
2. **RI4 get-up.**
   - Re-author as a sequenced get-up: forelimbs plant and push first, then the hind legs gather, then the wings fold in.
   - Keep at least 2 feet on the floor-contact rows in every frame, with no whole-body float.
   - Remove the frame 43 to 44 pop (consecutive IoU ≥0.97, no step above 2.2x neighbours).
   - Carry the collapse breath into frames 0 to 7 (d ≥0.3).
3. **CO4 end pose.**
   - End front height ≤0.50 of standing (now 0.69). Fold both wings onto the flanks.
   - In the 3/4 view the leftmost silhouette must be ≥x 200 at frame 144 (now 85).
   - Keep the new breathing.
   - Consider a heavier fall: ≥24 frames standing to lying (now 19).
4. **RS4.**
   - Follow the approved source rather than round 2's ≥1.22 target: peak front span 1.10x to 1.15x idle, with the wings raised so height stays ≥1.25x.
   - Halves within 5% of each other (now a gap of 0.10 mean, 0.20 max).
   - Replace the regular 4-frame tremor with a non-periodic one: hold saw <0.15 in the left view, wing-tip high-pass 1.5 to 3 px.
5. **Polish.**
   - Bite: remove the frame 50 to 51 twitch (no d step above 2.2x neighbours) and keep the 3/4 near-wing area ≥0.7 of frame 0 over frames 44 to 62.
   - Land2: raise the hop to 0.5 BH ± 0.05.
   - Hover: extend the downstroke so the tips go ≥0.15 BH below the shoulder line, and add tail lag (tip peak-to-peak ≥0.15 BH).
   - Fire-down: keep a beat of ≥0.3 BH wing-top peak-to-peak through frames 33 to 66.
   - Export the hover loop as frames 0 to 129.

Shippable now as engine Actions: BI4, LA4, AH4, TK4, FD4. Not shippable: RS4, CO4, RI4 and AL4 (the blocker).
