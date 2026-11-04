**Verdict: B is clearly better, and the difference is visible in every trial.** B's ordinary-camera healing presentation is acceptable on this stills evidence, with one threat-framing concern and a live-playback check still open. A is not acceptable.

I inspected `sequence.json` and all 32 images once. As you scoped it, I didn't open anything else, including the shared-brain or wiki pages.

**Phase parity:** the trials start within about 0.05s of each other, and the dragon poses broadly match, such as the wing raise in `A-heal-3-01` and `B-heal-3-01` r5–r6. The differences below are therefore camera differences, not encounter differences.

| Trial | A | B |
|---|---|---|
| 1 | Knight cut at the thigh, sky fills most of the frame, and the weapon is cropped by the bottom edge (`A-heal-1-01` r8). Ground fire is clipped. | Full body and feet, with the ground fire and red floor lines readable (`B-heal-1-detail`). |
| 2 | Feet missing, and the flame path is cut off by the bottom edge (`A-heal-2-01` r1–r2). | Feet planted, the full flame path is on the ground (`B-heal-2-01` r1–r2), and dragon wings and horns are clear (`B-heal-2-detail`). |
| 3 | **A's one advantage:** the whole rearing dragon stays in frame (`A-heal-3-03` r1–r4). The knight is still cut off (`A-heal-3-detail`). | Knight fully readable, but the dragon's head rises behind the boss bar (`B-heal-3-detail`), then leaves the frame, leaving belly and claws (`B-heal-3-03` r3–r5). |
| 4 | The dragon is almost absent, with only tail spikes at the bottom right (`A-heal-4-01` r3–r5). Feet missing. | Tail and body are visible at the right edge (`B-heal-4-01` r1–r4), and the knight is complete (`B-heal-4-detail`). |

**Criteria**
- **Knight and feet:** B shows the feet throughout the drink in all four trials, while A never does.
- **Cup and mouth:** this is effectively a tie, because the knight is the same size in both.
    - Trial 4's profile is the clearest, with the tilted cup at the visor (`A-heal-4-detail`, `B-heal-4-detail`).
    - In trials 2–3 the cup reads closer to the side of the faceplate than its centre, in both versions.
    - The closed helmet means true mouth contact can't be shown.
- **Camera continuity:** I saw no camera cut or snap in either version. A's low framing is there from the first tile to the last, so it's a persistent camera state rather than something the heal triggers.
- **Entry and exit:** both share the same fast weapon transition, about 70ms across three tiles.
    - Entry example: `A-heal-1-01` and `B-heal-1-01`, r2c3 to r3c1.
    - Exit example: `A-heal-1-03` and `B-heal-1-03`, r4c3 to r5c1.
    - This is not a camera difference, and stills can't show whether it feels abrupt.

**Remaining concerns for B**
1. **Dragon head out of frame:** the head is lost late in trial 3, so a head-based attack cue could be missed there. This is the main item to check in live play.
2. **Yellow ground arc:** it appears in trial 3 and passes behind the lower-right HUD (`B-heal-3-detail`). I can't tell from stills whether it's a telegraph or an arena marking, so I'm not calling it a defect.
3. **Foreshortened weapon:** it reads as a bundle in trials 2–3 (`B-heal-2-detail`). A shows the same thing, so this isn't a B regression.
4. **Not established:** continuous motion, camera smoothness and audio.

The fortress presentation looks intact in both versions, and I'm not proposing any change to it.
