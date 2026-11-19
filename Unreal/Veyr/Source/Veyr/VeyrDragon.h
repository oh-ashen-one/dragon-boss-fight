#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrCombatTypes.h"
#include "VeyrMoveData.h"
#include "VeyrGroundContacts.h"
#include "VeyrDragon.generated.h"

class AVeyrKnight;
class AVeyrArena;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UTextRenderComponent;
class UCapsuleComponent;
class UVeyrVisualDefinition;
class UVeyrSkeletalPresentation;
class UPrimitiveComponent;

UENUM(BlueprintType)
enum class EVeyrDangerShape : uint8 { None, Circle, Sector, Capsule };

/** World-space ground geometry in cm. This same definition drives telegraphs and contact. */
USTRUCT(BlueprintType)
struct FVeyrDragonFootprint
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) EVeyrDangerShape Shape = EVeyrDangerShape::None;
    UPROPERTY(BlueprintReadOnly) FVector Origin = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector End = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Forward = FVector::ForwardVector;
    UPROPERTY(BlueprintReadOnly) float InnerRadius = 0.f;
    UPROPERTY(BlueprintReadOnly) float OuterRadius = 0.f;
    UPROPERTY(BlueprintReadOnly) float HalfAngleDegrees = 180.f;
    UPROPERTY(BlueprintReadOnly) bool bDamaging = false;
};

/** The visible finite cone and damaging flame use this identical world-space beam. */
USTRUCT(BlueprintType)
struct FVeyrDragonFlameBeam
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FVector Origin=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Direction=FVector::ForwardVector;
    UPROPERTY(BlueprintReadOnly) float Length=1750.f;
    UPROPERTY(BlueprintReadOnly) float HalfAngleDegrees=12.f;
    UPROPERTY(BlueprintReadOnly) bool bDamaging=false;
};

struct FVeyrDragonContact
{
    FVector Start=FVector::ZeroVector, End=FVector::ZeroVector;
    float Radius=0.f;
};

/** One bound hurt capsule: boxes.json part resolved onto a bone of the imported mesh. */
struct FVeyrHurtPartRuntime
{
    int32 DataIndex=INDEX_NONE;
    FName Part, Kind, Bone;
    int32 BoneIndex=INDEX_NONE, Leg=INDEX_NONE;
    /** Segment ends in the bone's reference frame, mesh units (the bone's world transform carries the component scale). */
    FVector LocalA=FVector::ZeroVector, LocalB=FVector::ZeroVector;
    float DataRadius=0.f, Damage=1.f;
    bool bBlocksPawn=false;
};

