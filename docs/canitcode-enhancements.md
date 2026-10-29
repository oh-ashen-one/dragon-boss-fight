# Can It Code enhancements — plan for `claude-code-enhancements`

Owner request, 2026-10-28: replicate the process behind Can It Code's "I Made a Full Boss Fight in Unreal Engine
With AI" (YouTube z1mgtUvTdqg, 2026-10-25) on this branch and compare it with the current pipeline.

His stack: Unreal 5.8 (C++ and Python, no Blueprints, no MCP), Claude Opus 5.5 (code), GPT Astra (pictures and
textures), Tripo (3D models), Blender, Seedance (boss moves and voice), NVIDIA Kimodo (hero moves), Google
MediaPipe, UniRig, DINOv2, Niagara (fire), Suno (music), Freesound CC0 (SFX). Tool:
https://github.com/canitcode/video2rig (AGPL-3.0). Our fork with the Apple Silicon port:
https://github.com/oh-ashen-one/video2rig, branch `mac-mps`, checkout `~/video2rig`.

## What is actually different from Veyr today

| Area | Can It Code | Veyr on `main` (v030) | Verdict |
| --- | --- | --- | --- |
| Boss motion | Render start frame of own rig, Seedance image-to-video per move, video2rig joint reader fits the rig; Seedance clip audio becomes the boss voice | Dragon hand-keyed in Blender MCP (Tripo text-to-motion failed; Mixamo has no dragons) | Biggest gap. Adopt. |
| Hero motion | NVIDIA Kimodo + MediaPipe (details pending; his separate video gv-HCDDV2gQ) | Mixamo and Fab clips retargeted in Blender (source-first rule) | Keep source-first for the knight; evaluate Kimodo after the transcript is readable. |
| Rigging | UniRig auto-rig on Tripo meshes, jaw bone, wing/arm detection | Tripo auto-rig (biped mistake), hand-fixed `Dragon_Rig_v008_weightfix` | UniRig needs CUDA (spconv). Our dragon already has a usable 51-bone rig; skip for now. |
| Code | Pure C++ + editor Python, reproducible scripts, no MCP | C++ module + `Content/Python` tests, plus Unreal MCP and Blender MCP for live authoring | Already close. Push more of the authoring into checked-in scripts. |
| Fire | Niagara | Material-only breath FX (`Content/Veyr/FX/v2`) | Adopt Niagara for breath, embers, impacts. |
| Audio | Suno music, Freesound CC0 SFX, Seedance voice | OpenGameArt CC0 music/SFX, synthesized cues | Add Suno for a bespoke track; Seedance voice comes free with the clips. |
| Images/textures | GPT Astra | Higgsfield / Nano Banana | Equivalent; no change. |
| 3D | Tripo | Customuse (Meshy/Tripo), Tripo | Equivalent; no change. |

## Constraints on this machine and in our rules

- video2rig targets NVIDIA RTX 30+ with CUDA. This Studio is an M3 Ultra. The reader (DINOv2-small, 4 frozen
  blocks, light decoder) is portable to MPS/CPU; the port lives on the fork's `mac-mps` branch. UniRig is not
  portable (CUDA-only spconv). The old BootsTAPIR road already has a CPU path.
- Source-first animation (owner rule 2026-10-25) says no whole motions from scratch by default. video2rig
  generates whole motions. This branch runs under the owner's explicit instruction to replicate his process for
  the DRAGON; the knight stays on sourced clips unless the owner widens the exception.
- Video generation costs money. Seedance is available through Higgsfield (Seedance 2.0, image-to-video, first
  frame) or the BytePlus API. One clip at a time, owner confirms the budget before the first clip. The house
  default for non-animated AI video (MiniMax H3) does not fit here because the tool is tuned on Seedance.
- AGPL: using the tool to make animations is fine and the animations are ours. The tool's code stays in its own
  fork repo, never vendored into this MIT repo.

## Steps on this branch

1. Port video2rig to Apple Silicon (fork, `mac-mps`), smoke-test the reader on the dragon rig with Blender
   renders only. No spend. (In progress.)
2. Train the dragon's joint reader to 9000 steps. Record held-out error (target 2-4 px).
3. Owner approves a Seedance budget. Generate one clip (idle), check it with `video2rig check`, fit, review film,
   import as a Blender Action, compare against `Dragon_Idle_Blender_v1r3` in the asset reviewer.
4. If the idle wins, do roar, claw swipe, bite, stagger, collapse, death, takeoff, land. Keep Seedance audio as
   voice candidates.
5. Export to Unreal via the existing native import plan; keep approved knight clips byte-identical.
6. Niagara breath/ember systems replacing the material-only FX. Suno track candidate.
7. Write the comparison (before/after captures, timings, cost) in `docs/canitcode-enhancements/`.

## What the Patreon source (BossFight-Unreal-Project, 2026-10-28) actually does

Read from `~/Downloads/BossFight-Unreal-Project` (README, LICENSE, Config, Data, the Boss and FirstPerson headers,
content listings). License: use code and assets in our own games, commercial included; never re-upload the files
as they are. Do not copy his assets into a public repo.

1. **The move data is measured from the animation, not hand-typed.** `Data/leshy/moves.json` holds, per move, the
   root track per frame, the attack windows (which part, from, to, peak time, peak speed, where it is at the peak),
   floor shocks, floor contacts with speed, foot stances and quality numbers (slides, IK misses, toes under floor).
   A Python pass over the video2rig output produces it. The game reads it at start; no rebuild to retune.
2. **Hit windows come from the motion.** A paw or jaw hurts when it moves fast enough in the clip. Hurt capsules
   ride the bones (`boxes.json`, measured from the mesh). The brain picks a move whose reach, at its peak, holds
   where the player will be. Never the same move three times running, cooldowns, phase 2 under half health.
3. **Tempo per phase.** `tempo.json`: wind-up readable, blow fast, recovery quicker, per move, per time span.
4. **Sounds and effects are timestamps on moves.** `sounds.json` (the Seedance clip audio cut up, voice from the
   head, impacts from the body), `effects.json` (dust tier by contact speed, body-fall clouds, camera shake by
   speed and distance, motion blur). Footfalls from contacts.
5. **Fight feel is one system.** Hit-stop 50 to 120 ms, slow-motion back to speed after a heavy blow, camera shake
   by blow weight, hammer trail, surface-aware debris (snow, stone, wood), hit flash overlay, flinch on the boss
   (head and back snap, hips dip, spring home). Every effect on the game clock so the stop freezes it too.
6. **Hero on motion matching**, own database, inertialized switches, capsule waits for the body so nothing slides.
7. **Everything has a lab and a gate.** `-bosslab` plays moves on number keys with capsules drawn, `-bosstest`
   measures every move (travel vs track, toe drift under 1.5 cm, capsules vs Blender), `-bossparrytest`,
   `-flinchtest`, `-navfilm`, film capture with recorded audio. Numbers, then quit. This is how he kept quality
   while an AI wrote every line.
