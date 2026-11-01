# Every-move replay — first blind review, 2026-11-01

Result: **PASS B**, where B was the new observer-camera replay and A was the existing player camera. Mapping was withheld until the verdict. Both used Shipping source `02e6920c2763b067033a1fadba8e85f9177901246569e4b9ec8337a1e5a6aff9`, the same scripted repertoire and hidden knight. This evaluates inspection framing; it is not a comparison of natural boss AI or gameplay difficulty.

Opus 5.5 high read the anonymous manifest and all 40 per-move sheets. It preferred B overall but retained clear regressions: exposure, roar scale and head visibility in some stagger views. Sampled frames cannot establish continuous motion, exact contact sliding, audio or owner gameplay feel. The critic's wording and timestamps below are preserved as review observations, not independent telemetry.

# Veyr dragon inspection reels: blind comparison of A and B

**Verdict: PASS B.** Reel B is clearly the better inspection reel. Reel A's camera breaks partway through and stays broken, so 12 of the 20 moves can't be inspected. B has its own regressions (listed below), but they are much smaller.

## Files read
I read `sequence.json` and all 40 sheets, `A-01-Idle-01.jpg` to `A-20-Death-01.jpg` and `B-01-Idle-01.jpg` to `B-20-Death-01.jpg`. I opened nothing else.

**Sampling limits:**
- Each move is 15–16 still frames on a 4×4 grid, read left to right, top to bottom. I can't judge motion between frames, timing or contact sliding.
- My only tool was the image viewer, so I couldn't crop or measure pixels. Every scale, brightness and occlusion judgement below is by eye.

## Scores (out of 10)

| Axis | A | B |
|---|---|---|
| Full-body framing and scale across all moves | 3 | 7 |
| Windup / action / recovery readability | 3 | 6 |
| Contacts and limb visibility | 2 | 6 |
| Fire origin and destination | 6 | 6 |
| Wing and flight framing | 3 | 6 |
| Exposure and contrast | 6 | 3 |
| Death readability | 4 | 6 |
| Visual defects | 1 | 6 |

## Move by move

1. **Idle (0.6–6.3s): slightly better in A.** A shoots from low and in front, so the dragon stands out against the sky. B is a dark 3/4 view, but it does show the legs and tail.
2. **Roar (7.5–12.3s): A.** A shows the full wingspan and the raised head clearly. In B the dragon is small and dark, and the wings cover the neck.
3. **Walk (13.4–16.4s): B.** Seen head-on in A, the stride is hidden and the feet sit on the bottom edge of the frame. B's 3/4 view shows the legs moving.
4. **TurnLeft (17.5–19.7s): tie.** A's outline is clearer, but the tail runs off the left edge from 18.78s. B keeps the whole body in frame, but it is dark.
5. **TurnRight (20.7–22.9s): slightly better in B.** A cuts off the tail at the left edge from 20.68–21.55s.
6. **TurnLeftFine (23.9–25.6s): tie.** In A's front view the turn is barely visible. In B a wing covers the back.
7. **TurnRightFine (26.6–28.4s): tie.** Similar trade-offs to TurnLeftFine.
8. **Fire (29.3–32.8s): mixed.**
   - A has the best windup in either reel: the dragon rears at 30.14s and the head glows at 30.48s. But the fire leaves the frame toward the lower left at 30.88–31.68s, so you never see where it lands.
   - B shows the targeting marker on the ground, the fire leaving the mouth, and the burning patch where it lands (30.90–31.70s). The dragon, though, is small and dark.
9. **Flight (33.8–40.7s): B.** A's windup reads well, but from 37.25s A's camera ends up under or inside the dragon. Through the recovery (39.31–40.71s) the frame is just close-up scales, with no readable body. B keeps the dragon whole from above, shows the landing marker and the landing burst at 37.27s, and it lands in frame.
10. **Claw0 to Bite, five moves (Claw0, Claw1, Stomp3, Tail, Bite): all B, by a wide margin.** Stomp2 is covered in item 11.
    - From Claw0 at 41.71s onward, A's camera is stuck in nearly the same low close-up for every attack. Claw0, Claw1 and Stomp2–3 (41.7–57.0s) look almost the same: a wing fills the frame, with no readable claw or foot strike. In Tail (58.0–61.8s) the tail never appears. In Bite (62.8–64.5s) the head is cut off, though some forward movement shows.
    - B frames each attack as a whole body, from the side or behind. Its ground markers line up with the foot or claw: the ring under the stamping foot in Stomp2 (50.37–51.64s), the tail-sweep arc at 58.38–60.07s, and the bite ring at 63.24–63.67s.
11. **Stomp2 (50.0–53.0s): B.** Same reason as item 10.
12. **Stagger0 (65.5–76.1s): B.** A, still in the stuck close-up, shows the head on the ground while the dragon lies exposed (69.55–73.95s), but the body is cropped. B shows the whole collapse onto the belly in profile.
13. **Stagger1–3 (77.1–110.8s): B, but only modestly.**
    - A's sheets are almost identical for all three staggers, the same close-up as Stagger0.
    - B shows the whole body, but its rear camera lets the wings hide the head (Stagger1 at 78.0–87.7s, Stagger3 at 100.3–110.9s), and the collapse is hard to see. This is a real regression in B.
14. **Death (112.0–119.6s): B.**
    - A's first four frames (112.04–113.55s) are still the broken close-up. The camera then drops to ground level, and the body reads as a flat heap with an unclear head.
    - B shows the full fall, from standing at 112.11s through dropping at 114.11–114.62s to the final rest, all in profile.

**Tally:** B wins 12 moves, A wins 2 (Roar, plus a slight edge on Idle), and 6 are ties or mixed.

## Biggest gap in B (testable fix)
**Exposure:** B's dragon is a dark shape on a dark floor in every sheet. The fix: light the dragon (for example a rim or key light on it alone) so its outline clearly separates from the floor in every frame. Then re-check that the hind-limb contacts in Walk and Stomp and the head in the Stagger frames show up without zooming in.

## Other issues in B
- In Stagger1–3, a camera from the rear or the opposite side would stop the wings hiding the head.
- Roar and Fire lose the scale and drama A had. B could use a closer, front-quarter framing for windups that focus on the head.
- Idle, Walk and the four turns are framed small, with a lot of empty floor.

## Shared defect (not counted against either reel)
The wings flare open during the fine turns in both reels (A at 24.01s, B at 24.04s), so this comes from the animation, not the camera.

**PASS B**
