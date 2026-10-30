# Critique round 5: Veyr knight, RollAttack and blinks (2026-10-30)

**Blind critique from videos only.** Sources: the 24 clips in
`Local/knight-review-20261028/serve-round5/media/`, measured frame by frame with ffmpeg and pixel
scripts (CPU only). I did not read HANDOFF, plans, metrics JSON, commit messages or implementation
notes. The page captions were visible on the review page. I treated them as claims and did not use
them as evidence.

Frame numbers are 0-based video frames (`rt-*` RollAttack: 64 frames; `rt-*` blinks: 40 frames).
The views are, in order: P0 front, P1 side, P2 three-quarter.

## Scale and thresholds

- **RollAttack:** the floor checker repeats every 53 px along a screen row in the front and side
  views at every depth. The camera is orthographic. 53 px = 2 tiles = 50 cm, so the scale is
  **0.94 cm/px**. Floor depth is foreshortened to about 6-8 px per tile vertically, which gives an
  elevation of about 15 degrees. Vertical screen motion of a foot is therefore about 0.96 times
  its height change.
- **Blinks:** the same autocorrelation gives 46 px per 2 tiles in the front view, about
  1.0-1.1 cm/px. This does not match the page's 0.93 cm/px. My centimetre figures for the blinks
  use about 1 cm/px.
- **Round-4 thresholds at 1.5x:**
  - Foot motion: 2 px becomes **3 px**.
  - Near-ground band: 8 px becomes **12 px**.
  - Sword speed: 25 px/frame becomes **37.5 px/frame**.
- **rt-RollAttack camera:** I measured the floor with block matching and the floor-plane edge. The
  camera tracks the root until frame 23 and is fixed from **frame 24** onward. All absolute foot
  checks below are from f24 onward, except the roll landing, which I corrected for the
  floor-edge shift.

## Scores

| Row | AFTER r5 | BEFORE r4 | Verdict |
|---|---|---|---|
| RollAttack | **7** | **3** | BETTER |
| BlinkLeft | **6.5** | **5** | BETTER |
| BlinkLeftTwoHand | **6.5** | **5** | BETTER |
| BlinkRight | **7.5** | **5** | BETTER |
| BlinkRightTwoHand | **7.5** | **5** | BETTER |

### RollAttack

- **AFTER, 7.** The rear foot is locked from f24 to the end: in the side view it sits at x402-440
  with its bottom at 531 (0-1 px change), and in the 3/4 view at x371-391, bottom 532.
  - The front foot rises in place at f39-40 with no horizontal motion. It then travels back
    65 px (3/4 view) over f41-48 while its sole is 14-20 px above the local ground. It sets down
    vertically at f48-50 with 0 px horizontal change.
  - The blade centroid stays at or below 31 px/frame in the 3/4 view after f41.
  - The settle is clean: everything is still from f50 (under 2 px/frame), and f51-63 are
    pixel-identical to round 4's idle.
  - It loses points for the mid-swing floor tap at f27 and the back-loaded torso straighten
    (see the defects).
- **BEFORE, 3.**
  - At f38-42 (3/4 view) the front foot slides 56 px back with its sole only 3-11 px off the
    floor.
  - The rear foot drifts x344 to x371 (27 px, about 25 cm) between f30 and f47 while in contact.
  - The 3/4 blade centroid reaches 81.9 px/frame at f43 (54.6 px at round-4 scale; my
    predecessor measured 47).

### Blinks

- **BlinkLeft and BlinkLeftTwoHand, AFTER, 6.5.**
  - **Toe-off is present.** On push frame f14 (side view) the sole is pitched heel-up by about
    20 px over 30 px of foot length. Round 4 is flat on the same frame.
  - **Reappearance dips are gone.** At f20 and f23 the lowest foot point is at rest level in all
    three views (round 4 dipped 3-5 px there).
  - **But:**
    - The toe tip goes 4-5 px (about 4-5 cm) below the planted sole line on f13-14: 404/403 px
      against a rest of 399 in the side view, and 398 against 394 in the 3/4 view.
    - Lateral foot position does not change (front view x stays within 2 px), so this is the
      toe sinking into the floor during the heel pivot.
    - f14 is a new dip in round 5. f13 was already dipped in round 4.
- **BlinkLeft and BlinkLeftTwoHand, BEFORE, 5.** There is no toe-off: on f13-14 the feet stay
  flat and locked while the body leans. The foot dips below the floor at f13 (+5 px, side view)
  and on reappearance at f20 and f23 (+3 to +5 px).
- **BlinkRight and BlinkRightTwoHand, AFTER, 7.5.** The trailing foot pitches toe-down on f14 in
  the front and 3/4 views, a visible heel lift that round 4 lacks. The lowest point never drops
  more than 2 px below rest on push frames. Reappearance frames f20-39 are locked to 1 px with no
  dip.
- **BlinkRight and BlinkRightTwoHand, BEFORE, 5.** The feet stay flat through the push. The foot
  dips 3-5 px below rest on reappearance frames f20 and f23 (front 385/386, side 404, 3/4 399
  against rests of 383/399/394).

### Blink regression checks

- **Crouch depth, upper body, moving tail (cape) and sword:** unchanged. Every r5-r4 pixel
  difference lies below about y250-300 (legs and waist). Body-top y is identical on every frame.
