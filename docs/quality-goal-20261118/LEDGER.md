# Quality goal ledger

Director: Fable 5.2 (plans, briefs, reviews; builds nothing). Started 2026-11-18 12:35 ET on `fable/quality-goal-20261118`.

## Phase status

| Phase | State | Evidence |
|---|---|---|
| A bugs | A1, A3, A4 met and installed; **A2 reopened** (camera still inside the dragon in a real fight); band within tolerance | `Local/playtest-goal-review/phaseA/`, `Evidence/native-{footclosehits,camerahug,soleheights}-20261118T*` |
| B weight and sound | sound set staged (116 recorded + 26 generated); weight and sound code written, reviewed, fixed; waiting for the engine | `http://localhost:8823/audio.html` |
| C picture | code written, reviewed, fixed; waiting for the engine | |
| D camera and size | camera code written, reviewed, fixed; waiting for the engine | |
| E new knight | assets found on disk; plan in progress | |
| F dragon animation | playback code written, reviewed, fixed; waiting for the engine | |

## Spawns

| When (ET) | Piece | Agent / model | Engine | Time box | Outcome |
|---|---|---|---|---|---|
| 11-18 12:37 | A4 knock-down 5 s + difficulty band | opus-builder, Opus 5.5 high | held until 13:45 | 2.5 h | floor time 4.94 s max over 35 knock-downs (was 5.8-9.3), `-VeyrLegacyKnockdown`, pushed `735fa3c`. Band NOT held yet: the scripted knight reaches the head too late in a 3 s window (65/0/0/0 damage per knock-down against about 250). Paused by the director: band pass happens after the grounding fix merges. Next levers: bot locks on while closing, head bonus through 40 % of the rise, boss health |
| 11-18 12:37 | A1-A3 diagnosis (pinched foot, camera inside, floating) | opus-builder, Opus 5.5 high | none | 1 h | done 12:46: A1 = mirror tool leaves one right-front toe bone unpaired (339 vertices follow it); A2 = nothing on the dragon blocks the camera; A3 = clips raise the body bone, to be measured |
| 11-18 12:47 | A1-A3 implementation in a worktree, no building | same agent | none | 1.5 h | coded 13:07 (`fable/quality-goal-A123`: camera boom, grounding, mirror-toe fix, three proof replays); compiles; re-mirrored clips and film checker ready |
| 11-18 13:46 | A1-A3 merge, build, proofs, regression, baseline film | same agent | held to 16:30 | 3 h | A1 met (stretch 0.002 cm against 768 cm), A2 met (0 of 10285 frames inside, legacy 449), A3 met (67/67 clips within 3 cm, live float 0.0 cm against 25.5 cm median; the owner's 3 ft was not reproduced, worst clip was 68 cm). Package `78f2c849` (`3e5b681`). Regression: controls, intro, death, two-hand win pass; showcase FAILS at the Tail segment (new); one-hand win 166.9 s (band pass pending). Baseline film made |
| 11-18 16:33 | Showcase Tail regression: bisect and fix | same agent | held to 17:05 | 1 h | fixed: the camera's body hull was refitted on every mesh-variant switch (60-250 ms frames); now cached. Showcase 20/20, camera proof 0 of 10223 inside, camera cost 0.2 ms mean. Package `808a2f66` (`db87523`) |
| 11-18 17:07 | A band pass on the merged build | opus-builder (the A4 agent), Opus 5.5 high | held to 19:45 | 3 h | done (`ac89d8c`, package `331158b9`): scripted knight arrives locked and swings at the rising head; the head keeps its exposed bonus through 40 % of the rise (`-VeyrNoRiseHeadBonus`); health unchanged at 845. 16 seeds per grip: one-hand 15/16 within 150 s (one win at 175 s), median 84.3 s; two-hand 16/16, median 72.3 s; passive 7.5-12.34 s (one seed 0.34 s over, came in with the grounding merge); floor time 4.9 s. Damage per knock-down 151 / 101 (was about 250 with 7 s lying). Record `Local/playtest-suite-a4-G16-20261118T234533Z.json` |
| 11-18 19:47 | A2 second pass verification, regression, phase A film and clips (final phase A package) | opus-builder (the A1-A3 agent) | held to 21:21 | 2.5 h | done (`4c9a31c`, package `34667e83`, receipt `Local/package-20261119T005231Z`): camera 0 of 8246 frames inside the dragon, 0 inside the knight, knight whole on screen 99.0 % (stock camera: 343 inside, 78.8 %); regression all pass (record `Local/playtest-suite-phaseA-final-regression-20261119T010521Z.json`); film `Local/playtest-goal-films/veyr-phaseA-victory.mp4`; page rows updated. Open: camera still jumps (one top-down pop at 13 s of the film); take-off wing-root skin stretch needs a Blender reweight (moved to phase F); scripted fights got slower with the new camera on 7 one-hand seeds (median 92.6 s, in band) because the bot aims from the camera position in flight |
| 11-18 21:24 | B4-B6 weight: merge, assets, tuning by eye, proofs, regression, clips | opus-builder (the weight agent) | holds | 4 h | running |
| 11-18 21:28 | Blind critic, phase A clips round 2 | opus-critic, Opus 5.5 high | none | short | done: A3 fix wins; A2 fix wins but with a jump and other faults; A1 tie again (see `REVIEWS.md`) |
| 11-18 21:28 | Blind critic, our phase A fight film against the reference footage, six aspects | opus-critic, Opus 5.5 high | none | short | done 21:45: reference better on all six (large on picture, impacts, sound; clear on hero, creature, camera). It caught our camera inside the dragon in the real fight: A2 reopened |
| 11-18 21:40 | Phase A build installed behind Play Veyr.app (`~/Applications/Veyr/f161bd1e566e`, source `34667e83`) | director | none | | done |
| 11-18 21:50 | A2 reopened: diagnose the fight-film inside frames, fix, honest checks in every replay mode (no engine) | opus-builder (the A1-A3 agent) | none | 90 min | running |
| 11-18 17:10 | Blind critic on the phase A before/after clips | opus-critic, Opus 5.5 high | none | short | done 17:20: see `REVIEWS.md` (A2 and A3 fixes win; A2 needs a second pass; A1 clip pair proved nothing) |
| 11-18 17:22 | A2 second pass (minimum distance from the knight, never inside him, cut-through off) and A1 clip re-cut, code only | opus-builder (the A1-A3 agent) | none | short | coded 17:33 (`fable/quality-goal-A123` `1369e8b`); ankle spikes are modelled spurs, leg fins are a wing-root skin stretch in take-off (needs a reweight); waits for the engine |
| 11-18 17:15 | E knight swap: code path, editor scripts and motion-matching design written blind in a self-contained worktree | opus-builder (the E agent) | none | 3 h | done 17:50 (`fable/quality-goal-E` `fdde27f`, pushed): compiles, scripts unrun; merge of all waiting branches rehearsed, 5 textual conflicts |
| 11-18 16:35 | Progress page (`progress.html`, clips by phase) | sonnet-builder, Sonnet 5.5 high | none | 1 h | done: `http://localhost:8823/progress.html`, rows added with `add_clip.py`; layout checked by headless screenshot |
| 11-18 12:37 | B1 recorded sound set + audition page | sonnet-builder, Sonnet 5.5 high | none | 2.5 h | done 14:20: 116 CC0 cuts for 25 cues staged in `Local/AudioSources20261118/staged/Recorded20261118/`, receipt and tools pushed (`e3886c0`), audition page `http://localhost:8823/audio.html`. Weak: giant steps, wing flaps, impacts, heal, breathing |
| 11-18 14:24 | Generated supplement for the weak cues through fal.ai (3 USD cap) | same agent | none | 75 min | done 14:40: 26 kept of 37 takes (breathing, giant steps, wing, impact, heal, growl), staged in `staged/Generated20261118/`, 0.13 USD, pushed `8154450` |
| 11-18 12:37 | Greystone / animation sample access lookup | haiku-scout, Haiku 5.5 high | none | short | done: both already in `/Users/Shared/UnrealEngine/Launcher/VaultCache` (Greystone 2.1 GB, Game Animation Sample 5.8 7.0 GB); no login needed |
| 11-18 12:50 | E knight swap plan (read-only) | opus-builder, Opus 5.5 high | none | 75 min | done 13:00: plan in `Local/quality-goal/E-plan.md`. Accepted: Greystone as the only runtime skeleton, clips baked onto it by editor scripts, our C++ clip player kept, own C++ motion matcher over Game Animation Sample clips (fallback: baked search table like the reference). Skin is probably the pack's default mesh; confirm by render. Estimate 7-9 engine days, one-day trial first |
| 11-18 12:52 | Free effects inventory | haiku-scout, Haiku 5.5 high | none | short | done: only Cascade effects on disk (Paragon packs: Rampage/Gideon dust, Terra/Greystone ground impacts, Kwang/Greystone sparks, debris meshes); engine ships Niagara templates and the Cascade-to-Niagara converter; no dragon-breath effect |
| 11-18 13:10 | B4-B6 weight code (contacts, shake, dust, spine reaction, trail) in a worktree | opus-builder, Opus 5.5 high | none | 2.5 h | compiles 13:38 (`fable/quality-goal-Bfeel` `2c32825`); never run; waits for the engine. Broke the wait-for-other-builds rule once (reported it) |
| 11-18 13:20 | C picture: renderer features, relit courtyard, controls box (code in a worktree) | opus-builder, Opus 5.5 high | none | 2 h | compiles 13:40 (`fable/quality-goal-C` `a3afaa3`); never run; needs about 5 engine hours; waits |
| 11-18 13:44 | B1-B3 sound wiring code in a worktree (on top of the weight branch) | sonnet-builder, Sonnet 5.5 high | none | 2 h | compiles 14:00 (`fable/quality-goal-Baudio` `067c6a8`): variants, contact sounds, breathing, per-move sounds, polish default; never run; waits |
| 11-18 13:50 | D1-D2 camera for a giant (code in a worktree) | opus-builder, Opus 5.5 high | none | 2 h | compiles 14:03 (`fable/quality-goal-D` `bd9a2ce`): lock target slides chest to striking limb, mouse no longer drops the lock, camera life, framing metrics, `framing` replay; never run; waits |
| 11-18 13:50 | F1-F4 dragon playback (tempo, cross-fades, foot lock, root tracks; code in a worktree) | opus-builder, Opus 5.5 high | none | 3 h | compiles 14:15 (`fable/quality-goal-F` `08a2c1f`): per-move tempo in `Data/dragon/playback.json`, two-clip fades, four-leg IK lock, root tracks for buckle/collapse/rise only; gaps: no spine twist or turn clips for aim, strikes do not travel; never run; about 3 engine hours; waits |
| 11-18 14:16 | Code review of the weight and sound branches before engine time | opus-critic, Opus 5.5 high | none | short | done 14:34: weight 3 high / 6 medium / 6 low, sound 2 high / 4 medium / 3 low, no crashes; both builders resumed to fix in their worktrees |
| 11-18 14:36 | Code review of the dragon playback branch | opus-critic, Opus 5.5 high | none | short | done 15:00: 6 high / 7 medium / 6 low, no crashes (interrupted fades pop, front toes not carried by the leg IK, `playback.json` not in packages, collapse travel counted twice, large difficulty shift); builder resumed to fix |
| 11-18 14:36 | Code review of the picture and camera branches | opus-critic, Opus 5.5 high | none | short | done 15:02: picture 1 high / 4 medium / 3 low (fire-breath shadow cost, capture timing, exposure ceiling), camera 3 medium / 4 low (lock-on freeze after mouse, meter measures the wrong view, movement direction while locked); legacy switches confirmed exact; builders resumed to fix |

## Spend

| When | Provider | Job | Cost |
|---|---|---|---|
| | | none so far | 0 USD |
| 11-18 | fal.ai elevenlabs/sound-effects/v3 | 37 sound-effect takes for dragon breath, steps, wing, impact, heal, growl (docs/audio-20261118/generation-ledger.json) | 0.13 USD of the 3 USD budget |

## Incidents

- 11-18 15:35 ET: while stopping its own suite, the phase A builder sent SIGTERM by name pattern to pid 36755, another session's `gpu_slot` capture (label `catacombs-promote017-Promote062B`, a Unity batch run). The gate log shows that capture released with exit 124 after 33 s at 15:35:37, so the signal most likely ended that run early. That session carried on with later launches. Rule added: signal only recorded PIDs, never by pattern. Reported to the owner.
