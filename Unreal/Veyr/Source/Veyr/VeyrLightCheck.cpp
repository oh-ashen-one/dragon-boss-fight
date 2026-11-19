#include "VeyrLightCheck.h"
#include "VeyrArena.h"
#include "VeyrDragon.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrLook.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "DistanceFieldAtlas.h"
#include "DynamicRHI.h"
#include "EngineUtils.h"
#include "MeshCardBuild.h"
#include "ShaderCompiler.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RenderTimer.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UnrealClient.h"

namespace
{
    constexpr float FrameReportSeconds=60.f, FrameWarmupSeconds=2.f;
    float Percentile(TArray<float> Values,float Q)
    {
        if(Values.IsEmpty())return 0.f;
        Values.Sort();
        return Values[FMath::Clamp(FMath::FloorToInt(Q*(Values.Num()-1)+.5f),0,Values.Num()-1)];
    }
    float Mean(const TArray<float>& Values)
    {
        double Sum=0;for(float V:Values)Sum+=V;
        return Values.IsEmpty()?0.f:static_cast<float>(Sum/Values.Num());
    }
    TSharedRef<FJsonObject> Stats(const TArray<float>& Values)
    {
        auto O=MakeShared<FJsonObject>();
        O->SetNumberField(TEXT("mean"),Mean(Values));O->SetNumberField(TEXT("p50"),Percentile(Values,.5f));
        O->SetNumberField(TEXT("p95"),Percentile(Values,.95f));O->SetNumberField(TEXT("p99"),Percentile(Values,.99f));
        float Max=0.f;for(float V:Values)Max=FMath::Max(Max,V);O->SetNumberField(TEXT("max"),Max);
        return O;
    }
    void SaveJson(const TSharedRef<FJsonObject>& Root,const FString& File)
    {
        FString Text;const TSharedRef<TJsonWriter<>> Writer=TJsonWriterFactory<>::Create(&Text);
        FJsonSerializer::Serialize(Root,Writer);FFileHelper::SaveStringToFile(Text,*File);
    }
    TSharedRef<FJsonObject> LookFields(UWorld* World)
    {
        auto O=MakeShared<FJsonObject>();
        O->SetBoolField(TEXT("breathShadow"),VeyrLook::BreathShadow());O->SetBoolField(TEXT("poolShadows"),VeyrLook::FloorPoolShadows());
        O->SetNumberField(TEXT("brazierShadowBudget"),VeyrLook::ShadowedFireBudget());
        if(World)if(TActorIterator<AVeyrArena> It(World);It)
        {
            O->SetNumberField(TEXT("lumenSplitComponents"),It->GetLumenSplitComponentCount());
            O->SetNumberField(TEXT("shadowedCourtLightsAtEnd"),It->CountShadowedCourtLights());
        }
        O->SetBoolField(TEXT("legacyRender"),VeyrLook::IsLegacy());O->SetNumberField(TEXT("renderTier"),VeyrLook::RenderTier());
        O->SetBoolField(TEXT("lumenSplit"),VeyrLook::SplitInstancesForLumen());O->SetStringField(TEXT("commandLine"),FCommandLine::Get());
        if(GEngine&&GEngine->GameViewport&&GEngine->GameViewport->Viewport)
        {
            const FIntPoint Size=GEngine->GameViewport->Viewport->GetSizeXY();
            O->SetNumberField(TEXT("width"),Size.X);O->SetNumberField(TEXT("height"),Size.Y);
        }
        return O;
    }
}

AVeyrLightCheck::AVeyrLightCheck()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.bTickEvenWhenPaused=true;
    // Before the camera manager updates (LevelTick: UpdateCameraManager precedes TG_PostUpdateWork),
    // so a moved camera and its camera-cut flag land on the same rendered frame.
    PrimaryActorTick.TickGroup=TG_PrePhysics;
}

