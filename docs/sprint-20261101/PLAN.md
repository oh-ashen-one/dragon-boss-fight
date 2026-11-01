# Sprint investigation — baseline first

Owner attack-source selection remains pending. This independent pass refines runtime handling of the already approved Fab run, preserving the selected motion and its provenance. No new motion is authored or imported. Full backlog remains active.

The optional `-VeyrSprintProof` flag selects four sequences within the existing blendproof replay: SprintStop 1H/2H and WalkSprintWalk 1H/2H. The sequence uses ordinary movement/Shift/grip inputs with a passive boss, no actor teleport or resource edits. Setup walks to each start; lock-on is disabled for free sprint; a fixed side chase view and optional 25 cm floor checker expose foot travel. Run intervals last 2.2 seconds, or 1.6 seconds between one-second walk phases. Existing 60 cm/s planted-foot and 2 cm weapon-grip thresholds remain unchanged. Additional coverage requires peak speed above 500 cm/s, final stop below 10 cm/s and walk samples both before/after sprint.

This is inspection tooling, not a combat victory or a quality verdict. It records source clip phase, sprint request and actual speed per frame alongside the existing feet/capsule/weapon data. Baseline may fail the existing quality-related measurements; preserve those failures. Keep source files/assets unchanged until native evidence identifies the defect.

Known source facts: active Knight v030t inherits approved Run/RunTwoHand from the sourced v027b lineage, nominal 800 cm/s, gameplay play rate 1; ordinary speed caps are 580 sprint and 240 walk. The earlier footgate diagnosis covers lock-on strafes and downshift issues, not proof that the free-sprint loop is correctly matched. The new baseline must establish that separately.

Next: package harness-only Shipping, capture baseline through gpu_slot, inspect full start/cycle/downshift/stop in both grips, quantify steady and transition drift, then make a focused runtime correction with a legacy comparison flag. Film matched before/after and obtain a blind Opus verdict; first tie stops. Recheck normal victory under 150 seconds after accepted changes.

## Verified baseline

Harness-only Shipping `Local/package-20261101T230709Z/receipt.json`, source `305b39127115bb18717a7d471acc886d624cc5c967c445f877bb734199b876bc`, app `/private/tmp/veyr-verified-bundle-i287w93v/Veyr-Mac-Shipping.app`. Run `native-blendproof-20261101T230912Z` completed 47.174 game seconds, 4/4 sequences completed, 0/4 foot gates passed. The app exited cleanly; the command exited 1 because the measured scenario failed, not because of a crash. Peak speed 580 in every sequence. No tolerance changes.

| Sequence | Steady peak cm/s | Transition peak cm/s |
| --- | ---: | ---: |
| SprintStop 1H | 203.5 | 797.3 |
| SprintStop 2H | 780.1 | 467.4 |
| WalkSprintWalk 1H | 309.0 | 681.7 |
| WalkSprintWalk 2H | 197.8 | 1028.5 |

Interpretation limits: “steady” means unblended, not necessarily straight or constant-speed. Setup walks backward to each start, so the following forward sprint includes a natural turnaround; images at t=16.66 and 17.4 confirm rotation settles during the first part of the 2H trial. Do not misattribute its entire 780 cm/s maximum to stride mismatch. Among constant-speed (>550), unblended planted-foot samples, median signed world drift is about -51 cm/s right and -65 cm/s left; the implied source stance speed is 871–891 versus configured 800. Left stance sample count is only two per clip in this run, so this is a diagnostic, not sufficient calibration authority. Native run stance phases are ~0.47 left / ~0.97 right; walk phases broadly agree (~0.5 / ~0.92), so a wholesale phase offset is not supported.

A fixed-rate increase alone is not an adequate fix. Next investigate outgoing-pose continuation and foot contacts across start/downshift/stop, separately from turning. Preserve source assets, baseline films and strict gate. Add actor facing to per-frame diagnostics for the correction comparison. After the focused correction, capture same-build legacy/revision views plus actual gameplay camera, then blind review and combat regression.
