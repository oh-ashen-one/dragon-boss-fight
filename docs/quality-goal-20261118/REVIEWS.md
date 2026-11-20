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

## Phase B, blind review 2 (2026-11-19 11:05 ET): weight of impacts and sound, with the real game audio

Opus critic, sides hidden, 60 s of our phase B film against the 51 s reference film. He cannot listen; sound is judged
from levels, spectra, onsets and their timing against the picture.

- **Weight of impacts: reference clearly better.** Our stomps and falls are rated comparable to his slam (15 frames of
  shake up to 5.8 % of frame height, dust bloom). What loses is the knight hitting the dragon: a leg hit turns the leg a
  flat cream colour for 6 frames, no spark at the contact point, the leg does not move, the knight does not recoil; head
  hits flash for 2 frames and the head does not move. His hit: half a second of burst with debris and 10 frames of
  shake peaking at 5.4 %. He found no hit-stop and no zoom in either film. Our trail barely shows; our film drops a frame
  about every 5 s. Faults in the reference: dark and far away, heavy motion blur, the boss's reaction cannot be read.
- **Sound: reference slightly better.** Ours: weapon hits are silent in the real mix (3 dB rise at a leg hit against
  28-36 dB in his); the mix is 15 LU quieter (-30.3 LUFS against -15.0) with a narrow range; the stomps correlate at
  0.84-0.95 and read as one sample; the landing and the knight's steps have no clear sound; the fire breath has no
  onset. Credit to ours: low-end weight under stomps in sync within 30 ms, probable dragon vocals in calm stretches,
  no clipping, no pure tones. Faults in the reference: a 15 s stretch of combat with no distinct impact sounds, and
  effects piled into a dense bed elsewhere.
- Action: second passes ordered for both: the hit lands on the dragon and on the knight (struck part reacts, burst at
  the contact point, weapon rebound, visible stop), and the knight's own hits and steps are near-field and loud with a
  master level near the reference's.

## Phase F blind review 1 — 2026-11-19 14:40 ET, boss animation, round 1 playback film against the reference

Opus critic, sides hidden (labels J and K drawn at random; key kept outside the pack), our 72 s dragon playback round 1
film (`veyr-dragonplayback-victory.mp4`, package `6584eee5`) against the 51 s reference fight cut. One aspect only.

**Verdict: OURS CLEARLY BETTER.** Ours warns before attacks (throat glow before fire, roar pose, take-off and gliding
landing), planted feet hold on the cobbles in the strips he looked at (medium certainty; the tracker failed on the
repeating cobbles), it reacts to damage (belly-down, rises with dust) and moves in several ways. The reference has one
strong slam with real weight (1.1 s lowering, 0.7 s hold, drop) and clear stance changes, but its boss never reacts to
hits, grey hit smoke covers its head and its feet are unreadable in the dark.

Our faults, worst first:
1. Upper body snaps 60-90 degrees in about 80 ms as the fire starts (6.00-6.08 s, frames 181-183). Ruins the illusion for that moment.
2. The knight stands inside the dragon's foot at 38.8-40.6 s; the foot never pushes him away.
3. The camera shows only legs for most of the fight (26-57 s, 62-69 s), so head, wings and wind-ups are out of shot (camera work, in progress).
4. Uneven frame intervals in the film (388 intervals over 50 ms, longest 139 ms): game or recorder unknown.
5. The death fall is cut off by the end of the film.

Not judged by him: exact foot slide (rests on zoomed strips), our head and wings while the camera sat at leg height,
playback speed errors smaller than the hitching. Full text: `Local/quality-goal/review-F-blind1.md`.

Consequence: round 2 keeps its targets and adds the aim snap at the start of fire (fault 1) and a film that runs
through the whole death fall. Fault 2 is a contact rule, not animation: noted for the owner, hitboxes stay fixed.

## Sound blind review 3 — 2026-11-19 17:40 ET, second-pass capture 3 against the reference

Opus critic, sides hidden (labels P and Q drawn at random; key outside the pack), 62 s of our second-pass sound capture
(`veyr-b2sound-victory3.mp4`, branch `fable/quality-goal-B2sound` `9605a47`) against the 51 s reference fight cut. He
cannot listen; sound judged by levels, spectra and onsets against the picture.

**Verdict: OURS CLEARLY BETTER.**

| Measure | Reference | Ours |
|---|---|---|
| Integrated loudness | -15.0 LUFS whole film; -25.6 LUFS without the narrator | -17.2 LUFS |
| True peak | -1.2 dBTP (-10.1 dBFS without the voice) | +0.2 dBTP, 9 full-scale samples at 14.53 s |
| Hits over the music bed | +6.3 dB | +13.0 dB |
| Impacts with a clear onset | 5 of 8 | 13 of 14 |
| Median delay against the impact frame | 8.6 frames | 3.3 frames |
| Loudness range | 2.6 LU without the voice | 5.3 LU |

New fact: the reference clip carries a narrator over 33 of its 48 s. The -15.0 LUFS that earlier reviews and our level
target used was the voice, not the game; review 2's "reference slightly better" on sound compared our mix with his
narration. Our level target is now -20 LUFS plus or minus 2 with true peak at or under -1 dBTP.

Our faults, worst first: heavy boss events weak or late (claw slam at 8.17 s with no clear onset; stomp at 48.82 s 11
frames late; slash at 11.64 s and debris at 14.32 s 16 frames late); stereo image leans right (2.8 dB on average, up to
9.8 dB); one small clip. Not judged: footsteps, wing beats, swings and hurt sounds (not isolated), and anything that
needs ears (whether the sounds please, whether the low end booms). Full text: `Local/quality-goal/review-S-blind3.md`.

