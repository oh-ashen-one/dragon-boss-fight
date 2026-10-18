#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrCombatTypes.h"
#include "VeyrDragon.generated.h"

class AVeyrKnight;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UTextRenderComponent;
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
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") bool bUsingCustomuseVisual=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") FName MissingVisualClip=NAME_None;
    UFUNCTION(BlueprintCallable, Category="Presentation") bool ApplyCustomuseVisual(UVeyrVisualDefinition* Definition);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float Health = 8400.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float MaxHealth = 8400.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonState State = EVeyrDragonState::Idle;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrDragonMove Move = EVeyrDragonMove::ClawSwipe;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") TObjectPtr<AVeyrKnight> Target;

    UFUNCTION(BlueprintPure, Category="Combat") bool IsDead() const { return State == EVeyrDragonState::Dead; }
    UFUNCTION(BlueprintPure, Category="Combat") bool IsHeadExposed() const { return State == EVeyrDragonState::Exposed; }
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetHeadLocation() const;
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetLegLocation(int32 Index) const;
    UFUNCTION(BlueprintPure, Category="Combat") float GetLegStagger(int32 Index) const;
    /** Origin is already the world sword/contact center (no extra torso offset). */
    void ReceiveSword(const FVector& Origin, const FVector& Forward, bool bHeavy, int32 SwingId);

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

    bool bImportedTargetsValid=false;
    FVector ImportedHeadWorld=FVector::ZeroVector;
    FVector ImportedFeetWorld[4];
    void UpdateImportedPresentation();

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
    float GetDownAmount() const;
    void UpdateTemporaryPresentation(float DeltaSeconds);
    void UpdateTelegraphs();
    void DrawFootprint(UInstancedStaticMeshComponent* Lines, const FVeyrDragonFootprint& Footprint, bool bBright);
    void AddGroundLine(UInstancedStaticMeshComponent* Lines, const FVector& A, const FVector& B, float Width);
    UStaticMeshComponent* CreateTemporaryPart(FName Name, UStaticMesh* Mesh, const FVector& Scale);
    static void SetSegment(UStaticMeshComponent* Part, const FVector& A, const FVector& B, float Width);
    static bool ContainsPoint(const FVeyrDragonFootprint& Footprint, const FVector& Point);
    static bool SwordContact(const FVector& Origin, const FVector& Forward, const FVector& Point, float Radius, float& Score);
    static FVector Ground(FVector V) { V.Z=0; return V; }
    static FVector ClampArena(const FVector& V, float Radius = 2700.f);
};
