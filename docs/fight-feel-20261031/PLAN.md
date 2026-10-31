# Fight feel — 2026-10-31

Status: STOPPED — first completed blind Opus review returned TIE. Candidate not accepted. Shipping package and both core replays passed, but did not prove a visible improvement.

## Ownership and baseline

- Game checkout: `veyr-knight-20261028`, branch `fable/knight-complete-20261028`, baseline `589fd6a`.
- Dragon checkout stays on `claude-code-enhancements`; no edits in this pass.
- Builder: current Codex session. Required independent critic: Opus, blind A/B.
- Native MCP read-only inspection confirmed UE 5.8.3, VeyrArena, KnightB/v030t and DragonV3B/v028 runtime definitions. Dragon runtime has no Roar clip.
- Day-one audit: five missing systems (camera shake, hit-stop, boss flinch, hit flash, weapon trail). Dust/audio code presence is not quality acceptance.

## Reference and implementation boundary

Studied the owner-provided BossFight Unreal reference locally, particularly WardenCombatFx and the shared boss/hero runtime notes. No reference files, source fragments, music or models copied into this repository. Implementation is original Veyr code integrated at accepted contact events.

Reuse: existing project FXv3 ember material, unchanged; installed Epic Engine BasicShapes Plane, unchanged. No asset acquisition, account actions, generation or spend.

## Candidate targets

- Light accepted sword contacts: 55 ms hit-stop; heavy: 95 ms. Player contact: 70 ms; block: 50 ms. Undilated timer, restores previous game rate, cancels on pause/setting change/world teardown. Does not stack onto review slow motion.
- Camera: 0.25–1.65 degree base amplitude by weight, quadratic distance falloff to zero at 50 m, bounded decaying socket offset. Does not change control rotation. Landing, stomp, tail contact, sword connect and player damage hooks.
- Flinch: small additive head/neck contact correction over the existing sourced pose; no attack cancellation or authored-clip replacement. No airborne/dead flinch.
- Hit flash: local warm contact light, 180 ms lifetime with fast decay, no screen flash.
- Trail: bounded 24-segment pool, 100 ms game-time lifetime, existing textured material. Must be reviewed at combat camera distance.
- Persistent settings: camera shake, hit flashes and impact pause. `-VeyrFightFeelOff` is a runtime-only baseline switch that does not overwrite saved preferences.

## Verification and acceptance

1. Shipping compile/package, same source and assets for baseline and candidate.
2. Matched real-game replay captures, no text overlays; encode original timestamps without interpolation. Text labels belong outside videos.
3. Inspect counters and time restoration; contact misses must not cause hit-stop. Verify frame cap under shared gate.
4. Blind Opus critique, neutral labels and concealed mapping. First-round tie stops this pass and is reported; no tie ships.
5. Owner subjective feel remains separate. Do not mark done on compile, audit or fidelity alone.

Still required: native render/capture; full comparison; critic; roar hook with integrated sourced roar; timing and settings checks. Whole backlog remains active in owner order.


## First rendered verification

Shipping package `Local/package-20261031T210020Z/receipt.json` passed cook, dependency and signature checks. Baseline and candidate used the same package and assets, 1280×720, requested capture cadence 15 fps, hidden HUD, normal game timestep. Both core replays passed light/heavy/collapse/head-punish/rise/dodge coverage in about 42.4 game seconds. These are core validation runs, **not victory duration measurements**.

`runtime-check.json` passes bounded amplitude/trail, contact-only hit-stop accounting, disabled baseline, observed candidate effects, and restored game time. Candidate: 8 shake events; 5 hit-stops/flashes; 4 flinches; 43 trail samples. No subjective quality or settings-interaction acceptance follows from these counters. Full captured-frame metadata is under the local evidence directories listed in `captures.json`.

Owner first-tie rule applied. See `critique-round1.md`. No further iterations or later backlog work commenced after that verdict.
