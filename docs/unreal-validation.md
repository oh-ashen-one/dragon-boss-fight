# Unreal validation status

Final source `a450a43b` has completed packaging and all 11 native packaged scenarios. See [final results](native-test-results.md) for exact source identity, case durations and coverage. The owner handoff includes the signed app, exact-source recordings and a sanitized validation receipt. Physical controls were observed with the documented standalone Shift automation limitation; audio listening and owner gameplay judgement are not claimed.

The records below are historical debugging checkpoints. Earlier launch/spending holds were superseded by the owner's explicit standing permission. Earlier statements about primitives, pending tests or pending approval do not describe the final build.

## Historical integration and recovery record

# Unreal validation status

The requested native migration is separate from the preserved Unity prototype. Unity results in `validation.md` do not establish Unreal behavior.

## C++ integration checkpoint

2026-10-18: installed Unreal Engine 5.8.3 built `VeyrEditor Mac Development` successfully using the native build tool, Xcode27.0, four local actions, and distributed execution disabled. All encounter classes compiled and linked; no errors or warnings were reported. The source and linked module hashes are preserved in ignored local evidence.

The installed5.8 toolchain still names its local executor UBA when `-NoUBA` is supplied. Engine source confirms that this flag disables detouring; the local executor is always used. The build reported remote execution disabled and each action marked `NoUba`.

The initial Unreal PIE ran and produced a saved native screenshot, but no complete Unreal acceptance run has passed yet. No Unreal frame-rate, visual quality, fight duration or control claim is verified yet. Main characters currently use explicitly labeled engine primitive proxies pending Customuse assets.

The second compile also passed after adding camera-only body collision, frame-synchronous active telegraphs, view-facing unlocked guard, and the input-only replay recorder. Embedded native source identity: `55b42197e9c8487eb78f78602e6bcaba77eabe87b5345c344c91c91ffc6c8bf4`. The receipt verifies source files remained unchanged during the build.

`tools/unreal/build.py --engine <installed-engine-root>` creates a unique local log/receipt and embeds the native source/config/content manifest hash. `-VeyrReplay=core|death|victory -VeyrEvidence=<absolute-output-directory> -VeyrReplayQuit` enables the optional native recorder after normal encounter initialization. It issues player inputs and records observed state; it does not set health, position, action clocks or boss state. Death/victory predicates include settled terminal pose, ordinary restart, fresh resources, movement and attack acceptance. The replay policy remains untested and must be tuned from real runs.

## Required native acceptance

- Confirm task-owned project/world through Epic's native MCP, create/save the owned level and verify spawn/collision.
- Exercise jump, light/heavy attacks, roll invulnerability and recovery, directional guard/guard break, stamina, four heals and empty-heal rejection.
- Strike each leg independently; observe buckle, collapse, seven-second head window, bonus damage, rise and restored control.
- Avoid fire sweep, claw, rear stomp, tail, bite and fixed flight landing using the actual telegraphed footprints.
- Complete an organic3–5minute victory, settled death, player death and responsive restart.
- Review camera under/near the dragon, with lock-on, free orbit, walls and flight transitions.
- Capture native source/build-matched frames/video and report measured settings and contention honestly.

The owner cleared the desktop-dialog gate. Native project identity was verified and the initial PIE ran. Customuse model spending remains a separate pending decision.

## Goal continuation

The fresh `/Game/Maps/VeyrArena` map was created using the PythonScript commandlet under null RHI. An idempotent follow-up exited 0 after the GameFeatureData asset-manager rule was configured. Do not duplicate the engine Entry world through generic asset duplication: it returned success but retained cross-world references and caused one owned editor crash during map transition. Failure evidence is preserved.

The corrected camera, lighting and expanded input-only scenarios compile successfully with embedded source identity `0431ad5fa32fc53e01c25779b4721bdee61476dcb2493df9a4943100b46cab17`. `tools/unreal/run_native.py` runs one scenario through an explicitly supplied shared GPU wrapper, records logs and native screenshots locally, and caps gameplay at 60 FPS with 100 percent screen resolution. Default output is 1280×720; measurements include capture overhead and shared contention. A renderer run is not an exclusive performance benchmark.

A later compile including head guidance, mouse-safe click-to-begin, stronger replay assertions, procedural audio and bounded real-time video capture succeeded with source identity `dfcf89ae79be8a72455f7be5a1fbb843f614704ae1efa3a29ff34d0f4676cf20`. Its recorded core regression is pending. The audio cues compile but have not passed an acoustic review; silent replay runs do not validate output sound.

Standalone C++ linked, but nested UBA/.NET Xcode finalization failed to launch `/bin/sh` with a bad file descriptor. Direct task-local Xcode finalization with valid stdin and local unsigned packaging succeeded. No engine installation, account or global security settings were changed. Cook/archive and packaged-game validation remain separate gates.

The subsequent compile-only source `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871` passed with unchanged source. It replaces synchronous video PNG writes with one bounded background task and explicitly bypasses Zen for cooking. Both changes require an approved runtime check. Engine launches are held after the two recorded crashes; the task-local launchers enforce that hold.

## Resumed packaging verification

The owner approved bounded validation with a stop on the next crash. Corrected filesystem cooking and archive creation succeeded. The first packaged-app launch then aborted in dyld before Unreal initialized because the raw archive omitted its entire `Contents/UE` payload, including runtime libraries. The launch hold was reinstated; no automatic retry occurred.

A copy-only repair restores the matching staged payload and a verified ONNX install-name alias. The signed ZIP passes CRC and full extracted-file manifest comparison; its extracted app passes strict ad-hoc signature verification and a recursive audit of 15 Mach-O images with zero unresolved imports, including weak imports. The staged manifest includes `VeyrArena.umap`. Game UUID and code/string-section identity are unchanged, and embedded source matches `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871`. ZIP SHA256: `ad1427ca33e67e731eb5d8ac5994906c7da7e5f68e605cd70782c094f22a89ee`.

Documents FileProvider recreates Finder metadata on loose apps and interferes with strict signing. The durable artifact is a ZIP created from a verified private signing copy; a fresh extraction outside FileProvider also passed verification. No quarantine attribute, signing account or global security setting was changed. Native launch, physical controls and the newer gameplay regression remain unverified pending fresh approval.
