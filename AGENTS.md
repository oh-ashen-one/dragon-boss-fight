# Veyr project rules

Read `tools/asset-review/HANDOFF.md` for the current Knight review and approvals.

## Character animation — Blender authoring required (2026-10-21)

Owner instruction after the Veyr Knight walk review: always use Blender to author and refine character animation. This applies across projects, sessions and agent clients unless the owner explicitly chooses another workflow for a task.

- Author poses, rig constraints, keyframes, curves and timing in Blender. Keep an editable `.blend` containing the rig and actions. Scripts may automate Blender and verify exports; generating joint transforms outside Blender and only importing/exporting the result is not a substitute for Blender authoring and visual refinement.
- Inspect full-body motion in Blender at intended playback speed and from front, side and three-quarter views. Check weight transfer, planted feet, natural knees/elbows/shoulders, torso and pelvis motion, breathing, and hand/weapon contacts. Inspect transitions and the loop boundary; numerical checks alone do not establish visual quality.
- Preserve approved meshes, clips and timing. Start revisions from the relevant approved pose/action and save each candidate separately. Gripped handles stay inside the palms without crossing knuckles or visibly passing through the hands.
- Run heavy authoring/rendering on a verified Studio in the task's own Blender instance under the current shared GPU rules. Export for the requested viewer/engine, inspect the actual exported playback, and distinguish a saved scene, checked candidate and owner-approved result.
- Browser viewers remain review tools. Do not silently fall back to script-only animation if Blender is unavailable; report the missing capability and continue authorized preparation.

The owner authorized full native integration, builds, gameplay testing and critique agents on 2026-10-25. Work on the dedicated integration branch; preserve review sources and approved asset hashes. Earlier asset-review-only restrictions no longer apply to this integration pass.

## Owner-directed crash investigation — 2026-10-25

After receiving the packaged Veyr crash report, the owner explicitly authorized
continued diagnostic launches for this Veyr pass and asked that this authorization
be recorded here. Treat it as fresh authorization to test repaired candidates;
do not repeat the same permission question for routine validation in this pass.
Each launch must follow a concrete repair or diagnostic change, retain earlier
crash evidence and verify the actual app outcome rather than the LaunchServices
wrapper exit code. Keep renderer slots and process ownership intact. This is
task-specific authority, not authority to take over other sessions or run a
blind crash/relaunch script. Record the current candidate and remaining checks
in HANDOFF.md; source changes and successful builds are not runtime acceptance.


## Owner-directed October26 overhaul

For this pass, generate needed new 3D assets with Tripo or Meshy; do not spend
more time searching free 3D model catalogues. Reuse the already generated cathedral
kit. Animation remains source-first. Download through direct/API paths into the
owned project without Finder or Save dialogs; do not change browser security or
permission settings. Generated-provider credits are authorized by the owner.
