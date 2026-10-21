# Remaining Knight animations — Blender review, 2026-10-21

13 new candidates complete the remaining review inventory. The six previously
approved Blender idles/attacks and the original roll are preserved. No new
candidate has owner approval yet; no Unreal rebuild or integration is included.

| Motion | Duration | Playback |
|---|---:|---|
| One-hand walk | 1.2 s | Closed in-place cycle |
| Two-hand ready walk v4 | 3.5 s | Start/walk/stop; forward root travel |
| Run | 0.6 s | Closed in-place cycle |
| Backpedal | 1.6 s | Closed in-place cycle |
| Strafe left | 1.25 s | Closed in-place cycle |
| Strafe right | 1.3 s | Closed in-place cycle |
| One-hand guard | 4 s | Breathing hold loop |
| Two-hand guard | 4 s | Breathing hold loop |
| One-hand heavy attack | 1.4 s | Returns to approved idle |
| Jump | 1 s | Takeoff, airborne, landing, idle |
| Heal | 1.25 s | Left-hand flask gesture, idle |
| Stagger | 0.42 s | Recoil, recovery to idle |
| Death | 4.4 s | Weapon release, fall, held terminal pose |

## Actual authoring

Verified Studio: hostname Mac, model Mac15,14. The session was already executing
on the Studio, so SSH back into it was unnecessary. Blender 5.2.0 LTS ran through
the shared GPU slot wrapper, owner `codex-veyr-remainder-20261021`, loopback MCP
port 9882. Only this task's instance was used. No Unreal instance was launched.

`remainder_actions.py` uses `rebuild/approved_actions.py` as the native Blender
control-rig/bake layer. Source clips supply sparse body-pose references; their
full old animation is not merely re-exported. Approved hand shapes, wrist
attachments, sparse pose curves, anatomical four-limb IK, limb targets and poles
are edited/evaluated in Blender. One-handed limbs follow native FK bone controls;
two-handed grips use a shared hilt. Editable actions and both recipes are embedded
in each `.blend`. Python is the Blender MCP command language; external NumPy/SciPy
joint generation is not used. The separate audit uses NumPy/SciPy only to inspect
exported playback.

The clean approved Knight mesh replaces old reference meshes containing an
embedded sword. The original rest skeleton is compared before replacement.
Exported body topology matches the approved Blender body (77,475 triangle indices).
Blender import discards 12 degenerate triangles from the earlier pre-Blender
representation; the approved Blender export is the correct comparison baseline.

References: existing source motion files (hashes in reports), approved one-/two-
hand idles, approved sweep body mechanics for the one-hand heavy, and the prior
Blender ready walk v3. No new external reference or character design was invented.
The walk extracts a repeatable source interval 0.625–2.275 s, retimed to 1.2 s.
Native torso corrections reduce excessive forward pitch in run and strafes.
The one-hand heavy returns to the approved one-hand idle instead of the source
sweep's two-hand stance. Death uses a native Child Of attachment until release,
then an independently keyed hilt fall and settle. Heal includes a small native
Blender flask prop parented to the left palm.

## Review and checks

- `reports/export-audit.json`: all 13 exports pass independent 120 Hz checks for
  timing, closure/recovery where applicable, limb lengths, held weapon contacts,
  guard foot stability, rotation steps, and clean approved body topology.
- `reports/scene-inspection.json`: all 13 authoring timelines end at the playback
  endpoint, with four native IK constraints and editable actions in every scene.
  This catches the frozen tail caused by an earlier duplicate collection name;
  prepare now removes empty authoring collections before creating a replacement.
- Full-duration front, side and three-quarter films were rendered in Blender;
  pose sequences were inspected, and all 13 films were decoded and duration-checked.
- Chrome loaded the textured exports locally, showed all 13 new entries above
  earlier approved motions, and played the walk at 1x. Death held at 4.4 s with
  Loop off; scrubbing the jump to 0.5 s displayed the airborne pose.
- The six approved export hashes were rechecked and remain unchanged.

Numerical checks and agent visual inspection do not replace owner motion/feel
approval. The two-hand walk remains a start/walk/stop sequence, not a locomotion
loop. Jump includes preview vertical root motion; Unreal integration must
coordinate/strip that lift against capsule movement to avoid applying it twice.
The released death weapon and healing prop also require matching game attachment
behavior. No runtime gameplay, blending or frame-rate claim is made here.

## Resume / edit

Restore both private release archives into this checkout using
`tools/asset-review/restore_review_bundle.py`. Archives preserve differing local
files and verify each manifest entry. Sources are in
`Local/Blender/remainder-20261021/<job>_Blender_v1.blend`; viewer exports use names
from `tools/asset-review/remainder-catalog.json`.

Start a fresh owned Blender session under the current shared GPU protocol. Use
`VEYR_BLENDER_OWNER=codex-veyr-remainder-20261021` and `VEYR_BLENDER_PORT=9882` for
both the startup and `veyr_rpc.py` client, after checking that the port is free.
Verify the live owner tag before acting. Do not reuse recorded PIDs blindly.

Unhide `AUTHORING_<job>`, edit FK/target/pole/hilt curves, execute this checkout's
`remainder_actions.py` inside Blender with its actual `__file__`, and call
`core.bake()` to regenerate the deform action. Save a new version before changing
an accepted candidate. `build(job)` is for new scenes and refuses to overwrite
existing scene files. Timeline end must match the FK action's final key.

Viewer: `python3 tools/asset-review/server.py --local-only --port 8775`.
Private release: `oh-ashen-one/veyr-animation-sources`,
`knight-remainder-blender-v1-20261021`.
