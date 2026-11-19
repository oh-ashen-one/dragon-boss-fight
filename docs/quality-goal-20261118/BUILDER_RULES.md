# Rules for every builder and critic on the Veyr quality goal

Read this once, fully, before touching anything. The goal itself is `QUALITY_GOAL.md` at the repository root.

## Where things are

- Repository: `/Users/midir/veyr-knight-20261028`, branch `fable/quality-goal-20261118`. Unreal project: `Unreal/Veyr`
  (UE 5.8.3 at `/Users/Shared/Epic Games/UE_5.8`, C++ module `Source/Veyr`).
- Reference game (read-only, never copy its files into our repo; reimplement techniques):
  `/Users/midir/leshy-bossfight-mac` (source `Source/BossFight`, data `Data/`). Its footage and frames:
  `/Users/midir/leshy-reference`. Teardown notes: `/Users/midir/canitcode-teardown/{boss,hero}.md`.
- Baseline playable build of `main` (`79fe0bc`): `/private/tmp/veyr-verified-bundle-2484pvq3/Veyr-Mac-Shipping.app`.
- Tools: `tools/unreal/{build,package,run_native,playtest_suite,mux_film,encode_video,critic_pack,reinstall_shipping}.py`.
  Commands and switches: top of `HANDOFF.md`; numbers and method: `docs/playtest-goal-20261117/RESULTS.md`.
- Shared skills: resolve with `/Users/midir/.config/devin/brain/bin/brain resolve <id>` and read the returned file for
  `operating-rules` (GPU and engine sections), `unreal-engine`, and, for boss or combat work, `boss-fight-blueprint`;
  for animation work `animation-sourcing`.

## Machine and process rules (the owner enforces these)

- **Every build, package, cook, commandlet and game launch holds the engine lock.** It is one machine-wide lock
  (`~/.cache/veyr-engine/lock`, `tools/unreal/engine_lock.py`), so only one game, engine or build process of ours runs at
  a time on this machine, windowless (`-nullrhi`, commandlets, cooks) included, and two builders can take turns
  safely. Start these only through the tools (`build.py`, `package.py`, `run_native.py`, `playtest_suite.py`,
  `play_shipping.py`, `run_polish_import.py`, `open_owned_editor.py`), which take the lock themselves, or through
  `python3 tools/unreal/engine_lock.py --label "<who and why>" -- <command...>`. Never start UnrealBuildTool, `Build.sh`,
  RunUAT, `UnrealEditor`, `UnrealEditor-Cmd` or `Veyr-Mac-Shipping` any other way. If the lock is held you wait in
  the queue (the tool prints who holds it every minute); `engine_lock.py --status` shows the holder. Your brief no longer
  says "you hold the engine": you hold it only while one of your processes runs, so do reading, code and frame review
  between launches, not inside them. A suite takes the lock once per run, not once per suite. Never run fights in
  parallel (`--parallel` stays 1). Do not edit, kill or delete `~/.cache/veyr-engine/`; if a holder looks dead,
  `--status` says so.
  Keep holds short: no single run holds the lock longer than about 6 minutes unless the reason is in your notes file
  (a release after more than 6 minutes is logged as a "long hold" in `~/.cache/veyr-engine/history.jsonl`). Prefer
  cooked, packaged builds over the uncooked editor binary for checks: the editor rebuilds assets while it holds the lock.
- **Bands run as fast sweeps, in few lock holds.** `-VeyrFastSim` (windowless only, fixed 1/60 s steps, about ten times
  real time) with `-VeyrSeedSweep=0-15` runs the 16 band seeds in one launch of about 4-5 minutes:
  `playtest_suite.py --app <app> --run 'victory:headless,-VeyrFastSim,-VeyrSeedSweep=0-15'`, the same with `two-handed`,
  and `--run 'death:headless,-VeyrFastSim,-VeyrSeedSweep=0-3'`; summary with `tools/unreal/band_summary.py --per-seed`.
  A fast sweep is a distribution, not a seed-for-seed replay of real time (measured 2026-11-19 on 4 seeds: median 92.9 s
  fast against 85.0 s real, per-seed results differ), so use it to compare builds (old against new on the same package
  and mode) and for retune loops. The acceptance band of the final integrated build is run once at real time. Never run
  a 32-fight band at real time on a work branch; never more than 4 real-time windowless fights in one lock hold; keep at
  most one ticket in the lock queue at a time.
