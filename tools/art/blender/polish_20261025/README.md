# Veyr owner-requested animation corrections, 2026-10-25

This package authors new candidates inside an isolated Blender 5.2 MCP session.
Approved source scenes and exports under `/Users/midir/veyr-review-fable-20261021`
are read-only. Outputs are private and ignored by Git under
`Local/Blender/polish-20261025`; do not commit character binaries to the public repo.
The root integration owner handles backup, import, native validation and branch publication.

## Final candidate contract

Use `Local/Blender/polish-20261025/manifest.json` for exact GLB and packed Blend hashes.

| Runtime key | Candidate | Seconds |
|---|---|---:|
| FlightActive and FlightHoverAlternate | Dragon_FlyHover_Blender_polish_v1 | 2.0 |
| FlightWindup | Dragon_Takeoff_Blender_polish_v2 | 1.5 |
| FlightRecovery | Dragon_Land_Blender_polish_v3 | 1.5 |
| RunTwoHand | RunTwoHand_Blender_polish_v2 | 0.6266667 |
| GripToTwoHand | GripToTwoHand_Blender_polish_v2 | 0.5 |
| GripToOneHand | GripToOneHand_Blender_polish_v2 | 0.5 |
| Roll | Roll_Blender_polish_v2 | 0.78 |
| RollAttack | RollAttack_Blender_polish_v2 | 2.2 |

Every new Knight clip uses `BoatGreatsword_OneHand_v4.glb`, the existing intact
shaft mesh. The old two-hand Grip_v6 mesh exposes a missing shaft section when
released. RunTwoHand retains the approved Tripo gait and its nominal 460.4147cm/s.
Roll keeps the praised torso, legs and left-arm motion; its original right-palm
trajectory carries the sword forward through native right-arm IK. RollAttack's
0–0.78-second prefix is identical to the revised roll, including the socket;
its original slash resumes exactly from 0.98 seconds. Existing damage window
1.03–1.27 remains appropriate.

Dragon hind targets now sit below the hips, with downward-facing toes and
calibrated poles. Wing actions remain the source actions. Takeoff and landing
use short endpoint joins to the corrected hover. `PolishHoverBreath` preserves
the hover's exact corrective shape at these joins while retaining the original
transition's breath shape elsewhere. Preserve all hash-distinct morph targets;
do not enforce the old fixed count of eight. Final surface joins are below
0.001cm, rather than merely matching bones.

## Workflow and evidence

- `run.py SCRIPT.py CALL` dispatches through the isolated MCP execute_code channel,
  stores the command/log under the task output, and checks the owner tag.
- Start Blender using the existing `start_veyr_session.py`, port9891 and owner
  `codex-veyr-polish-20261025`, under the shared GPU slot wrapper. The installed
  addon requires GUI Blender; it cleanly rejects background mode. Verify PID,
  port and scene ownership before work. Never use a foreign MCP binding.
- `dragon.py` and `knight.py` author actual editable Blender actions/IK controls,
  bake, export and render. New versions must use new names.
- `full_review.py` and `encode_reviews.py` produce front/side/three-quarter
  full-speed PNG sequences and MP4s. Each timing.json records exact sampling and
  intended duration; there are no synthesized video frames.
- `contact_review.py` supplies detailed palm/hilt/forearm and floor views.
- `audit_candidates.py` checks exported body preservation, action-prefix identity,
  endpoint and palm/socket transforms, limb lengths and sword floor clearance.
  Generic core-bake diagnostics precede roll restoration; use the final audit
  instead of treating the old aggregate nativeIKError as a final limb measure.
- `finalize_scenes.py` packs all images into task-owned Blend candidates.
- `make_manifest.py` hashes delivery and verifies all32 approved originals unchanged.

Independent critique is recorded in `Local/Critique-Polish-20261025/critique-final.json`.
Final8 versions were judged ready for native validation after the run's buried
forearms, exposed cutaway grip and morph-shape endpoint differences were corrected.
This is not owner approval or native gameplay acceptance. Earlier candidate drafts
remain local evidence and must not be imported as final assets.
