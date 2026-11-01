#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrFightFeel.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class UCameraComponent;
class USkeletalMeshComponent;
class UPointLightComponent;
class UInstancedStaticMeshComponent;

/** Contact-driven presentation. Never creates damage or advances an action; hurt geometry follows the evaluated pose. */
UCLASS()
class VEYR_API AVeyrFightFeel : public AActor
{
    GENERATED_BODY()
public:
    AVeyrFightFeel();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void SwordContact(AVeyrDragon* Boss,bool bHeavy);
    void PlayerContact(AVeyrKnight* Player,float Damage,bool bBlocked);
    void Impact(const FVector& Position,float Weight,FName Kind);
    void ApplyCameraShake(UCameraComponent* Camera);
    void AddBossFlinch(AVeyrDragon* Boss,TMap<FName,FRotator>& Rotations) const;
    void UpdateWeaponTrail(AVeyrKnight* Player,float GameDelta);
    void RefreshSettings();
    void CancelHitStop() { RestoreTime(); }
    bool IsEnabled() const {return !bDisabled;}
    bool UsesContactFraming() const {return !bDisabled&&!bLegacy;}
    int32 GetRevision() const {return bDisabled?0:bLegacy?1:2;}
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 ShakeEvents=0,HitStopEvents=0,HitFlashEvents=0,FlinchEvents=0,TrailSamples=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") float LastHitStopSeconds=0.f,LastShakeDegrees=0.f,LastShakeDistance=0.f;
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 VisibleTrailSegments=0;
private:
    UPROPERTY() TObjectPtr<UPointLightComponent> HitFlash;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> WeaponTrail;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> HitMarker;
    TWeakObjectPtr<USkeletalMeshComponent> FlashMesh;
    FName FlashBone=NAME_None;
    FVector FlashLocalPoint=FVector::ZeroVector,FlashWorldPoint=FVector::ZeroVector;
    bool bDisabled=false,bLegacy=false,bOwnsDilation=false,bHaveBlade=false;
    float SavedDilation=1.f,StopRemaining=0.f;
    float ShakeAge=1.f,ShakeLife=.3f,ShakeAmplitude=0.f;
    float FlashAge=1.f,FlashWeight=0.f,FlinchAge=1.f,FlinchWeight=0.f,FlinchSide=1.f;
    double LastRealTime=0;
    FVector PreviousBladeTip=FVector::ZeroVector;
    struct FTrailSegment {FVector Start,End;float Age=0.f,Strength=0.f;};
    TArray<FTrailSegment> Trail;
    void RequestHitStop(float Seconds);
    void RestoreTime();
    void Flash(const FVector& Position,float Weight,USkeletalMeshComponent* Mesh=nullptr);
};
