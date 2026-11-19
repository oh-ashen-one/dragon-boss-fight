# Quality goal: state when the owner paused it (2026-11-18, about 23:30 ET)

The owner asked, about ten hours in, to stop after the milestone in progress, install a playable build and see a clear
before and after. This is that record. The goal (`QUALITY_GOAL.md`) is NOT met: phases C to F and the sound half of
phase B never reached the engine.

## What you can play

Play Veyr.app opens `~/Applications/Veyr/a20c600691d1` (source id `956518d5...`, commit `ff0fecf` on
`fable/quality-goal-20261118`). Earlier builds are kept beside it: `f161bd1e566e` (phase A only) and `652188ae51a3`
(2026-11-06). Before/after clips: `http://localhost:8823/progress.html` (`python3 serve.py 8823` in
`Local/playtest-goal-review/` if the server is down).

## In the installed build, measured

| Change | Before | After | Restore switch |
|---|---|---|---|
| Knock-down: time on the floor | 5.8-9.3 s | 4.9 s (35 knock-downs measured); the head stays vulnerable through the first 40 % of the rise | `-VeyrLegacyKnockdown`, `-VeyrNoRiseHeadBonus` |
| Foot mesh pinched out in mirrored strike clips | toe stretched up to 15 m in live play | 14 cm | `-VeyrLegacyMirrorToe` |
| Dragon floating | planted soles 25.5 cm above the floor (median), worst clip 68 cm; some clips sank a metre below | 0.0 cm, 67 of 67 ground clips within 3 cm | `-VeyrNoDragonGrounding` |
| Camera inside the dragon, close-range test | 343 of 9,476 frames inside; knight whole on screen 78.8 % | 0 of 8,246; 99.0 %; the see-through effect is off | `-VeyrLegacyCameraBoom`, `-VeyrLegacyCameraFraming`, `-VeyrLegacyCutThrough` |
| Dust and debris when the dragon touches the ground | none | pale dust at every footfall and stomp, a large cloud with debris on falls and landings | `-VeyrNoContactDust` |
| Camera shake | stomp, tail and landing only | every contact, scaled by speed and distance (footfall about 0.5 degrees, falls 3.5) | `-VeyrLegacyWeightShake` |
| Dragon's reaction to a sword hit | head and neck 2-6 degrees, small glint | spine flinch about 7 degrees, flash on the mesh, sparks and a puff | `-VeyrLegacyFlinch`, `-VeyrNoMeshFlash`, `-VeyrLegacyHitBurst` |
| Weapon trail | a 3.5 cm line of cards | a soft ribbon along the blade, 0.22 s | `-VeyrLegacyTrail` |
| Heavy hits and being hit | hit-stop only | short slow-motion tail, zoom punch, camera kick | `-VeyrNoSlowTail`, `-VeyrNoZoomPunch`, `-VeyrNoHurtKick` |

`-VeyrLegacyFeel` turns all the weight effects off at once.

Difficulty: boss health is unchanged (845) and no hitbox was touched. Sixteen seeds per grip on the phase A package:
one-hand 15 of 16 wins inside 150 s (one win at 175 s), median 84.3 s; two-hand 16 of 16, median 72.3 s; a passive
player dies in 7.5-12.3 s. Not re-measured on 16 seeds after the weight effects were merged; the regression wins on
the installed build took 95 s and 83 s.

Regression on the installed build: controls, full intro, showcase 20/20, death and restart, victory and restart in
both grips all pass. Frame cost of the weight effects: 17.17 ms mean against 16.86 ms.

## Known wrong in the installed build

- **The camera can still look through the dragon in a real fight.** When the dragon is knocked down with the knight
  beside it, the camera sometimes ends up looking at pale, faceted dragon surfaces or loses the knight. The close-range
  test did not cover this. A third pass was written (`origin/fable/quality-goal-A123-milestone`), tried once at the end
  and failed by eye on the second knock-down, so it is not in the build. The camera also jumps occasionally.
- The left front paw looks like a blunt block when it lifts (it rides on one bone with no toes), and the wing roots
  stretch during take-off. Diagnosed with numbers; not fixed.
- The dust is smaller than the reference's relative to the creature, the trail narrower, the flinch small.
- Blind reviews: see `REVIEWS.md`. After phase A the reference game was still rated better on all six aspects.

## Written, compiled, reviewed, never run in the engine

Each is on its own branch, with its own restore switches, and waits for engine time in this order:

| Piece | Branch | What it is |
|---|---|---|
| Camera third pass | `fable/quality-goal-A123-milestone` | No raised top-down views, sight lines through the whole body, camera audit in every replay mode |
| Sound | `fable/quality-goal-Baudio` | Several recorded variants per cue, dragon footsteps, breathing and per-move sounds, knight footsteps from foot contacts. 116 Freesound recordings and 26 generated takes are staged in `Local/AudioSources20261118/staged/`; old and new can be heard at `http://localhost:8823/audio.html` |
| Picture | `fable/quality-goal-C` | Lumen, virtual shadow maps, auto exposure, motion blur, relit courtyard, controls box hidden |
| Camera for a giant | `fable/quality-goal-D` | Lock-on that slides from the chest to the striking limb, camera life, framing measurements, sizes 2.5x and 3x |
| New knight | `fable/quality-goal-E` | Greystone code path, retarget and motion-matching scripts; both asset packs are already on this Mac |
| Dragon playback | `fable/quality-goal-F` | Clips at their own speed, two-clip fades, four-foot lock |

## Spend

0.13 USD on fal.ai sound effects (37 takes). No video was generated.

## To continue

`QUALITY_GOAL.md` is still the brief; `LEDGER.md` has every step and agent result; `BUILDER_RULES.md` the working
rules. One engine process at a time made the engine the bottleneck: about ten hours covered phase A and half of B.
