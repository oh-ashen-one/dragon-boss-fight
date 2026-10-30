#pragma once
#include "CoreMinimal.h"
#include "Templates/Function.h"

class AVeyrKnight;
class AVeyrDragon;
class ACameraActor;
class UInstancedStaticMeshComponent;
class FJsonObject;
class FJsonValue;
class UWorld;

/**
 * Engine-side visual proof tooling for the knight ("blendproof" replay mode, 2026-10-29).
 * Plain C++ helper owned by AVeyrReplay; it drives input only (never writes health, clocks or positions),
 * frames a fixed chase camera, optionally lays a 25 cm checker over the floor and records per-frame
 * sword/hand/foot/capsule evidence, then prints one VEYR_GATE line per sequence.
 */
class FVeyrBlendProof
{
public:
    struct FHooks
    {
        TFunction<void(const FString&)> Shot;            // event + forced screenshot
        TFunction<void(bool,const FString&)> Finish;     // end the replay
    };
    struct FFrame
    {
        int32 Seq=0; uint8 Phase=0; // 0 pre-idle, 1 action, 2 post-idle
        double T=0; float Dt=0, ActionElapsed=0, Alpha=1.f, FloorZ=0;
        FName Clip, From; FString Action; int32 Serial=0; bool bBlend=false, bHidden=false;
        FVector Capsule=FVector::ZeroVector, Toe[2]={FVector::ZeroVector,FVector::ZeroVector}, Ankle[2]={FVector::ZeroVector,FVector::ZeroVector};
        FVector Sword=FVector::ZeroVector, Hand=FVector::ZeroVector, SwordLocal=FVector::ZeroVector;
        bool bSwordValid=false, bHandValid=false, bFeetValid=false;
        float SwordHandCm=0.f, SwordExcessCm=0.f, SwordLocalErrCm=0.f;
        float CapsuleTravel=0.f, ToeTravel[2]={0.f,0.f}, AnkleTravel[2]={0.f,0.f};
        float ToeHeight[2]={0.f,0.f}, AnkleHeight[2]={0.f,0.f};
        bool bToePlanted[2]={false,false}, bAnklePlanted[2]={false,false};
        bool bFootPlanted[2]={false,false}; float FootSlide[2]={0.f,0.f}; // foot gate: toe AND ankle planted; windowed cm/s
    };

    bool Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,const FString& InRunDirectory,bool bProofFloor,FHooks InHooks);
    /** Called once per replay tick before capture; owns input for the tick. */
    void Drive(double Elapsed,float Dt);
    bool IsDone() const { return bDone; }
    TSharedPtr<FJsonObject> Evidence() const;
    TSharedPtr<FJsonObject> CurrentState() const;

private:
    enum class EKind : uint8 { Strafe, Blink, RollAttack };
    enum class EPhase : uint8 { Setup, PreIdle, Action, PostIdle };
    struct FDef
    {
        const TCHAR* Name; EKind Kind; int32 Dir; // 0 fwd 1 back 2 left 3 right
        bool bSprint, bTwo; float ActionSeconds, ExpectedTravelCm; const TCHAR* ExpectedClip; float CameraAzimuthDeg;
    };
    struct FSequenceResult
    {
        int32 Index=0; FString Name, Reason; bool bPassed=false, bCompleted=false;
        double GameStart=0, GameEnd=0; int32 Frames=0;
        TSharedPtr<FJsonObject> Metrics;
    };
    static const FDef& Def(int32 Index);
    static int32 DefCount();

    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    TWeakObjectPtr<ACameraActor> Camera;
    TWeakObjectPtr<UInstancedStaticMeshComponent> Checker;
    FHooks Hooks;
    FString RunDirectory, FramesFile;
    bool bDone=false, bBegan=false, bProofFloorApplied=false, bCameraApplied=false;
    int32 CheckerInstances=0;
    FVector Home=FVector::ZeroVector, Fwd0=FVector::ForwardVector, Right0=FVector::RightVector;
    float FloorZ=0.f;
    FVector Focus=FVector::ZeroVector; bool bFocusValid=false;

    int32 SeqIndex=0; EPhase Phase=EPhase::Setup;
    double SeqPhaseStart=0, SeqSetupStart=-1, ActionStart=0;
    int32 ActionSub=0, ActionTries=0; double ActionSubStart=0;
    float SetupStable=0.f; bool bSetupTimedOut=false, bActionIssued=false, bActionTimedOut=false, bRollUpgradeIssued=false, bRollUpgradeSeen=false;
    bool bExpectedActionSeen=false;
    int32 LastSerial=-1; bool bPendingMid=false; int32 MidSerial=0; FName MidFrom, MidTo; bool bMidActionShot=false;
    TArray<FFrame> Frames;
    TArray<FSequenceResult> Results;
    TArray<TSharedPtr<FJsonValue>> SequenceJson;
    int32 PassedCount=0;
    double LastT=0;

    void Input(const FVector& Dir,bool bSprint) const;
    FVector SequenceStart(const FDef& D) const;
    FVector DirVector(const FDef& D) const;
    void ApplyCamera(float Dt,bool bSnap);
    void BuildChecker();
    void Sample(double Elapsed,float Dt);
    void BeginSequence(double Elapsed);
    void FinalizeSequence(double Elapsed);
    void EnterPhase(EPhase P,double Elapsed);
    void DriveSetup(double Elapsed,float Dt);
    void DriveAction(double Elapsed,float Dt);
    void Neutral() const;
};
