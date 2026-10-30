# Rise from lying: AI clip vs authored v5 (blind critic, 2026-10-30 16:25 ET)

Side-by-side: `Local/progress-20261030/m/rise_ab.mp4` (A = Seedance rise_lying clip, front+side ortho; B = rise v5 threequarter render). Bar: would a player call one visibly better. Critic (Opus 5.5 high, videos only):

1. **Verdict: A is clearly better.**

I measured motion as the mean frame-to-frame difference of each panel (`A.txt` and `B.txt`). A has four distinct beats. B moves almost the whole time as one smooth, floaty arc, and it never starts from a real collapse.

2. **Strongest observations**

A:
- **It really starts collapsed and holds still (frames 0–70).** The belly is flat and the wings are sprawled. Motion stays near zero (0.01–0.35), so it reads as knocked down, waiting to recover.
- **The push is effortful and builds up (72–100).** Motion climbs from 0.5 to about 2.0 while the forelegs plant and the chest lifts before the hind legs follow. You can feel the weight going through the limbs.
- **The stand has a strong accent.** The wings snap open at 104–110, the sharpest motion in the clip (peak 7.4, against B's peak of 4.5). They hold spread at 111–128, fold at 129–138, and the body settles by 145. That is a clear "I'm back" boss moment.

B:
- **The rise is continuous (9–42).** It is a smooth ease in and out, and the feet stay planted with no sliding.
- **A crouch before the big move (51–90).** The head drops low, then the dragon rears onto its hind legs (96–132). It has more verticality and theatre than A.
- **The drop back to four legs is decent (129–145).** It carries the strongest weight transfer in B (peak 4.5).

3. **Defects**

A:
- The dead hold at 0–70 is too long for gameplay (nearly 3 s of nothing).
- The head and wing edges smear and ghost at 104–110, and the right wingtip curls into a claw shape at 101–103.
- Motion stops completely from 145 to 149 (zero difference), so it freezes rather than settling into a breathing loop.

B:
- There is no collapsed start. At frame 0 it is already crouched with its legs under it and its head up.
- Motion begins by frame 9, so there is no stillness beat.
- The rise at 9–42 is an even sine-like bell with no sense of struggle, so it reads floaty.
- The far wing sticks straight up like a spike behind the head at 30–93 while the other wing stays folded. It looks wrong.
- The bipedal rear at 99–132 looks like a roar animation spliced onto the get-up, not part of standing up.
- The beat at 43–50 is a hold that goes nowhere.

4. **Gain from re-authoring B with A as the motion reference: clear.**

The player would get a readable recovery: a genuine downed pose, a laboured push with weight in it, a sharp wing-flare stand, and a settle. Those are four distinguishable beats instead of B's continuous float.

Two conditions:
- Trim A's opening hold to about 1–1.5 s.
- Rebuild the end of A's settle so it loops into idle instead of freezing.

Optionally, B's hind-leg rear could stay as a separate roar animation after the stand, not inside the get-up.

Files are in `/private/tmp/claude-501/-Users-midir/1e99ac11-5966-4ca4-8ec7-273fc683df51/scratchpad/critic_rise/`:
- `sheet_all.png`
- `A_66_149.png`
- `A_98_115.png`
- `B_0_69.png`
- `B_72_149.png`
- `Bzoom.png`
- `A.txt`
- `B.txt`
