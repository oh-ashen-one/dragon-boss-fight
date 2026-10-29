# Veyr knight round 1: independent critique (critic round 2, 2026-10-28)

Reference: the Can It Code UE 5.8 boss-fight hero (z1mgtUvTdqg). It is a shipped-quality, weighty, readable third-person melee hero.

I did not read the builder notes, HANDOFF, docs or commit messages. I read the round-0 critique only after I had fixed my own scores.

## Evidence and method

- **Pixels.** I extracted all 41 round-0 and round-1 review videos to every frame. That is 1080x360 at 30 fps, as three 360 px panels: front, side and three-quarter. I also looked at zoomed crops and contact sheets, and at the in-game PNGs.
- **Joint data.** I evaluated the exact GLBs the game imports with my own glTF forward-kinematics evaluator, not the builder's measure scripts. Files:
  - round 1: `Local/CustomuseAssets/Knight20261029/knight/*`
  - round 0: `Knight20261028/knight/Mixamo_*_v2`, `Polish20261025/idle-joins/knight/Backpedal_Blender_loop_v1r3`, `Polish20261025/overhaul-v028/knight/Sourced_Blink*_Transit_v2`, `Sourced20261025b/knight/Sourced_RollAttack_v2`
  - reference idles: `Polish20261025/knight/IdleOneHand_Blender_v2r4` and `IdleTwoHand_Blender_v2r4`
- **Units.** Game cm are joint metres times 240. Mesh axes: +Z is forward (toward the boss), +X is the knight's left, Y is up.
- **Sword tip.** WeaponSocket at (0, 2.35, 0). The socket scale is 0.41, so the blade is about 275 game cm.
- **Clip rates.** These are the in-game clip-time rates, taken from game code and the v030n import plan:
  - strafe: 1.2 (capsule 1.2 x nominal)
  - sprint strafe: 1.1 (440.2 x 1.1 = 484 cm/s)
  - backpedal: 1.668 (100 cm/s)
  - blink: 1.15
  - roll attack: 1.282
  - stagger: 1.1667, or 1.6111 for back
- **Foot contact.**
  - Stance is the toe within 2 cm of its minimum height.
  - Per-stance drift is the world-space range of the toe while planted, with the capsule travel added back.
  - For blinks I added the authored root trajectory, with mesh scale 2.4 (122.3 rig-cm maps to 298.6 game cm, per the replay).
- **Carry.** I measured the angle of the blade axis (socket +Y) at the first and last frame against the grip-matched idle frame 0. Tip offset is in cm.
- **Facing.** Chest yaw is taken from the shoulder line and pelvis yaw from the hip line. Knee-bend yaw is the knee offset from the hip-ankle line. For all three, 0 is toward the boss, + is the knight's left and the idle measures 0.0 deg.

## Scores (round 1, 1-10)

Axes: W = weight, R = readability, C = foot contact, Wp = weapon handling, T = transition (seams, entry/exit, joins), S = silhouette.

