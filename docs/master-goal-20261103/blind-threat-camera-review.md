# Blind camera review: A vs B

All 26 listed images were inspected once. This review uses still frames only.

**winner:** B

**visiblyBetter:** Yes, but only in parts of the fight. B wins clearly during the rear and airborne fire attack, at about 21.1–22.4s and 24.3–26.9s. The two versions are close to identical at 20.0–21.0s, 22.6–23.7s and 27.6–30.0s, and in most of the context samples.

**Integration verdict:** The evidence supports further integration of B, but B isn't finished. It doesn't reject both versions, because B fixes A's worst threat-readability failure. B still needs the player-scale and sky-pitch problems below addressed.

## visibleImprovements (B over A)
- **Roar and mouth tell (about 21.2–21.7s):** B shows the neck, head and open mouth, as well as the whole stance. At the same moment, A shows only belly and legs (compare `B-detail-1` with `A-detail-1`). A's head doesn't appear until about 22.6s, after the camera has already lost the player.
- **Fire attack (about 24.4–25.4s):** This is the decisive difference. B shows the glowing chest, head, flame and impact point in one frame, so the attack reads from source to target. In A, the flame falls from above the frame with only the tail visible, so it has no visible source.
- **Rear and leap (about 21.7–22.4s):** B keeps the boss's full silhouette, which gives a clear sense of its height and pose. A shows disconnected legs and tail.
- **Recovery and descent (about 25.4–26.9s):** B keeps the head and mouth glow in frame as the boss comes down. A shows dim tail and lower-body shapes for most of this period.
- **Weight:** B's wider framing doesn't make the boss feel small. The boss still dominates the frame, and the castle adds scale.
- **Head clearance (about 27s):** `B-detail-3` places the head just under the boss bar, while `A-detail-3` tucks it behind the bar. This gain is small.

## visibleRegressions (B vs A)
- **Player scale:** At about 21.7–22.4s and 24.3–26.0s, the player is roughly half A's height on screen. Armor detail is reduced, and the knight is nearly a dark silhouette in front of the fire.
- **Weapon readability:** At about 21.9–22.3s, B's weapon shrinks to a thin streak, while A's stays clear.
- **Ground hazards:** The player sits lower in the frame and the ground is seen at a flatter angle. As a result, the rings and arcs are thinner and fainter than in A, especially at about 21.3–22.4s and 23.9–25.3s. They remain visible, but A is clearly better here.
- **Player against boss:** In `B-detail-1`, the player's feet and dark armor blend into the talons, which makes the footing harder to read.
- **Earlier reframing:** B's large framing change happens at about 20.98–21.14s, before the boss has visibly risen. That is a sizeable shift over a few frames, and its feel can't be judged from stills.
- **Boss bar overlap:** The bar touches the head or horns during B's fire attack, because the head sits right at the top of the frame.

## Common failures (both A and B)
- **Sky pitch (about 22.6–23.7s):** This is the most serious shared problem. The camera tilts up into the sky and the player leaves the frame for about a second, so feet and ground hazards are lost.
- **Weapon occlusion:** During that same window, the oversized weapon fills the foreground and often sits over or beside the boss's head (`A-detail-2`, `B-detail-2`). B's better framing doesn't help here.
- **Close-range framing:** At 20–21s, and in the 40s, 55s, 60s, 65s and 70s context samples, the boss is mostly legs and the head is out of frame. Any head tells at those moments wouldn't be visible.
- **Player cropping (about 28.3–29.5s):** The player's lower legs are cut off at the bottom of the frame, the view is low, and the player is pushed into the HUD area. No ground hazard is readable.
- **HUD clutter:** The controls panel sits over the boss's body and tail, and sometimes over rings on the ground.
- **Low contrast:** The dark boss blends into the dark sky, and the dark legs blend into shadow.

## remainingRequirements
1. Keep the player, including their feet, in frame during the airborne phase, and limit upward pitch so the camera can't lose the ground.
2. Stop the weapon from covering the boss's head, or reduce how much it fills the frame in the foreground.
3. Recover some player size in B, using a slightly tighter framing or a higher player position, without losing the head or flame source.
4. Raise the camera angle or strengthen the hazard markers so rings stay readable at B's distance.
5. Extend head and tell visibility to close-range grounded fighting, which B doesn't improve.
6. Fix the cropped legs at about 28–29.5s, and keep the head clear of the boss bar.
7. Trigger the pull-back from the boss's actual rise, then test it in motion to confirm the transition isn't abrupt.

## scopeLimitations
- I judged still frames and contact sheets, not video. I can't confirm continuous smoothness, motion comfort, audio, collision, manual control, performance or input latency.
- Dense coverage is limited to 20–30s. The rest of the fight is sparse samples, including healing and death, so issues between samples could be missed.
- Most sheet frames are small thumbnails, so scale and hazard judgments are approximate outside the six full-resolution details.
- Timing and player actions differ slightly between runs (for example, the 60s and 65s samples), so some differences may come from the simulation rather than the camera.
- This is one fight and one gameplay policy, so results may differ with other player positions or a human player.
