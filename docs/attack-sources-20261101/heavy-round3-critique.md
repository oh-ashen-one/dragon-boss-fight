# Heavy attack blind comparison, round 3

A = Kevin v9; B = existing heavy. Mapping disclosed after verdict. Critic wording is contradictory: BOTH FAIL, but A clear relative winner and ready to replace B. Treat the explicit failure and identified snap as rejection; candidate remains off.

**Verdict: BOTH FAIL. A is the clear relative winner, and it is visually ready to replace B.** Confidence is moderate, about 0.7.

**A**
- **Weight and wind-up:** these are strong. From 0.17 to 0.60 s the knight sinks into a wide, deep stance with the blade upright (normal view 2, A4–A9). From 0.71 to 0.88 s the blade goes back over the right shoulder (A10–A12). That reads clearly as a heavy cut coming.
- **Strike arc:** it's continuous. In slow view 4 the blade goes from the shoulder (0.842) to behind the right side (0.942–0.990), passes edge-on (1.001, 1.007) and ends low and level (1.017). That's about 180° in roughly 75 ms, with no gaps between samples.
- **Grip:** both hands are visibly on the hilt from 0.942 to 0.990 and at 1.017–1.034.
- **Whole body:** the knight steps forward (normal view 1, A4 at 0.167) and drops into a deep lunge held from 1.04 to 1.57 s. The pose keeps settling during the hold rather than freezing (A15 to A19).
- **Recovery and return to idle:** the knight rises from 1.64 to 2.0 s and the feet narrow back to the idle stance by 2.60 s (view 2, A29–A32). There's no visible pop going into or out of idle.
- **Defect (the main reason A fails):** the body drops into the lunge almost instantly. In slow view 2 the knight is upright with a wide stance at 0.992 (A19), halfway down at 1.001 (A20) and fully pitched into the lunge at 1.010 (A21). The head moves forward about 37 px, roughly a third of the figure's height, in 18 ms. View 4 shows the same change between 0.990 and 1.017. At 60 fps that is about one frame, so the drop will almost certainly look like a snap rather than the body committing to the swing. The normal-speed sheets jump from 0.966 to 1.040, so they can't confirm or rule it out.
- **Minor issues:**
  - During the 1.04–1.57 s hold the right pauldron covers the hands (view 4, A25–A39), so the grip can't be checked there.
  - The whole move runs about 2.6 s. Whether that's too slow is a gameplay question; I make no pacing judgement.

**B**
- **What works:**
  - The sweep is continuous: in slow view 4 the blade goes from far left (0.455) through edge-on (0.505–0.531) to the right side (0.545–0.646), with no gaps.
  - The two-handed grip is clear at 0.455–0.495.
  - The return to idle is smooth (view 2, B28–B36, 1.40–1.84 s).
- **Defects:**
  - **Wind-up too fast:** the blade goes from idle (0.074) to fully back on the left (0.200) in about 0.13 s. That snap-back doesn't read as anticipation for a heavy weapon.
  - **Body doesn't take part:** through the whole backswing hold (slow view 2, B1–B24, 0.255–0.446 s) the legs are nearly straight and the stance is narrow. Only the torso and arms move. The knees bend a little and the feet widen only during the release (B25 at 0.455, and 0.578 in the normal view).
  - **Light follow-through:** the blade wraps behind the hip (0.80–0.89 s; view 1, B16–B19) and is lifted back up by about 1.4 s. The whole thing reads as a medium sideways swipe, not a heavy two-handed cut.
- These are motion-quality failures, not a choice of different poses.

**Why A should replace B:** A beats B on every axis you listed except overall length. B has nothing that makes it worth keeping, and A's main defect is a single, fixable transition.

**Biggest gap (testable fix):** spread A's drop into the lunge over at least 0.06–0.10 s of game time, starting the knee bend around 0.94 s so it lands with the blade at about 1.01 s. To pass: in a new slow capture, the head should move no more than about 10% of body height between consecutive 120 Hz samples from 0.94 to 1.04 s. Also check a real-time 60 fps clip for a visible one-frame pop.

**Secondary for A:**
- Confirm both hands stay on the hilt during the 1.04–1.57 s hold, using a camera angle the pauldron doesn't block.
- Check the forward step (0.17 s) and the feet narrowing (2.44–2.60 s) for foot sliding. These sheets are too far apart in time to show sliding.

**Limits of this evidence:**
- **Normal-speed sheets:** they sample only about every 70–100 ms, so they can't resolve snaps or foot sliding.
- **Slow sheets:** they cover only the strike window (A: 0.842–1.160 s; B: 0.255–0.646 s). Wind-up, recovery and the transitions into and out of idle were judged from the normal-speed sheets only.
- **Lighting and impact:** the lighting is dark, and there was no enemy in shot, so blade contact on a target couldn't be checked.

This is not human gameplay acceptance.
