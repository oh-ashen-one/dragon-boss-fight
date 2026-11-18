# Veyr quality goal — paste into a fresh /goal (2026-11-18)

Current activation prompt. Goal file: `QUALITY_GOAL.md`. The playtest prompt below is closed history.

```text
/goal Close the visible quality gap between Veyr and the reference boss fight by completing /Users/midir/veyr-knight-20261028/QUALITY_GOAL.md in full. Read that file, then the top of HANDOFF.md and BACKLOG.md, AGENTS.md and the wiki page dragon-boss-fight. Verify live repo, build and GPU state before acting. Work on branch fable/quality-goal-20261118 cut from fable/owner-feedback-20261118. Make every routine decision yourself; no routine questions; no deadline.

Phases in this order, each with the checkpoint in the goal file: A the four bugs I saw (foot mesh pinching, camera inside the dragon, dragon floating, knock-down 5 s max); B weight and sound (Freesound CC0 recordings, dragon footsteps, breathing and per-move sounds, shake and dust by impact, whole-spine hit reaction, wide weapon trail); C picture (Lumen, shadow maps, motion blur, relit courtyard that just has to look good, controls box hidden); D camera for a huge dragon and a bigger dragon (test 2.5x and 3x); E the new knight, Paragon Greystone in the dark gold-trimmed skin, with motion-matched movement and buffered rolls; F dragon animation playback (clip speed, two-clip fades, four-foot lock, root motion).

Fixed: hitboxes and difficulty stay in the build 17 band; the dragon never gets smaller; free assets only and no paid generation of any kind; Mixamo for animations only; keep my intro and music; never copy the reference game's files into our public repo, reimplement its techniques.

How: you direct only. Opus and Sonnet builder subagents do all building, Opus critics gate every phase, every spawn labelled and time-boxed. Judge every phase against the reference footage in ~/leshy-reference, not against our own old build alone. Show me a clip from phase A within the first few hours, and after every phase add reference / before / after clips to the localhost page, install the build behind Play Veyr.app and send me two lines. One game or engine process at a time, through the GPU gate, nothing rendered during my 11:00-13:00 ET stream window. Every change behind a restore switch. Commit and push after each verified step; update HANDOFF, BACKLOG and the wiki; delete superseded builds you own.

If Greystone needs my Epic login, leave that as my one step and carry on with F. Don't mark the goal complete until every row in the goal file meets its "done when" or is recorded as blocked with the reason. Then merge into main and push.
```

---

# Veyr playtest goal — paste into a fresh /goal (2026-11-17)

Current activation prompt. The older resume prompt below is superseded history; the long animation research it describes is part of Tier 2 here.

```text
/goal Finish the Veyr playtest backlog in /Users/midir/veyr-knight-20261028/PLAYTEST_GOAL.md so I can play it fully and shoot the video. Read that file, then HANDOFF.md, BACKLOG.md, AGENTS.md and the wiki page dragon-boss-fight. Verify live repo, build and GPU state before acting. Work on branch opus/playtest-goal-20261117 from main. Make every routine decision yourself; don't ask me routine questions; no deadline.

Tier 1 in this order: remove the yellow/red floor attack circles; scale the dragon to about 30 ft against the 6 ft knight with reach, collision, camera and arena clearance following; about 1.3x faster knight and dragon movement with no foot sliding; range- and position-aware random attacks with anti-camping (under the dragon -> takeoff + fire, back-right foot and every other zone covered); much more aggressive pressure; 845 HP starting value, tuned together with aggression. Competent scripted wins stay at 150 s or less in both grips while a passive player dies; if those truly conflict, keep it hard and report the numbers.

When Tier 1 passes, install the new Shipping build behind Play Veyr.app and capture a full intro-to-victory film with game audio plus a death run, then message me that it's ready. Then do Tier 2: sprint start/stop and run/leap foot contacts, light-attack transitions, heal, flight camera, using new approaches only; never revive rejected candidates.

Every change: before/after native film, frames you inspected yourself, blind Opus critic on each Tier 1 item, and the full regression set (controls, intro, showcase 20/20, both-grip victory/restart, death/restart). Keep the approved 8-shot intro, OST and SFX unchanged. Blender for animation, sourced motion first, no paid generations without asking. Follow GPU slot rules, 60 fps, background windowed launches, my processes only. Commit and push after each verified step. When every gate passes, merge into main and push. Delete superseded builds you own, and update HANDOFF, BACKLOG and the wiki. Don't mark the goal complete until every Tier 1 and Tier 2 item meets its "done when".
```

---

# Veyr resume goal — paste into a fresh /goal

This is a reusable activation prompt. Editing this file does not restart the cleared goal.

```text
/goal Resume Veyr from the saved checkpoint and complete /Users/midir/veyr-knight-20261028/MASTER_GOAL.md in full. Read its resume section, then the latest HANDOFF.md and BACKLOG.md; verify live state before acting. Make routine decisions yourself, with no routine questions or arbitrary deadline.

Validate the existing fortress revision and improved heal first, then finish sprint/stop, running and jumping attacks, light-attack transitions, and two-handed recovery/balance. Keep competent victories under 150 seconds in both grips through real combat fixes. Preserve the accepted heavy attacks, wings, fight feedback and audio.

Require watchable before/after footage, actual gameplay checks and blind Opus quality review. Keep deleting obsolete owned builds. Respect the authorised branches, source/credit rules and GPU gates; never merge or push main. Finish every requirement before marking the goal complete, and update/push the handoff and wiki.
```
