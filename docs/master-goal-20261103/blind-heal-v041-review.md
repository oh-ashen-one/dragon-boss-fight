# Blind review: knight heal animation, sets A and B

**I looked at all 24 images, A-01 to A-12 and B-01 to B-12, with the Read tool.** Frame n is at about −0.15 + 0.25·(n−1) s, so frame 01 = −0.15 s, 05 = 0.85 s, 08 = 1.60 s, 11 = 2.35 s and 12 = 2.60 s. These are still frames. I did not watch any motion or hear any audio.

---

## Set A: fails

**What happens, frame by frame**
- **A-01** (before input): weapon on the shoulder, walking. Flask count is 4.
- **A-02**: weapon is down at the right side and the flask count is 3. No cup is visible yet, and the left hand is empty at the side.
- **A-03**: cup appears in the left hand at belt height.
- **A-04**: fist rises to the collar (gorget). The cup is upright and sits to the side of the fist, below the chin.
- **A-05 to A-07** (the drinking peak): the left forearm crosses horizontally in front of the lower helmet, and the elbow is raised out to screen-right. The fist ends up off the helmet's screen-left edge (about x 520–530). The cup hangs below the fist at about x 510–520, y 240–265. That is outside the helmet outline (left edge about x 585) and below the visor slit.
- **A-08** to **A-10**: the arm comes down. The cup is beside the helmet at shoulder height in 08, at the chest in 09 and at the hip in 10.
- **A-11**: cup is gone and the knight is idle. **A-12**: running with the weapon on the shoulder, camera turned the other way.

**Defects**
1. **The cup never reaches the visor or mouth (A-05, A-06, A-07, A-08).** At every peak frame the cup is outside the helmet outline, about 60–70 px to the left of it and level with the cheek or jaw. The forearm covers the face but the cup does not. It reads as a forearm across the face with the cup held beside the head, not as drinking. This is a worse version of the "cup beside the temple" failure.
2. **There is no meaningful drinking tilt (A-04 to A-08).** The cup stays roughly upright or hangs below the fist. I cannot see a rim tipped toward the face in any frame.
3. **The arm path looks odd (A-05 to A-07).** The shoulder pulls the arm hard across the body, and the forearm passes in front of the chin and collar. A still frame can't show depth, so the forearm may be cutting into the helmet's chin or collar.
4. **The shoulder or armpit mesh tears (A-05, A-06, A-07).** Jagged white shards show at about (710–720, 370–380) under the raised pauldron. This is a skinning failure while the arm is raised.
5. **Minor: the cup is late (A-02).** It is not visible at +0.10 s while the weapon has already dropped. The hand is empty for one frame before the cup appears.

**Strengths**
- The cup stays in hand at every frame where it is visible (A-03 to A-10).
- The right hand keeps a steady grip on the weapon.
- The return through A-08 to A-10 goes in order (shoulder, then chest, then hip), and the A-11 posture is natural and upright.

---

## Set B: relative winner, but not shippable as captured

**What happens, frame by frame**
- **B-01**: same as A-01.
- **B-02**: cup is already in the left hand at the hip. ⚠ The whole knight and weapon are drawn as flat-shaded, untextured low-detail geometry (a low-detail level or texture streaming problem) in this frame.
- **B-03**: cup comes up to chest and chin height in front of the left shoulder. It is upright and gripped by the handle, with the elbow out.
- **B-04**: the cup is over the front of the faceplate at visor-slit height, overlapping the screen-left half of the faceplate. The red eye glow shows just beside it.
- **B-05 to B-08**: the cup is tipped close to horizontal. A solid gold disc (most likely the cup's base) faces out over the faceplate, and the body runs down-right to the handle in the fist. The upper arm is about horizontal and the elbow is raised. These four frames are almost identical.
- **B-09**: the cup is still at the visor but rotating back toward upright. **B-10**: cup back down at the chest, upright. **B-11**: cup gone, idle. **B-12**: running with the weapon on the shoulder, camera turned.

**Defects**
1. **The shoulder or armpit mesh tears through the whole drink (B-04 to B-09).** White triangular shards show at about (700–740, 340–400). Dark spikes stick out below the elbow at about (780–830, 380–420), most clearly in B-04 and B-09. They are visible for about 1.25 s of on-screen time. This alone blocks shipping.
2. **The cup sits at eye level, not mouth level (B-04 to B-09).** The cup and its base cover the left eye slit. For a stylized closed helmet, slit level is just about acceptable, but it is higher than a mouth. It can read as pressing the cup into the eye.
3. **The cup may cut into the faceplate (B-04, B-09).** The cup body overlaps the faceplate in the frame. Whether the rim actually passes through the metal cannot be checked from a fixed camera.
4. **I can't fully confirm which way the cup faces (B-05 to B-08).** I read the solid disc facing out as the base, which would be correct for drinking. If it were the open rim, the knight would be drinking from the base. Tone and shading point toward base, but this needs a closer view.
5. **The pose is frozen for four frames (B-05 to B-08).** Pose, cup and arm are almost the same across about 0.75 s, possibly up to 1.0 s. It could play as a purposeful hold or as a stalled animation. Only continuous playback can tell.
6. **The return may be abrupt (B-09 to B-11).** The cup is still at the visor at 1.85 s, at the chest at 2.10 s, and gone with the hand at the side by 2.35 s. That compressed lowering and cup removal may pop.
7. **Rendering problem (B-02).** The untextured, flat-shaded frame is not a pose defect, but it is visible in a native capture.

**Strengths**
- This is a real drinking action, unlike A. The cup clearly reaches the visor (B-04 to B-09) with a large tilt, close to horizontal (B-05 to B-08).
- The handle stays in the fist throughout (B-02 to B-10).
- The raised elbow, flexed wrist and lifted shoulder are a believable drinking arm (B-05 to B-08).
- The raise goes in a clear order: hip (B-02), chest (B-03), visor (B-04).
- The cup appears in time (B-02). The weapon hand stays planted, and the idle posture in B-11 is clean.

---

## Verdict

- **Winner: B**, clearly, on drinking pose. B gets the cup to the visor with a real tilt. A never gets it there.
- **Visual-pose quality: BOTH FAIL / DO NOT SHIP.**
  - A fails the core criteria: the cup never reaches the visor, there is no tilt, and the forearm covers the face instead.
  - B passes the core drinking-pose criteria with reservations (eye-level contact, possible faceplate overlap). It still fails as captured because of the shoulder and armpit mesh tears in B-04 to B-09 and the broken render in B-02.
  - The same tearing in A-05 to A-07 suggests a shared problem when the arm is raised, not something specific to B.

## What these frames can't show

- **Depth:** I can't tell whether the cup cuts into the faceplate (B-04, B-09) or the forearm into the helmet (A-05 to A-07). This needs a side camera or close-up.
- **Movement over time:** I can't tell whether B-05 to B-08 is an intended hold or a freeze, how B goes from visor to chest to cup gone (B-09 to B-11), or how the weapon drops from shoulder to side between frames 01 and 02 in both sets. All three need continuous playback.
- **Cup direction:** which end of the cup faces the helmet in B-05 to B-08 needs a close-up or slow-motion view.
- **Out of scope:** frame 12 in both sets shows running after the heal, not heal poses. The weapon shaft in front of the helmet there (and in frame 01) may be clipping, but I didn't count it.
