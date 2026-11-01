# Fight feedback revision 2 — candidate

Revision 1 remains unaccepted after the original blind tie and a second, denser review following owner resume. The second review could see the warm leg flash but identified a floor spotlight at the head contact and inadequate close-range framing.

- Replace the default point light with a small depth-tested contact glint using the existing FXv3 ember material and Epic plane. Keep the accepted blade contact point, bind it to the nearest evaluated bone, and fade it briefly without illuminating the floor.
- At close grounded leg range, blend lock-on focus toward the nearby contact zone. Preserve the 72-degree lens, 560 cm arm, manual look and airborne/head-exposed focus. Smooth the focus, rather than changing framing at attack onset.
- `-VeyrFightFeelLegacy` retains revision 1 point-light and head-only focus for the progress comparison. `-VeyrFightFeelOff` remains the original disabled baseline. Replay evidence reports revision 0, 1 or 2.
- No damage, health, source animations, effect weights or hit-stop durations changed in revision 2. No new asset acquisition/generation/spend.

Pending: Shipping compile/package, before/after rendered validation, visual inspection and independent blind Opus critique. No quality acceptance yet.
