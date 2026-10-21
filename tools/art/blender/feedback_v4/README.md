# Knight feedback revision 4 — tooling (preparation, 2026-10-21)

Status: **tooling only.** No v4 pose, keyframe or export exists yet; the six v3
candidates are still awaiting owner review. Approved clips stay byte-for-byte unchanged.

This folder is a parameterised copy of `feedback_v3`. It starts from the saved v3
editable scenes and writes only to v4 locations. Nothing is hard-coded to a session.

## Parameters

Precedence: `run.py` CLI flag > environment variable > default (`common.py`).
Relative paths resolve against the repository root.

| Parameter | CLI | Env | Default |
|---|---|---|---|
| owner tag | `--owner` | `VEYR_V4_OWNER`, then `VEYR_BLENDER_OWNER` | `fable-veyr-knight-v4-20261021` |
| input scenes (read only) | `--scene-in` | `VEYR_V4_SCENE_IN` | `Local/Blender/feedback-v3-20261021` |
| output scenes/reports/renders | `--out` | `VEYR_V4_OUT` | `Local/Blender/feedback-v4-20261021` |
| delivered GLB copies | `--export-dir` | `VEYR_V4_EXPORT_DIR` | `Local/Blender/feedback-v4-20261021/export` |
| revision (names `<Review>_Blender_v<r>`) | `--revision` | `VEYR_V4_REVISION` | `4` |
| overwrite own v4 files | `--allow-overwrite` | `VEYR_V4_ALLOW_OVERWRITE` | off |
| MCP port | `--port` | `VEYR_BLENDER_PORT` | required |

Writes into the v3/v2/approved/remainder scene folders or `tools/asset-review/.asset-cache`
are refused. Delivery into the reviewer cache needs `VEYR_V4_ALLOW_REVIEWER_EXPORT=1`
and the owner's go-ahead; approved clip names are always refused.

## Scripts

- `run.py SCRIPT CALL` — client. Builds an owner-guarded command for `veyr_rpc.py`,
  sets `__file__`, passes parameters, keeps the command under `<out>/rpc/`.
- `revise.py` (in Blender): `open_job(job)` opens the v3 scene and re-tags the owner
  (no save); edit control curves; `rebake(job)` bakes, saves the v4 scene, exports
  `<out>/<job>_Blender_v1.glb` and copies `<Review>_Blender_v4.glb` to the export dir.
  The v3 authoring functions are kept verbatim; each rewrites that job's controls.
- `render.py` (in Blender): `capture(job, full=False, close=False, scene_dir=None,
  resolution=None, label=None)` — same views/times as v3, PNGs under `<out>/renders/`.
- `contact_audit.py` (in Blender): `audit(scene_dir=None, name=...)` — v3 thresholds.
- `audit_exports.py` (system python): `--glb-dir --report-dir --revision --approved-dir
  --out --jobs`; reads the delivered GLB names. Thresholds identical to v3.

Jobs: `heal heavy backpedal guard_two strafe_left strafe_right`.

## Example (one revision, guard)

```
cd <checkout>; R="python3 tools/art/blender/feedback_v4/run.py --port 9884"
$R revise.py "open_job('guard_two')"
# ... author control-curve changes through further run.py/veyr_rpc calls ...
$R revise.py "rebake('guard_two')"
$R render.py "capture('guard_two', full=True)"
python3 tools/art/blender/feedback_v4/audit_exports.py --jobs guard_two
```

Each `run.py` call re-executes the script, so `open_job` and later calls see the scene
already loaded in Blender. Visual inspection and owner approval remain separate from
these checks.
