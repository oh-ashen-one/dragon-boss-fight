# Opus 5.5 final enhancements — branch `opus-5.5-final-enhancements` (2026-11-05)

- **Video2rig bite, end to end (opt-in `-VeyrVideoBite`, awaiting owner visual review).** Existing Seedance bite → video2rig fit → Blender cut/retime (2.47 s, body lunge kept, jaw snap) → canonical export → native DragonV3B `v034videobite` (300 poses, 0 failures; RuntimePolish/DA_Dragon promoted, keyed Bite retained) → Shipping `Local/package-20261106T001217Z`. Before/after showcase runs on that one app both PASS 20/20. Review page `Local/bite-review-20261105/serve/` on port 8814 (task-owned server). Details and exact evidence: `docs/video-bite-20261105.md`.
- **Overnight results: `docs/overnight-v2r-20261105/RESULTS.md` (default video2rig moves + raised-wing idle; victory gate regression 316 s vs 79.8 s legacy).**
- **Overnight pass (2026-11-05/06, owner asleep, full autonomy; plan `docs/overnight-v2r-20261105/PLAN.md`).** Video2rig clips are named `<Clip>V2r` and play by default; `-VeyrLegacyDragon` restores keyed clips. Native versions: `v035videomoves` (Claw0/1, Buckle0/1, Collapse, Exposed loop, Tail, Stomp2/3; 414 poses, 0 failures) and `v036idlewings` (IdleOpenV2r: video2rig idle with raised, spread wings, replacing the crumpled folded idle the owner flagged). Attack durations now follow V2r clips. Tools: `tools/dragon_refine/{cut_v2r_move,mirror_v2r_action,probe_v2r_points,probe_wing_spread}.py`, `tools/unreal/prepare_video_moves_plan.py`, live dashboard `tools/dragon_refine/dashboard.py` (port 8815, serves `Local/bite-review-20261105/overnight-serve`). Credits 315/420 (ledger `Local/video2rig/dragon/clips/ledger-20261105.json`). Remaining: fire_r2 `f25440b6`, walk_r2 `8cba6700`, hind_stagger_r2 `aa4ea1cd` (fit + cut), turn (fit done, needs root-yaw samples), rise needs a lying start picture + reader, victory/core regression, blind review.
- **Current state for the next session (2026-11-06 ~13:57 ET):**
  - Branch `opus-5.5-final-enhancements`; latest Shipping app `/private/tmp/veyr-verified-bundle-38egs0xg/Veyr-Mac-Shipping.app` (receipt: `Local/package-20261106T185009Z/receipt.json`, source ID `1cd9e267dfba252c2651abc8329bcd6e2f35d4c85639dd7f09c4df09bfadf21f`). Active DragonV3B plan: `Local/CustomuseAssets/Polish20261025/videomoves-v039turn/` (chain v035→v036→v037→v038→v039, all native pose checks passed).
  - Default video2rig clips (`<Clip>V2r`): IdleOpen (raised-wing fix), Bite, Claw0/1, Tail, Stomp2/3, Fire, TurnLeft (87.5° stretch; actor turns by the clip's own root yaw samples, `root_motion_removed: true`). `-VeyrLegacyDragon` = all keyed. Opt-in: `-VeyrVideoStagger` (Buckle0/1, Collapse, Exposed), `-VeyrVideoWalk`. Bisect: `-VeyrLegacyClips=Prefix,...`.
  - **Step 1 completed (victory test + opening balance pass):** Unmodified `v039turn` failed the 150 s victory gate at `301.182 s` (`Evidence/native-victory-20261106T175001Z`) because shorter V2r recovery clips (`0.59–1.07 s` vs legacy `1.50–2.00 s`) and `0.35 s` post-reposition `Idle` expired while the knight completed `RunStop` (`0.40 s`) and lock-on facing rotation (`0.35 s`). Restoring the post-recovery (`FMath::Max(1.25f, 3.60f - RecoveryDuration)`) and post-reposition (`1.25f`) `Idle` windows when V2r clips are active (`!bLegacyDragon`) brings default victory down to **`75.042 s`** (`Evidence/native-victory-20261106T185252Z`, PASS, first hit `15.13 s`, terminal pose and restart verified).
  - Dashboard: `python3 tools/dragon_refine/dashboard.py Local/bite-review-20261105/overnight-serve --port 8815` (status in `status.json`, before/after clips cut by re-running showcase pairs).
- **Next steps (in order):** (2) walk: shorten showcase walk distance or lower `WalkV2r` nominal speed (428 cm/s) without foot sliding and make `WalkV2r` default; (3) stagger chain: verify/rebalance stagger openings so victory stays under 150 s with `-VeyrVideoStagger`, then make default; (4) hind buckles + rise skipped (checked Higgsfield workspace `3fd8dbb7-f3d5-4542-9e6c-65c8baddbb70` without spending: `7.79` credits remaining, below 35-credit Seedance 720p cost); (5) blind Opus review of the dashboard clips + `status.json` update; (6) wiki + cleanup of superseded builds.
- The playtest items below remain open. Next candidates once the owner approves the bite: same pipeline for claw/stagger/collapse/rise, root-motion actor travel, Leshy-style brain.
- `Local/video2rig/dragon/` was restored from release `v2r-dragon-20261028`; later Seedance clips are re-downloadable from Higgsfield history (no spend).

---

# New owner playtest backlog — 2026-11-05 (record only)

**Do not implement yet.** The owner is collecting feedback for a different session. These are requested changes, not completed fixes or authorization to resume the archived goal. Leave the running game, installed build, code and assets unchanged while collecting notes.

1. **Faster overall pace.** Running and dragon movement currently feel like roughly 0.75x speed. Make both noticeably faster and more responsive. This is a subjective description, not a measured time-dilation value or a specified global speed multiplier.
2. **Much harder, more aggressive boss.** The owner nearly depleted the dragon's health while barely being hit. It currently barely moves, attacks or connects. The desired result is a genuinely very difficult boss fight, with sustained pressure rather than passive stretches. Increasing health alone does not address this complaint.
3. **Range- and position-aware attack selection.** As soon as the player enters attack range, the dragon should pick a random suitable attack and engage. If the player stays underneath it too long, it should take off and use a fire attack that forces the player to run away. If the player camps the back-right foot/corner, it should select an attack that actually reaches that region. Generalize that spatial response so a safe corner cannot be exploited indefinitely. Preserve the owner's request for randomized selection while making the available choices appropriate to player position and recent camping.
4. **Remove the floor attack-radius telegraph.** Remove the large yellow/red circle on the ground that reveals the dragon's attack area. This request specifically concerns that floor indicator; it does not request removal of all combat feedback or the HUD.
5. **More dragon health.** Owner suggests approximately 30% more health. The last verified build has 650 HP, so 845 HP is the corresponding provisional value, not an implemented or final tuned value. The previously requested 150-second target has not been explicitly withdrawn; the future balance pass must assess that target together with greater aggression and health, rather than treating an easy automated victory as proof of sufficient difficulty.
6. **Much larger dragon.** Owner estimates the current dragon reads roughly 12–15 ft tall against a roughly 6 ft player and wants it to read around 30 ft tall. These are perceived scale estimates, not verified engine measurements. The player should feel tiny beneath its legs. Enlarge the entire creature proportionally; future implementation must also verify attack reach, collision, foot/head hit access, camera occlusion, flight and arena fit at the new scale.

## Continuation instructions

- Start with this section and collect any additional owner notes before implementing. All six items are **OPEN / NOT STARTED**.
- Preserve the owner-approved eight-shot fortress/mural intro, chosen soundtrack and existing assets. Do not revive rejected motion experiments as part of recording this feedback.
- When implementation is separately authorized, follow the existing GPU/process ownership rules and before/after film plus blind Opus quality gates. Player difficulty acceptance remains distinct from automated completion tests.
- Documentation branch: `codex/veyr-playtest-backlog-20261105`. The playable main baseline is `5bb338f7a1ad`; this documentation does not alter the installed Shipping build.

---

# Veyr playable wrap-up — 2026-11-05

The owner cleared the long-running goal and explicitly authorized compiling, merging Veyr branches into main, deleting obsolete builds, and handing over a playable game. This supersedes the older no-main restriction for this consolidation. The research loop is ended; do not resume unfinished animation experiments automatically.

## Compiled and verified

- Editor Development and game Shipping targets compile successfully; 482 tracked Python sources pass syntax checks.
- Fresh package: `Local/package-20261105T195840Z/receipt.json`. Source identity 8755f4dc816ad7923c6a346ee72b0a696be80ce5d58040a56514d163fbad325f.
- Final packaged controls and full production intro tests pass. The approved eight-shot fortress/mural sequence remains before the encounter, isolates combat/music, then hands back control and starts the chosen soundtrack once.
- Complete victory/restart checks pass: one hand 74.929 game / 75.618 active-wall seconds; two hands 38.781 game / 39.112 active-wall seconds, unchanged 650 HP. Controls/intro/victory screenshots were inspected. Exact evidence: `docs/wrapup-20261105/verification.json`.
- Play profile: canonical knight skin, stable weapon presentation, walk-entry blending and readable auto-lock. The rejected contiguous movement, unfinished sourced movement replacements and experimental threat-camera framing remain disabled. Backlog items are not claimed completed.

## Play installation

The signed Shipping app is installed under `$HOME/Applications/Veyr/<binary-hash>/Veyr-Mac-Shipping.app`. `Local/LatestShipping.json` now points to the installed, verified build; it is no longer stale. `Local/ShippingInstallation.json` records the exact app, source identity and signature/launcher checks.

Use **Play Veyr.app** on the Desktop, linked to `$HOME/Applications/Play Veyr.app`. Its small native launcher starts the existing GPU-guarded Python launcher without opening Terminal. It preserves background/windowed launch and 60 fps limits. Click/Enter in the game to take control; Enter restarts after victory/death. The supplied OST, dedicated dragon effects and single player grunt are preserved.

## Consolidation and ownership

All fetched Veyr branch heads are ancestors of local main, including the knight/game work, dragon authoring, prior cleanup records and main privacy fixes. The same repository was present in two independent clones, not multiple linked temporary worktrees. Both authoring checkouts contain private source assets and are retained. Recent dragon facts are archived in `docs/handoffs/DRAGON-AUTHORING-20261105.md`; full history remains reachable through the merge commits.

The pre-existing deletion of `Local/knight-review-20261028/critique-round2.md` belongs to earlier work and is intentionally left unstaged. Other sessions' processes and checkouts remain untouched. Merge/push verification and final cleanup results are recorded under `docs/wrapup-20261105/`.

## Experimental history retained, not promoted

The inactive v047 trial imported successfully and fixed its exact run-to-stop entry, but its full motion tests remained 0/4. Actual blind Opus preferred the earlier stop and the new sprint carry; neither was shippable. Details: `native-contiguous047-checkpoint.json`, `blind-contiguous047-receipt.json` and the full requirements ledger under `docs/master-goal-20261103`. First-tie Turn180_A v4 remains stopped. Known critic estimates total 25.0463422 USD plus one historical unpriced abort; no new paid work in this wrap-up.

Current and earlier films remain on the bare review page at port 8813. No renderer/encoder job from the cancelled research loop remains active. Only intentional review services and a later owner-play launch may remain running; verify receipts/PIDs before any action. The full unfinished scope remains in BACKLOG.md for a separately authorized future task.

## Final publication and cleanup

Main publication was verified at `53d82603112d`; the final bookkeeping commit follows it. Twelve fully merged inactive remote branches were removed; the two authoring branch references and Unity checkpoint are retained. Nine obsolete build/archive/staging directories were deleted, with approximately 16.277 GiB of measured free-space gain. The installed Shipping app, authoring assets and review films remain. Exact inventories: `docs/wrapup-20261105/consolidation.json` and `cleanup.json`.
