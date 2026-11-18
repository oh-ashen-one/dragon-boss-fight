# Veyr playtest goal — 2026-11-17

**Closed by the owner on 2026-11-18** ("mark this as complete for now") and merged into `main`. The owner's view of the
before/after films: "It looks more the same." Blind reviews rated items 1 and 6 "meets", items 2-5, 7-8, 10 and 11
"partly", and the first version of item 9 "fails" (its rework was not reviewed). Deliverables 1-3 were not finished: no
new build is installed and the only full film is from an earlier build of the run. Details:
`docs/playtest-goal-20261117/RESULTS.md`. The text below is the goal as written.

Owner-requested goal: implement every open backlog item, then hand back a build ready for a full playthrough and a recorded video. Baseline: `main` at `d1022c0` (2026-11-06), installed app `~/Applications/Veyr/652188ae51a3/`, dragon 650 HP, scripted one-hand victory 70.1 s. All 12 video2rig dragon move families are on by default.

Work branch: `opus/playtest-goal-20261117` (from `main`). The prompt to start it is in `GOAL_PROMPT.md`.

## Backlog

### Tier 1 — owner playtest notes, 2026-11-05 (blocks the video)

| # | Item | Where it starts | Done when |
|---|------|-----------------|-----------|
| 1 | **Remove the floor attack circles.** The yellow/red rings drawn on the ground that reveal the attack area. | `AVeyrDragon::UpdateTelegraphs` / `DrawFootprint` in `Unreal/Veyr/Source/Veyr/VeyrDragon.cpp` | No warning/danger floor rings in any move, inspected in native frames. Hit detection still uses the footprints. Windup animation, sound and other feedback stay. HUD stays. |
| 2 | **Dragon about 30 ft tall.** It currently reads 12–15 ft next to a 6 ft knight; the knight should feel tiny under its legs. | Imported presentation scale (the `21.558172` reference in `VeyrDragon.cpp`), collision, leg contacts, footprints | First measure the real engine heights of the dragon and knight and record them. Scale the whole creature proportionally to about 5× the knight's height. Hit volumes, leg contacts, attack reach, fire origin, walk stride/speed, flight height, camera framing (lock-on, flight, death) and arena clearance all follow the new scale. Showcase 20/20 with zero frustum misses, and no clipping into fortress walls/towers. |
| 3 | **Faster overall pace.** Knight running and dragon movement feel like about 0.75x. | Knight `MaxWalkSpeed = 580` in `VeyrKnight.cpp`; dragon walk/reposition speed and attack tempo in `VeyrDragon.cpp` | Roughly 1.3x faster for knight run/sprint and dragon travel/turns, with animation play rate matched to travel so feet don't slide. Dragon attack windups are tighter but still readable. Before/after film of the same moves. |
| 4 | **Range- and position-aware attacks.** Pick a random suitable attack as soon as the player is in range. If the player stays under the dragon, it takes off and uses fire to force them out. If the player camps the back-right foot, it uses an attack that actually reaches there. Generalize this to every zone. | Dragon move selection in `VeyrDragon.cpp` | A zone map (front, left, right, under, rear/tail, each foot) where each zone has at least one attack that really reaches it. In-range engage within about 0.5 s of an opening. Weighted random choice with no more than 2 repeats in a row. Being under the dragon for about 3 s triggers takeoff + fire that pushes the player out. Scripted camping tests per zone, including the back-right foot, show the dragon landing hits. |
| 5 | **Much harder, more aggressive boss.** The owner nearly killed it while barely getting hit. It barely moves, attacks or connects. | Post-recovery / post-reposition idle windows added on 11-06 (`1.25 s` / `max(1.25, 3.60 - recovery)`), attack frequency, damage, chaining | Constant pressure: the longest passive gap outside a punish window is about 2 s or less. Chained attacks and follow-ups. A scripted passive/careless player dies. The competent scripted player takes real damage, many hits per fight, not 0–3. |
| 6 | **About 30% more HP.** 650 → 845 as the starting value. | `MaxHealth` in `VeyrDragon.h` | 845 HP to start, then tuned together with #5. Competent scripted victories still finish in 150 s or less in both grips; the old target was never withdrawn. If 150 s and "very hard" truly conflict, keep the difficulty, record the measured times and flag it for the owner. |

Work order: 1 → 2 → 3 → 4 → 5 + 6 (a single balance pass). Scale comes before speed and balance because it changes reach, collision and travel.

### Tier 2 — older open items (after the Tier 1 build is installed)

7. **Knight sprint start/stop foot contacts.** Contact tests fail 0/4; there is a 180° heading reversal at the two-hand run start. Do not revive the rejected v047 / frozen-stride / Turn180_A v4 candidates. Change the transition approach or the source.
8. **Running and leap foot contacts.** All 8 cases fail. Leap capsule lift is 23–24 cm.
9. **Light-attack transitions.** Currently rough between chained light attacks.
10. **Heal animation.** v042 looked better, but blind review said FAIL for shoulder/armpit deformation. Side view and continuous motion are unverified.
11. **Camera.** In flight, the player/weapon look small, faint hazards are flattened, the head overlaps the HUD, and the player is lost during the unlocked upward look.
12. **Owner review aid.** Serve the 12/12 video2rig before/after page (port 8815) so the owner can approve the dragon moves. Only the owner can approve them.

## Hard rules for the goal run

- Keep the owner-approved 8-shot fortress/mural intro byte-identical, along with the single OST, dedicated dragon SFX and single player grunt. If the bigger dragon breaks an intro shot's framing, record before/after and make the smallest possible fix.
- Animation is authored/refined in Blender (repo `AGENTS.md`). Use sourced motion first (Mixamo, Fab, licensed sources). No paid generations without asking the owner.
- Follow the GPU slot protocol and the 60/30 fps caps. Launch windowed in the background, never focused or fullscreen, and only own your own processes. SIGTERM, then wait up to 60 s, before any SIGKILL. Never auto-relaunch after two crashes.
- Every change needs before/after native film of the same moves plus native frames you inspected yourself. Each Tier 1 item gets a blind Opus 5.5 critic A/B. Automated passes do not count as owner acceptance of difficulty or feel.
- After every change, regression gates must pass: controls smoke, full intro, showcase 20/20, one-hand and two-hand victory/restart, death/restart.
- Commit and push the task branch after every verified step. Keep `HANDOFF.md`, `BACKLOG.md` and the wiki (`dragon-boss-fight`) current. Delete superseded builds you own once a newer one is verified.

## Deliverables

1. Tier 1 complete: a new signed Shipping build installed through `tools/unreal/install_shipping.py`, **Play Veyr.app** pointing at it, `Local/LatestShipping.json` updated.
2. A continuous full-fight film with game audio (intro through victory) from the installed build, plus a death run, so the owner can judge recording readiness.
3. Tier 2 items done to the same gates, then a final reinstall and film.
4. Merge into `main` and push once every gate passes (see the prompt). Then clean up owned builds/evidence and run the final wiki update.
