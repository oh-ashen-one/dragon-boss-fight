# Pacing round 2 — owner resumed 2026-11-01

Owner requested fixing long no-damage stretches, camera occlusion and the unclear death pose; retain <=150 active seconds, film before/after and get a fresh blind Opus review. HP stays 650. The first-round TIE remains preserved.

## Diagnosis and bounded changes

- First contact in the rejected filmed candidate occurred at 63.812 active seconds; another 35.387-second no-damage gap followed. The largest four-second HP loss was 79.077%. These are native event measurements, not inferred frame timing (`pacing-round2-before-metrics.json`).
- Locked actor facing aimed at body center while the strike/replay target was a nearby leg. Candidate uses the nearby limb inside 450 cm, exposed head during punish, and preserves distant/airborne behavior. It changes actual player combat targeting, not only replay input.
- Completed attacks now leave 1.25 s grounded Idle instead of 0.40 s. Telegraphs and committed attack timing remain unchanged. Limb contact damage is 45/85 (light/heavy), exposed-head damage 65/120 instead of 125/270, before the unchanged stance multiplier. This spreads progress and reduces the final burst without another HP reduction. Values are provisional until rendered timing and critique.
- Grounded close camera focus lowers from 170 cm to 100 cm to look down at the contact; arm 560 and FOV 72 remain unchanged. Existing camera-mask support must be inspected live; the optional definition material reference permits a clone without rewriting inherited meshes. Baseline retains its original mask behavior.
- Reuse the existing Blender death_v3 candidate: the viewed source sequence ends on its flank, wings down, held still. Original standing Death/DeathDown remain available. Export binds the existing action to the compatible canonical rig and checks every frame; grafting preserves canonical mesh/skin/material bytes and checks every animation key/midpoint. These checks establish equivalence, not visual quality. Native import/playback is pending.
- Candidate names DeathFall (full 7 s) and DeathFallDown (proposed fall segment from 2 s) will be inspected in engine; do not claim a clean join before capture. Terminal replay waits for the actual clip duration plus a hold instead of restarting after a fixed 4.5 s.
- `-VeyrPacingLegacy` selects original targeting, recovery gap, damage and death clips for same-build A/B. Native definition includes both old and new animations; no source scene overwritten.

## Validation

- VeyrEditor compile passed with the optional material property. Latest gameplay Shipping compile also passed: `Local/unreal-build-20261101T175855557261Z/receipt.json`, source ID `4ddc51880b9d0685899f79e131d89ce6d0ab3287713d82a4ef52d8431ca5bdc5`. Packaging with the death/visibility assets, native integration, rendered before/after, repeated one-/two-hand timing and blind Opus review remain pending. The queued editor binary is for asset work; use the new Shipping package for gameplay verification.
- Pacing metrics tests: 3 pass (duplicate snapshot/restart exclusion, overkill cap, missing-contact and invalid-clock rejection).
- Canonical animation graft identity test: zero joint error over 181 keys/midpoints; unchanged canonical binary/geometry. A static root mismatch is rejected.
- Original Blender sources and old native assets are protected. No paid generation or purchases.

## GPU wait

Streaming gate currently has zero capture slots. Initial 180-second queued jobs exited 75 without launching any renderer. Blender export is queued under gpu_slot for up to 3600 seconds (`dragon-boss-fight/Local/native-pacing-20261101/gpu-wait.json`, log export-wait.log). Owned editor is queued after compile (`Local/pacing-editor-20261101/gpu-ready.json`, log launcher-ready.log). Do not change gate settings or STREAMING. Check live state before restarting either job. The earlier editor queue was cancelled cleanly before a second compile; it never launched.

## Concrete continuation

1. Inspect the queued export receipt/log and owned editor state. Original queue attempts did not launch; the current jobs are waiting up to 3600 s without any gate override.
2. After export success, run `tools/unreal/prepare_pacing_plan.py` with the exported GLB and original death_v3 scene. It creates a fresh v029pacing plan, preserves canonical bytes, and verifies the exact source receipt. It does not change the active plan or native assets.
3. Verify native MCP project/world, snapshot protected character assets, then update only the Dragon entry in active-plans.json to the hash-locked plan. Import through the existing native tool. Inspect/preserve inherited mesh/skeleton/clip assets. Finalization uses the new preserve_inherited_material_bindings option; actor MIDs reference an optional definition material instead of rewriting meshes. Activation must copy that field too.
4. Package newest Shipping, capture both -VeyrPacingLegacy and default at 650 HP, with clean video plus boss bar. Measure first hit/gaps/burst, victory <=150 s, head-punish/rise and death pose. Review frames before the blind critic; never treat compile or export equivalence as quality.
5. Fresh anonymous Opus review. Stop on a tie per owner rule; no lowering HP to pass.
