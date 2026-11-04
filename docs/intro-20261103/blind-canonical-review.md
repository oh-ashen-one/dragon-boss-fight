# A/B integration review: Veyr fortress handoff

## Verdict
- **Winner: A.**
- **Visibly better: yes, in these frame samples.** B loses the whole player in two captured frames, while A keeps the player visible in every frame I inspected.
- **Scoped integration acceptable: no, not yet.** B is rejected. A is the better candidate but narrowly misses, with a weapon dropout and a stance snap at the handoff.
- **Inspected:** 47 of 47 referenced images (29 sheets, 18 full-resolution PNGs), plus `sequence.json`.

## Comparison

| Criterion | A | B |
|---|---|---|
| Eight-shot tour | All eight shots present | All eight shots present, with no visible difference from A |
| Player visibility | Present in every inspected frame through 39.74 s | **Missing at 32.667 s and 36.109 s** |
| Weapon visibility | **Missing in one full-resolution frame** | Visible in the matching handoff frame |
| Environment | No geometry dropout seen | **Wall section missing at 32.173 s** |
| Materials | Stable at the handoff | Stable apart from the dropouts, though the floor may resolve later |
| Player stance | Abrupt idle-to-walk change | Same change, with the missing frame in the middle |

## Evidence

**B defects**
- **Player gone at 32.667 s:** in `B-handoff-02` (row 4, column 4), the HUD and dragon render but the knight doesn't. The knight is present in the previous tile, and again at 32.704 s.
- **Player gone at 36.109 s:** `B-late-detail-2` shows the full dragon, fire and HUD with no knight or weapon. `B-handoff-09` (tile 6) shows the same frame, and the knight is back in `B-late-detail-3`.
- **Wall gap at 32.173 s:** in `B-handoff-02` (row 1, column 1), the wall stops near x=445 with sky behind it. The next tile has the wall and mural again, and A's nearest frame (32.185 s) is intact.
- **Possible floor softness (low confidence):** the cobbles look softer than A's in the early rows of `B-handoff-02`.

**A defects**
- **Weapon gone at +0.017 s:** `A-handoff-detail-1` shows an empty-looking hand with no pommel or weapon head. `B-handoff-detail-1` shows the pommel, and it returns in `A-handoff-detail-2`. I confirmed this at full resolution only, because the sheet tiles are too small to be sure.

**Shared issues (they don't separate A from B)**
- **Idle-to-walk snap:** the knight goes from a wide idle stance to a narrow step almost at once. In A this happens between adjacent frames, 32.677 s and 32.712 s; in B it falls across the missing frame, between 32.646 s and 32.704 s.
- **Dragon head pop:** in B, the head goes from out of frame to fully visible between 35.813 s and 35.846 s. A's tile at 35.843 s shows a matching pose, but the frames before it aren't in the packet.
- **Wing material:** the red-brown membrane turns glossy black with blue-white highlights as the wings fold, as `A-late-detail-1` and `B-late-detail-1` both show.
- **Fire plume edges:** the translucent haze shows a hard, straight edge near the wall-floor line, for example in `A-late-detail-2` and `B-late-detail-1`.
- **Weapon in idle:** only the pommel and part of the handle read clearly; the head is mostly hidden behind the body.

**A-only observation**
- **Head jump at breath end:** the dragon's head jumps upward between 37.739 s and 37.774 s (`A-late-04`). B has no frames here to compare.

## Fixes needed before acceptance
1. Remove the one-frame weapon loss at the handoff.
2. Smooth the idle-to-walk change.
3. Re-capture continuous coverage from 35.6 s through the end of the breath, then repeat the visibility check.

## Limitations
- **Shared window:** late coverage overlaps only from 35.843 s to 36.175 s. B's late sheets repeat frames already in its handoff sheets, so they add no new coverage.
- **Gap in A:** A has no frames between 35.608 s and 35.843 s, so its clean player record excludes that window.
- **Fire exposure:** only A shows the plume crossing the player, and the player stays visible there. B may have further dropouts after 36.175 s that this packet can't show.
- **Damage:** no frame shows an unambiguous damage event, and the health arc is too small to read on the sheets. The damage check is therefore limited to visibility during fire exposure.
- **Evidence type:** these are sampled frames, so this says nothing about continuous playback, audio, controls or the remaining combat backlog.
