# Fix round 3 (v5) blind critique

Date: 2026-10-30. I judged the rendered MP4s only (r2 against r3, plus the sources). Scripts and evidence are in `/private/tmp/claude-501/-Users-midir/1e99ac11-5966-4ca4-8ec7-273fc683df51/scratchpad/critic_r3/`.

**How to read the numbers.** My d scale is about 2.5 times the round-3 critic's: AL r2 pop is 40.4 here against their 16.4. The pop rule is the same: d above 2.0 and above 2.2 times the median of the ±3 neighbouring steps.

| Clip | Verdict | r3 vs r2 to a player |
|---|---|---|
| Air land | NOT SHIPPABLE | clearly better |
| Rise | SHIPPABLE | clearly better |
| Collapse | NOT SHIPPABLE (narrow miss) | clearly better |
| Roar | NOT SHIPPABLE | marginally better |
| Bite | SHIPPABLE | marginally better |

## Air land
- **Fixed.** The frame 63 to 64 teleport is gone in all views (r2 d 40.4, 36.4 and 26.4; r3 has no pop there).
- **Fixed.** The braking flare works. Front span goes from 188 to 270 px (+44%) over frames 86 to 97, and descent slows from 4 to 1 px/frame.
- **Fixed.** The slam works. The left-view top drops to 74 px below standing (0.47 H) by frame 105, holds for frames 105 to 115 (11 frames), then rises over frames 116 to 131.
- **Fixed.** Breathing in frames 118 to 144 is kept.
- **New blocker: a wing snap at frames 98 to 100.** Both wings go from fully raised to tucked in 2 frames.
  - Front view: top moves 256, 279, 359; area goes 12770 to 7609 (-40%).
  - d at frame 99 is 22.0 against a neighbour median of 9.3 (2.37x), which fails the pop rule.
  - The source spreads its wings flat on impact instead.
- **Frozen hold in the front view.** Frames 106 to 114 have d = 0.00, so the frames are pixel-identical. Only the tail moves, and only in the left view.
- **Weak tail whip.** The left-view tail extends 15 px.

## Rise
- **No pops in any view.** The frame 43 to 44 pop is gone (r2 d 25.2, 15.9 and 17.6).
- **Sequenced get-up.** The forefeet lift and plant first (frames 12 to 16, belly still at row 428). The hind legs gather next (frames 28 to 34, forefeet held at row 418). Every frame has floor contact, so there is no float. No wing sweeps across the floor.
- **The chain breathes.** d over frames 1 to 7 is 1.4 to 4.1 (r2: 0.0 to 0.3).
- **Minor.** Frames 44 to 50 are a near-hold (d 0.6 to 0.9).

## Collapse
- **Heavier fall.** Standing to lying now takes 28 frames (frames 62 to 90; r2 took 16). Peak d drops from 31.8 to 23.1.
- **3/4 view fixed.** The leftmost point at the last frame is x 206 (r2: 87). The wing spike is gone.
- **Lying height still misses the target.**
  - End height against standing: front 0.53 (target ≤0.50; r2 0.65), left 0.50, 3/4 0.50.
  - The front top is a crumpled wing lump on screen-right. The wings are folded but scrunched, unlike the source's flat drape.
- **Breathing is weaker.** Over the last 35 frames, minimum d is 0.26 to 0.32 (r2 0.72 to 0.84).

## Roar
- **Size now follows the source.** Peak span is 1.10x (frame 92 only); the hold sits at 1.06 to 1.09x. Height is 1.27 to 1.33x, which passes.
- **The buzz is gone.** The d spectrum peak moved from 3.7 frames to 9.6 frames.
  - Tip high-pass is now 0.95 px (left) and 1.07 px (front).
  - That is below the 1.5 to 3 px band, but it reads as smooth, not dead: hold d averages 13.7.
- **Fail: asymmetry, worse than r2.** Half-spans are measured from the frame-0 centre.
  - r3: left 1.03, right 1.11, gap mean 0.085, max 0.14.
  - r2 on the same metric: gap 0.017.
  - At frame 66 the screen-right wing visibly reaches further out while the left stands vertical.

## Bite
- **Twitch fixed.** The frame 50 to 51 twitch is gone: r2 had a 3/4 pop of 19.3 against 8.2; r3 d runs 8.9, 9.2, 9.8.
- **Reach is better.** Reach is 87 px (14.5 cm; r2 76 px), with 3 frames at full extension.
- **Near wing is better but still short of the target.** It now reads as a fan, not a hook.
  - Upper-left wing-zone area is 0.54, 0.67 and 0.73 of frame 0 at frames 50, 56 and 62 (r2: 0.27, 0.37 and 0.52).
  - Target is ≥0.7 throughout.
- **Seams unchanged.** The bite seam IoU is 0.955 to 0.980; the roar seam is similar.

## Single biggest gap
**AL frames 98 to 100.** Spread the wing fold over at least 6 frames, or keep the wings spread to the floor as the source does:
- front area change of no more than 12% per frame;
- no d step above 2.2x its neighbours;
- the frames 106 to 114 front hold must have d ≥0.4 (my scale ≥1.0).

## Secondary
- **Roar.** Bring the halves within 5% (open the screen-left wing about 8 points) and sit the hold at 1.10 to 1.12x.
- **Collapse.** Flatten the screen-right wing lump so front height is ≤0.50, and restore breath amplitude.
- **Bite.** Near-wing area ≥0.7 at frames 44 to 50.