| Row | W | R | C | Wp | T | S | Verdict | Biggest measurable gap (builder instruction) |
|---|---|---|---|---|---|---|---|---|
| Roll attack | 5 | 6 | 3 | 6 | 5 | 6 | FAILS | Exit skate: the front (left) foot slides 84 cm back (z 85 to 1) in f45-f51 (0.23 s) with the toe 1.0-3.3 cm off the floor. That is about 360 cm/s of planted skate. Make it a lifted recovery step (toe at least 8 cm up while moving), or hold the lunge and add root motion so planted drift is 5 cm or less. The join is f24-f30 (6 frames, 0.20 s); lengthen it to at least 8. |
| Blink left | 3 | 4 | 2 | 7 | 4 | 4 | FAILS | Visible-window skate: during the 0-0.18 s and 0.34-0.58 s visible windows the root moves about 47 cm/s while the sprint cycle's stance feet run at 357-435 cm/s. Author a 3+ frame crouch-load and push-off, and a planted landing (5 cm or less of drift). Alternatively, move 85% or more of the stance-foot speed onto the root in visible frames. |
| Blink right | 3 | 4 | 2 | 7 | 4 | 4 | FAILS | Same skate (370-410 cm/s). Chest yaw is +67 deg, against -66 deg for blink left (a 133 deg facing flip between the pair). Its knees point toward the knight's left (+67..+88 deg) while it travels right, so it is a backward sprint. |
| Backpedal 1H (guard) | 6 | 5 | 8 | 5 | 8 | 5 | APPROACHES | The guard does not read. Blade pitch is 13.3-14.4 deg against 7.6 deg in the idle (+6.5 deg). The tip is 30 cm higher (178 vs 148 cm) and still points forward at hip height. Raise the blade at least 25 deg above the idle pitch, with the tip at 220 cm or higher, across the body. |
| Backpedal 2H (guard) | 6 | 6 | 8 | 7 | 8 | 6 | APPROACHES | Present. Carry is 4.9 deg from the 2H idle (tip 15.5 cm), so the "guard" is the 2H carry itself. Add a distinct guard beat: blade pitch at least 15 deg off the idle, or forward-angled. |
| Strafe L 1H | 6 | 5 | 8 | 6 | 4 | 5 | APPROACHES | Entry pop. Chest yaw is -74 deg and the hips are 104-112 cm, against the idle's 0 deg and 131.8 cm. Entering or leaving lock-on is a 74 deg torso turn plus a 24 cm head drop inside a 0.10 s blend. Author the chest within 30 deg of the boss and the hips within 10 cm of the idle, or add a 0.30 s enter/exit blend. Carry is 13.9 deg (1.1 deg inside the limit). |
| Strafe R 1H | 6 | 6 | 8 | 6 | 4 | 5 | APPROACHES | Same entry pop (chest -70 deg, hips -15..-26 cm). Carry is 13.7 deg. |
| Strafe L 2H | 6 | 5 | 8 | 7 | 4 | 6 | APPROACHES | Same entry pop (-74 deg). Carry is 6.5 deg. |
| Strafe R 2H | 6 | 6 | 8 | 7 | 4 | 6 | APPROACHES | Same entry pop (-70 deg). Carry is 6.8 deg. |
| Sprint strafe L 1H | 5 | 4 | 8 | 6 | 5 | 5 | APPROACHES | It is a backward sprint: chest -66 deg and knees -67..-88 deg, opposite the +X travel, at 484 cm/s. Stance width at the ends is 33 cm against 62 for the idle. Re-source the clip so the knee-bend yaw is within 45 deg of the travel direction. |
| Sprint strafe L 2H | 5 | 4 | 8 | 7 | 5 | 5 | APPROACHES | Same as sprint strafe L 1H. Carry is 6.4 deg. |
| Sprint strafe R 1H | 5 | 3 | 8 | 6 | 2 | 4 | FAILS | The mirror flipped the facing. Chest yaw is +67 deg against -70 deg for strafe-R walk, so every Shift tap flips the torso 137 deg in 0.10 s. Against sprint L the flip is 133 deg. It is also a backward sprint (knees +67..+88 deg). Rebuild it so the chest is within 20 deg of strafe-R walk and the knees point toward travel (-90 +/- 45 deg). |
| Sprint strafe R 2H | 5 | 3 | 8 | 7 | 2 | 4 | FAILS | Same as sprint strafe R 1H. Carry is 8.6 deg. |
| Stagger front 1H / 2H | 5 | 5 | 9 | 4 | 6 | 5 | APPROACHES | The head travels 66.4 cm by f7: 52.3 cm back and 39.3 cm toward the knight's right, which is 37 deg off the hit axis. The tip whips 74.6 / 84.0 cm per frame (2240 / 2520 cm/s) at f3 and the blade rises to 42.6 deg. Make 80% or more of the head displacement fall on -Z, and cap the tip at 40 cm per frame or less. The 2H f1 starts 13.4 deg / 60.6 cm off the idle carry. |
| Stagger back 1H / 2H | 6 | 7 | 9 | 7 / 6 | 7 | 6 | APPROACHES | The head moves 29.0 cm (24.8 forward, 13.8 down) and the feet drift 1.7 cm. The 2H tip whips 47.0 cm per frame at f1. Cap it at 40 or less and give the hit 2-3 frames of anticipation, which is 0 today. |
| Stagger left 1H / 2H | 4 | 5 | 9 | 4 | 6 | 4 | APPROACHES | The peak silhouette reads as an overhead wind-up: the tip is flung to 328 cm high, with blade pitch 55.2 deg at 0.23 s. Keep the head at 45-55 cm (51.3 today) but hold the blade pitch at 25 deg or less and the tip at 220 cm or lower. The 1H f1 starts 10.8 deg / 42.3 cm off the idle carry. |
| Stagger right 1H / 2H | 4 | 5 | 9 | 4 | 6 | 4 | APPROACHES | This is the mirror of stagger left: head 53.9 cm, tip to 326 cm, pitch 47.2 deg. Apply the same fix. |

