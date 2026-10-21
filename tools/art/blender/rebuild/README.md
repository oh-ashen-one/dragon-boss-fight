# Approved Knight motions rebuilt in Blender — 2026-10-21

Six new candidates preserve the approved meshes, grips, references and durations.
They are not owner-approved replacements and are not integrated into Unreal.

| Job | Approved reference | Duration | Editable pose beats |
|---|---|---:|---:|
| idle_one | IdleOneHand_Breathing_v3 | 4 s | 9 |
| idle_two | IdleTwoHand_ReadyBreath_v6 | 4 s | 9 |
| overhead | LightAttack_BlackKnightReference_v10 | 2.8 s | 18 |
| sweep | StrongAttackTwoHand_Sweep_v9 | 1.466667 s | 11 |
| thrust | StrongAttackTwoHand_Thrust_v7 | 2.306667 s | 11 |
| light_two | LightAttackTwoHand_Compact_v1 | 1.1 s | 9 |

## Authoring and references

Executed through the handed-off Veyr Blender MCP addon at loopback port 9881,
PID 28574, owner `codex-veyr-walk-20261021`, under shared GPU slot 0.
Blender 5.2.0 LTS. The generic Infected Blender connector was disconnected;
`veyr_rpc.py` sent owner-guarded commands to the task's actual MCP addon.
The Python command language automates Blender. No external NumPy/SciPy motion
generator was used to produce these actions. NumPy/SciPy are used only in the
independent export audit.

Approved actions supply sparse pose silhouettes. Blender interpolates editable
FK, hilt, hand/foot target, and pole curves, and its native four-limb IK solves
elbows and knees. The separate deform action is baked from that Blender result.
The one-hand hilt follows the native FK wrist through a bone constraint; the
two-hand clips use a shared weapon control and local palm targets. Original
rest bones, weights, fingers and weapon meshes are preserved. Source actions
remain stored as `REFERENCE_*`.

Original one-hand ArtStation frames and the owner's two-hand sweep/thrust GIF
frames remain in `.asset-cache/reference`. No new reference replaces them.
The compact light cut follows its approved action; it had no separate new GIF.

Preserved notes: continuous rest/behind-head/floor overhead arc; independent
free-arm guard; whole-body weight transfer; two palms on the handle; approved
3x strong-attack timings; compact 1.1-second light cut; breathing and closed
idle/recovery poses. The walk v3 remains separate and unchanged.

## Editing

Restore the private bundle in this checkout. Open
`Local/Blender/approved-rebuild-20261021/<job>_Blender_v1.blend`.
Unhide `AUTHORING_<job>` in the Outliner. Edit `Pose_Control_Rig` and the hilt,
hand/foot targets and pole actions in Blender's Dope Sheet/Graph Editor.
The visible character plays the baked action. Re-run `bake()` through the owned
MCP session after control edits; the bake reads the edited controls and does
not regenerate them. Save a new version before editing an accepted candidate.

Execute this repository's `approved_actions.py` inside Blender with `__file__`
set to its actual absolute path, then call `bake()`. `prepare(job)` is only for
new authoring scenes and refuses to overwrite an existing candidate. It creates
the controls, wrist attachment where applicable, and exact 150 Hz timebase.
`exact_sample_rate()` is idempotent. No new Blender instance is needed.

150 Hz export sampling makes all six durations integer frame ranges, avoiding
Blender's fps_base export discrepancy on the thrust and reducing between-frame
grip drift. This is animation sampling, not a runtime frame-rate claim.

## Verification and limits

`reports/export-audit.json` independently samples exported GLBs at 120 Hz:
all six pass duration, approved endpoint, limb-length, grip and rotation checks.
Worst two-hand palm drift is below 0.000808 rig units; endpoint joint-position
error is below 0.00000037. Original clip SHA256 values are retained in reports.
The left arm is intentionally free in one-hand clips.

Full-length Blender renders cover front, side and three-quarter views at the
approved durations; pose sequences were inspected for body motion, contact,
foot placement and recovery. The browser loaded the overhead export and its
original reference and advanced its timeline at 1x. In-app browser screenshot
capture timed out, so browser visual equivalence is not claimed from that UI.
Owner motion/feel review remains pending. Gray preview materials are for motion
inspection; GLBs preserve source materials. These checks do not prove gameplay
quality or Unreal integration.

Private bundle release: `oh-ashen-one/veyr-animation-sources`,
`knight-approved-blender-v1-20261021`. Restore with the existing
`tools/asset-review/restore_review_bundle.py`; it validates hashes and refuses
to overwrite differing files. The bundle adds candidates and preserves the
previous approved cache entries.
