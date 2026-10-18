# Veyr — The Cinder Warden

An original single-arena dragon boss fight, currently migrating to Unreal Engine 5.8. The knight breaks the dragon's balance by attacking four independent legs, then punishes its exposed head during a short collapse.

**Status: Unreal C++ build succeeds; no Unreal gameplay verification yet.** The previous Unity prototype is preserved at `checkpoint/unity-native-009`. Its results below are historical Unity evidence. Character geometry is explicitly temporary. The requested final models are being prepared in Customuse; website rigging, animation and redistribution capabilities remain under inspection. No paid generation has been submitted, and no reference-game assets are included.

The Unreal project is `Unreal/Veyr/Veyr.uproject`, with native C++ encounter code. Current branch: `feat/unreal-migration`. Planned controls are WASD movement, Space jump, Shift roll, J/LMB light attack, K heavy attack, F/RMB guard, Q healing, Tab lock-on and R terminal restart. These are implementation targets until tested natively.

## Preserved Unity prototype

WASD move; mouse while right button held rotates camera; left click or J attacks; Space dodges; Q heals; Tab toggles lock-on; R restarts after death or victory; Escape releases the pointer.

## Source and assets

Original project C++, C# and Python code: MIT (LICENSE). Original procedural meshes and authored temporary rig/animation: CC0-1.0 (ASSET-LICENSE.md). Unreal Engine resources remain subject to Epic's license and are not relicensed by this project. Customuse assets are not included pending generation approval and redistribution verification. Gameplay reference links are research citations only.

Unity 6000.3.20f1. Open this directory as a Unity project, or invoke that editor with `-batchmode -nographics -projectPath <this-directory> -executeMethod VeyrBuild.Build -quit`. It creates the native macOS build at `Builds/Veyr.app`. Run its executable `Builds/Veyr.app/Contents/MacOS/Veyr - The Cinder Warden` (quote the path in a shell).

For input-driven native validation, append `--replay combat|death|victory|avoidance|legregions|healing --capture-dir <absolute-new-output-directory>`. Choose one mode. Optional `--record-dir <absolute-new-video-directory>` records native backbuffer frames; `python3 tools/encode-recording.py <new-video-directory>` encodes them using ffmpeg. Use absolute, separate output directories to preserve runs: the native application can change its working directory. The executable writes its embedded source manifest beside captures.

See [validation](docs/validation.md) for actual results and limits, [combat design](docs/combat-design.md) for targets, and [references](docs/references.md) for the inspected public source footage. Follow the host's shared GPU-slot protocol before launching editors, games or renderers.
