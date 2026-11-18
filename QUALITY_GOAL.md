# Veyr quality goal — master prompt, 2026-11-18

This file is the full brief. The short `/goal` line in `GOAL_PROMPT.md` only points here.

Owner-requested goal: close the visible gap between Veyr and the reference game (Can It Code's Leshy boss fight) by
doing everything in the 2026-11-18 block at the top of `BACKLOG.md`.

**The owner's mandate (2026-11-18):** "This is the final improvement I want to make on this, so take however long you
need. You are in charge. Do this on your own, and the end product should be a game that is as high quality as the
source code." The bar is the reference game itself, not our previous build. There is no deadline and no check-in is
required: make every decision, including the ones this file marks "owner may change", and keep going until the bar in
"Done" is met.

Read first, in this order: this file; the top of `HANDOFF.md`; the top block of `BACKLOG.md`; `AGENTS.md`; the wiki page
`dragon-boss-fight`. Then verify the live repo, build and GPU state before acting.

Baseline: `main` at `79fe0bc`; planning branch `fable/owner-feedback-20261118`. Work branch:
`fable/quality-goal-20261118`, cut from the planning branch.

## Why the last goal changed nothing the owner could see

It tuned the boss's brain, health, size and pace, which were already level with the reference, and every review
compared our old build with our new one. This goal works on what is visibly different and judges every phase against
the reference footage.

## References

- Reference footage and frames: `~/leshy-reference` (episode video, 12 fight frames, contact sheets).
- Reference game, playable on this Mac: `~/leshy-bossfight-mac` (source in `Source/BossFight`, runtime data in `Data/`).
  Earlier teardown notes: `~/canitcode-teardown/{boss,hero,inventory}.md`. Tool notes: `~/video2rig` (`upstream/main` docs).
- Side-by-side page: `Local/playtest-goal-review/vs.html` (`python3 serve.py 8823`).
- What the owner saw and said: top block of `BACKLOG.md`. State and launch lines: top of `HANDOFF.md`.

## Fixed by the owner (do not reopen)

- Hitboxes and overall difficulty are good. Scripted results stay in the build 17 band: wins in both grips within
  150 s, medians within 15 % of 88 s (one-hand) and 73.5 s (two-hand) over 16 seeds, a passive player dies in under
  12 s. Any change that moves these is re-tuned back, never by touching hitboxes.
- The dragon is never made smaller. It gets bigger.
- Store assets (characters, packs, effects) are free ones only. Nothing is bought: no asset purchases, no credit
  top-ups, no plan changes.
- Generation is allowed with **fal.ai and Fish Audio** (owner, 2026-11-18: "don't use Higgsfield anymore. Higgsfield
  is gone. We now have FAL AI"). Never call Higgsfield. The fal key is in `~/.config/fal/secrets.env` as `FAL_KEY`
  (read it from there at run time; never print, log or commit it). Checked working on 2026-11-18 with the no-cost call
  `GET https://api.fal.ai/v1/models/pricing?endpoint_id=...` (`Authorization: Key $FAL_KEY`).
  fal bills in US dollars, so: read the live price from that endpoint before each job; one job at a time, reviewed
  before the next; every job in the clip or audio ledger with its cost; **at most 40 USD in this goal** and at most 8
  video clips, unless the owner raises it; stop and report rather than exceed it. Models seen on 2026-11-18: video
  `bytedance/seedance-2.5/us/image-to-video` (about 0.021 USD per 1,000 video tokens, roughly 2-3 USD for a 5 s 720p
  clip; start-frame mode, 720p), sound `elevenlabs/sound-effects/v3` (0.002 USD per second). Look up fal's current
  documentation before the first call; do not trust remembered request formats.
- Mixamo is for animations only, not characters. Sound comes from Freesound CC0 recordings first.
- The new knight is Paragon: Greystone in the dark gold-trimmed skin
  (`Local/knight-candidates/greystone-owner-pick-20261118.png`).
- The courtyard stays and is relit. The light only has to look good; it needs no visible source.
- Keep the approved 8-shot intro and the owner's music track.

## Phases, in order

Each phase ends with the same checkpoint (see "Checkpoint"). A phase is not done until its "done when" is measured.

### A. Bugs the owner saw

| # | Item | Done when |
|---|---|---|
| A1 | Foot mesh pinches out sideways on close hits (he thinks the right foot). Bisect: stance clean-up, per-leg stagger, unweighted rig bones. | Root cause named. A close-up film of 20 close hits on each foot shows no stretched vertex; a blind critic finds none. |
| A2 | Camera goes inside the dragon. | A scripted replay that hugs and circles the body, legs and belly for 60 s has zero frames with the camera inside a dragon body volume or showing back faces. Holds at the final dragon scale. |
| A3 | Dragon floats (about 3 ft by eye). | In every ground clip at the shipped scale, planted soles are within 3 cm of the floor. Side-on close-up frames inspected. |
| A4 | Knock-down too long. | From the drop to standing again: 5.0 s or less in every replay. Difficulty band above still holds. |

### B. Weight and sound

| # | Item | Done when |
|---|---|---|
| B1 | Replace placeholder sounds with Freesound CC0 recordings (tools: `tools/audio/freesound_candidates.py`, `prepare_recorded_set.py`; candidates already in `Local/AudioSources20261118/`). | No code-generated tone plays in default play. Frequent cues have at least 3 variants with random pitch. Provenance ledger committed. `-VeyrLegacyAudio` restores the old set. |
| B2 | Dragon sounds per move and per footfall; breathing in idle. Fill `Data/dragon/sounds.json` and play from clip time and foot contacts, placed at the head or the contact point. | Every dragon move and every footfall is audible in a captured film with game audio; idle has breath. |
| B3 | Knight footsteps from real foot contacts; armour and hit sounds layered. | Steps line up with feet in a half-speed film. |
| B4 | Camera shake scaled by impact speed and distance for every dragon contact with the ground; dust under each foot in three sizes by speed (Niagara, free Epic/Fab or engine content first). | Visible in film on walking, strikes, landing and collapse. |
| B5 | Dragon hit reaction across the whole spine, with a flash on the mesh; hit bursts in three sizes. | Blind critic: "the dragon reacts to hits" against the reference footage. |
| B6 | Knight attack feel: full-width smoothed weapon trail, motion blur, heavy-hit slow-motion tail and zoom punch, a hurt kick when hit. | Trail reads as a ribbon in frames; critic compares to the reference hammer trail. |

An old/new audition page for the sounds goes on the localhost page before the build that carries them.

### C. Picture

| # | Item | Done when |
|---|---|---|
| C1 | Turn on Lumen global illumination and reflections, virtual shadow maps, auto exposure, motion blur. | On by default with `-VeyrLegacyRender` to restore. Fight holds 60 fps at 1280x720 on this Mac (mean and p95 frame time reported before and after). |
| C2 | Relight the courtyard: warm shadow-casting lights, contrast, haze; remove the flat fill lights and the knight's fill light. | Blind critic rates our frames against `~/leshy-reference/frames` on lighting; "clearly worse" is not accepted. |
| C3 | Hide the always-on controls box after the first seconds (it stays in the pause menu). | Not present in fight frames. |

### D. Camera and size

| # | Item | Done when |
|---|---|---|
| D1 | Lock-on aims at the chest, settles in about a third of a second, keeps the knight and the striking limb in frame; mouse movement does not drop the lock for 1.8 s. | In a filmed fight the knight is fully in frame in at least 95 % of frames and the striking limb is visible at contact in at least 90 % of strikes. |
| D2 | Position lag, pull-back and wider lens when sprinting, small lean into turns. | Visible in film; no nausea-level motion (critic). |
| D3 | Bigger dragon: test 2.5x and 3x. Reach check on every attack, arena clearance, A2 and D1 rerun at each. | The largest scale that passes everything ships as default; clips at 2x, 2.5x and 3x are on the page for the owner. |

### E. New knight: Greystone

| # | Item | Done when |
|---|---|---|
| E1 | Compare the reference hero and our knight in Blender: why ours "breaks". | Short written finding, so the fault is not carried over. |
| E2 | Acquire Paragon: Greystone (free, Epic, Fab) through the owner's already-signed-in Epic/Fab session. Never type credentials. If a login is required, leave it as the one owner step and carry on with F. Raw files stay out of the public repo. | Asset in the project locally; acquisition steps recorded. |
| E3 | One-day trial first: the chosen skin in the game's light with idle, run, one attack, one roll. | Clip on the page beside the current knight before the full retarget starts. |
| E4 | Retarget all our clips onto his skeleton with one retarget setup; redo grip and foot fixes; rerun the grip and foot-contact proofs. Shield stays on the arm in the one-hand grip and guarding uses it; it goes on the back in the two-hand grip (owner may change this). | Every action works on Greystone; proofs pass; current knight kept behind `-VeyrLegacyKnight`. |
| E5 | Movement by motion matching (Unreal Pose Search with Epic's free Game Animation Sample): starts, stops, pivots and turn-arounds. | Blind critic compares run, stop and turn-around with the reference hero; foot slide within the existing gate. |
| E6 | Input: roll is buffered and interrupts actions; attacks turn toward the stick. | Measured in replays: no dropped roll input. |

### F. Dragon animation playback

| # | Item | Done when |
|---|---|---|
| F1 | Play the video-to-animation clips at their own speed; shorten only holds. | No phase above 1.25x except holds; difficulty band holds. |
| F2 | Cross-fade two running clips over 0.3-0.4 s. | No frozen-pose blend left; pops gone in film. |
| F3 | Four-foot floor lock at runtime, feet pinned in the clips; no whole-body snap turn under planted feet. | Planted-foot slide under 5 cm per second in every ground move. |
| F4 | Move the dragon along each clip's own root track where the clip has one. | Travel matches the clip; no slide-back at blends. |
| F5 | Pipeline upgrades: dense reader, upstream's whole-clip fit merged on a fork branch, refit existing clips. | Adopted only where a blind critic prefers the refit over the current clip. |
| F6 | Only if still needed after F1-F5: new dragon clips through Seedance on fal.ai, following the tool's own notes (first-frame start picture, full real speed, side and top views for tail and turns). Judge the fight against the reference footage first; generate only what is still missing. Expected at most: a proper right turn (today it is the left turn played backwards), a charge, a leaping strike, one authored multi-hit combo. | Each new move is in the brain with measured hit windows and root motion, passes the reach check at the shipped scale, and a blind critic prefers the fight with it. Difficulty band holds. If F1-F5 already reach parity on boss animation, this row is closed as not needed. |

## Checkpoint after every phase

1. Package a Shipping build. Run the regression set, one process at a time: controls, full intro, showcase 20/20,
   victory and restart in both grips, death and restart, and the 16-seed numbers for the difficulty band.
2. Film the same route and seed as the baseline, with game audio.
3. Add a three-way clip to the localhost page: reference, ours before the phase, ours after.
4. Blind Opus critic, twice: after against the reference footage, and after against before. If it still calls ours
   clearly worse on what the phase was about, do one more pass with a different approach, then report it plainly.
5. Commit and push. Install the build behind Play Veyr.app when the regression passes. Send the owner two lines and
   the page link.

The first clip for the owner comes from phase A, within the first few hours, not at the end.

## How the work is done

- The session model (Fable) directs only: plans, briefs, reviews, reports. `opus-builder` and `sonnet-builder` build,
  `haiku-scout` looks things up, `opus-critic` gates. Every spawn is labelled with its model. Every builder brief has
  a time box and a rough-first checkpoint. Critics are never skipped.
- One game or engine process at a time, windowless ones included. Rendered launches only through `gpu_slot`, 60 fps,
  background and windowed. No rendered launch between 11:00 and 13:00 ET while the stream flag exists: do builds,
  headless runs and Blender work then. Own processes only; SIGTERM and wait 60 s; never relaunch after two crashes.
  Do not delete evidence younger than an hour.
- Reimplement the reference game's techniques; never copy its files or assets into this public repo. Paragon and
  other raw third-party assets stay local with acquisition steps and a ledger. Source-first for every asset; Blender
  for animation authoring.
- Every change sits behind a switch that restores the old behaviour.
- `gitleaks protect --staged --no-banner` before every commit. Update `HANDOFF.md`, `BACKLOG.md` and the wiki at each
  phase. Delete superseded builds and evidence this goal produced.

## Done

All of these hold:

1. Every row above meets its "done when", or is recorded as blocked with the reason and what was tried.
2. **Parity with the reference.** A final blind review by Opus critics puts our final film beside the reference
   footage, sides labelled A and B at random, and rates six things separately: lighting and picture, hero model and
   movement, boss animation, weight of impacts, sound, camera. The goal is met when each is rated equal or better.
   Where one is still rated worse, go back and try a different approach; an aspect may be closed as "worse" only
   after three genuinely different approaches, each documented with its clip and the critic's reasons. Never claim
   parity the critics did not give, and never tune a number to pass a gate the picture does not pass.
3. The final build is installed behind Play Veyr.app; a full intro-to-victory film with game audio and a death film
   exist; the localhost page shows reference / start / end for every phase.
4. `HANDOFF.md`, `BACKLOG.md`, a results document under `docs/` and the wiki are updated; superseded builds and
   evidence are deleted; the branch is merged into `main` and pushed.
5. The owner has a short summary: what now matches the reference, what does not and why, and what was spent.
