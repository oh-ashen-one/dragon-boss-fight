# Heavy attack blind comparison, round 4

A = existing attacks; B = retimed Kevin candidate with dedicated combo entry. BOTH FAIL, B relative winner, rejected release continuity. This is the second unsuccessful visual revision of the Kevin approach. Switch to a different source; keep Kevin disabled.

**Verdict: BOTH FAIL. B is the clear relative winner.**

B is better than A on every axis I could judge, so swapping B in for A loses nothing visible. B is still not ready to accept on its own because of the strike-continuity blocker below. That blocker is in the standalone route; I can't confirm or rule it out in the chain route.

**Scores (1–10)**

| Axis | A | B | Evidence |
|---|---|---|---|
| Weight | 3 | 7 | A is a flat swipe at waist height from an upright stance. B builds up: a two-handed overhead windup (normal view2, 1.65–2.22 s), a descending diagonal, then a deep lunge that it holds. |
| Body participation | 3 | 8 | A's legs and torso barely load in either route. B drops its hips, leans the torso forward and stretches the rear leg back (view2 2.73–3.09 s). |
| Grip | 2 | 8 | **A's chain heavy is one-handed:** in view4 the left hand is off the grip from 1.10 to about 2.30 s, the left fist hangs out to the side, and the weapon dangles from the right hand (A32 2.16 s). A's standalone version is two-handed (slow view4 0.37–0.65 s). So A's two routes don't match. B has both hands on the grip through windup, strike, hold and guard (view4 B19–B41). |
| Foot support | 4 | 7 | A stays narrow and upright. B is wide in the windup and planted in the lunge. Foot sliding can't be measured at this sampling. |
| Continuous strike | 4 | 4 | A's chain route sweeps right (1.67–1.80 s), sinks back to a low one-handed hold (1.96–2.29 s), then sweeps again (2.34–2.49 s). It reads as a double swipe with a hitch, not one committed heavy. B has a snap at contact, described below. |
| Recovery / exit | 5 | 6 | A gets back to idle by about 2.7 s with no visible pop. B lifts into a vertical two-handed guard (3.49–3.87 s), then narrows to idle in about 0.2 s (3.87→4.07 s). That's readable but long: about 1.4 s committed after contact. |
| Cuts an enemy, not the floor | 6 | 7 | Both strike lines end around hip or thigh height. B's held follow-through is low (thigh/knee) but well clear of the floor. |

**Biggest gap (B): the cutting arc happens in about 20 ms of action time**

In B's standalone slow capture the blade sits high and back-left at 1.124 s (view2) / 1.126 s (view4). By 1.144 s (view2) / 1.152 s (view4) it's already horizontal on the right, and the body is already deep in the lunge. The one sample in between (view2 1.136 s) hides the blade behind the body. That window is 20–26 ms of action time, about one frame at 60 fps. Native 0.25x playback shows no in-between blade positions through roughly 150–180° of arc, so in game it will read as a pose pop, not a visible cut.

The fix, as a testable instruction: re-time the standalone release so the descending arc spans at least 4–6 game frames (about 70–100 ms). The 0.25x capture should then show at least 3 distinct mid-arc blade positions between "blade upper-left" and "blade horizontal right", with the pelvis dropping progressively, not in one step.

**Secondary issues**
- **B, lunge pushes the body into the closeup camera:** the body fills or clips the view4 camera exactly at contact (normal 2.617 s, slow 1.134 s). That hides the contact pose from my review; it isn't proven to be an animation flaw.
- **B, long commitment:** about 0.55 s of windup plus about 1.4 s of recovery is fine for a heavy, but whether it plays well is a gameplay call I can't make from stills.
- **A, routes differ:** the chain and standalone heavies differ in grip and shape (one-handed double swipe vs. two-handed single sweep).
- **Shared, not judged:** both variants hold the blade low behind for about 0.4–0.5 s after the second light (A 1.10–1.60 s, B 1.17–1.54 s). That looks like the shared light action's recovery, so I didn't count it against either.

**Limits of this evidence**
- At game speed the normal sheets sample every 65–100 ms, so B's chain-route contact (2.523→2.626 s) can't confirm or rule out the snap; I only measured it in the standalone route.
- The slow sheets cover only the strike windows (A 0.25–0.65 s, B 0.98–1.29 s), not the standalone entry or exit.
- Stills can't show foot sliding, hit-stop or VFX.
- This is a review of rendered frames, not human gameplay acceptance.
