# Veyr current checkpoint — 2026-11-05

**Full MASTER_GOAL active and incomplete. This continuation made substantial progress; it is not blocked.** Read MASTER_GOAL.md and the current BACKLOG.md; older job claims are historical. Git history and the linked evidence retain previous checkpoints.

## Ownership and fixed rules

- Knight/game: this checkout, `fable/knight-complete-20261028`. Dragon: `/Users/midir/dragon-boss-fight`, `claude-code-enhancements`, untouched. Never merge/push game main. Preserve the foreign unstaged deletion `Local/knight-review-20261028/critique-round2.md` and foreign wiki edits.
- Mac Studio `Mac15,14`; UE5.8.3 and Blender5.2. Background/windowed only; all renderer/encoder jobs use the ordinary shared `gpu_slot`, cap3 lowered to2 by the existing watchdog warning. Never override gates, restart watchdog, remove STREAMING, or touch foreign processes. Honor `tools/unreal/owned_launch_budget.py` (ten starts/hour).
- Owner approved the exact R5 eight-shot fortress/mural tour as the pre-fight intro. Its recipe remains byte-identical to491d37d; `approved-tour-current-check.json` verifies it. Preserve accepted heavy attacks, wings, feedback/settings, one supplied OST, dedicated CC0 dragon sounds and one player grunt. Never restore the Fish human-dragon imitation.
- Source-first animation, actual Blender authoring/editable scenes, licensed acquisition/provenance. Source/native fidelity is not quality acceptance. First blind tie stops that candidate: **Mixamo grounded Turn180_A v4 remains stopped and unimported**; do not revise or promote it without new direction.
- Current published rules revision6556abef. The latest injected cache is290c36bd3b9ebf5481c4. Freshness was refreshed and approved GitHub main verified before the paid review. Check freshness again before publication if it ages.

## Verified progress

1. **Default recovery smoke passed** on kqk_c5eo: `Evidence/native-controls-20261105T042817Z`,674 frames,23 event screenshots inspected. Recovery enabled without its explicit flag; attacks, roll, stamina, guard contact, heal and full-health rejection passed. Earlier scoped recovery4/4 + blind win and41.240s2H /74.987s1H victories remain valid for their exact builds at650HP. Final balance/regressions remain open.
2. **ACCAD source work actually executed in Blender.** ContactFitV4 contains all3 fitted/trimmed starts/stops; ankle-path/limb-length/retained-key checks passed but boots still penetrated (run-start7.33cm, stop5.26cm, walk-start3.65cm worst). SupportFitV5 corrects only the run-start via a shared upward body offset, preserving relative poses, footXY and grips. Exported boot minima are0.05cm; maximum shared lift7.4135cm. No independent knee reshaping or frozen stride.
3. **Two-handed weapon start v6** composes existing idle/Mixamo greatsword arms with corrected ACCAD lower/torso motion. First fixed-contact attempt failed reachability without saving an asset; fitting one constant handle contact succeeded under the same bound. Actual exported lower/torso error1.642e-6 and arm-length error6.432e-6 source units. Raw/editable sources stay under `Local/AttackSources20261105/ACCADMale1`.
4. **Actual blind Opus5.5 first round chose B=v6, visibly better, native trial allowed only.**31 reads/30 images verified; cost0.9489286USD. Remaining: shoulder deformation/gap, stiffness/insufficient sword weight, tight helmet clearance, precise finger contact and initial delay. This is NOT final quality acceptance. Reports `blind-accad-weapon-*`; total known critic estimates23.566352USD plus one older unpriced abort. No new paid generation.
5. **Native v046start imported and verified** with CPU-only NullRHI commandlet:384 native and384 canonical pose samples passed. Canonical export sole minimum0.04988cm; actor/pose reconstruction error9.068e-7. RuntimePolish now points to `/Game/Characters/Customuse/KnightB/v046start/DA_KnightB`; old v045 assets are retained. `prepare_accad_start.py` is the reproducible preparation. Native pose fidelity is not gameplay acceptance.
6. **Real opt-in RunStart state implemented and packaged.** Requires `-VeyrSourcedSprint -VeyrPlantedSprint -VeyrSourcedRunStart`. Swept authored root travel, interruptible inputs, measured velocity carry and a moving last0.30s blend into the phase-matched run loop. A four-case `-VeyrRunStartProof` uses ordinary inputs for full start, early release, primary cancellation and a one-hand control. Newest Shipping source46174b41... package receipt `Local/package-20261105T053009Z/receipt.json`; app `/private/tmp/veyr-verified-bundle-2_gxw0jo/Veyr-Mac-Shipping.app`. Default remains OFF.

## Native failures that still need fixes

- Same-app before/after: `native-blendproof-20261105T053952Z` / `054354Z`. **0/4 contact passes in both** with unchanged60cm/s foot and2cm grip limits. After, the real start state, running handoff, release and attack cancellation work; one-hand control never enters the two-hand start. All paired trial frame intervals are below38ms. Entry turns and run-to-stop joins still skate. Peak values are diagnostics, not an isolated improvement percentage: initial facing/outgoing gait phases can differ after ordinary-input setup.
- Fresh existing running/leap trial: `native-blendproof-20261105T050118Z`, **0/8 foot-contact passes**. Leap capsule lift now actually observed at23–24cm; the historical flat-capsule failure predates its existing source fix. Running attacks fail chiefly at entry joins; leaps fail steady contacts. The last3 one-hand trials exceed50ms frame intervals and must not enter acceptance packets. See `current-mobility-gameplay.json`.
- No native run-start blind quality pass has been claimed; hard contact failures remain. The source-only Opus win does not ship this prototype. Do not lower thresholds, freeze whole strides, restore a tied candidate, or lower HP to pass.

## Live state and next work

All task-owned engines, Blender jobs, native commandlets, encoders and critic calls are **terminal**. There is no queued Veyr renderer. Current source review server remains intentionally live on8813, receipt `Local/Fortress20261103/master-review-server.json`; other preserved review pages53995 (stopped turn) and58410 are deliverables. Verify PIDs/handles before using them; do not infer live state from this paragraph alone.

Next: diagnose stop-entry gait-phase mismatch and initial180degree turns from the actual failed captures, then repair them with appropriate sourced transitions/contact work. The new start still needs one-handed counterpart, native shoulder/grip/clearance/response review, and full acceptance. Keep running/leap/light transitions, normal-camera healing and airborne/rearing threat visibility, every-move/settings/collision/performance, final both-grip<=150s victories and final launcher/pointer promotion in scope. The source review permits a trial, not a final-quality shortcut.

The native pose reference helper `probe_grip_references.py` still pins v045: bind any new reference job to the definition matching its captured build; do not silently sample the wrong revision after v046 activation.

## Watching, builds and publication

Bare page: `http://localhost:8813/`. Source greatsword comparison: `#weaponstart`; native run-start comparison: `#nativestart`. Source and native films have no editorial overlays; existing gameplay HUD remains. Final full-goal quality is unaccepted.

Keep kqk_c5eo as the last default-controls fallback and2_gxw0jo as the active trial build. zio8vgsq is now superseded; prune receipt-owned obsolete bundles/archives/stages after the current source/wiki push is verified. Preserve original assets, final films and small evidence. `Local/LatestShipping.json` is still stale; do not use it to open the game. Final verified persistent installation/launcher is unfinished.

Current requirements and all evidence: `docs/master-goal-20261103/requirements.json`. Previous14.874GiB cleanup remains recorded; this checkpoint needs its own scoped security scan, push, wiki update and cleanup receipt. No game main merge/push.