- **Build in your own worktree.** A builder with a worktree first runs
  `python3 tools/unreal/clone_private_content.py --from /Users/midir/veyr-knight-20261028 --to <your worktree>` (APFS
  clones of the git-ignored Content and Config: Characters, Paragon, ArtPass, some audio; it also seeds
  `Unreal/Veyr/DerivedDataCache`, which you must do before your first run, or the first editor run rebuilds every static
  mesh while holding the lock; no extra disk, `--no-ddc` skips it), then builds and
  packages from its own worktree. Nobody builds or packages in another builder's tree. Throttle compile-checks with `-MaxParallelActions=6`; use `-WaitMutex`, never
  `-NoMutex`.
- Rendered launches only through the GPU gate (`run_native.py` / `playtest_suite.py` do this), 60 fps cap, windowed and
  in the background (`open -g`), never fullscreen, never focused. The ten-rendered-launches-per-hour budget is counted
  across all checkouts of the project (every worktree's receipts plus `~/.cache/veyr-engine/rendered-launches.jsonl`), so
  two builders together stay at ten.
- **No rendered launch while `~/.cache/gpu-slot/STREAMING` exists** (the owner's 11:00-13:00 ET stream window). Never
  remove that file and never set `GPU_SLOT_STREAMING_SLOTS`. Use that time for code, builds and windowless runs.
- **Never signal a process by name pattern** (`pkill`, `killall`, `pgrep ... | xargs kill`). Other sessions on this
  machine run their own engines and their own `gpu_slot` captures (for example a Unity project). Record the PID of
  every process you start, at launch, and signal only those PIDs after checking `ps -o pid,ppid,command -p <pid>`
  shows it is yours. On 2026-11-18 a builder's broad pattern hit another session's `gpu_slot` capture.
- Own only processes you started. Stop a driver script first, then SIGTERM the game and wait up to 60 s; SIGKILL only
  if it is still alive. Never relaunch automatically after two crashes: stop and report. No tool that raises an OS
  dialog. No computer-use or mouse control.
- **Disk.** Every package leaves a 1.7 GB verified bundle in `/private/tmp`, about 3 GB of archives under `Builds/` and
  `Local/package-*`, and (until `package.py` at the goal branch of 2026-11-19 17:35 or later is merged into your branch) a 2.9 GB stage
  folder. On 2026-11-19 at 17:11 ET this filled the data volume and broke a package. After every successful package:
  `python3 tools/unreal/cleanup_packages.py --keep-app <the app you run now> --report Local/cleanup-<stamp>.json --apply`
  from your own worktree, and delete your own raw frame dumps once the film is encoded and checked. Check
  `df -h /System/Volumes/Data` before each package; under 40 GB free, stop and clean your own artefacts first. Only your
  own worktree and your own bundles: never anything of another session.
- Do not delete evidence folders younger than an hour (the launch budget counts their receipts).
- Do not touch other sessions' files, branches, worktrees or processes.

## Work rules

- Every behaviour change sits behind a command-line switch that restores the old behaviour (`-VeyrNo...` or
  `-VeyrLegacy...`), new behaviour on by default. List your switches in your report.
- Fixed by the owner: hitboxes and difficulty (do not retune unless your brief says so), the dragon is never made
  smaller, the 8-shot intro and the music track stay as they are.
- Free store assets only. No paid generation unless your brief names it. Never use Higgsfield.
- Never print, log or commit credential values. Run `gitleaks protect --staged --no-banner` before every commit.
  Character content, raw third-party assets and anything under `Local/` stay out of git (the repo is public).
- Commit small, verified steps on the goal branch and push. End commit messages with the
  co-author line your own session instructions give you (it names the model that actually wrote the change). Never push or merge `main`. Leave the pre-existing
  unstaged deletion of `Local/knight-review-20261028/critique-round2.md` alone.
- Look at your own evidence: open the frames or the film sheet and say what you saw. A passing number with a
  wrong-looking frame is a failure.
- Write progress to the notes file named in your brief at each checkpoint (what was found, what changed, what is
  measured, what is next) so the director can read it while you work.
- Stay inside your brief. If you find something outside it, note it; do not fix it.
- Final report: under 400 words, facts first: what changed (files, switches), what was measured (numbers, paths to
  evidence), what you looked at, what failed or is unverified, commits pushed. Say plainly if a "done when" is not met.
