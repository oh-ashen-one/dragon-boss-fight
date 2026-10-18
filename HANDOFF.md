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

`VeyrVisualDefinition`, the native Interchange importer and deterministic `VeyrSkeletalPresentation` now support both actors through optional stable runtime definitions. Those definitions have not been activated in a game yet; gameplay evidence still shows primitives. Character assets are deliberately ignored by Git; source receipts and private import evidence preserve lineage. No accepted final-art build exists.

## Current integration checkpoint

Editor source `b6cb077f370a3398e6c22b3cacd3276ca7d35ca4f6d3bc01fd3574dea25e6c22` compiled successfully with unchanged source. This adds explicit synchronous skeletal sampling and optional knight/dragon runtime presentation. Missing clips remain explicit diagnostics, and successful reference-pose sampling is not animation acceptance. The earlier protected animation-status API compile error was corrected through the public compressed-data readiness check.

Fresh native knight v006 imports all four normalized clips on one skeleton. Dragon v001 imports the normalized 40-bone rig with coherent bounds and names. The knight sword is a closed disconnected surface of 1,048 triangles/1,245 vertices; native highlighted-mask review confirmed blade, guard, grip and pommel without fingers. New rigid RightHand-weight derivatives preserve all nonweapon skinning exactly and remain rigid through sampled poses. They are prepared for native import/QA, not yet accepted. Original assets and failed imports remain intact.

CPU motion analysis identifies useful attack trims and actual blade endpoints. Old light contact precedes the visible stroke. Root-locking also removes vertical bob; controlled horizontal-only in-place derivatives are being prepared. No timing/health balancing change has been accepted yet.

The first new healing run timed out after 180 seconds in the shared GPU queue without launching. This is resource contention, not a crash or gameplay failure. The subsequent bounded-queue run acquired a slot and passed all four-charge/cap/empty-flask assertions on source b6cb077f; process exit 0. The guard boundary run also passed (front chip, rear full damage with ample stamina, and real exhausted guard break) in 21.389 game seconds; exit 0. Root owns no running editor at this checkpoint. Respect both foreign reservations; do not bypass the two-renderer limit.

## Next work

- Complete normalized knight clip imports and inspect native deformation. Repair sword weighting only after a topology-derived mask is visually reviewed.
- Inspect and correct dragon wing/leg/head deformation with anatomical evidence; preserve originals and provenance.
- Integrate both Customuse characters, accurate attack/target transforms and complete motion states before removing the temporary-art disclosure.
- Run healing/guard boundary replays, then rebuild/package the latest source and validate physical controls, camera, audio, pacing and restart with actual native evidence.
- Keep the rolling handoff and exact source/build receipts current; sanitize and push checkpoints. Do not infer polished completion from compilation or asset previews.


## Later integration work awaiting native acceptance

All eleven knight motion candidates now exist; total paid debit is 1,044 credits, with 1,552 remaining at the last verified balance. Native v009 imports all eleven clips; corrected Idle/Walk still intersect the legs and are not accepted. Topology analysis found three isolated tabard/hem surfaces with erroneous arm influences; corrective weights and a reachable front-right sword hold are being authored. Original exports and failed candidates remain intact.

Dragon v4 is a 51-joint candidate with independent wings and an articulated jaw. Its oral seam duplicates 55 boundary vertices while preserving all original triangles/face attributes; the underside hinge remains continuous. CPU opening/wing probes pass, and root reviewed the actual diagnostic images. Native animation acceptance remains pending.

The edeb344a editor build compiled but source review caught a missing movement update; it is explicitly NOT an accepted gameplay checkpoint. Root restored exactly one movement update before pose/contact, added missing endpoint trajectory tests for collinear blade sweeps, cleared cached blade poses on definition replacement and rejected validation starts in already-played worlds. Corrected editor source `60be518f2633e758f6a3c9cb95ae5d50ef477db4d05254e57428e9d6216ae3aa` compiled successfully with unchanged source; native regression remains pending. Source/native-pose validation cannot be inferred from the earlier compile.

The editor closed through normal QUIT_EDITOR during the initial pose-check attempt; PIE had already ended, so that attempt reported zero PIE worlds and did not test the component. No crash occurred. All imported assets were saved. Fire material generation compiled three graphs, but revalidation exposed old-path redirectors from preserved partial attempts; the new recipe uses a fresh v2 namespace and verifies the saved object path/metadata before reporting success. No native fire-quality acceptance yet.

## Animation integration checkpoint (latest)

The owner continues to authorize Veyr launches and credit use without repeated permission questions. Total charged is 1,143 credits, last verified balance 1,453. Twenty paid operations completed (four meshes, two rigs and fourteen motion candidates); no paid operation is pending. Directional gait curation is local and preserves original exports.

