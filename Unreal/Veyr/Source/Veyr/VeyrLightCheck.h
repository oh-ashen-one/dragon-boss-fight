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
private:
    enum class EPhase : uint8 { WaitWorld, Setup, Hold, Capture, Settle, Done };
    struct FShot { FString Name; FName Segment; float HoldSeconds=1.5f; };
    UPROPERTY() TObjectPtr<ACameraActor> Camera;
    UPROPERTY() TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrDragon> Dragon;
    FString StillsDir, FrameDir;
    TArray<FShot> Shots;
    TArray<TSharedPtr<class FJsonValue>> ShotRecords;
    EPhase Phase=EPhase::WaitWorld;
    int32 ShotIndex=-1;
    float PhaseClock=0.f, TotalClock=0.f;
    bool bStrikeIssued=false, bSegmentStarted=false;
    FString PendingFile;
    FVector DragonHome=FVector::ZeroVector; FRotator DragonHomeRotation=FRotator::ZeroRotator;
    // Frame report
    bool bFrameRecording=false, bFrameDone=false;
    float FrameWarmup=0.f;
    double LastWall=0.0, FrameStartWall=0.0;
    TArray<float> FrameMs, GameMs, RenderMs, GpuMs;
    void TickStills(float DeltaSeconds);
    void TickFrameReport();
    void WriteFrameReport();
    bool BeginShot();
    bool ReadyToCapture() const;
    void PlaceCamera();
    void PlaceActors();
    void FinishStills();
    void MaybeQuit();
};
