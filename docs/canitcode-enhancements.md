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