- **Seams:** idle frames 0-9 and 24-39 are pixel-identical to round 4.
- **Feet outside the push frames:** locked within 1-2 px in every view.

### RollAttack regression checks

- **Roll (f0-12):** identical to round 4.
- **Roll landing (f17-23, front view, corrected for camera):** the feet are planted within about
  2 px.
- **Strike reach:** unchanged. The 3/4 blade x-max is 745-751 against 741.
- **Lunge stride:** unchanged. The front foot plants at the same spot as round 4 (3/4 x494-520).
- **Lunge depth:** about 6 px (about 6 cm) shallower at f38-39 (head y 330 against 336), because
  the rise starts one frame earlier. This is minor.
- **Blade clipping:** none seen at this resolution, but it cannot be proved from these renders.
- **Blade in frame:** the whole blade stays in frame in all 64 frames and all three views. The
  blade mask never touches a panel edge.

## Round-4 veto and spec items

1. **rt side view f41-50: no foot moves more than 3 px while within 12 px of the ground. MET.**
   - Rear foot: 0-1 px.
   - Front foot: 0 px horizontal at lift-off (f39-40) and 0 px at set-down (f48-50). Every
     horizontal move happens at 13-20 px of clearance. The tightest point is f47 to f48 in the
     3/4 view: 7 px of travel at 14 px clearance.
   - Caveat: in the side view the front foot is hidden behind the rear leg from f45 to f49. I
     measured those frames in the 3/4 view instead.
2. **Lunge-to-stand recovery spread over at least 8 frames. MET.**
   - Front foot: f39 to f50 (11 frames).
   - Head: moves f39 to f50 at 7-20 px/frame.
   - Hip band: 4-8 px/frame over f39 to f49.
3. **Sword at most 37.5 px/frame after f41 (3/4 view). MET.** The maximum is 31.1 px/frame at f45.
   The front view peaks at 35.8 at f42, also under.
4. **Whole blade in frame. MET** in every frame and every view.
5. **Round-4 rear-foot drag (about 14 cm) and lunge heel slide (about 14 cm). FIXED.**
   - The rear foot is locked from f24.
   - The lunge foot travels lifted (13 px clearance at f28-30). It lands vertically at f30-32:
     x494-534 constant in the side view, and the sole drops 508, 516, 520.
6. **Secondary, blink toe-off. MET.** A heel lift is visible on push frame f14 in all four blinks.

## Five most visible remaining defects (ranked)

1. **RollAttack, rt three-quarter, front and side views, frame 27.**
   - The lunge swing foot touches down mid-stride. It is lifted at f25-26 and f28-30, but at f27
     its sole is at or 0-4 px below floor level: 3/4 bottom 535 against a local ground of about
     531-535, and side bottom 527 against an estimated 522.
   - At the same time it moves about 25-29 px/frame forward, which is about 25 cm of floor
     contact in one frame.
   - It reads as a one-frame scuff or tap in the middle of the lunge step.
2. **BlinkLeft and BlinkLeftTwoHand, rt side and three-quarter views, frames 13-14.** The toe
   sinks 4-5 px (about 4-5 cm) below the planted sole line during the heel-lift pivot (side
   404/403 against 399, 3/4 398 against 394). The pivot is about the ball of the foot, not the
   toe tip. BlinkRight does not show this.
3. **RollAttack, rt side view, frames 45-50.**
   - The torso straightening is back-loaded. Head speed is 7-9 px/frame over f39-45, then
     14, 20, 17 px/frame at f46-48, then stops through 9.8, 2.3 and 0.1 px/frame by f50.
   - The deceleration into idle takes 2 frames, against 5 in round 4.
   - The hip band also reverses about 6 px (x449 to x455) at f47-49.
   - The result is a slight "arrive and stop" into the idle.
4. **All blinks, push frames 13-14.**
   - The toe-off exists for only 2 frames before the knight vanishes, so it reads only when
     stepping through frames.
   - The leading foot's lift is barely measurable in the side view (BlinkRight side-view profiles
     are within 1-2 px of round 4).
   - The push still reads mostly as an upper-body lean.
5. **RollAttack, rt side view, frames 38-39.** The lunge is held about 6 px (about 6 cm) higher
   than round 4 because the rise begins at f39. The strike's low hold is slightly less committed.
   This is minor.

## Verdict

**SHIPPABLE**, with notes, for the Blender set. This judges only the rows changed in round 5,
against the round-4 veto; the other rows were judged shippable in round 4 and are unchanged here.

- RollAttack meets every round-4 acceptance item by measurement, and the round-4 veto is lifted.
- No blink regressed in crouch depth, upper body, tail or seams.
- Defects 1 and 2 are real, measurable floor contacts, but each lasts 1-2 frames inside fast
  motion. They should be fixed in the next pass, and they do not reach the multi-frame severity
  of the round-4 veto:
  - **Defect 1 test:** in rt-RollAttack 3/4 view f25-30, the swing-foot sole stays at least 8 px
    above the interpolated local ground on every frame.
  - **Defect 2 test:** in rt-BlinkLeft side view f13-14, the lowest foot pixel is no more than
    1 px below the rest sole line (399).