void AVeyrLightCheck::Initialize(const FString& StillsDirectory,const FString& FrameDirectory)
{
    StillsDir=StillsDirectory;FrameDir=FrameDirectory;
    if(!StillsDir.IsEmpty())IFileManager::Get().MakeDirectory(*StillsDir,true);
    if(!FrameDir.IsEmpty())IFileManager::Get().MakeDirectory(*FrameDir,true);
    // Same list, order and hold times every run, so sheets can be rebuilt after each change.
    Shots={
        {TEXT("01_wide_courtyard"),NAME_None,2.5f},
        {TEXT("02_knight_closeup"),NAME_None,1.8f},
        {TEXT("03_dragon_front"),TEXT("Roar"),1.2f},
        {TEXT("04_under_dragon"),NAME_None,1.8f},
        {TEXT("05_fire_breath"),TEXT("Fire"),8.f},
        {TEXT("06_knight_strike"),NAME_None,.38f,1.f},
        {TEXT("07_dragon_claw"),TEXT("Claw0"),6.f},
        {TEXT("08_collapse"),TEXT("Stagger0"),10.f},
        {TEXT("09_flight"),TEXT("Flight"),8.f},
        {TEXT("10_dark_corner"),NAME_None,1.8f}};
    LastWall=FPlatformTime::Seconds();
    UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_BEGIN stills=%s frames=%s legacy=%d tier=%d"),*StillsDir,*FrameDir,VeyrLook::IsLegacy(),VeyrLook::RenderTier());
}

void AVeyrLightCheck::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!Knight||!Dragon)
        if(const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>()){Knight=Mode->Knight;Dragon=Mode->Dragon;}
    if(!FrameDir.IsEmpty())TickFrameReport();
    if(!StillsDir.IsEmpty())TickStills(FMath::Min(DeltaSeconds,.1f));
}

void AVeyrLightCheck::TickFrameReport()
{
    const double Now=FPlatformTime::Seconds();const float Wall=static_cast<float>((Now-LastWall)*1000.0);LastWall=Now;
    if(bFrameDone||!Knight)return;
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    const bool bFighting=Knight->HasEnteredEncounter()&&Mode&&!Mode->IsArenaIntroActive();
    TraceClock+=Wall/1000.f;
    if(TraceClock>=NextTraceSample)
    {
        NextTraceSample=TraceClock+.1f;
        const TCHAR* PhaseName=Mode&&Mode->IsArenaIntroActive()?TEXT("intro"):bFighting?TEXT("fight"):TEXT("other");
        ExposureTrace.Add(FString::Printf(TEXT("%.2f,%s,%.5f,%.5f,%.3f"),TraceClock,PhaseName,VeyrLook::LastExposure(),VeyrLook::LastSceneLuminance(),VeyrLook::FxExposureGain()));
    }
    if(!bFrameRecording)
    {
        // Stills runs report too: the clock then starts with the first scripted shot.
        if(!bFighting&&(StillsDir.IsEmpty()||Phase<EPhase::Hold))return;
        FrameWarmup+=Wall/1000.f;
        if(FrameWarmup<FrameWarmupSeconds)return;
        bFrameRecording=true;return;
    }
    // Pause-menu frames and the tool's own cuts and screenshot readbacks are not fight frames.
    if(GetWorld()->IsPaused()){++SkippedPaused;return;}
    if(FScreenshotRequest::IsScreenshotRequested())SkipFrames=FMath::Max(SkipFrames,3);
    if(SkipFrames>0){--SkipFrames;++SkippedTool;return;}
    FrameMs.Add(Wall);RecordedSeconds+=Wall/1000.f;
    if(VeyrLook::LastExposure()>0.f)ExposureFrames.Add(VeyrLook::LastExposure());
    GameMs.Add(FPlatformTime::ToMilliseconds(GGameThreadTime));
    RenderMs.Add(FPlatformTime::ToMilliseconds(GRenderThreadTime));
    GpuMs.Add(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0)));
    if(RecordedSeconds>=FrameReportSeconds)WriteFrameReport();
}

