# Integration replay: locked blink / lateral stale-basis race

Scope: `Unreal/Veyr/Source/Veyr/VeyrReplay.cpp`, `AVeyrReplay::DriveIntegrationInputs` (phase 0 of the trial). Knight gameplay code is unchanged; the gate still exercises the real `AVeyrKnight::TryDirectionalBlink`.

## Bug

Phase 0 of a trial arrives from the safety navigation with the knight still in RunStop and its actor forward 100-165 degrees away from the boss. The scenario toggled lock-on in the same frame and, without waiting, computed
`BlinkSide = Knight->GetActorRightVector() * (BlinkLeft ? -1 : 1)` (also feeding `BlinkPathNearEdge`) and `IntegrationDirection` (Blink and Lateral `= GetActorRightVector()`) from that stale actor rotation.
The knight then turned toward the boss within ~0.2 s. `AVeyrKnight::TryDirectionalBlink` decides `Left = dot(Direction, GetActorRightVector()) < 0` using the rotation at processing time (after the lock-on turn), so a world-space direction that was "left" of the stale actor was "right" of the turned actor.

Evidence (in `Evidence/`):
- `native-integration-20261030T025444Z` (gate fail): a `locked_blink_left` request played `BlinkRight` three times (frames `player_BlinkRight` followed by `integration_hidden_locked_blink_left`, e.g. frames 114-115, 126-127, 129-130), exhausting the three attempts.
- `native-integration-20261030T023818Z` (pass on retry): `locked_blink_right` attempt 1 never produced the expected action/clip ("public input did not produce the expected native action and clip", requested 84.1 s, ended 88.1 s, a `player_BlinkLeft` frame at 116 in the same window); attempt 2 passed.
- Same run, `locked_strafe_without_blink`: attempts 1 and 2 were interrupted at 13.76 s and 15.23 s with reason "actual telegraph interrupted locomotion observation", 0.25 s and 0.14 s after the strafe clip was accepted. Lateral used the same stale `GetActorRightVector()` basis, so the first input frames (before the per-frame recomputation in phase 1) pushed the knight along an arbitrary world direction, possibly toward the boss/telegraph footprints. Phase 1 interrupt logic itself (`Threat` -> `Retry`) is correct and is kept: a natural dragon telegraph during the 1.2 s observation is a legitimate interruption, absorbed by the three-attempt budget.

## Fix (VeyrReplay.cpp only)

1. For Blink and Lateral trials with `Trial.Lock`, "right" is taken from the boss-facing rotation the knight will have once locked: `FRotationMatrix(FRotator(0,(Dragon->GetActorLocation()-Feet).Rotation().Yaw,0)).GetUnitAxis(EAxis::Y)` (`TrialRight`). It feeds `BlinkSide`, `BlinkPathNearEdge` and `IntegrationDirection`. Non-locked trials still use the actor right vector.
2. For every `Trial.Lock` trial the input is issued only when the knight is `Ready` (not RunStop/Roll) and its actual forward is within 8 degrees of the boss direction, both continuously for the existing 0.40 s settle (`IntegrationConfiguredAt` is reset while not Ready or not aligned). While waiting the function returns true without counting an attempt; the existing 40 s trial timeout still applies.
3. Once aligned (within 8 degrees) the knight's own `GetActorRightVector()` and the boss-basis right agree, so `TryDirectionalBlink` picks the side the scenario requested.

Not compiled or run in this change (GPU/Unreal were off limits); needs one native `integration` replay to confirm.