I did not re-review the unchanged, owner-selected rows: walk, run, light attack, roll, grip to two hand, grip to one hand, and the run-to-RunStop join. Round-0 verdicts stand for those.

**No row MEETS. Overall verdict: FAILS the shipped bar.**

### Supporting measurements (round 1, with round 0 in brackets)

- **Carry at the first and last frame, deg:**
  - strafe 13.9/6.5/13.7/6.8 [63.7/30.8/63.7/30.8]
  - sprint strafe 10.7/6.4/10.7/8.6 [53.3/28.3/75.2/36.0]
  - backpedal 6.9 / 4.9 [2.7 / 67.2 for the 1H fallback in 2H]
  - blink 10.9/10.9 [53.3/75.2]
  - staggers end 0.0, start 1.5-13.4 [27.1-60.8]
  - roll attack end 0.0 [78.4]
- **Ankle distance at the ends (idle 61.9 cm):**
  - staggers 61.9 [123-151]
  - backpedal 61.8 [69.1]
  - strafe 47.5-50.1 [113.3]
  - sprint strafe and blink 32.0-33.5 [33.5]
  - roll-attack end 61.9 [123.2]
- **Loop seams:** 0.00 cm pose delta on every loop. The velocity jump at 120 Hz is 1.06 cm/sample at most in round 1 [2.89 in round 0].
- **Per-stance toe drift:**
  - strafe walk 2.3-4.5 cm lateral, 1.2 cm or less fore-aft (legs identical to round 0)
  - sprint strafe 2.4-4.0 cm [4.4-8.7]
  - backpedal 2.8 cm or less fore-aft
- **Toe stance speed per clip-second against the nominal:**
  - SRL 446/427 against 440.2
  - SRR 436/435 against 440.2
  - strafe L 139 against 138.4
  - strafe R 161 against 155.5
  - backpedal 58-60 against 59.95
- **Roll-attack tip:**
  - Round 0: the splice is at f24-f25, with step 64.4 then 207.6 cm/frame and acceleration 166.7 then 204.9.
  - Round 1, f24-f29: steps 9.1, 14.3, 37.1, 67.2, 90.7, 91.4 cm/frame, with acceleration 45.0 or less.
  - Round 1 peak acceleration is 124.8 at f31, the windup apex. The source strike itself reaches 117.6.
- **Stagger head peak, cm:**
  - front 66.4 [56.0]
  - back 29.0 [33.9]
  - left 51.3 [24.3]
  - right 53.9 [24.3]
  - The peak comes at about f7 (0.23 s) in every direction and recovers by f15-f18.

## The five round-0 fixes

1. **Blink left/right direction and mapping: PASS on direction; the legs fail.**
   - Slot BlinkLeft maps to `Knight_BlinkLeft_v3` (v030n plan, `VeyrKnight.cpp` TryBlink).
   - The body's stance feet move -X, so it travels +X (left). The root goes +122.3 rig-cm (298.6 game cm left per the replay). BlinkRight is exactly negated.
   - Both are backward-facing sprint cycles (chest -66 / +67 deg), with 357-435 cm/s skate in the visible frames.
2. **Roll-attack join: PARTIAL.**
   - The splice is gone (peak tip acceleration in the join went from 204.9 to 45.0 cm/frame²), and the clip ends exactly in the 1H carry (0.0 deg).
   - The join is still only 6 frames (0.20 s), against 8 asked for.
   - It adds a new 84 cm planted front-foot slide at the exit and a 7.9 cm hand-to-handle slip (hand-socket distance ranges 7.0-17.8 cm, against 14.9 at idle; round 0 was 15.1-17.8).
3. **Sprint-strafe-right travel axis: PASS on axis, FAIL on facing.**
   - Stance velocity is 0.0 deg off lateral and drift is 3.9 cm or less.
   - The round-0 clip was already lateral in mesh space (0.7 deg off, measured). The round-0 "22 deg off forward" came from the per-clip-facing render. That clip was a forward run with the chest at -86 deg.
   - The mirror "fix" turned it into a backward sprint whose chest flips 137 deg from strafe-R walk.
