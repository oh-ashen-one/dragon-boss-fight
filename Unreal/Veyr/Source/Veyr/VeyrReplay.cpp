#include "VeyrReplay.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrGameMode.h"
#include "VeyrIdentity.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/GameViewportClient.h"
#include "HAL/IConsoleManager.h"
#include "ImageUtils.h"
#include "Async/Async.h"
#include "Modules/ModuleManager.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Engine/World.h"
#include "UnrealClient.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace
{
    // Test-only evidence survives OpenLevel. No actor pointers or encounter state are retained.
    TSharedPtr<FJsonObject> PendingRestartEvidence;
    FString PendingRestartDirectory;
    double RestartRequestedWallTime=0;
    TArray<TSharedPtr<FJsonValue>> VectorJson(const FVector& V)
    {
        return { MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z) };
    }
    bool Contains(const FVeyrDragonFootprint& F, FVector P, float Margin=0)
    {
        P.Z=0; FVector Origin=F.Origin; Origin.Z=0;
        const FVector D=P-Origin; const double R=D.Size();
        if(F.Shape==EVeyrDangerShape::None)return false;
        if(F.Shape==EVeyrDangerShape::Capsule)
        {
            FVector End=F.End; End.Z=0;
            return FMath::PointDistToSegment(P,Origin,End)<=F.OuterRadius+Margin;
        }
        if(R>F.OuterRadius+Margin||R<FMath::Max(0.f,F.InnerRadius-Margin))return false;
        if(F.Shape==EVeyrDangerShape::Circle||R<1)return true;
        const float ExtraAngle=FMath::RadiansToDegrees(FMath::Atan2(Margin,FMath::Max(1.f,static_cast<float>(R))));
        return FVector::DotProduct(D.GetSafeNormal(),F.Forward.GetSafeNormal2D())>=FMath::Cos(FMath::DegreesToRadians(FMath::Min(180.f,F.HalfAngleDegrees+ExtraAngle)));
    }
    bool Contains(const TArray<FVeyrDragonFootprint>& Shapes,const FVector& P,float Margin=0)
    {
        for(const auto& F:Shapes)if(Contains(F,P,Margin))return true;
        return false;
    }
    TArray<TSharedPtr<FJsonValue>> FootprintsJson(const TArray<FVeyrDragonFootprint>& Shapes)
    {
        TArray<TSharedPtr<FJsonValue>> Values;
        for(const auto& F:Shapes)
        {
            auto O=MakeShared<FJsonObject>();O->SetNumberField(TEXT("shape"),static_cast<int32>(F.Shape));
            O->SetArrayField(TEXT("origin"),VectorJson(F.Origin));O->SetArrayField(TEXT("end"),VectorJson(F.End));
            O->SetArrayField(TEXT("forward"),VectorJson(F.Forward));O->SetNumberField(TEXT("innerRadius"),F.InnerRadius);
            O->SetNumberField(TEXT("outerRadius"),F.OuterRadius);O->SetNumberField(TEXT("halfAngleDegrees"),F.HalfAngleDegrees);
            O->SetBoolField(TEXT("damaging"),F.bDamaging);Values.Add(MakeShared<FJsonValueObject>(O));
        }
        return Values;
    }
}

AVeyrReplay::AVeyrReplay()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PostPhysics;
}

bool AVeyrReplay::GetPendingRestartRequest(FString& OutMode,FString& OutEvidenceDirectory)
{
    if(!PendingRestartEvidence.IsValid()||PendingRestartDirectory.IsEmpty())return false;
    OutMode=PendingRestartEvidence->GetStringField(TEXT("mode"));
    OutEvidenceDirectory=PendingRestartDirectory;
    return true;
}

bool AVeyrReplay::Initialize(const FString& Mode, const FString& EvidenceDirectory)
{
    if(bInitialized)return false;
    ReplayMode=Mode.ToLower();
    bLegIsolation=ReplayMode==TEXT("leg0")||ReplayMode==TEXT("leg1")||ReplayMode==TEXT("leg2")||ReplayMode==TEXT("leg3");
    if((ReplayMode!=TEXT("core")&&ReplayMode!=TEXT("death")&&ReplayMode!=TEXT("victory")&&ReplayMode!=TEXT("controls")&&ReplayMode!=TEXT("avoidance")&&ReplayMode!=TEXT("healing")&&ReplayMode!=TEXT("guard")&&!bLegIsolation)||EvidenceDirectory.IsEmpty()||FPaths::IsRelative(EvidenceDirectory))
    {
        UE_LOG(LogTemp,Error,TEXT("VEYR_REPLAY_REJECTED requires core|death|victory|leg0|leg1|leg2|leg3|controls|avoidance|healing|guard and absolute evidence directory")); return false;
    }
    AVeyrGameMode* ModeActor=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!ModeActor||!IsValid(ModeActor->Knight)||!IsValid(ModeActor->Dragon))
    {
        UE_LOG(LogTemp,Error,TEXT("VEYR_REPLAY_REJECTED initialize only after knight and dragon are ready")); return false;
    }
    Knight=ModeActor->Knight; Dragon=ModeActor->Dragon;
    if(bLegIsolation)TargetLeg=FCString::Atoi(*ReplayMode.Right(1));
    ControlOrigin=Knight->GetFootLocation();
    const bool bResume=PendingRestartEvidence.IsValid()&&PendingRestartEvidence->GetStringField(TEXT("mode"))==ReplayMode;
    if(bResume)
    {
        const TSharedPtr<FJsonObject> Saved=PendingRestartEvidence;
        RunDirectory=PendingRestartDirectory;
        Elapsed=Saved->GetNumberField(TEXT("durationSeconds"));TerminalSeconds=Saved->GetNumberField(TEXT("terminalSeconds"));
        FrameCount=Saved->GetNumberField(TEXT("frameCount"));MaximumFrameSeconds=Saved->GetNumberField(TEXT("maximumFrameSeconds"));
        Samples=Saved->GetArrayField(TEXT("samples"));Events=Saved->GetArrayField(TEXT("events"));
        double SavedFailures=0;if(Saved->TryGetNumberField(TEXT("warningContainmentFailures"),SavedFailures))ObservedWarningContainmentFailures=SavedFailures;
        bLightLegContact=Saved->GetBoolField(TEXT("lightLegContact"));bHeavyLegContact=Saved->GetBoolField(TEXT("heavyLegContact"));
        bSawRise=Saved->GetBoolField(TEXT("riseObserved"));bRiseCompleted=Saved->GetBoolField(TEXT("riseCompleted"));
        for(const TSharedPtr<FJsonValue>& V:Saved->GetArrayField(TEXT("wallFrameIntervalsSeconds")))WallFrameIntervals.Add(V->AsNumber());
        for(const TSharedPtr<FJsonValue>& V:Saved->GetArrayField(TEXT("screenshots")))
        {
            const TSharedPtr<FJsonObject> F=V->AsObject();CaptureNames.Add(F->GetStringField(TEXT("event")));
            CaptureFiles.Add(FPaths::Combine(RunDirectory,F->GetStringField(TEXT("file"))));
            CaptureTimes.Add(F->GetNumberField(TEXT("requestedAtSeconds")));CaptureTriggerTimes.Add(F->GetNumberField(TEXT("triggeredAtSeconds")));
            CaptureStates.Add(MakeShared<FJsonValueObject>(F->GetObjectField(TEXT("stateAtRequest"))));
        }
        ScreenshotIndex=CaptureFiles.Num();
        RestartLoadSeconds=FPlatformTime::Seconds()-RestartRequestedWallTime;
        const TSharedPtr<FJsonObject>* SavedVideo=nullptr;
        if(Saved->TryGetObjectField(TEXT("nativeVideo"),SavedVideo))
        {
            VideoFrameIndex=(*SavedVideo)->GetNumberField(TEXT("requestedFrames"));
            VideoFramesSaved=(*SavedVideo)->GetNumberField(TEXT("savedFrames"));
            VideoSkippedSlots=(*SavedVideo)->GetNumberField(TEXT("skippedSlots"));
            VideoFailedFrames=(*SavedVideo)->GetNumberField(TEXT("failedFrames"));
            VideoWorldIndex=(*SavedVideo)->GetNumberField(TEXT("worldIndex"))+1;
            VideoWriteSeconds=(*SavedVideo)->GetNumberField(TEXT("pngWriteSeconds"));
            (*SavedVideo)->TryGetNumberField(TEXT("pixelCopySeconds"),VideoPixelCopySeconds);
            VideoStartedWallTime=FPlatformTime::Seconds()-(*SavedVideo)->GetNumberField(TEXT("elapsedWallSeconds"))-RestartLoadSeconds;
            bVideoStopped=(*SavedVideo)->GetBoolField(TEXT("stopped"));
            VideoStopReason=(*SavedVideo)->GetStringField(TEXT("stopReason"));
        }
        PendingRestartEvidence.Reset();PendingRestartDirectory.Reset();
        bRestartVerification=true;RestartOrigin=Knight->GetFootLocation();
        bFreshResourcesVerified=FMath::IsNearlyEqual(Knight->Health,100.f)&&FMath::IsNearlyEqual(Knight->Stamina,100.f)&&Knight->HealingCharges==4&&
            FMath::IsNearlyEqual(Dragon->Health,Dragon->MaxHealth)&&!Knight->IsDead()&&!Dragon->IsDead()&&Knight->LightAttacks==0;
    }
    else
    {
        const FString RunName=FString::Printf(TEXT("unreal-%s-%s-%s"),*ReplayMode,*FDateTime::UtcNow().ToString(TEXT("%Y%m%dT%H%M%SZ")),*FGuid::NewGuid().ToString(EGuidFormats::Digits).Left(8));
        RunDirectory=FPaths::Combine(EvidenceDirectory,RunName);
        if(!IFileManager::Get().MakeDirectory(*RunDirectory,true))
        {
            UE_LOG(LogTemp,Error,TEXT("VEYR_REPLAY_REJECTED cannot create evidence directory %s"),*RunDirectory); return false;
        }
    }
    bInitialized=true; bQuit=FParse::Param(FCommandLine::Get(),TEXT("VeyrReplayQuit"));
    LastWallFrameTime=FPlatformTime::Seconds();
    StartedWallTime=LastWallFrameTime;
    DurationLimit=ReplayMode==TEXT("victory")?480.f:ReplayMode==TEXT("death")?120.f:ReplayMode==TEXT("avoidance")?240.f:bLegIsolation?120.f:180.f;
    InitializeVideo();
    if(!Knight->bLockedOn)Knight->ToggleLockOn();
    Event(bResume?TEXT("restart_world_loaded"):TEXT("start")); SaveEvidence(false);
    if(bResume&&!bFreshResourcesVerified)Finish(false,TEXT("restart resource reset failed"));
    UE_LOG(LogTemp,Display,TEXT("VEYR_REPLAY_STARTED mode=%s evidence=%s limit=%.1f"),*ReplayMode,*RunDirectory,DurationLimit);
    return true;
}

