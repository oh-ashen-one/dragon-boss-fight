# Veyr gameplay and cathedral overhaul — work in progress

Owner approved the complete October26 playtest backlog, scheduled start13:30 America/New_York. This pass began at the scheduled time on the verified Mac15,14 Studio. Branch `codex/veyr-cathedral-overhaul-20261026` starts from `3310d64`. Prior delivered v027 app and final editable sources are preserved.

## Acceptance worklist

- [ ] Close fixed camera, upward free look and manual lock-on override; wall/floor collision only shortens distance.
- [ ] Moving sword contact across reachable dragon anatomy, both grips and frame rates; impact feedback.
- [ ] Stamina costs/recovery and shorter boss encounter balance.
- [ ] Faster repositioning, more frequent/high flight and clearly warned overhead fire.
- [ ] Corrected dangling-paw hover in native bank, continuous takeoff/landing.
- [ ] Source-adapted directional blink, sword alignment and effects.
- [ ] Recorded/licensed combat sounds, dragon/environment audio, ambience/music and separate controls.
- [ ] Towering layered Gothic arena, coherent materials and open flight corridors.
- [ ] Bounded destructibles/chandeliers and distant dragon flybys.
- [ ] Native full encounter/pause/restart/collision checks, visual critique, isolated frame-time evidence.
- [ ] Signed playable delivery, private asset backup, pushed handoff and cleanup.

## Current evidence

Camera, stamina and anatomy-contact source changes passed the first VeyrEditor compile (`31547e00ceed65bf6719a5e209ea0c6f98c3cb8a3e695c8874e67bcef9323f48`). Flight/audio source changes passed a second compile (`b2963cfd3e3a6b15a443067b83ce65362de6ad6a8721660ba2abb519843f4311`). These are compile checks, not runtime acceptance. No replacement delivery exists yet.

Built-in image generation produced the persistent environment target at `Local/Overhaul20261026/cathedral-concept.png`: close third-person framing, open combat floor, layered Gothic terraces/ribs, giant moon and suspended warm chandeliers. It is concept art, not a game capture.

Independent read-only critics confirmed the old camera's1600cm flight pullback/pitch restrictions, missing body damage regions, high chained stamina cost and flight-scheduling starvation. Current available model inherited for critics; unavailable historical Opus/Fable labels are not claimed.

## Ownership and limits

Bully's foreign game was active at startup (PID93138 with GPU slot holder93122). Preserve it. Its shared GPU load prevents valid isolated performance claims until naturally available. This task uses at most one owned renderer and the global two-slot cap. Task Blender MCP is localhost9891, owner `codex-veyr-overhaul-20261026`, logs in `Local/Overhaul20261026/blender`.

Downloaded audio is $0 CC0 source material, staged privately. Selected PCM preparation is reproducible with `tools/art/prepare_overhaul_audio.py`. Provenance, listening and final in-engine mix checks remain required before delivery.

3DAssets.dev offered CC0 chandelier/vault candidates; CDN acquisition returned403 and Chrome blocked the CDN. No bypass attempted. Fab alternative Mikhail Kadilnikov's Chandelier lists CC BY4.0 in signed-in UI; acquisition is not yet verified locally.
