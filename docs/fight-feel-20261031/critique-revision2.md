# Revision 2 blind review

Opus 5.5 high, returned identity verified. Same-package legacy revision 1 versus revision 2; contact-position/facing diagnostics included without version identity.

**VERDICT: A**

I judged everything by eye from the sheets and the 1280×720 detail frames. I had no pixel-cropping tool, so the frame coordinates below are estimates, not measurements.

**Scores (impact / contact clarity / camera readability / motion coherence)**
- **A:** 3 / 5 / 7 / 6
- **B:** 6 / 4 / 3 / 5

**Light leg (contact 1)**
- **What matched:** position difference was 0.63 cm and facing 0.09°, but the dragon state was not the same.
- **A:** The camera sits low behind the knight, who stays in frame the whole time, from the wind-up (r1c1–c4, −94 to −24 ms) through the follow-through (r4c1–c4, +188 to +260 ms). Contact at r2c1 (0 ms) shows only a tiny orange speck near the weapon head (r2c2–c4). The hit is weak but readable.
- **B:** From r1c1 (−94 ms) the camera is already tilted up. The knight is cut off at the bottom-left, with only his helmet and pauldron showing. At r2c2–r2c4 (+24 to +71 ms) a clear warm-white flash appears on the leg. After that, the weapon and knight are almost gone (rows 3–4 show only the leg and sky). The dragon-state mismatch limits this comparison, but the cut-off framing is already there before the actions differ.

**Heavy leg (contact 2)**
- **What matched:** 3.28 cm, 0.06°, same dragon state, so the views are comparable.
- **A:** A wide shot with the knight's full body inside the ring and a readable swing arc (r1c1–c4). In the detail frame the knight runs from about y 360 to 670 of 720. Contact (r2c1) has only a small ember inside the weapon cage, so impact is underplayed.
- **B:** In the detail frame only the knight's helmet and shoulder show, at about y 590 to 720, with the body cut off. At contact (r2c2–r3c1, +23 to +95 ms) a bright light patch appears on the leg, but the weapon isn't visible at the hit. The flash shows where the hit landed, not what landed it. This is a new blocking regression in camera readability.

**Heavy head (contact 3)**
- **What matched:** 0.1 cm, 0.0°, same dragon state. The two runs are essentially identical, including the same camera reframe between r1c4 and r2c1.
- **B is clearly better here:** a warm spark at the mouth plus a pool of light on the ground at r2c2–r3c3 (+25 to +165 ms), fading over about 140 ms. It reads as a hit with weight.
- **A:** shows only the red snout decal, which is already there before contact (r1c1). There is no impact signal at all.
- **Minor problem in B:** the ground light is a flat, evenly lit ellipse that looks like a spotlight more than light from the impact.

**Improvements in B:** the contact lighting is visible on all three hits and makes them easier to place, most of all on the head hit.

**New defects in B:** on both leg contacts the camera pitches up and cuts off the knight and weapon, from before contact through the follow-through. You can't read the action.

**Shared limitations:** neither run shows camera shake, hit-stop or a visible dragon flinch in these 16-frame windows. In both, the swing passes through the dragon's leg with no visible deflection.

**Gate:** Not met. B's lighting is better, but the cut-off framing on the light-leg and heavy-leg contacts is a blocking regression, so B isn't better overall.

**Biggest gap (testable):** On leg contacts, keep the camera pitch so that at t = 0 ±24 ms the knight's helmet and weapon head are both inside the frame, at y ≤ 85% of frame height. Keep B's contact light. Then recapture contact 2 with the same matching diagnostics.

## Unblinding and interpretation

{"A": "after", "B": "before"}

The critic chose A (revision 2), but its final gate paragraph instead evaluates B and says not met. The report also scores revision 2 impact lower and identifies missing head-hit feedback. This contradictory gate is **not treated as acceptance**. Revision 3 keeps the clearer framing and restores the stronger body highlight using the existing character-only lighting channel, excluding floor receivers.
