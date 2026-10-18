# Native validation record

These are real-time native Unity runs using `PlayerCombat.SetReplayInput` through the same action logic as keyboard input. They do not teleport, write health, force boss states, accelerate time or call damage directly. They are input-driven automated tests; they do not replace human controller/camera review. Private logs and full evidence remain local.

| Build / scenario | Result | Evidence and limits |
|---|---|---|
| 002 / core | FAILED | Core mechanics observed, but simultaneous screenshot requests lost an image. Capture queue repaired. |
| 003 / core | PASSED,31.08s | All ten milestone screenshots; leg damage, buckle, collapse, head damage, rise and dodge contact. Source978bb24. Native31s clip saved. |
| 003 / death | FAILED | Death observed; scene reload did not reconstruct encounter. Actual lifecycle fixed. |
| 004 / core | PASSED,20.47s | Reachable corrected collapsed head and visible amber player silhouette. No player damage. Sourced2b458c. |
| 004 / death | PASSED,38.08s | Death, fresh health/boss reset and movement after restart. |
| 004 / victory | FAILED duration | Defeat at65.25s and fresh responsive restart observed; target180–300s not met. Boss health adjusted from2800 to8400 for retest, not yet accepted as balanced. |
| 004 / avoidance | PASSED,30.21s | All five moves observed windup→active→recovery, initially threatened player escaped by movement without damage. One incidental unthreatened stomp correctly did not count. |
| 005 / build | Succeeded,0errors | Six exact duplicate generated TypeDB/runtime initialization files quarantined; no source deletion. |
| 005 / core | PASSED,20.34s | Core rules preserved. Knight clip-duration guard triggered explicit visual fallback; authored knight not accepted yet. |

## Capture and performance conditions

Native1280×720 window, target60fps,4×MSAA, linear HDR,95m shadow distance. JPEG backbuffer recording preserves actual frame timestamps and is encoded as variable-frame-rate H.264. Screenshot and video content comes from the executable, never from the separate concept image. Per-build SHA256 source manifests are retained beside tests.

The shared-slot reports mark runs nonexclusive. Capture overhead also changes frame times. No exclusive performance benchmark or guaranteed frame-rate claim is made.

## Still required

- Tuned full180–300s victory, death and restart with accepted authored player.
- Four-region isolation test, keyboard controls, healing/limited-flask behavior and manual camera inspection.
- Final approved Tripo main meshes, Blender cleanup/weights/animation refinement and native visual review.
- Source/build/capture-matched final handoff. Current captures are explicitly temporary art.
