#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "VeyrCombatTypes.h"
#include "VeyrKnight.generated.h"

class AVeyrDragon;
class UCameraComponent;
class USpringArmComponent;
class UStaticMesh;
class UStaticMeshComponent;
class USceneComponent;
class UPrimitiveComponent;
class APlayerController;
class UVeyrSkeletalPresentation;
class UVeyrVisualDefinition;

/** Native combat owner. Primitive presentation is explicitly temporary pending Customuse. */
UCLASS()
class VEYR_API AVeyrKnight : public ACharacter
{
    GENERATED_BODY()

public:
    AVeyrKnight();
    virtual void Tick(float DeltaSeconds) override;
    // Owner removed jumping; also reject inherited/Blueprint jump requests.
    virtual bool CanJumpInternal_Implementation() const override { return false; }
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float Health = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") float Stamina = 100.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") int32 HealingCharges = 4;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") EVeyrKnightAction Action = EVeyrKnightAction::Ready;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") TObjectPtr<AVeyrDragon> Boss;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") bool bLockedOn = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat") bool bTwoHanded = false;
    UFUNCTION(BlueprintPure, Category="Combat") bool IsTwoHanded() const { return bTwoHanded; }
    UFUNCTION(BlueprintCallable, Category="Combat") void ToggleGrip();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 LightAttacks = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 HeavyAttacks = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 Rolls = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 DodgedHits = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 HitsTaken = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 GuardedHits = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 GuardBreaks = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 SuccessfulHeals = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 SuccessfulJumps = 0;
    /** Sampled from the preceding resolved spring-arm frame; walls may legitimately compress it. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float CameraResolvedDistance = 720.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float CameraSeverelyCompressedSeconds = 0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") int32 CameraHiddenProxyParts = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float CameraFloorClearance=220.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float CameraPitchCeiling=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float CameraFramingArm=720.f;

    UFUNCTION(BlueprintPure, Category="Combat") bool IsDead() const { return Health <= 0.f; }
    UFUNCTION(BlueprintPure, Category="Combat") bool IsGrounded() const;
    UFUNCTION(BlueprintPure, Category="Combat") bool IsRollingInvulnerable() const;
    UFUNCTION(BlueprintPure, Category="Combat") bool IsGuardBroken() const { return bGuardBroken; }
    UFUNCTION(BlueprintPure, Category="Combat") float GetActionElapsed() const { return ActionElapsed; }
    UFUNCTION(BlueprintPure, Category="Combat") float GetActionDuration() const { return ActionDuration; }
    UFUNCTION(BlueprintPure, Category="Combat") float GetSwordContactTime() const;
    UFUNCTION(BlueprintPure, Category="Combat") float GetAttackDuration(bool bHeavy) const;
    UFUNCTION(BlueprintPure, Category="Combat") float GetAttackContactTime(bool bHeavy) const;
    UFUNCTION(BlueprintPure, Category="Combat") float GetPlanarSpeed() const;
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetFootLocation() const;
    UFUNCTION(BlueprintPure, Category="Combat") FVector GetRollDirection() const { return RollDirection; }
    UFUNCTION(BlueprintPure, Category="Input") bool IsMouseCaptured() const { return bMouseCaptured; }
    UFUNCTION(BlueprintPure, Category="Input") bool IsReplayControlled() const { return bReplayControlled; }
    UFUNCTION(BlueprintPure, Category="Input") bool HasEnteredEncounter() const { return bHasEverCapturedMouse || bReplayControlled; }
    UFUNCTION(BlueprintCallable, Category="Combat") void ApplyBossDamage(float Amount, const FVector& Source, bool bUnblockable = false);
    UFUNCTION(BlueprintCallable, Category="Combat") void TryLightAttack();
    UFUNCTION(BlueprintCallable, Category="Combat") void TryHeavyAttack();
    UFUNCTION(BlueprintCallable, Category="Combat") void TryRoll();
    UFUNCTION(BlueprintCallable, Category="Combat") void TryHeal();
    UFUNCTION(BlueprintCallable, Category="Combat") void SetGuard(bool bHeld);
    UFUNCTION(BlueprintCallable, Category="Combat") void ToggleLockOn();
    UFUNCTION(BlueprintCallable, Category="Combat") void RestartIfTerminal();
    UFUNCTION(BlueprintCallable, Category="Presentation") bool ApplyCustomuseVisual(UVeyrVisualDefinition* Definition);

    /** Input-level test hook; never writes health, action clocks, position or boss state. */
    void SetReplayInput(const FVector& WorldMove, bool bLight, bool bHeavy, bool bRoll, bool bHeal, bool bJump, bool bGuard);
    void ClearReplayInput();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera") TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera") TObjectPtr<UCameraComponent> CombatCamera;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Temporary Art") TObjectPtr<USceneComponent> TemporaryVisual;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Presentation") TObjectPtr<UVeyrSkeletalPresentation> ImportedPresentation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Presentation") TObjectPtr<UVeyrVisualDefinition> CustomuseVisualDefinition;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") bool bImportedPresentationActive=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") bool bRequestedPresentationClipSampled=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") bool bPresentationUsingFallback=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") FName RequestedPresentationClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") FString PresentationDiagnostic;
    /** Native centimeters/second represented by each authored locomotion clip. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Presentation") TMap<FName,float> PresentationNominalSpeeds;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") FName RequestedLowerPresentationClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float PresentationLowerWeight=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") float PresentationJumpPhase=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") bool bHealFlaskVisible=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Evidence") FString HealFlaskDiagnostic;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY() TObjectPtr<USceneComponent> SwordPivot;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> BoatWeapon;
    bool bBoatReleased=false;
    float BoatReleaseTime=0.f;
    FTransform BoatReleaseStart,BoatReleaseRest;
    bool GetWeaponSweep(FVector& Base,FVector& Tip);
    void UpdateEquippedWeapon();
    UPROPERTY() TObjectPtr<UStaticMeshComponent> LeftLeg;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> RightLeg;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> ProxyParts;
    UPROPERTY() TObjectPtr<USceneComponent> HealFlaskRoot;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> HealFlaskParts;

    float GripTransitionRemaining = 0.f;
    float BufferedAttackRemaining = 0.f;
    bool bBufferedHeavy = false;
    bool bSwingTwoHanded = false;
    float ActionElapsed = 0.f;
    float ActionDuration = 0.f;
    float RegenDelay = 0.f;
    float DamageGrace = 0.f;
    float VisualClock = 0.f;
    float PresentationLocomotionTime = 0.f;
    float PresentationLowerTime = 0.f;
    float PresentationJumpLaunchSpeed = 580.f;
    float PresentationRollYaw = 0.f;
    FName PresentationLowerClip=NAME_None;
    FName PresentationTransitionLowerClip=NAME_None;
    FName FailedPresentationClip=NAME_None;
    FString FailedPresentationReason;
    bool bIdleFallbackRejected=false;
    FName PresentationTransitionClip=NAME_None;
    float PresentationTransitionStarted=0.f;
    float PresentationPreviousActionElapsed=-1.f;
    bool bPresentationTransitionActive=false;
    float CameraDistance = 720.f;
    float CameraFloorZ = 0.f;
    float CameraObstructionHold = 0.f;
    float LockHeadBlend = 0.f;
    TWeakObjectPtr<APlayerController> OcclusionController;
    TMap<TWeakObjectPtr<UPrimitiveComponent>, float> CameraHiddenParts;
    TWeakObjectPtr<APlayerController> MouseInputController;
    int32 SwingId = 0;
    bool bContactSent = false;
    bool bPreviousBladePoseValid=false;
    FVector PreviousBladeBase=FVector::ZeroVector, PreviousBladeTip=FVector::ZeroVector;
    bool bHealGranted = false;
    bool bGuardRequested = false;
    bool bGuardBroken = false;
    bool bForwardHeld = false, bBackHeld = false, bLeftHeld = false, bRightHeld = false;
    bool bReplayControlled = false;
    bool bMouseCaptured = false;
    bool bHasEverCapturedMouse = false;
    bool bMouseCaptureConfirmationPending = false;
    float MouseCaptureRequestedAt = 0.f;
    bool bReplayJumpHeld = false;
    bool bReplayLight = false, bReplayHeavy = false, bReplayRoll = false, bReplayHeal = false, bReplayJump = false, bReplayGuard = false;
    FVector ReplayMove = FVector::ZeroVector;
    FVector MoveIntent = FVector::ZeroVector;
    FVector RollDirection = FVector::ForwardVector;

    bool IsTerminal() const;
    bool CanStartGroundedAction() const;
    void BeginAction(EVeyrKnightAction NewAction, float Duration);
    void FinishAction();
    void AdvanceCombat(float DeltaSeconds);
    void UpdateMovement(float DeltaSeconds);
    void UpdateCamera(float DeltaSeconds);
    void UpdateCameraOcclusion(float DeltaSeconds);
    void RestoreCameraOcclusion();
    void UpdateTemporaryPresentation(float DeltaSeconds);
    void UpdateImportedPresentation(float DeltaSeconds=0.f);
    FName SelectDirectionalLocomotion(bool bAllowRun) const;
    void UpdateHealFlask();
    void SetPresentationDiagnostic(const FString& Diagnostic);
    UStaticMeshComponent* CreateProxyPart(const TCHAR* Name, UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Location, const FVector& Size);
    void LookYaw(float Value);
    void LookPitch(float Value);
    void ZoomIn();
    void ZoomOut();
    void GuardPressed();
    void GuardReleased();
    void ForwardPressed(); void ForwardReleased();
    void BackPressed(); void BackReleased();
    void LeftPressed(); void LeftReleased();
    void RightPressed(); void RightReleased();
    bool HumanInputEnabled() const { return bMouseCaptured && !bReplayControlled; }
    void UpdateMouseCapture();
    void CaptureMouseOrAttack();
    void BeginControlFromKeyboard();
    void ReleaseMouse();
    void GripPressed();
    void LightPressed(); void HeavyPressed(); void RollPressed();
    void HealPressed(); void LockPressed();
};
