# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden
Active branch: `feat/unreal-migration`.

## Objective and current truth

Finish the original single-arena Unreal dragon encounter with a roughly 3–5 minute fight, four independent leg staggers and a collapsed-head punish window, responsive knight controls, readable attacks, reliable camera, death/victory/restart and final Customuse knight/dragon art. The goal is not complete. Native gameplay has passed on a primitive-art checkpoint; the newest source and packaged app still need acceptance. No second phase is warranted before the core quality bar is met.

The historical Unity branch `checkpoint/unity-native-009` and captures are preserved. Unity build009's 188.22-second victory is historical evidence, not Unreal acceptance.

## Current owner authorization

The owner explicitly reconfirmed that all Veyr task operations and credit spending are approved and that repeated approval questions must stop. Earlier queued questions are superseded.

The owner subsequently granted standing permission to finish Veyr, explicitly including task-related launches and credit spending, and instructed the agent not to keep asking routine approval questions. This supersedes the earlier mesh-only, 41-credit-question and stop-on-next-crash approval gates described in historical evidence below. Track actual charges, verify live prices, preserve unrelated workloads and security controls, and use bounded debugging rather than blind crash loops. Root has recorded this authorization locally and resumed the repaired packaged app; the asset worker owns paid Customuse rig/animation operations.

### Operational boundaries

- Standing Veyr credit and launch authorization supersedes all historical approval holds. Keep the charge ledger, bounded debugging and evidence; do not ask routine approval again.
- Preserve Pocket Planet Argon, Ghostty, foreign locks and unrelated processes. Ghostty control remains denied. Root alone controls this task's editor/integration. Enforce the shared hard two-renderer limit.
- Push sanitized task-branch checkpoints to this repository. No main merge, duplicate repository, private-log publication or raw-asset publication without redistribution verification.

## Verified native milestones

Checkpoint `85686c4`, embedded source `0431ad5fa32fc53e01c25779b4721bdee61476dcb2493df9a4943100b46cab17`:

- Core passed in 37.95 game seconds: jump, light/heavy contacts, leg buckle/collapse, five head bonus hits, completed rise and invulnerable dodge contact.
- Independent leg0–leg3 passed in 28.29, 30.88, 27.55 and 28.77 seconds. Each selected leg staggered and buckled while the other three remained unchanged.
- Player death/restart passed: terminal presentation, fresh resources, movement and attack.
- Full victory occurred at 182.38 seconds (3:02), followed by fresh resources, movement and attack after restart. Total scenario time was 188.09 seconds.

These were real rendered native runs at 1280×720, 100 percent screen resolution and a 60 FPS cap, with screenshots/evidence overhead and shared workloads. They are not exclusive performance measurements or physical-key acceptance. See `docs/native-test-results.md`.

## Newer source and evidence limits

Later source adds close-lock head guidance, a projected/edge head marker, compact HUD, click-to-begin and Escape/focus-loss mouse release, original procedural audio, stronger jump/avoidance assertions and continuous timestamped video recording. The knight is 244 cm tall. The encounter waits for first capture/replay input; releasing the mouse after engagement does not pause it.

Recorded source `dfcf89ae79be8a72455f7be5a1fbb843f614704ae1efa3a29ff34d0f4676cf20` FAILED core at 180.02 seconds: no invulnerable dodge contact was observed despite jump, eight collapses, 37 head bonus hits and boss defeat. Preserve this failure. It saved 979 native frames with zero failed writes, skipped 500 capture slots and spent 78.49 seconds writing PNGs over 184.49 wall seconds. Silent VFR encoding passed per-frame timestamp verification.

The bounded background PNG writer and filesystem-cook configuration compiled successfully with unchanged source: `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871`. The packaged recorded regression subsequently passed; see the current results below. The image critic found improved destination/feet visibility but the head surface still disappears in some proxy-occlusion views. Audio compilation does not establish acoustic quality.

## Packaging recovery

1. Generic native duplication of the engine Entry world reported success but retained cross-world references, crashing on map change. Do not repeat it. Fresh null-RHI `tools/unreal/create_map.py` successfully created `/Game/Maps/VeyrArena`; idempotent verification exited 0.
2. Initial cook crashed in Zen storage. Project `bUseZenStore=False`, explicit cooker `-SkipZenStore` and corrected cache-path quoting fixed that path. The resumed cook and archive completed successfully.
3. The first resumed packaged-app launch aborted with exit134 in dyld, before Unreal initialization: `libtbb.12.dylib` was missing. Static inspection found the archive omitted its entire `Contents/UE` payload even though the staged app contains it. The earlier stop-on-next-crash hold was subsequently superseded by the owner's direct standing authorization; the failure remains preserved.

