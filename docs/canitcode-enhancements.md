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
| 2026-10-28 | collapse | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 6 s (145 frames at 24 fps), audio on, size-constraint prompt | 35 recorded (5 s rate; 6 s cost to verify) | pass (coordinator): wings at span, drops flat, chin on floor, panels agree; side panel crops the tail at the right edge once it lies flat | OK: body 1.17% (p90 1.35%), limbs 0.77% (p90 3.96%); frame 0 match 0.94 / 0.90. Fit: median miss 4.72 px, outline 0.75 / 0.83, max twist 21.4 deg (VeyrWingNegZRoot), warnings: body under the floor in 74 frames, hind knees at joint limit 60 frames |
| 2026-10-28 | death | Higgsfield, Seedance 2.5, omni_reference | 720p, 16:9, 7 s (169 frames at 24 fps), audio on, size-constraint prompt | 35 recorded (5 s rate; 7 s cost to verify) | pass (coordinator): falls, rolls partly onto its right flank, head stretched out, wings at span, panels agree | OK: body 0.93%, limbs 1.36% (close to the 1.5% line), frame 0 match 0.89 / 0.96. Fit: median miss 7.07 px, outline 0.71 / 0.82, max twist 51.7 deg (front upper leg; neck 48.9, shoulder 42.2), warning: body under the floor in 24 frames. Weakest fit of the set |

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