TSharedPtr<FJsonObject> AVeyrReplay::Snapshot() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("seconds"),Elapsed);
    O->SetStringField(TEXT("replayStage"),bRestartVerification?TEXT("restart_verification"):bAwaitingReload?TEXT("awaiting_reload"):bTerminalSettling?TEXT("terminal_settling"):TEXT("combat"));
    if(!IsValid(Knight)||!IsValid(Dragon))return O;
    O->SetNumberField(TEXT("playerHealth"),Knight->Health); O->SetNumberField(TEXT("stamina"),Knight->Stamina);
    O->SetNumberField(TEXT("healsRemaining"),Knight->HealingCharges); O->SetNumberField(TEXT("bossHealth"),Dragon->Health);
    O->SetStringField(TEXT("action"),StaticEnum<EVeyrKnightAction>()->GetNameStringByValue(static_cast<int64>(Knight->Action)));
    O->SetNumberField(TEXT("actionElapsed"),Knight->GetActionElapsed()); O->SetNumberField(TEXT("actionDuration"),Knight->GetActionDuration());
    O->SetStringField(TEXT("dragonState"),StaticEnum<EVeyrDragonState>()->GetNameStringByValue(static_cast<int64>(Dragon->State)));
    O->SetStringField(TEXT("dragonMove"),StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(Dragon->Move)));
    O->SetNumberField(TEXT("stateElapsed"),Dragon->GetStateElapsed()); O->SetNumberField(TEXT("stateDuration"),Dragon->GetStateDuration());
    O->SetArrayField(TEXT("playerFeet"),VectorJson(Knight->GetFootLocation())); O->SetArrayField(TEXT("playerForward"),VectorJson(Knight->GetActorForwardVector()));
    O->SetArrayField(TEXT("bossPosition"),VectorJson(Dragon->GetActorLocation())); O->SetArrayField(TEXT("headPosition"),VectorJson(Dragon->GetHeadLocation()));
    O->SetBoolField(TEXT("grounded"),Knight->IsGrounded()); O->SetBoolField(TEXT("invulnerable"),Knight->IsRollingInvulnerable());
    O->SetBoolField(TEXT("insideWarning"),Dragon->IsPointInsideWarning(Knight->GetFootLocation()));
    O->SetArrayField(TEXT("warningFootprints"),FootprintsJson(Dragon->GetWarningFootprints()));
    O->SetArrayField(TEXT("activeFootprints"),FootprintsJson(Dragon->GetActiveFootprints()));
    O->SetNumberField(TEXT("warningContainmentFailures"),Dragon->WarningContainmentFailures);
    O->SetStringField(TEXT("importedCombatDiagnostic"),Dragon->ImportedCombatDiagnostic);
    O->SetBoolField(TEXT("importedCombatPoseValid"),Dragon->HasValidImportedCombatPose());
    const FVeyrDragonFlameBeam Beam=Dragon->GetActiveFlameBeam();
    O->SetArrayField(TEXT("mouth"),VectorJson(Dragon->GetMouthLocation()));
    O->SetArrayField(TEXT("flameDirection"),VectorJson(Beam.Direction));
    O->SetBoolField(TEXT("flameDamaging"),Beam.bDamaging);
    O->SetBoolField(TEXT("insideActiveDanger"),Dragon->IsPointInsideActiveDanger(Knight->GetFootLocation()));
    O->SetNumberField(TEXT("lightAttacks"),Knight->LightAttacks); O->SetNumberField(TEXT("heavyAttacks"),Knight->HeavyAttacks);
    O->SetNumberField(TEXT("rolls"),Knight->Rolls); O->SetNumberField(TEXT("dodgedHits"),Knight->DodgedHits);
    O->SetNumberField(TEXT("hitsTaken"),Knight->HitsTaken); O->SetNumberField(TEXT("guardedHits"),Knight->GuardedHits);
    O->SetNumberField(TEXT("guardBreaks"),Knight->GuardBreaks); O->SetNumberField(TEXT("healsCompleted"),Knight->SuccessfulHeals);
    O->SetNumberField(TEXT("jumpsConfirmed"),Knight->SuccessfulJumps); O->SetNumberField(TEXT("swordContacts"),Dragon->GetSwordContactCount());
    O->SetNumberField(TEXT("lastHitRegion"),Dragon->GetLastHitRegion()); O->SetNumberField(TEXT("lastSwordDamage"),Dragon->GetLastSwordDamage());
    O->SetNumberField(TEXT("collapses"),Dragon->GetCollapseCount()); O->SetNumberField(TEXT("headBonusHits"),Dragon->GetHeadBonusHitCount());
    O->SetNumberField(TEXT("headWindow"),Dragon->GetHeadWindowRemaining());
    O->SetNumberField(TEXT("targetLeg"),TargetLeg);
    O->SetNumberField(TEXT("struckLeg"),Dragon->GetStruckLegIndex());
    O->SetBoolField(TEXT("lockedOn"),Knight->bLockedOn);
    O->SetNumberField(TEXT("controlStage"),ControlStage);
    O->SetNumberField(TEXT("boundaryStage"),BoundaryStage);
    O->SetNumberField(TEXT("verifiedHealCharges"),VerifiedHealCharges);
    O->SetBoolField(TEXT("controlJumpAirborneObserved"),bControlJumpAirborne);
    O->SetBoolField(TEXT("controlJumpLandingObserved"),bControlJumpLanded);
    O->SetNumberField(TEXT("controlJumpMaximumRiseCm"),ControlJumpMaximumRise);
    O->SetNumberField(TEXT("desiredAvoidanceMove"),DesiredAvoidanceMove);
    O->SetBoolField(TEXT("avoidanceGoalInReachableRegion"),bAvoidanceGoalAvailable);
    O->SetArrayField(TEXT("avoidanceGoal"),VectorJson(AvoidanceGoal));
    TArray<TSharedPtr<FJsonValue>> MoveCoverage;
    for(int32 I=0;I<6;++I)
    {
        const EVeyrDragonMove Move=static_cast<EVeyrDragonMove>(I);
        TSharedPtr<FJsonObject> Coverage=MakeShared<FJsonObject>();
        Coverage->SetStringField(TEXT("move"),StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(I));
        Coverage->SetNumberField(TEXT("started"),Dragon->GetAttackCount(Move));
        Coverage->SetNumberField(TEXT("completed"),Dragon->GetCompletedAttackCount(Move));
        Coverage->SetNumberField(TEXT("threatenedWindupAvoidedThroughRecovery"),AvoidedMoves[I]);
        MoveCoverage.Add(MakeShared<FJsonValueObject>(Coverage));
    }
    O->SetArrayField(TEXT("moveCoverage"),MoveCoverage);
    if(Knight->CombatCamera&&Knight->CameraBoom)
    {
        const FVector Camera=Knight->CombatCamera->GetComponentLocation();
        const FVector Pivot=Knight->CameraBoom->GetComponentLocation();
        TSharedPtr<FJsonObject> Metrics=MakeShared<FJsonObject>();
        Metrics->SetArrayField(TEXT("position"),VectorJson(Camera));
        Metrics->SetNumberField(TEXT("pitch"),Knight->CombatCamera->GetComponentRotation().Pitch);
        Metrics->SetNumberField(TEXT("yaw"),Knight->CombatCamera->GetComponentRotation().Yaw);
        Metrics->SetNumberField(TEXT("requestedArmCm"),Knight->CameraBoom->TargetArmLength);
        Metrics->SetNumberField(TEXT("pivotDistanceCm"),FVector::Distance(Pivot,Camera));
        Metrics->SetBoolField(TEXT("collisionFixApplied"),Knight->CameraBoom->IsCollisionFixApplied());
        Metrics->SetNumberField(TEXT("hiddenProxyParts"),Knight->CameraHiddenProxyParts);
        Metrics->SetNumberField(TEXT("severelyCompressedSeconds"),Knight->CameraSeverelyCompressedSeconds);
        FHitResult Hit;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(VeyrReplayCamera),false,Knight);
        const bool bOccluded=GetWorld()->LineTraceSingleByChannel(Hit,Camera,Knight->GetActorLocation(),ECC_Camera,Query);
        Metrics->SetBoolField(TEXT("lineToPlayerCameraChannelBlocked"),bOccluded);
        Metrics->SetBoolField(TEXT("blockerIsDragon"),bOccluded&&Hit.GetActor()==Dragon);
        FVector2D Screen;
        if(const APlayerController* PC=Cast<APlayerController>(Knight->GetController()))
        {
            int32 Width=0,Height=0;PC->GetViewportSize(Width,Height);
            const bool bProjected=PC->ProjectWorldLocationToScreen(Knight->GetActorLocation(),Screen);
            Metrics->SetBoolField(TEXT("playerCenterWithinViewport"),bProjected&&Width>0&&Height>0&&Screen.X>=0&&Screen.Y>=0&&Screen.X<Width&&Screen.Y<Height);
        }
        Metrics->SetStringField(TEXT("scope"),TEXT("geometric diagnostics only; visual readability requires rendered review"));
        O->SetObjectField(TEXT("camera"),Metrics);
    }
    TArray<TSharedPtr<FJsonValue>> Staggers; for(int32 I=0;I<4;++I)Staggers.Add(MakeShared<FJsonValueNumber>(Dragon->GetLegStagger(I)));
    O->SetArrayField(TEXT("legStagger"),Staggers);
    return O;
}