8. **Data-driven intro cutscene** (`intro.json`: shots, cameras, FOV, f-stop, follow, the boss's moves on cue).
9. **Renderer**: Lumen GI and reflections, virtual shadow maps, no static lighting, DX12 SM6, auto-exposure
   extended range. Modular church from Tripo parts, a module lab level to check each part alone. Snow with a trail
   render target that keeps every footprint.
10. **Module layout**: one C++ module, Boss/ and FirstPerson/ folders, non-unity build so missing includes show up,
    Epic template variants left in but unused.

## What Veyr adopts now (this branch) and every boss fight adopts from here on

- Measured move data and bone-riding hurt capsules generated from the clips, read at runtime from JSON.
- Attack windows and reach from motion speed; brain chooses by reach and cooldown; phase 2.
- Per-move sound and effect timestamps; Niagara contact dust and body-fall clouds tiered by speed.
- Fight feel system: hit-stop, camera shake by weight, flinch, hit flash, surface debris.
- Lab and gate flags on the GameMode: a move lab, a measured move test, a parry test, a film capture. No feature
  ships without its gate line in the log.
- Lumen, VSM, no static lighting as the project default.

## Rule check: Blender authoring (project AGENTS.md, 2026-10-21)

video2rig does not replace Blender authoring. Its output is an Action inside the rig's own `.blend`
(`blender/import_motion.py`), which is then inspected at playback speed from front, side and three-quarter views,
retimed, foot-pinned and refined in Blender before export, exactly as the project rule requires. The AI video is the
motion source, Blender stays the authoring and refinement layer. Every candidate is saved separately; approved
knight clips stay byte-identical.

## Port status (2026-10-28)

Fork `oh-ashen-one/video2rig` branch `mac-mps`: reader road runs on MPS bf16; 300-step smoke test passed
(held-out 13.4 px, expected for a smoke test); 9000-step training running (about 3 h on this GPU while shared).
Start frame rendered with `--facing +X --widths 840,1080 --margin-wide 1.25`. Blocker found: the Tripo rig's
"Left"/"Right" limb names mean front/hind, so the tool pairs no twins; a `twins` setting in `creature.json` is
being added to the fork instead of renaming bones (renaming would break the Unreal skeleton and the reader).

## Clip ledger

| Date | Clip | Provider / model | Settings | Credits | Eyeball check | Tool check |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-28 | idle | Higgsfield, MiniMax H3 Max | 768p (1344x768), 16:9, 5 s, 24 fps, start-frame mode, literal prompt (preset declined) | 12.5 | pass: panels in step, static cameras, no effects, body in frame, wings lift and settle in both views, end pose = start pose | OK: body 0.58%, limbs 0.59% of height (fail line 1.5%); frame 0 match 0.93 / 0.97 |
| 2026-10-28 | roar | Higgsfield, MiniMax H3 Max | 768p, 16:9, 5 s, 24 fps, start-frame, literal prompt | 12.5 | pass: head back, jaws wide, wings fully flared in both views, tail lifts, returns to stance, no effects | OK: body 0.89%, limbs 0.65%; frame 0 match 0.93 / 0.97. Fit: median miss 3.05 px, outline 0.62 / 0.75 (wings fully open), max twist 25.8 deg on a wing root, feet pinned in 7 stretches |
| 2026-10-28 | roar2 (size-constrained prompt) | Higgsfield, MiniMax H3 Max | same as roar | 12.5 | wings still drawn about 2x the model's span and off the front panel edges; motion blur on the side panel in the fast frames despite the no-blur sentence | OK: body 1.16%, limbs 0.67%. Fit: miss 3.69 px, outline 0.61 / 0.72, twist 68.8 deg on a wing root; no better than roar |
| 2026-10-28 | roar_sd (Seedance 2.5 control run, owner-approved) | Higgsfield, Seedance 2.5, omni_reference | 720p (1280x720), 16:9, 5 s, 24 fps, audio on, size-constraint prompt | 35 | wings still drawn wider than the model's span in the front panel; side panel clean and sharp; panels drift apart (the side panel's body and tail do not match the front at the peak) | FAIL: panels disagree on the body by 2.2% of height (fail line 1.5%); frame 0 match 0.90 / 0.96. Fit anyway: miss 4.24 px, outline 0.64 / 0.82, max twist 8.0 deg (MiniMax: 25.8 and 68.8) |
| 2026-10-28 | roar_sd2 (Seedance, half-open wings no wider than body length) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s, 24 fps, audio on | 35 | wings stay at the model's span, both panels in step, sharp, no effects | OK: body 1.13%, limbs 0.65%. Fit: miss 3.30 px, outline 0.76 / 0.85, max twist 5.5 deg, no warnings. Best roar fit so far |
| 2026-10-28 | collapse | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 6 s (145 frames at 24 fps), audio on, size-constraint prompt | 48.4 derived (see the cost note) | pass (coordinator): wings at span, drops flat, chin on floor, panels agree; side panel crops the tail at the right edge once it lies flat | OK: body 1.17% (p90 1.35%), limbs 0.77% (p90 3.96%); frame 0 match 0.94 / 0.90. Fit: median miss 4.72 px, outline 0.75 / 0.83, max twist 21.4 deg (VeyrWingNegZRoot), warnings: body under the floor in 74 frames, hind knees at joint limit 60 frames |
| 2026-10-28 | death | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 7 s (169 frames at 24 fps), audio on, size-constraint prompt | 56.5 derived (see the cost note) | pass (coordinator): falls, rolls partly onto its right flank, head stretched out, wings at span, panels agree | OK: body 0.93%, limbs 1.36% (close to the 1.5% line), frame 0 match 0.89 / 0.96. Fit: median miss 7.07 px, outline 0.71 / 0.82, max twist 51.7 deg (front upper leg; neck 48.9, shoulder 42.2), warning: body under the floor in 24 frames. Weakest fit of the set |
| 2026-10-28 | bite | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames at 24 fps), audio on, size-constraint prompt | 35 | pass (coordinator) with caveats: wind-up front panel wings maybe 1.3x, side panel a touch larger than start.png, tail tip near the edge | OK: body 0.92% (p90 1.71%), limbs 1.22% (p90 1.54%), frame 0 match 0.93 / 0.94. Fit: median miss 3.76 px, outline 0.78 / 0.80, max twist 24.9 deg (bone_7), no warnings |
| 2026-10-28 | claw_swipe | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames; content 30 fps with every 5th frame dropped, resampled to 24), audio on | 35 (1 render; two earlier submissions failed before rendering) | pass (coordinator): right foreleg lifts to chest height, draws back, swipes, returns; some motion blur on the fastest side-panel frames around frame 70 | OK: body 0.81% (p90 1.18%), limbs 0.74% (p90 1.32%), frame 0 match 0.89 / 0.95. Fit (reader-78, kept): median miss 2.63 px, outline 0.77 / 0.88, max twist 41.8 deg (bone_11), body under floor 10 frames. Reader-64: miss 2.48 px, outline 0.80 / 0.85, twist 65.8 deg, under floor 41 frames, hind feet lifted 2.6 cm |
| 2026-10-28 | stagger | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames at 24 fps), audio on | 35 | pass (coordinator): right shoulder drops, front lurches down and right, head low, recovers | OK: body 0.85%, limbs 1.17%, frame 0 match 0.94 / 0.93. Fit: median miss 4.49 px, outline 0.77 / 0.82, max twist 13.5 deg (bone_7), no warnings |
| 2026-10-28 | land (hop and hard landing) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames), audio on | 35 | pass (coordinator): crouch, hop to about half a body height, wing flare, hard four-foot landing | FAIL: panels disagree on the body by 1.76% of height (fail line 1.5%); limbs 1.16%; frame 0 match 0.91 / 0.96. Not fitted (rule: a FAIL is regenerated, not fitted) |
| 2026-10-28 | takeoff | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames), audio on | 35 | coordinator: crouch, spring, rises about one body height and hovers; wings open to full span, past the rig 1.27x limit | FAIL: panels disagree on the body by 2.14% of height (fail line 1.5%); limbs 1.54% (also over the line); frame 0 match 0.93 / 0.96. Not fitted |
| 2026-10-28 | rise (recovery) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames; content 30 fps with every 5th frame dropped, resampled to 24), audio on | 35 (1 render; one earlier attempt failed provider-side) | coordinator: crouches low, rears up onto the hind legs with both forelegs off the floor and wings raised (about frame 90), drops back; went further than the prompt | OK: body 1.17%, limbs 0.99%, frame 0 match 0.92 / 0.89. Fit: median miss 3.07 px, outline 0.81 / 0.84, max twist 62.2 deg (bone_7), warning: body under the floor in 15 frames |
| 2026-10-28 | idle_look (8 s head-intent idle) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 8 s (193 frames at 24 fps), audio on | 64.6 derived (see the cost note) | coordinator: slow breathing, head turns, wings at span, feet planted, returns to stance | OK: body 1.02%, limbs 0.91%, frame 0 match 0.92 / 0.95. Fit: median miss 2.00 px (best of the set), outline 0.84 / 0.92, max twist 8.5 deg (bone_3), no warnings |
| 2026-10-29 | land2 (small hop, regenerated; replaces land) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames), audio on, prompt pins the hop low | 35 | coordinator: lower hop, panels level | OK: body 0.86% (land: 1.76%), limbs 0.88%, frame 0 match 0.90 / 0.95. Fit: median miss 2.83 px, outline 0.79 / 0.87, max twist 40.3 deg (bone_7), warning: body under the floor in 29 frames |
| 2026-10-29 | takeoff2 (low rise, regenerated) | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 5 s (121 frames), audio on, prompt pins the rise low | 35 | coordinator: still rises about a body height; side panel sits higher than the front | FAIL: panels disagree on the body by 2.41% of height (fail line 1.5%; first takeoff 2.14%), limbs 2.27% (WARN), frame 0 match 0.89 / 0.95. Not fitted |

Prompts live beside the clips in `Local/video2rig/dragon/clips/<clip>.prompt.txt`; per-clip provenance in `<clip>.json`.
Clips and prompts are not committed (Local/ is gitignored); the ledger here is the record.

## Reader and first fit (2026-10-28)

- Reader (64 keypoints, 9000 steps, MPS bf16, about 2 h 40 min while the GPU was shared): held-out median
  4.23 px front, 4.05 px side (p90 17.7 / 19.1). The tool's good band is 2 to 4 px. Kept as
  `reader/reader-64.pt`; a 78-keypoint reader (paw and wing-tip side points from the `limbs` setting) is training
  as `reader/reader-78.pt`.
- Idle fit: 124 frames at 24 fps, median keypoint miss 1.73 px, outline match 0.81 front / 0.90 side, no warnings,
  feet pinned in two stretches with 0.1% drift, nothing under the floor, largest twist 2.9 deg, largest one-frame
  jump 3.0 deg. Two hind-leg bones sat at a joint limit for 51 and 25 frames; check in Blender.
- Action imported: `Local/video2rig/dragon/Dragon_Idle_v2r_v1.blend` (123 frames). Review film
  `work/idle/review.mp4`. Blind A/B against `Dragon_Idle_Blender_v1r3` in progress.

## Blind A/B, round 1 (2026-10-28): raw video2rig idle vs hand-keyed idle

Package `Local/ab-idle-20261028/` (identical headless renders, three cameras, random labels; Opus critic saw only
the videos). Mapping after the fact: G3 = `Dragon_Idle_Blender_v1r3` (hand-keyed), L2 = `Dragon_Idle_v2r_v1`
(video2rig, untouched fit).

| Axis | hand-keyed | video2rig raw |
| --- | --- | --- |
| Weight and groundedness | 7 | 4 |
| Breathing | 5 | 3 |
| Head and neck intent | 6 | 4 |
| Wings and tail | 5 | 5 |
| Smoothness | 8 | 4 |
| Three-quarter silhouette | 5 | 6 |
| Loop readiness | 7 | 1 |
| Overall AAA boss idle | 5 | 3 |

Verdicts: hand-keyed APPROACHES, video2rig raw FAILS. Measured reasons for the loss: the clip does not close
(last-to-first jump 3 to 10 times a normal step, the last 25 frames nearly still), forefoot slides 4 to 6 px and
hovers 2 to 4 px above its shadow in the left view, a tail flick that stops dead for two frames. What it won:
the wings genuinely move (2.2x the body's motion) and the half-open pose has the menace the hand-keyed one lacks.

Reading: this matches the tool's own warnings (feet slide a little, pin them; long holds get retimed, not
regenerated; loops need the end pose asked for and then closed in Blender). His process refines in Blender after
the fit; so does our project rule. Round 2 = refit with the 78-keypoint reader, then a scripted Blender pass:
trim the still tail, close the loop, pin the four feet with IK, smooth the tail flick, keep the wing life. Then the
same blind A/B again. Full critique: `Local/ab-idle-20261028/critique.md`.

## Reader comparison (2026-10-28)

| Reader | Keypoints | Held-out front / side (median px) | Idle fit: median miss | outline front / side | max twist |
| --- | --- | --- | --- | --- | --- |
| reader-64 | 64 | 4.23 / 4.05 | 1.73 px | 0.813 / 0.897 | 2.9 deg |
| reader-78 | 78 (paw, claw, wing-tip side points) | 5.32 / 4.94 (the 18 off-bone points 5.6 / 6.5) | 2.05 px | 0.790 / 0.898 | 4.4 deg |

The extra side points did not improve the idle fit; `reader/reader.pt` stays the 64-point reader, `reader-78.pt` is
kept for a fast-motion clip where paw tracking matters more. Fits: `out/idle.npz` (64) and `out/idle-r78.npz`.

## Round 2 refinement (2026-10-28, scripted Blender pass on the fit)

`Local/video2rig/dragon/Dragon_Idle_v2r_v2.blend`, Action `idle_v2`, 90 frames (source frames 12 to 101; the still
tail began at 102). Scripts and JSON measurements in `Local/video2rig/dragon/refine/`.

