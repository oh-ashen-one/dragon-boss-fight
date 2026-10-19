# Veyr presentation rebuild handoff

Repository: https://github.com/oh-ashen-one/veyr-cinder-warden
Branch: `feat/unreal-migration`. Historical Unity branch: `checkpoint/unity-native-009`.

## Active owner revision

The owner played and rejected a450a43b presentation. Work is active on the boat greatsword, one/two-hand combat, repaired full-body motion, active dragon, Gothic moonlit Tripo cathedral and restrained HUD. See docs/art-pass-20261019.md. The previous handoff below is a preserved mechanical baseline, not current visual acceptance.

## Revision checkpoint — 2026-10-19 20:15 UTC

Latest pushed checkpoint f35646b; current source changes still uncommitted. Latest native editor build0432f7aedc6c21a69b4615bb510ea960da9de1d9d15417256df44349a79bc2be passed. All three owned editors closed normally; last Local/owned-editor-20261019T200555Z wrapper81084 exit0 at20:14. Active root-owned offscreen stance test Evidence/native-stance-20261019T201443Z, wrapper22265,12requestedFPS1600x900. This tests the new full moveset and8.5s idle proof; finalresultpending.

Tripo web debit310 credits this pass. BoatGreatsword_v004 final2.8m weapon with correct shaftcenter/worldscale1,45cm belowrightgrip and28cm handspacing; native17,242/8,500/3,500tris. Three major cathedral meshes and1.8m brazier native imported with3LODs andactualUV1, importedPBRpreserved. Generated floor materialv001 repaired/saved; skyv003 nativecompiled/saved, sourceusescontinuous3Dcloudnoise. Ten built-in imagegen references/prompts retained privately and owneroutputs.

Dragonv00740clips activated. Native unengaged8.5sidle observation confirms head axis motion49.47/98.64/71.43cm, noinput. First90.134savoidancepassedall6moves butearlierartrejected. Round3nativeenvironment muchimproved/coherent, critic5.5/10; round4source0432 addsframingarchitecture/localwarm pools/lowmist/ridgeoverlap. Actualround4renderreviewpending.

Knightv014 full18clips imported/validated withzero definition/completeerrors andstableDAactivated forruntimeQA. PriorstableDA archived at /Game/Characters/Customuse/Runtime/Archive/DA_Knight_a450a43b. Includes10newcore/guard/heal/roll clips pluscorrectedJump/Stagger/Death andpreservedlocomotion. Nativev013posecritique found high/crossed2H arms andweaklowerbodyload; animatorworkingstancev2. V014notowneraccepted/final. Death visibleweaponrelease .30s/.72s fall hasoffline0bodyintersections/floor3cm, nativepending. Rollbody/lefttracks preserved, rightcarryonlychanged.

Rootownsengine/browser/builds/integration/Knight/Replay; animatorowns author_knight_stances.py/privatecandidates; Arena workerround4frozen. Preserveunrelated SourceManifest2file. No crashes this pass. Do notmistake API/materialerrors forcrashes; do notclaimplayablehandoffyet.

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
