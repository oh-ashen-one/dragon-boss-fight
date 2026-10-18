# Veyr implementation handoff

## Current state

Public repository: https://github.com/oh-ashen-one/veyr-cinder-warden

Active branch: `feat/first-playable`. First complete build source checkpoint: `577481f`.

Unity 6000.3.20f1 generated the project settings and built the native macOS app with zero errors. The first rendered run failed because runtime-only shaders were stripped; explicit shader resource assets fixed this in build 002.

Native input replay 002 observed leg damage, independent leg buckle, collapse, seven-second exposed head, increased head damage, rise, and a real contact avoided during dodge. Its overall result remains FAILED because multiple screenshot requests in one frame were not all saved. The capture queue is being repaired. Death, victory, restart and full fight duration remain to be validated.

All current character geometry is temporary. Original arena, combat and procedural audio are implemented. A native Blender rig and fourteen animation clips are saved; authored rig integration is in progress. No Tripo credit was spent. The inspected profile shows 55 credits per H3.1 model and an export upgrade gate; subscribed-profile clarification and concrete generation approval remain pending.

## Remaining work

1. Complete replay capture reliability and validate death/restart/victory.
2. Integrate temporary Blender clips with accurate contact timings and bone-linked targets.
3. Improve environmental materials and lighting against actual gameplay captures.
4. Obtain approved Tripo assets, verify distribution rights, clean/rig/weight/refine in Blender.
5. Watch the cited public gameplay sources directly; current research clearly labels playback unverified.
6. Measure a full 3–5 minute fight, camera behavior, native frame timing and source/build-matched screenshots/video.

No performance claim: shared GPU usage was nonzero; replay timing is not an exclusive performance benchmark. No unrelated processes were stopped, and Ghostty was not used.

## Ownership

Root integrates and exclusively runs Unity. Separate workers own arena/audio, dragon state machine, Blender importer/visual sampling, and input replay source. Shared GPU slot protocol applies to tool launches. Preserve existing artifacts and failure reports; do not treat compilation as polished completion.
