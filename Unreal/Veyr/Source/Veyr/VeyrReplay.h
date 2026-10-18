#pragma once
#include "CoreMinimal.h"
#include "Async/Future.h"
#include "GameFramework/Actor.h"
#include "VeyrReplay.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class FJsonObject;
class FJsonValue;

/** Value-only result: no UObject or replay-owned pointers cross the worker boundary. */
struct FVeyrVideoWriteResult
{
    FString File, SourceId;
    int32 Index=0, WorldIndex=0, Width=0, Height=0;
    double CapturedWallSeconds=0, RequestedWallSeconds=0, RequestedGameSeconds=0;
    double PixelCopySeconds=0, PNGWriteSeconds=0;
    bool bSaved=false;
};

/** Optional input-only native validation. No authority to alter encounter state. */
UCLASS()
class VEYR_API AVeyrReplay : public AActor
{
    GENERATED_BODY()
public:
    AVeyrReplay();
    bool Initialize(const FString& Mode, const FString& EvidenceDirectory);
    virtual void Tick(float DeltaSeconds) override;
protected:
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    UPROPERTY() TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrDragon> Dragon;
    FString ReplayMode, RunDirectory, OutcomeReason;
    bool bInitialized=false, bFinished=false, bFinalSaved=false, bPassed=false, bQuit=false;
    bool bLightLegContact=false, bHeavyLegContact=false, bSawRise=false, bRiseCompleted=false;
    bool bTerminalSettling=false, bAwaitingReload=false, bRestartVerification=false;
    bool bFreshResourcesVerified=false, bRestartMoved=false, bRestartAttackAccepted=false;
    float TerminalSeconds=-1, TerminalClock=0, RestartClock=0;
    FVector RestartOrigin=FVector::ZeroVector;
    float Elapsed=0, SampleClock=0, SaveClock=0, CaptureClock=0, FinishClock=0;
    float DurationLimit=180, MaximumFrameSeconds=0;
    int32 FrameCount=0, ScreenshotIndex=0, TargetLeg=2;
    int32 PreviousDragonState=-1, PreviousKnightAction=-1, PreviousContacts=0;
    int32 PreviousDodges=0, PreviousDamage=0, PreviousHeals=0, PreviousJumps=0;
    bool bLegIsolation=false, bIsolationViolated=false, bIsolatedStagger=false, bCorrectLegBuckle=false;
    bool bFullHealthHealRejected=false, bFullHealthHealRequested=false, bLockOffObserved=false, bLockOnObserved=false;
    bool bControlMovement=false, bControlStaminaSpent=false, bControlStaminaRecovered=false;
    bool bControlJumpAirborne=false, bControlJumpLanded=false, bAvoidanceGoalAvailable=false;
    float ControlJumpStartFootZ=0, ControlJumpMaximumRise=0;
    int32 DesiredAvoidanceMove=-1;
    FVector AvoidanceGoal=FVector::ZeroVector;
    bool bAvoidanceThreatObserved=false;
    int32 ObservedAttack=-1, ObservedAttackHits=0, ControlStage=0;
    int32 AvoidedMoves[6]={0,0,0,0,0,0};
    float ControlStageStarted=0, ControlStaminaBefore=100;
    FVector ControlOrigin=FVector::ZeroVector;
    TArray<TSharedPtr<FJsonValue>> Samples, Events;
    TArray<TSharedPtr<FJsonValue>> CaptureStates;
    TArray<FString> CaptureQueue, CaptureNames, CaptureFiles;
    TArray<double> CaptureTimes;
    TArray<double> CaptureTriggerTimes;
    double PendingCaptureTriggerTime=0;
    double LastWallFrameTime=0, RestartLoadSeconds=0;
    double StartedWallTime=0;
    int32 VideoFPS=0, VideoFrameIndex=0, VideoFramesSaved=0, VideoSkippedSlots=0, VideoFailedFrames=0, VideoWorldIndex=0;
    bool bVideoStopped=false, bVideoPixelsReceived=false;
    double VideoStartedWallTime=0, VideoNextWallTime=0, VideoRequestWallTime=0, VideoRequestGameTime=0;
    double VideoWriteSeconds=0, VideoPixelCopySeconds=0;
    TFuture<FVeyrVideoWriteResult> VideoWriteFuture;
    FString VideoDirectory, PendingVideoFile, VideoStopReason;
    FDelegateHandle VideoPixelsHandle, VideoProcessedHandle;
    TArray<double> WallFrameIntervals;
    TSharedPtr<FJsonObject> LastEvidence;
    TSharedPtr<FJsonObject> Snapshot() const;
    void Observe();
    void DriveInputs();
    bool DriveScenarioInputs();
    void ObserveScenarios();
    bool AllMovesAvoided() const;
    void Event(const FString& Name, bool bScreenshot=true);
    void ServiceCapture();
    void InitializeVideo();
    void ServiceVideoCapture();
    void OnVideoPixels(int32 Width, int32 Height, const TArray<FColor>& Pixels);
    void OnVideoRequestProcessed();
    void ConsumeVideoWrite(bool bWait=false);
    void StopVideoCapture(const FString& Reason);
    bool AppendVideoRecord(const TSharedRef<FJsonObject>& Record);
    void SaveEvidence(bool bFinal);
    void Finish(bool bSuccess, const FString& Reason);
    void BeginTerminalVerification();
    void AdvanceRestart(float DeltaSeconds);
    FVector EscapeDirection() const;
};
