# October 26 gameplay and cathedral overhaul

Branch: `codex/veyr-cathedral-overhaul-20261026`, based on `3310d64`. This pass preserves the approved knight, dragon, sourced walk/run/slash/roll and original guard. Owner gameplay and listening acceptance remain separate from the checks below.

## Implemented

- Fixed close560cm camera /72-degree FOV, no flight pullback or wheel zoom. Manual look spans−55..68degrees; automatic aerial tracking stops at25degrees with raised pivot. Minor breakables hide when occluding the player instead of crushing the spring arm; solid architecture still blocks the camera.
- Sword sweeps include torso, chest, neck and tail alongside four legs and head, use bounded actual blade thickness and retain one damage event per swing. Contact sparks mark the selected hit position.
- Light attacks cost16/20 stamina, heavy24/29, roll18 and blink20. Ready recovery38/s and shorter delays allow longer chains. Boss health2800; two-hand attacks deal1.55x damage with slower timing.
- Faster turns/travel, encounter-clock flight scheduling, higher flight, committed overhead-fire target/warning and separate fire/landing hit budgets. Airborne death descends and airborne stagger cannot strand the dragon.
- Dragon v028 uses the dangling-paw hover and Blender-corrected takeoff/landing joins. Knight v029 adapts sourced lateral motion with most displacement inside blink disappearance; native-axis mapping is verified. Original guard remains unchanged.
- Thirteen recorded effects plus orchestral music and dungeon ambience, spatial boss/destruction emitters, bounded voices and separate master/music/effects settings. Existing supplementary heal/exposed/terminal tones remain.
- Layered Gothic terraces, high open ribs, generated grounded portals, warm suspended chandeliers, atmospheric separation and distant flying dragons. Four falling chandeliers and ten breakable props use a bounded debris pool.

## Validation

`validation.json` records exact evidence paths and source IDs. Native R3 integration passes18/18 features; original guard passes front chip/rear damage/exhaustion; all eight collision stages pass, including sprint/roll/blink and landing push. Final native banks pass168 knight and258 dragon pose samples. The actual Shipping stance run verifies six grip/damage/roll cases and exact health loss for accepted contacts. Full Shipping victory, resource reset, movement and primary attack after restart pass.

Independent visual critique confirms the earlier armor-filled aerial camera regression is resolved: reviewed R3/Shipping requested560cm, resolved about562–564cm, FOV72, automatic pitch≤25, zero severe compression. Manual controls and final performance are recorded separately in adjacent receipts. Final Shipping integration also passes18/18. Exclusive1280×720 performance averaged59.91FPS with the explicit60FPS cap; p50/p95/p99 intervals16.67/16.77/16.85ms,7of11987 intervals over33.3ms, maximum72.17ms. Still captures do not certify continuous motion or acoustic quality.

The final Shipping89.37s stereo master recording contains99.65% nonzero samples, peak−14.28dBFS, zero clipped samples. This proves sound output, not a listening-quality verdict.

## Startup repair

One Development packaged candidate crashed before game initialization in `FLLMTracker::PopTag` through `FMallocAnsi` during AppKit startup. The private crash report and failed run are preserved. Standard Shipping excludes that Development debug-tracker path and has passed repeated cold launch and full gameplay. No engine source, security controls or global allocator environment were changed. The existing app-scoped ANSI setting is retained. Signed ZIP extraction, bundled Mach-O dependencies and ad-hoc signature are verified; the app is not notarized.

## Assets and restoration

New architecture is three Meshy7.1 models,90credits total, downloaded directly by API without Finder/Save dialogs. An earlier65-credit Tripo chandelier remains in the account but was not exported or used. The Fab experiment is unused. See `assets.md` for source rights and transformations.

Final editable assets are backed up privately in `oh-ashen-one/veyr-animation-sources`, release `overhaul-authoring-20261026`, with matching remote SHA256. Native delta and game delivery use the adjacent backup/delivery receipts. Restricted raw models/motions are excluded from public Git. Restore the v027 baseline chain before applying the v029 delta; cloning code alone is insufficient.

## Limits

The architecture is more coherent and vertically layered, but remains darker and more enclosed than the generated concept. Generated decorative meshes are not watertight and use appropriate simple collision. The input replay covers actual gameplay action paths, not every physical key or all possible frame-rate/hitch/contact combinations. Automated fight pacing is not a human difficulty verdict. Performance results apply only to the documented Studio, resolution and uncontaminated run. No laptop or different-resolution performance is inferred.

The delivered app and separate silent native capture/master audio are in `~/Downloads/Veyr-Cathedral-Overhaul-v029`. Capture cadence9.81FPS is deliberately separate from the capture-free performance test. Manual menu keyboard operation and music change/restore passed; physical mouse activation and maximum manual upward angle remain unverified.
