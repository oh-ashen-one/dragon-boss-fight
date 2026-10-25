#pragma once
#include "CoreMinimal.h"
#include "Async/Future.h"
#include "GameFramework/Actor.h"
#include "VeyrReplay.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class FJsonObject;
class FJsonValue;
class UPrimitiveComponent;
enum class EVeyrDragonMove : uint8;

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
    static bool GetPendingRestartRequest(FString& OutMode, FString& OutEvidenceDirectory);
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
    bool bRestartAttackInputIssued=false;
    bool bVictoryStartTwoHandedRequested=false,bVictoryGripInputIssued=false,bVictoryGripTransitionCompleted=false;
    float TerminalSeconds=-1, TerminalClock=0, RestartClock=0;
    FVector RestartOrigin=FVector::ZeroVector;
    float Elapsed=0, SampleClock=0, SaveClock=0, CaptureClock=0, FinishClock=0;
    float DurationLimit=180, MaximumFrameSeconds=0;
    int32 FrameCount=0, ScreenshotIndex=0, TargetLeg=2;
    int32 ObservedWarningContainmentFailures=0;
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
    int32 BoundaryStage=0, VerifiedHealCharges=0, TrialCharges=0, TrialHeals=0, TrialHits=0;
    float BoundaryStageStarted=0, TrialHealth=0;
    bool bHealCapVerified=false, bEmptyHealRejected=false;
    bool bFrontGuardVerified=false, bRearGuardVerified=false, bGuardBreakVerified=false;
    bool bGuardRechargeLatched=false, bRearGuardArmed=false;
    int32 GuardRechargeCount=0;
    float LastObservedFullDamageGuardCost=0.f;
    bool bGuardSampleValid=false, bGuardSampleHeld=false, bGuardSampleGrounded=false;
    float GuardSampleHealth=100, GuardSampleStamina=100, GuardSampleFacing=0;
    int32 GuardSampleHits=0, GuardSampleBlocks=0, GuardSampleBreaks=0;
    TArray<TSharedPtr<FJsonValue>> BoundaryTrials;
    int32 StanceTrialIndex=0,StanceAttempt=0,StanceSafeSwitches=0;
    int32 StanceContactsBefore=0,StanceActionsBefore=0,StanceHitsBefore=0;
    float StanceRequestedAt=0,StanceSwitchAt=-1,StanceBossHealthBefore=0,StanceStaminaBefore=0;
    float StanceDamage[4]={0,0,0,0},StanceDurations[4]={0,0,0,0},StanceRollDurations[2]={0,0};
    bool bStanceIdleVerified=false,bStancePending=false,bStanceActionObserved=false,bStanceContactVerified=false;
    FBox StanceIdleDragonHeadBounds=FBox(ForceInit),StanceIdleKnightHeadBounds=FBox(ForceInit);
    int32 StanceIdlePoseSamples=0;
    bool bStanceSwitchBlocked=false,bStanceRollInvulnerable=false,bStanceRollRecovery=false;
    bool bStanceInterrupted=false,bStancePassed=false;
    TSharedPtr<FJsonObject> StanceCurrentTrial;
    TArray<TSharedPtr<FJsonValue>> StanceTrials;
    // Input-only integration coverage. These clocks/counters belong to the replay,
    // never to the Knight or encounter simulation.
    int32 IntegrationStage=0,IntegrationPhase=0,IntegrationAttempt=0;
    int32 IntegrationCompleted=0,IntegrationMaxKnightFailures=0,IntegrationMaxDragonFailures=0;
    int32 IntegrationContactsBefore=0,IntegrationHitsBefore=0,IntegrationEchoesBefore=0;
    int32 IntegrationRollsBefore=0,IntegrationRollAttacksBefore=0;
    int32 IntegrationLightBefore=0,IntegrationHeavyBefore=0,IntegrationBlinksBefore=0;
    bool bIntegrationBlinkRequested=false;
    float IntegrationMaximumSourceTime=0,IntegrationPeakSpeed=0;
    float IntegrationStageStarted=0,IntegrationConfiguredAt=0,IntegrationObservedSeconds=0;
    float IntegrationRequestedAt=0,IntegrationRecoveryStarted=0,IntegrationLastObservedAt=0;
    bool bIntegrationIssued=false,bIntegrationAccepted=false,bIntegrationMidCapture=false;
    bool bIntegrationRollPrefix=false,bIntegrationRollQueued=false,bIntegrationRunStop=false;
    bool bIntegrationHiddenSeen=false,bIntegrationEchoVisible=false,bIntegrationFallback=false;
    FVector IntegrationOrigin=FVector::ZeroVector,IntegrationDirection=FVector::ZeroVector;
    FString IntegrationFeature;
    FName IntegrationExpectedClip=NAME_None;
    TMap<FName,int32> IntegrationKnightClips,IntegrationDragonClips;
    TSharedPtr<FJsonObject> IntegrationTrial;
    TArray<TSharedPtr<FJsonValue>> IntegrationTrials;
    TSharedPtr<FJsonObject> IntegrationEvidence(bool bIncludeTrials=false) const;
    bool DriveIntegrationInputs();
    bool bStanceGripPending=false,bStanceGripTarget=false;
    float StanceGripRequestedAt=0;
    bool DriveCollisionInputs();
    bool DriveAnatomyCollisionInputs();
    TSharedPtr<FJsonObject> CollisionEvidence(bool bIncludeTrials=false) const;
    UFUNCTION() void ObserveCollisionHit(UPrimitiveComponent* HitComponent,AActor* OtherActor,UPrimitiveComponent* OtherComponent,FVector NormalImpulse,const FHitResult& Hit);
    int32 CollisionStage=0,CollisionPhase=0,CollisionHits=0,CollisionHitsBefore=0,CollisionRootBlocksBefore=0,CollisionCompleted=0,CollisionAttempts=0;
    float CollisionStageStarted=0,CollisionInputStarted=0,CollisionSurfaceSeconds=0,CollisionLastObserved=0;
    float CollisionIndependentDepth=0,CollisionMaximumDepth=0,CollisionPenetratingSeconds=0,CollisionMaximumPersistentSeconds=0;
    float CollisionPredictedDistance=0,CollisionExpectedFreeTravel=0;
    bool bCollisionArmed=false,bCollisionActionObserved=false;
    FName CollisionTargetShape=NAME_None,CollisionLastHitShape=NAME_None;
    FVector CollisionOrigin=FVector::ZeroVector,CollisionDirection=FVector::ForwardVector;
    FVector CollisionLastHitPoint=FVector::ZeroVector,CollisionLastHitNormal=FVector::ZeroVector;
    TArray<TSharedPtr<FJsonValue>> CollisionTrials;
    TMap<FName,int32> CollisionComponentHits,CollisionComponentPushes;
    TMap<FName,float> CollisionComponentMaximumDepth;
    int32 CollisionLastObservedPushes=0,CollisionLandingPushes=0,CollisionLandingAttempts=0;
    bool bCollisionRegionContactObserved=false,bCollisionFlightObserved=false,bCollisionLandingObserved=false,bCollisionTorsoProbeHit=false;
    float CollisionTorsoProbeHeight=0.f;
    FName CollisionRegionContactShape=NAME_None;
    FVector CollisionRegionContactDirection=FVector::ZeroVector,CollisionRegionContactPoint=FVector::ZeroVector;

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
    bool DriveBoundaryInputs();
    bool DriveStanceInputs();
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
    FVector GuardDamageSource() const;
    FVector HeadApproachGoal(FName* OutBlocker=nullptr,float* OutSweepDistance=nullptr) const;
    float AuthoredKnightSeconds(FName Clip,float Fallback) const;
    float DragonPhaseSeconds(EVeyrDragonMove Move,const TCHAR* Phase,float Fallback) const;
    float SafeStationarySeconds(const FVector& Point) const;
    float DangerContactDelay() const;
    bool LandingDangerPending() const;
    void TrackFlightWithLookInput();
    bool bCombatHealSeeking=false;
    int32 CombatHealCountAtRequest=0;
    float BoundaryHealDuration=0,BoundaryEmptyObservation=0;

};
