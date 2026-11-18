# Greystone knight: motion matching (quality goal E, step E5)

Status: designed and written blind on 2026-11-18. No engine was available. The C++ (`VeyrMotionMatcher.h/.cpp`, `VeyrGreystoneEditorLibrary.h/.cpp`) compiles with 0 warnings. It is not wired into `AVeyrKnight`. The editor scripts in `tools/unreal/greystone/` have not been run.

## Rule set

- **The capsule stays authoritative for gameplay.** Hitboxes, the roll's invulnerability, damage, the camera target and the dragon's targeting all read the capsule, exactly as they do today. Motion matching chooses only which clip, and which time in it, the shown body plays.
- **The shown body plays one clip at one time.** There is no blend tree. A switch is an inertialized jump to a new clip and time (the offsets decay in `UVeyrSingleNodeInstance`). There are never two clips mixed.
- **Actions are never searched.** Attacks, rolls, blinks, heal, hit reactions and death keep the existing explicit clip path and the existing timing data (damage windows and impact times). Motion matching runs only while `Action == Ready` and the knight is grounded.
- **`-VeyrLegacyMotion` restores today's locomotion selection completely.** The matcher is never constructed when that flag is present.

## Database

Greystone's skeleton holds every database. The clips come from GASP's Dense databases, retargeted with `RTG_UEFN_to_Greystone`, which is Epic's TwinBlast retargeter with its target rig swapped (`make_rigs.py`, then `make_motion_databases.py`).

| Gate | GASP source databases | Our database |
| --- | --- | --- |
| Idle | `PSD_Dense_Stand_Idles` | `PSD_GS_Idle_Stand_Idles` |
| Start | Stand Walk, Run and Sprint Starts | `PSD_GS_Start_*` |
| Loop | Stand Walk, Run and Sprint Loops | `PSD_GS_Loop_*` |
| Stop | Stand Walk, Run and Sprint Stops | `PSD_GS_Stop_*` |
| Pivot | Stand Walk, Run and Sprint Pivots | `PSD_GS_Pivot_*` |
| TurnInPlace | `PSD_Dense_Stand_TurnInPlace` | `PSD_GS_Turn_Stand_TurnInPlace` |

- **What is left out:** crouch, jump, land, traversal and spin databases. The knight has none of those states.
- **Schema:** `PSS_GS_Default` is a duplicate of GASP `PSS_Default` with its skeleton swapped. It has no mirror table yet, so every entry is set to "original only". A Greystone mirror table is follow-up work. It needs the `_l`/`_r` bone pairs plus the sword and shield bones, which must not mirror.
- **Normalization:** `PSN_GS_All` covers all of our databases, so costs are comparable across gates.
- **Gate filing:** `FVeyrMotionMatcher::Initialize` sorts each database into a gate by the gate word in its name.

## Feature vector (fallback table and query)

The vector has 33 floats. They are expressed in the capsule frame: x forward, y right, z up, in world cm at the definition's scale. The origin is the mesh component location (sole level).

| Floats | Feature | Default weight |
| --- | --- | --- |
| 0-5 | foot_l and foot_r position | 0.75 |
| 6-11 | hand_l and hand_r position | 0.25 |
| 12-17 | foot velocities | 0.5 |
| 18-20 | pelvis velocity | 0.5 |
| 21-26 | future root XY position at 1/3, 2/3 and 1 s | 1.0 |
| 27-32 | future facing XY at the same times | 1.0 |

- **Normalization:** each feature is scaled by its mean and standard deviation over all rows, then weighted.
- **Cost:** the weighted squared distance.
- **The Pose Search path** uses the schema's own channels: GASP's trajectory channel and pose channels (feet, pelvis velocity). The 33-float table is the fallback. It is used when the PoseSearch databases fail to load, and it is forced with `-VeyrMotionFallback`. `bake_motion_features.py` bakes it from the same clips into `Content/Characters/Greystone/MotionMatching/veyr_motion_features.json`, schema `veyr-motion-features-v1`.

### Fallback table format

```json
{"schema": "veyr-motion-features-v1", "step": 0.0333,
 "mean": [33 floats], "std": [33 floats], "weights": [33 floats],
 "rows": [{"clip": "/Game/.../GS_M_Neutral_Run_Loop_F.GS_...", "time": 0.4667, "gates": ["Loop"], "f": [33 floats]}]}
```

- `LoadJson` rejects the table when the schema is wrong, when any array length is not 33, when a value is not finite, or when the file is empty.
- A standard deviation below 1e-4 is treated as 1, so that channel only adds its weight.
- The table needs staging for a packaged build: add it to `DirectoriesToAlwaysStageAsNonUFS`. It is local content, so the asset itself is never committed.

## Trajectory and search

- **Desired trajectory:** a critically damped spring moves the simulated position and yaw (`FVeyrSpringTrajectory`).
  - Velocity half-life is 0.20 s; yaw half-life is 0.12 s.
  - The target is the gameplay's desired velocity and facing.
  - The future samples use the closed-form spring prediction at 1/3, 2/3 and 1 s, built into an `FTransformTrajectory` for Pose Search.
