# Playtest goal results (closed by the owner on 2026-11-18)

Branch `opus/playtest-goal-20261117`, merged into `main` on 2026-11-18 at the owner's request.

**State at close.** The newest build ("build 18", `Local/package-20261118T140119Z`, source `e9fcb8a`) is packaged but
**not installed**: Play Veyr.app still launches the 2026-11-06 build. Build 18's own rendered regression, film and
16-seed numbers were cut off when the owner asked for all game instances to be stopped. The numbers below are from
build 17, which has the same gameplay code; build 18 only turns one camera option (near-boss framing) off by default.

**Owner's verdict on the before/after films (2026-11-18):** "The before and after isn't really that crazy. It looks
more the same." Nothing here is owner-accepted. Difficulty and feel are the owner's call.

## How the numbers were measured

- **Timing gates** come from null-renderer runs of the packaged app (`run_native.py --headless`): the same game code at a
  clean 60 fps, no window, no GPU. Each fight is one process. These processes still show up as running apps on macOS.
- **Rendered runs** give frames, films and the functional regression. Each evidence screenshot stalls one frame by about
  0.1 s, which costs the scripted player hits; `-VeyrStillInterval=2` reduces that.
- Fights are chaotic: a one-line change gives a different fight on the same seed. Balance was judged on 16 brain seeds
  per grip (`-VeyrBrainSeed=N`; replays default to 20261117, normal play seeds from the clock).
- The scripted player is frame-perfect at rolling out of strikes. Almost all the damage it takes is from tramples, the
  fire jets and landings. A person will be hit by strikes far more often.

## Measured (build 17, clean 60 fps, 16 seeds per grip)

| Gate | Result |
|---|---|
| One-hand scripted fights | 15 wins, all within 150 s (50-141 s, median 88 s); 1 death (the default seed); 4.4 hits taken on average |
| Two-hand scripted fights | 16 wins, all within 150 s (57-103 s, median 73.5 s); 4.6 hits taken on average |
| Passive player (stands in front, never dodges), 4 seeds | dies in 7.5-11.8 s |
| Passive player at the entrance, 27 m away | dies in 14.6 s; the opening fire breaths land |
| Camp test, 9 boss-relative zones | every zone hit within 3.9 s; under the belly: takeoff after 3.4 s |
| Longest boss idle | 2.15 s, and only after a string the player avoided completely |
| Showcase (every dragon move, framed) | 20 of 20 segments |
| Contact proof: sprint start/stop, running and leap attacks, light-attack taps | 4/4, 8/8, 4/4 (were 0/4, 4/8, 4/4); base set 2/9 (was 0/9) |

Old behaviour switched back on (build 16, before the one-hand chain change): one-hand win 86 s and two-hand 56 s with
0 hits taken; a passive player survives 49 s; the camp test leaves the underbelly and a flank unanswered.

Rendered regression: build 16 passed two-hand victory/restart, death/restart, camp, controls, full intro and showcase
20/20; its plain one-hand run died once and ran 163.6 s once, and its filmed one-hand run won in 95.2 s. Build 17
passed one-hand (79.8 s), two-hand (82.0 s) and death before the runs were stopped. Raw records: `data/b17-headless.json`.

One process slip to know about: clearing old evidence folders removed the launch receipts the hourly launch budget
counts, so more than 10 rendered launches ran inside one hour on 2026-11-18. Do not delete evidence younger than an hour.

## What changed

- **Floor rings** hidden (`-VeyrFloorTelegraph` restores).
- **Scale** 2x: idle head 1546 cm against a 244 cm knight (`-VeyrDragonScale=1`).
- **Pace** 1.3x: sprint 754 cm/s, run clip at 0.92 of its authored speed (`-VeyrLegacyPace`).
- **Brain** (`-VeyrLegacyBrain`): weighted random choice among strikes whose measured contact reaches the player;
  strings of 1-3 blows; a late snap turn onto the player; whiff punish (1.35-2.15 s opening after a fully avoided
  string, 0.6-0.9 s after one that connected); takeoff and hunting fire for the underbelly (2 s fuse), for the pocket in
  front of the chest that no strike reaches (4 s fuse, at most every 28 s, a walk-through in between) and for any close
  spot held 10 s; a knock-down ends early after 200 damage; leg stagger per opening (one-hand 25/45, two-hand 16/28).