void AVeyrLightCheck::WriteFrameReport(bool bPartial)
{
    bFrameDone=true;
    auto Root=LookFields(GetWorld());
    Root->SetStringField(TEXT("mode"),StillsDir.IsEmpty()?TEXT("fight"):TEXT("stills"));
    Root->SetBoolField(TEXT("partial"),bPartial);
    Root->SetNumberField(TEXT("seconds"),RecordedSeconds);Root->SetNumberField(TEXT("frames"),FrameMs.Num());
    Root->SetNumberField(TEXT("skippedPausedFrames"),SkippedPaused);Root->SetNumberField(TEXT("skippedToolFrames"),SkippedTool);
    Root->SetObjectField(TEXT("frameMs"),Stats(FrameMs));Root->SetObjectField(TEXT("gameThreadMs"),Stats(GameMs));
    Root->SetObjectField(TEXT("renderThreadMs"),Stats(RenderMs));Root->SetObjectField(TEXT("gpuMs"),Stats(GpuMs));
    int32 Over=0;for(float V:FrameMs)Over+=V>17.5f;
    Root->SetNumberField(TEXT("framesOver17_5ms"),Over);
    Root->SetNumberField(TEXT("meanFps"),Mean(FrameMs)>0.f?1000.f/Mean(FrameMs):0.f);
    // Exposure over the recorded frames, and its range in stops (build 16 manual exposure = 0.833).
    Root->SetObjectField(TEXT("exposure"),Stats(ExposureFrames));
    {
        float Lo=0.f,Hi=0.f;
        if(ExposureFrames.Num()){Lo=Percentile(ExposureFrames,.05f);Hi=Percentile(ExposureFrames,.95f);}
        Root->SetNumberField(TEXT("exposureStopsP5toP95"),Lo>0.f?FMath::Log2(Hi/Lo):0.f);
        Root->SetNumberField(TEXT("fxExposureLock"),VeyrLook::FxExposureLock());
    }
    Root->SetStringField(TEXT("exposureTrace"),TEXT("exposure-trace.csv"));
    {
        FString Csv=TEXT("seconds,phase,exposure,sceneLuminance,fxGain\n");
        for(const FString& Line:ExposureTrace)Csv+=Line+TEXT("\n");
        FFileHelper::SaveStringToFile(Csv,*FPaths::Combine(FrameDir,TEXT("exposure-trace.csv")));
    }
    Root->SetStringField(TEXT("note"),StillsDir.IsEmpty()
        ?TEXT("wall-clock frame interval under the 60 fps cap; GPU ms is the headroom signal")
        :TEXT("stills mode: scripted poses, not a fight; frames around cuts and screenshots are skipped"));
    SaveJson(Root,FPaths::Combine(FrameDir,TEXT("frame-report.json")));
    UE_LOG(LogTemp,Display,TEXT("VEYR_FRAME_REPORT frames=%d seconds=%.1f partial=%d meanMs=%.2f p95Ms=%.2f gpuMeanMs=%.2f gpuP95Ms=%.2f legacy=%d tier=%d"),
        FrameMs.Num(),RecordedSeconds,bPartial,Mean(FrameMs),Percentile(FrameMs,.95f),Mean(GpuMs),Percentile(GpuMs,.95f),VeyrLook::IsLegacy(),VeyrLook::RenderTier());
    if(!bPartial)MaybeQuit();
}

void AVeyrLightCheck::EndPlay(const EEndPlayReason::Type Reason)
{
    // A restart (OpenLevel) or quit before 60 s still leaves the frames measured so far.
    if(!FrameDir.IsEmpty()&&bFrameRecording&&!bFrameDone&&FrameMs.Num()>0)WriteFrameReport(true);
    if(!StillsDir.IsEmpty()&&Phase!=EPhase::Done&&ShotRecords.Num()>0)
    {
        auto Root=LookFields(GetWorld());Root->SetArrayField(TEXT("shots"),ShotRecords);Root->SetBoolField(TEXT("partial"),true);
        SaveJson(Root,FPaths::Combine(StillsDir,TEXT("lightcheck.json")));
    }
    Super::EndPlay(Reason);
}

int32 AVeyrLightCheck::OutstandingBuilds(FString& What) const
{
    // Uncooked runs build distance fields, Lumen cards and shaders after load; cooked ones report 0.
    const int32 Fields=GDistanceFieldAsyncQueue?GDistanceFieldAsyncQueue->GetNumOutstandingTasks():0;
    const int32 Cards=GCardRepresentationAsyncQueue?GCardRepresentationAsyncQueue->GetNumOutstandingTasks():0;
    const int32 Shaders=GShaderCompilingManager?GShaderCompilingManager->GetNumRemainingJobs():0;
    What=FString::Printf(TEXT("distanceFields=%d cards=%d shaders=%d"),Fields,Cards,Shaders);
    return Fields+Cards+Shaders;
}

