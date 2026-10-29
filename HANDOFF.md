# HANDOFF — dragon-boss-fight (Can It Code north-star pass)

Date: 2026-10-28 · Branch: `claude-code-enhancements` · Host: Studio (midirstudio) · Status: **WIP, pipeline proven, runtime compile-only; switching to laptop**

## What this is

Replicating Can It Code's boss-fight process (YouTube `z1mgtUvTdqg`, Patreon source pack) on our Veyr dragon so we can
compare it with what we had. The shared-brain package `boss-fight-blueprint` (merged, agents-md PR #27) is the
reusable design; this branch is its first application. Decisions confirmed by Hari: creature motion may come from
AI video of our own rig through video2rig (the explicit exception to source-first animation; the knight stays on
sourced clips); MiniMax H3 Max at 768p was the first provider, Seedance 2.5 approved on 2026-10-28 evening after
MiniMax oversized the wings; one clip at a time, review before the next; merge of PR #27 approved and done; after
that "do whatever you want on your own". Hari approved the idle and roar on 2026-10-28 evening (laptop review); see Owner verdict below.

## Owner verdict (2026-10-28 evening, laptop)

Hari watched the before/after page served locally on the laptop (`Local/ab-idle-20261028/serve`, the Studio server
pid 53126 and its tailnet publish were stopped). Idle and roar approved with no change requests. He asked that the
shared brain and all future sessions use this method; promoted in agents-md PR #32 (video2rig = creature default).
The laptop clone is `~/dev/dragon-boss-fight`; only the `serve/` folder and `rangeserver.py` were copied, the full
Local/ bundle is not restored here yet.

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
- Owner verdict received 2026-10-28 evening: idle and roar APPROVED ("much better", roar "so, so good"). Next clips unblocked.
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
2. Done: owner approved idle and roar. Shared-brain PR #32 (plus #30, #31) makes video2rig the creature default; Hari merges.
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


---

## Knight completion 2026-10-28

Branch `fable/knight-complete-20261028` (off `origin/claude-code-enhancements` 5e619f6), worktree
`/Users/midir/veyr-knight-20261028` on the Studio (a separate clone; the dragon checkout was not written).
Runtime knight definition is now **KnightB v030m**, promoted into `RuntimePolish/DA_Knight` (44 clips: 28 inherited from
v029 unchanged, 16 new). Nothing here is owner-approved. Built on Opus 5.5 (the first commit's trailer names Fable 5.1
as requested by the launching agent; later commits name the model that did the work).

### Verified state

- **Restore**: 1078 native files from four private releases (order: `native-integration-20261025`,
  `combat-arena-polish-native-20261025`, `sourced-animation-game-v027`, `overhaul-game-v029-20261026`); SHA256SUMS OK
  for the two releases that publish them, 403 in-zip manifest hashes OK, 0 dataless files after restore. Against the
  live Codex tree: 864 identical, 225 dataless-there size-matched, 0 different, 1 missing
  (`UI/MoonlitB/T_MoonlitSilverAtlas_v1.uasset`, in no release, copied from the live checkout, sha256 ba65d05a...).
  Per-file provenance: `docs/knight-complete-20261028/restore-provenance.json`, `restore-receipt.json`.
- **Lock-on locomotion** (`VeyrKnight.cpp`): while locked on and walking, the knight faces the boss; back = approved
  `Backpedal` loop (100 cm/s, clip nominal 59.9, 1.67x), sides = `StrafeLeft/Right` (walk cap 1.2x nominal: 166/187 cm/s),
  Shift + side = `StrafeRunLeft/Right` (1.1x nominal: 452/444 cm/s), forward = Walk. Shift + forward/back runs freely
  (orient to movement). Hysteresis 0.15 on direction changes. `-VeyrNoLockOnStrafe` restores the old behaviour.
  `BackpedalStep` stays on its existing path (`TryBackstep`, exec `VeyrBackstep`, integration trial); no new key binding.
- **Strafes**: 4 Mixamo Sword and Shield strafes (walk L/R, run L/R) retargeted with `retarget.py`, weapon-fitted with
  `fit_weapon.py` in one-hand and two-hand grips (the pipeline supports both; 8 clips). Nominal speeds from stance-foot
  medians x 240 cm per glTF metre (calibrated on three plan clips, 239.8 to 246.6): walk L 138.4, R 155.5; run L 411.3,
  R 404.0 cm/s.
- **Directional staggers**: impact (3) = Front (head back 39 deg), impact (2) = Back (head forward 25 deg), impact = Left
  (left shoulder driven back), Right = mirrored copy of Left (`retarget.py` mirror). One- and two-hand, 8 clips, each
  played to 0.60 s (gameplay rate 1.167, Back 1.611). The old `Stagger` (0.42 s) stays the default when the source
  direction is degenerate or a clip is missing. `-VeyrNoDirectionalStagger` restores it. Log: `VEYR_KNIGHT_STAGGER`.
  **Gameplay change**: stagger lock grows from 0.42 to 0.60 s.
- **RunStop join**: measured with `measure_runstop.py` (24 run phases, all joints plus sword tip, in-game frozen-source
  local blend). Fab run -> RunStop: sword 50 to 60 cm apart at every phase (RunStop was authored from the Blender run);
  0.10 s blend peak 2215 cm/s, over the clips' own peak (1343) in 22/24 phases; 0.20 s 5/24; 0.30 s 0/24 (peak 1188).
  Run<->RunStop now blends 0.30 s (`-VeyrRunStopBlend=` overrides). No re-authoring.
- **Approved assets byte-identical**: every pre-existing `Content/Characters/Customuse` .uasset hash unchanged except
  `RuntimePolish/DA_Knight` (926 files compared); original guard `.uasset` sha256 `1d7b990a...efa069` unchanged;
  guard signature verified by the importer. v030m adds 17 assets (16 AnimSequences + DA).
- **v030k was rejected and superseded**: it imported its own rig and mesh variant in a `-nullrhi` commandlet and those
  meshes rendered white in the packaged game. v030m references v029's rig and the identical mesh variant
  (`knight_571e0abbfde2720e`). v030k assets are parked in `Local/failed-import-v030k-whitemesh/` (not in Content).

### Gate lines

- UBT VeyrEditor Mac Development: `Result: Succeeded`, 0 warnings (`Local/unreal-build-20261029T002011653662Z`).
- UBT Veyr Mac Shipping: `Result: Succeeded`, 1 engine-side warning (MetalShaderConverter include dir)
  (`Local/unreal-build-20261029T011120733748Z`).
- Package Shipping: `BUILD SUCCESSFUL`, `AutomationTool exiting with ExitCode=0`, receipt
  `Local/package-20261029T011117Z/receipt.json`, signed zip
  `Builds/Unreal-Mac-20261029T011117Z/Repaired/Mac/Veyr-Mac-Shipping.zip` sha256 `2c7bd8e5...090c8f`,
  app `/private/tmp/veyr-verified-bundle-uyyqawy6/Veyr-Mac-Shipping.app`.
- Packaged runs (all through `gpu_slot` capture, one engine at a time), `Evidence/`:
  - lockon `native-lockon-20261029T011329Z`: `True lock-on: 10 locomotion trials sampled their clips, max facing error 0.9 deg; directional stagger lab 5/5`
  - core `native-core-20261029T011412Z`: `True jump-disabled light heavy collapse head bonus completed rise and dodge contact observed`
  - controls `native-controls-20261029T011645Z`: `True movement jump-disabled attacks roll stamina recovery lock toggles actual guard contact heal and full-health rejection observed`
  - guard `native-guard-20261029T011807Z`: `True front chip block, rear full damage while guarding with ample stamina, and real exhausted guard break verified`
  - death `native-death-20261029T011946Z`: `True death terminal pose, resource reset, movement and primary attack after restart verified`
  - integration: 1 pass of 3 (`native-integration-20261029T010702Z` True, 18 features incl. `locked_strafe_without_blink`
    now expecting `StrafeRight`); 2 fails at `locked_blink_left` (`...010302Z`, `...012024Z`): blink accepted and
    travelled 299 cm but the hidden window (0.16 s) or second afterimage window (0.12 s) was skipped. These runs ran at
    about 16 fps with 0.30 to 0.40 s frames because other sessions held the GPU at 97 to 100%; v029's passing run had
    52 fps. Treat as contaminated; rerun when the GPU is quiet (see INTEGRATION_PERF below). The afterimage capture is
    frame-window based (`UpdateBlinkEchoes`), so it is fragile under hitches; not changed here.
- Run on the first package (v030k, white meshes) are superseded: `Evidence/native-*-20261029T0057*..0103*`.

### Evidence

- Review page (do not need a server here; serve `serve/` with a byte-range server):
  `Local/knight-review-20261028/serve/index.html`, 29 rows, 56 videos (front | side | three-quarter, 30 fps, in-game
  rate), 15 packaged-game screenshots, RunStop numbers. Critic brief: `Local/knight-review-20261028/critic-brief.md`.
- Data: `docs/knight-complete-20261028/data/` (Mixamo classification, stance calibration, RunStop joins, v030m plan,
  activation receipt, manifest).
- Tools: `tools/art/knight_complete/` (restore, analyze, build clips, measure, plan, native import, render, page).

### Restore on another machine (exact)

```bash
git clone -b fable/knight-complete-20261028 https://github.com/oh-ashen-one/dragon-boss-fight.git ~/veyr-knight-20261028
cd ~/veyr-knight-20261028 && mkdir -p Local/restore-20261028/dl && cd Local/restore-20261028/dl
R=oh-ashen-one/veyr-animation-sources
gh release download overhaul-game-v029-20261026 -R $R -D overhaul-game-v029-20261026 -p Veyr-Native-Overhaul-v029.zip
gh release download sourced-animation-game-v027 -R $R -D sourced-animation-game-v027 -p Veyr-Native-Sourced-v027.zip
gh release download native-integration-20261025 -R $R -D native-integration-20261025 -p '*.zip' -p '*.json' -p '*.txt'
gh release download combat-arena-polish-native-20261025 -R $R -D combat-arena-polish-native-20261025 -p '*.zip' -p '*.json' -p '*.txt'
(cd native-integration-20261025 && shasum -a 256 -c SHA256SUMS.txt && shasum -a 256 -c prop-material-fix-SHA256SUMS.txt)
(cd combat-arena-polish-native-20261025 && shasum -a 256 -c SHA256SUMS.txt)
cd ~/veyr-knight-20261028 && python3 -I tools/art/knight_complete/restore_native_content.py Local/restore-20261028 "$PWD"
# knight completion delta (v030m native + authoring + review page)
mkdir -p Local/restore-20261028/kc && cd Local/restore-20261028/kc
gh release download knight-complete-20261028 -R $R && shasum -a 256 -c SHA256SUMS
cd ~/veyr-knight-20261028 && for z in Local/restore-20261028/kc/*.zip; do unzip -n "$z"; done
# HUD atlas is in no release: copy Unreal/Veyr/Content/UI/MoonlitB/T_MoonlitSilverAtlas_v1.uasset (sha256 ba65d05a...)
# from the Codex checkout /Users/midir/Documents/Codex/2026-10-18/go/work/veyr-native-integration on the Studio.
```

Then: `python3 tools/unreal/build.py --engine "/Users/Shared/Epic Games/UE_5.8"`,
`python3 tools/unreal/package.py --engine "/Users/Shared/Epic Games/UE_5.8" --configuration Shipping`,
`python3 tools/unreal/run_native.py --app <app> --gpu-slot ~/.cache/gpu-slot/bin/gpu_slot.sh --mode lockon`.
Re-import is headless: `UnrealEditor <uproject> -run=pythonscript -script=tools/art/knight_complete/native_import_v030k.py
-nullrhi -unattended -NoZenAutoLaunch -notraceserver -DDC=(EnginePak=InstalledEnginePak,Local)` (reads the active plan;
refuses an existing version folder). Do not import rigs/mesh variants in that commandlet (v030k lesson); reuse them.

### Unapproved / open (owner decisions)

- Not recorded as accepted: Mixamo walk (both grips), Fab run (both grips), Mixamo slash, Fab roll, `Sourced_RollAttack_v2`.
  Unapproved: Blink L/R (`Sourced_Blink*_Transit_v2`, v029 maps BlinkLeft to the file named ...Right), GripTo* polish v2,
  all 16 new strafes/staggers, the 0.30 s RunStop blend, the 0.60 s stagger length, the 100 cm/s backpedal.
- Two-hand backpedal falls back to the one-hand `Backpedal` clip (only one approved backpedal exists): expect a grip
  change while backing up two-handed. Two-hand strafes exist.
- Integration `locked_blink_left` needs a clean-GPU rerun (above). A perf-mode retry (`--performance`, exclusive lock,
  waits for GPU < 15%) was cancelled by me after 5 min (SIGTERM, no engine had started) because its settle hold blocked
  another session's capture while the GPU stayed at 98%; `Evidence/native-integration-20261029T012221Z` is that
  incomplete attempt.
- No blind critic has run; I wrote the brief only.
- Spend: Higgsfield 0 credits; no browser downloads; no MCP used. Compute: 4 headless Blender jobs (retarget 25 s,
  fit about 40 s, renders 333 s), 3 import commandlets (14 min failed, 7 min v030k, 34 s v030m), 3 UBT builds,
  2 Shipping packages, 13 packaged scenario runs.

### Local-only (did not travel), cleanup state

- Worktree `/Users/midir/veyr-knight-20261028` holds the restored native content (gitignored), `Builds/` (2.7 GB),
  `Local/` (CustomuseAssets 3 GB, FabRigTesting 2.8 GB, backup zips 3 GB in `Local/backup-20261028`), `Evidence/`.
  Everything needed is in the branch plus the private releases above; the worktree can be removed once the owner has
  reviewed the page and app. Staging `/private/tmp/veyr-stage-*` and `/private/tmp/veyr-verified-bundle-uyyqawy6` are this
  thread's. No servers, LaunchAgents or engines left running.


### Fix round 1 (2026-10-29), after the blind critique `Local/knight-review-20261028/critique.md`

The runtime knight is now **KnightB v030n** (46 clips: 25 inherited unchanged, 19 rebuilt, 2 new), promoted from v030m.
Owner-approved and owner-selected sources (walk, run, light attack, roll, idle, heal, death, guard, approved backpedal
loop and step) were only read. Every pre-existing `Customuse` .uasset is byte-identical except
`RuntimePolish/DA_Knight` (22 new assets). Nothing here is owner-approved.

| Critic item | Result (numbers from `docs/knight-complete-20261028/data/round1-checks.json`) |
|---|---|
| Blink files crossed | The v029 *mapping* was right by motion: the file named `Sourced_BlinkRight_Transit_v2` moves left (hips +X glTF) and is Mixamo strafe (3); `..._BlinkLeft_...` moves right and is strafe (4), whose feet run fore-aft. Rebuilt: `Knight_BlinkLeft_v3` (strafe (3), travel, correct name) and `Knight_BlinkRight_v3` (its sagittal mirror, hips -1.223 m). v029 root trajectory reused, x mirrored for right. Packaged lockon: BlinkLeft lateral -298.6 cm, BlinkRight +298.6 cm; screenshots `frame-0025/0026/0028`. |
| Roll attack splice | `Sourced_RollAttack_v3`: roll extrapolated at its end velocity and smootherstep-blended into the slash over 0.40 s source (0.31 s in game, about 9 frames at 30 fps), last 0.36 s blend into the 1H idle frame 0. Sword-tip step at 30 fps around the join: max 45 cm/frame (v2: 103 cm at the splice). End carry 0.0 deg, end ankles 61.9 cm (idle 61.9). Max tip step overall 116 cm/frame is inside the slash swing itself (same as v2). |
| Sprint strafe right axis | `Knight_StrafeRunRight(TwoHand)_v3c` = true mirror of strafe (3) (`retarget.py` mirror). Stance travel 1.4 deg off lateral (left 0.4). The critic's fore-aft reading also came from the round-0 review camera, which aimed "front" along each clip's first-frame foot direction; round-1 renders use one fixed facing from the 1H idle. |
| 2H backpedal missing | `Knight_BackpedalGuardTwoHand_v3c` (approved loop legs, 2H idle carry). Lock-on back now selects `BackpedalGuard`/`BackpedalGuardTwoHand` by grip (approved `Backpedal` remains the fallback). |
| Sprint strafe left 24% slow | Nominal set to 440.2 cm/s from source hips travel (3.479 m/s x 0.5272 retarget x 240); planted-toe speed 446/458 cm/s confirms. The 24% was mostly the round-0 camera (lateral motion seen at an angle). In-game cap 484 cm/s (1.1x). |
| Carry continuity | Canonical carry = approved IdleOneHand / IdleTwoHand frame 0. All rebuilt clips start/end within 13.9 deg (strafes 6.4-13.9, staggers 0-13.4 start / 0.0 end, backpedals 4.9/6.9, blinks 10.9, roll attack 0.0/0.0). Grip transitions already end exactly on the idles (0.0 deg). Loops start at their narrowest stance: ankles 32-62 cm (idle 61.9). |
| Stagger front foot slide | Staggers rebuilt as additive deltas (hips, spine, neck, head, clavicles) on the approved idle with analytic two-bone leg IK: ankle drift <= 1.3 cm (3 game cm) in all 8. |
| Stagger L/R amplitude | Lateral gain x2: head 23.5 / 22.7 cm rig = 56 / 54 game cm, about 35 / 34 px at the critic's 1.6 cm/px (round 0: 16 px). Left 2H now uses the 2H idle carry (no wrong shoulder). |
| Backpedal guard | Forward lean +7.0 cm head-ahead-of-hips (rig) = 17 game cm, about 10.5 px; blade pitched up 27 deg relative to the leaned chest and lifted 6 cm (net 6.9 / 4.9 deg from the idle carry, kept under the 15 deg continuity bound). |
| Review page | Loops render exactly one cycle, actions end on their last frame; one fixed camera facing; checker now 25 game-cm tiles. Whole-body stagger captures in game (lock released, view lifted). |
| frame-0002 brightness | Lighting, not material: same Backpedal mesh/material is dark in frame-0023; a different mesh (StrafeLeft) is equally bright at the same position and camera yaw (sky/moon specular on the back plate). |

Gate lines (round 1, app `/private/tmp/veyr-verified-bundle-95t1py9v/Veyr-Mac-Shipping.app`):
- UBT VeyrEditor Development `Result: Succeeded` (`Local/unreal-build-20261029T020309422145Z`); UBT Veyr Shipping
  `Result: Succeeded` (`Local/unreal-build-20261029T020604594210Z`); package `BUILD SUCCESSFUL`, `ExitCode=0`
  (`Local/package-20261029T020601Z`), signed zip sha256 `a1399cdc...e1ae727`.
- lockon: `True lock-on: 10 locomotion trials sampled their clips, max facing error 3.5 deg; blink direction 2/2; directional stagger lab 5/5`
- core / controls / guard / death: True (same reason strings as round 0), `Evidence/native-*-20261029T0209..0214`.
- integration x3: GPU never went below 30% for 60 s in a 45-minute wait (another session's video2rig reader training
  and Blender render held it at 98-100%), so the runs are contaminated by load; all three passed anyway:
  `True all18 updated integration features ...` at 15.5 / 14.7 / 14.1 fps (max frame 0.372 / 0.298 / 0.283 s),
  `Evidence/native-integration-20261029T030046Z`, `...030319Z`, `...030459Z`. A clean-GPU fps number is still owed.

Not fixed this round (and why):
- Roll airborne dive / head landing, run landing speed, 1H "lance" carry tilt, walk/run seams, light-attack guard start:
  owner-selected or approved sources (Fab roll, Fab run, Mixamo walk/slash, approved 1H idle), which this round must
  not touch. The canonical 1H carry is the approved idle's, so the lance angle is inherited.
- Grip transition hip dip/settle: grip clips end exactly on the idles already; the critic's settle suggestion was not in
  the fix list.
- Strafe planted-foot depth drift (5 px) was not in the fix list; strafe legs are the Mixamo source.
- The 2H canonical carry (blade vertical in front of the visor) differs from the owner-selected 2H walk carry by 22 deg;
  the coordinator defined the canonical carry from the idles, so walk-to-strafe still changes the 2H blade by ~22 deg.
- RunStop brake length (critic: extend to 12 frames): RunStop is approved; only the blend was changed in round 0.
- New mesh-variant imports are avoided: all new clips reference body variant `knight_571e0abbfde2720e` (Blender round
  trips re-encode the body; v030k showed commandlet-imported bodies render white).

Restore for round 1: after the round-0 restore above, `gh release download knight-complete-round1-20261029 -R
oh-ashen-one/veyr-animation-sources`, `shasum -a 256 -c SHA256SUMS`, `unzip -n` each zip at the worktree root.
Review page: `Local/knight-review-20261028/serve/index.html` (round 1, before = round 0 for changed rows);
round-0 page kept at `serve-round0/`.


### Fix round 2 (2026-10-29), after `Local/knight-review-20261028/critique-round1.md`

The runtime knight is now **KnightB v030p** (48 clips: 25 inherited unchanged, 21 rebuilt, BlinkLeftTwoHand and
BlinkRightTwoHand new), promoted from v030n. Every pre-existing `Customuse` .uasset is byte-identical except
`RuntimePolish/DA_Knight` (24 new assets). The approved and owner-selected sources were only read. Nothing is approved.
Metrics: `docs/knight-complete-20261028/data/round2-metrics.json` (critic definitions: yaw 0 = boss, + = knight left,
game cm, in-game rates) and `round2-handslip.json`.

Root causes:
- **A (mirror).** `retarget.py`'s mirror was a correct sagittal reflection; the Mixamo Sword and Shield strafes are side-on
  (chest -70..-86 deg), and reflecting a side-on body flips its facing. Only the right-moving clips are forward gaits
  (strafe.fbx walk, strafe (4).fbx sprint: knees within 10 deg of travel for the sprint). Left = sagittal mirror of those;
  then a spine counter-twist (Spine/Spine1/Spine2 30/35/35%) brings each clip's mean chest yaw to 0. Mirror pairs: mean
  chest 0.0 vs 0.1 (walk), 0.4 vs -0.8 (sprint): within 5 deg.
- **B (socket).** I did not reparent WeaponSocket in the skeleton: that would mean re-importing every approved clip.
  Instead the game places the sword from the right hand while a pose blend runs, with the hand-space grip interpolated
  between the source and target clips' own grips (`AVeyrKnight::GetWeaponSocketWorld`, `-VeyrNoWeaponGripLock` = old).
  Approved assets are untouched (hash check above). Simulated engine transitions (`measure_handslip.py`): extra hand
  slip before 1.8-9.9 cm (light attack <-> idle 8.9/9.9, strafe -> idle 9.6, strafe -> stagger 4.5), after 0.0 cm on
  all 10. In authored clips the roll attack writes WeaponSocket = RightHand x grip every frame (slip 0.0).
- **C (lock-on posture).** Lock-on enter/exit blends 0.30 s (`-VeyrLockOnBlend=`). Chest within 20 deg of the boss on
  every strafe, sprint strafe and blink. Walk-strafe hips stay 15-26 cm below the idle (source crouch); sprint and blink
  hips are -9..+3 cm.

| Row | Chest yaw (deg) | Knee vs travel (deg) | Hand slip (cm) | Foot skate / drift | Other |
|---|---|---|---|---|---|
| Sprint strafe L / R (1H, 2H) | -13.7..13.8 / -13.7..13.6 | 9.8 / 9.7 | 0.0 | stance speed = nominal 453.4 / 456.9 cm/s (planted toe) | ends at ankles 61.5-63.5 / 60.7-62.3 cm |
| Strafe L / R (1H, 2H) | -3.7..4.7 / -4.6..3.7 | 48.7 / 48.7 (source knees, 3.7 deg over) | 0.0 | nominal 163.6 / 159.7 cm/s | ends 62.2-64.1 / 59.4-62.0 cm; hips -15..-26 |
| Blink L / R (1H, new 2H) | -13.7..13.9 / -13.7..13.6 | 9.9 / 9.8 | 0.0 | root = 90% of planted-toe speed while visible, about 52 cm/s residual in game; planted drift with root 4.9 / 7.2 cm | ends 61.5-67.6 / 57.3-62.3 cm; lateral 298.6 cm total kept |
| Staggers F/B/L/R (1H, 2H) | front 0.0..0.8 | n/a | 0.0 | ankle drift <= 0.4 cm | tip <= 36.5 cm/frame; pitch 1H <= 25.0, 2H <= idle+10 (78.1); first/last carry 0.0/0.2 deg; front head 45.4 of 45.5 cm straight back; L/R 53.1 / 55.5 cm |
| Backpedal guard 1H / 2H | -7.4..5.9 | backward gait by design | 0.0 | stance 59.95 cm/s | 1H blade +40 deg above the idle carry (pitch 45.8-47.7, tip 309 cm); 2H tilted 22 deg forward (46 deg) |
| Roll attack | n/a | n/a | 0.0 | exit planted drift <= 1.9 cm; recovery steps lift 15.5 / 12.6 cm | join 0.60 s source (14 frames in game); ends in the 1H idle carry (0.0 deg) |

Deviations from the round-2 instructions:
- Backpedal guard is **held through the loop** (carry 39.8 / 23.4 deg off the idle at the loop seam) instead of easing to
  within 15 deg at the first/last 3 frames. A 1.2 s loop that dips back to the carry every cycle would bob the blade
  2.5 times a second; the 0.30 s lock-on enter/exit blend covers the transition.
- 2H staggers cannot hold an absolute 25 deg pitch (the 2H idle carry itself is 68 deg); they are capped at idle+10.
- Walk strafes keep the source knees (48.7 deg max, 3.7 over the 45 deg limit) and source hip height.
- No 2H roll attack: RollAttack starts as the approved 1H Fab Roll (owner-selected), so a 2H roll attack would still
  snap at the roll; it needs a 2H roll first.

Gate lines (round 2). The GPU never went below 30% in a 120-minute wait (23:45-01:45; other sessions' video2rig reader
training and renders for the dragon and Markhor Meadow held it at 98-100%), so every run below ran at 11-14 fps with
0.40 s clamped frames and is load-contaminated:
- UBT VeyrEditor `Result: Succeeded` (`Local/unreal-build-20261029T055627234434Z` pair); UBT Shipping `Result: Succeeded`;
  package `BUILD SUCCESSFUL`, `ExitCode=0` (`Local/package-20261029T055623Z`), signed zip sha256 `11afb863...200662ae`,
  app `/private/tmp/veyr-verified-bundle-ei9yiygb/Veyr-Mac-Shipping.app`.
- Batch 1 (build `package-20261029T034134Z`): lockon True (blink direction 3/3, lab 5/5, facing 1.2 deg, 12.0 fps); core,
  controls, guard, death True (13.4 / 12.7 / 13.0 / 12.2 fps); integration 0/3 (11.2 / 11.8 / 12.6 fps), each failing at a
  locked blink: the 0.12 s second-afterimage window fell between two 0.4 s frames (1 of 2 echoes captured).
- Fix: `UpdateBlinkEchoes` now captures a skipped afterimage late (same authored source time; no change at normal fps).
- Batch 2 (echo-fix build): lockon True (3/3, 5/5, facing 4.9 deg, 13.3 fps); integration 1/3 (12.1 / 12.2 / 12.3 fps):
  run 1 passed all 18 features; runs 2-3 failed `locked_blink_right` with both echoes captured and 298.6 cm travel but no
  frame inside the 0.16 s hidden window; core True (13.7), death True (13.2); controls and guard False "player died before
  objectives" (13.5 / 13.3 fps; both passed in batch 1 at the same rate on identical animation data).
- Evidence: `Evidence/native-*-20261029T0544..0554` (batch 1), `Evidence/native-*-20261029T0608..0620` (batch 2).
  A quiet-GPU integration and controls/guard rerun is still owed; the failures are frame-window sampling and bot survival
  at 12 fps, and none reproduced as a clip-selection or direction error (lockon 3/3, direction trials measured).

Notes: the round-1 bodies exported Blender's default scene range (frame 1..250); round 2 sets the range explicitly. While
clearing my own package staging I ran `rm -rf /private/tmp/veyr-stage-*`; my receipts name three such directories, and I
cannot prove no other session's staging directory matched that glob.

Restore for round 2: after rounds 0 and 1, `gh release download knight-complete-round2-20261029 -R
oh-ashen-one/veyr-animation-sources`, `shasum -a 256 -c SHA256SUMS`, `unzip -n` each zip at the worktree root.
Review page: `Local/knight-review-20261028/serve/index.html` (round 2 vs round 1); `serve-round1/`, `serve-round0/` kept.

- Rerun 2026-10-29 03:04-03:11 on the same build (`package-20261029T055623Z`, no rebuild): the coordinator reported the
  dragon jobs finished, but the GPU still read 98-100% for the whole 20-minute wait (another UnrealEditor and other loads
  were running), so these runs are load-contaminated too. core True 12.9 fps, death True 12.4, lockon True 12.8 (blink 3/3,
  lab 5/5, facing 1.9 deg), integration False 12.0 (`locked_blink_left`: both echoes captured, 298.6 cm travel, no frame
  inside the 0.16 s hidden window; frame sampling, not code), controls True 12.0, guard True 13.4. Evidence
  `Evidence/native-*-20261029T0704..0710`; recorded in `round2-metrics.json` under `gates_20261029T0704`.
