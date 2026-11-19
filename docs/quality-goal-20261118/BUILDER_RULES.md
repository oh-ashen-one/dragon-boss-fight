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

- Before starting any UnrealBuildTool build (also a compile-check in your own worktree), check that no other
  UnrealBuildTool, `build.py` or `package.py` process is running and wait until none is; use `-WaitMutex`, never
  `-NoMutex`; throttle worktree compile-checks with `-MaxParallelActions=6`.
- **One game or engine process at a time on this machine for this goal, windowless (`-nullrhi`, commandlets, cooks)
  included.** Never run fights in parallel (`--parallel` stays 1). Before any launch, check that no `Veyr-Mac-Shipping`
  or `UnrealEditor` process of ours is running. Your brief says whether you hold the engine; if it does not, you may
  not build, package or launch.
- Rendered launches only through the GPU gate (`run_native.py` / `playtest_suite.py` do this), 60 fps cap, windowed and
  in the background (`open -g`), never fullscreen, never focused.
- **No rendered launch while `~/.cache/gpu-slot/STREAMING` exists** (the owner's 11:00-13:00 ET stream window). Never
  remove that file and never set `GPU_SLOT_STREAMING_SLOTS`. Use that time for code, builds and windowless runs.
- **Never signal a process by name pattern** (`pkill`, `killall`, `pgrep ... | xargs kill`). Other sessions on this
  machine run their own engines and their own `gpu_slot` captures (for example a Unity project). Record the PID of
  every process you start, at launch, and signal only those PIDs after checking `ps -o pid,ppid,command -p <pid>`
  shows it is yours. On 2026-11-18 a builder's broad pattern hit another session's `gpu_slot` capture.
- Own only processes you started. Stop a driver script first, then SIGTERM the game and wait up to 60 s; SIGKILL only
  if it is still alive. Never relaunch automatically after two crashes: stop and report. No tool that raises an OS
  dialog. No computer-use or mouse control.
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
