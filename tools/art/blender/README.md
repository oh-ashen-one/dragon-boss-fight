# Knight Blender authoring

Owner rule, 2026-10-21: use Blender for character animation authoring and
refinement. Python automates Blender and validates exported playback. Keep
approved clips unchanged and retain editable Blender sources.

Current owned Studio session: `codex-veyr-walk-20261021`, loopback port 9881.
Verify its scene owner tag with `veyr_rpc.py` before every operation. Never use
another session's Blender. Start through the shared GPU slot protocol.

## Files and workflow

1. `start_veyr_session.py` starts the isolated MCP server in a fresh Blender.
2. `prepare_knight_walk.py` imports the unapproved v2 reference, rig and sword.
3. `refine_knight_walk.py` creates editable pelvis, torso, breath and hilt curves
   and a separate anatomical four-limb IK rig. It calibrates pole angles and
   bakes the deform rig without changing its rest bones or skin. On subsequent
   runs it retains and samples the edited control curves; it does not recreate
   them. The source action remains `REFERENCE_Walk_v2_UNAPPROVED`.
4. Unhide `WALK_AUTHORING_CONTROLS` objects in Blender to edit their actions.
   After changing the four main controls, run the embedded refinement text to
   rebake. Keyframe changes to limb target trajectories are recalculated by the
   bake; make structural changes in the recipe. Save a new candidate version.
5. `render_knight_walk_review.py` captures front, side and three-quarter poses.
6. `export_knight_walk.py` exports only the deform rig/body/socket, merges active
   actions into one 3.5-second clip and embeds the authoring recipe in the blend.
   The browser attaches the separately preserved strong-grip sword.
7. `audit_export.py` uses the independent glTF evaluator at 120 Hz to check palm
   contact, planted feet and rotation steps after Blender's basis conversion.

Authoring paths in these task scripts currently point at the verified Studio.
Resolve and change those paths for a different machine; do not assume portability.

## Candidate v3

- Blender 5.2.0 LTS; 60 fps, 211 samples, 3.5 seconds.
- Editable scene: Studio `/Users/midir/veyr-blender-walk-20261021/Knight_Walk_Blender_v3.blend`.
- Export: `WalkTwoHand_Blender_v3.glb`, SHA256
  `d0713bac27cd87f6d5ed34eebb2c10a4bc6d1011a125bbe30f65bda405cd3c3d`.
- Endpoint matrix errors versus preserved idle endpoints: below 2.3e-6.
- Independent export audit: palm drift below 0.000789 rig units, planted-foot
  frame drift below 0.000021, largest local joint step 3.366 degrees at 60 Hz.
- This remains a start/walk/stop study, not a seamless locomotion cycle.
- It has not been approved or integrated into Unreal.

The project GitHub repository is public. Character derivatives remain private
under the project's existing asset restriction: keep the `.blend` and GLB on
the Studio and laptop asset cache; do not commit them to this public repository.
The authoring recipes, checks, reports and retrieval instructions are committed.
