# Blind reviews (Opus 5.5 high; sides labelled A and B at random; key held by the director)

## Phase A, round 1 — 2026-11-18 17:20 ET, clips from packages 17e33e67 / c00bffc1 / 78f2c849

| Item | Better side | Confidence | Passes its question | What the reviewer saw |
|---|---|---|---|---|
| A1 foot mesh | tie | medium | no | No stretched toe in EITHER clip: the "before" clip does not show the bug in its 15 s, so the pair proves nothing. In both: thin wire-like spikes at the back of the ankle, flat polygon fins on a lifting leg, a see-through hole in a hind leg (the dither cut-through), the knight standing inside the claws; the dragon is airborne for 40 % of the clip |
| A2 camera inside the dragon | fix | high | only "never inside the dragon" | The old camera goes inside repeatedly (dithered leg, claws cut into shards, see-through belly, a hole through the tail). The fix never does, but: 0.5-2.0 s nothing on screen but floor; twice the camera is inside the KNIGHT and the screen is black; the knight's back fills the screen; the knight is cut off at the bottom edge |
| A3 feet on the floor | fix | medium-high | not proven | The old build floats in 36 of 60 frames (gap 14-16 px, up to 40). The fix touches the floor line in most frames; without contact shadows the framing cannot confirm contact. Measured in engine: planted sole 0.0 cm median, 0.0 cm p90 |

Also noted, outside the questions: the sword lying flat on the floor away from the knight's hand at moments; the fire effect is a flat pink translucent smear; dragon leg and belly textures are blurry and the claws faceted in close-up.

Outcome: A2 gets a second pass (minimum distance from the knight, never inside the knight, cut-through off by default, new measured checks); the A1 clip pair is re-cut so the old clip shows the bug; the ankle and fin artifacts are investigated.

## Phase A, round 2 — 2026-11-18 21:35 ET, re-cut clips (A2 from the final package 34667e83)

| Item | Better side | Confidence | Passes its question | What the reviewer saw |
|---|---|---|---|---|
| A1 foot mesh | tie | low | no | Again no spike or sheet in either clip. In both, one front paw reads as "a toeless stump" (later traced to the left front paw's own mesh and skinning: it rides on one bone with no toe chain; not the mirrored-toe repair). A third pair, cropped on the foot at the claw clip's worst moment, now shows the old build's toe pinched out into a long sheet and the fix without it (on the page; not yet blind-reviewed) |
| A2 camera | fix | medium | no | Not like for like (the dragon flew off in the fix run, so it never went under the belly). The old camera dithers a hole through the belly and overexposes. The fix: the tail looked see-through over the knight for a quarter second, the knight was pushed behind the HUD, and the camera jumped at 12.59 s |
| A3 feet on the floor | fix | medium | not in every frame | The old build floats in most frames (one sole about 150 px up). The fix touches the floor in most; a few gaps remain that may be feet lifted mid-step |

## Whole fight against the reference, after phase A — 2026-11-18 21:45 ET

Our phase A victory film (60 s) against 51 s of the reference's fight footage, neutral names, six aspects. Full text:
`Local/quality-goal/critic-fight-A/review.md`.

| Aspect | Better | Gap | Confidence | Main reason |
|---|---|---|---|---|
| Picture and lighting | reference | large | high | Ours is flat grey-blue (darkest 5 % at brightness 29 against 6.7), fire casts no light, a control panel stays on screen |
| Hero model and movement | reference | clear | medium | Our weapon reads as a ribbed rowboat; the roll looks like a sprawl |
| Creature animation | reference | clear | medium-high | Ours has one slow tempo, a landing with no contact, no reaction to hits |
| Weight of impacts | reference | large | high | Ours: a faint 2-3 frame glow, no shake, sparks or reaction. Theirs: dust, debris, sparks, trails |
| Sound | reference | large | high | Ours peaks 21 dB lower, one hit sample repeats identically, a synthetic tone plays |
| Camera | reference | clear | high | **Ours still goes inside the dragon at least six times in a real fight** (confirmed by the director on frames at film 35.5, 36.75, 73.5, 79.5 s), points at the floor once and snaps |

This is the starting scoreboard: reference better on all six. It also shows the phase A camera proof was too narrow:
the dedicated camera test measured zero inside frames while the fight film has several. A2 is reopened.