- **Pose history:** `FPoseHistory` is fed with the shown pose every frame (`RecordShownPose`, all skeleton bones).
- **When it searches:**
  - every 0.05 s (20 Hz);
  - immediately on a gate change (forced search);
  - never while an action plays.
- **Gates:** only the current gate's databases are offered (`FVeyrMotionGates::Update`):

  | Gate | Condition |
  | --- | --- |
  | Start | input held while speed is below 40 cm/s |
  | Stop | input released while speed is above 30 cm/s |
  | Pivot | desired direction more than 135° from the velocity |
  | TurnInPlace | standing still with a facing error above 60° |
  | Loop | moving otherwise |
  | Idle | otherwise |

- **Hysteresis:**
  - Switch only when the current clip's cost is more than 2 × the best cost + 0.3.
  - Allow at most one switch per 0.10 s.
  - A continuing Pose Search result (`bIsContinuingPoseSearch`) is not a switch.

## Inertialized switch

`UVeyrSingleNodeInstance::StartInertialSwitch(FVeyrInertialSwitch)` works in three steps:

1. On the next evaluation, it captures per-bone offsets: the previous shown pose minus the new clip's pose, plus the velocity from the two previous shown poses.
2. It then decays the offsets with a critically damped spring per bone.
3. `AdvanceInertialization(dt)` runs once per tick.

Half-lives:

| Switch | Half-life |
| --- | --- |
| Default | 0.10 s |
| Legs (thighs to toes) entering a Pivot | 0.06 s, so the plant lands quickly |
| Torso entering a Loop from another gate | 0.35 s, so the upper body settles without a snap |

Applied in this order: after the leg locks, then the inertial offsets, then the shield and sword bone pins. The pins always win.

## Capsule follows body

`FVeyrCapsuleCoupling::Step`:

- The clip's own root travel moves a "body" point.
- The capsule moves by gameplay as today.
- Each tick the body is pulled toward the capsule by at most 20 % of the clip's own travel that tick. The correction stays inside motion the clip is already making, so the feet do not visibly slide.
- The body-to-capsule separation is hard-clamped at 15 cm.
- The mesh is drawn at the body point. When the clamp engages, `Evidence()` counts it; that count is the foot-slide metric for review.

## Not written blind (needs the engine)

- Wiring `FVeyrMotionMatcher` into `AVeyrKnight::UpdateImportedPresentation`, behind `-VeyrGreystone` without `-VeyrLegacyMotion`. The tick order around the existing locomotion clip selection has to be checked on the running game.
- Tuning the half-lives, weights and gate thresholds against film.
- The mirror table.
- The capsule speeds versus GASP clip speeds. GASP runs near 400-500 cm/s. The knight's run and sprint speeds must be checked against the 244 cm scale, and the stride may need a play-rate warp.

## APIs relied on (read from the installed UE 5.8.3 headers)

- **PoseSearch runtime:**
  - `UPoseSearchLibrary::MotionMatch(AnimContexts, Roles, PoseHistories, AssetsToSearch, ContinuingProperties, Future, Event)` returning `FSearchResult`;
  - `FSearchResult::{IsValid, GetCurrentResultAnimationAsset, IsAssetTimeValid, GetAssetTime, GetSearchIndexAsset, PoseCost, bIsContinuingPoseSearch}`; the `AssetTime` field is deprecated in 5.8;
  - `FPoseHistory::{Initialize_AnyThread, EvaluateComponentSpace_AnyThread, SetTrajectory}`;
  - `FSKMCComponentSpacePoseProvider`, which is experimental and wrapped in `PRAGMA_DISABLE_EXPERIMENTAL_WARNINGS`;
  - `UPoseSearchSchema::GetMirrorDataTable(Role)`, because `Skeletons` is private in C++ and is set from Python through `set_editor_property`;
  - `UPoseSearchDatabase::{GetNumAnimationAssets, GetDatabaseAnimationAsset, SetAnimationAssetAt, RemoveAnimationAssetAt}`, which are WITH_EDITOR;
  - `FPoseSearchDatabaseAnimationAsset::{AnimAsset, MirrorOption}`.
- **IK Rig and Retargeter (IKRigEditor):**
  - `UIKRigController::{GetController, SetSkeletalMesh, AddRetargetChain, SetRetargetRoot, AddNewGoal, ApplyAutoFBIK}`;
  - `UIKRetargeterController::{SetIKRig, SetPreviewMesh, AddDefaultOps, AssignIKRigToAllOps, AutoMapChains, AutoAlignAllBones, GetSourceChain}`;
  - `UIKRetargetBatchOperation::RunBatchRetarget(FIKRetargetBatchOperationInputs)`; `DuplicateAndRetarget` is deprecated in 5.8.
- **AnimationBlueprintLibrary:**
  - `UAnimPoseExtensions::{GetAnimPoseAtFrame, GetAnimPoseAtTime, GetBonePose(World), GetReferencePose}`;
  - the sequence `Controller` with `AddBoneCurve`, `SetBoneTrackKeys` and `Open/CloseBracket`.
- **Plugin:** PoseSearch is enabled in `Veyr.uproject`. It is not enabled by default. IKRig is already on.
