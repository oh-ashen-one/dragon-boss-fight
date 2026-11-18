# Owner playtest feedback and gap backlog — 2026-11-18; NOT STARTED

The owner played today's `main` (`79fe0bc`, packaged, not installed) and asked for the items below to be recorded.
**Nothing here is started; wait for the owner's go.** Side-by-side footage of the reference game (Can It Code's
Leshy fight) and ours: `Local/playtest-goal-review/vs.html` (`python3 serve.py 8823`, then
`http://localhost:8823/vs.html`); reference frames in `~/leshy-reference`.

## Keep as it is (owner, 2026-11-18)

- **Hitboxes and overall difficulty**: "really good". Do not retune.
- **Dragon size**: 2x is fine and "the dragon needs to be much bigger". Never shrink the dragon to fix framing; fix the
  camera for a huge dragon instead. A larger scale needs the reach check on every attack again (fire and swings passed
  over the knight when the scale first went to 2x).
- The reference boss is a humanoid, moose-like creature about two knight-heights tall; ours is a heavy four-legged
  dragon. Copy his techniques, not his proportions.

## What the owner noticed playing the reference game (2026-11-18)

His words, mapped to the items below. Still discussion; nothing started.

- **Sound of the world**: footsteps audible on snow and sand, the hero running, the boss breathing in idle with a
  sound on the floor. (Items 5-7. His footsteps are sorted by surface; the boss idle clip has breath sounds at fixed
  times.)
- **Hero run is fluid, not blocky**; a "slightly overexaggerated" whole-body turn and abrupt stop when reversing
  mid-run. (Item 20: his motion matching has 135/180 degree pivots and stops at four foot phases; ours has turns and
  stops off by default.)
- **Attacks**: screen shake, and "a blurred line that follows the tip of the hammer". The swing is "fluid and fast",
  not "a blocky 90 degree angle attack". (Items 19, 21: full-width smoothed trail, motion blur, blows that turn toward
  the stick and exit into movement.)