void AVeyrReplay::Event(const FString& Name, bool bScreenshot)
{
    TSharedPtr<FJsonObject> O=Snapshot(); O->SetStringField(TEXT("event"),Name); Events.Add(MakeShared<FJsonValueObject>(O));
    // Coalesce pending requests rather than giving a later frame a stale event label.
    // Every event remains in JSON; each screenshot also carries its own sampled state.
    if(bScreenshot){CaptureQueue.Reset();CaptureQueue.Add(Name);PendingCaptureTriggerTime=Elapsed;}
    UE_LOG(LogTemp,Display,TEXT("VEYR_REPLAY_EVENT seconds=%.3f event=%s"),Elapsed,*Name);
}

void AVeyrReplay::Observe()
{
    ObservedWarningContainmentFailures=FMath::Max(ObservedWarningContainmentFailures,Dragon->WarningContainmentFailures);
    ObserveScenarios();
    const int32 State=static_cast<int32>(Dragon->State), Action=static_cast<int32>(Knight->Action);
    if(State!=PreviousDragonState)
    {
        if(Dragon->State==EVeyrDragonState::Rise)bSawRise=true;
        if(bSawRise&&PreviousDragonState==static_cast<int32>(EVeyrDragonState::Rise)&&Dragon->State==EVeyrDragonState::Idle)bRiseCompleted=true;
        Event(TEXT("dragon_")+StaticEnum<EVeyrDragonState>()->GetNameStringByValue(State)); PreviousDragonState=State;
    }
    if(Action!=PreviousKnightAction)
    {
        Event(TEXT("player_")+StaticEnum<EVeyrKnightAction>()->GetNameStringByValue(Action),Knight->Action!=EVeyrKnightAction::Ready); PreviousKnightAction=Action;
    }
    if(Dragon->GetSwordContactCount()!=PreviousContacts)
    {
        if(Dragon->GetLastHitRegion()<4)
        {
            bLightLegContact|=FMath::IsNearlyEqual(Dragon->GetLastSwordDamage(),28.f);
            bHeavyLegContact|=FMath::IsNearlyEqual(Dragon->GetLastSwordDamage(),62.f);
        }
        Event(Dragon->GetLastHitRegion()==4?TEXT("head_contact"):TEXT("leg_contact")); PreviousContacts=Dragon->GetSwordContactCount();
    }
    if(Knight->DodgedHits!=PreviousDodges){Event(TEXT("dodge_contact"));PreviousDodges=Knight->DodgedHits;}
    if(Knight->HitsTaken!=PreviousDamage){Event(TEXT("damage_received"));PreviousDamage=Knight->HitsTaken;}
    if(Knight->SuccessfulHeals!=PreviousHeals){Event(TEXT("heal_completed"));PreviousHeals=Knight->SuccessfulHeals;}
    if(Knight->SuccessfulJumps!=PreviousJumps){Event(TEXT("jump_confirmed"));PreviousJumps=Knight->SuccessfulJumps;}
}

bool AVeyrReplay::AllMovesAvoided() const
{
    for(int32 Count:AvoidedMoves)if(Count==0)return false;
    return true;
}

void AVeyrReplay::ObserveScenarios()
{
    if(bLegIsolation)
    {
        for(int32 I=0;I<4;++I)
            if(I!=TargetLeg&&Dragon->GetLegStagger(I)>.001f)bIsolationViolated=true;
        if(Dragon->GetSwordContactCount()!=PreviousContacts&&Dragon->GetLastHitRegion()!=TargetLeg)bIsolationViolated=true;
        bIsolatedStagger|=Dragon->GetLegStagger(TargetLeg)>0;
        if(Dragon->State==EVeyrDragonState::Buckle)
        {
            bCorrectLegBuckle|=Dragon->GetStruckLegIndex()==TargetLeg;
            bIsolationViolated|=Dragon->GetStruckLegIndex()!=TargetLeg;
        }
    }
    if(Dragon->State==EVeyrDragonState::Windup&&PreviousDragonState!=static_cast<int32>(EVeyrDragonState::Windup))
    {
        ObservedAttack=static_cast<int32>(Dragon->Move);ObservedAttackHits=Knight->HitsTaken;bAvoidanceThreatObserved=false;
    }
    if(Dragon->State==EVeyrDragonState::Windup&&Dragon->IsPointInsideWarning(Knight->GetFootLocation()))bAvoidanceThreatObserved=true;
    if(PreviousDragonState==static_cast<int32>(EVeyrDragonState::Recovery)&&Dragon->State==EVeyrDragonState::Idle&&ObservedAttack>=0)
    {
        if(bAvoidanceThreatObserved&&Knight->HitsTaken==ObservedAttackHits)
        {
            ++AvoidedMoves[ObservedAttack];
            Event(TEXT("avoidance_verified_")+StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(ObservedAttack));
        }
        ObservedAttack=-1;
    }
}