/** Original native encounter rules. Primitive presentation is temporary, not Customuse art. */
UCLASS()
class VEYR_API AVeyrDragon : public AActor
{
    GENERATED_BODY()
public:
    AVeyrDragon();
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") TObjectPtr<UVeyrSkeletalPresentation> ImportedPresentation;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Presentation") TObjectPtr<UVeyrVisualDefinition> VisualDefinition;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bUsingPolishDefinition=false;
    /** Test tooling only (blendproof replay): the boss behaves as before first engagement, breathing but never attacking. */
    bool bProofPassive=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bUsingCustomuseVisual=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") FName MissingVisualClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") FString LocomotionDiagnostic;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") float GazeYawDegrees=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") float GazePitchDegrees=0.f;
    UFUNCTION(BlueprintCallable, Category="Presentation") bool ApplyCustomuseVisual(UVeyrVisualDefinition* Definition);
    /** Select the approved tucked hover on subsequent flights; transitions still
     * enter/leave through the v1 hover pose shared by takeoff and landing. */
    UFUNCTION(BlueprintCallable, Category="Presentation") void SetHoverAlternate(bool bEnabled) { bPreferHoverAlternate=bEnabled; }
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") bool bPreferHoverAlternate=false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") bool bAlternateHoverVariants=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bHoverAlternateThisFlight=false;
    /** Bounded native aiming layer; source animation and contact radii stay unchanged. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bBiteGroundAimReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") float BiteGroundPitchDegrees=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") float BiteGroundStrikeMuzzleHeightCm=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") FString BiteGroundAimDiagnostic;
    /** Parameter binding readiness; rendered mask acceptance is a separate gate. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation|Camera") bool bCameraOcclusionReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation|Camera") bool bCameraOcclusionEnabled=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation|Camera") FString CameraOcclusionDiagnostic;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Presentation|Camera",meta=(ClampMin="1.0")) float CameraOcclusionRadius=100.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Presentation|Camera",meta=(ClampMin="0.0")) float CameraProtectedHeadRadius=180.f;
    /** World centimetres. Changes only this actor's transient material instances. */
    UFUNCTION(BlueprintCallable, Category="Presentation|Camera")
    bool SetViewOcclusion(const FVector& CameraWorld,const FVector& FocusWorld,bool bEnabled);
    /** A2 fourth pass net: dither away the skin within Radius of the lens (no pale back faces at the near plane).
     * Reuses the camera-tunnel material with a short segment through the lens and no protected head. */
    bool SetNearLensOcclusion(const FVector& CameraWorld,const FVector& Forward,float Radius);
    /** Camera fifth pass: the dragon gives way in its materials (RuntimePolish/Fade/<name>_Fade clones). Distance fade from
     * NearCm (gone) to FarCm (solid) around Lens; sight fade (kept fraction SightFloor at Amount 1) in the capsule
     * Lens -> Focus of SightRadius; back faces clipped where a fade acts, everywhere when bBackDiscard. False (and
     * nothing applied) when the fade materials are not bound. */
    bool SetCameraFade(const FVector& Lens,const FVector& Focus,float NearCm,float FarCm,float SightRadius,float Amount,float SightFloor,bool bBackDiscard);
    /** Fade materials bound (fifth pass) and what the last SetCameraFade really applied (audit). */
    bool bCameraFadeMaterials=false,bCameraFadeBackDiscardApplied=false;float CameraFadeSightApplied=0.f;uint64 CameraFadeFrame=0;

    // Owner target: a competent victory within 150 wall seconds. Health is
    // calibrated by input-only victory replays; leg stagger thresholds stay independent.
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float Health = 650.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") FVector LastSwordContactWorld=FVector::ZeroVector;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float MaxHealth = 650.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonState State = EVeyrDragonState::Idle;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonMove Move = EVeyrDragonMove::ClawSwipe;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") TObjectPtr<AVeyrKnight> Target;

    UFUNCTION(BlueprintPure, Category="Combat") bool IsDead() const { return State == EVeyrDragonState::Dead; }
    // ---- Owner playtest 2026-11-05 (PLAYTEST_GOAL.md). Each has a restore switch for before/after films.
    /** Uniform creature scale against the 244 cm knight: -VeyrDragonScale=1 restores the old size. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") float BodyScale=1.f;
    /** Travel/turn/attack tempo multiplier: -VeyrLegacyPace restores 1. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float PaceScale=1.f;
    /** Zone-aware random brain, chains and anti-camping: -VeyrLegacyBrain restores the positional policy. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") bool bAggression=false;
    /** Floor attack rings are hidden by default; -VeyrFloorTelegraph draws them again. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bFloorTelegraph=false;
    /** Under half health the tempo tightens and strings run longer. */
    bool InSecondPhase() const { return bAggression&&Health<=MaxHealth*.5f; }
    /** True between the four planted feet: the underbelly camping zone. */
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") bool IsPointUnderBody(const FVector& Point) const;
    /** Lower bound on when a new blow could land on a stationary point: what a competent player reads. */
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float EarliestNextContactSeconds(const FVector& Point) const;
    /** When the committed strike's sweep arrives at a point (the moment a practised player rolls):
     * seconds from now, 0 while it is on the point, a large value when it never passes there. */
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float SecondsUntilStrikeReaches(const FVector& Point) const;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 BrainSeed=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 ChainCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 AntiCampFlights=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 RepositionCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 TrampleCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") float UnderBodySeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") float CampSeconds=0.f;
    /** Time spent in the pocket in front of the chest and around the fore paws that no strike reaches. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") float GuardPocketSeconds=0.f;
    bool IsPointInGuardPocket(const FVector& Point) const;
    int32 GuardPocketFlights=0,GuardPocketOverruns=0;
    /** Pocket and camp takeoffs are spaced out; in between the answer is to walk through the player. */
    float SpacedFlightReadyAt=0.f;
    bool bForceOverrun=false;
    bool SpacedAntiCampDue() const { return (GuardPocketSeconds>=GuardPocketLimit||CampSeconds>=CampLimit)&&EncounterClock>=SpacedFlightReadyAt; }
    /** Longest unbroken Idle while the encounter was live (the passive-gap gate). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") float LongestIdleSeconds=0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat") float ExposedSeconds=7.f;
    /** How far the creature's origin may travel from the court centre. The court is 4900 x 4400 cm
     * to its walls; a body twice as long and wide keeps tail and wings inside by roaming less. */
    float RoamRadius() const { return 2700.f-700.f*(BodyScale-1.f); }
    /** Distance in front of the body centre where the bite lands (measured from its clip). */
    float FrontSweet() const { return FrontSweetCm; }
    /** True while a wind-up may still turn the body onto the player. */
    /** The coil turns onto the player late: a short snap just before the blow, so a player who circles with
     * the body cannot settle back into a blind spot between the turn and the strike. The roll is the answer. */
    bool IsWindupTracking() const { return WindupMayStillTrack(); }
    bool WindupMayStillTrack() const { return State==EVeyrDragonState::Windup&&WindupTrackBudget>0.f&&StateElapsed<=StateDuration-.03f; }
    int32 OverrunCount=0;
    /** Fire aim: the neck pitches the jet down onto the player's range (the breath of a 30 ft creature leaves
     * the mouth about 11 m up and would otherwise pass over a knight on the ground). Degrees, 0 to 50. */
    float FireAimPitchDegrees=0.f;
    int32 FireHits=0;
    void UpdateFireAim(float DeltaSeconds);
    TMap<FName,FRotator> FireAimRotations(float Weight) const;
    FVeyrDragonFootprint FireAimBand() const;
    /** The flight is a threat from above: true from takeoff until the landing blow has gone. */
    bool IsFlightHazardActive() const;
    /** Where that threat meets the ground now: the hunting jet's target, then the landing point. */
    FVector GetFlightHazardPoint() const;
    /** Any blow of the current string really hurt the player (not rolled through). Decides the opening after it. */
    bool bStringLanded=false;
    /** Openings granted after a string the player avoided completely. */
    int32 WhiffOpenings=0;
    /** Finished strings in a row that the player avoided completely; each one tires the dragon a little more. */
    int32 WhiffStreak=0;
    /** Test evidence: one line per started attack (time, move, certainty, where the player stood, outcome). */
    TArray<FString> BrainLog;
    void CloseBrainLogEntry(const TCHAR* Outcome);
    bool bBrainLogOpen=false;
    /** The takeoff answer to sheltering or camping is armed and the dragon is still strong enough to fly. */
    bool AntiCampArmed() const;
    float BrainLogYaw0=0.f,BrainLogMinGap=100000.f;
    float WhiffOpeningFloor() const { return 1.35f+.25f*FMath::Min(WhiffStreak,2); }
    /** Damage taken during the current head-exposed window, and the amount at which the dragon tears free. */
    float ExposedDamage=0.f;
    float ExposedDamageCap=200.f;
    int32 ExposedCapRises=0;
    /** Owner 2026-11-18: "He should only be on the floor for 5 seconds maximum." Floor time runs from the body
     * reaching the floor (start of Exposed) to standing again (end of Rise). The rise plays 1.25x and the lying
     * window is what is left of the 5 s; buckle and fall keep their authored speed.
     * -VeyrLegacyKnockdown restores the 7 s lying window and the authored rise. */
    bool bLegacyKnockdown=false;
    float KnockdownFloorBudgetSeconds=4.9f; // 0.1 s under the 5 s limit: states end on frame boundaries
    float KnockdownRiseRate=1.25f;
    /** Lever (b), band pass: the head keeps its exposed bonus through the first part of the rise while it is
     * still low. Off by default until measured; -VeyrRiseHeadBonus turns it on (new knock-down timing only). */
    bool bRiseHeadBonus=false;
    float RiseHeadBonusFraction=.4f;
    /** Exposed, or (lever b) the low first part of the rise: blows to the head take the exposed bonus. */
    UFUNCTION(BlueprintPure, Category="Combat") bool IsHeadBonusActive() const;
    /** Seconds left of the head bonus (Exposed remaining plus the rise share when lever b is on). */
    float GetHeadBonusRemaining() const;
    /** Where the head lies during Exposed, in actor space per unit of BodyScale. Measured on build A
     * (2026-11-18, 8 fights, scale 2: 1390 cm ahead, 88 cm left, 287 cm up); refreshed from every Exposed frame. */
    FVector DownHeadLocalPerScale=FVector(695.f,-44.f,143.5f);
    /** Where the head will lie once the fall ends (valid from the buckle on); the scripted player heads there. */
    FVector GetPredictedDownHeadLocation() const { return GetActorLocation()+GetActorQuat().RotateVector(DownHeadLocalPerScale*BodyScale); }
    float KnockdownBuckleSeconds(int32 Leg) const;
    float KnockdownCollapseSeconds() const;
    float KnockdownRiseSeconds() const;
    float PostRiseIdleSeconds() const { return bAggression?.5f:.8f; }
    /** Lying window of a knock-down (fitted to the floor budget, never above ExposedSeconds). */
    float PlannedExposedSeconds() const;
    /** Time left until the dragon is standing again (end of Rise); 0 when it is not knocked down. */
    float GetKnockdownRemaining() const;
    /** Evidence per knock-down that ended standing: floor time (Exposed start to Rise end), buckle start to
     * Rise end, and buckle start to the end of the post-rise wait. */
    TArray<float> KnockdownFloorSeconds, KnockdownStandSeconds, KnockdownActSeconds;
    float KnockdownElapsed=0.f, KnockdownFloorStart=-1.f;
    bool bKnockdownActive=false, bKnockdownAwaitAct=false;
    /** Largest distance any grounded body part reached past the court floor edge; negative = always inside. */
    float CourtOverreachCm=-100000.f;
    static float ConfiguredBodyScale();
    static float ConfiguredPaceScale();
    /** Actor pose without the creature scale: world-centimetre local frames for reach tests. */
    FTransform RigidTransform() const { return FTransform(GetActorQuat(),GetActorLocation()); }
    bool UsesPacingRevision() const { return !bLegacyPacing; }
    FName IdlePresentationClip() const { return bOpenIdleWings?FName(TEXT("IdleOpen")):FName(TEXT("Idle")); }
    /** "BiteV2r" when the video2rig bite trims exist (default; -VeyrLegacyDragon restores "Bite"). */
    FString BiteClipStem() const;
    /** The "<Clip>V2r" video2rig variant when present and enabled, otherwise the keyed clip. */
    FName VideoClip(FName Keyed) const;
    /** Duration of the video2rig variant when one plays, otherwise the fixed state length. */
    float VideoStateDuration(FName Keyed,float Fixed) const;
    bool UsesFinisherRevision() const { return !bLegacyPacing&&!bLegacyFinisher; }
    /** Explicit non-combat rehearsal; never used by victory validation. */
    bool BeginShowcase();
    bool StartShowcaseSegment(FName Segment,FString& Error);
    bool IsShowcaseSegmentComplete() const;
    void RestAfterShowcaseSegment();
    TArray<FTransform> GetShowcaseFramingTransforms() const;
    FVector GetShowcaseFlightFacing() const;
    bool IsShowcase() const { return bShowcaseMode; }
    UFUNCTION(BlueprintPure, Category="Combat") bool IsHeadExposed() const { return State == EVeyrDragonState::Exposed; }
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetHeadLocation() const;
    /** Torso points for camera framing (chest, neck base, pelvis bones of the drawn body); false before the body is ready. */
    bool GetTorsoLocations(FVector& Chest,FVector& NeckBase,FVector& Pelvis) const;
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetMouthLocation() const;
    bool HasValidImportedCombatPose() const {return bImportedTargetsValid&&bImportedAttackCacheReady&&MissingVisualClip.IsNone();}
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetLegLocation(int32 Index) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVector GetLegKneeLocation(int32 Index) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVector GetLegHockLocation(int32 Index) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float GetLegContactRadius(int32 Index) const;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") bool bAnatomicalLegContactsReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") FString LegContactDiagnostic;
    /** Physical blockers follow the evaluated anatomy; hurt regions remain separate. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Collision") bool bSolidBodyReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Collision") int32 SolidBodyPushCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Collision") float SolidBodyPenetrationDepthCm=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Collision") FName LastSolidBodyPushShape=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Collision") FString SolidBodyDiagnostic;
    UFUNCTION(BlueprintPure, Category="Combat") float GetLegStagger(int32 Index) const;
    /** Origin is already the world sword/contact center (no extra torso offset). */
    void ReceiveSword(const FVector& Origin, const FVector& Forward, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f);
    bool ReceiveSwordSweep(const FVector& PreviousBase, const FVector& PreviousTip,
                           const FVector& CurrentBase, const FVector& CurrentTip, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f, float BladeRadius=8.f);

    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float GetStateElapsed() const { return StateElapsed; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float GetStateDuration() const { return StateDuration; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float GetHeadWindowRemaining() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") bool IsAirborne() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") bool IsEncounterStopped() const { return bEncounterStopped; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetCollapseCount() const { return CollapseCount; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetLastHitRegion() const { return LastHitRegion; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetStruckLegIndex() const { return StruckLeg; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetStompLegIndex() const { return StompLeg; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetSwordContactCount() const { return SwordContactCount; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetHeadBonusHitCount() const { return HeadBonusHitCount; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetAttackCount(EVeyrDragonMove Attack) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetCompletedAttackCount(EVeyrDragonMove Attack) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetDamageContactCount() const { return DamageContactCount; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 GetAvoidedContactCount() const { return AvoidedContactCount; }
    int32 GetTotalAttackCount() const { return TotalAttacks; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") float GetLastSwordDamage() const { return LastSwordDamage; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVector GetLandingLocation() const { return MoveEnd; }
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FText GetStateLabel() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVeyrDragonFootprint GetWarningFootprint() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVeyrDragonFootprint GetActiveFootprint() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") TArray<FVeyrDragonFootprint> GetWarningFootprints() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") TArray<FVeyrDragonFootprint> GetActiveFootprints() const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") FVeyrDragonFlameBeam GetActiveFlameBeam() const;
    /** Positional policy only; repetition and periodic flight can still override it. */
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") int32 PredictPositionalMove(const FVector& Point) const;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") FString ImportedCombatDiagnostic;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 WarningContainmentFailures=0;
    /** The connected court has walkable stairs/aisles up to 240 cm. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Combat|Evidence") float MaximumWarningFloorHeightCm=240.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Evidence") int32 WarningSurfaceTraceCount=0;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") bool IsPointInsideWarning(const FVector& Point) const;
    UFUNCTION(BlueprintPure, Category="Combat|Evidence") bool IsPointInsideActiveDanger(const FVector& Point) const;

    // ---- Data-driven move layer (Data/dragon/*.json, boss-fight-blueprint). Additive: with no
    // data, or veyr.MoveData.Enable 0, every hard-coded move, region and timing is unchanged.
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") bool bMoveDataLoaded=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") bool bHurtPartsReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") FString MoveDataDirectory;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") FString MoveDataDiagnostic;
    /** Import frame chosen for boxes.json a/b (yaw about +Z, degrees) and its bone-distance residual in game cm. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") float HurtFrameYawDegrees=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") float HurtFrameResidualCm=-1.f;
    /** Knight damage per attack part when a data window connects (knight health is 100). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|MoveData") TMap<FName,float> AttackPartDamage;
    /** Attack part (moves.json) -> hurt capsule (boxes.json) whose world segment is tested. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|MoveData") TMap<FName,FName> AttackPartCapsule;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") FName CurrentDataMove=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") float DataMoveClipSeconds=0.f;
    /** True when CurrentDataMove follows a hard-coded EVeyrDragonMove; false for a data-only move. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") bool bDataMoveFollowsEnum=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") int32 DataWindowHitCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") int32 DataWindowBlockedCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") int32 DataWindowAvoidedCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") FName LastSwordHurtPart=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|MoveData") FName LastDataHitPart=NAME_None;
    /** Reads Data/dragon again and rebinds the capsules. False keeps the hard-coded behaviour. */
    UFUNCTION(BlueprintCallable, Category="Combat|MoveData") bool ReloadMoveData();
    /** Plays a data move by name from Idle (lab). An enum-mapped name starts the hard-coded attack. NAME_None stops. */
    UFUNCTION(BlueprintCallable, Category="Combat|MoveData") bool PlayDataMove(FName MoveName);
    /** Hurt part whose capsule this is, NAME_None otherwise. */
    UFUNCTION(BlueprintPure, Category="Combat|MoveData") FName ResolveHurtPart(const UPrimitiveComponent* Component) const;
    /** Part-aware sword entry: legs keep the per-leg stagger, head keeps the exposure bonus, others hit the body. */
    bool ReceiveSwordOnPart(FName Part, const FVector& ContactWorld, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f);
    /** World segment and radius of a bound hurt part (current pose). */
    bool GetHurtPartWorld(FName Part, FVector& OutA, FVector& OutB, float& OutRadius) const;
    const FBossMoveData& GetMoveData() const { return MoveData; }
    /** The blueprint's first gate line: data, windows, parts and the runtime binding. */
    void DescribeMoveData(TArray<FString>& OutLines) const;
    /** Which hard-coded move a JSON move name stands for; false = data-only. */
    static bool MapDataMoveToEnum(FName MoveName, EVeyrDragonMove& OutMove);

    // ---- B4 (2026-11-18): ground contacts. -VeyrNoGroundContacts disables; see VeyrGroundContacts.h.
    /** Fires inside the dragon tick, once per contact (feet, head, neck, body, tail, wings). */
    FVeyrOnGroundContact OnGroundContact;
    /** Contacts detected on the latest dragon tick. */
    const TArray<FVeyrGroundContact>& GetGroundContactsThisFrame() const { return GroundContacts.ThisFrame(); }
    /** Last serial issued (monotonic, 0 before the first contact). */
    int32 GetGroundContactSerial() const { return GroundContacts.LastSerial(); }
    /** Contacts with a serial above AfterSerial from a 64-entry ring; returns the last serial. */
    int32 GetGroundContactsSince(int32 AfterSerial,TArray<FVeyrGroundContact>& Out) const { return GroundContacts.CopySince(AfterSerial,Out); }
    const FVeyrGroundContactCounters& GetGroundContactCounters() const { return GroundContacts.Counters(); }
    const FVeyrGroundContactDetector& GetGroundContactDetector() const { return GroundContacts; }
    /** True when contacts drive the camera shake (the old hard-coded stomp/tail/landing shakes are skipped). */
    /** True when contact events (not the fixed per-move impacts) shake the camera this frame. */
    bool ContactsDriveShake() const;
    /** Showcase rails for the feel proof: Collapse (Buckle skipped) as one segment. */
    bool StartFeelSegment(FName Segment,FString& Error);

protected:
    virtual void BeginPlay() override;

private:
    bool bLegacyPacing=false;
    bool bOpenIdleWings=false;
    bool bVideoBite=false;
    bool bLegacyDragon=false;
    bool bLegacyFinisher=false;
    bool bShowcaseMode=false;
    FName ShowcaseSegment=NAME_None,ShowcaseOverrideClip=NAME_None;
    int32 ShowcaseLeg=INDEX_NONE;
    UPROPERTY() TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> BodyMesh;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> ChestMesh;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> HeadMesh;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> JawMesh;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> UpperLegMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> LowerLegMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> FootMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> TailMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> WingMeshes;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> TemporaryParts;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> WarningLines;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> DangerLines;
    UPROPERTY() TObjectPtr<UTextRenderComponent> TemporaryLabel;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BasaltMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CopperMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> HeadMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> WarningMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> DangerMaterial;
    UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> LegMaterials;

    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> CameraOcclusionMaterials;
    void ResetCameraOcclusionMaterials();
    bool InitializeCameraOcclusionMaterials();
    UPROPERTY() TObjectPtr<UVeyrSkeletalPresentation> AttackPoseProbe;
    UPROPERTY() TArray<TObjectPtr<UCapsuleComponent>> SolidBodyCapsules;
    FName SolidPelvisBone=NAME_None,SolidChestBone=NAME_None,SolidNeckBaseBone=NAME_None,SolidNeckMiddleBone=NAME_None;
    FVector SolidPreviousStarts[19],SolidPreviousEnds[19];
    bool bSolidBodyHasPose=false;
    bool InitializeSolidBody();
    void UpdateSolidBody();
    void ResolveKnightBodyPenetration();
    bool bImportedTargetsValid=false;
    bool bImportedAttackCacheReady=false;
    bool bPreviousContactPoseValid=false;
    bool bWarningDrawn=false;
    int32 ClawLeg=0;
    FVector ImportedMouthWorld=FVector::ZeroVector, ImportedMouthAimWorld=FVector::ZeroVector;
    FVector ImportedContactFeetWorld[4], ImportedTailWorld[4];
    TMap<FName,TArray<FVeyrDragonFootprint>> LocalAttackWarnings;
    /** Unpadded contact sweep per clip: a player standing inside it is struck. The brain's "certain reach". */
    TMap<FName,TArray<FVeyrDragonFootprint>> LocalAttackContacts;
    bool CachedContactContains(FName Clip,const FVector& WorldPoint) const;
    /** Certain reach after the wind-up has turned the body by up to TrackLimitDegrees toward the player. */
    bool TrackedContactContains(FName Clip,const FVector& WorldPoint,float* OutYawDegrees=nullptr) const;
    /** Body turn (degrees, within the tracking limit) that brings the strike's reach closest to the point. */
    float TrackedContactNearestYaw(FName Clip,const FVector& WorldPoint) const;
public:
    /** Lab: text map of which strike is certain at each spot around the body (evidence "brainReachMap"). */
    TArray<FString> BrainReachMap() const;
private:
    static constexpr float TrackLimitDegrees=30.f,TrackRateDegreesPerSecond=150.f;
    float WindupTrackBudget=0.f,WindupTrackYaw=0.f;
    bool bWindupTrackPending=false;
    TArray<FVeyrDragonFootprint> CommittedWarning;
    TMap<FIntPoint,float> WarningSurfaceHeights;
    TWeakObjectPtr<AVeyrArena> WarningArena;
    bool WarningSurfaceHeight(const FVector& Point,float& Height);
    TArray<FVeyrDragonContact> PreviousContacts;
    FVeyrDragonFlameBeam PreviousFlame;
    FName ImportedMoveClip(EVeyrDragonMove Attack,int32 Leg,const TCHAR* Suffix) const;
    bool CacheImportedAttackWarnings();
    bool ReadImportedContactPose(UVeyrSkeletalPresentation* Presentation,EVeyrDragonMove Attack,int32 Leg,
        TArray<FVeyrDragonContact>& OutContacts,FVeyrDragonFlameBeam& OutBeam) const;
    TArray<FVeyrDragonContact> GetImportedContacts() const;
    FVeyrDragonFootprint ProjectFlameToGround(const FVeyrDragonFlameBeam& Beam,float Padding=0.f,bool bAllWalkableHeights=false) const;
    bool ImportedContactHitsKnight(const TArray<FVeyrDragonContact>& Contacts) const;
    bool FlameHitsKnight(const FVeyrDragonFlameBeam& Beam) const;
    void CommitImportedWarning();
    bool CachedWarningContains(FName Clip,const FVector& WorldPoint) const;
    static bool ContainsAny(const TArray<FVeyrDragonFootprint>& Footprints,const FVector& Point);
    bool bImportedTransitionReady=false;
    FName LastImportedClip=NAME_None;
    EVeyrDragonState LastImportedState=EVeyrDragonState::Idle;
    float ImportedTransitionStarted=0.f;
    float ImportedTransitionSeconds=.12f;
    FVector ImportedHeadWorld=FVector::ZeroVector;
    FVector ImportedFeetWorld[4];
    FName ImportedKneeBones[4],ImportedHockBones[4];
    FVector ImportedKneesWorld[4],ImportedHocksWorld[4];
    bool InitializeAnatomicalLegContacts();
    void UpdateImportedPresentation();
    void UpdateGaze(float DeltaSeconds);
    FVector LastPresentationLocation=FVector::ZeroVector;
    float LastPresentationYaw=0.f,WalkPhase=0.f,TurnPhase=0.f;
    float GazeSmoothedYaw=0.f,GazeSmoothedPitch=0.f;
    float NextFlightAt=10.f,EncounterClock=0.f;
    FVector TerminalDescentStart=FVector::ZeroVector;
    float TerminalDescentElapsed=0.f;
    bool bTerminalDescent=false;
    FVector AerialFireTarget=FVector::ZeroVector;
    bool bAerialFireConsumed=false;
    bool bPresentationMotionInitialized=false,bRepositionWalking=false;
    float RepositionTurnDuration=0.f,RepositionTravelDuration=0.f;
    float RepositionYawDelta=0.f;
    FTransform RepositionStartTransform=FTransform::Identity;
    bool bRepositionAuthoredTurn=false,bRepositionReverseTurn=false;
    FName RepositionTurnClip=NAME_None;
    float RepositionTurnSourceDuration=0.f;
    FVector LandingLocalCenter=FVector::ZeroVector;
    float LandingWarningRadius=600.f;
    bool HasAuthoredFlight() const;
    bool IsLandingContactWindow() const;
    float VisualClipDuration(FName ClipName,float Fallback) const;
    float WalkCycleDistance() const;
    bool ReadTurnTrajectory(float SourceSeconds,FVector& Translation,float& YawDegrees) const;
    FTransform RepositionTurnTransform(float Phase) const;
    FName BiteNeckBase=NAME_None,BiteNeckMiddle=NAME_None,BiteHead=NAME_None;
    bool HasGroundTargetBite() const;
    bool CalibrateBiteGroundAim();
    TMap<FName,FRotator> BiteGroundRotations(float SourceSeconds,float PitchDegrees) const;

    bool bFightFeelContactPlayed=false;
    float LegStagger[4] = {0,0,0,0};
    float LegFlash[4] = {0,0,0,0};
    FVector LegLocal[4];
    FVector HeadLocal = FVector(650,0,350);
    float StateElapsed = 0.f, StateDuration = 2.2f, Clock = 0.f;
    float WindupDuration = 1.f, ActiveDuration = .3f, RecoveryDuration = 1.5f;
    float AttackDamage = 30.f, StaggerProtection = 0.f, VisualAccumulator = 0.f;
    float DeathStartDown = 0.f, DeathStartBuckle = 0.f, LastSwordDamage = 0.f;
    int32 CollapseCount = 0, LastHitRegion = -1, StruckLeg = 0, StompLeg = 2;
    int32 SwordContactCount = 0, HeadBonusHitCount = 0, DamageContactCount = 0, AvoidedContactCount = 0;
    int32 TotalAttacks = 0, RepeatedMoveCount = 0;
    int32 StartedAttacks[6] = {0,0,0,0,0,0}, CompletedAttacks[6] = {0,0,0,0,0,0};
    bool bContactConsumed = false, bEncounterStopped = false, bJustRepositioned = false;
    EVeyrDragonMove LastMove = EVeyrDragonMove::ClawSwipe;
    FVector AttackOrigin = FVector::ZeroVector, AttackForward = FVector::ForwardVector;
    FVector MoveStart = FVector::ZeroVector, MoveEnd = FVector::ZeroVector;
    FRotator TurnStart, TurnEnd;
    TSet<int32> AcceptedSwings;
    TArray<int32> RecentSwings;
    static constexpr float FlightSeconds = 2.4f;


    // ---- B4 ground contacts
    FVeyrGroundContactDetector GroundContacts;
    float LastAirborneClock=-100.f;
    void UpdateGroundContacts(float DeltaSeconds);
    // ---- Data-driven move layer state
    FBossMoveData MoveData;
    UPROPERTY(Transient) TArray<TObjectPtr<UCapsuleComponent>> HurtCapsules;
    TArray<FVeyrHurtPartRuntime> HurtParts;
    TMap<EVeyrDragonMove,FName> DataMoveForEnum;
    TSet<int32> SpentDataWindows;
    TSet<FName> ActiveDataParts;
    FName DataOnlyClip=NAME_None;
    bool LoadMoveDataFromDisk();
    void DestroyHurtParts();
    bool BuildHurtParts();
    void UpdateHurtParts();
    void BeginDataMove(FName MoveName, bool bFollowsEnum);
    void StopDataMove();
    bool IsDataOnlyMovePlaying() const { return !CurrentDataMove.IsNone()&&!bDataMoveFollowsEnum; }
    void UpdateDataMove(float DeltaSeconds);
    void EvaluateDataWindows(const FBossMove& DataMove, float FromSeconds, float ToSeconds, bool bMayHurt);
    const FVeyrHurtPartRuntime* FindHurtPart(FName Part) const;
    bool HurtPartWorldSegment(const FVeyrHurtPartRuntime& Part, FVector& OutA, FVector& OutB, float& OutRadius) const;
    int32 HurtPartRegion(const FVeyrHurtPartRuntime& Part) const;
    void DrawMoveDataDebug() const;
    /** veyr.MoveData.Hits 2: a mapped data move with attacks replaces the hard-coded contact. */
    bool DataWindowsReplaceContact() const;
    /** -VeyrMoveDataDump on the command line logs the gate lines once the capsules are bound. */
    void LogMoveDataDumpIfRequested() const;
    // ---- Aggression revision (owner 2026-11-05): reach-based random choice, strings and anti-camping.
    struct FBrainOption { EVeyrDragonMove Move; int32 Leg; float Weight; };
    FRandomStream BrainRandom;
    int32 ComboCount=0,ComboBudget=1,ForcedStompLeg=INDEX_NONE,CampHitsBaseline=0;
    bool bChainedAttack=false;
    float IdleRunSeconds=0.f,FrontSweetCm=600.f;
    static constexpr float UnderBodyLimit=2.f,GuardPocketLimit=4.f,CampLimit=10.f,ChainWindupScale=.85f,MinimumWindup=.45f;
    /** Trample: a foot, shin or tail segment moving fast while the body turns or walks hurts on contact. */
    float SolidPartSpeed[19]={};
    float TrampleCooldown=0.f;
    void GatherBrainOptions(const FVector& Feet,const FVector& Lead,bool bChain,TArray<FBrainOption>& Out) const;
    bool BeginBrainOption(const TArray<FBrainOption>& Options,bool bChained);
    void ChooseAggressiveAttack();
    bool TryChainAttack();
    void RollComboBudget();
    void UpdateCampTimers(float DeltaSeconds);
    /** Paced phase lengths and damage for one attack, exactly as BeginAttack will play it. */
    void BaseAttackTiming(EVeyrDragonMove Attack,int32 Leg,float& Windup,float& Active,float& Recovery,float& Damage) const;
    void EnterState(EVeyrDragonState Next, float Duration);
    void ChooseAttack();
    void BeginAttack(EVeyrDragonMove Next);
    void BeginReposition();
    void AdvanceState(float DeltaSeconds);
    void TryDamageTarget();
    bool CanStagger() const;
    void ApplySwordRegion(int32 Region, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f, float PartDamageScale=1.f);
    float GetDownAmount() const;
    void UpdateTemporaryPresentation(float DeltaSeconds);
    void UpdateTelegraphs();
    void DrawFootprint(UInstancedStaticMeshComponent* Lines, const FVeyrDragonFootprint& Footprint, bool bBright,
        const TArray<FVeyrDragonFootprint>* Union=nullptr,int32 OwnIndex=-1);
    void AddGroundLine(UInstancedStaticMeshComponent* Lines, const FVector& A, const FVector& B, float Width);
    UStaticMeshComponent* CreateTemporaryPart(FName Name, UStaticMesh* Mesh, const FVector& Scale);
    static void SetSegment(UStaticMeshComponent* Part, const FVector& A, const FVector& B, float Width);
    static bool ContainsPoint(const FVeyrDragonFootprint& Footprint, const FVector& Point);
    static bool SwordContact(const FVector& Origin, const FVector& Forward, const FVector& Point, float Radius, float& Score);
    static FVector Ground(FVector V) { V.Z=0; return V; }
    static FVector ClampArena(const FVector& V, float Radius = 2700.f);
};
