# Every-move rehearsal — in progress

This is a scripted, non-combat replay in the actual arena, separate from victory validation. It selects production attack/state playback, measures native clip/state/phase coverage and records a text-free film. Damage is disabled only for this mode; it must not produce victory timing or a combat-success claim. Normal fight behavior is unchanged.

Ordered segments: Idle, owner-approved Roar, one measured Walk cycle, large left/right root turns, fine left/right turns, Fire, complete Flight (takeoff/hover/fire-down/landing), both foreleg Claws, both rear Stomps, Tail, Bite, all four struck-leg buckle→collapse→exposed→rise cycles, and the current full DeathFall. Retained legacy/comparison aliases are not new production moves; the downed-death trim is already part of the full death source and has separate victory evidence. Clip/state coverage must be explicit, not inferred from a successful file import.

The Roar source is the owner-approved 2026-10-28 v2 scene. It is exported through the existing canonical-rig transfer, preserving geometry/skin/material bytes. Its shake cue is the first authored jaw-opening sample at 80% of maximum (2.5833 s of 5 s), not a damaging contact. No new generation or purchase. Data/dragon collision payloads are not silently staged/enabled.

A chapter camera fits the native mesh/action envelope and chooses an unblocked court view. A player-camera baseline flag retains the existing game camera for the matched visibility comparison. The wide-camera run must sample the required clip phases, states, fire-down beam and full mesh framing; this fidelity gate does not replace blind visual review. The knight is hidden/immobile for both views so it does not obstruct the creature. Camera cuts occur at chapter boundaries; actor motions are not reset or teleported between moves.

Current code compiles for VeyrEditor. Roar plan is prepared under Local/CustomuseAssets/Polish20261025/showcase-v031. Native import, alias inventory, runtime coverage/framing, Shipping film, blind Opus review and owner-facing chapter navigation are pending. The original 150 s victory gate must still pass after the integration.

## Native findings

- Roar imported as v031showcase; 276 pose samples and transition endpoint checks passed. Protected files changed only at RuntimePolish/DA_Dragon; prior assets preserved. Source roar exported/grafted with zero joint-matrix mismatch and preserved canonical geometry/skin/material bytes.
- First camera run failed Roar (139/275 framed samples) and was visibly too distant/top-down. Component bounds did not describe the useful anatomy. The next camera uses evaluated head/limb/wing/tail support volumes with padding; the 90% per-clip framing gate remains. Frustum and obstruction failures are separated.
- Second run passed Idle/Roar/Walk but failed TurnLeft (111/125 framed samples). The next shot fits the full production root-motion turn trajectory and holds a fixed chapter view.
- Third run (`native-showcase-20261101T221501Z`) passed all 20 segments in 120.804 game seconds, including fire-down. No combat victory was claimed. Roar produced one shake at 2036.22 cm with 0.432 degrees amplitude, respecting the active observer distance.
- Render review found the flight shot too overhead to reveal the downward flame. The next candidate plans its front-quarter view from the actual production hover target/direction and reduces excessive height allowance. Offline hover anchors peak at ~2084 cm head / 2130 cm wing tips including the 850 cm actor arc; head aim only lowers the runtime head. The padded 1400 cm envelope above the initial pose covers those supports. Updated capture is pending.
- Retained entries are explicitly accounted for in coverage-policy.json; unknown native clip entries fail preflight. Chapter navigation is outside the videos. Its timeline converter has three passing tests, including wall-time mapping and missing/changed-evidence rejection.