Consequence: a short third pass on the three faults plus stomp variety and the fire onset, then the sound branch merges.

## Sound blind review 4 — 2026-11-19 18:35 ET, second pass against third pass (our own two mixes)

Opus critic, sides hidden, 80 s of each of our two sound captures (`veyr-b2sound-victory3.mp4`, pass 2, `9605a47`;
`veyr-b2sound-victory4.mp4`, pass 3, `a68f67d`).

**Verdict: PASS 2 SLIGHTLY BETTER.** Pass 2 keeps a clear order of events (13.4 dB from the loudest kind to the
quietest; pass 3: 7.0 dB). In pass 3 the knight's footsteps are louder than the dragon's walking steps, slams stand
only 4 dB over walking steps, and weapon hits are buried (2-8 kHz peak -27.3 dB against -18.1). Pass 3 wins on headroom
(no full-scale samples; pass 2 clips at +0.2 dBTP) and on a centred image (pass 2 leans right by 2.8 dB). Neither mix
turns the low end into a continuous rumble. In both, low thumps play while the dragon flies, the landing is quieter
than an ordinary slam, and the hit sound starts 150-185 ms after the flash (to be settled on the game clock). Full
text: `Local/quality-goal/review-S-blind4-passes.md`.

Consequence: pass 4 = pass 2's hierarchy and hit clarity with pass 3's headroom and balance, then a fresh blind review
against the reference before the sound branch merges.

## Camera blind review — 2026-11-19 19:45 ET, steady view with dissolve against the reference

Opus critic, sides hidden (labels G and H at random; key outside the pack), silent films: 100 s of our steady-view
one-hand victory (`veyr-camera-steady-1h.mp4`, branch `fable/quality-goal-camera4` `6097716`, package 20, with the
evidence-save fix) against the 51 s reference fight cut (about 39 s of continuous play in nine pieces once its edits
are removed). One aspect only.

**Verdict: OURS SLIGHTLY BETTER.**

| Measure | Ours | Reference |
|---|---|---|
| Hero hidden | about 1.5 s of 100 s | about 9 s of 39 s |
| Boss head in frame | about 33 % | about 90 % |
| Typical view speed (px per frame at 640 wide) | 2.7 | 1.2 |
| 99th percentile | 22.4 | 18.1 |

Ours keeps the hero readable almost throughout; the reference loses him behind the boss, its antlers, smoke and
pillars, with no fade. Our faults, worst first: the boss is framed as feet and belly (head out of frame two thirds of
the time, so a bite or breath cannot be read coming: "breaks the fight"); legs come right up to the lens and the fade
reads as switching on late; lurches of 37-57 px per frame at four moments; the hero under the HUD dial for a moment.
Our own audit's "head or torso in frame 96-98 %" hid the first fault. Full text:
`Local/quality-goal/review-A-blind5-camera.md`.

Consequence: the branch merges after its regression (it already beats the reference), then a third pass: head and
chest in frame at least 70 %, parts near the lens fully faded before they cover a quarter of the frame, view motion
capped outside impact kicks, the knight kept clear of the HUD.

## Impacts blind review 3 — 2026-11-19 20:30 ET, second approach against the reference

Opus critic, sides hidden (labels R and S at random; key outside the pack), silent films: our 74 s two-hand victory on
the impacts second approach (`veyr-b2impact-victory-2h.mp4`, branch `fable/quality-goal-B2impact` `e3e36c2`, package
11) against the 51 s reference fight cut. One aspect only: weight of impacts.

**Verdict: OURS CLEARLY BETTER** (the first review of this aspect, on phase B, was "reference clearly better").

| | Ours | Reference |
|---|---|---|
| Hero hits judged | 9, all read, same feedback each time | 3 judgeable |
| Flash | on the contact frame, 10-14 frames | white puff 6 frames, then smoke over the contact |
| Blade held (hit-stop) | 8-10 frames at 60 fps | 0 |
| Zoom punch | 5.3-6.2 % | 3.3 % once |
| Shake | 2.1-4.8 % of height, about 15 frames | 1.3-3.2 %, 6-8 frames |
| Boss hits on the hero | no shake (under 0.7 %), no flash | 3-4.9 % shake, one 11 % kick |

Our faults, worst first: a hit at 13.78 s whites out half the screen, turns the claw flat yellow for 10 frames and the
old camera snaps away; the boss's hits on the hero get no feedback at all ("weaker than the hero's taps"); the struck
leg does not visibly move at fight distance (0 frames measured); light and heavy hits differ only by the tint; shake
starts 2-4 frames late. Capture note: 1,881 of 4,447 of our frames repeat (about 35 game frames per second in a 60 fps
file). Full text: `Local/quality-goal/review-W-blind3-impacts.md`.

Consequence: the branch merges once its band and regression pass; the five faults are the next pass.

## Standing after 2026-11-19 20:30 ET

| Aspect | Latest blind verdict | On which build | In the goal branch |
|---|---|---|---|
| Lighting and picture | ours slightly better | picture polish round | yes, installed |
| Boss animation | ours clearly better | playback round 1 film | no (band not yet in) |
| Sound | ours clearly better | sound pass 2 (clips slightly) | no (mix calibration running) |
| Camera | ours slightly better | steady view, package 20 | no (merge pending its identity check) |
| Weight of impacts | ours clearly better | impacts second approach | no (band and regression pending) |
| Hero model and movement | not reviewed | | Greystone films pending |

"Done" needs all six on ONE final film of the integrated build, reviewed blind again.

