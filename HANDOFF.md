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

**Dragon fix round 2 (2026-10-29, Studio, branch `claude-code-enhancements`, not pushed):**
- Nine v4 Actions built from the round-2 critique (`Local/video2rig/dragon/Dragon_<Move>_sd_v2r_v4.blend`, Actions
  `roar_v4`, `collapse_v4`, `bite_v4`, `land2_v4`, `rise_v4`, `air_hover_v4`, `air_land_v4`, `takeoff3_v4`,
  `air_fire_down_v4`); scripts in `tools/dragon_refine/v4/`. Move data (`Data/dragon/`) rebuilt from them; movedata tests OK.
- Measured on a CPU raster with the critic's definitions (no GPU render possible: foreign trainer at 100 %):
  `Local/dragon-review-20261029/measure_v4.json`. 29 of 33 targets pass; fails: wing-body correlation at lag 0-4
  (all airborne, |r| 0.29-0.45; best at negative lag), takeoff last-24 centroid 0.14 BH, raw hover last-8 span, fire-down
  span drift 7.3 %. Per-item table: `docs/canitcode-enhancements.md`, section "Fix round 2".
- **Next:** run the render queue when the GPU is quiet: `tools/dragon_refine/v4/run_queue_v4.sh`
  (reads `Local/dragon-review-20261029/queue_v4.txt`, gpu_slot capture, adds the "Round 2 fix" cards to the review page),
  then a blind re-critique on the renders.

**Session end 2026-10-29 (laptop orchestrator, owner continuing on the Studio):**
- Dragon: 12 clips through video2rig (8 ground + 4 airborne), all on this branch (head c7056e0 before this note).
  Review page `Local/dragon-review-20261029/serve/index.html` (airborne section at `#airborne`). Open dragon items:
  air_land touchdown is authored not fitted, takeoff3 overshoots the hover by ~50 cm, a lying-start "rise" clip is a
  known gap, and a dragon fix round 2 (re-critique of round 1) has not been run.
