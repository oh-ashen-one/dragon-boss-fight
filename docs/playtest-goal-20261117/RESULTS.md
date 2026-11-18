# Playtest goal results

Branch `opus/playtest-goal-20261117`. Build under test: `Local/package-20261118T105325Z` (Shipping, "build 14").
Nothing here is owner-accepted; difficulty and feel are the owner's call.

## How the numbers were measured

- **Timing gates** come from null-renderer runs of the packaged app (`run_native.py --headless`): the same game code at a
  clean 60 fps (mean frame 0.0167 s, p95 0.0172 s), no window, no GPU. Each fight is one process.
- **Rendered runs** provide frames, films and the functional regression. Each evidence screenshot stalls one frame by
  about 0.1 s, and on 2026-11-18 the GPU was shared with another session's training job, so rendered fights ran at
  35-60 fps. The scripted player dodges on a 0.32 s cue, so stalls cost it hits. Rendered times are reported, but the
  timing gate is judged on the clean runs.
- Fights are chaotic: a one-line change gives a different fight on the same seed. Balance was judged on 16 brain seeds
  per grip (`-VeyrBrainSeed=N`; replays default to 20261117, normal play seeds from the clock).
- The scripted player is frame-perfect at rolling out of strikes. Almost all the damage it takes is from tramples, the
  hunting fire jet and landings. A person will be hit by strikes far more often.

## Tier 1, measured (build 14, clean 60 fps)

| Gate | Result |
|---|---|
| One-hand scripted win, default seed | 106.1 s, 4 hits taken, 1 heal |
| One-hand, 16 seeds | 15 wins and 1 death. 11 wins within 150 s (81-148 s), 4 wins at 158-180 s. Median win 126 s; 7.6 hits taken on average |
| Two-hand scripted win, default seed | 71.4 s, 5 hits taken |
| Two-hand, 16 seeds | 16 wins, all within 150 s (57-119 s, median 71 s); 4.6 hits taken on average |
| Passive player (stands in front, never dodges), 4 seeds | dies in 7.5-11.8 s; 4 blows, 4 land |
| Passive player at the entrance, 27 m away | dies in 14.6 s; both opening fire breaths land |
| Camp test, 9 boss-relative zones | every zone hit within 3.9 s; under the belly: takeoff after 3.4 s, first hit 2.6 s |
| Longest boss idle | 2.20 s, and only after a string the player avoided completely (the punish window) |
| Showcase (every dragon move, framed) | 20 of 20 segments |

Same build with the old behaviour switched back on:

| Run | Old behaviour | New |
|---|---|---|
| One-hand win (all five switches back) | 83.1 s, 0 hits taken | 106.1 s, 4 hits |
| Two-hand win (all five switches back) | 56.3 s, 0 hits taken | 71.4 s, 5 hits |
| Passive player dies after | 49.3 s | 7.7 s |
| Old brain and 650 HP at the new size and pace: one-hand / two-hand win | 61.3 s / 20.7 s, 0 hits | as above |
| Camp test with the old brain | under the belly never answered (first hit 25 s); left flank safe | all zones pass |

The 150 s limit and "very hard" pull against each other for the one-hand grip. The default-seed run and the median are
inside the limit, but 4 of 16 seeds run 158-180 s and one is a death; those are the fights where the scripted player
is hit most. The difficulty was kept, as the goal says. Raw records: `data/b14-headless.json`.

## What changed in the boss (items 4, 5, 6)

- **Random suitable attack in range.** Weighted random choice among the strikes whose measured contact reaches the
  player's position or lead position; never three of the same in a row.
- **Whiff punish.** A string the player avoided completely leaves a 1.35-2.15 s opening (longer after consecutive
  clean dodges). A string that connected is pressed home after 0.6-0.9 s.
- **Strings.** 1-3 blows per string (more threes below half health), 0.2-0.45 s between blows.
- **Late snap tracking.** The wind-up turns onto the player in a short snap timed to end as the blow starts (up to
  30 degrees), and keeps turning toward a player who has left the original arc.
- **Anti-camp.** Under the belly for 2.5 s: takeoff and a hunting fire jet. The pocket in front of the chest and around
  the fore paws, which no strike physically reaches, is treated the same way on a 4 s fuse (at most one such takeoff
  every 40 s; in between the dragon walks through the player). Any close spot held 10 s without being hit: the same.
- **Knock-down cap.** After 200 damage to the exposed head the dragon rises early, so one knock-down no longer decides
  the fight (two-hand used to deal about 450 in one window).
- **Leg stagger per opening.** One-hand light/heavy 25/45, two-hand 16/28: both grips bring a leg down after about two
  good openings on it.
- **Fire aim.** At the new size the fire left the mouth about 11 m up and pointed level or upward, so it passed over a
  knight on the ground and could not hurt him. The neck now pitches the jet down onto the player's range and follows it.
- **Health** 845 (650 behind `-VeyrBossHealth=650`).
- **Bug fixed.** Below 25 % health the boss cannot fly, but the armed anti-camp answer still cut every opening to
  0.15 s and blocked strings. That locked it into an endless stomp/tail loop (a 480 s stalemate on one seed).

## Known limits

- The pocket in front of the chest and beside the fore paws has no strike of its own; it is covered by takeoff, trample
  and walk-through only. A dedicated close strike would need a new dragon animation.
- Two-hand fights are about half as long as one-hand fights, as they were before this goal (41 s vs 75 s at 650 HP).
- Wind-up snap turns pivot the 30 ft body by up to 30 degrees in about 0.15 s without a stepping animation.

Rendered regression, before/after films, blind reviews and Tier 2 are recorded below as they complete.
