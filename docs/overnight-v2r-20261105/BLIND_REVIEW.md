# Blind Opus Review — Dragon Video2Rig Before/After (2026-11-06)

## Method
- **Pairs evaluated**: 10 default video2rig moves (`IdleOpenV2r`, `Bite*V2r`, `Claw0/1*V2r`, `Buckle0/1V2r`, `CollapseV2r` + `ExposedV2r`, `Tail*V2r`, `Stomp2/3*V2r`, `Fire*V2r`, `WalkV2r`, `TurnLeftV2r`) vs their `-VeyrLegacyDragon` keyed baselines.
- **Same-build showcase captures**:
  - Legacy (`before`): `Evidence/native-showcase-20261106T154608Z` (`-VeyrLegacyDragon`)
  - Default video2rig (`after`): `Evidence/native-showcase-20261106T194359Z` (all 10 moves active by default, 20/20 chapters PASS)
- **Blinding**: Each move's before/after MP4 and 6-frame contact sheet were assigned deterministically pseudorandom labels (`A` vs `B`) in an isolated staging folder with no filenames or metadata indicating which was keyed or video2rig. An independent blind Opus critic subagent (`c76c5c7e-15eb-4ab1-9726-ac2db7db5446`) inspected only the anonymized `A`/`B` sheets and MP4s.

## Unblinded Results Summary: **10 / 10 wins for `after (video2rig)`**

| Pair ID | Move | Candidate A | Candidate B | Blind Winner | Unblinded Winner | Confidence | Key Critic Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `01_idle_wings` | Idle wings (folded look) | `after (video2rig)` | `before (keyed)` | **A** | **video2rig** | High | A keeps wings cleanly raised and arched above the shoulders with natural breathing oscillation; B crimps and droops wings into a beetle-shell clump over the hindquarters. |
| `02_bite` | Bite | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | High | B rears head/chest high with jaws open, snaps downward/forward with whole-body weight and flared wings; A collapses wings against the ribcage and performs a flat neck thrust. |
| `03_claw_foreleg` | Claw (both forelegs) | `after (video2rig)` | `before (keyed)` | **A** | **video2rig** | High | A rears the foreleg and twists the upper torso/neck into a wide swipe arc with spread wings; B is nearly static with only a minor paw twitch and end-frame wing crimp. |
| `04_buckle_front` | Buckle, front legs | `after (video2rig)` | `before (keyed)` | **A** | **video2rig** | Medium | A has genuine skeletal collapse weight and spine/tail commitment vs B's stiff procedural crouch where rigid vertical wings clip into the stone floor. |
| `05_collapse_exposed` | Collapse + Exposed | `after (video2rig)` | `before (keyed)` | **A** | **video2rig** | High | A rears in pain and collapses onto its belly/side with curled tail, draped wings, and visible breathing; B stays stuck in an upright four-legged standing crouch. |
| `06_tail_smack` | Tail smack | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | High | B commits pelvis, spine, torso, and spread wings to a forceful whip across the target zone; A bends only the tail on a frozen torso/legs. |
| `07_rear_stomp` | Rear stomps | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | High | B shifts weight, lifts the hindquarter high with wing/tail counterbalance, and slams into the target ring; A is nearly motionless. |
| `08_fire_ground` | Fire (ground) | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | Medium | B maintains clean raised wings across all frames and a committed forward neck/chest lunge (A wraps wings into the torso), though B's flame particle emitter pitch angles upward rather than hitting the ground cone. |
| `09_walk` | Walk | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | High | B pairs a grounded diagonal quadrupedal gait with clean, raised wing carriage and secondary motion; A plasters collapsed wings tightly around the ribcage. |
| `10_turn_left` | Turn 90° | `before (keyed)` | `after (video2rig)` | **B** | **video2rig** | High | B executes a smooth, grounded 90° stepping turn with natural spine/tail curve and raised wings; A's wings collapse into the torso during frames 1–5. |
