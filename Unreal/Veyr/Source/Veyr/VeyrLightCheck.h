#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrLightCheck.generated.h"

class ACameraActor;
class AVeyrKnight;
class AVeyrDragon;

/** Phase C picture evidence.
 *  -VeyrLightCheck=<abs dir>: the same ten stills every run (fixed actor placement, scripted
 *   showcase moves, fixed camera rules), PNGs + lightcheck.json, then quit.
 *  -VeyrFrameReport=<abs dir>: with any fight replay, 60 s of frame times from the first
 *   encounter frame (after a 2 s warm-up) to frame-report.json. -VeyrFrameReportQuit exits after. */
UCLASS()
class VEYR_API AVeyrLightCheck : public AActor
{
    GENERATED_BODY()
public:
    AVeyrLightCheck();
    void Initialize(const FString& StillsDirectory,const FString& FrameDirectory);
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    enum class EPhase : uint8 { WaitWorld, Setup, Hold, Capture, Settle, Breath, Done };
    /** PreRollSeconds: placed and still before the knight's input, so exposure has settled. */
    struct FShot { FString Name; FName Segment; float HoldSeconds=1.5f; float PreRollSeconds=0.f; };
    UPROPERTY() TObjectPtr<ACameraActor> Camera;
    UPROPERTY() TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrDragon> Dragon;
    FString StillsDir, FrameDir;
    TArray<FShot> Shots;
    TArray<TSharedPtr<class FJsonValue>> ShotRecords;
    EPhase Phase=EPhase::WaitWorld;
    int32 ShotIndex=-1;
    float PhaseClock=0.f, TotalClock=0.f;
    bool bStrikeIssued=false, bSegmentStarted=false, bPreRollDone=true;
    float BuildWaitSeconds=0.f;
    FString PendingFile;
    FVector DragonHome=FVector::ZeroVector; FRotator DragonHomeRotation=FRotator::ZeroRotator;
    // Frame report
    bool bFrameRecording=false, bFrameDone=false;
    float FrameWarmup=0.f, RecordedSeconds=0.f;
    double LastWall=0.0;
    /** Frames left out of the report: paused, or the frames around a cut or a screenshot. */
    int32 SkipFrames=0, SkippedPaused=0, SkippedTool=0;
    TArray<float> FrameMs, GameMs, RenderMs, GpuMs, ExposureFrames;
    /** 10 Hz exposure trace from spawn (intro included) to the report: t, phase, exposure, luminance. */
    TArray<FString> ExposureTrace;
    float TraceClock=0.f, NextTraceSample=0.f;
    void TickStills(float DeltaSeconds);
    void TickFrameReport();
    void WriteFrameReport(bool bPartial=false);
    int32 OutstandingBuilds(FString& What) const;
    bool BeginShot();
    bool ReadyToCapture() const;
    void PlaceCamera();
    void PlaceActors();
    void FinishStills();
    /** After the stills: -VeyrLightCheckBreathSeconds=N (default 30, 0 = off) of repeated fire breath from the
     *  shot-05 camera; frame times only while the beam is live go to breath-report.json. */
    void BeginBreath();
    void TickBreath(float DeltaSeconds);
    void WriteBreathReport();
    float BreathSeconds=30.f, BreathClock=0.f, BreathRest=0.f;
    double BreathLastWall=0.0;
    int32 BreathCount=0;
    TArray<float> BreathMs, BreathGpuMs, BreathExposure;
    void MaybeQuit();
};