- **Hero model** is "a much higher-quality 3D asset. There's no breaking... straight out of Elden Ring".
  **DECIDED by the owner (2026-11-18): replace our knight with Paragon: Greystone** (Epic Games, free on Fab,
  https://www.fab.com/listings/122fd7bf-6f12-4304-a930-cccbbacdaebc), **in the dark skin he picked**: black plate
  armour with gold trim, dark green tabard, sword with a glowing gold edge, shield with a gold glow. His screenshot of
  that skin: `Local/knight-candidates/greystone-owner-pick-20261118.png` (local only). See section G.
  Owner's rules for this: **free assets only**; **Mixamo is for animations only** (its characters "look much
  shittier" than Fab's). Considered and not chosen: "Dark Knight - Female Character" by Hawtor Studio
  (https://www.fab.com/listings/5be9349e-acb1-4a0b-8811-9e999e036755; free, Rigify rig, the most retarget work), Mixamo's
  own knights (rejected on looks), third-party Epic-skeleton knights on Fab (paid, 15-50 USD).
- **Boss room interior and lighting** "looks amazing", "almost looks candlelit"; the building outside is about the
  same as our castle ("80%"). DECIDED by the owner: keep the courtyard and relight it. The light does not have to be
  realistic or have a visible source ("Where is this lighting coming from? There are no candles. That doesn't
  matter. We just need the lighting to look good."). (Item 8.)
- **Intro**: cut from walking into a letterboxed close-up of the boss. "We don't necessarily need that."
- **Weight**: when the boss hits or moves "the camera shakes, and you could feel that he weighs a ton"; the same when
  you hit him. (Items 9, 17: shake by impact speed and distance, dust under feet, whole-spine flinch.)

## A. Bugs the owner saw (fix first)

1. **Foot mesh pinches out sideways.** When the knight hits the dragon from very close, a corner of a foot (the owner
   thinks the right one) stretches far out to the right. Suspects to bisect: the stance clean-up foot hold
   (`-VeyrNoStanceCleanup`), the per-leg stagger, the six rig bones with no skin weight.
2. **Camera goes inside the dragon.** Very close to the body the camera clips through and shows the inside of the
   mesh. "That should never happen." Needs camera collision against the dragon's body volumes (pull in fast, release
   slowly, rise against large bodies) and a near-plane check at 2x and above.
3. **Dragon floats above the floor**, about 3 ft by the owner's eye. Measure sole height per clip at the shipped scale
   (the video-to-animation rest pose is known to sit 18 cm high at 1x) and ground every clip.
4. **Knock-down lasts far too long.** From the moment the dragon drops after a stagger to the moment it is back up:
   5 seconds at most. Today the exposed phase alone is 7 s (`ExposedSeconds`, `VeyrDragon.h:156`) plus the fall and rise
   clips.

## B. Sound (owner: "We need better sound for sure")

**Status 2026-11-18: PAUSED by the owner before anything reached the game** ("I don't want you to start anything yet. I
still want to be discussing what we're going to be doing"). Owner's direction so far: use free Freesound recordings as
the reference game did; Higgsfield or Fish Audio only where no recording fits. What exists, none of it wired in:
`tools/audio/freesound_candidates.py` (public CC0 search, no account) and `tools/audio/recorded_set_plan.json` fetched
about 100 candidate recordings for 20 cues into `Local/AudioSources20261118/` with a provenance ledger;
`tools/audio/prepare_recorded_set.py` (uses the Earshot analysis tool in `~/.cache/earshot/venv` to drop downloads that
do not sound like their label and to cut variants) was stopped after two cues. `VeyrAudio.cpp` is unchanged; the partial
`Content/Audio/Recorded20261118/` folder is not loaded or staged. When this resumes it goes to builder subagents with an
Opus critic, not the directing session, and the owner hears an old/new audition page before a build.

5. **Replace the placeholder sounds**: "too many basic beeps, dings". Several cues are sine tones generated in code
   (`VeyrAudio.cpp`, `Tone(...)`); the recorded set is about 22 short files with one contact sound and one swing.
   `Data/dragon/sounds.json` is an empty stub, so no dragon move has its own timed sound and the dragon has no footsteps.
   Owner, later on 2026-11-18: Higgsfield is gone; generation goes through fal.ai (key in
   `~/.config/fal/secrets.env`) or Fish Audio, only where a free recording or existing clip does not do the job.
   Budget and terms: `QUALITY_GOAL.md`.
6. Sources to use, in this order: real recordings (Freesound CC0, as the reference game did); the audio tracks of our
   own Seedance dragon clips (generated with audio on, already paid for) as the dragon's voice; generated effects from
   fal.ai or Fish Audio where no recording fits (one job at a time, within the goal file's budget); a Suno fight track as a candidate.
7. Play sounds from clip time per move (voice from the head, body and footfalls from the contact point), with several
   variants and random pitch per event, sorted by surface.

## C. Picture: features the reference has on and ours has off

Why they are off: the first native Unreal commit (`8430d78`, 2026-10-18) created `DefaultEngine.ini` with a
lightweight prototype renderer and no reason recorded; `docs/canitcode-enhancements.md` (2026-10-28) listed turning
them on and it was never done.

8. Turn on Lumen global illumination and reflections, virtual shadow maps, auto exposure and motion blur; let the
   arena's lights cast shadows; remove the flat fill lights. Measure the frame rate on this Mac before and after.
9. Add Niagara effects (the project has none): dust under each foot sized by contact speed, hit bursts in three sizes,
   debris, fire. Take free Fab/Epic systems first.
10. Hide the always-on controls box after the first seconds.

## D. Camera for a huge dragon

11. Lock-on aims at the chest, eases in about a third of a second, and keeps the knight and the striking limb in view;
    mouse movement must not drop the lock for 1.8 s.
12. Position lag, a pull-back and wider lens when sprinting, a small lean into turns. Today lag is forced off.

## E. Dragon animation playback

13. Play the video-to-animation clips at their own speed and shorten only the holds; today most phases run 2-4x and the
    1.3x pace multiplies again. Difficulty must stay where the owner likes it: re-check the 16-seed numbers.
14. Cross-fade two running clips over 0.3-0.4 s instead of blending from a frozen pose in 0.12 s.
15. Lock all four feet to the floor at runtime and pin them in the clips; replace the pre-strike snap turn (rotates the
    whole body under planted feet) with turn clips or a spine twist.
16. Move the dragon along each clip's own root track; add a charge, a leaping strike and one authored multi-hit combo
    (new clips, 35 credits each, owner's budget OK first).
17. A stronger hit reaction: the whole spine rocks and dips, the flash is on the mesh.
18. Pipeline: train the dense reader (about 4 h GPU, no spend), merge upstream's whole-clip fit into the fork, test a
    side|top start picture for tail and turns, drop the 55 % wing re-base where it hides the video's motion.

## F. Knight

19. Buffer the roll and let it interrupt actions; attacks turn toward the stick.
20. Locomotion by motion matching (Unreal Pose Search with Epic's free Game Animation Sample, retargeted) instead of
    about six looping clips; sourced turns, starts and stops on by default until then.
21. A full-width weapon trail; more impact variety (sparks, floor hits on a miss, a short slow-motion tail on heavies).

## G. New knight: Paragon Greystone (owner's pick, NOT STARTED)

22. Acquire "Paragon: Greystone" from Fab with the owner's Epic account (free; Epic's own listing). Confirm the terms
    shown at download. The PARAGON name may not be used to name or advertise the game. Epic's raw files stay out of
    this public repository (same rule as the current character content: local only, with acquisition steps recorded).
23. First a one-day trial, then show the owner a clip before anything else: the chosen dark skin in the game's light
    beside the current knight, with idle, run, one attack and one roll.
24. Retarget our clips (Mixamo sources refined in Blender) onto Greystone's Epic skeleton with one retarget setup;
    redo the hand fixes (sword grip, planted feet) and rerun the grip and foot-contact proofs. Keep the current knight
    behind a switch until the owner accepts the new one.
25. Design points to settle with the owner before building: Greystone carries a **shield**; our knight has one sword
    with a one-hand / two-hand grip switch and a guard. Does the shield stay (guard with the shield, drop the two-hand
    grip) or is it hidden? Which sword: his or our current one? Capsule, camera height and attack reach need a
    re-check for his proportions.
26. This also sets up item 20: Epic's motion matching sample uses the same family of skeleton.
27. Still to do before or during the trial: the direct comparison of the reference hero and ours in Blender (why
    ours "breaks"), so the same fault is not carried over.


# Playtest goal closed — 2026-11-18

The owner closed the 2026-11-17 playtest goal after watching before/after films ("It looks more the same") and had the
branch merged into `main`. All six Tier 1 changes and the Tier 2 foot-contact, heal, chain and flight-camera changes are
in source behind restore switches; none is owner-accepted and no new build is installed. Numbers, blind-review verdicts
and what stays open: [docs/playtest-goal-20261117/RESULTS.md](docs/playtest-goal-20261117/RESULTS.md). State and
switches: top of [HANDOFF.md](HANDOFF.md).

# Latest owner feedback — 2026-11-05; documentation only

Six new OPEN / NOT STARTED requirements are recorded at the top of [HANDOFF.md](HANDOFF.md): faster player/dragon movement; much harder aggression; range/position-aware attacks and anti-camping; remove the yellow/red floor attack-radius circle; approximately 30% more dragon HP; and a roughly 30-ft dragon that dwarfs the player. The owner explicitly said **do not fix anything yet**. Earlier delivery/testing results below are historical and do not imply acceptance of the current difficulty or scale.

# Playable wrap-up delivered — 2026-11-05

The owner ended the long-running goal and authorized consolidation into main. The current accepted play profile was compiled and passed controls, full intro, both-grip victory/restart checks. Unfinished movement and camera experiments remain disabled; the items below are future work, not an active autonomous goal. See HANDOFF.md and `docs/wrapup-20261105/verification.json` for the current playable handoff.

# Native trial and blind verdict — 2026-11-05

v047 is now imported as an inactive trial and tested in a Shipping build. Exact run-to-stop entry is continuous, and two transition peaks improved, but all4 full movement cases still fail contacts. Blind Opus prefers the earlier brake's plant/settle and the new trial's sprint carry; neither is shippable. No default promotion. Next retain those strengths while repairing grip/clearance and actual native contact/start-turn failures. Native movies are queued behind STREAMING; see HANDOFF.md for the sole live handle. Source-only/prepared-only descriptions below are historical.

# Current source/native-preparation checkpoint — 2026-11-05

The latest two-hand source pair is V17/PairV18. Actual running boot support now exists on both feet, with measured support windows below60cm/s; late-stop marker checks still fail. Current/earlier source movies are watchable at `#placement` and history links. V13's marker-only false pass is import-blocked. No new gameplay animation is active.

A shared-prefix native representation is prepared as v047, but remains diagnostic-only and unimported. Next is a properly isolated native-trial route/controller and real gameplay comparison, preserving all import/activation safeguards. Do not keep mistaking source fidelity for completion. One-hand/start/turn/running/leap/light, camera and final full-build gates remain open; exact current state is HANDOFF.md and the requirement ledger.

# Source footage and weapon adaptation — 2026-11-05

Matched run/stop source movies are available at `#contiguous`; the two-handed full-source adaptation is saved and independently checked. Neither is enabled in gameplay. Two whole-body support corrections failed their unchanged bounds and are stopped; next use supporting-leg contact correction. Final source/native contacts, weapon playback and blind quality review remain open. See HANDOFF.md for exact artifacts; all previous queued jobs are now terminal.

# Exported locomotion pair — 2026-11-05

The contiguous ACCAD run/exit pair is now saved and independently verified for shared entry poses and loop seam. It remains unaccepted: one fixed-reference foot window still exceeds60cm/s, and running boot-support coverage needs improvement. Matched source rendering and two-handed adaptation are queued in one owned Blender process; no new gameplay motion is enabled. Exact live handle and evidence are in HANDOFF.md.

# Locomotion source follow-up — 2026-11-05

New approach: derive a run/stop pair from the same ACCAD capture. Untrimmed fitted and boot-corrected Blender sources are saved; pair extraction is queued and unverified, weapon adaptation/native gameplay/films/Opus remain open. Source screening still has one62.110cm/s right-foot window over the unchanged60cm/s limit. No new animation is enabled. See HANDOFF.md for the live handle.

# Camera follow-up — 2026-11-05

- Flight camera candidate wins its first blind Opus comparison for visible roar/flame/descent. It remains opt-in: player/weapon scale, ground warnings, sky-pitch player loss and final continuous/manual/collision/performance checks are open.
- Same-build one-hand victories74.932s before /74.926s after, unchanged650HP/damage. Four-charge heal and player-death/restart regressions pass; representative stills inspected. Final both-grip balance/full-game acceptance remains open.
- Approved eight-shot fortress intro unchanged. Complete silent before/after camera films are on the bare review page at `#threat`. Handoff and `threat-camera-gameplay.json` hold exact evidence.

# Current backlog status — 2026-11-05

Full MASTER_GOAL remains active and incomplete. These current facts supersede historical implementation plans below; preserve the eight original playtest notes as context.

- Accepted/scoped: exact owner-approved R5 opening tour; heavy attacks, wider idle wings, feedback/settings and chosen audio; recovery contact/Opus pass, prior41.24s2H and74.99s1H wins at650HP. Newest prior-default controls smoke passed. Final build regressions remain.
- Follow-up: the run-start completion speed dip is repaired and checked against actual displacement. Two stop-matcher revisions still fail contact gates; the next step must change transition approach or source. Newest controls smoke passed with movement experiments disabled.
- Sprint/start/stop/turn: source ACCAD two-hand run-start won its first blind Opus round for a native trial, imported as v046 and now has a real opt-in gameplay state. Start/handoff/release/attack-cancel mechanics work, but same-app contact tests still fail0/4. Entry turns and stopping joins need repair. One-hand start and source-review shoulder/grip/weight/clearance caveats remain.
- Running/jumping: fresh8-case test fails all foot-contact gates; actual leap capsule lift23–24cm is now observed. Three one-hand capture trials are too sparse for acceptance review. Running-entry and leap contacts remain unfinished.
- Still open: light transitions, healing/camera continuity and tall/airborne threat readability; final both-grip balance/wins; all-move/settings/collision/performance tests; final verified Shipping installation/launcher/pointer.
- Grounded Mixamo Turn180_A v4 remains stopped after its first blind tie. Do not revise/import/promote it without new direction.
- Music scope is ONE supplied OST, dedicated dragon SFX and ONE player hit grunt. Older multi-track/generation suggestions below are superseded. No human TTS dragon imitation.

See HANDOFF.md for exact builds, films, evidence and next steps. A source/fidelity check or a visibly preferred trial does not close a full requirement.

# Veyr backlog (owner playtest feedback, 2026-10-31)

Owner played the v030t Shipping build (`Builds/Unreal-Mac-20261031T171249Z`) on 2026-10-31 and said it is "looking much
better now". These are his notes for the next session, in his order, with the facts checked in code on the same day.
Start with `HANDOFF.md`, then pick items here. Each item needs a before/after the owner can watch (bare page: video plus
BEFORE/AFTER label, no text walls) and a blind Opus critic before it is called done.

## Latest checkpoint — 2026-11-04

- **Owner approved the R5 fortress/mural tour and requested it as the pre-fight loading presentation. Preserve its exact eight shots.** Production full playback and skip/death/retry tests pass. The first-walk texture fix is packaged but its capture is waiting for GPU capacity; integration review remains open.
- Healing v042 won matched front/side blind pose review and is enabled. Four-charge resource checks pass on the fortress. Normal-camera framing and continuous-motion acceptance remain open.
- Released two-hand attack recovery now has real victory evidence: 45.923s two-handed and75.623s one-handed on the same candidate build, unchanged650HP/damage. Recovery remains opt-in pending contact and blind review; these are not final balance measurements.
- CPU diagnostics suggest full-boot contact correction can reduce drift, but project AGENTS.md requires actual Blender authoring. Versionv043 is explicitly diagnostic-only and import-blocked. Blender authoring/review recipes forv044 are prepared but unexecuted. Runtime starts/stops/turns remain unfinished.
- Running-attack CPU diagnosis identified an added0.30s standing join. Its removal must be authored and inspected in Blender; the corresponding recipe is prepared, not executed. Comparison code compiles/defaults off. Native contacts, visual review, interrupts and leap landing/contact work remain open.
- Remaining light-foot transitions, final both-grip<=150s wins, settings/camera/collision/performance and whole-build regressions remain open. Exact active job, evidence and retained builds: HANDOFF.md top. No additional paid generation in this pass.

## New map requirement — owner-approved presentation, final regression pending

Built-in image references, five browser-generated Tripo assets and four distinct secular murals are integrated into the gothic fortress/war-court. The owner explicitly approved the R5 tour on2026-11-03 and asked to retain it before combat. Earlier rejected map rounds are historical evidence, not a direction to redesign the approved R5 scene. The exact tour is now the skippable production intro. Remaining scope: handoff rendering, independent integration review, readable combat cameras, collision and performance on the final Shipping build. MASTER_GOAL.md retains the complete map and combat scope.

## Audio scope update — 2026-11-03

Owner selected one supplied OST plus dragon vocals and one player pain moan. The human-voice Fish dragon source was rejected on 2026-11-03 and replaced with dedicated CC0 creature-library effects. Fish remains only for the single human hit grunt. Runtime audio checks pass; actual replacement auditions and before/after are on port 8812 /dragon-replacement/. Subjective listening remains owner acceptance. The earlier request for a full newly generated music/SFX suite is superseded by this narrower audio direction. Animation backlog is unchanged.

## Continuation status — 2026-11-02

- Item 7: accepted fight-feel revision preserved, including persistent settings.
- Item 4: new default build victory **78.793 s one-hand / 25.145 s two-hand**, unchanged 650 HP; death/restart checks pass. Human balance acceptance remains open.
- Item 3: all 20 moves freshly filmed with wider idle wings; native coverage passes.
- Item 8: Mixamo downward two-hand heavy/finisher won blind Opus review and is default. Kevin rejected after two failed revisions. Jump/run assets imported but disabled: landing/startup contact failures remain. New heavy passed contact scope; broad primary test still has one old-light foot failure.
- Item 2: half-spread idle wings won blind review; default. Original breathing curves preserved exactly; subtle breathing not independently visible in sampled critic frames.
- Item 1: sprint/stop unfinished; failed contact experiment off. Correct forward run and stop sources acquired.
- Item 5: sourced heal passes resource mechanics, but first blind pair was inconclusive due framing. Second closeup critic BOTH FAIL: no convincing cup tip; disabled.
- Item 6: free licensed audio cues and timing/mix candidate implemented, disabled pending listening acceptance.
- Full goal incomplete. Current review/build paths, cleanup and exact failures: HANDOFF.md. Descriptions below preserve original playtest context.

## 1. Knight running feels blocky, not like a sprint
- Owner: "the running still feels a bit blocky. It doesn't feel like you're actually sprinting, and it doesn't seem too fluid."
- Runtime run clips: Run / RunAlternate / RunTwoHand (approved Fab run v18 family, see `docs/knight-complete-20261028/local-assets-provenance.json`), RunStop join 0.30 s.
- Look at: sprint speed vs clip stride (foot slide), Shift-sprint state (separate sprint clip or only a rate bump?), lean/acceleration, camera FOV/lag at sprint, run-start/stop blends. Source-first: Mixamo/Fab sprint candidates before any authoring.

## 2. Dragon idle: wings cramped against the body
- Owner: "In the idle animation for the dragon, his wings are super cramped against his body."
- Idle is owner-approved (2026-10-28) but the folded wings now read wrong in play. Fix as a wing-spread layer or a new idle take; keep the breathing. Dragon tooling: `~/dragon-boss-fight` branch `claude-code-enhancements`, `tools/dragon_refine/`, move data `tools/movedata/run_veyr.sh`.

## 3. Playthrough that shows every dragon animation
- Owner: "I don't think I saw all of the animations the dragon had. We need a playthrough where you get to see each individual part as it goes."
- Build a scripted replay mode (like `VeyrReplay` lockon/blendproof) that walks the dragon through every move and state in order: Fire, FlyAway (takeoff, hover, fire-down, air-land), ClawSwipe, BackStomp, TailSmack, Bite, Buckle, Collapse, Exposed, Rise, Dead, plus idle, walk/turns, roar. Record it as one video with a small move-name caption and serve it on a bare page.

## 4. Fight too long: 2.5 minutes max
- Owner: "The dragon has too much health, and it takes forever to kill him. It should be a 2.5-minute boss fight max."
- Baseline at the owner playtest: `AVeyrDragon::MaxHealth = 2800` (`Unreal/Veyr/Source/Veyr/VeyrDragon.h:115`). Knight damage 28 / 62 per light hit (1H / 2H), heavy 43.4 / 96.1 (see `docs/handoffs/HANDOFF-codex-v030-chain-20261028.md`). 2800 HP is about 100 one-hand light hits.
- Tune health (and/or damage, stagger/exposed multipliers) so a competent player wins in at most 150 s; measure with the `victory` replay and an owner playtest. Update the gates that assume the old fight length.

## 5. Knight drinking-cup (heal) animation is bad
- Owner: "For the player, the drinking cup animation is really bad."
- Heal clip + `ApprovedHealCup` prop in `VeyrKnight.cpp`. Source-first: find a drink/potion motion (Mixamo "drinking", Fab), retarget, fit the cup to the hand, keep heal timing and stamina rules.

## 6. Music and sound effects for the whole game
- Owner: "We have fish audio and the Higgsfield MCP, and we need to add background music and sound effects to the entire thing."
- Now: `VeyrAudio.cpp` plays raw PCM from `Unreal/Veyr/Content/Audio/Overhaul/` (Music, Ambience, Blink, Break, Breath, Contact, Fire, Footstep, ...) through procedural sound waves. Treat it as placeholder.
- Generate a boss theme (intro / loop / final phase / victory) and per-action SFX (sword swings light/heavy, hits on scales, blink whoosh, roll, footsteps on stone, armour clank, heal gulp, dragon roar/bite/stomp/wingbeats/fire/landing, UI). Owner tools: Fish Audio and the Higgsfield MCP (audio generation). Spend: one generation at a time, review, then the next (`feedback_generate_one_at_a_time`); log every spend. Mix so combat feedback is never masked by music.

## 7. Camera shake and fight feel (missing)
- Owner: from the video2rig/Unreal reference repo "When the dragon was hit, landed really hard, or during the boss fight, it shook the camera. Do we also have that or not? I don't think we have that."
- Checked 2026-10-31: **we do not have it.** No camera shake, hit-stop or flinch anywhere in `Unreal/Veyr/Source/Veyr/` (grep for CameraShake/Shake: no matches).
- Reference: shared-brain `boss-fight-blueprint` (fight-feel system: hit-stop, shake by weight, flinch, hit flash, weapon trail, dust tiers) and its `references/hero-runtime.md` (`UWardenCombatFx`, blow weights, hit-stop times, shake amplitudes). Resolve with `~/.config/devin/brain/bin/brain resolve boss-fight-blueprint`.
- His code is on the Studio (study/use licence, never commit or mirror it): `~/Downloads/BossFight-Unreal-Project`. Shake and hit feel live in `Source/BossFight/FirstPerson/WardenCombatFx.{h,cpp}` (player side), `Source/BossFight/Boss/BossFighter.{h,cpp}` (boss contacts), `Source/BossFight/Boss/BossIntro.cpp` (intro), tunables in `Data/leshy/effects.json`. Blueprint numbers (`boss-runtime.md`): shake on body contacts from 4 m/s, full at 30 m/s, 0.8-2.4 deg, 0.3-0.7 s, falloff 5000 cm; hit-stop 50-120 ms; slow-mo back to speed after heavy blows.
- Why it is missing: it was step 6 of the Veyr plan (`veyr-application.md`, order of work) and the dragon HANDOFF has listed "fight-feel system: not started" since 2026-10-28; every session since worked on animation clips (steps 2-4) and nobody picked it up.
- Add: shake on dragon landings, stomps, tail hits, roar, heavy knight hits and knight damage, scaled by weight and distance; short hit-stop on connects; keep it subtle and add a settings toggle.

## 8. Knight attacks are boring: source better ones
- Owner: "the attack animations for the knight are pretty boring. Let's go on like Fab ... and look for some two-handed heavy attacks, jumping attacks, and better attacks as well."
- State: v030t took five round-A1 winners (`docs/knight-complete-20261028/attacks-20261031/ab-a1.md`); blind critic says none ship. The two-hand attacks are arm-only because every local Mixamo source is one-handed.
- Do: search Fab (free listings only), Mixamo (Great Sword pack; the owner asked on 2026-10-31 to go and source these, downloads use his own Mixamo/Fab login in Chrome), and the wider free sources in the `animation-sourcing` playbook for two-handed greatsword heavies, jumping/leaping attacks, running attacks and stronger light chains. Stage candidates on a bare localhost page for the owner to pick (source-then-pick), then retarget, fit the blade, set damage windows, blind A/B, import as the next KnightB version.
- Also still open from A1: recoveries that retrace the strike or hold still; LightAttack wind-up as fast as the strike; LightCombo blade dips below the floor; two-hand thrust freeze; one-hand light-light-heavy chain now 3.95 s (was 3.28 s).

## Also open from earlier passes
- Owner approval of the shadow-dash blink and v030t attacks (he has played it).
- Engine crossfade foot skating (`docs/knight-complete-20261028/blendproof-footgate-diagnosis.md` section 5).
- Dragon: rise-from-lying v1 near wing needs hand-keying (frames ~60-90); roar/collapse/air_land v6 retries (see `~/dragon-boss-fight` HANDOFF).