bool AVeyrReplay::DriveBoundaryInputs()
{
    if(ReplayMode!=TEXT("healing")&&ReplayMode!=TEXT("guard"))return false;
    const FVector Feet=Knight->GetFootLocation();
    const bool bAvailable=Knight->Action==EVeyrKnightAction::Ready||Knight->Action==EVeyrKnightAction::Guard;
    const float Remaining=Dragon->GetStateDuration()-Dragon->GetStateElapsed();
    const bool bSafeRecovery=Dragon->State==EVeyrDragonState::Recovery&&Remaining>1.35f;
    FVector Movement=FVector::ZeroVector;
    bool bHeal=false,bGuard=false;
    auto Next=[&](int32 Stage,const TCHAR* Name)
    {
        BoundaryStage=Stage;BoundaryStageStarted=Elapsed;Event(Name);
    };
    // Approach a natural bite region without moving actors or forcing attacks.
    // A flight/turn can relocate the goal; only seek positions inside the clear
    // arena center, falling back inward to allow normal boss repositioning.
    FVector Goal=FVector::ZeroVector;
    for(float Distance:{850.f,700.f,550.f})
    {
        const FVector Candidate=Dragon->GetActorTransform().TransformPosition(FVector(Distance,0,0));
        if(Candidate.Size2D()<2950.f){Goal=Candidate;break;}
    }
    const float DistanceToGoal=FVector::Dist2D(Feet,Goal);
    if(DistanceToGoal>40.f)Movement=(Goal-Feet).GetSafeNormal2D()*FMath::Clamp(DistanceToGoal/140.f,.2f,1.f);

    if(ReplayMode==TEXT("healing"))
    {
        if(Knight->Health>100.01f){Finish(false,TEXT("healing exceeded 100 HP cap"));return true;}
        if(BoundaryStage==0&&Knight->Health<99.99f&&bAvailable&&Knight->IsGrounded()&&bSafeRecovery)
        {
            TrialHealth=Knight->Health;TrialCharges=Knight->HealingCharges;
            TrialHeals=Knight->SuccessfulHeals;TrialHits=Knight->HitsTaken;
            Movement=FVector::ZeroVector;bHeal=true;
            Next(TrialCharges>0?1:3,TrialCharges>0?TEXT("healing_charge_requested"):TEXT("injured_empty_flask_requested"));
        }
        else if(BoundaryStage==1)
        {
            Movement=FVector::ZeroVector;
            if(Knight->HitsTaken!=TrialHits){Finish(false,TEXT("healing trial interrupted by damage; cap comparison invalid"));return true;}
            if(Knight->SuccessfulHeals==TrialHeals+1)
            {
                const float Expected=FMath::Min(100.f,TrialHealth+55.f);
                if(Knight->HealingCharges!=TrialCharges-1||!FMath::IsNearlyEqual(Knight->Health,Expected,.02f))
                {Finish(false,TEXT("completed heal did not consume exactly one charge and restore capped 55 HP"));return true;}
                TSharedPtr<FJsonObject> Trial=MakeShared<FJsonObject>();
                Trial->SetStringField(TEXT("kind"),TEXT("completed_heal"));Trial->SetNumberField(TEXT("seconds"),Elapsed);
                Trial->SetNumberField(TEXT("healthBefore"),TrialHealth);Trial->SetNumberField(TEXT("healthAfter"),Knight->Health);
                Trial->SetNumberField(TEXT("expectedHealth"),Expected);Trial->SetNumberField(TEXT("chargesBefore"),TrialCharges);
                Trial->SetNumberField(TEXT("chargesAfter"),Knight->HealingCharges);Trial->SetNumberField(TEXT("actualCompletionCount"),Knight->SuccessfulHeals);
                BoundaryTrials.Add(MakeShared<FJsonValueObject>(Trial));
                bHealCapVerified|=TrialHealth>45.f&&FMath::IsNearlyEqual(Knight->Health,100.f,.02f);
                ++VerifiedHealCharges;Next(2,TEXT("healing_charge_verified"));
            }
            else if(Knight->SuccessfulHeals>TrialHeals+1||Elapsed-BoundaryStageStarted>1.8f)
            {Finish(false,TEXT("requested heal did not complete exactly once within its action duration"));return true;}
        }
        else if(BoundaryStage==2)
        {
            Movement=FVector::ZeroVector;
            if(bAvailable)Next(0,TEXT("healing_seek_next_natural_injury"));
        }
        else if(BoundaryStage==3)
        {
            Movement=FVector::ZeroVector;
            if(Knight->Action==EVeyrKnightAction::Heal||Knight->HealingCharges!=0||Knight->SuccessfulHeals!=TrialHeals||
                Knight->HitsTaken!=TrialHits||!FMath::IsNearlyEqual(Knight->Health,TrialHealth,.02f))
            {Finish(false,TEXT("injured empty-flask trial changed action/resources/health or was contaminated by damage"));return true;}
            if(Elapsed-BoundaryStageStarted>=1.4f)
            {
                bEmptyHealRejected=TrialHealth<100.f&&TrialCharges==0&&TrialHits>0;
                TSharedPtr<FJsonObject> Trial=MakeShared<FJsonObject>();
                Trial->SetStringField(TEXT("kind"),TEXT("injured_empty_flask_rejected"));Trial->SetNumberField(TEXT("injuredHealth"),TrialHealth);
                Trial->SetNumberField(TEXT("observedSeconds"),Elapsed-BoundaryStageStarted);Trial->SetNumberField(TEXT("successfulHealsUnchanged"),Knight->SuccessfulHeals);
                BoundaryTrials.Add(MakeShared<FJsonValueObject>(Trial));
                const bool bPass=VerifiedHealCharges==4&&Knight->SuccessfulHeals==4&&Knight->HealingCharges==0&&bHealCapVerified&&bEmptyHealRejected;
                Finish(bPass,bPass?TEXT("four real heal completions consumed four charges; 100 HP cap and injured empty-flask rejection verified"):
                    TEXT("healing boundary evidence incomplete after empty-flask trial"));return true;
            }
        }
    }
    else
    {
        // Compare actual contact outcomes with the preceding frame's guard,
        // grounded state and facing. Requesting guard alone proves nothing.
        if(bGuardSampleValid&&Knight->HitsTaken>GuardSampleHits)
        {
            const float Lost=GuardSampleHealth-Knight->Health;
            const int32 Blocks=Knight->GuardedHits-GuardSampleBlocks,Breaks=Knight->GuardBreaks-GuardSampleBreaks;
            TSharedPtr<FJsonObject> Trial=MakeShared<FJsonObject>();
            Trial->SetStringField(TEXT("kind"),TEXT("guard_contact"));Trial->SetNumberField(TEXT("seconds"),Elapsed);
            Trial->SetNumberField(TEXT("stage"),BoundaryStage);Trial->SetBoolField(TEXT("guardHeldBefore"),bGuardSampleHeld);
            Trial->SetBoolField(TEXT("groundedBefore"),bGuardSampleGrounded);Trial->SetNumberField(TEXT("facingDotBefore"),GuardSampleFacing);
            Trial->SetNumberField(TEXT("healthBefore"),GuardSampleHealth);Trial->SetNumberField(TEXT("healthAfter"),Knight->Health);
            Trial->SetNumberField(TEXT("staminaBefore"),GuardSampleStamina);Trial->SetNumberField(TEXT("staminaAfter"),Knight->Stamina);
            Trial->SetNumberField(TEXT("actualHitDelta"),Knight->HitsTaken-GuardSampleHits);Trial->SetNumberField(TEXT("guardedDelta"),Blocks);
            Trial->SetNumberField(TEXT("guardBreakDelta"),Breaks);
            Trial->SetStringField(TEXT("move"),StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(Dragon->Move)));
            Trial->SetStringField(TEXT("actionAfter"),StaticEnum<EVeyrKnightAction>()->GetNameStringByValue(static_cast<int64>(Knight->Action)));
            BoundaryTrials.Add(MakeShared<FJsonValueObject>(Trial));
            const bool bSingle=Knight->HitsTaken==GuardSampleHits+1&&bGuardSampleHeld&&bGuardSampleGrounded;
            if(BoundaryStage==0&&bSingle&&GuardSampleFacing>.75f&&GuardSampleStamina>=40.f&&Blocks==1&&Breaks==0&&
                Lost>0.f&&Lost<=10.f&&GuardSampleStamina-Knight->Stamina>=10.f)
            {bFrontGuardVerified=true;Next(1,TEXT("front_guard_chip_and_stamina_verified"));}
            else if(BoundaryStage==1&&bSingle&&GuardSampleFacing<-.5f&&GuardSampleStamina>=40.f&&Blocks==0&&Breaks==0&&Lost>=20.f)
            {bRearGuardVerified=true;Next(2,TEXT("rear_guard_full_damage_verified"));}
            else if(BoundaryStage==2&&bSingle&&GuardSampleFacing>.75f&&GuardSampleStamina>0.f&&GuardSampleStamina<35.f&&
                Blocks==0&&Breaks==1&&Lost>=20.f&&Knight->Stamina<.5f&&Knight->IsGuardBroken()&&Knight->Action==EVeyrKnightAction::Stagger)
            {
                bGuardBreakVerified=true;Finish(bFrontGuardVerified&&bRearGuardVerified,
                    TEXT("front chip block, rear full damage while guarding with ample stamina, and real exhausted guard break verified"));return true;
            }
        }
        const bool bRear=BoundaryStage==1;
        if(Knight->bLockedOn==bRear)Knight->ToggleLockOn();
        bGuard=true;
        if(bRear)
        {
            if(APlayerController* Player=Cast<APlayerController>(Knight->GetController()))
            {
                const FVector Source=(Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active)?
                    Dragon->GetWarningFootprint().Origin:Dragon->GetActorLocation();
                const float AwayYaw=(Knight->GetActorLocation()-Source).Rotation().Yaw;
                const float Error=FMath::FindDeltaAngleDegrees(Player->GetControlRotation().Yaw,AwayYaw);
                // Normal controller look input; never SetActor/ControlRotation.
                Player->AddYawInput(FMath::Clamp(Error*.1f,-6.f,6.f));
            }
        }
        // Permit ordinary recovery healing to survive the natural sequence;
        // it neither replenishes stamina nor contributes guard coverage.
        if(Knight->Health<45.f&&Knight->HealingCharges>0&&bAvailable&&bSafeRecovery)
        {bGuard=false;bHeal=true;Movement=FVector::ZeroVector;}
        GuardSampleHealth=Knight->Health;GuardSampleStamina=Knight->Stamina;
        GuardSampleHits=Knight->HitsTaken;GuardSampleBlocks=Knight->GuardedHits;GuardSampleBreaks=Knight->GuardBreaks;
        bGuardSampleHeld=Knight->Action==EVeyrKnightAction::Guard;bGuardSampleGrounded=Knight->IsGrounded();
        const FVector Threat=(Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active)?
            Dragon->GetWarningFootprint().Origin:Dragon->GetActorLocation();
        GuardSampleFacing=FVector::DotProduct(Knight->GetActorForwardVector(),(Threat-Knight->GetActorLocation()).GetSafeNormal2D());
        bGuardSampleValid=true;
    }
    Knight->SetReplayInput(Movement,false,false,false,bHeal,false,bGuard);
    return true;
}

bool AVeyrReplay::DriveScenarioInputs()
{
    if(DriveBoundaryInputs())return true;
    if(ReplayMode!=TEXT("controls")&&ReplayMode!=TEXT("avoidance"))return false;
    FVector Movement=FVector::ZeroVector;
    bool bLight=false,bHeavy=false,bRoll=false,bHeal=false,bJump=false,bGuard=false;
    const FVector Feet=Knight->GetFootLocation();
    const bool bAvailable=Knight->Action==EVeyrKnightAction::Ready||Knight->Action==EVeyrKnightAction::Guard;
    const float Remaining=Dragon->GetStateDuration()-Dragon->GetStateElapsed();
    auto Toward=[&](const FVector& Goal)
    {
        const float Distance=FVector::Dist2D(Feet,Goal);
        if(Distance>35.f)Movement=(Goal-Feet).GetSafeNormal2D()*FMath::Clamp(Distance/140.f,.2f,1.f);
    };
    if(ReplayMode==TEXT("avoidance"))
    {
        const FVector Positions[6]={FVector(1300,0,0),FVector(2000,0,0),FVector(0,600,0),FVector(-280,-400,0),FVector(-900,0,0),FVector(850,0,0)};
        // Search inside the authored obstacle-free center instead of clamping a
        // transformed goal: clamping can silently change which attack region it is in.
        // Periodic flight/reposition and anti-repeat policy may still override a
        // positional choice. Actual observed attacks alone establish coverage.
        bAvoidanceGoalAvailable=false;DesiredAvoidanceMove=-1;
        for(int32 DesiredMove=0;DesiredMove<6&&!bAvoidanceGoalAvailable;++DesiredMove)
        {
            if(AvoidedMoves[DesiredMove]>0)continue;
            float BestScore=TNumericLimits<float>::Max();
            auto Consider=[&](const FVector& Local)
            {
                FVector Candidate=Dragon->GetActorTransform().TransformPosition(Local);Candidate.Z=0;
                if(Dragon->PredictPositionalMove(Candidate)!=DesiredMove)return;
                if(Candidate.Size2D()>3100.f)return;
                const float Score=FVector::Dist2D(Local,Positions[DesiredMove])+.15f*FVector::Dist2D(Feet,Candidate);
                if(Score<BestScore){BestScore=Score;AvoidanceGoal=Candidate;bAvoidanceGoalAvailable=true;DesiredAvoidanceMove=DesiredMove;}
            };
            Consider(Positions[DesiredMove]);
            for(int32 Radius=500;Radius<=2000;Radius+=150)
                for(int32 Angle=0;Angle<360;Angle+=15)
                    Consider(FVector(Radius,0,0).RotateAngleAxis(Angle,FVector::UpVector));
        }
        // A constrained orientation can offer no reachable untested region.
        // Returning inward may provoke normal repositioning; it is not coverage.
        if(!bAvoidanceGoalAvailable)AvoidanceGoal=FVector::ZeroVector;
        Toward(AvoidanceGoal);
        if(Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active)
        {
            if(Contains(Dragon->GetWarningFootprints(),Feet,65.f))
            {
                Movement=EscapeDirection();
                bRoll=bAvailable&&Knight->Stamina>=25.f&&(Dragon->State==EVeyrDragonState::Active||Remaining<.32f);
            }
            else Movement=FVector::ZeroVector; // Do not step back into a read telegraph.
        }
        if(Knight->Health<65.f&&Knight->HealingCharges>0&&Dragon->State==EVeyrDragonState::Recovery&&Remaining>1.3f&&bAvailable)
        {
            bHeal=true;Movement=FVector::ZeroVector;
        }
    }
    else
    {
        auto Next=[&]() { ++ControlStage;ControlStageStarted=Elapsed;Event(FString::Printf(TEXT("controls_stage_%d"),ControlStage)); };
        switch(ControlStage)
        {
            case 0:
                if(bAvailable&&Knight->IsGrounded())
                {
                    bHeal=true;bFullHealthHealRequested=true;Next();
                }
                break;
            case 1:
                if(Elapsed-ControlStageStarted>.2f)
                {
                    bFullHealthHealRejected=Knight->Health==100.f&&Knight->HealingCharges==4&&Knight->SuccessfulHeals==0&&Knight->Action!=EVeyrKnightAction::Heal;
                    if(!bFullHealthHealRejected){Finish(false,TEXT("full health heal consumed a charge or entered heal"));return true;}
                    Knight->ToggleLockOn();bLockOffObserved=!Knight->bLockedOn;
                    ControlJumpStartFootZ=Feet.Z;Next();
                }
                break;
            case 2:
                Movement=FVector(0,1,0);bJump=Knight->SuccessfulJumps==0&&Knight->IsGrounded();
                bControlMovement|=FVector::Dist2D(Feet,ControlOrigin)>100.f;
                if(Knight->SuccessfulJumps>0&&!Knight->IsGrounded())
                {
                    ControlJumpMaximumRise=FMath::Max(ControlJumpMaximumRise,static_cast<float>(Feet.Z-ControlJumpStartFootZ));
                    bControlJumpAirborne|=ControlJumpMaximumRise>10.f;
                }
                bControlJumpLanded|=bControlJumpAirborne&&Knight->IsGrounded();
                if(bControlMovement&&Knight->SuccessfulJumps>0&&bControlJumpAirborne&&bControlJumpLanded)
                {
                    Knight->ToggleLockOn();bLockOnObserved=Knight->bLockedOn;Next();
                }
                break;
            case 3:
                bLight=Knight->LightAttacks==0;
                if(Knight->LightAttacks>0&&bAvailable)Next();
                break;
            case 4:
                bHeavy=Knight->HeavyAttacks==0;
                if(Knight->HeavyAttacks>0&&bAvailable)Next();
                break;
            case 5:
                Movement=EscapeDirection();bRoll=Knight->Rolls==0;
                if(Knight->Rolls>0&&bAvailable)
                {
                    ControlStaminaBefore=Knight->Stamina;bControlStaminaSpent=Knight->Stamina<90.f;Next();
                }
                break;
            case 6:
                bControlStaminaRecovered|=Knight->Stamina>ControlStaminaBefore+10.f;
                if(bControlStaminaRecovered&&Knight->Stamina>80.f)Next();
                break;
            case 7:
                Toward(Dragon->GetActorTransform().TransformPosition(FVector(850,0,0)));
                bGuard=Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active;
                if(Knight->GuardedHits>0)Next();
                break;
            case 8:
                bGuard=Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active;
                if(Dragon->State==EVeyrDragonState::Recovery&&Remaining>1.3f&&bAvailable&&Knight->Health<100.f)
                {
                    bGuard=false;bHeal=true;
                }
                if(Knight->SuccessfulHeals>0)Next();
                break;
            default:break;
        }
    }
    Knight->SetReplayInput(Movement,bLight,bHeavy,bRoll,bHeal,bJump,bGuard);
    return true;
}

