# Blind critic rubric — playtest goal, Tier 1

Each Tier 1 item gets one blind A/B review by `opus-critic` (Opus 5.5, high). The critic sees two
sets of native frames or films labelled A and B in random order, the owner's requirement in the
owner's words, and this rubric. It is never told which side is new.

For every item the critic answers:

1. Which side better meets the owner's requirement, A, B or TIE, with confidence (high / medium / low).
2. Does the better side fully meet the requirement (MEETS / PARTLY / FAILS)?
3. The three most visible defects on each side, with the frame or timestamp.
4. Anything on the better side that is worse than on the other side (a regression).

Scores from 1 to 10 are optional. The record is the choice, the defects and the measured numbers.

## Per-item questions

| Item | Owner's words | What the critic checks |
|---|---|---|
| 1 Floor rings | "Remove the large yellow/red circle on the ground that reveals the dragon's attack area." | Any yellow, orange or red ring, arc or line drawn on the floor in any frame. Other feedback (wind-up pose, fire, HUD) must still be present. |
| 2 Scale | "It reads 12-15 ft tall; make it read around 30 ft so the player feels tiny beneath its legs." | Dragon height against the knight in the same frame: back height and head height in knight-heights. Knight under the belly with clear room. Feet on the floor, no clipping through walls or towers, no part cut off by the fortress. Does the camera still show what the player needs? |
| 3 Pace | "Running and dragon movement feel like roughly 0.75x speed. Make both noticeably faster and more responsive." | Knight run and dragon walk/turn cadence in the film. Feet planted during travel (no skating). Motion must not look fast-forwarded. |
| 4 Attack choice | "As soon as the player enters range it should pick a random suitable attack. Under it too long: take off and fire. Back-right foot: an attack that actually reaches there." | Per zone: does a blow land on a player holding that spot, and how soon. Underbelly: takeoff then fire. Variety: not the same move three times running. |
| 5 Aggression | "I nearly depleted its health while barely being hit. It barely moves, attacks or connects. I want a genuinely very difficult boss." | Idle gaps between actions, strings of attacks, how much it turns and steps, hits landed on a player who does not dodge. |
| 6 Health | "About 30% more health." | Boss bar and measured fight length; judged with item 5. |

## Measured gates that travel with each review

- Camp replay: seconds to first hit per zone, anti-camp takeoff time under the belly.
- Victory replay, one hand and two hands: wall seconds, hits taken, heals used, longest boss idle.
- Death replay (a player who stands in front and never dodges): seconds to death.
- Showcase: segments passed out of 20, frustum misses.
