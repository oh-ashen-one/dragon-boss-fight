# Veyr implementation handoff

Repository: https://github.com/oh-ashen-one/veyr-cinder-warden
Branch: `feat/unreal-migration`. Historical Unity work remains preserved at `checkpoint/unity-native-009`.

## Objective and authority

Finish the original native Unreal dragon encounter and deliver a runnable Mac build, source, controls, native evidence, tests and asset credits. The owner explicitly grants standing Veyr launch and credit permission and says not to ask routine approval again. No subscription/account change, main merge or generated-asset public publication is needed. Keep Ghostty, Pocket Planet, foreign processes and reservations untouched. Root owns engine operations; the hard global renderer limit remains two.

The goal is active and near handoff, not complete. Remaining work is the final navigation-only package validation, physical input pass, final deliverables/documentation and cleanup.

## Current implementation

Unreal 5.8.3, native C++. Final main characters are Customuse Knight B and Dragon V3-B. Active private assets are Knight `v012`, Dragon `v006`, and stable runtime definitions under `/Game/Characters/Customuse/Runtime`. Both load automatically in a fresh game.

Knight: 244 cm, rigid sword, corrected cloth/carry, grounded Run, directional steps, full action set and native lower-body layers for moving guard/heal. Light/heavy strike windows match authored frontal blade motion. Four healing charges, directional guard, stamina, roll invulnerability, jump, lock and restart are implemented.

Dragon: repaired 51-joint rig, independent wings/jaw, 38 authored clips, four independent leg targets and buckle/collapse/head opening/rise. Actual mouth/feet/tail poses drive contacts and fixed warning unions. The native masked camera material preserves the head while clearing a narrow view corridor. Camera floor/boot framing, wall compression and marker placement have native rendered acceptance. Original procedural basalt, stone/fire graphs and audio complete the arena presentation.

Provider originals and rejected candidates remain private and unchanged. Local rig/skin/motion derivatives preserve lineage. Recorded generation debit totals 1,143 credits across 20 completed operations; no paid job is pending. Account balances, links and operation identities belong only in private records. Generated characters remain outside public Git pending raw redistribution clearance.

## Verified packaged baseline

Source `ee0313cda00023e00cfd6a679e37164de1cba268eee85db027bb4a31dc211516` passed the complete 11-scenario packaged suite: core, controls, leg0–leg3, avoidance, healing, guard, death/restart and victory/restart. Both characters remained active; no warning-containment failures were observed.

- Complete fight: boss defeated at 240.611 seconds (4:01), restart verified; total 246.206 seconds.
- Full suite receipt: `Local/final-packaged-suite-ee0313.json`.
- Victory evidence: `Evidence/native-victory-20261019T004812Z`.
- Core evidence: `Evidence/native-core-20261019T004813Z`.
- Package receipt: `Local/package-20261019T004413Z/receipt.json`.
- Baseline ZIP SHA256: `65b446f2ed73401f9bb2cad102efd70bd5c112b7130f6322df6be4b5c6d23c48`.

The final camera implementation was separately inspected in `Evidence/native-core-20261019T003614Z`: former wall/roll clipping is resolved, floor clearance >=224.167 cm, coherent foot projection <=600/720, clear collapse view, and marker above the knight with a leader line. Fire is a continuous orange plume. The small cheek detail was traced to unchanged original throat triangles, not a new jaw defect.

## Final navigation-only revision

The final baseline capture showed the automated player standing too close to the snout. Actual mesh clipping measured the front surface 206.535 cm from the head target; with the pawn radius, a safe center distance is >=248.535 cm. Heavy strikes reach 290 +/-15 cm without changing hit radii, damage or assets. The replay now runs beside the head, locks again near the target, uses heavy head punishes, and stays clear during Rise. Recovery completion must follow a head hit. Only `Source/Veyr/VeyrReplay.cpp` differs from the fully tested baseline.

Latest source: `e73a8a85b8a161ee0a6d532d8fa21729fc83d1595d4da4a82e6c0f2a275b3825`.

- Editor build: `Local/unreal-build-20261019T011006603475Z/receipt.json`, success.
- Native core: `Evidence/native-core-20261019T011105Z`, PASS 44.936 s, three heavy head bonuses at approximately 288 cm stand-off, then completed Rise. Root inspected the head-contact frame: the knight no longer stands inside the mouth.
- Latest package operation: `Local/package-20261019T011244Z`; inspect its terminal receipt before using the new app.
- Earlier `9ebd7ce6` navigation candidate stalled at the waypoint tolerance during its first opening; preserved. The waypoint was moved beyond the transition threshold, and the successful e73 run validates that correction.

Recheck final packaged core/victory and physical controls, record exact final-source footage, and make the handoff self-contained. The baseline suite remains an exact record; do not silently label its results with the final source ID.

## Packaging and operational rules

`tools/unreal/package.py` builds/cooks and creates a delivery copy from the exact matching fresh staged app. UAT can retain stale cooked payloads in its raw archive; both original/rejected outputs remain preserved. Code identity and map manifest must match before copying the stage. Final ZIP/extraction receives dependency, manifest/CRC and strict signature audits.

Documents FileProvider can reattach Finder metadata. Pre-staging signing uses a verified private copy when that specific race occurs, copies only signer-produced bytes back and checks exact payload parity. Final delivery signing/extraction stays outside that race. No quarantine or system security settings are changed.

Use `tools/unreal/run_native.py` for bounded tests through the shared slot wrapper; it stops on a failed scenario or process. Use `open_owned_editor.py` only when live native MCP work is needed. Native MCP is loopback port 18773; Snapshot before selecting Slate refs. The coordinator's editor maximum hold is 2,400 seconds: close owned sessions normally well before it, and do CPU authoring while the editor is closed. Prior lease-expiry evidence is preserved; never auto-relaunch crashed engines blindly.

Owned editor sessions are currently closed. Restore any transient background-throttle setting before closing an interactive editor. No foreground terminal windows are needed. Preserve the unrelated untracked `Assets/Resources/SourceManifest 2.txt`.

## Delivery state

The chat output area contains earlier milestones and `veyr-unreal-handoff`. The latter currently holds the ee0313 candidate ZIP, passed baseline videos, a checksummed private active-authoring pack (71 assets), and a README explicitly saying validation is in progress. Replace that status only after the final checks. Keep superseded files as clearly named milestones rather than confusing them with the final app.

Final answer should link only the actual final delivery files, the existing source branch/commit, current controls and concise test/limitation details. Capture is silent and uses real wall timestamps; GPU runs are shared, not exclusive performance benchmarks. Owner gameplay judgement remains distinct from mechanical and rendered checks.
