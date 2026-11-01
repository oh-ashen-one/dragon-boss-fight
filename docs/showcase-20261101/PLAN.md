# Every-move rehearsal — filmed and scoped blind pass

This is a scripted, non-combat replay in the actual arena, separate from victory validation. It selects production attack/state playback, measures native clip/state/phase coverage and records a text-free film. Damage is disabled only for this mode; it must not produce victory timing or a combat-success claim. Normal fight behavior is unchanged.

Ordered segments: Idle, owner-approved Roar, one measured Walk cycle, large left/right root turns, fine left/right turns, Fire, complete Flight (takeoff/hover/fire-down/landing), both foreleg Claws, both rear Stomps, Tail, Bite, all four struck-leg buckle→collapse→exposed→rise cycles, and the current full DeathFall. Retained legacy/comparison aliases are not new production moves; the downed-death trim is already part of the full death source and has separate victory evidence. Clip/state coverage must be explicit, not inferred from a successful file import.

The Roar source is the owner-approved 2026-10-28 v2 scene. It is exported through the existing canonical-rig transfer, preserving geometry/skin/material bytes. Its shake cue is the first authored jaw-opening sample at 80% of maximum (2.5833 s of 5 s), not a damaging contact. No new generation or purchase. Data/dragon collision payloads are not silently staged/enabled.

A chapter camera fits the native mesh/action envelope and chooses an unblocked court view. A player-camera baseline flag retains the existing game camera for the matched visibility comparison. The wide-camera run must sample the required clip phases, states, fire-down beam and full mesh framing; this fidelity gate does not replace blind visual review. The knight is hidden/immobile for both views so it does not obstruct the creature. Camera cuts occur at chapter boundaries; actor motions are not reset or teleported between moves.

Native import, inventory, runtime coverage, Shipping films and chapter navigation are verified below. First blind Opus quality review returned PASS B for observer framing, with exposure/roar/stagger limitations. The normal victory regression passes under 150 seconds.

## Native findings

- Roar imported as v031showcase; 276 pose samples and transition endpoint checks passed. Protected files changed only at RuntimePolish/DA_Dragon; prior assets preserved. Source roar exported/grafted with zero joint-matrix mismatch and preserved canonical geometry/skin/material bytes.
- First camera run failed Roar (139/275 framed samples) and was visibly too distant/top-down. Component bounds did not describe the useful anatomy. The next camera uses evaluated head/limb/wing/tail support volumes with padding; the 90% per-clip framing gate remains. Frustum and obstruction failures are separated.
- Second run passed Idle/Roar/Walk but failed TurnLeft (111/125 framed samples). The next shot fits the full production root-motion turn trajectory and holds a fixed chapter view.
- Third run (`native-showcase-20261101T221501Z`) passed all 20 segments in 120.804 game seconds, including fire-down. No combat victory was claimed. Roar produced one shake at 2036.22 cm with 0.432 degrees amplitude, respecting the active observer distance.
- Render review found the flight shot too overhead to reveal the downward flame. The next candidate plans its front-quarter view from the actual production hover target/direction and reduces excessive height allowance. Offline hover anchors peak at ~2084 cm head / 2130 cm wing tips including the 850 cm actor arc; head aim only lowers the runtime head. The padded 1400 cm envelope above the initial pose covers those supports. Updated capture is pending.
- Retained entries are explicitly accounted for in coverage-policy.json; unknown native clip entries fail preflight. Chapter navigation is outside the videos. Its timeline converter has three passing tests, including wall-time mapping and missing/changed-evidence rejection.

## Final matched evidence

- Shipping receipt: `Local/package-20261101T223210Z/receipt.json`; source ID `02e6920c2763b067033a1fadba8e85f9177901246569e4b9ec8337a1e5a6aff9`. Active Knight v030t, Dragon v031showcase.
- Final observer run `native-showcase-20261101T223921Z`: all 20 chapters pass; 120.898 game seconds. Matched player-camera baseline `native-showcase-20261101T224204Z`: all 20 chapters pass the clip/state gate. Baseline deliberately does not require observer framing. Both runs preserve combat resources and have no encounter/victory timing; audits are recorded separately.
- The hidden knight's camera no longer hides arena props or alters dragon occlusion during an observer shot. Native framing uses evaluated anatomical support points, with separate frustum/obstruction counts; this is geometric coverage, not pixel-quality proof.
- Both continuous films have verified native timing and zero failed frames, approximately 123.7 seconds each. The bare page on port 8806 has 23 external chapter controls per film, including takeoff/hover/fire-down/landing. Browser verification loaded both videos without media errors and exercised the after-film Fire down seek and current-chapter label. Nothing is burned onto the videos.
- Normal combat regression `native-victory-20261101T224534Z` passed in **79.93922850117087 active wall seconds** on the same Shipping source, including native death completion and restart. Showcase is not counted as a victory.
- Fresh blind packet: 20 native contact sheets per randomized variant, sampling every production state interval. It compares existing player-camera versus observer-camera inspection of the same scripted repertoire, not natural boss combat. Opus returned PASS B (observer); report in critique.md. Continuous motion/player feel remain outside sampled-frame evidence.
