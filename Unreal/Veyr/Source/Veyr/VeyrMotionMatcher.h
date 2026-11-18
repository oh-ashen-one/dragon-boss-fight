#pragma once

#include "CoreMinimal.h"
#include "Animation/TrajectoryTypes.h"
#include "UObject/StrongObjectPtr.h"
#include "VeyrSingleNodeInstance.h"

class UAnimSequence;
class UAnimInstance;
class UPoseSearchDatabase;
class USkeletalMeshComponent;
namespace UE::PoseSearch { struct FPoseHistory; }

// Quality goal E5: motion matching for Greystone locomotion, in plain C++ on top of our explicit sampler (the
// reference hero's structure: SIM spring moves the capsule, the shown body plays ONE clip at ONE time, inertialized
// switches, capsule-follows-body coupling, gates in C++ instead of Chooser tables, actions never searched).
// Design: docs/greystone/motion-matching.md. Status: written blind (no engine); not wired into the knight yet.
// Off unless the knight is Greystone AND -VeyrMotionMatching is given; -VeyrLegacyMotion always restores today's
// clip selection (and -VeyrLegacyKnight restores KnightB entirely).

/** What the search may return this frame. One gate is active at a time; actions suspend matching entirely. */
enum class EVeyrMotionGate : uint8 { Idle, Start, Loop, Stop, Pivot, TurnInPlace, Count };

/** Spring movement model (SIM): critically damped velocity toward the desired velocity, yaw toward the desired
 * facing. Positions in world cm, yaw in degrees. Same model predicts the future trajectory for the query. */
struct FVeyrSpringTrajectory
{
    FVector Position=FVector::ZeroVector;
    FVector Velocity=FVector::ZeroVector;
    FVector Acceleration=FVector::ZeroVector;
    float Yaw=0.f;
    float YawRate=0.f;
    float VelocityHalfLife=.20f;  // reference hero: about 0.2 s
    float YawHalfLife=.12f;

    void Reset(const FVector& InPosition,float InYaw);
    void Step(const FVector& DesiredVelocity,float DesiredYaw,float Dt);
    /** Predicted position/yaw after Seconds from the current state (closed form, no integration error). */
    void Predict(const FVector& DesiredVelocity,float DesiredYaw,float Seconds,FVector& OutPosition,float& OutYaw) const;
    /** History (from Recorded) + current + future samples at FutureTimes, world space, for UE PoseSearch. */
    FTransformTrajectory BuildTrajectory(const TArray<FTransformTrajectorySample>& Recorded,const FVector& DesiredVelocity,
        float DesiredYaw,TConstArrayView<float> FutureTimes) const;
};

/** 33 floats in character (capsule) space: L/R foot pos, L/R hand pos, L/R foot vel, hips vel (3 each = 21),
 * trajectory XY positions at 1/3, 2/3, 1 s (6), trajectory facing XY at the same times (6). */
struct FVeyrMotionFeatures
{
    static constexpr int32 Num=33;
    float Values[Num]={};
};

/** Fallback search: a baked table (tools/unreal/greystone/bake_motion_features.py), brute force, normalized,
 * weighted squared distance, filtered by gate. Used when the PoseSearch API is unavailable or misbehaves outside an
 * AnimGraph (-VeyrMotionFallback forces it). */
struct FVeyrMotionFeatureTable
{
    struct FRow
    {
        FName Clip;
        float Time=0.f;
        uint8 GateMask=0; // bit per EVeyrMotionGate
        FVeyrMotionFeatures Features;
    };
    TArray<FRow> Rows;
    float Mean[FVeyrMotionFeatures::Num]={};
    float InverseStd[FVeyrMotionFeatures::Num]={};
    float Weights[FVeyrMotionFeatures::Num]={};
    FString Source;

    /** JSON: {"schema":"veyr-motion-features-v1","mean":[33],"std":[33],"weights":[33],
     *  "rows":[{"clip":"A_GS_Jog_Fwd_Loop","time":0.5,"gates":["Loop"],"f":[33]}]} */
    bool LoadJson(const FString& File,FString& OutError);
    float Cost(const FVeyrMotionFeatures& Query,const FRow& Row) const;
    int32 Search(const FVeyrMotionFeatures& Query,EVeyrMotionGate Gate,float& OutCost) const;
};

/** Reference rule set (Warden): starts by angle, stops only on input release, pivots at >= 135 degrees between the
 * current velocity and the desired one, steady cycle otherwise. Returns the gate and whether it changed (forced search). */
struct FVeyrMotionGates
{
    EVeyrMotionGate Current=EVeyrMotionGate::Idle;
    float StartSpeedCmPerSecond=40.f;
    float StopSpeedCmPerSecond=30.f;
    float PivotDegrees=135.f;
    float TurnInPlaceDegrees=60.f;

    bool Update(const FVector& Velocity,const FVector& DesiredVelocity,bool bInputHeld,float FacingErrorDegrees);
};