FVector AVeyrReplay::EscapeDirection() const
{
    const FVector Feet=Knight->GetFootLocation();
    const TArray<FVeyrDragonFootprint> Warning=Dragon->GetWarningFootprints();
    const FVector WarningOrigin=Warning.IsEmpty()?Dragon->GetActorLocation():Warning[0].Origin;
    FVector Best=(Feet-WarningOrigin).GetSafeNormal2D(); float BestScore=-1.e9f;
    for(int32 I=0;I<24;++I)
    {
        const FVector D=FVector::ForwardVector.RotateAngleAxis(I*15.f,FVector::UpVector);
        const FVector Candidate=Feet+D*650.f;
        if(Candidate.Size2D()>3100)continue;
        const bool bSafe=!Contains(Warning,Candidate,75.f);
        float Score=bSafe?10000.f:0.f;
        Score+=static_cast<float>(FVector::Dist2D(Candidate,WarningOrigin))*.1f;
        // Prefer routes that exit the telegraph early, not ones crossing its whole interior.
        for(int32 Step=1;Step<=5;++Step)if(!Contains(Warning,Feet+D*(Step*100.f),45.f))Score+=100.f;
        if(Score>BestScore){BestScore=Score;Best=D;}
    }
    return Best;
}

void AVeyrReplay::DriveInputs()
{
    if(DriveScenarioInputs())return;
    FVector Movement=FVector::ZeroVector;
    bool bLight=false,bHeavy=false,bRoll=false,bHeal=false,bJump=false;
    const FVector Feet=Knight->GetFootLocation();
    const bool bAvailable=Knight->Action==EVeyrKnightAction::Ready||Knight->Action==EVeyrKnightAction::Guard;
    const float Remaining=Dragon->GetStateDuration()-Dragon->GetStateElapsed();
    if(!Knight->bLockedOn)Knight->ToggleLockOn();
    if(ReplayMode==TEXT("death"))
    {
        const FVector Goal=Dragon->GetHeadLocation()+Dragon->GetActorForwardVector()*120.f;
        if(FVector::Dist2D(Feet,Goal)>70.f)Movement=(Goal-Feet).GetSafeNormal2D();
    }
    else if(Elapsed<1.4f)
    {
        bJump=Elapsed>.35f&&Knight->SuccessfulJumps==0&&Knight->IsGrounded();
    }
    else
    {
        const bool bDown=Dragon->State==EVeyrDragonState::Buckle||Dragon->State==EVeyrDragonState::Collapse||Dragon->IsHeadExposed();
        FVector Goal;
        if(bDown)Goal=Dragon->GetHeadLocation()+Dragon->GetActorForwardVector()*205.f;
        else
        {
            const FVector Leg=Dragon->GetLegLocation(TargetLeg);
            Goal=Leg+(Leg-Dragon->GetActorLocation()).GetSafeNormal2D()*185.f;
        }
        const float GoalDistance=static_cast<float>(FVector::Dist2D(Feet,Goal));
        if(GoalDistance>45.f)Movement=(Goal-Feet).GetSafeNormal2D()*FMath::Clamp(GoalDistance/160.f,.2f,1.f);
        const bool bThreat=Contains(Dragon->GetWarningFootprints(),Feet,65.f);
        const bool bDodgeExercise=ReplayMode==TEXT("core")&&Knight->DodgedHits==0&&Dragon->Move==EVeyrDragonMove::BackStomp;
        if(bDodgeExercise&&Dragon->State==EVeyrDragonState::Windup&&bThreat)
        {
            // Cross the stomp center while invulnerable so an actual damaging contact is observed.
            Movement=FVector::ZeroVector;
            if(Remaining<.19f&&bAvailable&&Knight->Stamina>=25.f)
            {
                Movement=(Dragon->GetWarningFootprint().Origin-Feet).GetSafeNormal2D(); bRoll=true;
            }
        }
        else if(bThreat&&(Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active))
        {
            Movement=EscapeDirection();
            bRoll=bAvailable&&Knight->Stamina>=25.f&&(Dragon->State==EVeyrDragonState::Active||Remaining<.32f);
        }
        else if(bAvailable&&Knight->IsGrounded())
        {
            const bool bSafeHeal=(Dragon->State==EVeyrDragonState::Recovery&&Remaining>1.35f)||bDown;
            if(Knight->Health<48.f&&Knight->HealingCharges>0&&bSafeHeal){bHeal=true;Movement=FVector::ZeroVector;}
            else if(GoalDistance<45.f&&!Dragon->IsAirborne()&&Dragon->State!=EVeyrDragonState::Rise&&Dragon->State!=EVeyrDragonState::Reposition)
            {
                Movement=FVector::ZeroVector;
                const float SafeTime=Dragon->State==EVeyrDragonState::Windup?Remaining-.22f:Dragon->State==EVeyrDragonState::Recovery?Remaining+.75f:20.f;
                const bool bNeedLight=(ReplayMode==TEXT("core")||bLegIsolation)&&!bLightLegContact&&!bDown;
                const float Reserve=bDown?0.f:25.f;
                bHeavy=!bNeedLight&&Knight->Stamina>=38.f+Reserve&&SafeTime>Knight->GetAttackDuration(true)&&(!bDown||Dragon->IsHeadExposed());
                bLight=!bHeavy&&Knight->Stamina>=22.f+Reserve&&SafeTime>Knight->GetAttackDuration(false)&&(!bDown||Dragon->IsHeadExposed());
            }
        }
    }
    Knight->SetReplayInput(Movement,bLight,bHeavy,bRoll,bHeal,bJump,false);
}

void AVeyrReplay::ServiceCapture()
{
    if(!CaptureQueue.IsEmpty()&&CaptureClock>=.30f&&!FScreenshotRequest::IsScreenshotRequested()&&PendingVideoFile.IsEmpty())
    {
        CaptureClock=0; const FString Name=CaptureQueue[0]; CaptureQueue.RemoveAt(0);
        const FString File=FPaths::Combine(RunDirectory,FString::Printf(TEXT("frame-%04d-%s.png"),++ScreenshotIndex,*Name));
        CaptureNames.Add(Name); CaptureFiles.Add(File); CaptureTimes.Add(Elapsed);
        CaptureTriggerTimes.Add(PendingCaptureTriggerTime);CaptureStates.Add(MakeShared<FJsonValueObject>(Snapshot()));
        FScreenshotRequest::RequestScreenshot(File,true,false);
    }
    ServiceVideoCapture();
}

