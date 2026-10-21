# Veyr presentation rebuild handoff

Repository: https://github.com/oh-ashen-one/veyr-cinder-warden
Branch: `feat/unreal-migration`. Historical Unity branch: `checkpoint/unity-native-009`.

## Active owner revision

The owner played and rejected a450a43b presentation. Work is active on the boat greatsword, one/two-hand combat, repaired full-body motion, active dragon, Gothic moonlit Tripo cathedral and restrained HUD. See docs/art-pass-20261019.md. The previous handoff below is a preserved mechanical baseline, not current visual acceptance.

## Final revision handoff — 2026-10-19

The requested boat-sword and cathedral pass is implemented and the native Mac build is verified for owner playtest. Final source-and-asset identity: `9b185634d4c3b88084749bc8eb8c079546724eb6a969cf382f390620c81758db`. Package receipt: `Local/package-20261019T210433Z/receipt.json`. All 12 source-matched packaged scenarios passed in `Local/final-packaged-suite-sky4.json`. Victory occurred at 202.145 seconds (3:22), followed by a successful restart.

Physical E-key switching and the other recorded keyboard controls were verified. The UI API's standalone Shift limitation remains separate from the passing native roll checks. All owned editors and games exited normally and released their slots. Foreign Hollow Current work remained untouched. There were no Unreal crashes in this pass.

Active assets are Knight v015 (18 clips) and Dragon v007 (40 clips), retaining both character designs. The knight uses the v2 core/guard poses, reviewed v1 heal/roll/jump/stagger/death clips, and preserved locomotion. The accepted roll body and left-side tracks are unchanged; only the right-arm carry accommodates the new weapon. Generator SHA256: `5c87df5509a5f4b7a8a2afc7dae6b64dd865c0ba29b539fac7bf50cfd02cf1d1`. Root and critic reviewed 12 native poses without a hard grip or pose blocker. Remaining polish includes close-range weapon occlusion against the dragon and environmental depth. Do not claim AAA/reference-match or owner acceptance.

Tripo used 310 credits in this pass: weapon 55 plus retopology 35, then facade, wall, arch and brazier at 55 each. Boat v004 is 2.8 m tall with unit world scale. Eleven major cathedral placements retain their imported PBR materials. Built-in image generation supplied 10 references/textures and saved prompts. Floor material is v001; night sky is v004. Ambient light captures the actual night sky instead of the old daylight cubemap. The meteor starts at u=0.47, polar UV=0.39, with vertical travel 0.018 and a 37-second period. Natural visibility was verified around 23 seconds without a time override. The earlier high-sky version remains preserved privately.

Owner delivery is `/Users/midir/Documents/Codex/2026-10-18/go/outputs/veyr-art-pass`. It contains `Veyr-Mac-9b185634.zip`, validation, physical-input notes, instructions, native videos and reference art. The ZIP is 638637929 bytes; SHA256 is `25bb280fe123d68a8d6a16b9c835b0bd4659b5be2c8f566653c1e6c41acd5747`. Studio Downloads contains the same ZIP and the verified extracted app at `/Users/midir/Downloads/Veyr-Cathedral-Pass-9b185634/Veyr.app`. No laptop installation is claimed.

The private editable archive `Veyr-EditableAssets-Knight15-Dragon7-Sky4.zip` contains 105 active packages. Its SHA256 is `f63b336cc63eb7f314daf8d143bfd29444fd70657d23905385dae313994afa25`. Restore its Content directory under Unreal/Veyr. Provider originals and rejected candidates remain private; raw assets were not published to GitHub. Source stays on `feat/unreal-migration`; no main merge was performed. Preserve the unrelated `Assets/Resources/SourceManifest 2.txt`.

## Prior delivered state

Native Unreal 5.8.3 arm64 macOS encounter, source identity `a450a43b4b726a5bdebdd5ce8ca8a49fcf36dbc766fe4884d939e4d3ec8ac825`. The final signed app passed all 11 packaged scenarios, with Customuse Knight B v012 and Dragon V3-B v006 active. Victory occurred at 214.158 game seconds (3:34); fresh responsive restart completed at 219.691 seconds. See [final test results](docs/native-test-results.md).