void AVeyrLightCheck::PlaceActors()
{
    const FShot& Shot=Shots[ShotIndex];
    if(Dragon->State==EVeyrDragonState::Idle&&!Dragon->IsDead())
        Dragon->SetActorLocationAndRotation(DragonHome,DragonHomeRotation,false,nullptr,ETeleportType::TeleportPhysics);
    const float KnightZ=Knight->GetActorLocation().Z;
    FVector Position(-1600.f,0.f,KnightZ);FRotator Facing(0,0,0);
    if(Shot.Name.StartsWith(TEXT("06")))
    {
        // In front of the near foreleg, facing it, at sword reach.
        const FVector Leg=Dragon->GetLegLocation(0);
        const FVector Out=(Leg-Dragon->GetActorLocation()).GetSafeNormal2D();
        Position=Leg+(Out.IsNearlyZero()?FVector(-1,0,0):Out)*280.f;Position.Z=KnightZ;
        Facing=(Leg-Position).GetSafeNormal2D().Rotation();
    }
    else if(Shot.Name.StartsWith(TEXT("10")))
    {
        // Away from every brazier and floor pool: the readability test.
        Position=FVector(-2600.f,-1800.f,KnightZ);
        Facing=(Dragon->GetActorLocation()-Position).GetSafeNormal2D().Rotation();
    }
    Knight->SetActorLocationAndRotation(Position,Facing,false,nullptr,ETeleportType::TeleportPhysics);
    if(Knight->GetCharacterMovement())Knight->GetCharacterMovement()->StopMovementImmediately();
}

void AVeyrLightCheck::PlaceCamera()
{
    if(!Camera||!Knight||!Dragon)return;
    const FString& Name=Shots[ShotIndex].Name;
    const FVector K=Knight->GetActorLocation(),Head=Dragon->GetHeadLocation(),D=Dragon->GetActorLocation();
    const FVector KF=Knight->GetActorForwardVector(),KR=Knight->GetActorRightVector();
    FVector At=K,Look=Head;float Fov=72.f;
    if(Name.StartsWith(TEXT("01"))){At=FVector(-4200,-2600,900);Look=FVector(600,300,500);Fov=70.f;}
    else if(Name.StartsWith(TEXT("02"))){At=K+KF*260.f-KR*140.f+FVector(0,0,40);Look=K+FVector(0,0,45);Fov=45.f;}
    else if(Name.StartsWith(TEXT("03"))||Name.StartsWith(TEXT("10"))){At=K-KF*560.f+KR*60.f+FVector(0,0,190);Look=Head;Fov=72.f;}
    else if(Name.StartsWith(TEXT("04")))
    {
        FVector Under=FVector::ZeroVector;for(int32 I=0;I<4;++I)Under+=Dragon->GetLegLocation(I)*.25f;
        At=FVector(Under.X,Under.Y,K.Z-25.f);Look=Head;Fov=82.f;
    }
    else if(Name.StartsWith(TEXT("05"))||Name.StartsWith(TEXT("07")))
    {
        const FVector Mid=(K+D)*.5f;const FVector Across=FVector::CrossProduct((D-K).GetSafeNormal2D(),FVector::UpVector);
        At=Mid+Across*(1500.f+400.f*Dragon->BodyScale)+FVector(0,0,420);Look=Mid+FVector(0,0,260);Fov=70.f;
    }
    else if(Name.StartsWith(TEXT("06"))){At=K-KF*380.f+KR*240.f+FVector(0,0,150);Look=K+KF*180.f+FVector(0,0,90);Fov=68.f;}
    else if(Name.StartsWith(TEXT("08")))
    {
        const FVector DF=Dragon->GetActorForwardVector(),DR=Dragon->GetActorRightVector();
        At=Head+DF*650.f+DR*520.f;At.Z=K.Z+90.f;Look=Head;Fov=66.f;
    }
    else if(Name.StartsWith(TEXT("09"))){At=K-KF*300.f+FVector(0,0,110);Look=Head;Fov=80.f;}
    Camera->GetCameraComponent()->SetFieldOfView(Fov);
    Camera->SetActorLocationAndRotation(At,(Look-At).Rotation());
}

