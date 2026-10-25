#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrCombatTypes.h"
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
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") bool bAlternateHoverVariants=true;
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

    // Calibrated for the native characters' safe approach and head-punish
    // cadence. Damage, independent leg thresholds and enemy moves are unchanged.
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float Health = 5800.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float MaxHealth = 5800.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonState State = EVeyrDragonState::Idle;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonMove Move = EVeyrDragonMove::ClawSwipe;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") TObjectPtr<AVeyrKnight> Target;

    UFUNCTION(BlueprintPure, Category="Combat") bool IsDead() const { return State == EVeyrDragonState::Dead; }
    UFUNCTION(BlueprintPure, Category="Combat") bool IsHeadExposed() const { return State == EVeyrDragonState::Exposed; }
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetHeadLocation() const;
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
                           const FVector& CurrentBase, const FVector& CurrentTip, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f);

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

protected:
    virtual void BeginPlay() override;

private:
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

    void EnterState(EVeyrDragonState Next, float Duration);
    void ChooseAttack();
    void BeginAttack(EVeyrDragonMove Next);
    void BeginReposition();
    void AdvanceState(float DeltaSeconds);
    void TryDamageTarget();
    bool CanStagger() const;
    void ApplySwordRegion(int32 Region, bool bHeavy, int32 SwingId, float DamageMultiplier=1.f);
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
