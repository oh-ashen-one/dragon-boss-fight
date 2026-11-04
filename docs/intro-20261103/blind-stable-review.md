## Verdict: A, by a narrow margin
A is only slightly better. The difference shows in the full-resolution handoff frames, while the tile sheets are close to indistinguishable. A's scoped handoff is **conditionally acceptable**. B's isn't yet, because of the missing weapon in `B-handoff-detail-1`. This is a relative and scoped call, not overall quality acceptance.

## What separates them
| Check | A | B | Edge |
|---|---|---|---|
| **Weapon at handoff** | `A-handoff-detail-1` (0.000s): weapon end clearly visible beside the right hand, with the head partly visible behind the hip | `B-handoff-detail-1` (0.017s): right hand looks empty, no weapon visible; it is back in `detail-2` (0.088s) | **A** |
| **Idle-to-walk** | `A-handoff-detail-2` (0.097s): stance has only begun to narrow | `B-handoff-detail-2` (0.088s): legs already closer together, despite less elapsed time | **A**, slightly |
| **Same-time tiles** | `A-handoff-02` r1c2 (32.710s): legs still apart | `B-handoff-02` r1c1 (32.712s): further into the step | **A**, slightly |

The cause and duration of B's missing weapon are uncertain. It's confirmed in only one full-resolution frame, and the tiles can't resolve it. A's gentler walk start is also a modest difference, and only continuous playback can confirm it.

## No visible difference
- **Tour:** all eight shots match in `A-tour-01` and `B-tour-01`, so the approved tour is preserved.
- **Camera and HUD:** the sweep to the player and dragon matches, and the HUD appears at r8c3 in both (32.618s in A, 32.642s in B).
- **Player visibility:** the player enters at the bottom edge in row 4 of `handoff-01` and is fully framed by row 7.
- **Materials:** armor, cloth, cobbles and walls stay consistent through the handoff, with no visible material pop.
- **Late frames:** `A-late-detail-1` and `B-late-detail-1` look essentially identical. Weapon, feet and fire lighting all read well.

## Remaining defects in both
1. **Unexplained weapon arc:** in `handoff-02` r5 through `handoff-03` r2 (about 33.2–33.9s), the large weapon sweeps up over the dragon and around to the low left. It looks disconnected from the walk, and its grip is unresolved at tile size. It may be a deliberate attack, but the frames don't show that.
2. **Abrupt recovery:** in `handoff-03`, the player goes from turned to square-on idle in about 0.06–0.07s (r3c1–r3c3). It looks like a snap, but this is uncertain at tile size.
3. **Weak idle weapon read:** the body hides most of the weapon, so it mostly reads as a small knob by the hand.
4. **Armor highlight swing:** a blown-out white patch on the back plate turns into a hard vertical split during the step (`detail-3`), and the torso goes much darker during the arc.
5. **Fire cutoff (outside the handoff):** the mouth flame disappears between `late-02` r8c2 and r8c3, about 35ms apart in both.

## Uncertain
- **Feet:** they look planted at idle, with sensible shadows, but stills can't rule out foot sliding.
- **Grip:** the hand and weapon look connected in A's details and in B's `detail-2` and `detail-3`, but not in `B-handoff-detail-1`. Grip through the arc is unresolved.
- **Missed capture near 36.78s:** there's no obvious jump around it, but this doesn't prove continuity.

**Next check:** A still needs a continuous playback review of 33.2–34.1s. For B, confirm how long the empty-hand state lasts.
