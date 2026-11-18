# Planning with the owner — 2026-11-18, after the playtest goal closed. NOTHING IS STARTED.

Branch **`fable/owner-feedback-20261118`** (pushed; `main` + backlog and audio-tool commits only, no game code changed).
The whole agreed list is the top block of `BACKLOG.md`. Read it first. The owner is still deciding the plan: **do not
build anything until he says the plan is settled** (he stopped sound work that was started on a "yes").

- **What happened today:** read-only comparison with the reference game (Can It Code's Leshy fight). The owner played
  both. His footage and frames: `~/leshy-reference`; side-by-side page: `Local/playtest-goal-review/vs.html`
  (`python3 serve.py 8823`). The reference game runs on this Mac from `~/leshy-bossfight-mac` (launch line in the wiki
  page `dragon-boss-fight`; Esc quits it).
- **Decided by the owner:** hitboxes and difficulty stay; the dragon gets bigger, never smaller; relight the courtyard
  (the light need not have a visible source); replace the knight with **Paragon: Greystone in the dark gold-trimmed
  skin** (backlog section G); free assets only; Mixamo for animations only; Freesound recordings first for sound,
  Higgsfield or Fish Audio only where no recording fits.
- **Bugs he saw in `79fe0bc`:** foot mesh pinches out on close hits, camera goes inside the dragon, dragon floats about
  3 ft, knock-down must be 5 s at most (backlog section A).
- **Not decided:** the order of work (proposed: bugs, then weight and sound, lighting, knight, dragon animation
  playback); the shield and grip question for Greystone.
- **Paused sound work:** candidates in `Local/AudioSources20261118/`, tools in `tools/audio/` (`freesound_candidates.py`,
  `prepare_recorded_set.py`); `VeyrAudio.cpp` untouched. Analysis tool: `~/.cache/earshot/venv`.
- **Who builds:** the session model (Fable) directs only. Building goes to `opus-builder` / `sonnet-builder`, gates to
  `opus-critic`. Show the owner a clip or an audition page early, compare against the reference footage, one game
  process at a time.
- **Playable build of `79fe0bc`:** `/private/tmp/veyr-verified-bundle-2484pvq3/Veyr-Mac-Shipping.app` (not installed;
  gone after a reboot, re-package from `main`). Launch: `python3 tools/unreal/play_shipping.py --app <that app>`. The
  GPU gate opens no slot between 11:00 and 13:00 ET while `~/.cache/gpu-slot/STREAMING` exists.

# Playtest goal — closed by the owner on 2026-11-18, merged into `main`

Goal file: `PLAYTEST_GOAL.md`. Numbers, reviews and open items: `docs/playtest-goal-20261117/RESULTS.md`.
Session model: Fable 5.2. Critics: `opus-critic` (Opus 5.5 high).

**Read this first.** The owner watched the before/after films and said: "The before and after isn't really that crazy.
It looks more the same." The goal was marked complete "for now", not accepted. Do not resume it without a new brief.

## State

- `main` holds all of the source below. Nothing new is installed: **Play Veyr.app still launches the 2026-11-06 build**
  (`~/Applications/Veyr/652188ae51a3/`). The last package of this run (build 18, source `e9fcb8a`) was deleted in
  clean-up; re-package from `main` to get it back. Its rendered regression and 16-seed numbers were never completed.
- Knight content `v050heal` (heal fit v11) is active locally and is not in the repository (character content is ignored).

## Defaults now, and the switch that restores the old behaviour

| Change | Default now | Restore switch |
|---|---|---|
| Floor rings | hidden | `-VeyrFloorTelegraph` |
| Scale | 2x (idle head 1546 cm; knight 244 cm) | `-VeyrDragonScale=1` |
| Pace | knight and dragon travel 1.3x | `-VeyrLegacyPace` |
| Brain | reach-based random choice, snap tracking, strings, whiff punish, anti-camp takeoff, fire aim | `-VeyrLegacyBrain` |
| Health | 845 | `-VeyrBossHealth=650` |
| Knight foot clean-up | on | `-VeyrNoStanceCleanup` |
| One-hand chain flow | on (not reviewed in its final form) | `-VeyrNoChainFlow` |
| Flight camera framing | on | `-VeyrNoFlightFraming` |
| Near-boss camera framing | off | `-VeyrBossNearFraming` turns it on |

Other switches: `-VeyrBrainSeed=N` (replays default to 20261117; normal play seeds from the clock), `-VeyrBrainMap`,
`-VeyrStillInterval=N`, `-VeyrFilmIntro`, `-VeyrDeathFar`.

## How to build and test

```
python3 tools/unreal/build.py --engine "/Users/Shared/Epic Games/UE_5.8" --target VeyrEditor --configuration Development
python3 tools/unreal/package.py --engine "/Users/Shared/Epic Games/UE_5.8" --configuration Shipping
python3 tools/unreal/playtest_suite.py --app <app from the newest Local/package-*/receipt.json> --run camp --run death --run victory --run victory:two-handed
python3 tools/unreal/reinstall_shipping.py --receipt <receipt.json> --suite <Local/playtest-suite-*.json> --verification docs/playtest-goal-20261117/RESULTS.md
```

- Add `headless` to a run (`victory:headless,-VeyrBrainSeed=3`) for a numbers-only run with no window and no GPU slot.
  **Each headless run is still a full game process and shows as a running app. The owner objected to 8 at once on
  2026-11-18: run them one at a time unless told otherwise.**
- Do not edit source while `build.py` runs (it checks a source hash), and do not delete evidence younger than an hour
  (the launch budget counts its receipts).
- `mux_film.py <run> --output <mp4>` joins a filmed run with its game audio; `critic_pack.py` builds blind A/B packs.

## Findings worth keeping

- The run clip's authored speed is 822.8 cm/s and the knight sprinted at 580, so it played at 0.70x.
- At 2x, claw and tail swings passed over the knight's head and the fire passed over him entirely; both are corrected.
- Fight outcomes are chaotic per seed. Judge balance on 16 seeds per grip, never on one run.
- The scripted player is frame-perfect, so it understates how often a person is hit.
- Camera at 2x is the weakest part: from under the dragon the wind-ups cannot be read and the camera clips into the body.

## Open

See "Open at close" in `docs/playtest-goal-20261117/RESULTS.md`.

---

# Opus 5.5 final enhancements — branch `opus-5.5-final-enhancements` (2026-11-05)

- **Video2rig bite, end to end (opt-in `-VeyrVideoBite`, awaiting owner visual review).** Existing Seedance bite → video2rig fit → Blender cut/retime (2.47 s, body lunge kept, jaw snap) → canonical export → native DragonV3B `v034videobite` (300 poses, 0 failures; RuntimePolish/DA_Dragon promoted, keyed Bite retained) → Shipping `Local/package-20261106T001217Z`. Before/after showcase runs on that one app both PASS 20/20. Review page `Local/bite-review-20261105/serve/` on port 8814 (task-owned server). Details and exact evidence: `docs/video-bite-20261105.md`.
- **Overnight results: `docs/overnight-v2r-20261105/RESULTS.md` (default video2rig moves + raised-wing idle; victory gate regression 316 s vs 79.8 s legacy).**
- **Overnight pass (2026-11-05/06, owner asleep, full autonomy; plan `docs/overnight-v2r-20261105/PLAN.md`).** Video2rig clips are named `<Clip>V2r` and play by default; `-VeyrLegacyDragon` restores keyed clips. Native versions: `v035videomoves` (Claw0/1, Buckle0/1, Collapse, Exposed loop, Tail, Stomp2/3; 414 poses, 0 failures) and `v036idlewings` (IdleOpenV2r: video2rig idle with raised, spread wings, replacing the crumpled folded idle the owner flagged). Attack durations now follow V2r clips. Tools: `tools/dragon_refine/{cut_v2r_move,mirror_v2r_action,probe_v2r_points,probe_wing_spread}.py`, `tools/unreal/prepare_video_moves_plan.py`, live dashboard `tools/dragon_refine/dashboard.py` (port 8815, serves `Local/bite-review-20261105/overnight-serve`). Credits 315/420 (ledger `Local/video2rig/dragon/clips/ledger-20261105.json`). Remaining: fire_r2 `f25440b6`, walk_r2 `8cba6700`, hind_stagger_r2 `aa4ea1cd` (fit + cut), turn (fit done, needs root-yaw samples), rise needs a lying start picture + reader, victory/core regression, blind review.
- **Current state for the next session (2026-11-06 ~15:58 ET):**
  - Merged and pushed to `main` (and `opus-5.5-final-enhancements`); latest verified Shipping app `/private/tmp/veyr-verified-bundle-ikoo510e/Veyr-Mac-Shipping.app` and installed playable app `/Users/midir/Applications/Veyr/652188ae51a3/Veyr-Mac-Shipping.app` (`Local/LatestShipping.json`, receipt `Local/package-20261106T204452Z/receipt.json`, source ID `cc945b5cb63bf38ce91db44f0a2d43de2373d8bbc91b245af2719bc5fc372618`). Active DragonV3B plan: `Local/CustomuseAssets/Polish20261025/videomoves-v040complete/` (chain v035→v036→v037→v038→v039→v040complete, all native pose checks passed).
  - **All 12 video2rig dragon move families (`<Clip>V2r`) are natively imported and default in game**: `IdleOpenV2r` (raised-wing fix), `BiteV2r`, `Claw0V2r`/`Claw1V2r`, `TailV2r`, `Stomp2V2r`/`Stomp3V2r`, `FireV2r`, `TurnLeftV2r` (87.5° stretch; actor turns by the clip's own root yaw samples, `root_motion_removed: true`), `WalkV2r` (`160 cm/s`, re-centered `tripo__Spine_0`), front-leg buckles (`Buckle0V2r`, `Buckle1V2r`), hind-leg buckles (`Buckle2V2r`, `Buckle3V2r`), `CollapseV2r`, `ExposedV2r`, and `RiseV2r`. `-VeyrLegacyDragon` restores all keyed clips; `-VeyrLegacyClips=Prefix,...` restores individual prefixes.
  - **Step 1 completed (victory test + opening balance pass):** Restored post-recovery (`FMath::Max(1.25f, 3.60f - RecoveryDuration)`) and post-reposition (`1.25f`) `Idle` windows when V2r clips are active (`!bLegacyDragon`) so the knight can finish `RunStop` + lock-on turn before the next windup.
  - **Step 2 completed (`WalkV2r` default + framing/sliding fix):** Lowered `WalkV2r` effective nominal speed from `428 cm/s` to `160 cm/s` (`218.7 cm` cycle travel), synced `WalkV2r` sampling to `WalkPhase * Duration`, re-centered `WalkV2r`'s baked `tripo__Spine_0` frame-51 offset (`+12.44, -38.99, 0` in bone space = `921 cm` in world space) to match `IdleOpenV2r`, and made `WalkV2r` the default.
  - **Step 3 & Step 4 completed (`Buckle0..3V2r`, `CollapseV2r`, `ExposedV2r`, and `RiseV2r` default in `v040complete`):** Fitted `hind_stagger.mp4` (`4.53 px` miss) → cut `Buckle3V2r` (`1.17 s`) + Y-mirrored `Buckle2V2r`, and fitted `rise_lying.mp4` (`5.85 px` miss against lying start rig from `CollapseV2r` end pose) → cut `RiseV2r` (`2.30 s`), exported canonical GLBs, and natively imported/activated `DragonV3B` `v040complete`. With all 12 move families active by default, **scripted victory passes in `70.062 s` game / `70.743 s` wall** (`Evidence/native-victory-20261106T204717Z`, limit `150 s`, `riseObserved: true`, `riseCompleted: true`, `warningContainmentFailures: 0`) and **showcase passes `20/20` chapters** (`Evidence/native-showcase-20261106T204922Z`, all frames inspected).
  - **Step 5 & Cleanup completed (blind Opus review, live dashboard `12/12`, and `30.7 GiB` disk cleanup):** Blind Opus review (`docs/overnight-v2r-20261105/BLIND_REVIEW.md`) scored **10/10 wins for `video2rig`**. Encoded all before/after `.mp4` clips (`stagger0..3`, `rise`, `walk`, `collapse`, etc.) into `Local/bite-review-20261105/overnight-serve/` and updated `status.json` (`12/12` moves `"done, default"`, served on `http://127.0.0.1:8815`). Pruned superseded builds, old saves (`Saved/Autosaves`, `Saved/ShaderDebugInfo`, `Saved/Cooked`), and obsolete Oct/Nov checkouts (`+30.7 GiB` reclaimed, `37 GiB` free).
- **Next steps:** Review the 12/12 before/after comparisons on `http://127.0.0.1:8815` and playtest via `Play Veyr.app`. When ready to start the 6-item playtest difficulty/scale backlog below, branch from `main`.
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
