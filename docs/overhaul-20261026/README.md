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

## Owner steering during implementation

Owner explicitly requested generated 3D assets through Tripo or Meshy for this pass, with no further free-model search; animation stays sourced. Downloads must be direct/noninteractive without Finder or Save dialogs. The Fab chandelier is therefore retained only as an unused experiment. Two Meshy API jobs now produce the chandelier and a large vaulted-arch module. Their result files download directly to task-local storage.

## Preparation checkpoint before native import

Final generated meshes are directly downloaded Meshy7.1 outputs, not the unused Fab experiment. Chandelier51,854 triangles /4.8m width and portal46,888 triangles /18m height retain2K PBR maps; native import will produce three LODs. Six lit review renders and editable scenes passed source-integrity checks. The portal is decorative architecture with a low rear wall, so its base is grounded outside combat space rather than treated as a traversable vault. Receipts contain geometry caveats.

Source-adapted blink candidates are fitted on the existing knight with the retained one-hand sword grip. Final flight joins are r2 in `Local/Overhaul20261026/flight-r2`; all51 exported skin joints match hover endpoints to1.26e-6 or better, original ground poses and motion outside the0.4s joins are preserved, and morph error is zero. The first correction missed three non-Limb-named helper joints and is rejected. Native banks are prepared as additive v028 and not yet activated.

Independent source critiques led to corrections for airborne death/descent, airborne stagger gating, accelerated-turn sampling, pre-start flight cooldown, diagonal wall orientation, intact prop solidity, spatial audio, music lifecycle and sky-dragon update cost. Current source has a fixed560cm arm/FOV72 (collision may shorten it), camera manual-look override, broader anatomy hits, impact sparks, stamina/HP tuning, overhead fire, bounded falling chandeliers/debris, and two10Hz distant dragon poses. Source is still awaiting the final compile/native/playable acceptance pass.

Editor58320, started through the owned slot at18:15UTC, is rebuilding the removed project DDC. Its measured stack is actively in Unreal's quadric mesh reduction; each large pre-existing Tripo mesh takes several minutes. It is not a crash or stalled permission prompt. Do not restart it and lose progress. Native MCP18773 will become available after startup. New generated meshes are50k-class and avoid this original multi-million-face preprocessing cost.