The owner delivery contains `Veyr-Mac-a450a43b.zip`, exact-source core/full-fight videos and timing receipts, `Validation.json`, `Physical-Input.json`, SHA256SUMS and `READ-ME.txt`. The separate private active-authoring ZIP contains 71 assets, unchanged since ee0313. Restore its Characters directory under Unreal/Veyr/Content before rebuilding from public source. Its older filename identifies the asset snapshot, not a different final character revision.

Game ZIP SHA256: `d37d2c0c5526a3dac0a01b1edb4c29fa1e243b8d03347156ef8c90653cfcec5d`. Cook, strict ad-hoc signature, ZIP CRC, extracted manifest and 15 binary dependencies passed. The app is locally signed, not notarized. Raw Customuse derivatives remain private pending public redistribution clearance. Code is MIT; original procedural art and Epic resources retain their separate licenses.

## Evidence and exact build

- Final package: `Local/package-20261019T012734Z/receipt.json`.
- Standalone build: `Local/unreal-build-20261019T012735299495Z/receipt.json`.
- Matching editor build: `Local/unreal-build-20261019T013815658137Z/receipt.json`.
- Final suite: `Local/final-packaged-suite-a450a43b.json`.
- Victory: `Evidence/native-victory-20261019T013107Z`.
- Core: `Evidence/native-core-20261019T013108Z`.
- Physical input: `Evidence/manual-input-a450a43b/physical-input.json`.

Physical standalone input verified capture, movement, attacks, jump, guard, healing, lock, Escape release, recapture and restart. The UI API rejects modifier-only Shift, so its physical mapping remains owner-playtest coverage; native tests verified dodge motion, stamina and invulnerability. Audio was enabled but not aurally reviewed. Recordings are silent 8-FPS requested captures with actual wall timestamps; shared GPU/capture overhead precludes exclusive performance claims. Owner feel/difficulty/visual judgement is not inferred from automated tests.

## Final implementation

Knight: 244 cm, rigid weapon, corrected cloth/carry and grounded gait; full action clips with moving guard/heal layers; four heals, directional guard, stamina, jump, dodge immunity and optional lock. Dragon: 51-joint repaired rig, 38 authored clips, independent leg stagger/buckle/collapse, exposed head and rise; pose-driven attack contacts and bounded warnings for six attacks. Camera floor/wall/close framing and head marker were reviewed in native captures. Original basalt, material graphs, continuous fire cards and synthesized audio complete the arena.

Safe automated head approach uses a side waypoint and approximately 288 cm heavy-punish distance, avoiding the snout. Final dragon health is 5,800, calibrated from a measured 6:20 safe-route fight at 8,400 to the verified 3:34 final fight. No player damage, stagger, stamina or enemy move changes accompanied that calibration.

Recorded provider debit: 1,143 credits across 20 completed operations; no pending paid job. Provider originals and failed/rejected evidence remain preserved. The owner grants standing Veyr launch/credit authority and explicitly says not to ask routine permission again. No main merge, subscription change or generated-asset public publication was performed.

## Operating continuity

All owned editor and standalone sessions are closed; final physical process exit was 0 and its GPU slot released. No renderer should be assumed reserved. Verify actual ownership and shared slots before another launch; hard cap remains two renderer-bearing engines. Ghostty, Pocket Planet and foreign jobs remain outside task authority. Preserve unrelated untracked `Assets/Resources/SourceManifest 2.txt`.

The baseline source was frozen at d94cd2e; the authorized presentation revision is now in progress. Use source-matched package receipts and native results when extending it. Earlier historical failures and milestones remain labeled; do not reuse their source IDs as final acceptance. FileProvider signing races and stale raw UAT payloads are handled by audited private signing copies and exact fresh-stage packaging; no global security or quarantine setting was weakened.
