# Heavy attack blind comparison, round 2

A = existing heavy; B = Kevin v8. Mapping disclosed after verdict. Runtime gates remain separate.

**Verdict: PASS B.** B is clearly better on weight, body movement and phrasing. It is **not proven ready to ship.**

**A: fails as a heavy attack**
- **Weapon weight:** the blade drops from vertical (A4, 0.17s) to fully horizontal at arm's length (A6–A7, 0.29–0.34s). That's about 90° in roughly 0.12s with no visible effort. A7–A13 then sweep it across the body at chest height in about 0.35s. A large two-handed weapon moving that easily looks weightless.
- **Whole body:** the torso stays nearly upright and the stance stays about hip-width through A6–A12 (views 2 and 3). The hips, knees and torso don't visibly load or drive the swing, so it reads as arm-only.
- **Phases:** there's effectively no wind-up (A1–A5 take 0.23s), and the strike and follow-through blur together (A7–A21). The weapon lifts back to vertical in a single upward arc (A22–A28), led by the arms. The only lower-body change is a slight crouch around A13–A16 (view 1).
- **Grip:** both hands look to be on the hilt in view 3 (A7–A12), but I can't confirm it at the sampled resolution.
- **Idle transitions:** idle at A1 and A29–A36 match, and both ends are clean.

**B: better on every axis checked**
- **Wind-up:** the knight steps into a wide stance (B4, 0.27s), lifts the weapon (B5–B9), and cocks it behind the head (B10–B12, 0.80–0.98s). That's about 1s of readable anticipation.
- **Strike:** the weapon goes from cocked (B12) to a low, deep lunge (B14, 1.16s), with the torso pitched forward and the rear leg extended (view 1, B14–B19). This is a full-body commitment that A never shows.
- **Foot contact:** the extended rear foot stays planted from B5 to B28. In view 1 its position within the frame is about 210px at B5 and B14, about 215px at B21 and about 205px at B28. A shift of 10px or less shows no visible slide. Feet come back together around B29–B30.
- **Recovery:** after an extended low hold (B14–B19, about 0.45s), the weapon rises through B20–B24 and returns upright by B25–B30. Idle is reached at about B31 (2.67s) and matches B1.
- **Grip:** both hands look to be on the hilt through the low hold (B15–B19, views 1 and 3).

**Blockers before B can ship**
1. **The strike arc is unverified, and it's the biggest gap.** B12 shows the weapon cocked behind the head, B13 shows it already horizontal at hip height off to the left (views 1–3), and B14 shows the low finish. At about 0.09s per sample, the actual downstroke falls between frames. Re-render B from 0.95s to 1.20s at 60 fps or more from all three views. Then confirm that both hands stay on the hilt, the blade follows a continuous arc without popping, and the torso rotation leads the weapon.
2. **No visible contact at impact.** In view 2 the blade sits at roughly knee height through B14–B19 and never reaches the ground. If this is meant to be a slam, it needs real ground contact or an impact pose. If it's meant to be a sweep, it needs a clearer finish and a hit window that matches it.
3. **The low hold may look frozen.** B14–B19 show almost no change in silhouette across about 0.45s. Check that there's settling or breathing motion so it doesn't look like a pause.
4. **Recovery steps are unchecked.** The stance narrows between B25 and B30. Foot lift, clearance and sliding during that step can't be judged from samples at about 0.09s spacing.
5. **Timing fit is unknown.** The full action takes about 3.1s, compared with 2.0s for A. Whether that suits the player or boss role needs a hands-on gameplay test.

**Limits of this review**
- These are sampled frames, so they can't show continuous smoothness, jitter, blend pops or how the attack feels to play.
- No code, hitbox data or test results were provided.
- The scene lighting is dark enough that I can't confirm hand placement or exact ground contact at this resolution.