bool AVeyrLightCheck::BeginShot()
{
    if(++ShotIndex>=Shots.Num())
    {
        FParse::Value(FCommandLine::Get(),TEXT("VeyrLightCheckBreathSeconds="),BreathSeconds);
        if(BreathSeconds>0.f)BeginBreath();else FinishStills();
        return false;
    }
    const FShot& Shot=Shots[ShotIndex];
    PhaseClock=0.f;bStrikeIssued=false;bSegmentStarted=false;bPreRollDone=Shot.PreRollSeconds<=0.f;SkipFrames=FMath::Max(SkipFrames,10);
    PlaceActors();
    if(!Shot.Segment.IsNone())
    {
        FString Error;
        bSegmentStarted=Dragon->StartShowcaseSegment(Shot.Segment,Error);
        if(!bSegmentStarted)
        {
            // StartShowcaseSegment records the segment before validating it: clear it, or every
            // later segment fails with "requires an idle rehearsal actor".
            UE_LOG(LogTemp,Warning,TEXT("VEYR_LIGHTCHECK_SEGMENT_FAILED %s %s"),*Shot.Name,*Error);
            Dragon->RestAfterShowcaseSegment();
        }
    }
    PlaceCamera();
    VeyrLook::NotifyCameraCut(GetWorld());
    UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_SHOT_BEGIN %s segment=%s"),*Shot.Name,*Shot.Segment.ToString());
    return true;
}

bool AVeyrLightCheck::ReadyToCapture() const
{
    const FShot& Shot=Shots[ShotIndex];
    const float Elapsed=Dragon->GetStateElapsed();
    if(!bSegmentStarted)return PhaseClock>=Shot.HoldSeconds;
    if(PhaseClock>=Shot.HoldSeconds)return true; // timeout: capture whatever the moment is
    if(Shot.Segment==TEXT("Roar"))return PhaseClock>=1.2f;
    if(Shot.Segment==TEXT("Fire"))return Dragon->State==EVeyrDragonState::Active&&Elapsed>=.6f;
    if(Shot.Segment==TEXT("Claw0"))return Dragon->State==EVeyrDragonState::Active&&Elapsed>=.08f;
    if(Shot.Segment==TEXT("Stagger0"))return Dragon->State==EVeyrDragonState::Exposed&&Elapsed>=.4f;
    if(Shot.Segment==TEXT("Flight"))return Dragon->State==EVeyrDragonState::Active&&Elapsed>=1.f;
    return false;
}

