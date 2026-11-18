#pragma once
#include "CoreMinimal.h"
#include "Templates/Function.h"

class AVeyrKnight;
class AVeyrDragon;
class AActor;
class FJsonObject;
class UWorld;
class UVeyrSkeletalPresentation;

/**
 * Proof modes for quality-goal phase A1-A3 (2026-11-18), owned by AVeyrReplay:
 *   footclosehits  A1: every clip swept on a CPU pose probe (rigid-link stretch with and without the
 *                  mirrored-clip repair), then a live fight at the mirrored toe's leg.
 *   camerahug      A2: the knight hugs legs, belly, wings and tail while the camera orbits; every frame
 *                  checks the camera point against the dragon's bare body and wing shapes.
 *   soleheights    A3: every ground clip swept for sole height above the floor (no grounding), then a
 *                  live fight measuring the visible dragon's lowest sole each frame.
 * Drives input only, plus the camp mode's knight health refill so the run lasts; never moves actors.
 */
class FVeyrA123Proof
{
public:
    struct FHooks
    {
        TFunction<void(const FString&)> Shot;
        TFunction<void(bool,const FString&)> Finish;
    };
    static bool IsMode(const FString& Mode) { return Mode==TEXT("footclosehits")||Mode==TEXT("camerahug")||Mode==TEXT("soleheights"); }
    bool Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,const FString& InMode,FHooks InHooks);
    /** Owns the knight's input for this tick. */
    void Drive(double Elapsed,float Dt);
    TSharedPtr<FJsonObject> Evidence() const;
    float DurationLimit() const { return Mode==TEXT("camerahug")?240.f:180.f; }

private:
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    TWeakObjectPtr<AActor> ProbeActor;
    TWeakObjectPtr<UVeyrSkeletalPresentation> Probe;
    FString Mode;
    FHooks Hooks;
    bool bSwept=false,bDone=false,bPassed=false;
    double LiveStart=-1.0,LastShot=-100.0;
    float LiveSeconds=90.f;
    float Scale=1.f;           // dragon BodyScale / 2
    float BodyScale=2.f;
    int32 HealthRefills=0;
    TSharedPtr<FJsonObject> SweepJson;
    FString FailReason;

    // footclosehits
    float SweepMirroredRepairedMaxCm=0.f,SweepMirroredLegacyMaxCm=0.f,SweepUnmirroredMaxCm=0.f;
    FName SweepWorstBone;
    int32 MirroredClips=0;
    float LiveMaxStretchCm=0.f; FName LiveWorstBone; int32 LiveMirrorSamplesStart=0,LiveMirroredFrames=0,LiveFrames=0;

    // camerahug
    int32 CameraFrames=0,CameraInsideFrames=0,CollapseFrames=0,CollapseInsideFrames=0,PullInStart=0;
    float MaxLiftCm=0.f,MinFraction=1.f,MaxCameraJumpCm=0.f;
    FVector LastCameraRelative=FVector::ZeroVector; bool bHasLastCamera=false;
    TMap<FName,int32> InsideByShape;
    int32 WaypointIndex=0; double WaypointStart=0.0;

    // soleheights
    TArray<float> LiveGroundLowest;
    float WorstSweepFloatCm=0.f; FName WorstSweepClip;
    int32 SoleFailures=0;

    void Sweep();
    void SweepFootStretch();
    void SweepSoles();
    void Live(double Elapsed,float Dt);
    void Finalize(double Elapsed);
    void Input(const FVector& Move,bool bLight) const;
    FVector KnightTargetFor(double Elapsed);
    UVeyrSkeletalPresentation* MakeProbe();
};