| Measure | raw fit | refined | target |
| --- | --- | --- | --- |
| Seam jump vs normal step (bone rotation) | 17.0x | 0.95x | at most 1.5x |
| Seam jump on renders, front / left / three-quarter | 9.3 / 3.3 / 7.1x | 0.77 / 0.77 / 0.76x | at most 1.5x |
| Wing tips at the seam | not returning | 0.2 to 0.6 cm; silhouette top 2 to 3 px | within 3 px |
| Motion in the last second vs median | 0.50 / 0.27 / 0.32x | 1.13 / 1.04 / 1.09x | at least 0.5x |
| Foot excursion, four feet (cm; mesh 48 cm tall) | 0.32 / 0.58 / 0.02 / 0.02 | 0 / 0 / 0 / 0 | planted |
| Forefoot drift on renders, left / front | 6.5 / 7.9 px | 0.83 / 0.25 px | |
| Tail tip peak, 3D | 2.63 cm per frame (6.5x median) | 1.11 (2.9x) | no dead stops |

Departures: tail Gaussian ran six passes (sway lost about 30%); feet lowered 0.5 to 1.0 cm to touch the floor;
the loop blends the last 12 frames into the first frames instead of toward a frozen pose. Not achieved: a speed-up
over frames 79 to 86 (bone speed 1.86x median; the raw clip already peaks at 1.83x). Owner copies of the
side-by-sides: `~/Downloads/Veyr-Idle-AB-20261028/`.

## Blind A/B, round 2 (2026-10-28): refined video2rig idle (T6) vs hand-keyed idle (G3)

Fresh Opus critic, videos only. Summed 47 (T6) vs 41 (G3); T6 wins front, three-quarter and overall, G3 wins left.

| Axis | refined video2rig (T6) | hand-keyed (G3) |
| --- | --- | --- |
| Weight and groundedness | 6 | 7 |
| Breathing | 6 | 5 |
| Head and neck intent | 3 | 6 |
| Wings and tail | 6 | 3 |
| Smoothness | 8 | 6 |
| Three-quarter silhouette | 6 | 5 |
| Loop readiness | 7 | 4 |
| Overall AAA boss idle | 5 | 5 |

Both FAIL the shipped bar. Measured: T6 seam 0.86 to 0.92x a normal step (clean); all four feet 0 px in both clips;
T6 is one sine (every part keeps 90%+ of its motion in the 3.75 s cycle; head follows the chest at correlation 0.99);
T6 wings overlap the chest by 26 frames but pump 54 px, chest heaves 21 px (reads as panting). G3 repeats its first
frame last (seam step 0.14 to 0.35x normal, a visible freeze every 6 s), wings rigid (under 4 px vs hips), but its
head turns 44 px independently of the breathing.

Gap instructions: T6 needs a head-and-neck layer uncorrelated with the chest (correlation under 0.6, one look of 25+
px held 12+ frames) and a loop of 144+ frames so no part keeps more than 85% of its motion in one cycle; G3 needs
its duplicate end frame dropped. Full critique: `Local/ab-idle-20261028/critique-round2.md`.

Reading: with the refinement pass the AI-video route already edges the hand-keyed clip on a dragon idle, with the
wing life and silhouette the critic wanted; its remaining gap is a second motion layer, which the pipeline can
supply as another short clip ("idle look": head turn and hold) layered in Blender, or as a longer 8 s clip.

## Roar: wing flare limit (2026-10-28)

The MiniMax clip drew the flared wings about twice the model's wing size and past both panel edges from frame 40.
The reader placed the elbow 104 to 154 px from the wing root while the root bone is 82 px long, with moderate
confidence (0.6 to 0.9 on the side panel). The fit lays the bone at full length and cannot reach, so front outline
stays about 0.40 at peak flare whatever the setting: low-pass off, self-pass off, wrist range 1.6 or 2.8, root or
elbow prior 8 or 0.2, membrane prior 10, five fit settings. Kept: `joints.VeyrWing{PosZ,NegZ}Wrist.range = 1.6`
(twist 25.8 to 17.0 deg, outline unchanged). Reader confidence is not the limit; retraining would not help.

Rule from this: generated creature clips must keep body-part sizes. Add to every prompt "the wings, limbs, head and
tail keep exactly the size and proportions they have in the first frame; nothing grows" and "nothing leaves the
frame". Reject a clip whose parts outgrow the start picture before fitting it. Where a move needs the full span,
render the start picture with more margin (that means a new reader).

Refined roar anyway: `Local/video2rig/dragon/Dragon_Roar_v2r_v2.blend` (110 frames; feet 14 cm excursion to
0.003 cm; tail peak 6.6x to 3.0x median; head, jaw and wings untouched); renders `clip_RO1_*` in the A/B folder.

## Provider finding (2026-10-28): MiniMax ignores size constraints on this creature

Two roar clips, the second with an explicit "nothing grows, wings open only as far as their real span allows"
sentence: both draw the flared wings at about twice the model's span and push them past the front panel edge,
and the second adds motion blur on the side panel in the fast frames. The fits cannot follow (outline about 0.4 at
peak flare). The idle, with little wing travel, was unaffected. Options, in order of cost:
1. Try the same roar prompt on Seedance 2.5 (the generator the tool was tuned on) once, as a controlled test.
   Needs the owner's say-so: the standing instruction is MiniMax H3 Max.
2. Keep MiniMax and re-render the start picture with the wings folded tight and a wider margin, so the flare has
   room and the generator has less wing to exaggerate. Costs a new reader (about 3 h, free).
3. Keep the current roar fit (head, jaw, body and feet are good) and hand-flare the wings in Blender as a
   permitted correction; cheapest, and the wing pose is a few keys.

## Provider control run result (2026-10-28, late)

Seedance 2.5 on the same start picture and prompt: the side panel is far cleaner (outline 0.82, wing twist 8 deg
vs 26 to 69 on MiniMax, no motion blur), but the front panel still spreads the wings wider than the model and the
two panels disagree enough to fail the tool's own check (2.2% vs the 1.5% line). So the wing exaggeration is not a
MiniMax quirk; it comes from the start picture showing foreshortened, half-folded wings that any generator "unfolds"
to a span the rig does not have. Two responses run in parallel: one more Seedance clip asking for a half-open flare
no wider than the body length, and a corrective Blender pass that hand-keys the wing flare on the otherwise good
MiniMax roar fit (permitted correction). Longer term: render the start picture with the wings at their true full
span so the generator sees the limit, and train that reader.

Credit costs measured on Higgsfield (2026-10-28): MiniMax H3 Max 768p 5 s = 12.5; Seedance 2.5 720p 5 s with audio
= 35. Spend so far on this branch: 3 MiniMax + 2 Seedance = 107.5 credits.

## Roar refinement (Seedance fit, 2026-10-28)

`Dragon_Roar_sd_v2r_v2.blend` (Action `roar_sd_v2`, 121 frames, no trim: the move is still live at the end and
does not return to stance, so it will need a blend into idle in the engine). Feet excursion 1.3 / 5.3 / 0.03 /
0.04 cm to 0 on all four; forefoot drift on the front render 0.01 / 0.02 px. Tail peak 8.2 to 6.4 cm per frame,
still a visible spike from frame 37 (the clip's own tail whip); treat as a Blender hand-fix or accept as the
move's accent. Wings untouched: +25.7 px of span at the peak over frame 0. Renders `clip_RS1_*`; owner copies in
`~/Downloads/Veyr-Idle-AB-20261028/roar-*.mp4`.

## Rig finding that closes the wing question (2026-10-28, last)

Hand-keying the flare on the MiniMax roar (`Dragon_Roar_v2r_v3.blend`, renders `clip_RO2_*`) showed the real
limit: this rig's wings are already spread in a fan at rest, so rotating the wing bones reaches at most about
1.27x the rest span (54 cm vs 43 cm per wing) before the membrane tears or the wing hits the body. The fit's
earlier "flare" came from membrane stretch (9x to 24x on edges), not from span. So the generators were not only
exaggerating: they drew a flare the model cannot do. The Seedance half-open prompt matched the rig's reality,
which is why it fitted cleanly.

Rule: before writing a move prompt, measure the rig's reachable range for the parts the move uses (span, reach,
jaw opening) and describe the gesture inside it. The wing chains on this rig are also mirrored in name (PosZ sits
at -Y, NegZ at +Y); note that in creature.json comments.

Open items on the roar: the v3 end pose differs from the start (blend into idle in the engine or match the start);
the NegZ wing rises steeper than PosZ at the peak (body yaw and roll in the clip).

## Move data generator (2026-10-28)

`tools/movedata/` (README there): `sample_action.py` samples an Action headlessly in Blender, `build_moves.py`
writes `Data/dragon/{moves,boxes,tempo,sounds}.json` in the Leshy contract at game scale (x21.558172, about
1050 cm tall). Run on `idle_v2` and `roar_sd_v2` with `tools/movedata/run_veyr.sh`; output is deterministic.
Roar at 5 m/s: tail 1.34-2.14 s (peak 33 m/s at 1.66), jaw 1.47-1.78 s (peak 11.8 m/s at 1.55), wings
1.54-1.90 s (31-34 m/s), then a settle at 3.75-4.99 s (wings 8-10, tail 11 m/s). No shocks or contacts (feet stay
planted); track zero (Root static, body lurch 126 cm on Spine_0). Twelve hurt capsules, rest cover 0.77. C++ not
changed yet.

## Move data generated (2026-10-28, last commit of the day)