void AVeyrLightCheck::TickStills(float DeltaSeconds)
{
    if(Phase==EPhase::Done||!Knight||!Dragon)return;
    TotalClock+=DeltaSeconds;PhaseClock+=DeltaSeconds;
    Knight->Health=100.f; // stills never end in a death screen
    APlayerController* PC=GetWorld()->GetFirstPlayerController();
    switch(Phase)
    {
    case EPhase::WaitWorld:
        // Wait for the visual dragon to be ready, then take every input away from the brain.
        if(PhaseClock<1.5f||!PC)return;
        {
            FString What;
            if(OutstandingBuilds(What)>0)
            {
                BuildWaitSeconds+=DeltaSeconds;
                if(BuildWaitSeconds<600.f)
                {
                    if(FMath::FloorToInt(BuildWaitSeconds/5.f)!=FMath::FloorToInt((BuildWaitSeconds-DeltaSeconds)/5.f))
                        UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_WAIT_BUILDS %.0fs %s"),BuildWaitSeconds,*What);
                    return;
                }
                UE_LOG(LogTemp,Warning,TEXT("VEYR_LIGHTCHECK_BUILDS_TIMEOUT %s: stills may show partial Lumen"),*What);
            }
            else if(BuildWaitSeconds>0.f)UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_BUILDS_DONE after %.0fs"),BuildWaitSeconds);
        }
        if(!Dragon->BeginShowcase()){if(PhaseClock>15.f){UE_LOG(LogTemp,Error,TEXT("VEYR_LIGHTCHECK_FAILED dragon showcase unavailable"));FinishStills();}return;}
        DragonHome=Dragon->GetActorLocation();DragonHomeRotation=Dragon->GetActorRotation();
        Camera=GetWorld()->SpawnActor<ACameraActor>();
        if(!Camera){FinishStills();return;}
        Camera->GetCameraComponent()->bConstrainAspectRatio=false;
        PC->SetViewTarget(Camera);
        if(PC->MyHUD&&!FParse::Param(FCommandLine::Get(),TEXT("VeyrLightCheckHUD")))PC->MyHUD->bShowHUD=false;
        Phase=EPhase::Setup;PhaseClock=0.f;return;
    case EPhase::Breath:
        TickBreath(DeltaSeconds);return;
    case EPhase::Setup:
        if(!BeginShot())return;
        Phase=EPhase::Hold;return;
    case EPhase::Hold:
        PlaceCamera();
        if(!bPreRollDone)
        {
            // Hold the placed pose until exposure has settled, then give the input; the hold
            // clock (0.38 s for the strike) starts at the input.
            if(PhaseClock<Shots[ShotIndex].PreRollSeconds)return;
            if(Shots[ShotIndex].Name.StartsWith(TEXT("06"))){Knight->SetReplayInput(FVector::ZeroVector,true,false,false,false,false,false);bStrikeIssued=true;}
            bPreRollDone=true;PhaseClock=0.f;return;
        }
        if(!ReadyToCapture())return;
        PendingFile=FPaths::Combine(StillsDir,Shots[ShotIndex].Name+TEXT(".png"));
        FScreenshotRequest::RequestScreenshot(PendingFile,FParse::Param(FCommandLine::Get(),TEXT("VeyrLightCheckHUD")),false);
        {
            auto Row=MakeShared<FJsonObject>();
            Row->SetStringField(TEXT("shot"),Shots[ShotIndex].Name);Row->SetStringField(TEXT("file"),FPaths::GetCleanFilename(PendingFile));
            Row->SetStringField(TEXT("segment"),Shots[ShotIndex].Segment.ToString());Row->SetBoolField(TEXT("segmentStarted"),bSegmentStarted);
            Row->SetNumberField(TEXT("dragonState"),static_cast<int32>(Dragon->State));Row->SetNumberField(TEXT("stateElapsed"),Dragon->GetStateElapsed());
            Row->SetNumberField(TEXT("holdSeconds"),PhaseClock);
            Row->SetNumberField(TEXT("exposure"),VeyrLook::LastExposure());Row->SetNumberField(TEXT("fxGain"),VeyrLook::FxExposureGain());Row->SetNumberField(TEXT("runSeconds"),TotalClock);
            ShotRecords.Add(MakeShared<FJsonValueObject>(Row));
        }
        UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_CAPTURE %s state=%d elapsed=%.2f"),*Shots[ShotIndex].Name,static_cast<int32>(Dragon->State),Dragon->GetStateElapsed());
        Phase=EPhase::Capture;PhaseClock=0.f;return;
    case EPhase::Capture:
        PlaceCamera();
        if(FScreenshotRequest::IsScreenshotRequested()&&PhaseClock<5.f)return;
        if(bStrikeIssued){Knight->ClearReplayInput();bStrikeIssued=false;}
        Phase=EPhase::Settle;PhaseClock=0.f;return;
    case EPhase::Settle:
        // The rehearsal actor only accepts a new segment from idle: let this one finish.
        if(bSegmentStarted&&!Dragon->IsShowcaseSegmentComplete()&&PhaseClock<20.f)return;
        if(bSegmentStarted){Dragon->RestAfterShowcaseSegment();bSegmentStarted=false;PhaseClock=0.f;}
        if(PhaseClock<1.f)return;
        Phase=EPhase::Setup;PhaseClock=0.f;return;
    default:return;
    }
}

void AVeyrLightCheck::BeginBreath()
{
    ShotIndex=4; // 05_fire_breath framing
    Phase=EPhase::Breath;BreathClock=0.f;BreathRest=.5f;BreathLastWall=FPlatformTime::Seconds();bSegmentStarted=false;
    PlaceActors();PlaceCamera();VeyrLook::NotifyCameraCut(GetWorld());
    UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_BREATH_BEGIN seconds=%.0f"),BreathSeconds);
}

