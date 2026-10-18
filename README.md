# Veyr — The Cinder Warden

An original single-arena dragon boss fight, currently migrating to Unreal Engine 5.8. The knight breaks the dragon's balance by attacking four independent legs, then punishes its exposed head during a short collapse.

**Status: native Unreal core combat, all four independent leg tests, death/restart and a 3:02 victory/restart have passed on a source-stamped prototype.** The previous Unity prototype is preserved at `checkpoint/unity-native-009`. Its results below are historical Unity evidence. See [native test results](docs/native-test-results.md) for the verified Unreal checkpoint; newer presentation/input/audio changes require their own regression. Character geometry is explicitly temporary. The requested final models are being prepared in Customuse; website rigging, animation and redistribution capabilities remain under inspection. No paid generation has been submitted, and no reference-game assets are included.

The Unreal project is `Unreal/Veyr/Veyr.uproject`, with native C++ encounter code. Current branch: `feat/unreal-migration`. Native controls are WASD movement, Space jump, Shift roll, J/LMB light attack, K heavy attack, F/RMB guard, Q healing, Tab lock-on and R terminal restart. The current source adds click-to-begin and Escape-to-release mouse control; these physical bindings still need a packaged-app acceptance pass. Input-only replay verification is separate from physical key verification.

Build the native module with `python3 tools/unreal/build.py --engine <installed-engine-root>`. This records a source hash and local receipt without launching the editor. See [Unreal validation](docs/unreal-validation.md) for current evidence and remaining acceptance checks. `tools/unreal/run_native.py --engine <installed-engine-root> --gpu-slot <shared-slot-wrapper> --mode core` runs one bounded native scenario. Optional `--video-fps 10` records unchanged viewport frames with observed wall timestamps; `tools/unreal/encode_video.py <run>/native-video/frames.jsonl` encodes silent VFR evidence. Run the real game through the host slot protocol. `tools/unreal/package.py --engine <installed-engine-root>` prepares a local Mac archive; packaging success alone is not runtime acceptance.

## Preserved Unity prototype

WASD move; mouse while right button held rotates camera; left click or J attacks; Space dodges; Q heals; Tab toggles lock-on; R restarts after death or victory; Escape releases the pointer.

## Source and assets

Original project C++, C# and Python code: MIT (LICENSE). Original procedural meshes and authored temporary rig/animation: CC0-1.0 (ASSET-LICENSE.md). Unreal Engine resources remain subject to Epic's license and are not relicensed by this project. Customuse assets are not included pending generation approval and redistribution verification. Gameplay reference links are research citations only.

Unity 6000.3.20f1. Open this directory as a Unity project, or invoke that editor with `-batchmode -nographics -projectPath <this-directory> -executeMethod VeyrBuild.Build -quit`. It creates the native macOS build at `Builds/Veyr.app`. Run its executable `Builds/Veyr.app/Contents/MacOS/Veyr - The Cinder Warden` (quote the path in a shell).

For input-driven native validation, append `--replay combat|death|victory|avoidance|legregions|healing --capture-dir <absolute-new-output-directory>`. Choose one mode. Optional `--record-dir <absolute-new-video-directory>` records native backbuffer frames; `python3 tools/encode-recording.py <new-video-directory>` encodes them using ffmpeg. Use absolute, separate output directories to preserve runs: the native application can change its working directory. The executable writes its embedded source manifest beside captures.

See [validation](docs/validation.md) for actual results and limits, [combat design](docs/combat-design.md) for targets, and [references](docs/references.md) for the inspected public source footage. Follow the host's shared GPU-slot protocol before launching editors, games or renderers.
