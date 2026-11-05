# Veyr — The Cinder Warden

An original native Unreal Engine 5.8 dragon encounter in a gothic fortress and ruined war-court. An armored knight attacks independently damageable legs, breaks the dragon's balance, and reaches its exposed head before it rises again.

The current presentation includes the owner-approved fortress and mural tour as a skippable pre-fight intro, sourced heavy attacks, broader idle wings, healing, combat feedback, one owner-supplied soundtrack, dedicated dragon effects and one player hit grunt. Experimental movement replacements remain disabled when they have not passed gameplay and visual review. See [the current handoff](HANDOFF.md) and [remaining backlog](BACKLOG.md) for honest status.

## Play and controls

On the owner's Mac, use **Play Veyr** on the Desktop. It launches the current verified Shipping app through the shared GPU guard, with the tested presentation settings and no Terminal window. The local installation pointer is `Local/LatestShipping.json`; packaged builds and licensed/private assets are not published in this repository.

Click or press Enter to take control. Move with WASD and aim the camera with the mouse. Shift sprints, LMB attacks, F performs a heavy attack, RMB guards, E changes grip, Q rolls, Space blinks, R heals, Tab toggles lock-on, and Escape opens the menu. The game displays its controls and restart action on screen. The intro can be skipped and does not repeat on a retry in the same session.

Guard direction, stamina, invulnerability timing and healing charges matter. Leg staggers create exposed-head openings. Fire, bites, claws, rear stomps, tail sweeps and flight have visible anticipation and danger areas.

## Native project and validation

The project is `Unreal/Veyr/Veyr.uproject`; consolidated source is on `main`. Build the editor module with:

```sh
python3 tools/unreal/build.py --engine <installed-engine-root>
```

`tools/unreal/package.py --engine <installed-engine-root> --configuration Shipping` builds, cooks and audits a local Mac package. The delivery copy comes from the matching fresh stage, with an independently verified signed ZIP and extraction. Build/cook success is separate from runtime acceptance.

Run a bounded native scenario through the host's shared GPU coordinator:

```sh
python3 tools/unreal/run_native.py --app <verified-app-path> --gpu-slot <shared-slot-wrapper> --mode core
```

Modes include core, controls, leg0–leg3, avoidance, healing, guard, death and victory. Optional `--video-fps 8` records unchanged native viewport frames. `tools/unreal/encode_video.py <run>/native-video/frames.jsonl` produces silent variable-frame-rate evidence using the observed wall timestamps. Capture and shared workloads affect timing; these recordings are not exclusive rendering benchmarks.

See [Unreal validation](docs/unreal-validation.md), [native results](docs/native-test-results.md), [combat design](docs/combat-design.md) and [gameplay references](docs/references.md).

## Source and asset separation

Project code is MIT. Original procedural arena geometry, stone/fire material graphs and synthesized audio follow [ASSET-LICENSE.md](ASSET-LICENSE.md). Epic Engine Content remains under Epic's terms.

The final knight and dragon originate in Customuse. Their raw and derived assets remain private pending raw redistribution clearance; they are not relicensed by this repository. The owner's local project contains them under `Content/Characters/Customuse`, and the private handoff includes the active authoring assets. Restore those assets before rebuilding the final presentation from a public checkout. Without them, the code deliberately displays a labeled temporary-character fallback.

No models, textures, animation, audio or footage were ripped from the reference games. Public gameplay references informed encounter principles only.

## Preserved Unity history

The earlier Unity prototype and its evidence remain preserved at `checkpoint/unity-native-009`. Unity results and controls in the historical [validation record](docs/validation.md) are not Unreal acceptance. Current implementation and delivery use Unreal.
