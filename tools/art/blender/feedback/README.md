# Knight owner feedback — revision 2, 2026-10-21

Owner approved **Death v1** and **Stagger v1**. Exact hashes and the owner's
corrections/removals are in `decisions.json`. The earlier six approved idles and
attacks remain unchanged. **Jump and one-hand guard are removed from the active
review inventory.** Run and ready walk are first in the reviewer for the next
owner decision; neither is newly approved.

## Six revised Blender motions

| Clip | Change | Duration |
|---|---|---:|
| Heal v2 | Upright body; simple cup pickup, cup-to-mouth, lower and return. Stable outward elbow pole and neutral wrist relative to forearm. | 2.4 s |
| One-hand heavy v2 | Preserved sword/body motion; independent left-arm lift, guard/counterbalance, and recovery instead of a hand pinned at the hip. | 1.4 s |
| Backpedal v2 | Built from approved idle, three alternating backward steps with planted support feet and no torso pitch/roll. | 2.4 s |
| Two-hand guard entry v2 | Starts at exact approved two-hand idle, visibly raises/angles the sword into a braced guard, then holds. | 1.1 s |
| Left sidestep v2 | Upright target-facing stance; left foot leads and right foot follows without crossing. | 1.3 s |
| Right sidestep v2 | Mirrored lead/follow order with shoulders kept facing forward. | 1.3 s |

The movement revisions are explicit root-motion steps: backpedal ends .36 source
units backward; sidesteps end .22 units left/right. They are one-shots that finish
in the translated idle, not cycles that should wrap/teleport. Game integration
must coordinate/strip root translation against actor movement. The guard entry
is also a one-shot; its endpoint is the held defensive pose.

## Native Blender authoring

Used the verified Studio Mac15,14 and a task-owned Blender 5.2.0 LTS instance
through its MCP addon: owner `codex-veyr-feedback-20261021`, port 9883, shared GPU
slot. `feedback_actions.py` authors native FK poses, world-space foot targets,
hand targets, poles, hilt curves and native IK. No rejected crouched/backpedal/
strafe reference poses are reused: those motions start from approved idle.

`rebuild/approved_actions.py` now supports a neutral hand/forearm orientation for
selected limbs. Heal and the heavy attack use it to prevent wrist distortion.
The editable controls, source action, baked rig and recipes remain in each blend.
The cup is a small hollow native Blender prop, parented to the left palm. Its
appearance uses an imperceptible nonzero scale instead of a singular zero matrix.

Editable files live under `Local/Blender/feedback-20261021`. Internal filenames
retain `<job>_Blender_v1.blend` for the shared authoring utility; the delivered
exports are the **v2 filenames in the active catalog** and this directory is the
separate feedback-v2 workspace. Earlier files are not overwritten.

To revise an existing scene through a verified owned MCP connection, execute the
current `feedback_actions.py` with its actual absolute `__file__`, call
`configure(job)`, edit the controls, then `c.bake()` and `export_current(job)`.
`build(job)` is for a new scene and refuses an existing output scene. Preserve
accepted variants before editing. Configure is required for the neutral wrist
setting on heal/heavy. Recipes are embedded in the blend as well.

## Evidence and limitations

- All six independent 120 Hz export audits pass, including approved idle start,
  translated idle recovery, limb lengths, held palm contact and rotation steps.
- Backpedal/sidesteps have effectively zero torso rotation, minimum left/right
  ankle separation over .257 units and knee separation over .211 units.
- Heal's elbow remains at least .103 units above the pelvis. Wrist deviation
  relative to forearm is below .001 degree; the cup reaches the helmet mouth area.
- The heavy attack's free hand moves over .25 units in chest-local space.
- Blender front/side/three-quarter sequences and closeups were inspected; six
  normal-speed review films were rendered, decoded and duration-checked.
- Chrome loaded the revised textured heal over the private Tailnet URL; the
  cup-to-mouth pose and elbow clearance were checked close up. Run and ready walk
  were opened separately at 1x for owner review.
- These six revisions are still **owner-review candidates**. Metrics do not imply
  artistic approval, successful Unreal animation integration, or gameplay feel.

## Gameplay removals

Jump no longer has a Space binding, a TryGroundedJump path, or an airborne Jump
presentation selection. `CanJumpInternal_Implementation()` returns false and jump
launch velocity is zero, so inherited requests cannot produce a jump. Legacy
replay jump input is ignored; the controls/core replay acceptance now checks that
jump stays disabled. Historical evidence counters remain for schema compatibility.

Guard entry always readies two-handed grip, including queued guard transitions;
one-handed Guard is no longer selected. Grip cannot be toggled away while holding
guard. Native Mac VeyrEditor compilation succeeded after these changes; see
`reports/native-build.json`. This is compile validation, not a gameplay run.
The installed packaged game was not replaced. New animation import, transition
configuration and packaged gameplay verification remain a later integration step.

## Laptop access and recovery

The private link remains `http://100.95.131.102:8775/`, through existing Tailscale
Serve TCP forwarding to loopback. No laptop terminal or SSH tunnel is needed.
The reviewer is a detached task-owned process. Agents can use
`tools/asset-review/start_background.py` to start it, or `--restart` after catalog
changes. It preserves unrelated processes. No login service or OS permission
changes remain; a launch-agent attempt was removed after it failed to listen.

The active catalog is `tools/asset-review/remainder-catalog.json`. It excludes
jump/one-hand guard, replaces the six rejected versions with v2, marks death and
stagger approved, and places Run/Ready walk first.

Private backup release: `oh-ashen-one/veyr-animation-sources`,
`knight-feedback-v2-20261021`. This is a delta on the prior review bundle. The
original variants remain archived for provenance, not active review.