/** The shown body moves by the clip's own root track; the capsule (gameplay-authoritative: hitboxes, difficulty)
 * moves by the spring. Each frame the body is pulled toward the capsule by at most 20 % of the clip's own travel
 * that frame and is never further than 15 cm from it, so feet do not slide and the capsule never waits for the body. */
struct FVeyrCapsuleCoupling
{
    FVector BodyOffset=FVector::ZeroVector; // planar, world cm, body minus capsule
    float MaxSeparationCm=15.f;
    float MaxCorrectionShare=.20f;
    int32 ClampedSteps=0,Steps=0;   // review metric: how often the 15 cm clamp had to engage (visible slide)
    float WorstSeparationCm=0.f;     // before the clamp

    void Reset(){BodyOffset=FVector::ZeroVector;ClampedSteps=Steps=0;WorstSeparationCm=0.f;}
    /** ClipTravel: planar world displacement of the clip root this frame. CapsuleTravel: what the capsule did. */
    FVector Step(const FVector& ClipTravel,const FVector& CapsuleTravel);
};

/** Result of one matcher step. */
struct FVeyrMotionChoice
{
    const UAnimSequence* Sequence=nullptr;
    FName FallbackClip;      // set when the fallback table chose: the sequence object path (rows store paths)
    float Time=0.f;
    bool bMirrored=false;
    float Cost=MAX_flt;
    bool bSwitched=false;    // the caller samples the new clip and starts an inertial switch
    bool bFromFallback=false;
};

class FVeyrMotionMatcher
{
public:
    FVeyrMotionMatcher();
    ~FVeyrMotionMatcher();

    /** Load databases by gate from DatabaseFolder (names containing Idle/Start/Loop/Stop/Pivot/Turn) and the fallback
     * table. Safe to call again after a definition change. */
    bool Initialize(USkeletalMeshComponent* Mesh,const FString& DatabaseFolder,const FString& FallbackTableFile,FString& OutError);
    bool IsReady() const {return bReady;}

    /** Once per frame, after the frame's final sample: record the shown pose and root into the pose history. */
    void RecordShownPose(const USkeletalMeshComponent* Mesh,float Dt);
    /** Once per frame before sampling. DesiredVelocity in world cm/s from input; FacingYaw desired facing (deg).
     * bActionPlaying suspends matching (actions are never searched). Returns the clip/time to show. */
    FVeyrMotionChoice Step(UAnimInstance* AnimContext,const FVector& CapsuleLocation,float CapsuleYaw,const FVector& DesiredVelocity,
        float DesiredYaw,bool bInputHeld,bool bActionPlaying,float Dt);
    /** The shown clip advanced by the caller (gameplay clock): keep our continuing time in step. */
    void AdvanceCurrent(float SourceSeconds);

    const FVeyrSpringTrajectory& Spring() const {return Sim;}
    FVeyrCapsuleCoupling Coupling;
    FVeyrInertialSwitch SwitchFor(EVeyrMotionGate From,EVeyrMotionGate To) const;
    TSharedRef<class FJsonObject> Evidence() const;

    float SearchInterval=.05f;      // 20 Hz
    float SwitchCostRatio=2.f;      // switch only if current > ratio * best + bias
    float SwitchCostBias=.3f;
    float MinSecondsBetweenSwitches=.10f;
    static constexpr float FutureTimes[3]={1.f/3.f,2.f/3.f,1.f};

private:
    bool bReady=false;
    bool bForceFallback=false;
    FString LastError;
    TSharedPtr<UE::PoseSearch::FPoseHistory> History;
    TArray<FTransformTrajectorySample> RecordedRoot;
    FVeyrSpringTrajectory Sim;
    FVeyrMotionGates Gates;
    FVeyrMotionFeatureTable Fallback;
    TArray<TStrongObjectPtr<UPoseSearchDatabase>> Databases[static_cast<int32>(EVeyrMotionGate::Count)];
    FVeyrMotionChoice Current;
    EVeyrMotionGate CurrentGate=EVeyrMotionGate::Idle;
    float SinceSearch=0.f,SinceSwitch=0.f,Clock=0.f;
    int32 Searches=0,Switches=0,FallbackSearches=0,ForcedSearches=0;

    bool SearchPoseSearch(UAnimInstance* AnimContext,EVeyrMotionGate Gate,FVeyrMotionChoice& Out);
    bool SearchFallback(const USkeletalMeshComponent* Mesh,EVeyrMotionGate Gate,const FVector& DesiredVelocity,float DesiredYaw,FVeyrMotionChoice& Out);
    TWeakObjectPtr<const USkeletalMeshComponent> LastMesh;
    // Fallback query needs velocities: last frame's component-space feet/hips.
    FVector LastFeet[2]={FVector::ZeroVector,FVector::ZeroVector},LastHips=FVector::ZeroVector;
    bool bHaveLastFeet=false;
    float LastDt=1.f/60.f;
};