4. **Two-hand backpedal present: PASS. Guard readable: FAIL for 1H, marginal for 2H.**
   - The 1H blade rises only +6.5 deg (the page claims 27 deg; I could not reproduce that). The tip is +30 cm, still at hip height and forward.
   - The 2H guard is the 2H carry, 4.9 deg off.
   - Forward lean is +17 cm at the head, against the round-0 loop (head z 4 to 21 cm; the page claims +7.0 cm).
5. **Pose continuity and stagger head amplitude: carry PASS, stance PARTIAL, amplitude PASS.**
   - Carry is within 15 deg on all 21 round-1 clips (worst 13.9 deg).
   - Feet are within the idle stance width for staggers, backpedal and the roll-attack end. Blinks and sprint strafes are 28-30 cm narrow at their ends, and strafe walk is 12-14 cm narrow.
   - Left/right stagger head amplitude rose from 24.3 to 51.3 / 53.9 cm (2.1-2.2x).
   - The page says staggers "start in the idle pose". f1 is 10.8 deg / 42.3 cm off (1H left) and 13.4 deg / 60.6 cm off (2H front), so the claim is false for f1. The end frames are exact.

## Pipeline defects (separate)

1. **The weapon socket is a root child (VeyrRoot to WeaponSocket), not a hand child.**
   - Every blend interpolates the hand and the sword independently.
   - Measured hand-grip slip is 7.9 cm in the new roll-attack join. All 0.10 s engine transition blends carry the same exposure.
2. **The mirror pipeline mirrors facing, not just travel.**
   - The blink-right and sprint-right "true mirrors" flip the chest from -66 to +67 deg.
   - This is the source of the 133-137 deg flips.
3. **The lateral locomotion family is side-on.**
   - All strafes, sprint strafes and blinks hold the chest 66-74 deg off the boss. Three of the six lateral clips are backward gaits (strafe L, sprint L, sprint R).
   - The idle is at 0 deg, so every lock-on enter and exit is a 66-74 deg torso pop in 0.10 s. Every stagger taken while strafing is also a 70 deg pop, because the staggers are baked on the idle, not additive at runtime.
4. **Grip-agnostic actions.**
   - Blink and RollAttack have only 1H clips (TryBlink picks `BlinkLeft`/`BlinkRight` regardless of grip).
   - From 2H, the carry snaps from 68 deg blade pitch to 7 deg and the left hand releases.
5. **The in-game evidence is unusable for contact or performance.**
   - The screenshots crop the knight at or above the waist; the blink departure/arrival shots show only the shoulders.
   - The page states the capture ran at about 15 fps under GPU contention.
   - Foot contact, blink travel and performance are therefore unproven in game. Only clip selection is shown.
6. **Review-page claims I did not reproduce:**
   - "blade raised 27 deg": measured about 7 deg against the round-0 loop and 6.9 deg against the idle
   - "+7.0 cm head lean": measured +17 cm
   - "starts ... in the idle pose" (staggers): f1 is up to 60.6 cm off at the tip
7. **Round-0 measurement artifacts that drove round-1 work:**
   - Sprint-strafe-right "wrong axis": it was lateral in data (0.7 deg).
   - Sprint strafe L "312 cm/s vs 411": the toe stance speed was 427-446 cm/s per clip-second.
   - Both readings came from a pixel scale and per-clip render facing. The round-1 fixed-facing renders resolve this, but the sprint-right "fix" was unnecessary and harmful.

## Ranked top-5 remaining fixes

1. **Sprint strafe right 1H/2H.**
   - Replace the mirrored clip with a right sprint whose chest yaw is within 20 deg of strafe-R walk (-70 deg). Today it is +67 deg, a 137 deg flip on every Shift tap.
   - Its knee-bend yaw must be within 45 deg of the travel direction (-90 deg). Today it is +67..+88 deg, a backward sprint.
   - Keep the stance drift at 4 cm or less.