bool AVeyrReplay::AppendVideoRecord(const TSharedRef<FJsonObject>& Record)
{
    FString Line;
    const TSharedRef<TJsonWriter<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>> Writer=TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
    if(!FJsonSerializer::Serialize(Record,Writer))return false;
    Line+=TEXT("\n");
    return FFileHelper::SaveStringToFile(Line,*FPaths::Combine(VideoDirectory,TEXT("frames.jsonl")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
}

void AVeyrReplay::InitializeVideo()
{
    int32 RequestedFPS=0;
    if(!FParse::Value(FCommandLine::Get(),TEXT("VeyrVideoFPS="),RequestedFPS))return;
    if(RequestedFPS<1||RequestedFPS>15)
    {
        bVideoStopped=true;VideoStopReason=TEXT("invalid FPS: accepted range is 1 through 15");
        UE_LOG(LogTemp,Warning,TEXT("VEYR_VIDEO_DISABLED %s"),*VideoStopReason);return;
    }
    VideoFPS=RequestedFPS;VideoDirectory=FPaths::Combine(RunDirectory,TEXT("native-video"));
    if(VideoStartedWallTime<=0)VideoStartedWallTime=FPlatformTime::Seconds();
    VideoNextWallTime=FPlatformTime::Seconds();
    if(bVideoStopped)return;
    if(!IFileManager::Get().MakeDirectory(*VideoDirectory,true))
    {
        bVideoStopped=true;VideoStopReason=TEXT("cannot create video directory");return;
    }
    // ImageUtils supports worker compression only after ImageWrapper is loaded
    // on the game thread. Never attempt module loading from the encoder job.
    if(!FModuleManager::Get().LoadModule(FName(TEXT("ImageWrapper"))))
    {
        bVideoStopped=true;VideoStopReason=TEXT("ImageWrapper unavailable for background PNG encoding");return;
    }
    // This completion delegate does not suppress normal screenshot writing.
    VideoProcessedHandle=FScreenshotRequest::OnScreenshotRequestProcessed().AddUObject(this,&AVeyrReplay::OnVideoRequestProcessed);
    TSharedRef<FJsonObject> Record=MakeShared<FJsonObject>();
    Record->SetStringField(TEXT("type"),TEXT("world_start"));Record->SetNumberField(TEXT("worldIndex"),VideoWorldIndex);
    Record->SetStringField(TEXT("sourceId"),VEYR_SOURCE_ID);Record->SetNumberField(TEXT("requestedFPS"),VideoFPS);
    Record->SetNumberField(TEXT("wallSeconds"),FPlatformTime::Seconds()-VideoStartedWallTime);
    Record->SetStringField(TEXT("timing"),TEXT("monotonic screenshot pixel-callback time; one background PNG job; native readback and pixel copy remain on game thread; real game timestep unchanged; silent"));
    if(!AppendVideoRecord(Record))StopVideoCapture(TEXT("manifest write failed"));
}

void AVeyrReplay::ServiceVideoCapture()
{
    if(VideoFPS<=0||bVideoStopped||bAwaitingReload)return;
    const double Now=FPlatformTime::Seconds();
    if(Now-VideoStartedWallTime>=600.||VideoFrameIndex>=6000)
    {
        StopVideoCapture(TEXT("bounded capture limit reached"));return;
    }
    if(Now<VideoNextWallTime)return;
    const double Interval=1./VideoFPS;
    const int32 Missed=FMath::Max(0,FMath::FloorToInt((Now-VideoNextWallTime)/Interval));
    VideoNextWallTime=Now+Interval; // Never issue catch-up captures after a slow frame.
    const IConsoleVariable* ScreenshotDelegate=IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenshotDelegate"));
    FString SkipReason;
    if(FScreenshotRequest::IsScreenshotRequested()||!PendingVideoFile.IsEmpty())SkipReason=TEXT("screenshot busy or event priority");
    else if(VideoWriteFuture.IsValid())SkipReason=TEXT("background PNG job busy; no queue");
    else if(UGameViewportClient::OnScreenshotCaptured().IsBound())SkipReason=TEXT("another pixel callback owns capture");
    else if(!ScreenshotDelegate||ScreenshotDelegate->GetInt()==0)SkipReason=TEXT("native screenshot callback disabled");
    if(Missed>0||!SkipReason.IsEmpty())
    {
        const int32 Skipped=Missed+(SkipReason.IsEmpty()?0:1);VideoSkippedSlots+=Skipped;
        TSharedRef<FJsonObject> Record=MakeShared<FJsonObject>();Record->SetStringField(TEXT("type"),TEXT("skip"));
        Record->SetNumberField(TEXT("wallSeconds"),Now-VideoStartedWallTime);Record->SetNumberField(TEXT("slots"),Skipped);
        Record->SetStringField(TEXT("reason"),SkipReason.IsEmpty()?TEXT("late tick; no catch-up"):SkipReason);
        if(!AppendVideoRecord(Record)){StopVideoCapture(TEXT("manifest write failed"));return;}
    }
    if(!SkipReason.IsEmpty())return;
    PendingVideoFile=FPaths::Combine(VideoDirectory,FString::Printf(TEXT("frame-%06d.png"),++VideoFrameIndex));
    if(IFileManager::Get().FileExists(*PendingVideoFile)){StopVideoCapture(TEXT("refusing to overwrite existing video frame"));return;}
    VideoRequestWallTime=Now;VideoRequestGameTime=Elapsed;bVideoPixelsReceived=false;
    // Bind only for this exact owned request. UE suppresses its default writer
    // while this delegate is bound, so OnVideoPixels owns saving this PNG.
    VideoPixelsHandle=UGameViewportClient::OnScreenshotCaptured().AddUObject(this,&AVeyrReplay::OnVideoPixels);
    FScreenshotRequest::RequestScreenshot(PendingVideoFile,true,false,false,FIntRect(),true);
}

void AVeyrReplay::OnVideoPixels(int32 Width,int32 Height,const TArray<FColor>& Pixels)
{
    const double Captured=FPlatformTime::Seconds();
    if(PendingVideoFile.IsEmpty()||FScreenshotRequest::GetFilename()!=PendingVideoFile)return;
    if(VideoWriteFuture.IsValid())return; // Never replace an owned in-flight job.
    bVideoPixelsReceived=true;
    FVeyrVideoWriteResult Request;
    Request.File=PendingVideoFile;Request.SourceId=VEYR_SOURCE_ID;
    Request.Index=VideoFrameIndex;Request.WorldIndex=VideoWorldIndex;
    Request.Width=Width;Request.Height=Height;
    Request.CapturedWallSeconds=Captured-VideoStartedWallTime;
    Request.RequestedWallSeconds=VideoRequestWallTime-VideoStartedWallTime;
    Request.RequestedGameSeconds=VideoRequestGameTime;
    // At most one copied frame, capped at 64 MiB of pixels. Invalid/oversized
    // frames produce a failed result without allocating a large worker copy.
    TArray<FColor> PixelCopy;
    if(Width>0&&Height>0&&static_cast<int64>(Width)*Height==Pixels.Num()&&Pixels.Num()<=16*1024*1024)
        PixelCopy=Pixels;
    Request.PixelCopySeconds=FPlatformTime::Seconds()-Captured;
    VideoWriteFuture=Async(EAsyncExecution::ThreadPool,[Request=MoveTemp(Request),PixelCopy=MoveTemp(PixelCopy)]()
    {
        // Captures are immutable values. No this pointer, actor access, delegate,
        // manifest append or game-thread callback is needed to finish the job.
        FVeyrVideoWriteResult Result=Request;
        const double WriteStarted=FPlatformTime::Seconds();
        TArray64<uint8> PNG;
        if(!PixelCopy.IsEmpty())
            FImageUtils::PNGCompressImageArray(Request.Width,Request.Height,TArrayView64<const FColor>(PixelCopy.GetData(),PixelCopy.Num()),PNG);
        Result.bSaved=!PNG.IsEmpty()&&FFileHelper::SaveArrayToFile(PNG,*Request.File);
        Result.PNGWriteSeconds=FPlatformTime::Seconds()-WriteStarted;
        return Result;
    });
}

void AVeyrReplay::ConsumeVideoWrite(bool bWait)
{
    if(!VideoWriteFuture.IsValid()||(!bWait&&!VideoWriteFuture.IsReady()))return;
    // Normal ticks only consume ready work. Shutdown/reload may wait for this
    // one owned task; its worker never waits for the game thread.
    const FVeyrVideoWriteResult Result=VideoWriteFuture.Consume();
    VideoWriteSeconds+=Result.PNGWriteSeconds;VideoPixelCopySeconds+=Result.PixelCopySeconds;
    if(Result.bSaved)++VideoFramesSaved;else ++VideoFailedFrames;
    TSharedRef<FJsonObject> Record=MakeShared<FJsonObject>();Record->SetStringField(TEXT("type"),Result.bSaved?TEXT("frame"):TEXT("failed_frame"));
    Record->SetStringField(TEXT("file"),FPaths::GetCleanFilename(Result.File));Record->SetNumberField(TEXT("index"),Result.Index);
    Record->SetStringField(TEXT("sourceId"),Result.SourceId);Record->SetNumberField(TEXT("worldIndex"),Result.WorldIndex);
    Record->SetNumberField(TEXT("width"),Result.Width);Record->SetNumberField(TEXT("height"),Result.Height);
    Record->SetNumberField(TEXT("wallSeconds"),Result.CapturedWallSeconds);
    Record->SetNumberField(TEXT("requestedWallSeconds"),Result.RequestedWallSeconds);
    Record->SetNumberField(TEXT("requestedGameSeconds"),Result.RequestedGameSeconds);
    Record->SetNumberField(TEXT("pngWriteSeconds"),Result.PNGWriteSeconds);
    Record->SetNumberField(TEXT("pixelCopySeconds"),Result.PixelCopySeconds);
    Record->SetBoolField(TEXT("backgroundPNG"),true);
    if(!Result.bSaved)Record->SetStringField(TEXT("reason"),TEXT("invalid/oversized pixels or PNG encode/write failure"));
    if(!AppendVideoRecord(Record)){bVideoStopped=true;VideoStopReason=TEXT("manifest write failed");}
}

void AVeyrReplay::OnVideoRequestProcessed()
{
    if(PendingVideoFile.IsEmpty())return; // Event screenshots are never video frames.
    if(VideoPixelsHandle.IsValid()){UGameViewportClient::OnScreenshotCaptured().Remove(VideoPixelsHandle);VideoPixelsHandle.Reset();}
    if(!bVideoPixelsReceived)
    {
        ++VideoFailedFrames;
        TSharedRef<FJsonObject> Record=MakeShared<FJsonObject>();Record->SetStringField(TEXT("type"),TEXT("failed_frame"));
        Record->SetStringField(TEXT("file"),FPaths::GetCleanFilename(PendingVideoFile));
        Record->SetNumberField(TEXT("wallSeconds"),FPlatformTime::Seconds()-VideoStartedWallTime);
        Record->SetStringField(TEXT("reason"),TEXT("owned pixel callback absent or filename mismatched"));
        if(!AppendVideoRecord(Record)){bVideoStopped=true;VideoStopReason=TEXT("manifest write failed");}
    }
    PendingVideoFile.Reset();bVideoPixelsReceived=false;
}

void AVeyrReplay::StopVideoCapture(const FString& Reason)
{
    if(VideoPixelsHandle.IsValid()){UGameViewportClient::OnScreenshotCaptured().Remove(VideoPixelsHandle);VideoPixelsHandle.Reset();}
    if(VideoProcessedHandle.IsValid()){FScreenshotRequest::OnScreenshotRequestProcessed().Remove(VideoProcessedHandle);VideoProcessedHandle.Reset();}
    if(!PendingVideoFile.IsEmpty())
    {
        if(FScreenshotRequest::GetFilename()==PendingVideoFile)FScreenshotRequest::Reset();
        if(!bVideoPixelsReceived)++VideoFailedFrames;
        PendingVideoFile.Reset();
    }
    ConsumeVideoWrite(true);
    if(VideoFPS>0&&!VideoDirectory.IsEmpty())
    {
        TSharedRef<FJsonObject> Record=MakeShared<FJsonObject>();Record->SetStringField(TEXT("type"),TEXT("world_end"));
        Record->SetNumberField(TEXT("wallSeconds"),FPlatformTime::Seconds()-VideoStartedWallTime);
        Record->SetNumberField(TEXT("worldIndex"),VideoWorldIndex);Record->SetStringField(TEXT("reason"),Reason);
        AppendVideoRecord(Record);
    }
    bVideoStopped=true;if(VideoStopReason.IsEmpty())VideoStopReason=Reason;
}

void AVeyrReplay::Finish(bool bSuccess, const FString& Reason)
{
    if(bFinished)return;
    if(ObservedWarningContainmentFailures>0)bSuccess=false;
    bFinished=true;bPassed=bSuccess;OutcomeReason=ObservedWarningContainmentFailures>0?
        TEXT("Bone contact escaped committed warning; damage was suppressed"):Reason;FinishClock=0;
    Knight->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    CaptureQueue.Reset(); Event(bSuccess?TEXT("result_pass"):TEXT("result_fail")); SaveEvidence(false);
    UE_LOG(LogTemp,Display,TEXT("VEYR_REPLAY_RESULT pass=%d seconds=%.3f reason=%s"),bPassed,Elapsed,*OutcomeReason);
}

void AVeyrReplay::BeginTerminalVerification()
{
    bTerminalSettling=true;TerminalSeconds=Elapsed;TerminalClock=0;
    Knight->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    Event(TEXT("terminal_reached_waiting_for_pose"));SaveEvidence(false);
}

void AVeyrReplay::AdvanceRestart(float DeltaSeconds)
{
    if(bTerminalSettling)
    {
        TerminalClock+=DeltaSeconds;
        if(TerminalClock>=3.6f&&TerminalClock-DeltaSeconds<3.6f)Event(TEXT("terminal_pose_settled"));
        // Leave enough time for the requested terminal screenshot to reach disk.
        if(TerminalClock>=4.5f&&!FScreenshotRequest::IsScreenshotRequested())
        {
            ConsumeVideoWrite(true); // Include the last frame before copying restart evidence.
            bAwaitingReload=true;bTerminalSettling=false;Event(TEXT("restart_requested"),false);SaveEvidence(false);
            PendingRestartEvidence=LastEvidence;PendingRestartDirectory=RunDirectory;RestartRequestedWallTime=FPlatformTime::Seconds();
            Knight->RestartIfTerminal();
        }
        else if(TerminalClock>12.f)Finish(false,TEXT("terminal screenshot did not complete before restart"));
        return;
    }
    RestartClock+=DeltaSeconds;
    if(bAwaitingReload)
    {
        if(RestartClock>12.f){PendingRestartEvidence.Reset();PendingRestartDirectory.Reset();bAwaitingReload=false;Finish(false,TEXT("restart did not load a fresh world"));}
        return;
    }
    if(!bRestartVerification)return;
    if(Knight->IsDead()||Dragon->IsDead()){Finish(false,TEXT("fresh world became terminal before response verification"));return;}
    const bool bMove=RestartClock>.2f&&RestartClock<.9f;
    const bool bAttack=RestartClock>1.f&&Knight->LightAttacks==0;
    Knight->SetReplayInput(bMove?FVector::ForwardVector:FVector::ZeroVector,bAttack,false,false,false,false,false);
    if(!bRestartMoved&&FVector::Dist2D(Knight->GetFootLocation(),RestartOrigin)>90.f){bRestartMoved=true;Event(TEXT("restart_movement_confirmed"));}
    if(!bRestartAttackAccepted&&Knight->LightAttacks>0){bRestartAttackAccepted=true;Event(TEXT("restart_attack_accepted"));}
    if(bFreshResourcesVerified&&bRestartMoved&&bRestartAttackAccepted)
        Finish(true,ReplayMode+TEXT(" terminal pose, resource reset, movement and attack after restart verified"));
    else if(RestartClock>12.f)Finish(false,TEXT("fresh pawn did not respond to movement and attack inputs"));
}

void AVeyrReplay::SaveEvidence(bool bFinal)
{
    TSharedPtr<FJsonObject> Root=MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("warningContainmentFailures"),ObservedWarningContainmentFailures);
    TSharedPtr<FJsonObject> Video=MakeShared<FJsonObject>();
    Video->SetNumberField(TEXT("requestedFPS"),VideoFPS);Video->SetNumberField(TEXT("requestedFrames"),VideoFrameIndex);
    Video->SetNumberField(TEXT("savedFrames"),VideoFramesSaved);Video->SetNumberField(TEXT("failedFrames"),VideoFailedFrames);
    Video->SetNumberField(TEXT("skippedSlots"),VideoSkippedSlots);Video->SetNumberField(TEXT("worldIndex"),VideoWorldIndex);
    Video->SetNumberField(TEXT("pngWriteSeconds"),VideoWriteSeconds);
    Video->SetNumberField(TEXT("pixelCopySeconds"),VideoPixelCopySeconds);
    Video->SetBoolField(TEXT("backgroundPNGJobInFlight"),VideoWriteFuture.IsValid());
    Video->SetNumberField(TEXT("maximumBackgroundPNGJobs"),1);
    Video->SetNumberField(TEXT("elapsedWallSeconds"),VideoStartedWallTime>0?FPlatformTime::Seconds()-VideoStartedWallTime:0);
    Video->SetBoolField(TEXT("stopped"),bVideoStopped);Video->SetStringField(TEXT("stopReason"),VideoStopReason);
    Video->SetStringField(TEXT("manifest"),VideoFPS>0?TEXT("native-video/frames.jsonl"):TEXT(""));
    Video->SetStringField(TEXT("scope"),TEXT("silent native viewport; wall-clock pixel timestamps; 6000 requests and 600 wall-second bounds; one background PNG job; readback, pixel copy, event screenshots and evidence I/O still affect frame pacing; pngWriteSeconds is worker time"));
    Root->SetObjectField(TEXT("nativeVideo"),Video);
    Root->SetStringField(TEXT("mode"),ReplayMode); Root->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());
    Root->SetStringField(TEXT("sourceId"),VEYR_SOURCE_ID);
    const bool bImportedArt=IsValid(Knight)&&IsValid(Dragon)&&Knight->bImportedPresentationActive&&Dragon->bUsingCustomuseVisual;
    Root->SetStringField(TEXT("artStatus"),bImportedArt?
        TEXT("Customuse knight and dragon with authored motion; runtime quality acceptance is separate"):
        TEXT("temporary character primitives remain active"));
    Root->SetBoolField(TEXT("bothCustomuseCharactersActive"),bImportedArt);
    Root->SetStringField(TEXT("policy"),TEXT("input-only provisional navigation; runtime tuning required"));
    Root->SetBoolField(TEXT("finished"),bFinished); Root->SetBoolField(TEXT("passed"),bFinished&&bPassed);
    Root->SetStringField(TEXT("reason"),bFinished?OutcomeReason:TEXT("running")); Root->SetNumberField(TEXT("durationSeconds"),Elapsed);
    Root->SetNumberField(TEXT("scenarioLimitGameSeconds"),DurationLimit);
    Root->SetNumberField(TEXT("worldWallElapsedSeconds"),FPlatformTime::Seconds()-StartedWallTime);
    Root->SetStringField(TEXT("worldWallElapsedScope"),TEXT("current world only; resets on restart; includes rendering, capture and evidence I/O"));
    Root->SetBoolField(TEXT("legIsolationScenario"),bLegIsolation);
    Root->SetNumberField(TEXT("targetLeg"),TargetLeg);
    Root->SetBoolField(TEXT("otherRegionContactOrStaggerObserved"),bIsolationViolated);
    Root->SetBoolField(TEXT("targetLegStaggerObserved"),bIsolatedStagger);
    Root->SetBoolField(TEXT("correctLegBuckleObserved"),bCorrectLegBuckle);
    Root->SetBoolField(TEXT("fullHealthHealRequested"),bFullHealthHealRequested);
    Root->SetBoolField(TEXT("fullHealthHealRejected"),bFullHealthHealRejected);
    Root->SetBoolField(TEXT("lockOffObserved"),bLockOffObserved);
    Root->SetBoolField(TEXT("lockOnObserved"),bLockOnObserved);
    Root->SetBoolField(TEXT("controlMovementObserved"),bControlMovement);
    Root->SetBoolField(TEXT("controlJumpAirborneObserved"),bControlJumpAirborne);
    Root->SetBoolField(TEXT("controlJumpLandingObserved"),bControlJumpLanded);
    Root->SetNumberField(TEXT("controlJumpMaximumRiseCm"),ControlJumpMaximumRise);
    Root->SetBoolField(TEXT("controlStaminaSpent"),bControlStaminaSpent);
    Root->SetBoolField(TEXT("controlStaminaRecovered"),bControlStaminaRecovered);
    Root->SetBoolField(TEXT("allSixMovesAvoided"),AllMovesAvoided());
    Root->SetNumberField(TEXT("boundaryStage"),BoundaryStage);
    Root->SetNumberField(TEXT("verifiedHealCharges"),VerifiedHealCharges);
    Root->SetBoolField(TEXT("healCapVerified"),bHealCapVerified);
    Root->SetBoolField(TEXT("injuredEmptyFlaskRejected"),bEmptyHealRejected);
    Root->SetBoolField(TEXT("frontGuardVerified"),bFrontGuardVerified);
    Root->SetBoolField(TEXT("rearGuardVerified"),bRearGuardVerified);
    Root->SetBoolField(TEXT("staminaGuardBreakVerified"),bGuardBreakVerified);
    Root->SetArrayField(TEXT("boundaryTrials"),BoundaryTrials);
    Root->SetStringField(TEXT("boundaryCoverageDefinition"),TEXT("healing: four actual completions, one charge each, min(100,before+55), then injured zero-charge request unchanged for 1.4s; guard: actual contacts with preceding-frame grounded guard/facing/stamina plus health and counter deltas; natural attacks and normal controller yaw input only"));
    Root->SetStringField(TEXT("controlsCoverageLimit"),TEXT("input hook validates gameplay action paths, not physical key bindings; empty flask, rear guard and guard break are not assertions in controls mode"));
    Root->SetStringField(TEXT("avoidanceCoverageDefinition"),TEXT("inside actual warning at least once during windup, then no HitsTaken increase through completed recovery; no boss move forcing"));
    Root->SetNumberField(TEXT("terminalSeconds"),TerminalSeconds);
    Root->SetBoolField(TEXT("victoryWithinThreeToFiveMinutes"),ReplayMode==TEXT("victory")&&TerminalSeconds>=180.f&&TerminalSeconds<=300.f);
    Root->SetBoolField(TEXT("restartRequested"),bAwaitingReload||bRestartVerification);Root->SetBoolField(TEXT("restartResourcesVerified"),bFreshResourcesVerified);
    Root->SetBoolField(TEXT("restartMovementVerified"),bRestartMoved);Root->SetBoolField(TEXT("restartAttackVerified"),bRestartAttackAccepted);
    Root->SetNumberField(TEXT("restartLoadWallSeconds"),RestartLoadSeconds);
    Root->SetNumberField(TEXT("frameCount"),FrameCount); Root->SetNumberField(TEXT("meanFrameSeconds"),FrameCount?Elapsed/FrameCount:0);
    Root->SetNumberField(TEXT("maximumFrameSeconds"),MaximumFrameSeconds);
    Root->SetBoolField(TEXT("lightLegContact"),bLightLegContact);Root->SetBoolField(TEXT("heavyLegContact"),bHeavyLegContact);Root->SetBoolField(TEXT("riseObserved"),bSawRise);Root->SetBoolField(TEXT("riseCompleted"),bRiseCompleted);
    TArray<TSharedPtr<FJsonValue>> WallSamples;for(double Interval:WallFrameIntervals)WallSamples.Add(MakeShared<FJsonValueNumber>(Interval));
    Root->SetArrayField(TEXT("wallFrameIntervalsSeconds"),WallSamples);
    Root->SetStringField(TEXT("wallFrameIntervalScope"),TEXT("replay actor tick intervals; includes capture and evidence I/O; excludes world reload; not GPU frame time"));
    if(!WallFrameIntervals.IsEmpty())
    {
        TArray<double> Sorted=WallFrameIntervals;Sorted.Sort();
        Root->SetNumberField(TEXT("wallFrameP50Seconds"),Sorted[FMath::FloorToInt((Sorted.Num()-1)*.50)]);
        Root->SetNumberField(TEXT("wallFrameP95Seconds"),Sorted[FMath::FloorToInt((Sorted.Num()-1)*.95)]);
        Root->SetNumberField(TEXT("wallFrameP99Seconds"),Sorted[FMath::FloorToInt((Sorted.Num()-1)*.99)]);
    }
    Root->SetObjectField(TEXT("latest"),Snapshot());Root->SetArrayField(TEXT("samples"),Samples);Root->SetArrayField(TEXT("events"),Events);
    TArray<TSharedPtr<FJsonValue>> Frames;
    for(int32 I=0;I<CaptureFiles.Num();++I)
    {
        TSharedPtr<FJsonObject> F=MakeShared<FJsonObject>();F->SetStringField(TEXT("event"),CaptureNames[I]);F->SetStringField(TEXT("file"),FPaths::GetCleanFilename(CaptureFiles[I]));
        F->SetNumberField(TEXT("requestedAtSeconds"),CaptureTimes[I]);F->SetBoolField(TEXT("fileExists"),IFileManager::Get().FileSize(*CaptureFiles[I])>0);
        F->SetNumberField(TEXT("triggeredAtSeconds"),CaptureTriggerTimes[I]);F->SetField(TEXT("stateAtRequest"),CaptureStates[I]);
        Frames.Add(MakeShared<FJsonValueObject>(F));
    }
    Root->SetArrayField(TEXT("screenshots"),Frames);Root->SetBoolField(TEXT("finalWrite"),bFinal);
    LastEvidence=Root;
    FString Json;const TSharedRef<TJsonWriter<>> Writer=TJsonWriterFactory<>::Create(&Json);
    const FString File=FPaths::Combine(RunDirectory,TEXT("evidence.json"));
    if(!FJsonSerializer::Serialize(Root.ToSharedRef(),Writer)||!FFileHelper::SaveStringToFile(Json,*(File+TEXT(".tmp")))||!IFileManager::Get().Move(*File,*(File+TEXT(".tmp")),true))
        UE_LOG(LogTemp,Error,TEXT("VEYR_REPLAY_EVIDENCE_WRITE_FAILED %s"),*File);
}

