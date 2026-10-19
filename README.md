# Veyr — The Cinder Warden

An original native Unreal Engine 5.8 dragon encounter in a ruined cathedral arena. An eight-foot armored knight attacks four independently damageable legs, breaks the dragon's balance, and reaches its exposed crown before it rises again.

Both main characters now use Customuse models, with corrected rigging, skinning and authored motion. A packaged complete fight reached victory in 4:15 and verified a fresh responsive restart. Core combat, all four independent leg tests and avoidance of all six attack types have passed native validation. The latest camera, fire and boundary-test revision is completing its final packaged acceptance suite; [native test results](docs/native-test-results.md) records exact checkpoints rather than treating compilation as gameplay proof.

## Play and controls

The private owner handoff includes the signed local macOS ZIP. Click or press Enter to capture control; Escape releases the mouse. Movement is WASD, mouse controls the free camera, Space jumps, Shift rolls, J/LMB performs a light attack, K a heavy attack, F/RMB guards, Q uses one of four healing draughts, Tab toggles lock-on, and R restarts after defeat or victory.

Guard direction, stamina, invulnerability timing and healing charges matter. Each leg has its own stagger meter. A buckle leads to a brief exposed-head opening with bonus damage, followed by recovery. Fire sweeps, bites, claws, rear stomps, tail sweeps and flight/landing share visible anticipation and danger areas.

## Native project and validation

The project is `Unreal/Veyr/Veyr.uproject`; the task branch is `feat/unreal-migration`. Build the editor module with:

```sh
python3 tools/unreal/build.py --engine <installed-engine-root>
```

`tools/unreal/package.py --engine <installed-engine-root>` builds, cooks and audits a local Mac package. The delivery copy comes from the matching fresh stage, with an independently verified signed ZIP and extraction. Build/cook success is separate from runtime acceptance.

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