2. **Blinks.**
   - Bring the visible-window stance skate from 357-435 cm/s down to 60 cm/s or less. Either author a crouch-load of 3 or more frames (hips 10 cm or more down), a push-off and a planted landing, or put 85% or more of the stance-foot speed on the root while visible.
   - Start and end at idle stance width (62 +/- 10 cm, today 32-33.5) and chest yaw within 20 deg of the boss (today -66 / +67).
3. **Roll-attack exit.**
   - Remove the 84 cm planted front-foot slide in f45-f51. Use a lifted step (toe at least 8 cm up), or add root motion so planted drift is 5 cm or less.
   - Lengthen the join from 6 to 8 or more frames.
   - Parent the sword to the hand, or lock the hand to the socket, so grip slip is 2 cm or less (7.9 cm today).
4. **Lock-on posture continuity.**
   - Strafe walk enters at chest -70..-74 deg and hips 20-28 cm below the idle, inside a 0.10 s blend.
   - Author the strafes so the chest is within 30 deg of the boss and the hips within 10 cm of the idle, or give lock-on enter/exit a 0.30 s or longer blend. Measure f0 against the idle.
5. **Staggers.**
   - Cap the sword-tip speed at 40 cm/frame or less (53.7-84.0 today) and the blade pitch at 25 deg or less (42.6-55.2 deg today, with the tip up to 328 cm, which reads as an attack wind-up).
   - Put 80% or more of the front stagger's head displacement on -Z (today 52.3 back and 39.3 lateral).
   - Keep the left/right head amplitude at 45-55 cm.

Secondary:

- Raise the 1H backpedal guard blade 25 deg or more above the idle pitch (+6.5 deg today).
- Author 2H blink and roll-attack variants, or a pre-blend to 1H.
- Re-shoot the in-game evidence with the full body in frame at 30 fps or better.

## Round 1 against round 0, per row

Mean of the 6 axes. The round-0 numbers are the previous critic's AFTER scores, so the methods differ:

- My T axis penalises entry/exit facing and hip pops, not just seams.
- My C axis uses 3D toe drift plus the root trajectory, not pixel blobs.

| Row | Round-0 critic | Round 1 (this critique) | Delta | Note |
|---|---|---|---|---|
| Roll attack | 4.67 FAILS | 5.17 FAILS | +0.5 | splice fixed, exit skate added |
| Blink left | 4.83 APPROACHES | 4.00 FAILS | -0.8 | legs identical to round 0 (same per-joint accelerations); carry 53 to 11 deg; skate now measured in visible windows |
| Blink right | 3.83 FAILS | 4.00 FAILS | +0.2 | direction fixed; backward-facing mirror |
| Backpedal 1H | 5.17 APPROACHES | 6.17 APPROACHES | +1.0 | lean added; guard too small |
| Backpedal 2H | none (1H fallback, carry 67 deg snap) | 6.83 APPROACHES | new | |
| Strafe L 1H | 5.67 | 5.67 | 0.0 | carry 64 to 14 deg gained; entry pop scored |
| Strafe R 1H | 5.83 | 5.83 | 0.0 | as Strafe L 1H |
| Strafe L 2H | 6.00 | 6.00 | 0.0 | |
| Strafe R 2H | 6.33 | 6.17 | -0.2 | |
| Sprint strafe L 1H | 5.50 | 5.50 | 0.0 | drift 6.4 to 4.0 cm |
| Sprint strafe L 2H | 5.67 | 5.83 | +0.2 | |
| Sprint strafe R 1H | 4.33 FAILS | 4.67 FAILS | +0.3 | axis was never wrong in data; facing flip added |
| Sprint strafe R 2H | 4.50 FAILS | 5.00 FAILS | +0.5 | |
| Stagger front | 5.33 | 5.67 | +0.3 | |
| Stagger back | 5.67 | 7.00 (1H) / 6.83 (2H) | +1.3 | |
| Stagger left | 4.83 | 5.33 | +0.5 | |
| Stagger right | 5.83 | 5.33 | -0.5 | wind-up silhouette, tip whip 54 cm/frame |

**One line:** Round 1 improved on round 0 by about +0.2 mean per changed row (range -0.8 to +1.3). The weapon-carry continuity gain is large: worst first/last-frame carry fell from 75.2 to 13.9 deg. Stagger stance and amplitude are fixed, and so is the roll-attack splice. It is offset by new regressions: sprint-strafe-right and blink-right flip facing 133-137 deg, and the roll-attack exit has an 84 cm foot slide.
