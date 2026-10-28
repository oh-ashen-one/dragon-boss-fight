# HANDOFF — dragon-boss-fight (Can It Code north-star pass)

Date: 2026-10-28 · Branch: `claude-code-enhancements` · Host: Studio (midirstudio) · Status: **WIP, pipeline proven, runtime compile-only; switching to laptop**

## What this is

Replicating Can It Code's boss-fight process (YouTube `z1mgtUvTdqg`, Patreon source pack) on our Veyr dragon so we can
compare it with what we had. The shared-brain package `boss-fight-blueprint` (merged, agents-md PR #27) is the
reusable design; this branch is its first application. Decisions confirmed by Hari: creature motion may come from
AI video of our own rig through video2rig (the explicit exception to source-first animation; the knight stays on
sourced clips); MiniMax H3 Max at 768p was the first provider, Seedance 2.5 approved on 2026-10-28 evening after
MiniMax oversized the wings; one clip at a time, review before the next; merge of PR #27 approved and done; after
that "do whatever you want on your own". Hari was not yet asked for a verdict on the idle or roar clips.

## Repo / branch map

| Repo | Checkout (Studio) | Branch |
|---|---|---|
| oh-ashen-one/dragon-boss-fight (public, renamed from veyr-cinder-warden today) | `/Users/midir/dragon-boss-fight` | `claude-code-enhancements` (off `main` 0755faf, Hari created main from Codex's v030) |
| oh-ashen-one/video2rig (public fork of canitcode/video2rig, AGPL) | `/Users/midir/video2rig` | `mac-mps` (Apple Silicon port + `twins` and `limbs` creature.json settings) |
| oh-ashen-one/agents-md (private shared brain) | `/Users/midir/agents-md` | `main` has the package; draft PRs #30 (sync rebuild fix) and #31 (lessons) await Hari's merge |
| oh-ashen-one/veyr-animation-sources (private backups) | none | release `v2r-dragon-20261028` = this thread's Local/ artifacts |

Other sessions' checkouts on the Studio, do not touch: `/Users/midir/veyr-review-fable-20261021` (holds the dragon
rig source `Local/Blender/dragon-v1-20261021/Dragon_Rig_v008_weightfix.blend` and the hand-keyed idle), Codex's
dated `codex/*` branches. The Patreon pack is at `~/Downloads/BossFight-Unreal-Project` on the Studio only; never
put it in a repo.

## Where things stand

- Pipeline works on this Mac end to end: start picture → clip → check → fit → review → Blender Action → scripted
  refinement → blind A/B. Clip to Action takes about four minutes once a reader exists.
- Idle: refined video2rig idle beats the hand-keyed idle in a blind A/B (47 vs 41); both still fail the shipped bar.
- Roar: landed on Seedance with a half-open-wings prompt (the rig's wings are fanned at rest; 1.27x span is the
  physical limit). Two usable Actions: `Dragon_Idle_v2r_v2.blend`, `Dragon_Roar_sd_v2r_v2.blend`.
- Move data measured from those Actions into `Data/dragon/*.json`; C++ loader and bone hurt capsules compile
  (UBT, editor and Shipping) but nothing is verified in PIE.
- Spend: 107.5 Higgsfield credits (3 MiniMax at 12.5, 2 Seedance at 35).

## What happened this session

- `docs/canitcode-enhancements.md`: plan, gap analysis, rule checks, clip ledger, every A/B and fit number, the
  wing finding, provider costs (commits dc71d2c … 0ae3440).
- `tools/movedata/` + `Data/dragon/`: measured moves, capsules, tempo, sounds (3aa61c3, 6124a05).
- `Unreal/Veyr/Source/Veyr/VeyrMoveData.*`, `VeyrDragonMoveData.cpp`, hooks in `VeyrDragon.*`: data-driven
  windows and capsules, console commands `veyr.MoveData.Dump/Draw/Play`, `veyr.MoveData.HurtBlocksPawn` (6334c7b).
- Fork `video2rig` `mac-mps`: device helper (cuda/mps/cpu), MPS resize workaround, `twins`, `limbs`, docs/MACOS.md.
- Shared brain: `boss-fight-blueprint` package (teardowns, inventory, Apple Silicon reference, Veyr lessons log),
  routing row, creature exception, search keywords; merged as a675572.

## Verification done

- `brain doctor` after the merge: revision a675572, freshness verified, no issues; `brain resolve
  boss-fight-blueprint` and `brain search boss fight` rank the package first.
- `video2rig check` on idle 0.58%, roar_sd2 1.13% (fail line 1.5%); fits with warnings none.
- Two blind Opus critics (videos only); numbers in docs and `Local/ab-idle-20261028/critique*.md`.
- UBT `Build.sh VeyrEditor Mac Development` and Shipping: `Result: Succeeded`, no new warnings.
- `tools/movedata/test_build_moves.py`: 3 passed. Bundle sha256 recorded in the release's SHA256SUMS.

## Not done / explicitly out of scope

- No PIE or packaged run of the data-driven dragon. This clone has no `Content/Characters/Customuse` (native
  character content is not in git; it is in Codex's checkout and the private backups), so capsules cannot bind here.
- Hari has not judged the idle or roar; the owner verdict gates the next clips.
- Idle gap: no head intent (one breathing sine); needs an 8 s clip or a second "look" clip layered in Blender.
- Roar: does not return to stance (engine blend into idle needed); tail whip still a spike; v3 hand-flare end pose
  differs from start.
- First post-merge shared-brain release lacks search keywords until PR #30 merges and a `brain sync --force
  --strict` runs; mandatory routing row works regardless.
- Remaining clips (claw swipe, bite, stagger, collapse, death, takeoff, land), the brain by reach, fight-feel
  system, lab flags, Niagara, Lumen/VSM defaults: not started.
- `Local/ab-idle-20261028/frames/` (PNG frame sets) and `Local/video2rig/dragon/reader/renders/` were left out of
  the bundle; they regenerate.

## Next steps

1. On the laptop: restore the bundle (below), then `brain sync --force --strict` once PR #30 is merged.
2. Owner verdict on idle and roar (page: `Local/ab-idle-20261028/serve/index.html`, or the Downloads copies).
3. Engine session on the Studio with the native content: bind capsules (`veyr.MoveData.Draw 1`), import the two
   Actions, rerun the collision and stance trials, fix the 18 cm rest-pose float in the import offset.
4. Next clip (claw swipe) on Seedance with the gesture described inside the rig's reach; same check/fit/refine/A/B.
5. Promote `Local/video2rig/dragon/refine/` scripts into `tools/` or the fork so the refinement is reusable.

## Key files

- `docs/canitcode-enhancements.md` — the full record: plan, ledger, numbers, lessons, provider finding.
- `tools/movedata/README.md` — move-data schema, units, commands, thresholds.
- `Data/dragon/moves.json`, `boxes.json` — measured windows and capsules at game scale (x21.56).
- `Unreal/Veyr/Source/Veyr/VeyrMoveData.h` — loader structs mirroring the blueprint's contract.
- `Local/video2rig/dragon/creature.json` — root, facing, hinges, `twins`, `limbs`, wing wrist range (restored from bundle).
- `Local/video2rig/dragon/clips/*.prompt.txt` and `*.json` — prompts and provenance per clip.
- `Local/ab-idle-20261028/critique.md`, `critique-round2.md` — blind critic reports; `private/mapping.json` — labels.

## How to run it

```bash
# restore artifacts (laptop): private release asset, ~540 MB
cd ~/dragon-boss-fight && mkdir -p Local && cd Local
gh release download v2r-dragon-20261028 -R oh-ashen-one/veyr-animation-sources -p 'veyr-v2r-dragon-20261028.tar.gz' -p SHA256SUMS
shasum -a 256 -c SHA256SUMS && mkdir -p restore && tar -xzf veyr-v2r-dragon-20261028.tar.gz -C restore
mkdir -p video2rig ab-idle-20261028 && mv restore/dragon video2rig/dragon && mv restore/ab-idle/* ab-idle-20261028/ && mv restore/movedata movedata

# video2rig fork (Apple Silicon)
git clone -b mac-mps https://github.com/oh-ashen-one/video2rig.git ~/video2rig && cd ~/video2rig
python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt torch torchvision
export V2R_BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
P=~/dragon-boss-fight/Local/video2rig/dragon
.venv/bin/python -m video2rig check "$P" roar_sd2 && .venv/bin/python -m video2rig run "$P" roar_sd2 && .venv/bin/python -m video2rig review "$P" roar_sd2

# move data (headless Blender) and tests
cd ~/dragon-boss-fight && bash tools/movedata/run_veyr.sh && python3 -m unittest tools/movedata/test_build_moves.py

# Unreal compile only (Studio)
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" VeyrEditor Mac Development -Project=/Users/midir/dragon-boss-fight/Unreal/Veyr/Veyr.uproject -NoUBA -NoXGE -NoFASTBuild -NoSNDBS -MaxParallelActions=4 -WaitMutex
```

## Running processes / infra

- Studio: before/after page served by Python pid 53126 on port 8790 from `Local/ab-idle-20261028/serve`,
  published to the tailnet with `tailscale serve --tcp 8790` (http://100.95.131.102:8790/). Stop with `kill 53126`
  and `tailscale serve --tcp=8790 off`. Nothing else running for this thread; no LaunchAgents; no engines.

## Picking this up on the other machine

- Branch is pushed to: `origin/claude-code-enhancements` — `git clone -b claude-code-enhancements https://github.com/oh-ashen-one/dragon-boss-fight.git ~/dragon-boss-fight`
- Written on: Studio
- **Local-only, did NOT travel:** the Patreon pack (`~/Downloads/BossFight-Unreal-Project`), the teardown notes
  (`~/canitcode-teardown/`, their content is in the shared-brain package), review frames and reader renders
  (regenerable), the Downloads copies of the videos.
- **Needs rebuilding there:** `~/video2rig/.venv` (torch with MPS), Blender 5.2, ffmpeg; Unreal 5.8 if compiling.
- **Must already exist there:** `gh` auth for oh-ashen-one, Higgsfield MCP for clips, shared brain installed
  (`brain doctor`).
- **Studio-only:** engine sessions with the native Customuse content, GPU-heavy reader training (laptop MPS works but
  slower), the served page.

## Secrets

- None new. Higgsfield is through the MCP connector; no keys in files. `VEYR_BLENDER_OWNER`/`VEYR_BLENDER_WORK`
  are names used by older Blender MCP tooling, not needed for this thread.

## Gotchas

- Generators draw gestures the rig cannot do (wings 2x span); describe moves inside the rig's measured reach.
  `check` does not catch a part that grows; eyeball the peak frame against the start picture.
- Changing the start picture, rig or model means a new reader (about 3 h on the Studio's MPS).
- Tripo rig: Left/Right limb names mean front/hind; wing PosZ sits at -Y; no root motion on `tripo::Root`
  (body travels on `tripo::Spine_0`); rest pose floats 18 cm at game scale.
- Blender scripts must run `--background --factory-startup` or the MCP add-on registers itself into exports.
- Python's stock `http.server` cannot serve byte ranges: Safari will not play the videos; use `rangeserver.py`.
- The Studio's Tailscale app only passes ports published with `tailscale serve`.
- The always-on shared rules file sits at 11,997 of 12,000 bytes; any new route needs a trim first.
- Do not rename rig bones to fix tools: the Unreal skeleton and trained readers are keyed to the names.

## Resume command

```
work out of ~/dragon-boss-fight on branch claude-code-enhancements, read HANDOFF.md, restore the v2r-dragon-20261028 bundle into Local/, pick up at next steps
```