void AVeyrLightCheck::TickBreath(float DeltaSeconds)
{
    const double Now=FPlatformTime::Seconds();const float Wall=static_cast<float>((Now-BreathLastWall)*1000.0);BreathLastWall=Now;
    BreathClock+=DeltaSeconds;
    PlaceCamera();
    const bool bBeam=bSegmentStarted&&Dragon->Move==EVeyrDragonMove::Fire&&Dragon->State==EVeyrDragonState::Active;
    if(bBeam&&!FScreenshotRequest::IsScreenshotRequested())
    {
        BreathMs.Add(Wall);BreathGpuMs.Add(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0)));
        if(VeyrLook::LastExposure()>0.f)BreathExposure.Add(VeyrLook::LastExposure());
    }
    if(bSegmentStarted)
    {
        if(!Dragon->IsShowcaseSegmentComplete())return;
        Dragon->RestAfterShowcaseSegment();bSegmentStarted=false;BreathRest=.5f;return;
    }
    if(BreathClock>=BreathSeconds){WriteBreathReport();FinishStills();return;}
    BreathRest-=DeltaSeconds;
    if(BreathRest>0.f||Dragon->State!=EVeyrDragonState::Idle)return;
    PlaceActors();
    FString Error;
    bSegmentStarted=Dragon->StartShowcaseSegment(TEXT("Fire"),Error);
    if(bSegmentStarted)++BreathCount;
    else{UE_LOG(LogTemp,Warning,TEXT("VEYR_LIGHTCHECK_BREATH_FAILED %s"),*Error);Dragon->RestAfterShowcaseSegment();WriteBreathReport();FinishStills();}
}

void AVeyrLightCheck::WriteBreathReport()
{
    auto Root=LookFields(GetWorld());
    Root->SetStringField(TEXT("mode"),TEXT("breath"));Root->SetNumberField(TEXT("breaths"),BreathCount);
    Root->SetNumberField(TEXT("beamFrames"),BreathMs.Num());
    Root->SetObjectField(TEXT("frameMs"),Stats(BreathMs));Root->SetObjectField(TEXT("gpuMs"),Stats(BreathGpuMs));
    Root->SetObjectField(TEXT("exposure"),Stats(BreathExposure));
    int32 Over=0;for(float V:BreathMs)Over+=V>17.5f;
    Root->SetNumberField(TEXT("framesOver17_5ms"),Over);
    Root->SetStringField(TEXT("note"),TEXT("frames while the fire beam is live, shot-05 camera; wall-clock interval under the 60 fps cap"));
    SaveJson(Root,FPaths::Combine(StillsDir,TEXT("breath-report.json")));
    UE_LOG(LogTemp,Display,TEXT("VEYR_BREATH_REPORT breaths=%d frames=%d meanMs=%.2f p95Ms=%.2f gpuP95Ms=%.2f tier=%d"),
        BreathCount,BreathMs.Num(),Mean(BreathMs),Percentile(BreathMs,.95f),Percentile(BreathGpuMs,.95f),VeyrLook::RenderTier());
}

void AVeyrLightCheck::FinishStills()
{
    Phase=EPhase::Done;
    auto Root=LookFields(GetWorld());
    Root->SetArrayField(TEXT("shots"),ShotRecords);Root->SetNumberField(TEXT("runSeconds"),TotalClock);
    Root->SetNumberField(TEXT("waitedForBuildsSeconds"),BuildWaitSeconds);
    Root->SetStringField(TEXT("rebuild"),TEXT("tools/unreal/lightcheck_sheet.py <this dir> [other dirs...]"));
    SaveJson(Root,FPaths::Combine(StillsDir,TEXT("lightcheck.json")));
    UE_LOG(LogTemp,Display,TEXT("VEYR_LIGHTCHECK_DONE shots=%d seconds=%.1f"),ShotRecords.Num(),TotalClock);
    MaybeQuit();
}

void AVeyrLightCheck::MaybeQuit()
{
    const bool bStillsPending=!StillsDir.IsEmpty()&&Phase!=EPhase::Done;
    const bool bFramesPending=!FrameDir.IsEmpty()&&!bFrameDone;
    if(bStillsPending||bFramesPending)return;
    // A stills run owns its process; a frame report quits only when asked (a replay may still be running).
    if(!StillsDir.IsEmpty()||FParse::Param(FCommandLine::Get(),TEXT("VeyrFrameReportQuit")))
        FPlatformMisc::RequestExit(false,TEXT("Veyr lightcheck completed"));
}
