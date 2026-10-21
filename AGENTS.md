# Veyr project rules

Read `tools/asset-review/HANDOFF.md` for the current Knight review and approvals.

## Character animation — Blender authoring required (2026-10-21)

Owner instruction after the Veyr Knight walk review: always use Blender to author and refine character animation. This applies across projects, sessions and agent clients unless the owner explicitly chooses another workflow for a task.

- Author poses, rig constraints, keyframes, curves and timing in Blender. Keep an editable `.blend` containing the rig and actions. Scripts may automate Blender and verify exports; generating joint transforms outside Blender and only importing/exporting the result is not a substitute for Blender authoring and visual refinement.
- Inspect full-body motion in Blender at intended playback speed and from front, side and three-quarter views. Check weight transfer, planted feet, natural knees/elbows/shoulders, torso and pelvis motion, breathing, and hand/weapon contacts. Inspect transitions and the loop boundary; numerical checks alone do not establish visual quality.
- Preserve approved meshes, clips and timing. Start revisions from the relevant approved pose/action and save each candidate separately. Gripped handles stay inside the palms without crossing knuckles or visibly passing through the hands.
- Run heavy authoring/rendering on a verified Studio in the task's own Blender instance under the current shared GPU rules. Export for the requested viewer/engine, inspect the actual exported playback, and distinguish a saved scene, checked candidate and owner-approved result.
- Browser viewers remain review tools. Do not silently fall back to script-only animation if Blender is unavailable; report the missing capability and continue authorized preparation.

Use the existing review branch for this work thread. Do not rebuild Unreal or replace the installed game as part of asset review.
