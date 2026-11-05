# Veyr playable wrap-up — 2026-11-05

The owner cleared the long-running goal and explicitly authorized compiling, merging Veyr branches into main, deleting obsolete builds, and handing over a playable game. This supersedes the older no-main restriction for this consolidation. The research loop is ended; do not resume unfinished animation experiments automatically.

## Compiled and verified

- Editor Development and game Shipping targets compile successfully;482 tracked Python sources pass syntax checks.
- Fresh package: `Local/package-20261105T195840Z/receipt.json`. Source identity8755f4dc816ad7923c6a346ee72b0a696be80ce5d58040a56514d163fbad325f.
- Final packaged controls and full production intro tests pass. The approved eight-shot fortress/mural sequence remains before the encounter, isolates combat/music, then hands back control and starts the chosen soundtrack once.
- Complete victory/restart checks pass: one hand74.929game/75.618active-wall seconds; two hands38.781game/39.112active-wall seconds, unchanged650HP. Controls/intro/victory screenshots were inspected. Exact evidence: `docs/wrapup-20261105/verification.json`.
- Play profile: canonical knight skin, stable weapon presentation, walk-entry blending and readable auto-lock. The rejected contiguous movement, unfinished sourced movement replacements and experimental threat-camera framing remain disabled. Backlog items are not claimed completed.

## Play installation

The signed Shipping app is installed under `$HOME/Applications/Veyr/<binary-hash>/Veyr-Mac-Shipping.app`. `Local/LatestShipping.json` now points to the installed, verified build; it is no longer stale. `Local/ShippingInstallation.json` records the exact app, source identity and signature/launcher checks.

Use **Play Veyr.app** on the Desktop, linked to `$HOME/Applications/Play Veyr.app`. Its small native launcher starts the existing GPU-guarded Python launcher without opening Terminal. It preserves background/windowed launch and60fps limits. Click/Enter in the game to take control; Enter restarts after victory/death. The supplied OST, dedicated dragon effects and single player grunt are preserved.

## Consolidation and ownership

All fetched Veyr branch heads are ancestors of local main, including the knight/game work, dragon authoring, prior cleanup records and main privacy fixes. The same repository was present in two independent clones, not multiple linked temporary worktrees. Both authoring checkouts contain private source assets and are retained. Recent dragon facts are archived in `docs/handoffs/DRAGON-AUTHORING-20261105.md`; full history remains reachable through the merge commits.

The pre-existing deletion of `Local/knight-review-20261028/critique-round2.md` belongs to earlier work and is intentionally left unstaged. Other sessions' processes and checkouts remain untouched. Merge/push verification and final cleanup results are recorded under `docs/wrapup-20261105/`.

## Experimental history retained, not promoted

The inactive v047 trial imported successfully and fixed its exact run-to-stop entry, but its full motion tests remained0/4. Actual blind Opus preferred the earlier stop and the new sprint carry; neither was shippable. Details: `native-contiguous047-checkpoint.json`, `blind-contiguous047-receipt.json` and the full requirements ledger under `docs/master-goal-20261103`. First-tie Turn180_A v4 remains stopped. Known critic estimates total25.0463422USD plus one historical unpriced abort; no new paid work in this wrap-up.

Current and earlier films remain on the bare review page at port8813. No renderer/encoder job from the cancelled research loop remains active. Only intentional review services and a later owner-play launch may remain running; verify receipts/PIDs before any action. The full unfinished scope remains in BACKLOG.md for a separately authorized future task.