- **Fire aim**: at 2x the fire left the mouth about 11 m up and passed over the knight, so it could not hit. The neck
  now pitches the jet onto the player's range.
- **Health** 845 (`-VeyrBossHealth=650`).
- **Stance clean-up** (default on, `-VeyrNoStanceCleanup`): a foot that is down is held within a 10 cm budget; a low
  foot that has to travel is lifted into a step.
- **One-hand chain flow** (default on, `-VeyrNoChainFlow`): a held chain cuts from each follow-through into the next
  raise. Not filmed or reviewed in its final form.
- **Flight framing** (default on, `-VeyrNoFlightFraming`): 90 degree lens in flight, upward look capped at 40 degrees.
  On film the knight's centre is in view for 58 % of a flight, was 9 %.
- **Near-boss framing** is opt-in (`-VeyrBossNearFraming`): it made the knight too small for little gain.
- **Heal** v11 "sip" fit imported as knight `v050heal` (character content is local only, not in the repository).
- **Bug fixed**: below 25 % health the boss cannot fly, but the armed anti-camp answer still cut every opening to
  0.15 s, which locked it into an endless stomp/tail loop.

## Blind reviews (Opus 5.5, high; sides labelled A/B at random)

| Item | Better side | Confidence | Verdict | What the reviewer still wants |
|---|---|---|---|---|
| 1 Floor rings | new | high | MEETS | nothing |
| 2 Dragon size | new | high | PARTLY | head 6.3 knight-heights (was 3.1); the close camera shows legs and belly in wind-ups and crops the knight |
| 3 Pace | new | high | PARTLY | exactly 1.30x; stills cannot prove the planted foot holds; camera clips into the 2x dragon up close |
| 4 Attack choice (two rounds) | new | high | PARTLY | every zone hit within 5.6 s (old: four zones safe); the attack log mislabelled fire-from-the-air hits (fixed afterwards) |
| 5 Aggression (final numbers) | new | high | PARTLY | clearly harder, but a frame-perfect script losing 1 fight in 32 is "not genuinely very difficult" yet |
| 6 Health (final numbers) | new | high | MEETS | thin margin: slowest one-hand win 141 s |
| 7-8 Sprint and running-attack contacts | new | medium | PARTLY | contact test 4/4 against 0/4, no frozen leg; cropped frames cannot settle "fluid or blocky" |
| 9 Light-attack chain, first version | tie | high | FAILS | both sides reset to a standing pose for 0.25 s between cuts; the reworked hand-over was not reviewed |
| 10 Heal (three rounds, v10) | new | high | PARTLY | rim at the mouth, continuous drink; weak grip on the handle and pale elbow streaks are the unchanged asset |
| 11 Flight camera (two rounds) | new | high | PARTLY | knight's body in 8 of 8 flight frames (was 2 of 8); the dragon's head sits under the boss bar in 3 |

## Open at close

- Install build 18 (or a newer package) with `tools/unreal/reinstall_shipping.py`, after its rendered regression.
- Film build 18 and review the reworked one-hand chain.
- The camera at 2x: wind-ups are hard to read from under the dragon, and the camera can clip into its body.
- The pocket in front of the chest has no strike of its own; a close strike would need a new dragon animation.
- Whether it is hard enough is undecided. `-VeyrBossHealth=N` and the opening lengths in `VeyrDragon.cpp` are the knobs.
- The `healing` replay fails its last check because the aggressive boss damages the knight during the trial.
- The owner found the visible difference small. The largest visible levers left untouched are the dragon's own
  animations and the camera; both need a new approach, not more tuning of the above.
