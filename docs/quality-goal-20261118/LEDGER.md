# Quality goal ledger

Director: Fable 5.2 (plans, briefs, reviews; builds nothing). Started 2026-11-18 12:35 ET on `fable/quality-goal-20261118`.

## Phase status

| Phase | State | Evidence |
|---|---|---|
| A bugs | in progress | |
| B weight and sound | sound set in preparation (no engine) | |
| C picture | not started | |
| D camera and size | not started | |
| E new knight | assets found on disk; plan in progress | |
| F dragon animation | not started | |

## Spawns

| When (ET) | Piece | Agent / model | Engine | Time box | Outcome |
|---|---|---|---|---|---|
| 11-18 12:37 | A4 knock-down 5 s + difficulty band | opus-builder, Opus 5.5 high | held until 13:45 | 2.5 h | floor time 4.94 s max over 35 knock-downs (was 5.8-9.3), `-VeyrLegacyKnockdown`, pushed `735fa3c`. Band NOT held yet: the scripted knight reaches the head too late in a 3 s window (65/0/0/0 damage per knock-down against about 250). Paused by the director: band pass happens after the grounding fix merges. Next levers: bot locks on while closing, head bonus through 40 % of the rise, boss health |
| 11-18 12:37 | A1-A3 diagnosis (pinched foot, camera inside, floating) | opus-builder, Opus 5.5 high | none | 1 h | done 12:46: A1 = mirror tool leaves one right-front toe bone unpaired (339 vertices follow it); A2 = nothing on the dragon blocks the camera; A3 = clips raise the body bone, to be measured |
| 11-18 12:47 | A1-A3 implementation in a worktree, no building | same agent | none | 1.5 h | coded 13:07 (`fable/quality-goal-A123`: camera boom, grounding, mirror-toe fix, three proof replays); compiles; re-mirrored clips and film checker ready |
| 11-18 13:46 | A1-A3 merge, build, proofs, regression, baseline film | same agent | holds | 3 h | running |
| 11-18 12:37 | B1 recorded sound set + audition page | sonnet-builder, Sonnet 5.5 high | none | 2.5 h | running |
| 11-18 12:37 | Greystone / animation sample access lookup | haiku-scout, Haiku 5.5 high | none | short | done: both already in `/Users/Shared/UnrealEngine/Launcher/VaultCache` (Greystone 2.1 GB, Game Animation Sample 5.8 7.0 GB); no login needed |
| 11-18 12:50 | E knight swap plan (read-only) | opus-builder, Opus 5.5 high | none | 75 min | done 13:00: plan in `Local/quality-goal/E-plan.md`. Accepted: Greystone as the only runtime skeleton, clips baked onto it by editor scripts, our C++ clip player kept, own C++ motion matcher over Game Animation Sample clips (fallback: baked search table like the reference). Skin is probably the pack's default mesh; confirm by render. Estimate 7-9 engine days, one-day trial first |
| 11-18 12:52 | Free effects inventory | haiku-scout, Haiku 5.5 high | none | short | done: only Cascade effects on disk (Paragon packs: Rampage/Gideon dust, Terra/Greystone ground impacts, Kwang/Greystone sparks, debris meshes); engine ships Niagara templates and the Cascade-to-Niagara converter; no dragon-breath effect |
| 11-18 13:10 | B4-B6 weight code (contacts, shake, dust, spine reaction, trail) in a worktree | opus-builder, Opus 5.5 high | none | 2.5 h | compiles 13:38 (`fable/quality-goal-Bfeel` `2c32825`); never run; waits for the engine. Broke the wait-for-other-builds rule once (reported it) |
| 11-18 13:20 | C picture: renderer features, relit courtyard, controls box (code in a worktree) | opus-builder, Opus 5.5 high | none | 2 h | compiles 13:40 (`fable/quality-goal-C` `a3afaa3`); never run; needs about 5 engine hours; waits |
| 11-18 13:44 | B1-B3 sound wiring code in a worktree (on top of the weight branch) | sonnet-builder, Sonnet 5.5 high | none | 2 h | running |

## Spend

| When | Provider | Job | Cost |
|---|---|---|---|
| | | none so far | 0 USD |