The previous `Local/ENGINE_LAUNCH_HOLD.json` was archived with the owner's subsequent standing authorization. The launchers retain support for genuine future holds, but routine launches no longer need repeated questions. Original failed archives/logs remain preserved. A signed ZIP and fresh extracted runtime now pass recursive dependency, cooked-map, ZIP-manifest and strict signature checks without executing the app. The audit covers 15 Mach-O images with zero unresolved imports. ZIP SHA256: `ad1427ca33e67e731eb5d8ac5994906c7da7e5f68e605cd70782c094f22a89ee`. Documents FileProvider reattaches Finder metadata to loose apps, so the durable artifact is a ZIP and the verified execution copy is task-owned temporary storage. Do not call static audit a runtime pass.

Standalone C++ and direct Xcode finalization succeeded. `tools/unreal/build.py` avoids the nested UBA bad-file-descriptor failure, finalizes directly with valid stdin, and now prepares/verifies a local ad-hoc app signature. Only benign FinderInfo/ResourceFork metadata is removed from the task-built app. No signing account, provisioning update, engine installation or global security setting changes are authorized. Private build logs may contain automatically dumped environment data; never publish them.

## Customuse models

All four generated GLBs are preserved privately under `Local/CustomuseAssets`: knight A/B and dragon v2-B/v3-B. Copies and checksums are in this chat's user-facing output directory. They are mesh candidates, not accepted final animated characters. All contain 4K PBR textures and no skins/animation clips. Actual triangles: knight A 28,263; knight B 26,885; dragon v2-B 57,269; dragon v3-B 59,736. The dragon requests used the provider's 50K polygon setting; record actual triangle counts when budgeting runtime.

Both selected rigs and four knight motion clips completed. Total definite spend is 813 credits: meshes 640, rigs 41, four motions 132. The most recently verified remaining balance was 1,783. Knight B has 52 bones; Dragon V3-B has 40. No further paid operation is currently in progress. Native dragon jaw independence and useful wing deformation remain unverified; provider bone names do not reliably describe anatomy. Raw and derived assets remain private pending redistribution verification.

The original knight GLB imported with mismatched mesh/bind coordinates. A representation-normalized derivative bakes the static mesh transform into positions/normals and inverse binds while preserving joints, weights and motion. CPU verification across all 35,003 vertices at rest and 19 motion samples found maximum world-position error 5.51e-8 metres. Fresh native import v004 has coherent skeleton positions and an intact rendered walk preview. Earlier failed imports are preserved. This fixes import deformation, not the provider's separate bending-sword problem or final animation quality.

## Current packaged and editor evidence

Signed/extracted packaged source `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871` passed core (40.829s), controls (12.215s), all-six-move avoidance (52.576s), and victory/restart (191.837s total; boss defeat 186.124s). Recorded core saved 350 frames with 26 skipped slots and zero failed writes. Pixel copying took 0.0767s total; PNG work took 27.12s on the worker over 43.43s wall time. These are primitive-art tests with shared workloads, not a final performance claim.

Later editor source `555a679b9decdec627bde5f9caa0124bc0058bcd6d269deb41aae1a15afbc441` compiled successfully. It fixes uncaptured LMB dispatch, adds Enter-to-begin and checks actual native capture before engagement. Physical PIE input confirmed native capture, movement, light/heavy attacks, jump and lock-on. Physical roll, guarded contact, healing and packaged Escape/reacquisition still require final validation. New healing/guard boundary replay modes compile but have not run.

`VeyrVisualDefinition` and the native Interchange importer are integration foundations. Neither final character is wired into gameplay yet. Character assets are deliberately ignored by Git; source receipts and private import evidence preserve lineage. No accepted final-art build exists.

## Next work

- Complete normalized knight clip imports and inspect native deformation. Repair sword weighting only after a topology-derived mask is visually reviewed.
- Inspect and correct dragon wing/leg/head deformation with anatomical evidence; preserve originals and provenance.
- Integrate both Customuse characters, accurate attack/target transforms and complete motion states before removing the temporary-art disclosure.
- Run healing/guard boundary replays, then rebuild/package the latest source and validate physical controls, camera, audio, pacing and restart with actual native evidence.
- Keep the rolling handoff and exact source/build receipts current; sanitize and push checkpoints. Do not infer polished completion from compilation or asset previews.
