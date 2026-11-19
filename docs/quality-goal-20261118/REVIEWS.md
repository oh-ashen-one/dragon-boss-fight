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

## Phase B weight effects, before against after — 2026-11-18 23:30 ET (installed build 956518d5)

| Item | Better side | Difference | Confidence | What the reviewer saw |
|---|---|---|---|---|
| Dragon footfalls | new | clear | high | A grey dust puff at each landing foot; "you notice it if you're looking"; small and short-lived, no debris or cracks: "doesn't read as a creature weighing many tons" |
| Dragon hit by the sword | new | large | high | Orange sparks at the contact, a white flash, a dust-and-debris cloud. No recoil of the spine or head could be confirmed in either |
| Weapon trail | new | clear | high | A flat white streak about one blade long for about 8 frames plus sparks; "clearly weaker than the other game", whose bar is heavy motion blur and large layered bursts with debris |
| Heavy blow and fall | new | clear | medium | Full-head flash, streak, dust, debris cloud; the fall itself barely shows dust in either clip |

Overall: "a casual player would notice". **Measured camera shake: none in either version** (frame-to-frame background
shift 0.2 px median, 2 px at most), and no slow motion or zoom was visible: those three effects fire by the counters
but do not show on screen. Also seen: the head flash blows out to flat white, a two-frame camera pop, one red-brown
tinted frame, the controls overlay in every clip.

## Phase C, blind review 1 (2026-11-19 07:05 ET): lighting and picture

Opus critic, sides hidden, 12 real play frames from our picture film against the 12 reference frames, and the same 12
against the installed build on the same route.

- **Ours against the reference: reference clearly better.** His reasons, most costly first: our floor in front of the
  camera is crushed to black (up to 90 % near-black in the bottom third); our highlights top out at 108-154 of 255 in 8
  of 12 frames against his 200-220, so the picture is dim with no shine on metal or scales; our walls glow evenly orange
  with no source big enough to explain it; one flat wall at one distance where he layers lit pillars, a dark middle and
  a bright far wall; our dust is an opaque grey slab; the dragon reads as blue-grey plastic and the fire never lights its
  underside; one frame was a motion-blur smear. Faults he found in the reference: the hero vanishes against the floor,
  flat milky windows, heavy motion blur in two frames.
- **New against old: new clearly better.** The old build is nearly colourless, has no light direction, milky blacks, and
  dust that whites out the screen. The old build's one win: hero and floor read better in the mid-tones.
- Action: a second, structural pass (floor that reflects, real highlights, visible sources with pools and falloff, depth
  dressing, thin lit dust, warm up-light and breath light on the dragon, less motion blur).

## Phase C, blind review 2 (2026-11-19 09:00 ET): lighting and picture after the structural pass

A fresh Opus critic, sides hidden, 10 real play frames from the second picture film against 10 reference fight frames.

- **Verdict: ours slightly better.** His reasons: our knight reads among the dragon's limbs with armour highlights where
  the reference hero is a black cut-out; cool moonlight against orange braziers where the reference is one warm brown;
  our dust and debris take the scene's light where his smoke is a flat grey sprite; his motion blur smears whole frames,
  ours stays crisp; our braziers cast shadow streaks and light the dragon from below where his windows are flat cards.
  He credits the reference with the more cohesive interior mood when nothing is happening.
- Faults he found in ours, most costly first: foreground cobbles crushed to blue-black in some frames (44 % of one frame
  at luma 12 or below); a pale pinkish fill with no source on the dragon's legs and tail that makes them look plastic and
  shows the faceted mesh; a washed-out dust veil in one frame; moon-blue floor patches ending in hard edges; brazier
  bloom and small armour highlights clipping.
- C2 ("clearly worse is not accepted") is met on this review. The faults go to the picture builder as a polish list.