void AVeyrReplay::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);if(!bInitialized||bFinalSaved)return;
    ConsumeVideoWrite();
    const double Now=FPlatformTime::Seconds();
    if(LastWallFrameTime>0)WallFrameIntervals.Add(Now-LastWallFrameTime);LastWallFrameTime=Now;
    if(!IsValid(Knight)||!IsValid(Dragon))
    {
        bFinished=true;bPassed=false;OutcomeReason=TEXT("encounter actors lost");StopVideoCapture(OutcomeReason);SaveEvidence(true);bFinalSaved=true;return;
    }
    CaptureClock+=DeltaSeconds;
    if(bFinished)
    {
        FinishClock+=DeltaSeconds;
        if(FinishClock>3.f){StopVideoCapture(TEXT("replay completed"));SaveEvidence(true);bFinalSaved=true;if(bQuit)FPlatformMisc::RequestExit(false,TEXT("Veyr replay completed"));}
        else ServiceCapture();
        return;
    }
    Elapsed+=DeltaSeconds;++FrameCount;MaximumFrameSeconds=FMath::Max(MaximumFrameSeconds,DeltaSeconds);
    SampleClock+=DeltaSeconds;SaveClock+=DeltaSeconds;Observe();
    if(SampleClock>=.25f){SampleClock=0;Samples.Add(MakeShared<FJsonValueObject>(Snapshot()));}
    if(bTerminalSettling||bAwaitingReload||bRestartVerification)AdvanceRestart(DeltaSeconds);
    else if(ReplayMode==TEXT("death")&&Knight->IsDead())BeginTerminalVerification();
    else if(Knight->IsDead())Finish(false,TEXT("player died before objectives"));
    else if(ReplayMode==TEXT("victory")&&Dragon->IsDead())BeginTerminalVerification();
    else if(bLegIsolation&&bIsolationViolated)Finish(false,TEXT("leg isolation failed: contact or stagger changed a different region"));
    else if(bLegIsolation&&bLightLegContact&&bHeavyLegContact&&bIsolatedStagger&&bCorrectLegBuckle&&Dragon->State==EVeyrDragonState::Collapse)
        Finish(true,FString::Printf(TEXT("leg %d isolated light/heavy stagger, correct buckle and collapse observed; other three legs unchanged"),TargetLeg));
    else if(ReplayMode==TEXT("controls")&&ControlStage>=9&&bFullHealthHealRejected&&bLockOffObserved&&bLockOnObserved&&bControlMovement&&bControlJumpAirborne&&bControlJumpLanded&&bControlStaminaSpent&&bControlStaminaRecovered&&Knight->SuccessfulJumps>0&&Knight->LightAttacks>0&&Knight->HeavyAttacks>0&&Knight->Rolls>0&&Knight->GuardedHits>0&&Knight->SuccessfulHeals>0)
        Finish(true,TEXT("movement jump attacks roll stamina recovery lock toggles actual guard contact heal and full-health rejection observed"));
    else if(ReplayMode==TEXT("avoidance")&&AllMovesAvoided())
        Finish(true,TEXT("all six naturally selected moves threatened the player in windup and completed recovery without a damaging hit"));
    else if(ReplayMode==TEXT("core")&&Knight->SuccessfulJumps>0&&bLightLegContact&&bHeavyLegContact&&Dragon->GetCollapseCount()>0&&Dragon->GetHeadBonusHitCount()>0&&bRiseCompleted&&Knight->DodgedHits>0)
        Finish(true,TEXT("jump light heavy collapse head bonus completed rise and dodge contact observed"));
    else if(Elapsed>DurationLimit)Finish(false,TEXT("objective timeout; inspect event history and policy"));
    if(!bFinished&&!bTerminalSettling&&!bAwaitingReload&&!bRestartVerification)DriveInputs();ServiceCapture();
    if(SaveClock>=5.f){SaveClock=0;SaveEvidence(false);}
}

void AVeyrReplay::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if(EndPlayReason==EEndPlayReason::EndPlayInEditor||EndPlayReason==EEndPlayReason::Quit)
    {
        PendingRestartEvidence.Reset();PendingRestartDirectory.Reset();
        bAwaitingReload=false;
    }
    StopVideoCapture(bAwaitingReload?TEXT("world reload"):TEXT("world ended"));
    if(bInitialized&&!bFinalSaved&&!bAwaitingReload)
    {
        if(!bFinished){bFinished=true;bPassed=false;OutcomeReason=TEXT("run interrupted before objectives");}
        SaveEvidence(true);
    }
    if(IsValid(Knight))Knight->ClearReplayInput();
    Super::EndPlay(EndPlayReason);
}
