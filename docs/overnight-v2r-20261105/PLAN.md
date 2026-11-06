# Overnight video2rig dragon pass — approved 2026-11-05 evening

Owner approvals (2026-11-05): run unattended overnight; up to ~420 Higgsfield credits for new Seedance clips (6 clips, at most one regenerate each after a failed `video2rig check`); every move that passes all checks becomes the default; flight skipped (current flight kept).

Recipe per move (same as `docs/video-bite-20261105.md`): Seedance video → video2rig fit (reader-64) → Blender cut + per-phase retime (`tools/dragon_refine/cut_v2r_move.py`; video steps/lunges/wings/tail kept; feet pinned only while planted; no forced stance blend) → mirrored twin where a leg variant is needed → canonical export → native import + pose check → showcase before/after on one Shipping build.

| Game clip(s) | Source | Batch |
|---|---|---|
| Claw0/Claw1 Windup/Active/Recovery | claw_swipe `0ea9e6f9` (+ Blender mirror) | A (free) |
| Buckle0/Buckle1 | stagger `660936bd` (+ mirror) | A |
| Collapse | collapse `3ad2ed35` | A |
| Exposed | lying tail of collapse, looped | A |
| Rise | rise-from-lying `461da1de` | A |
| Tail Windup/Active/Recovery | new tail sweep | B |
| Stomp2/Stomp3 | new rear stomp (+ mirror) | B |
| Fire Windup/Active/Recovery | new ground fire-breath pose | B |
| Walk | new travelling walk loop | B |
| TurnLeft (+ reversed right) | new 90-degree turn | B |
| Buckle2/Buckle3 | new hind-leg stagger (+ mirror) | B |

Runtime: one switch. Video2rig clips are named `<Clip>V2r` (bite keeps `BiteV2r<Phase>`); they play by default when present, `-VeyrLegacyDragon` restores every keyed clip for comparisons.

Gates per move: `video2rig check` PASS/WARN; fit median miss <= 5 px; three-view Blender renders inspected; native pose check 0 failures; showcase passes with and without `-VeyrLegacyDragon`. Final: victory <= 150 s and core regression on the default build; one blind Opus review of the per-move sheets.

Stop rules: two failed attempts → the move keeps its keyed clip (recorded). GPU busy → wait in the normal gpu_slot queue, never override; one engine at a time. Never exceed the credit cap. No main merge; push after each move. Morning deliverable: per-move side-by-side review page, status table, credits spent, HANDOFF update.
