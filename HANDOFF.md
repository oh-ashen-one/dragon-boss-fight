# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden

Active branch: `feat/first-playable`. Rigged native milestone: `978bb24`, build 003, capture `combat-20261018T040013325Z`. This is an early playable, not visual completion.

## Verified and preserved

- Unity 6000.3.20f1 native macOS build 002 compiled with zero errors after fixing runtime shader stripping. Build 003 ran successfully but its report contained 56 duplicate TypeDB registration errors; a clean-cache rebuild is pending to resolve and verify those.
- Native input replay 003 PASSED leg damage, buckle, collapse, exposed-head bonus damage, rise, dodge and contact avoidance, with all ten required screenshots. Actual native backbuffer recording saved a 31-second clip; captures are not concept renders.
- Replay 002's overall FAILED result remains preserved: the game mechanics passed, but simultaneous screenshot requests overwrote captures. The queued capture implementation corrected this in 003.
- Death test 003 reached player death, then FAILED restart: the bootstrap initializer did not run on scene reload. The actual lifecycle bug is corrected in source; native retest pending.
- Original arena and procedural audio are implemented. Temporary original Blender dragon has 28 bones and fourteen authored clips. Regenerated version 2 corrects root translation axes; native collapse/death visual review pending.
- Public footage of Kalameet, Sinh and Midir was inspected; timestamped observations and their limits are in `docs/references.md`.

## Current work and gates

1. Rebuild and validate death/restart, full victory/restart, a 180–300 second fight and each attack's avoidance.
2. Validate camera framing and player visibility near/under the giant.
3. Refine original environmental lighting/materials and authored impact/contact poses against native captures.
4. Replace temporary main characters through the requested Tripo workflow, then Blender cleanup, rig/weights and animation refinement. The inspected profile displays 55 credits per H3.1 model and an export upgrade gate; subscribed-profile clarification and applicable generation budget remain pending. No Tripo credits spent.

A separately saved generated image is art direction only (`ArtSource/Concept`). It is not gameplay or a replacement for the Tripo main-model requirement.

No performance claim: shared GPU use and capture overhead make current measurements nonexclusive. No unrelated processes were stopped; Ghostty was not used. Machine logs and failure evidence remain local and excluded from Git.

## Ownership

Root exclusively integrates and runs Unity through the shared GPU slot. Workers own arena/camera, reference research, Blender source/importer and input replay. Preserve failure reports; compilation and a short replay are not polished completion.
