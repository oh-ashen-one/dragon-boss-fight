#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrGroundContacts.h"
#include "ProceduralMeshComponent.h"
#include "VeyrFightFeel.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class UCameraComponent;
class USkeletalMeshComponent;
class UPointLightComponent;
class UInstancedStaticMeshComponent;
class UProceduralMeshComponent;
class UMaterialInstanceDynamic;
class FJsonObject;

/** Contact-driven presentation. Never creates damage or advances an action; hurt geometry follows the evaluated pose.
 *  B4-B6 (2026-11-18): camera shake by contact weight, whole-spine flinch with a mesh flash, a full-width blade
 *  ribbon, slow-motion tail, zoom punch and a hurt kick; switches in VeyrFeelTuning.h restore each old piece. */
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
    void PlayerContact(AVeyrKnight* Player,float Damage,bool bBlocked,const FVector& Source=FVector::ZeroVector);
    void Impact(const FVector& Position,float Weight,FName Kind);
    /** B4: a dragon floor contact (bound to AVeyrDragon::OnGroundContact). */
    void ContactImpact(AVeyrDragon* Dragon,const FVeyrGroundContact& Contact);
    void ApplyCameraShake(UCameraComponent* Camera);
    void AddBossFlinch(AVeyrDragon* Boss,TMap<FName,FRotator>& Rotations) const;
    void UpdateWeaponTrail(AVeyrKnight* Player,float GameDelta);
    void RefreshSettings();
    void CancelHitStop() { RestoreTime(); }
    bool IsEnabled() const {return !bDisabled;}
    bool UsesContactFraming() const {return !bDisabled&&!bLegacy;}
    int32 GetRevision() const {return bDisabled?0:bLegacy?1:bMarkerOnlyReview?2:3;}
    /** Counters for evidence.json > feel. */
    TSharedPtr<FJsonObject> FeelEvidence(bool bStatic=false) const;
    /** This frame's spine flinch moves the pose enough to fake floor contacts (the dragon mutes them). */
    bool FlinchDisplacesPose() const { return FlinchFrame==GFrameCounter&&FlinchDegreesNow>2.5f; }
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 ShakeEvents=0,HitStopEvents=0,HitFlashEvents=0,FlinchEvents=0,TrailSamples=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") float LastHitStopSeconds=0.f,LastShakeDegrees=0.f,LastShakeDistance=0.f;
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 VisibleTrailSegments=0;
    // B4-B6 evidence
    int32 ContactShakes=0,ShakesByClass[4]={0,0,0,0};
    float MaxShakeByClass[4]={0.f,0.f,0.f,0.f};
    int32 SpineFlinches=0,MeshFlashes=0,FallbackFlashes=0,SlowTails=0,ZoomPunches=0,HurtKicks=0,RibbonFrames=0,MaxRibbonRows=0;
    mutable int32 FlinchBoneCount=0,LegCompensations=0; // filled when the chain is (re)built from the pose path
    mutable float MaxFlinchDegrees=0.f,FlinchDegreesNow=0.f;
    mutable uint64 FlinchFrame=0;
    float MaxRibbonWidthCm=0.f;
    mutable FString FlinchDiagnostic;
    FString FlashDiagnostic,RibbonDiagnostic;
private:
    UPROPERTY() TObjectPtr<UPointLightComponent> HitFlash;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> WeaponTrail;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> HitMarker;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Ribbon;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RibbonMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> MeshFlashMaterial;
    TWeakObjectPtr<USkeletalMeshComponent> FlashMesh;
    TWeakObjectPtr<USkeletalMeshComponent> OverlayMesh;
    TWeakObjectPtr<AVeyrDragon> BoundDragon;
    FDelegateHandle ContactHandle;
    FName FlashBone=NAME_None;
    FVector FlashLocalPoint=FVector::ZeroVector,FlashWorldPoint=FVector::ZeroVector;
    bool bDisabled=false,bLegacy=false,bMarkerOnlyReview=false,bOwnsDilation=false,bHaveBlade=false;
    float SavedDilation=1.f,StopRemaining=0.f,SetDilation=1.f;
    float ShakeAge=1.f,ShakeLife=.3f,ShakeAmplitude=0.f,ShakeBounce=0.f,ShakeFrequency=1.f;
    FVector ShakePhase=FVector::ZeroVector;
    float FlashAge=1.f,FlashWeight=0.f,FlinchAge=1.f,FlinchWeight=0.f,FlinchSide=1.f;
    // B6 camera
    bool bPendingSlow=false,bCameraBaseCaptured=false,bVignetteOwned=false;
    float SlowRemaining=0.f,SlowTotal=0.f;
    float PunchAge=10.f,PunchAmp=0.f,LastFovDelta=0.f,LastFovSet=-1.f;
    float KickAge=10.f,KickAmp=0.f,HurtAge=10.f,HurtAmp=0.f;
    FVector KickFrom=FVector::ForwardVector,CameraBaseLocation=FVector::ZeroVector;
    // B5 flinch: up to six blows add up (the reference's spring), world-space rotation vectors in degrees.
    struct FReact { FVector Rock=FVector::ZeroVector; float Twist=0.f,Age=10.f; };
    FReact Reacts[6]; int32 NextReact=0;
    // B5 mesh flash (overlay material on the struck mesh), on the frame's own time like the reference.
    float MeshFlashAge=10.f,MeshFlashPeak=0.f;
    // Cached spine for the current dragon mesh.
    struct FChainBone { FName Bone; float Share=0.f; };
    mutable TWeakObjectPtr<const UObject> ChainMesh;
    mutable TArray<FChainBone> Chain;      // head first; signed shares (tail and leg roots negative)
    void BuildChain(AVeyrDragon* Boss) const;
    // B6 ribbon
    static constexpr int32 RibbonMaxSamples=24,RibbonSub=4,RibbonMaxRows=(RibbonMaxSamples-1)*RibbonSub+1;
    struct FRibbonSample { FVector Base=FVector::ZeroVector,Tip=FVector::ZeroVector; float Age=0.f,Strength=0.f; bool bHeavy=false; };
    FRibbonSample RibbonSamples[RibbonMaxSamples]; int32 RibbonCount=0;
    TArray<FVector> RibbonVerts,RibbonNormals; TArray<FLinearColor> RibbonColors; TArray<FVector2D> RibbonUVs;
    TArray<FProcMeshTangent> RibbonTangents; TArray<int32> RibbonTris;
    bool bRibbonReady=false,bRibbonCreated=false,bRibbonVisible=false;
    FVector PreviousRibbonTip=FVector::ZeroVector; bool bHaveRibbonTip=false;
    double LastRealTime=0;
    FVector PreviousBladeTip=FVector::ZeroVector;
    struct FTrailSegment {FVector Start,End;float Age=0.f,Strength=0.f;};
    TArray<FTrailSegment> Trail;
    void RequestHitStop(float Seconds);
    void RestoreTime();
    void StartShake(float Degrees,float Life,float Bounce,float Frequency,FName Kind,float Distance,bool bVaryPhase);
    void Flash(const FVector& Position,float Weight,USkeletalMeshComponent* Mesh=nullptr);
    void StartMeshFlash(USkeletalMeshComponent* Mesh,const FVector& Position,float Weight);
    void UpdateMeshFlash(float RealDelta);
    void UpdateRibbon(AVeyrKnight* Player,float GameDelta);
    void BindDragon();
};
