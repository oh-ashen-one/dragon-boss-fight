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