- Knight: branch `fable/knight-complete-20261028` (worktree `/Users/midir/veyr-knight-20261028` on the Studio), read its
  own HANDOFF.md. Round 2 is built, packaged and pushed; the blind critic says round 2 is **not shippable** (blinks are
  a sprint loop, sprint-strafe waist twist, roll-attack exit slide, loop seams; sword and skate fixes unproven because
  no engine blends were rendered). Critique: `Local/knight-review-20261028/critique-round2.md` in that worktree.
  Its ranked fix list is the round-3 plan. Gates: 5 of 6 pass; integration fails on `locked_blink_left` only because
  the GPU is pinned by other sessions (12 fps, 0.4 s frames miss the 0.16 s hidden window). A frame-rate-independent
  gate (reads the game's own blink record) was in progress when the session ended; see the knight HANDOFF.
- Shared brain: agents-md PRs #30, #31, #32 (video2rig as the creature default) are open and need the owner's merge.
- Higgsfield: this session spent 589.5 credits on 15 Seedance clips; balance about 575.


- Pipeline works on this Mac end to end: start picture → clip → check → fit → review → Blender Action → scripted
  refinement → blind A/B. Clip to Action takes about four minutes once a reader exists.
- Idle: refined video2rig idle beats the hand-keyed idle in a blind A/B (47 vs 41); both still fail the shipped bar.
- Roar: landed on Seedance with a half-open-wings prompt (the rig's wings are fanned at rest; 1.27x span is the
  physical limit). Two usable Actions: `Dragon_Idle_v2r_v2.blend`, `Dragon_Roar_sd_v2r_v2.blend`.
- Move data measured from those Actions into `Data/dragon/*.json`; C++ loader and bone hurt capsules compile
  (UBT, editor and Shipping) but nothing is verified in PIE.
- Spend: 107.5 Higgsfield credits (3 MiniMax at 12.5, 2 Seedance at 35).

## Dragon clips 2026-10-29 (Seedance 2.5 move set, Studio)

Nine first-take clips plus two regenerations went through the pipeline overnight. Full numbers per clip are in
`docs/canitcode-enhancements.md` (Clip ledger rows and the section "Remaining clips (2026-10-28/29)").

**Fitted, refined, rendered** (Actions in `Local/video2rig/dragon/*.blend`, all 24 fps; scripts in `refine/`, gitignored):

| Move | Blend / Action | Frames | End | Check body / limbs | Fit miss, outline front / side |
| --- | --- | --- | --- | --- | --- |
| idle (earlier) | `Dragon_Idle_v2r_v2` / `idle_v2` | 90 | loop | 0.58% / 0.59% | 1.73 px, 0.81 / 0.90 |
| roar (earlier) | `Dragon_Roar_sd_v2r_v2` / `roar_sd_v2` | 121 | live, no return | 1.13% / 0.65% | 3.30 px, 0.76 / 0.85 |
| collapse | `Dragon_Collapse_sd_v2r_v2` / `collapse_v2` | 145 | lying flat | 1.17% / 0.77% | 4.72 px, 0.75 / 0.83 |
| death | `Dragon_Death_sd_v2r_v2` / `death_v2` | 169 | on the right flank | 0.93% / 1.36% | 7.07 px, 0.71 / 0.82 (weakest) |
| bite | `Dragon_Bite_sd_v2r_v2` / `bite_v2` | 121 | stance (closed onto frame 0) | 0.92% / 1.22% | 3.76 px, 0.78 / 0.80 |
| claw_swipe | `Dragon_ClawSwipe_sd_v2r_v2` / `claw_swipe_v2` | 121 | stance | 0.81% / 0.74% | 2.63 px, 0.77 / 0.88 (reader-78) |
| stagger | `Dragon_Stagger_sd_v2r_v2` / `stagger_v2` | 121 | stance | 0.85% / 1.17% | 4.49 px, 0.77 / 0.82 |
| land (land2 clip) | `Dragon_Land2_sd_v2r_v2` / `land2_v2` | 118 | stance | 0.86% / 0.88% | 2.83 px, 0.79 / 0.87 |
| rise | `Dragon_Rise_sd_v2r_v2` / `rise_v2` | 121 | stance | 1.17% / 0.99% | 3.07 px, 0.81 / 0.84 |
| idle_look | `Dragon_IdleLook_sd_v2r_v2` / `idle_look_v2` | 193 | loop | 1.02% / 0.91% | 2.00 px, 0.84 / 0.92 (best) |
| idle layered | `Dragon_IdleLayered_sd_v2r_v2` / `idle_layered_v2` | 193 | loop | (idle_v2 body + look head) | |

Keep all three idles (`idle_v2`, `idle_look_v2`, `idle_layered_v2`); the layered one has the look clip's 46 deg of head yaw on idle_v2's breathing, tail
and wings (measured table in the doc). Hari's call on which is the shipped idle.

**Failed the check, not fitted** (check FAIL is regenerated, never fitted): `land` 1.76% (body disagreement between the panels; fail line 1.5%),
`takeoff` 2.14%, `takeoff2` 2.41% (a lower rise in the prompt made it worse). Land passed once the hop was pinned low in the prompt (land2, 0.86%), but
the generator still hops 0.59 body heights. Finding: airborne moves need a flying start picture and a reader trained on it; likely cause (untested) is that
the start picture and reader assume feet on a floor.

**What the refinement does** (`refine/move/refine_move.py`, `refine/collapse/refine_fall.py` for collapse and death): trims a still tail, blends the end
onto frame 0 for moves that return to stance (24 to 36 frames), clamps wings to 1.27x of the frame-0 lateral extent (never needed tonight: raw peaks were
1.00 to 1.24x), lifts a wing root or the body when the fit goes under the floor, smooths tail spikes, plants feet by temporary IK bake only while grounded
(`ground=auto`) or the whole clip (`ground=all`). Collapse and death also relay the tail and clear the floor. Footage frame rate: claw_swipe and rise came
as 30 fps content with every 5th frame dropped (the tool detects and resamples to 24).

**Move data**: `Data/dragon/*.json` rebuilt for every Action with `tools/movedata/run_veyr.sh` (the runner now lists all Actions; `BLENDER_CAP=2` when a
render is running); 3 unit tests pass. Landing shock (land2): feet down frames 84 to 86, shock recorded at 3.583 s (7.24 m/s foot). Collapse: chest hits
at 3.167 s (10.9 m/s). Still nothing verified in PIE.

**Review page**: `Local/dragon-review-20261029/serve/index.html` (per move: Seedance source, hand-keyed before where one exists, raw fit, refined, three
angles; idle_v2 vs idle_look_v2 vs idle_layered in one row). `rangeserver.py` beside it (Safari needs byte ranges); no server is running. Renders live
in `Local/ab-idle-20261028/video/clip_<label>_{front,left,threequarter}.mp4` (labels CO, DE, BI, CS, ST, RI, LA, IL; 0 = raw fit, 1 = refined; IL2 = layered;
H* = hand-keyed before from the review checkout, read-only).

**Credits** (Higgsfield balance 1241.64 to 792.14): 449.5 spent this session on 11 renders = 9 first takes (379.5) + land2 + takeoff2 (35 each, both
5 s). 5 s clips cost 35; the 6, 7 and 8 s clips (collapse, death, idle_look) cost about 8.07 credits per second, derived (48.4 / 56.5 / 64.6; verify
against the transaction list). The failed first land and takeoff cost 35 each and produced no Action. Branch total with the earlier 107.5: 557.0.

**Fix round 1 (v3 Actions)**: from the blind critique (`Local/dragon-review-20261029/critique.md`). Eight new Actions, v2 untouched: `roar_sd_v3`, `collapse_v3`,
`death_v3`, `bite_v3`, `claw_swipe_v3`, `stagger_v3`, `land2_v3`, `rise_v3` (`Dragon_<Move>_sd_v2r_v3.blend`). Shared stance = idle_v2 frame 0 (frame 0 and last frame overlap
1.000, feet 0 mm off); claw and rise keyed at container time (no 4-frame stutter); land2 on a ballistic arc with touchdown at frames 74 to 75; stagger recoil at frame 2 with a
3 cm catch-step lift; roar flared to 1.20x idle (not the 1.25x target) with a tremor; bite jaw 38 deg; death holds from 110; collapse wing swept and folded. Numbers per fix:
`docs/canitcode-enhancements.md`, section "Fix round 1". Scripts in `Local/video2rig/dragon/refine/v3/` (gitignored). `tools/movedata/run_veyr.sh` now builds from the v3
Actions (roar ends on the stance: seam 0.00x); `Data/dragon/*.json` rebuilt; 3 tests pass.

**Airborne reader (trained)**: sibling project `Local/video2rig/dragon-air/` (hover start picture `start/start.png`, ground picture `start-ground/start.png`, perspective lens 50, same
cameras; Higgsfield media ids hover 3d674b17-e4f8-4a0b-b90c-a6edb3f55476, ground 2e796531-c58c-4f75-b7c0-762510fb5bc1), reader trained (9000 steps, 172 min total, held-out median front 7.31 px / side 6.68 px; `reader/reader.pt`) on the fork branch
`air-reader` (`~/video2rig-air`, opt-in `air` key in creature.json). Prompts: `dragon-air/clips/air_fire_down|air_land|air_hover|takeoff3.prompt.txt`.

**Airborne clips**: `air_hover`, `air_land`, `takeoff3`, `air_fire_down` fitted with the airborne reader and refined (`Dragon_AirHover|AirLand|AirTakeoff|AirFireDown_sd_v2r_v3.blend`,
Actions `air_hover_v3`, `air_land_v3`, `takeoff3_v3`, `air_fire_down_v3`). Checks are WARN (no panel check with perspective cameras); fits: 2.57, 4.84, 5.53, 4.31 px median. The landing and take-off fits
are weak (outline 0.61 to 0.71): air_land's touchdown is authored, takeoff3 overshoots the hover by 50 cm. Details: `docs/canitcode-enhancements.md` "Airborne clips". Move data has the four air moves
(`floor_metrics_valid: false`; fire_down window 3.333 to 6.667 s).

**Next steps**
1. Flying start picture for takeoff and land: render the start picture with the body off the floor (and a reader trained on it, about 3 h of MPS), then
   regenerate takeoff and a real tall hop. Until then takeoff, fly-hover stay on the hand-keyed Blender versions in the review checkout.
2. A lying-start clip for rise: the rise clip starts standing, 21 cm (mean vertex shift, rig scale) from the collapse's last frame; the engine would have to
   do the get-up. Generate a clip whose first frame is the collapse's end pose (needs its own start picture).
3. Owner review of the page, then pick the idle; then the engine session (bind capsules with the Customuse content, import Actions, blend collapse to rise, fix the
   18 cm rest-pose float in the import offset).
4. Death needs a second look (median miss 7.07 px, twist 51.7 deg on a foreleg, a leg dips 1.85 cm under the floor in transit); stagger's catch-step and the
   claw swipe's 7.8 cm of head overreach past the straight-neck figure are noted in the doc and uncorrected.

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

- Nothing running on the Studio for this thread as of 2026-10-29 07:30: the old page server (pid 53126) and
  `tailscale serve --tcp 8790` were turned off on 2026-10-28 evening at the owner's request. No engines, no LaunchAgents.
- Other sessions' processes were on the Studio GPU all night (an Unreal Editor under `/Users/Shared/Epic` and Markhor
  Meadow video2rig jobs); device utilisation read 100%. They are not ours; do not touch them.
- The review pages are served on the **laptop** only: dragon `Local/dragon-review-20261029/serve` on port 8790,
  knight `Local/knight-review-20261028/serve` on port 8791 (`python3 rangeserver.py serve <port>`), with the Chrome
  lazy-load patch applied. Both folders are rsync copies of the Studio ones; the Studio copies are the source.

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
