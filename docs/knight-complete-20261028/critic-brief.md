# Critic brief: Veyr knight completion, 2026-10-28

You are a blind, harsh critic. Judge only what you can see in the videos and numbers. Do not read
the implementation notes, commit messages or HANDOFF before scoring; they argue for the work.

## Material

- Page: `Local/knight-review-20261028/serve/index.html` (serve the `serve/` folder with a
  byte-range-capable server; Python's stock `http.server` breaks Safari video).
- Each video is front | side | three-quarter, 30 fps real time, played at the in-game rate.
  Same rig, sword, lights, cameras and 25 cm checker floor on both sides. Cameras follow the hips,
  so in-place loops show foot slip directly against the checker.
- "AFTER" is what the game now plays in that slot; "BEFORE" is what occupied the slot previously
  (or "none"). For the lock-on rows, BEFORE is the forward walk/run that used to play while the
  knight turned his back on the boss.
- Numbers: `Local/knight-review-20261028/data/runstop-fab.json`, `runstop-tripo.json`,
  (join measurements for 0.10/0.20/0.30 s blends), and the packaged-run evidence listed on the page.

## What to compare (per row, AFTER versus BEFORE, then AFTER on its own)

1. Locomotion loops (walk, run, backpedal, strafes, sprint strafes, both grips): foot plant and
   slip against the checker at the stated rate, loop seam (watch the second cycle start),
   weight transfer, knee and hip mechanics, torso counter-rotation, arm and sword carry.
   For strafes: do the feet cross or scissor cleanly, does the body lean into the direction of
   travel, does the sword stay in both palms in the two-hand variants without passing through
   the body or the legs.
2. Backpedal: is the 1.67x rate readable as a deliberate guarded retreat or does it look hurried?
3. Directional staggers (front, back, left, right, both grips): does each read as a hit from the
   named side? Is the right stagger convincingly a mirror of the left (no flipped wrist, no sword
   swapping sides)? Hand/sword contact, feet planted, recovery back toward a ready stance, and
   whether 0.60 s feels like a punish window or too long next to the old 0.42 s stagger.
4. Light attack, roll, roll attack, blinks, grip changes: arcs, contact readability, grip
   integrity (palms on the hilt, no knuckle crossing), recovery to ready.
5. Run-to-RunStop join (0.10 s versus 0.30 s blend): is there a visible pop of the sword arm at
   the switch? Is the stop's first footfall still readable with the longer blend?

## Scoring

For every row give AFTER and BEFORE a 0 to 10 score, one sentence of evidence each (frame,
view, body part), and a verdict: BETTER / SAME / WORSE / NO-BEFORE. Then list, ranked, the five
most visible defects across the whole page with the row and view where they appear. State
plainly whether any row is not shippable. Do not average away a single bad row.

## Out of scope

Dragon animation, environment, HUD, audio. Do not grade code. Do not trust any claim that a
clip is "approved"; owner approval is recorded separately and you are not the owner.