Editor source `84956b75cd0fa6e3c37fbd61d789b28a85dfa38ef8afe509aafc495effd1bf83` compiled successfully. It includes bone-based dragon contacts and committed warning unions, lower-body knight motion layers, a left-hand healing flask, imported roll/jump timing, protected-head camera visibility controls, and revised arena materials/lighting. Native acceptance of this source remains pending.

Earlier source `60be518f2633e758f6a3c9cb95ae5d50ef477db4d05254e57428e9d6216ae3aa` passed the 66-sample native knight pose/transition checks with zero endpoint, repeat or interrupted-blend error; fresh PIE controls passed in 22.7386 game seconds. These controls still used primitive art. Native knight v010 shows repaired cloth and a safe sword hold; dragon v004 has the repaired 51-joint rig. Neither is a complete accepted final-art fight.

Thirty-eight original dragon motion clips and five revised knight action clips have CPU deformation/IK evidence and are ready for native import. No claim of native animation acceptance follows from CPU checks. The final directional gait work remains in progress.

The prior owned editor reached the shared coordinator's 2,400-second maximum hold and was terminated by the coordinator. This was not an observed gameplay crash. Its report and exit-124 receipt are preserved privately. The owned crash reporter failed to exit after SIGTERM and more than 60 seconds, so root terminated that exact reporter as a last resort. Future native authoring batches must close normally well before the lease limit, with CPU authoring performed while the editor is closed.

## Native import correction and checks

The normalized dragon v006 fixes an Unreal Interchange disagreement between bind and animation transforms. Folding the canceling scene-parent translation preserves all 3,635 sampled reference/key/midpoint poses exactly, with zero skinned-vertex difference. Native v006 then passed 190 samples across all 38 clips: deterministic targets, independent claw/stomp feet, downward two-sided fire sweep and bite contact height. Camera material parameter binding is verified after assigning the copied masked material through the skeletal-material array correctly. Native rendering confirms the previous roughly 525 cm sinking is corrected; original v005 is preserved.

Knight v011 passed 84 native pose samples plus all ten guard/heal lower-layer combinations, including left/right/backward gaits, with zero blend boundary/repeat error. Native static pose views of idle, roll, healing gesture, light contact and settled death are preserved privately. Full runtime feel remains open.

The first imported-art core run failed with player death and zero sword contacts. It also suffered the editor's background 3 Hz throttle. Native endpoint measurements confirm the original provider light strike reaches mostly sideways and heavy strikes behind the knight at the configured contact time. Correct frontal strike derivatives are being authored; no gameplay radius inflation is approved or needed. This failed run must not be counted as a pass.

For subsequent owned-editor validation, root transiently disabled the actual CDO property `bThrottleCPUWhenNotForeground`, without saving configuration. Restore the previous True value before normal editor shutdown. The native source now avoids blending from the bind pose during first visual activation and preserves the imported 4.4-second death duration. These source corrections still require a new build.

An original deterministic 680-triangle basalt cliff mesh imported with exact centered 100 cm bounds; its source generator and native importer are reproducible. New Arena source uses it in place of distant cube silhouettes, retaining the previous floor, cathedral and collision. Native environment rendering after rebuild remains pending.

The subsequent actual imported-art controls run passed in 18.543 game seconds with mean simulation step 0.01291 seconds after the transient throttle correction. It exercised movement, jump, light/heavy action input, roll, stamina recovery, lock toggles, actual guarded contact, healing and full-health healing rejection. It does not prove successful sword hits. The normalizer, material binding and native pose receipts remain separate evidence.

## Final-art candidate activation

Knight v012 contains corrected original frontal light/heavy strikes, the longer left/right combat steps and grounded Run derivative. It passes all 84 native pose samples and ten guard/heal movement-layer cases. Native blade endpoints now match the intended frontal contact path; measured active-window target probes use the existing combat radii. Native strike and strafe pose images were reviewed. The Run correction preserves original rotations/horizontal stride and removes the previous foot penetration; its small original rotational loop seam uses the existing transition.

Private stable runtime definitions now reference Knight v012 and Dragon v006. A fresh PIE session automatically loaded both and reported no knight presentation diagnostic, no missing dragon clip and ready camera material parameters. This activates the assets for final gameplay validation; it does not mark the full fight accepted.

Source additionally uses a level initial camera pitch (rendered review keeps the entire standing dragon in frame), hides the internal imported-preview label, requires the replay to approach within 45 cm of its intended stand-off, and records the phase-zero dragon contact pose on Active entry. Complete authored clips use native sequence end times; definition validation now matches the runtime strict interval check.

Both latest editor sessions ended normally with exit 0; the temporary background-throttle override was restored before shutdown. Root is packaging the standalone candidate next. Earlier failed core evidence remains preserved. Full packaged contacts, pacing, attack coverage, camera, restart and physical controls remain acceptance gates.