`tools/movedata/` (sample bones in headless Blender, build the blueprint's JSON) produced `Data/dragon/moves.json`,
`boxes.json`, `tempo.json`, `sounds.json` for `idle_v2` and `roar_sd_v2` at game scale (x21.56, the rig is 48.7 cm
tall in Blender and 1050 cm in game). Deterministic output, 3 tests pass.

Roar at the 5 m/s threshold: jaw hot 1.47 to 1.78 s (peak 11.8 m/s), wings 1.54 to 1.90 s (31 to 34 m/s), tail
1.34 to 2.14 s (33 m/s, the whip) with second waves after 3.7 s. Feet planted the whole clip (drift 0.01 to 1.85
cm; the right hind foot is over the 1.5 cm gate). Idle: one tail flick, loop seam 0.88x a step. Twelve hurt
capsules cover 0.77 of the mesh at rest.

Findings to carry into the runtime work:
- `tripo::Root` never moves; the body travels on `tripo::Spine_0` (126 cm lurch in the roar). Travelling moves
  need the track read from Spine_0 or a Root bake in Blender.
- At game scale the rig's rest pose floats: lowest foot 18 cm above the floor. Fix once in the import offset or
  the rest pose, not per clip.
- Nothing is curated yet: every fast window is an attack. Whether the roar's jaw or wings hurt is a design call
  for the brain pass.
- Wings as one capsule each cover air; legs are one capsule shoulder to foot. Split when the hit tests need it.
- The roar does not return to stance (seam 7.6x a step): the engine blends it back into the idle.

## Runtime: data-driven moves (compile-only, 2026-10-28)

First runtime piece of the blueprint (boss-runtime.md sections 2 and 4). Compiled headless with UnrealBuildTool only;
no editor, PIE or packaged game was launched, so nothing below is verified in play yet.

What was added (additive; every hard-coded move, timing, warning, leg region, head exposure, health and the knight
interfaces are unchanged):

- `Unreal/Veyr/Source/Veyr/VeyrMoveData.h/.cpp`: plain structs `FBossMove`, `FBossAttack`, `FBossShock`,
  `FBossContact`, `FBossPart` (plus `FBossTempoPhase`, `FBossSoundEvent`) and `FBossMoveData::Load`, reading
  `moves.json` and `boxes.json` (required) and `tempo.json`, `sounds.json` (optional, a broken one is a warning).
  Any missing or malformed required file logs `VEYR_MOVEDATA_FAILED ... dragon keeps its hard-coded behaviour` and
  leaves the data empty. Log category `LogVeyrMoveData`.
- Data path: CVar `veyr.MoveData.Dir` (empty by default), else `-VeyrMoveData=<dir>`, else
  `<ProjectDir>/../../Data/dragon` (the repository's `Data/dragon`, the default for editor/PIE), else
  `<ProjectDir>/Data/dragon`. The resolved folder is logged as `VEYR_MOVEDATA_DIR`. `veyr.MoveData.Enable 0` turns
  the whole layer off. Packaged builds do not stage `Data/` yet.
- `AVeyrDragon` (new file `VeyrDragonMoveData.cpp`, hooks in `VeyrDragon.cpp`): loads at BeginPlay; when the
  imported Customuse skeleton is present, one `UCapsuleComponent` `VeyrHurt_<part>` per boxes.json part is attached
  to its bone (`a`/`b` mapped into the bone's reference frame at load, radius in world cm, absolute scale).
  Bone names are matched exactly, then by letters and digits only (`tripo::Spine_0` = `tripo__Spine_0`).
  Import frame check: for yaw 0/90/180/270 the reference-pose bone heads are compared with the measured
  `|a_bone|`, `|b_bone|` distances; the best yaw and its residual are logged as `VEYR_MOVEDATA_FRAME` (over 40 cm
  is flagged SUSPECT).
- Collision: same response set as the existing solid body (WorldDynamic, query only, Block Pawn, everything else
  ignored, no step-up). `veyr.MoveData.HurtBlocksPawn` 1 (default) = every part but the two wing plates blocks
  the knight (the wing capsules mostly cover air, see the move-data findings), 2 = all, 0 = none. Pawn-blocking
  hurt capsules join the existing penetration resolver, so a moving part pushes the knight out like the solid body.
- Sword: `ReceiveSwordSweep` first tests every hard-coded region exactly as before; only a sweep that misses all of
  them is tested against the hurt capsules (`veyr.MoveData.SwordParts`, default 1). Part to region: the four leg
  capsules use their `leg` index (0 FL, 1 FR, 2 HL, 3 HR) so the per-leg stagger and the four-leg collapse loop
  work through them; `head` is region 4 (exposure bonus); neck, chest, belly, hips, wings, tail are region 5 (body
  damage times the part's boxes.json share: wings 0.5, tail 0.7, others 1.0). Part-aware entry
  `ReceiveSwordOnPart(part, contact, heavy, swing, multiplier)` and `ResolveHurtPart(component)`.
- Attack windows: per tick, after the pose is sampled, the current data move's windows whose `[t0, t1]` overlaps
  the tick's clip interval are hot. Attack part to capsule (`AttackPartCapsule`, UPROPERTY): jaw -> head,
  paw_fl/fr/hl/hr -> leg_fl/fr/hl/hr, wing_l/r -> wing_l/r, tail -> tail. Hit = segment distance from the part
  capsule to the knight capsule axis within the two radii, and a visibility line trace from the contact point to
  the knight centre (ignoring both actors) is clear; a blocked window stays open. One hit per window; loops never
  hurt. Damage per attack part (`AttackPartDamage`, UPROPERTY; knight health 100): jaw 34, front paws 29, hind
  paws 32, tail 30, wings 20; `ApplyBossDamage` keeps its roll, guard and grace rules.
- Move names: `fire/bellows/breath`, `flight/fly/flyaway`, `claw/claw_swipe`, `stomp/back_stomp`,
  `tail/tail_smack`, `bite` (case, `_` and `-` ignored) map onto `EVeyrDragonMove`; a mapped data move follows
  the hard-coded attack's clock from the wind-up. Today's data (`idle`, `roar`) maps onto nothing, so both are
  data-only moves and no hard-coded attack changes. `veyr.MoveData.Hits`: 0 never hurt, 1 (default) data-only
  moves hurt, 2 mapped moves hurt too and replace that move's hard-coded contact.
- Lab and gate lines: `veyr.MoveData.Dump` (moves, windows, parts, enum mapping, runtime binding, capsule world
  segments; with no dragon in the world it does a file check), `veyr.MoveData.Draw 1` (capsules green when they
  block the knight, cyan when query-only, red while their window is hot, plus a label with the move and clip time),
  `veyr.MoveData.Play <move>|none` (plays a data move from Idle; the brain does not choose attacks meanwhile; a
  clip named after the move, `roar` or `Roar`, plays if the visual definition has one, otherwise the capsules ride
  the idle pose), `veyr.MoveData.Reload`, and `-VeyrMoveDataDump` on the command line.
- Loaded but not yet used: `track` (all zero on this rig), `shocks`, `contacts`, `sounds`; tempo is applied only to
  data-only playback.

Build (headless UnrealBuildTool, the flags `tools/unreal/build.py` uses, log kept outside `Local/`):

    "/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" VeyrEditor Mac Development \
        -Project=/Users/midir/dragon-boss-fight/Unreal/Veyr/Veyr.uproject -NoUBA -NoXGE -NoFASTBuild -NoSNDBS \
        -MaxParallelActions=4 -NoHotReloadFromIDE -WaitMutex

Result (2026-10-28): `VeyrEditor Mac Development` -> `Result: Succeeded` (first full module build 19 actions; the
last incremental `[1/2] Compile VeyrDragon.cpp`, `[2/2] Link libUnrealEditor-Veyr.dylib`, 9.5 s). Also compiled
`Veyr Mac Shipping` with `UE_BUILD_FROM_XCODE=1` (compile and link only, no Xcode finalization, no app run):
`Result: Succeeded`. No errors or warnings from the new code; the only warnings are the existing "Referenced
directory ... Intermediate/VeyrBuild does not exist" (this checkout never ran `tools/unreal/build.py`, so the
source identity header is the fallback) and an engine MetalShaderConverter include notice on Shipping.

Not verified (needs an owned editor/PIE session):
- This checkout has no `Content/Characters/Customuse` (gitignored), so here the dragon runs on its primitive
  stand-in and the capsules stay unbound (`VEYR_MOVEDATA_HURT unbound`); binding needs the owner's imported mesh.
- Bone names of the imported skeleton against boxes.json (`bone_5`, `tripo::Spine_0`, `VeyrWingNegZElbow`, ...),
  the frame check residual, and that the capsules sit on the mesh (`veyr.MoveData.Draw 1`).
- Knight movement against the larger leg/body capsules (radius 80-125 cm vs the solid body's 60-75 cm shins): the
  existing collision stages and the guard/stance trials must be rerun; `veyr.MoveData.HurtBlocksPawn 0` restores
  the old movement envelope if they regress.
- Sword hits on thighs, belly, hips and wings through the new fallback, and leg stagger through the leg capsules.
- `veyr.MoveData.Play roar` window hits (no roar clip is imported yet, so the capsules ride the idle pose and the
  roar's windows test idle-pose parts).
- The Python integration tests in `Unreal/Veyr/Content/Python` import `unreal` and need the editor; not run.
  `tools/movedata` tests (no engine) pass: 3/3.

## Owner verdict — 2026-10-28 evening

Hari reviewed the before/after page on the laptop: refined video2rig idle vs hand-keyed (front, left, three-quarter)
and the Seedance roar. Approved outright: "the dragon looks much better", the roar "so, so good". He asked that the
shared brain and every future session always use this method; agents-md PR #32 promotes the creature exception to
the default. Remaining clips proceed on Seedance 2.5, one at a time, owner sees each.

## Remaining clips (2026-10-28/29)

Studio worker notes per clip: check numbers, fit numbers, scripted refinement (before/after), render paths. Scripts in
`Local/video2rig/dragon/refine/{collapse,death,bite}/` (gitignored); clips and Actions are not committed.

### collapse (6 s, 145 frames) - fit and refinement

`Dragon_Collapse_sd_v2r_v2.blend`, Action `collapse_v2`, 145 frames at 24 fps, no trim, no loop (ends lying). Script `refine/collapse/refine_fall.py`
(report `refine/collapse/refine_report.json`); renders `clip_CO1_{front,left,threequarter}.mp4` in the A/B video folder.
Phases: standing sway to frame 60, drop 60 to 84, lying from 100 (Spine_0 height 20.7 to 12.7 cm).

| Measure | raw fit | refined |
| --- | --- | --- |
| Feet excursion standing (frames 0 to 62), four feet, cm | 2.4 / 3.1 / 3.9 / 2.1 | 0 / 0 / 0 / 0 |
| Feet excursion lying (frames 100 to 144), cm | 0.27 / 1.10 / 0.02 / 0.74 | 0 / 0 / 0 / 0 |
| Lowest mesh point lying (cm, floor = 0), body+head / feet | -0.89 / -0.71 | +0.14 / +0.20 |
| -Y wing (PosZ) lowest point lying | -4.97 (45 frames under) | +1.27 |
| Wing root lift to clear the floor | | 9.0 deg (PosZ), 2.0 deg (NegZ) |
| Body lift (Spine_0 world Z, fall frames) | | max 1.79 cm over 84 frames |
| Tail tip lying (x, y, z cm) | (-8.9, 27.2, 13.9): curled sideways and up | (-53.4, 3.6, 1.3): flat behind, on the floor |
| Tail tip peak speed (cm per frame) | 19.2 at frame 72 | 4.9 (the fall keeps its whip; the ratio to the median, 108x to 54x, is meaningless in a mostly still clip) |
| Bones outside tail, wing roots, legs changed | | 0.000004 deg |

Findings: the side panel crops the tail once the dragon lies flat (the clip draws it past the panel edge), so the fit
curled it; replaced by the rest pose blended in over the fall and pitched 22 deg to lie on the floor. The fit put the
-Y wing 5 cm under the floor; fixed by rotating the wing root about the long axis, not by moving the body. Feet are
planted by temporary IK at the frame-0 pose until the drop starts (released over 10 frames) and at the settled pose
from frame 100 (ramped over 8 frames before).

### death (7 s, 169 frames) - fit and refinement

`Dragon_Death_sd_v2r_v2.blend`, Action `death_v2`, 169 frames, no trim, no loop (ends on the floor, rolled onto the right flank, Spine_0 at y -8.6 cm).
Script `refine/death/refine_fall.py` (same as collapse, `tail_flat=0`: the fit tail already hangs limp, tip z 6.3 cm lying), report
`refine/death/refine_report.json`, renders `clip_DE1_*`. Phases: stagger to frame 36, fall 36 to 87, lying from 87.

| Measure | raw fit | refined |
| --- | --- | --- |
| Feet excursion standing (frames 0 to 38), four feet, cm | 2.5 / 3.2 / 0.8 / 6.2 | 0 on all four |
| Feet excursion lying (frames 87 to 168), cm | 1.12 / 0.58 / 0.57 / 1.46 | 0 on all four |
| Lowest non-wing point lying (cm, floor = 0) | -2.42 (82 frames under) | +0.02 |
| Wing lowest point lying, -Y / +Y | -2.39 / -3.50 | +2.23 / +2.34 |
| Wing root lift to clear the floor | | 22.0 deg (PosZ), 12.0 deg (NegZ) |
| Body lift (Spine_0 world Z) | | max 2.57 cm over 133 frames |
| Tail tip peak speed (cm per frame) | 3.48 | 2.58 |
| Bones outside tail, wing roots, legs changed | | 0.000003 deg |

Remaining defects: while the planted feet fade out during the fall, a leg segment goes up to 1.85 cm under the floor in
transit (lying frames are clean); the hind +Y foot reaches its lying plant target within 0.64 cm, not exactly. Max leg-chain
rotation change from planting 22 deg. The fit itself is the weakest of the set (median miss 7.07 px), so the stagger and the
roll are the reader best read, not exact; treat the death as a candidate for a re-generate or a hand pass if it ships.

### bite (5 s, 121 frames) - fit and refinement

`Dragon_Bite_sd_v2r_v2.blend`, Action `bite_v2`, 121 frames, not trimmed (the fit is still moving at frame 120). Script `refine/bite/refine_bite.py`
(report `refine/bite/refine_report.json`), renders `clip_BI1_*`. Steps: end pose blended onto frame 0 over the last 24 frames, wing
clamp to 1.27x of the frame-0 lateral extent, tail spike smoothing, four feet planted at the frame-0 pose for the whole clip.

| Measure | raw fit | refined |
| --- | --- | --- |
| End pose vs frame 0 (summed bone angle) | 8.02 rad (the fit does not return to stance) | 0 (identical frame) |
| Blend region peak step vs median step | | 2.27x (12-frame blend gave 3.0x, so 24 was kept); whole-clip peak 5.4x is the strike itself |
| Wing lateral extent, -Y / +Y, max over frame 0 | 1.236x (at frame 120) / 1.04x | 1.18x / 1.04x: under the 1.27x cap, no clamp needed |
| Head: nose ahead of chest front, max / min (cm) | 24.2 / 11.5 | same; the strike reaches 24.2 against 24.4 cm of straight neck |
| Feet excursion, four feet (cm) | 1.11 / 5.74 / 0.04 / 0.14 (the -Y front foot) | 0 on all four |
| Tail tip peak speed (cm per frame) | 6.04 (15.0x median) | 3.02 (7.5x), 8 passes touching 72 frames |
| Bones outside tail, wings, legs changed | | 0.000003 deg |

The wing worry did not appear in the fit: the raw peak is 1.236x of the frame-0 extent, at the last frame where the fit has not
returned, and closing the pose brings it to 1.18x.

### claw_swipe (5 s, 121 frames) - fit and refinement

`Dragon_ClawSwipe_sd_v2r_v2.blend`, Action `claw_swipe_v2`, 121 frames at 24 fps, not trimmed. Script `refine/move/refine_move.py`
(`ground=auto floor_lift=1`, report `refine/claw/refine_report.json`), renders `clip_CS1_*` refined and `clip_CS0_*` raw fit.
Reader comparison on this fast move (the idle comparison had favoured reader-64): reader-78 kept. Both readers give the same
mean outline (0.826 / 0.824); reader-78 has lower twist (41.8 vs 65.8 deg) and keeps the hind feet and body down (reader-64 shows
both hind feet lifting 2.6 cm for frames 77 to 101 and needs a 2.6 cm body lift; reader-78 needs none).

| Measure | raw fit (reader-78) | refined |
| --- | --- | --- |
| Foreleg peak reach, shoulder to claw tip (right foreleg) | 25.1 cm at frame 69 (rest 24.5) | unchanged; 83% of the 30.1 cm extended-leg limit, never past its own length |
| Swinging foot (front -Y): lift / travel from its frame-0 spot | 32.3 cm / 35.0 cm | free for frames 31 to 105, planted 0 to 30 and 106 to 120 |
| Feet excursion while planted (three planted feet, whole clip; swinging foot on its grounded frames) | 0.58 / 0.29 / 1.58 cm (front +Y, hind -Y, hind +Y) | 0.00 / 0.01 / 0.00 / 0.00 cm |
| End vs frame 0 (summed bone angle) | 6.13 rad | 0 (last 24 frames blended; blend peak step 2.46x median, whole-clip peak 4.1x) |
| Wing lateral extent over frame 0, -Y / +Y | 1.00x / 1.08x | same, no clamp needed (cap 1.27x) |
| Spine_0 height | min 19.6 (frame 17), end 21.0 | same, no lift needed |
| Tail tip peak speed (cm per frame) | 4.15 | 4.10 (nothing above 3x the median) |

Caveat: the nose reaches 32.2 cm ahead of the chest front at frame 71, 7.8 cm past the 24.4 cm straight-neck figure; the lean
and head dip carry it. Not corrected.

### stagger (5 s, 121 frames) - fit and refinement

`Dragon_Stagger_sd_v2r_v2.blend`, Action `stagger_v2`, 121 frames, same script (`ground=auto floor_lift=1`, report
`refine/stagger/refine_report.json`), renders `clip_ST1_*` refined, `clip_ST0_*` raw.

| Measure | raw fit | refined |
| --- | --- | --- |
| End vs frame 0 (summed bone angle) | 7.85 rad | 0 (24-frame blend, peak step 2.23x median; whole-clip 3.8x) |
| Left forefoot (front +Y) catch-step | 7.75 cm travel, 2.6 cm lift | free for frames 24 to 101, planted before (0 to 23) and after (102 to 120) |
| Other three feet | 3.30 / 1.02 / 0.82 cm | 0 / 0 / 0 |
| Wing lateral extent over frame 0, -Y / +Y | 1.14x / 1.11x | same, under the 1.27x cap |
| Body lift (Spine_0) | | max 0.82 cm over 102 frames |
| Tail tip peak speed (cm per frame) | 2.51 | 1.07 (8 passes, 37 frames) |

### land (5 s) - check FAIL, not fitted

`check` body 0.0176 (1.76% of height, fail line 1.5%, clean clips up to about 1.2%), limbs 0.0116, frame 0 0.91 / 0.96. The tool: the
panels draw the hop differently (the two views disagree on how high the body is). Not fitted, no Action; needs a new generation.

### takeoff (5 s) - check FAIL, not fitted

`check` body 0.0214 (2.14% of height, fail line 1.5%), limbs 0.0154 (also over), frame 0 0.93 / 0.96. The tool: the panels draw the move
differently in each panel. Not fitted, no Action. Both airborne moves (land, takeoff) fail the same way: when the body leaves the floor
the two panels disagree on its height, which the reader cannot reconcile; a regenerate with a smaller rise, or a flying-specific start
picture (side-over-top stack, see the tool framing options), is the lead.

### rise (recovery, 5 s, 121 frames) - fit and refinement

`Dragon_Rise_sd_v2r_v2.blend`, Action `rise_v2`, 121 frames, same script (`ground=auto floor_lift=1 W=36`, report `refine/rise/refine_report.json`),
renders `clip_RI1_*` refined, `clip_RI0_*` raw. A 24-frame close put the clip drop and the blend together (peak step 5.8x median); 36 frames gave 3.4x
(whole-clip 4.5x), so 36 was kept.

| Measure | raw fit | refined |
| --- | --- | --- |
| End vs frame 0 (summed bone angle) | 7.17 rad | 0 (36-frame blend) |
| Hind feet (planted the whole clip) | 0.77 / 0.26 cm drift | 0.00 / 0.00 cm |
| Forefeet: lifted frames 66 to 105 (+Y) and 66 to 110 (-Y), max lift 23.5 / 22.2 cm, 6.0 / 4.6 cm sideways | free | planted 0 to 65 and 106 to 120: 0.003 / 0.006 cm drift |
| Spine_0 height | 20.9 start, 16.2 at the crouch (frame 53), peak 24.3 at frame 87 (rise +3.3 cm over frame 0), 20.9 end | same  |
| Wing lateral extent over frame 0, -Y / +Y | 1.07x / 1.16x | same, under the 1.27x cap |
| Body lift | | max 0.36 cm over 18 frames |
| Tail tip peak speed (cm per frame) | 2.54 | 1.44 |
| Foreleg reach, shoulder to claw tip | 26.4 / 26.4 cm | unchanged, 88% of the 30.1 cm limit |

Distance from the collapse end to the rise start (for the blend in game): collapse `collapse_v2` last frame vs `rise_v2` frame 0:
vertex shift mean 21.0 cm, p95 38.9, max 46.1 (rig scale; x21.56 in game); summed bone angle 26.7 rad; mean height difference 17.2 cm
(lying vs standing); largest bone differences are the wing chain (VeyrWingPosZElbow 112 deg, Wrist 107 deg, VeyrWingNegZRoot 99 deg) and the
forelegs (tripo::1_Left_Limb_0 101 deg, tripo::0_Left_Limb_0 80 deg). The rise starts standing, so the engine blend from the collapse end has to
do the get-up itself: it is a 17 cm lift plus folding the wings and legs, not a small pose blend. The rise clip is the stand-up from frame 53
(crouch) onward, but the clip begins already standing; a better source for a post-collapse recovery is a clip whose first frame is the lying pose.

### idle_look (8 s, 193 frames) and the idle comparison

`Dragon_IdleLook_sd_v2r_v2.blend`, Action `idle_look_v2` (refine_move `ground=all W=24`, report `refine/idle_look/refine_report.json`): end blended onto
frame 0 over the last 24 frames (the fit ended 5.67 rad of summed bone angle from the start; blend peak step 4.0x median), feet planted the whole clip
(0.75 / 2.55 / 0.02 / 0.05 cm to 0), wings 1.03x / 1.01x of frame 0, tail tip peak 1.68 to 1.05 cm per frame. Renders `clip_IL1_*` (refined), `clip_IL0_*` (raw).
`Dragon_IdleLayered_sd_v2r_v2.blend`, Action `idle_layered_v2` (script `refine/idle_look/layer_idle.py`): idle_v2 for the whole body, played 6.7% slower so two
cycles fill the 192 steps and the loop closes exactly, plus the look clips neck and jaw motion added on top in bone-local space (bone_3, bone_4, bone_5,
VeyrJaw, relative to the look clips frame 0). Replacing the head chain outright gave a 6.4 cm nose bob (the idle_v2 head compensates its own chest
tilt); the additive version has 2.1 cm. Renders `clip_IL2_*`. All three Actions are kept.

Measured (`refine/move/idle_metrics.py`, JSON in `refine/idle_look/metrics_*.json`; yaw = nose direction from bone_3 in plan view minus the body direction,
relative to frame 0; positive = toward +Y, the dragons left; breathing = height of the mean torso vertex):

| Measure | idle_v2 (3.75 s) | idle_look_v2 (8 s) | idle_layered_v2 (8 s) |
| --- | --- | --- | --- |
| Head yaw range, min / max (deg) | -4.3 / 6.5, range 10.8 | -37.8 / 0.4, range 38.2 | -38.9 / 6.9, range 45.8 |
| Head pitch range (deg) | 2.7 | 2.5 | 5.5 |
| Nose travel y / z (cm) | 3.3 / 0.9 | 15.5 / 0.4 | 15.1 / 2.1 |
| Breathing, torso height peak to peak (cm), period | 1.53, 3.75 s | 0.30, 8 s (does not breathe at the clips own rate in the fit) | 1.53, 4.0 s |
| Tail tip y / z range (cm) | 4.9 / 11.9 | 6.0 / 1.2 | 4.9 / 11.9 |
| Wing lateral range, +Y / -Y (cm) | 1.19 / 1.76 | 0.82 / 1.41 | 1.19 / 1.75 |
| Loop seam (step across the join over the median step) | 0.95 | 0.98 (last frame is a copy of frame 0, step from frame 191) | 0.93 |
| Feet excursion | 0 | 0 | 0 (idle_v2 legs) |

Findings: (1) the clip turns the head toward the dragons right (-38 deg; the source frames show the head swinging to screen-left in the front panel), not
to the left as the prompt asked, and returns without the slight turn the other way (max +0.4 deg); the fit is right, the generator mirrored the instruction.
(2) idle_look has the head intent but almost no breathing (0.3 cm) and little tail sway (z 1.2 cm); idle_v2 has breathing and tail but only 10.8 deg of head
motion. The layered Action has both: 45.8 deg of head yaw and idle_v2 breathing, tail and wing motion, a clean seam, same planted feet. Candidate for the
final idle; the owner decides on the renders (the 1.5 cm breathing figure is the idle_v2 fits and may be larger than a dragon this size would breathe).

### land2 (small hop and hard landing, 5 s) - fit and refinement

`Dragon_Land2_sd_v2r_v2.blend`, Action `land2_v2`, 118 frames (3 still frames trimmed from the end), `ground=auto floor_lift=1 W=24 dz=2 dxy=8` (report `refine/land2/refine_report.json`),
renders `clip_LA1_*` refined, `clip_LA0_*` raw. The panels now agree (the first land failed at 1.76%), but the hop is still not low: Spine_0 rises 28.9 cm (0.59 body
heights, peak 49.8 cm at frame 61) and the feet leave the floor by up to 28 cm (hind) and 41 cm (fore), against the prompts knee height of about 10 cm.

| Measure | raw fit | refined |
| --- | --- | --- |
| Takeoff frame (all four feet off the floor) | | 39 (hind feet leave at 38 to 39, fore at 37 to 38) |
| Touchdown frame, per foot | | front +Y 84, hind 85, front -Y 86: all four down from frame 86 |
| Airtime | | 46 frames, 1.9 s |
| Crouch before the hop (Spine_0) | 17.8 cm at frame 33 (standing 20.9) | same |
| Peak descent speed of Spine_0 | 0.71 m/s at frames 71-72 (x21.56 = 15.2 m/s in game) | same |
| Landing deceleration of Spine_0 | peak 5.6 m/s2 at frame 78 (122 m/s2 in game) | same; the movedata run records the shock windows |
| Landing crouch (Spine_0 minimum after touchdown) | 18.9 cm at frame 90 (2.0 cm below standing) | same; the prompt asked for the chest almost on the floor |
| Planted feet, planted frames (0 to 37 and from touchdown) | the feet spread up to 15.7 cm on the landing (front -Y) | 0.006 / 0.019 / 0.005 / 0.003 cm |
| Free feet (airborne) | | not planted |
| End vs frame 0 (summed bone angle) | 8.31 rad | 0 (24-frame blend, peak step 1.4x median; whole-clip 5.9x is the hop) |
| Wing lateral extent over frame 0, -Y / +Y | 1.07x / 1.02x | same (cap 1.27x, no clamp needed) |
| Body lift (Spine_0) | | max 5.6 cm over 50 frames (the crouch and landing sank the fit under the floor) |
| Tail tip peak speed (cm per frame) | 12.7 | 8.7 (the landing whip) |

The spine stops falling at frame 78, six frames before the feet register as grounded (84 to 86): the legs reach down and the body is already
decelerated when they touch; the shock for gameplay is better read from the foot contacts (frames 84 to 86) than from the spine.

### takeoff2 (5 s) - check FAIL, not fitted; airborne moves

`check` body 0.0241 (2.41%), limbs 0.0227, frame 0 0.89 / 0.95, same message as takeoff: the two panels draw the body at different heights. A lower
rise in the prompt did not help (2.14% then 2.41%). Not fitted, no Action. Land2 passed once the hop was pinned low in the prompt (1.76% then 0.86%), but
takeoff, where the body stays up, did not.

Finding: airborne moves need a flying start picture and a reader trained on it. Likely cause (not tested tonight): the start picture and the reader both
assume feet on a floor, and a hovering body has no floor reference to keep the two panels at the same height. Out of scope tonight; the takeoff and
fly-hover stay on the hand-keyed Blender versions until then.

### Summary, cost and review page (2026-10-29)

| Clip | Result | Action | Credits |
| --- | --- | --- | --- |
| collapse (6 s) | fitted, refined | `collapse_v2` | 48.4 derived |
| death (7 s) | fitted, refined (weakest fit) | `death_v2` | 56.5 derived |
| bite | fitted, refined | `bite_v2` | 35 |
| claw_swipe | fitted (reader-78), refined | `claw_swipe_v2` | 35 |
| stagger | fitted, refined | `stagger_v2` | 35 |
| land (first take) | check FAIL 1.76%, not fitted | none | 35 |
| land2 | fitted, refined | `land2_v2` | 35 |
| takeoff (first take) | check FAIL 2.14%, not fitted | none | 35 |
| takeoff2 | check FAIL 2.41%, not fitted | none | 35 |
| rise | fitted, refined | `rise_v2` | 35 |
| idle_look (8 s) | fitted, refined; layered with idle_v2 | `idle_look_v2`, `idle_layered_v2` | 64.6 derived |

Cost note: Higgsfield balance 1241.64 at the start of the session, 792.14 at the end: 449.5 credits on 11 renders (9 first takes = 379.5, plus land2
and takeoff2 at 35 each). The 5 s clips cost 35; the 6, 7 and 8 s clips (collapse, death, idle_look) share 169.5 credits over 21 s, about 8.07 per second, so
the per-clip figures above are derived and should be checked against the transaction list. Branch total with the earlier 107.5 credits (3 MiniMax at 12.5, 2
Seedance at 35): 557.0. The failed first land and takeoff stay in the ledger as failed takes.

Review page: `Local/dragon-review-20261029/serve/index.html` (`rangeserver.py` beside it, no server started). Per move: Seedance source clip, hand-keyed
before where one exists (idle, bite, claw swipe, land, takeoff, from the review checkout, opened read-only), raw fit and refined renders from three angles; the
idle row compares idle_v2, idle_look_v2 and idle_layered_v2. Move data rebuilt for every Action by `tools/movedata/run_veyr.sh` (Data/dragon/*.json).

### Fix round 1 (2026-10-29): v3 Actions from the blind critique

Source of the list: `Local/dragon-review-20261029/critique.md` (blind critic, 0 of 11 rows meet the bar). Refinements on the existing Actions, saved as new
`Dragon_<Move>_sd_v2r_v3.blend` / `<move>_v3` (v2 untouched). Script `Local/video2rig/dragon/refine/v3/refine_v3.py` (and `refine_fall_v3.py` for collapse and death),
starting from the raw import, never from v2. Review page `Local/dragon-review-20261029/serve/index.html` has a "round 1" cell beside the round 0 "after" on every
touched row (lazy-loaded videos); renders `clip_<RS|CO|DE|BI|CS|ST|LA|RI>3_*`.

| Fix | Before | After |
| --- | --- | --- |
| 1 Shared stance (stance = idle_v2 frame 0, velocity-matched offset blend over 12 frames at the start and 12 at the end, 24 for roar and bite) | frame 0 / last front overlap with the stance: roar 0.82 / 0.80, bite 0.82, claw 0.82, stagger 0.81, land2 0.82, rise 0.82; feet 15 to 18 mm (9 to 11 px) off the stance | 1.000 / 1.000 (front and side) on all six; feet 0.0 mm. Over the first and last 6 frames the minimum is 0.76 to 0.97 (roar 0.95 / 0.97, bite 0.86 / 0.91, claw 0.89 / 0.84, stagger 0.76 / 0.83, land2 0.91 / 0.83, rise 0.88 / 0.85): the moves start and finish moving inside those frames, so 95% holds on frames 0 and last only. The layered idle was already 1.000. Roar ends on the stance (seam 7.62x to 0.00x of a step) |
| 2 4-frame stutter (cause: the importer keys at content time, the tool read the clips as 30 fps with every 5th frame dropped; the fits step uniformly per container frame, ratios 0.97 to 1.04) | critic-style mod-4 phase ratios, range: claw 0.24, rise 0.25 (bite 0.24 on this measure) | keys at container time i/24: claw 0.08, rise 0.07 (bite 0.08); stagger and land2 are native 24 fps, stagger 0.04 to 0.06 |
| 3 land2 | touchdown frames 84 to 86 (hover 75 to 81), body lift 5.6 cm, hop leaves the frame | take-off 39, touchdown 73, all four feet planted by IK on the floor at 74 to 75; parabola on Spine_0 through the take-off and touchdown heights (apex 23.2 cm above the line, peak 49.4 cm); body lift 0.8 cm (feet and wings excluded); tall review camera (3.1 m back, aimed 0.40 m up) keeps the whole hop in shot |
| 4 stagger | 12 dead frames, catch-step drag, 40 px | first 12 frames trimmed (clip 109 frames), recoil starts at frame 2; the catch-step foot lifts 3.0 cm over frames 15 to 27 (and again 92 to 104 on the return). Head minimum height above the floor 5.68 cm in v2 and v3: the chin does not clip |
| 5 roar | front span 502 px at the peak (idle 505), tremor 0 | flare on the stance wings (OPEN pose, scale 0.85, Root offset per side for the body roll) over frames 44 to 84: front span 604 px, 1.20x idle (one wing 1.255x, the other 1.157x). The 1.25x target (640 px) is not reached: the rig peaks near 1.24x per wing at this pose family and tears the membrane beyond (a 1.47x pose tears about 1000 edges per wing; this one 249 and 225); head/chest tremor 0.35 cm (2 px) over frames 46 to 85 |
| 6 bite | jaw shut through the strike, 32-frame frozen hold | VeyrJaw opens to 38 deg by frame 36, held to 43, shut by 46; hold frames 58 to 90 compressed to 58 to 70, recovery 90 to 120 stretched to 70 to 110 (111 frames, 4.6 s) |
| 7a death | frames 120 to 168 keep moving (mean frame change 1.87), drift 100 to 168 of 18.9 | all channels damped to a hold from frame 110: change 0.0 after frame 120, drift 100 to 168 of 6.7 (all inside the 100 to 110 damping), upper wing frozen |
| 7b collapse | -Y wing a stiff strip out to x 154 at frame 144 (9 deg root lift) | root lift capped at 3 deg, the wing swept back 24 deg about the vertical axis over frames 85 to 110 and folded at the elbow (up to 24.6 deg) so it clears the floor by 1.2 cm: leftmost front silhouette x 264 (target 250), width 554 to 444 px |
| 8 rise | listed as a recovery | marked "recovery-from-stance": it starts and ends standing; the lying-start get-up comes with a new clip |

Findings from the work: the critic's 4-frame stutter was in the importer's timing assumption, not in the fit; the jaw is not moved by the fit at all (it is authored
now); the roar's two wings cannot both reach 1.25x because of the body roll in the clip.

## Airborne pipeline (2026-10-29): hover start picture and reader

Why: land and takeoff failed the check three times (1.76, 2.14 and 2.41% of height) because a body off the floor has no floor reference in the ground start picture.
Project `Local/video2rig/dragon-air/` (sibling of `dragon/`; rig exported from the hover pose so the tool treats it as the start pose; reader trained fresh).
- Hover pose: new Action `hover_pose_v1` (script `dragon-air/hover/author_hover.py`, parameters `hover_params.json`, report `hover_report.json`): Spine_0 raised so the lowest foot is
  48.7 cm above the floor (one body height; the trailing tail tip is at 34.6 cm), body levelled (the rest pose stands 18 deg nose-up), wings 1.22x the rest span (96.9 cm tip to tip), legs tucked,
  tail trailing down and back, head level, jaws closed. No existing Action touched.
- Pictures: `start/start.png` (hover) and `start-ground/start.png` (standing), the same two cameras and floor. Flags: `render_start.py --facing +X --widths 840,1080 --margin-wide 1.25
  --hover 0.58935 --lens 50 --engine CYCLES --samples 64` (frame height widened to 1.557 m by the hover; the ground picture reuses the cameras through `render_start_air.py --cameras-from`).
  A perspective camera replaced the orthographic one: a level orthographic camera sees the floor edge-on, so the first hover picture showed no floor and no height cue at all.
- Reader: 64 keypoints, 9000 steps, MPS bf16, normal priority; fork branch `air-reader` (`poses.py` opt-in `air` key: 55% of the poses lifted up to 1.3 body heights, 35% starting from the
  standing stance, lifts lowered until the body is inside both panels; `--copies 1` because a perspective camera cannot share a frame with copies). Poses 297 s, pictures 852 s, training 10,295 s (172 min total).
  Held-out median error: front 7.31 px, side 6.68 px (p90 44.7 / 35.7); the 18 off-bone points 8.48 / 8.97 px. The ground reader got 4.23 / 4.05. The airborne reader is less exact:
  a wider pose range, a taller frame (the dragon is smaller in it) and a perspective camera. Expect fits near 3 to 5 px median rather than 2 to 3.
- Prompts (`dragon-air/clips/*.prompt.txt`, notes in `README-air-prompts.txt`): `air_fire_down`, `air_land`, `air_hover`, `takeoff3` (start = ground picture, end = hover picture).
  Higgsfield media ids: hover 3d674b17-e4f8-4a0b-b90c-a6edb3f55476, ground 2e796531-c58c-4f75-b7c0-762510fb5bc1.

### Airborne clips (2026-10-29): air_hover, air_land, takeoff3, air_fire_down

Four Seedance 2.5 clips from the hover and ground start pictures (media ids hover 3d674b17-e4f8-4a0b-b90c-a6edb3f55476, ground 2e796531-c58c-4f75-b7c0-762510fb5bc1; air_land has the
ground picture as end image, takeoff3 starts on it and ends on the hover picture). Credits recorded 35 each (5 s rate; the 6 s air_land and 8 s air_fire_down to verify). Provenance json
beside the clips in `Local/video2rig/dragon-air/clips/`; jobs 119fc989 (air_land), ca748e9a (air_hover), 32d41f49 (takeoff3), 0929c03a (air_fire_down).

| Clip | Check | Fit (airborne reader) | Action |
| --- | --- | --- | --- |
| air_hover (5 s, 121 frames) | WARN: no panel check with perspective cameras; centroid proxy 0.14% of height median | median miss 2.57 px, outline 0.74 / 0.88, max twist 26.4 deg, no warnings | `air_hover_v3`, loop, ends blended onto `hover_pose_v1` (fit ends 7.2 rad away) |
| air_land (6 s, 145 frames) | WARN: start pose covers frame 0 only 0.83; proxy 3.6% median | median miss 4.84 px, outline 0.66 / 0.71, twist 77 deg, a 297 deg bone flip at frame 106, outline down to 0.30 in the landing | `air_land_v3`: legs held from frame 84, feet IK-planted from frame 90 (authored touchdown), last 40 frames crossfaded onto the standing stance |
| takeoff3 (5 s, 121 frames) | WARN: start pose covers frame 0 only 0.55 / 0.46 (the project start pose is the hover, the clip starts standing); proxy 2.9% | median miss 5.53 px, outline 0.61 / 0.70, twist 69 deg, 112 spikes smoothed | `takeoff3_v3`: stance start standing, end hover; wings clamped to the 1.27x limit (19 and 7 frames); the fit rises to 115 cm and settles at 63.8 cm (overshoots the hover by 50 cm) |
| air_fire_down (8 s, 193 frames) | WARN: no panel check; proxy not a height test (the body pitches) | median miss 4.31 px, outline 0.81 / 0.83, twist 31 deg, no warnings | `air_fire_down_v3`: body pitch kept (hip-to-chest line +21 to -8 deg over frames 72 to 160), root height pinned to the hover height (the fit sank by 7.4 cm), jaw authored 40 deg open frames 80 to 160 (the fit does not move the jaw), ends on the hover pose |

`video2rig check` only compares orthographic panels, so none of the four got the panel-disagreement test that failed land and takeoff; the verdict is WARN, not OK, and the fits are
the evidence (the three lower-quality fits are the ones with landing and take-off motion). The panel proxy (`panel_agree.py`: vertical centroid of the dragon mask in each panel against
frame 0) gives 0.14% for the hover and 2.8 to 3.6% for the three others (the failing ground clips were 1.8 to 2.4% on the real check); it is not equivalent.
Refinement script: `refine_v3.py` with new options `stance_end`, `floor_feet_npz`, `masks_after_stance`, `end_mode=crossfade`, `touch`, `legs_hold_from`, `plant_ramp`, `pin_root_z`, `limit_abs_cm`, `plant=none`.
Move data: `air_hover` (loop), `air_land`, `air_takeoff`, `air_fire_down` in `Data/dragon/moves.json` with `airborne` and `floor_metrics_valid: false` (the generator infers the floor from the lowest foot, so
the shocks, contacts and stances of the air moves are artifacts); annotations: `fire_down_hold` 3.333 to 6.667 s (jaws open, head down: the Niagara window) on `air_fire_down`, `touchdown` at 3.75 s on `air_land`.
Review page: section "Airborne" (renders `AH`, `AL`, `TK`, `FD`, 0 = raw fit, 1 = refined; takeoff3 on an extra-tall camera because the fit rises to 1.15 m).

### Fix round 2 (2026-10-29): v4 Actions from the round-2 critique

Spec: the ranked fix list in `Local/dragon-review-20261029/critique-round2.md`. Nine new Actions `<move>_v4` in
`Local/video2rig/dragon/Dragon_<Move>_sd_v2r_v4.blend` (v2/v3 untouched; claw swipe, stagger, death, idle unchanged).
Scripts: `tools/dragon_refine/v4/` (`refine_v4.py` recipes, `lib_v4.py`, `measure_v4.py`, `run_queue_v4.sh`).
No Higgsfield clip was generated and no reader was trained.

**How it was measured.** The GPU was held by another session (STREAMING window, then a foreign MPS trainer at 100 %,
`gpu_slot capture` exit 75), so no EEVEE render was made. Every number below comes from a CPU raster of the evaluated
mesh through the review cameras (`raster.py`, z-buffered, the critic's plates), scored with the critic's own
definitions (`critic.py` is a port of its `met.py` / `air.py`). Calibration against the critic's cached v3 render masks
(`refine/v4/calibration.json`): silhouette IoU 0.79 to 0.88, lowest row within 1 to 8 px, frame-step correlation 0.93
to 0.996. Per-frame-change (hold) numbers are raster values times that clip's own critic/raster ratio. Airborne v4 clips
use the extra-tall K camera (the T frame cuts off the wing tips on the upstroke), so their pixel limits scale by
158/227 against T. Full numbers: `Local/dragon-review-20261029/measure_v4.json` (v3 and v4 side by side).

**Sourced vs authored.** The source videos have **no wing beats** (hover top row moves 12 px on a 40-frame sway; the
generator made a glide), so every wing beat is procedural: one beat function (26-frame period, not a multiple of 4,
or the beat aliases into the critic's 4-frame saw) on the wing root, elbow and wrist over the hover pose, with the
fit's own high-pass wing detail kept. Body bob is a table measured from the visible wing-tip height (`bob_table.py`).
Everything else keeps the fitted motion and adds authored layers; each report JSON (`refine/v4/*.report.json`)
lists `sourced` and `authored` per move.

| # | Item, target | v3 (round 1) | v4 (round 2) | Result |
| --- | --- | --- | --- | --- |
| 1 | Takeoff: feet down until ≥ 36 | liftoff frame 2 | 53 | PASS |
| 1 | crouch ≥ 0.08 BH | 0.00 | 0.101 | PASS |
| 1 | span +30 % in 6 frames before liftoff | −1 % | +56 % (liftoff on the first downstroke) | PASS |
| 1 | peak / end height ≤ 1.2 | 2.20 | 1.06 | PASS |
| 1 | centroid change last 24 frames ≤ 0.1 BH | 0.84 | 0.14 (one beat of bob; mean-height change vs the previous 24 frames 0.14) | FAIL |
| 5 | takeoff foot jump ≤ 8 px T | 21 px | 3 px K | PASS |
| 2 | Wing-tip p2p ≥ 0.5 BH (hover / land / takeoff / fire) | 0.04 / 0.35 / 1.09 / 0.14 | 0.65 / 0.76 / 1.11 / 0.87 | PASS |
| 2 | period 18 to 30 | 40 / 78 / 109 / 193 | 26.2 / 26.0 / 29.0 / 27.6 | PASS |
| 2 | body bob ≥ 0.06 BH | 0.027 / 0.40 / 0.99 / 0.25 | 0.14 / 0.38 / 0.75 / 0.36 (land, takeoff, fire include the descent, rise or pitch) | PASS (hover is the clean case) |
| 2 | corr(wing-tip velocity, body accel) ≥ 0.6 at lag 0 to 4 | 0.12 / 0.13 / 0.24 / 0.08 | −0.37 / −0.33 / −0.45 / −0.29 (best −0.47 to −0.59 at lag −1 to −5) | FAIL |
| 2 | span drift ≤ 5 % (beat-averaged) | 0.16 / 0.03 / 0.24 / 0.11 | 0.009 / 0.011 / 0.007 / 0.073 | PASS 3 of 4 (fire: the sourced nose-down pitch narrows the front span) |
| 3 | Hover seam ≤ 1.2 steps | 0.0 | 0.0 | PASS |
| 3 | span change last 8 frames ≤ 3 % | 5.4 % | raw 44 % (mid-beat); against the same beat phase one beat earlier 1.1 % | FAIL raw / PASS phase-matched |
| 3 | saw ≤ 0.07 both views | 0.26 / 0.30 | 0.020 / 0.026 | PASS |
| 4 | Roar hold change ≥ 1.2 | 0.94 (critic 0.77) | 3.5 (est.) | PASS |
| 4 | Fire-down hold ≥ 1.0 | 0.80 / 0.50 | 4.7 / 2.2 (est.) | PASS |
| 4 | Collapse lying breathing ≥ 0.4 | 0.33 | 0.64 (est.) | PASS |
| 4 | Roar snout / wing-tip tremor 1.5 to 3 px | 0.33 / 0.49, 0.30 | 1.72 / 1.52, 2.89 | PASS |
| 5 | air_land foot jump at contact | 21 px T | 6 px K (8.6 px T-equivalent) | PASS in K px, marginal in T scale |
| 5 | foot ≤ 1.2x body speed at contact (air_land / land2) | 1.07 / 0.62 | 1.14 / 0.55 | PASS |
| 5 | land2 foot jump ≤ 8 px T (takeoff / touchdown) | 14 / 20 | 7 / 7 | PASS |
| 6 | air_land descent speed −40 % over 12 frames | +398 % (speeds up) | −50 % | PASS |
| 6 | span +30 % in that window | +3 % | +37 % | PASS |
| 6 | compression ≥ 0.08 BH within 4 frames | 0.15 | 0.094 | PASS |
| 6 | end stance IoU ≥ 0.97 | 0.951 / 0.945 | 0.993 / 0.995 | PASS |
| 7 | land2 a_down / a_up 0.8 to 1.25 | 2.00 | 0.98 | PASS |
| 7 | bite full-reach freeze ≤ 10 | 35 | 4 | PASS |
| 7 | bite reach ≥ 12 cm | 9.3 | 12.7 | PASS |
| 8 | roar both wings ≥ 1.22x idle half-span, within 5 % | 1.31 / 1.16 (12 %) | 1.29 / 1.29 (0.4 %) | PASS |
| 8 | roar opens over ≥ 8, closes over ≥ 10 (10-90 %) | 3 / 13 | 10 / 10 | PASS |
| 8 | rise frame 0 IoU vs collapse end ≥ 0.95 | 0.13 | 1.00 vs collapse_v4 (0.87 / 0.80 vs collapse_v3, which now breathes differently) | PASS |

**What did not reach the target, and why.**
- Wing-body coupling (item 2, all four airborne clips). The body now rides the wings (bob 0.14 to 0.75 BH on the beat
  period) but |r| at lag 0 to 4 is 0.29 to 0.45. Two causes measured on the raster: (a) in the front view the beating
  wing covers and uncovers the body, so the body-only centroid (the critic's `m & ~w`) jumps with the wing, not with the
  body (rigid-bob grid in `bob_table.py`: up to |r| 0.80 with the whole-mesh centroid, 0.50 with the visible-body
  centroid); (b) the strongest coupling sits at negative lags (body acceleration after the wing, as in real flight),
  outside the critic's 0-to-4 window in its own lag convention (`air.py`: `vw[6+l:...]` vs `ab`). Needs the critic to
  confirm the intended lag sign before more tuning.
- Hover "span change in the last 8 frames ≤ 3 %" and takeoff "centroid change in the last 24 frames ≤ 0.1 BH" were
  written for the beat-less v3 clips; a real 26-frame beat changes span 44 % inside 8 frames and moves the centroid
  0.14 BH inside one beat. Phase-matched span (1.1 %) passes; the takeoff centroid fails raw.
- Fire-down span drift 7.3 % comes from the sourced nose-down pitch (kept from round 1), not from the wings.

**Per-move changes (authored layers on sourced motion).**
- air_hover_v4: fit destuttered ([1,2,2,2,1] kernel, cyclic), resampled 121 → 131 frames (5 beats), wings = hover pose x
  fit high-pass detail, beat + bob + tail follow; frame 130 = frame 0.
- takeoff3_v4: idle_v2 breathing on the ground, 7 cm crouch (8 to 34), wind-up beat, three 24-frame beats from frame 48,
  feet planted by IK until the body clears the stance (release at 46 + 5-frame ramp), min-jerk rise 43 → 100 to the
  hover height (no overshoot); ends on hover frame 0 phase.
- air_land_v4: beats to the last upstroke top at 78, braking flare to contact (92), descent peak 3.1 cm/frame braked
  to 30 %, 4.5 cm leg compression, head dip and tail slap, 6-frame IK contact ease, idle_v2 settle; ends on the stance.
- air_fire_down_v4: beats continue through the fire hold (7 beats of 27.4 frames), sourced pitch and jaw kept.
- roar_v4: flare rebuilt per wing (scale searched to 1.25x lateral, capped at 1.15x of the round-1 open pose), opens over
  26 and closes over 30 frames, breath heave 0.8 cm, head tremor 3.4 deg, wing tremor 3.9 deg, tail lash 7 deg, feet planted.
- collapse_v4: breathing while lying from frame 108 (40-frame breaths: spine, chest, folded wings, tail, 0.35 cm body).
- bite_v4: hold compressed by time warp (121 → 93 frames), 4 cm lean and 8 deg neck into the strike, 4 deg worry shake.
- land2_v4: centroid moved onto one parabola (same acceleration up and down) in two raster passes (`land2_corr.py`),
  apex lowered to 0.38 BH (the clip's prompt asked for a knee-high hop; 0.52 BH lands at 16 px/frame); foot vertical
  speed capped at 1.4 cm/frame near the floor (front-foot IK misses up to 9 cm in the air, feet are not on the floor then).
- rise_v4: 44-frame authored get-up from collapse_v4's last frame (head and chest first, feet step under the body one by
  one with 3.5 cm lifts, wings half-open), then rise_v3 from its frame 14. 151 frames.

**Not verified.** No EEVEE render yet (GPU busy); the critic's own numbers on renders may differ within the calibration
spread above. One roar wing shows a few more open membrane holes than round 1 in raster close-ups (the mesh is
tattered in both); check on the render. Review renders are queued in `Local/dragon-review-20261029/queue_v4.txt`;
run `tools/dragon_refine/v4/run_queue_v4.sh` (gpu_slot capture, one clip at a time, then adds the "Round 2 fix" cards to
the review page with `build_review_page_v4.py`). Move data rebuilt from the v4 Actions (`Data/dragon/`, tests 3 OK).
