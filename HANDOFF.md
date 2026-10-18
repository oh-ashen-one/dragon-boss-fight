# Veyr implementation handoff

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden
Active branch: `feat/unreal-migration`.

## Objective and current truth

Finish the original single-arena Unreal dragon encounter with a roughly 3–5 minute fight, four independent leg staggers and a collapsed-head punish window, responsive knight controls, readable attacks, reliable camera, death/victory/restart and final Customuse knight/dragon art. The goal is not complete. Native gameplay has passed on a primitive-art checkpoint; the newest source and packaged app still need acceptance. No second phase is warranted before the core quality bar is met.

The historical Unity branch `checkpoint/unity-native-009` and captures are preserved. Unity build009's 188.22-second victory is historical evidence, not Unreal acceptance.

## Owner authorization

- Customuse: two P2 mesh attempts each for knight and dragon, at the quoted 160 credits each; four attempts, 640 credits total. All four returned definite receipts and completed, charging exactly 640 credits. No retry, rigging or animation purchase is authorized.
- Engine: the owner approved bounded validation after the first two crashes, with an immediate stop on the next crash. That resumed attempt has now aborted during packaged-app loading, so further engine/app launches are held again. A fresh explicit approval is required; do not reinterpret automatic goal continuation as approval.
- Preserve Pocket Planet Argon, Ghostty, foreign locks and unrelated processes. Ghostty control remains denied. Root alone controls this task's engine and integration. All renders use the shared slot protocol and the hard two-renderer limit.
- Push sanitized task-branch checkpoints to the existing repository; no merge to main, duplicate repository, secret/private-log publication or raw asset publication without rights verification.

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

The bounded background PNG writer and filesystem-cook configuration compiled successfully with unchanged source: `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871`. Their recorded regression is still unverified. The image critic found improved destination/feet visibility but the head surface still disappears in some proxy-occlusion views. Audio compilation does not establish acoustic quality.

## Packaging and launch hold

1. Generic native duplication of the engine Entry world reported success but retained cross-world references, crashing on map change. Do not repeat it. Fresh null-RHI `tools/unreal/create_map.py` successfully created `/Game/Maps/VeyrArena`; idempotent verification exited 0.
2. Initial cook crashed in Zen storage. Project `bUseZenStore=False`, explicit cooker `-SkipZenStore` and corrected cache-path quoting fixed that path. The resumed cook and archive completed successfully.
3. The first resumed packaged-app launch aborted with exit134 in dyld, before Unreal initialization: `libtbb.12.dylib` was missing. Static inspection found the archive omitted its entire `Contents/UE` payload even though the staged app contains it. Further launches are held under the owner's stop-on-next-crash condition.

`Local/ENGINE_LAUNCH_HOLD.json` is enforced by replay/packaging launchers. Keep it until fresh owner approval. Original failed archives/logs remain preserved. A signed ZIP and fresh extracted runtime now pass recursive dependency, cooked-map, ZIP-manifest and strict signature checks without executing the app. The audit covers 15 Mach-O images with zero unresolved imports. ZIP SHA256: `ad1427ca33e67e731eb5d8ac5994906c7da7e5f68e605cd70782c094f22a89ee`. Documents FileProvider reattaches Finder metadata to loose apps, so the durable artifact is a ZIP and the verified execution copy is task-owned temporary storage. Do not call static audit a runtime pass.

Standalone C++ and direct Xcode finalization succeeded. `tools/unreal/build.py` avoids the nested UBA bad-file-descriptor failure, finalizes directly with valid stdin, and now prepares/verifies a local ad-hoc app signature. Only benign FinderInfo/ResourceFork metadata is removed from the task-built app. No signing account, provisioning update, engine installation or global security setting changes are authorized. Private build logs may contain automatically dumped environment data; never publish them.

## Customuse models

All four generated GLBs are preserved privately under `Local/CustomuseAssets`: knight A/B and dragon v2-B/v3-B. Copies and checksums are in this chat's user-facing output directory. They are mesh candidates, not accepted final animated characters. All contain 4K PBR textures and no skins/animation clips. Actual triangles: knight A 28,263; knight B 26,885; dragon v2-B 57,269; dragon v3-B 59,736. The dragon requests used the provider's 50K polygon setting; record actual triangle counts when budgeting runtime.

The website exposes humanoid rigging/animation and Tripo Quadruped configuration. A generic graph connection to Humanoid Animation does not prove winged-dragon compatibility. Actual-model rig quotes are verified: Knight B with Cartwheel/Humanoid, 8 credits; Dragon V3-B with Tripo/Quadruped, 33 credits. A revised 41-credit approval question explicitly naming V3-B supersedes the earlier unanswered V2-B proposal. No rig job has run. Raw-asset redistribution has not been cleared, so keep models out of public Git. See `docs/customuse-capabilities.md` and `docs/asset-cost-decision.md`; private receipts/identifiers never belong in those documents.

## Next work

- Await applicable approval for the two single rig attempts, Knight B plus Dragon V3-B at 41 credits total; no animation or retries. Do not act on an ambiguous reply to the older V2-B question.
- Await fresh launch approval for the concrete signed ZIP/extraction; the static repair and signature checks are complete. Stop further launches on another crash.
- After approval, run packaged recorded core, controls and all-move avoidance; verify physical mouse/keyboard input, healing boundaries, rear guard/guard break, camera/head surface, audio, full-fight pacing and restart. Stop on another crash.
- Integrate and validate final Customuse models/rigs/animations; retain temporary-art disclosure until actually replaced and visually accepted.
- Keep one rolling handoff, failed evidence and exact build/source receipts. Sanitize and push task-branch changes. Do not claim polished completion from compilation, a viewer or the old passing checkpoint.
