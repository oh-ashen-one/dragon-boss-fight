# Veyr — The Cinder Warden

An original single-arena dragon boss fight in Unity 6. The knight severs the dragon's balance by attacking four independent legs, then punishes its exposed head during a short collapse.

**Status: native early playable with passing automated combat checks; not visually complete.** Character geometry is explicitly temporary. The intended final asset pipeline is Tripo → Blender cleanup, rigging and authored animation → Unity. No reference-game assets are included.

## Controls

WASD move; mouse while right button held rotates camera; left click or J attacks; Space dodges; Q heals; Tab toggles lock-on; R restarts after death or victory; Escape releases the pointer.

## Source and assets

New C# and Python code: MIT (LICENSE). Original procedural meshes and authored temporary rig/animation: CC0-1.0 (ASSET-LICENSE.md). Tripo assets are not included pending generation approval and redistribution verification. Gameplay reference links are research citations only.

Unity 6000.3.20f1. Open this directory as a Unity project, or invoke that editor with `-batchmode -nographics -projectPath <this-directory> -executeMethod VeyrBuild.Build -quit`. It creates the native macOS build at `Builds/Veyr.app`. Run its executable `Builds/Veyr.app/Contents/MacOS/Veyr - The Cinder Warden` (quote the path in a shell).

For input-driven native validation, append `--replay combat|death|victory|avoidance|legregions|healing --capture-dir <new-output-directory>`. Choose one mode. Optional `--record-dir <new-video-directory>` records native backbuffer frames; `python3 tools/encode-recording.py <new-video-directory>` encodes them using ffmpeg. Use separate output directories to preserve runs.

See [validation](docs/validation.md) for actual results and limits, [combat design](docs/combat-design.md) for targets, and [references](docs/references.md) for the inspected public source footage. Follow the host's shared GPU-slot protocol before launching editors, games or renderers.
