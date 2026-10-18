# Native validation record

These are real-time native Unity runs using `PlayerCombat.SetReplayInput` through the same action logic as keyboard input. They do not teleport, write health, force boss states, accelerate time or call damage directly. They are input-driven automated tests; they do not replace human controller/camera review. Private logs and full evidence remain local.

| Build / scenario | Result | Evidence and limits |
|---|---|---|
| 002 / core | FAILED | Core mechanics observed, but simultaneous screenshot requests lost an image. Capture queue repaired. |
| 003 / core | PASSED,31.08s | All ten milestone screenshots; leg damage, buckle, collapse, head damage, rise and dodge contact. Source978bb24. Native31s clip saved. |
| 003 / death | FAILED | Death observed; scene reload did not reconstruct encounter. Actual lifecycle fixed. |
| 004 / core | PASSED,20.47s | Reachable corrected collapsed head and visible amber player silhouette. No player damage. Sourced2b458c. |
| 004 / death | PASSED,38.08s | Death, fresh health/boss reset and movement after restart. |
| 004 / victory | FAILED duration | Defeat at65.25s and fresh responsive restart observed; target180–300s not met. Boss health adjusted from2800 to8400; build006 subsequently met duration target. |
| 004 / avoidance | PASSED,30.21s | All five moves observed windup→active→recovery, initially threatened player escaped by movement without damage. One incidental unthreatened stomp correctly did not count. |
| 005 / build | Succeeded,0errors | Six exact duplicate generated TypeDB/runtime initialization files quarantined; no source deletion. |
| 005 / core | PASSED,20.34s | Core rules preserved. Knight clip-duration guard triggered explicit visual fallback; authored knight not accepted yet. |

| 005 / four legs | PASSED,13.85s | Four distinct contact regions each increased only its own stagger meter; no premature collapse. |
| 005 / physical keyboard | Observed | Native CUA input exercised movement, sword, dodge, wheel zoom, death and R restart. Q arrived after death, so did not verify healing. RMB orbit remains unverified. |
| 006 / victory | PASSED,194.08s fight | Eleven collapses, real boss defeat and fresh responsive restart;197.35s including capture/restart. Earlier knight visual fallback remained active. |
| 007 / build | Succeeded,0errors | Accepted27-bone,8-clip knight after correcting yaw-only model fitting. All embedded manifest files match source6b39ddc. |
| 007 / core | PASSED,20.31s | Accepted knight visibly slashes and rolls; leg damage, buckle, collapse,120HP exposed-head hit, rise and dodge contact. Native clip preserved and delivered. |
| 007 / healing | PASSED,31.06s | Four real damage/heal cycles consumed4→0 charges, each capped at100HP; eight injured empty-flask requests caused no healing. |
| 007 / death | PASSED,38.42s | Authored death allowed to settle before capture; terminal health remained stable; fresh responsive restart. |

| 008 / build | NOT accepted,182errors | Unity reported Succeeded but six numbered generated metadata files reappeared. Their type multiset accounts for all182 errors. Fresh source/cache verification is being prepared; native output/evidence retained. |

| 008 / victory | PASSED,191.77s fight | Accepted knight, eleven collapses, settled dragon death and fresh responsive restart. This gameplay pass does not waive the182-error build report. |
| 009 / build | Succeeded,0errors | Fresh source-only import with independent cache; all embedded manifest files match sourcec3c2e16. Original cache/build preserved. |
| 009 / core and lock | PASSED,20.38s | Real Tab key enabled lock-on during collapse/head approach, verified in native capture state. Head attack and dodge-contact checks passed. This is partial lock-on coverage, not RMB orbit acceptance. |

| 009 / victory | PASSED,188.22s fight | Sourcec3c2e16; accepted knight, leg-collapse/head loop, dodge contact, settled dragon death, fresh responsive restart. Full native recording retained. |

## Capture and performance conditions

Native1280×720 window, target60fps,4×MSAA, linear HDR,95m shadow distance. JPEG backbuffer recording preserves actual frame timestamps and is encoded as variable-frame-rate H.264. Screenshot and video content comes from the executable, never from the separate concept image. Per-build SHA256 source manifests are retained beside tests.

Build009 full fight recorded10,140 frame intervals after startup: median16.67ms,p95 33.17ms,p99 33.34ms. These include video/screenshot overhead and are measured frame intervals, not GPU timing. The shared-slot reports mark runs nonexclusive. Capture overhead also changes frame times. No exclusive performance benchmark or guaranteed frame-rate claim is made.

## Still required

- Complete manual orbit/lock-on camera review near and under the giant. Camera silhouette, wheel zoom and a real Tab toggle during the head window have been observed; no claim of full manual camera acceptance.
- Final approved Tripo main meshes, Blender cleanup/weights/animation refinement and native visual review.
- Source/build/capture-matched final handoff. Current captures are explicitly temporary art.
