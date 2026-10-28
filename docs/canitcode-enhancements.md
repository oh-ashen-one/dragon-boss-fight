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
