# Status: first blind TIE — stopped; candidate disabled

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

## Opt-in contact candidate (unreviewed)

`-VeyrSprintContactRevision` enables corrective stance anchoring only for grounded, unlocked Ready/RunStop locomotion. No source animation, speed, cadence, attack or damage change. The actor samples the uncorrected native pose, tracks low-foot contact and swing/lift/reach release, then re-evaluates with component-space ankle targets. The native proxy uses Epic AnimationCore two-bone IK without limb stretching, after the existing pose transition and before published bone/render data. Locked feet release over 60 ms when the sourced motion lifts/swings them or the correction exceeds 65 cm. A submerged toe marker may be lifted to floor level; normal bone/sole height is retained. Source curves/upper body are unchanged. Default gameplay remains legacy until review.

The pilot must verify no missing-bone fallback, finite transforms, unchanged bone lengths, contact release/no stuck feet, knee bend and rendered transitions. Existing foot/grip limits are not relaxed. Current Shipping compile succeeded; package/pilot pending. Actor yaw was added to evidence so turnaround drift can be distinguished from straight running. No quality claim or blind verdict yet.


### First contact pilot: rejected before blind review

Source `1d40b3a513ad3225baf7fad8cae100d679c268b181b2d6be7c2ca39d522d4425`, package 231844, run `native-blendproof-20261101T232105Z`: all four completed, all foot gates still failed. One-hand steady peak improved 203.5→39.9 cm/s, but two-hand start transition worsened to 1469.8 cm/s. Exact results in contact-pilot1-results.json. Native frames and yaw telemetry show the held foot released around alpha .5 during a 180-degree startup turn, then travelled 49 cm in 34 ms while still low. The world-relative velocity was incorrectly used to release an already planted foot. This candidate is not accepted and remains opt-in.

Second pilot removes velocity-based release for an existing plant (velocity still prevents false acquisition), retaining actual lift release; the raw-displacement escape is increased from 65 to 130 cm to avoid reacting to the rotation sweep. The solver still forbids stretching; explicit native upper/lower bone-length invariants and missing-ankle rejection were added. Runtime evidence now records the enabled flag and foot weights. Package/capture pending; no default activation or quality verdict.


### Second pilot and next correction

`native-blendproof-20261101T232837Z`, source `ba452f6fdb0b37a82b01ed715d64d2cc6200c1bb07863d3d3da9d3b2dcd01d80`, package 232613: all four completed, foot gates 0/4. Enabled flag observed in all 185 snapshots; no native presentation diagnostic or bone-length failure. SprintStop steady maxima are now 39.0 (1H) and 1.1 (2H) cm/s, but transitions remain 406 / 291 cm/s; WalkSprintWalk also fails. Results preserved in contact-pilot2-results.json.

Next pilot keeps the toe anchor but follows the source foot orientation/heel roll, and releases vertical correction immediately on sourced lift while fading only planar correction. Full-transform release had held the foot low while moving it. Per-frame anchor weights are now recorded. This is still opt-in and unreviewed; no source motion, gait speed or gate limit was altered. Package/capture pending.


### Third/fourth pilot evidence

Third run `native-blendproof-20261101T233320Z`: 0/4 foot gates, worst maxima 152 / 975 / 753 / 624 cm/s. Toe anchoring retained heel roll, but foot heading still rotated while planted and raw low-swing frames were counted as contact. Fourth run `native-blendproof-20261101T234007Z`: 0/4, maxima 140 / 519 / 788 / 273 cm/s; one 2H sword hand-space check was 2.02 cm against unchanged 2 cm limit. Actor-space source velocity and bounded swing clearance improve several measures but do not establish acceptance. All cases/frames remain preserved.

Fifth pilot preserves planted heading while retaining source heel roll, releases large (>50 degree) pivots with clearance before replanting, and holds existing plants during stationary stop/idle blends. Normal authored swing/lift still releases the contact. Pose-reference resets explicitly clear the new IK targets. Compiling/packaging; still opt-in, no default activation, no blind verdict.


### Calibrated candidate and first blind review

Final reviewed candidate is package 235414, source d0656427ab499ab2e839f203459f4e1ede457759e8e164edf5f0c561d0c032ac. Boot sole offsets were measured read-only from the approved glTF in owned background Blender; source SHA unchanged. Same-build lab and ordinary-camera before/after films are complete; all timing verified, zero failed captures. Page 8808 switches views without text on the films. Fidelity failures are retained in review-results.json; no tolerance change or automatic acceptance. The independent first blind review is running on all 41 native frame sheets. No further visual iteration until its result; first TIE stops work.


## First blind outcome — TIE, stop

The critic inspected all 41 sheets and found no meaningful overall preference. A (baseline) closes feet rapidly into a cleaner idle stance; B (candidate) keeps contact but freezes a wide/unresolved stride. Starts, running and downshift are effectively unchanged; downshift remains abrupt. Do not claim sprint improvement from numerical changes. The user explicitly requires stopping on the first blind tie; no further implementation/review/engine launch was performed after this verdict. Candidate remains opt-in/off by default. Owner continuation is required. The suggested next investigation is a sourced stop/step-in that reaches a deliberate stance without skating, followed by genuinely matched visual evidence; do not silently continue it now.
