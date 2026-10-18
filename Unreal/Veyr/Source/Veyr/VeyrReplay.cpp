#include "VeyrReplay.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrGameMode.h"
#include "VeyrIdentity.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
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
}

AVeyrReplay::AVeyrReplay()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PostPhysics;
}

bool AVeyrReplay::Initialize(const FString& Mode, const FString& EvidenceDirectory)
{
    if(bInitialized)return false;
    ReplayMode=Mode.ToLower();
    bLegIsolation=ReplayMode==TEXT("leg0")||ReplayMode==TEXT("leg1")||ReplayMode==TEXT("leg2")||ReplayMode==TEXT("leg3");
    if((ReplayMode!=TEXT("core")&&ReplayMode!=TEXT("death")&&ReplayMode!=TEXT("victory")&&ReplayMode!=TEXT("controls")&&ReplayMode!=TEXT("avoidance")&&!bLegIsolation)||EvidenceDirectory.IsEmpty()||FPaths::IsRelative(EvidenceDirectory))
    {
        UE_LOG(LogTemp,Error,TEXT("VEYR_REPLAY_REJECTED requires core|death|victory|leg0|leg1|leg2|leg3|controls|avoidance and absolute evidence directory")); return false;
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
        PendingRestartEvidence.Reset();PendingRestartDirectory.Reset();
        bRestartVerification=true;RestartOrigin=Knight->GetFootLocation();
        bFreshResourcesVerified=FMath::IsNearlyEqual(Knight->Health,100.f)&&FMath::IsNearlyEqual(Knight->Stamina,100.f)&&Knight->HealingCharges==4&&
            FMath::IsNearlyEqual(Dragon->Health,8400.f)&&!Knight->IsDead()&&!Dragon->IsDead()&&Knight->LightAttacks==0;
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

bool AVeyrReplay::DriveScenarioInputs()
{
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
        int32 DesiredMove=0;while(DesiredMove<6&&AvoidedMoves[DesiredMove]>0)++DesiredMove;
        const FVector Positions[6]={FVector(1300,0,0),FVector(2000,0,0),FVector(0,600,0),FVector(-280,-400,0),FVector(-900,0,0),FVector(850,0,0)};
        if(DesiredMove<6)Toward(Dragon->GetActorTransform().TransformPosition(Positions[DesiredMove]));
        if(Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active)
        {
            if(Contains(Dragon->GetWarningFootprint(),Feet,65.f))
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
                    Knight->ToggleLockOn();bLockOffObserved=!Knight->bLockedOn;Next();
                }
                break;
            case 2:
                Movement=FVector(0,1,0);bJump=Knight->SuccessfulJumps==0&&Knight->IsGrounded();
                bControlMovement|=FVector::Dist2D(Feet,ControlOrigin)>100.f;
                if(bControlMovement&&Knight->SuccessfulJumps>0&&Knight->IsGrounded())
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
    const FVeyrDragonFootprint Warning=Dragon->GetWarningFootprint();
    FVector Best=(Feet-Warning.Origin).GetSafeNormal2D(); float BestScore=-1.e9f;
    for(int32 I=0;I<24;++I)
    {
        const FVector D=FVector::ForwardVector.RotateAngleAxis(I*15.f,FVector::UpVector);
        const FVector Candidate=Feet+D*650.f;
        if(Candidate.Size2D()>3100)continue;
        const bool bSafe=!Contains(Warning,Candidate,75.f);
        float Score=bSafe?10000.f:0.f;
        Score+=static_cast<float>(FVector::Dist2D(Candidate,Warning.Origin))*.1f;
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
        const bool bThreat=Contains(Dragon->GetWarningFootprint(),Feet,65.f);
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
            else if(GoalDistance<95.f&&!Dragon->IsAirborne()&&Dragon->State!=EVeyrDragonState::Rise&&Dragon->State!=EVeyrDragonState::Reposition)
            {
                Movement=FVector::ZeroVector;
                const float SafeTime=Dragon->State==EVeyrDragonState::Windup?Remaining-.22f:Dragon->State==EVeyrDragonState::Recovery?Remaining+.75f:20.f;
                const bool bNeedLight=(ReplayMode==TEXT("core")||bLegIsolation)&&!bLightLegContact&&!bDown;
                const float Reserve=bDown?0.f:25.f;
                bHeavy=!bNeedLight&&Knight->Stamina>=38.f+Reserve&&SafeTime>1.15f&&(!bDown||Dragon->IsHeadExposed());
                bLight=!bHeavy&&Knight->Stamina>=22.f+Reserve&&SafeTime>.65f&&(!bDown||Dragon->IsHeadExposed());
            }
        }
    }
    Knight->SetReplayInput(Movement,bLight,bHeavy,bRoll,bHeal,bJump,false);
}

void AVeyrReplay::ServiceCapture()
{
    if(CaptureQueue.IsEmpty()||CaptureClock<.30f||FScreenshotRequest::IsScreenshotRequested())return;
    CaptureClock=0; const FString Name=CaptureQueue[0]; CaptureQueue.RemoveAt(0);
    const FString File=FPaths::Combine(RunDirectory,FString::Printf(TEXT("frame-%04d-%s.png"),++ScreenshotIndex,*Name));
    CaptureNames.Add(Name); CaptureFiles.Add(File); CaptureTimes.Add(Elapsed);
    CaptureTriggerTimes.Add(PendingCaptureTriggerTime);CaptureStates.Add(MakeShared<FJsonValueObject>(Snapshot()));
    FScreenshotRequest::RequestScreenshot(File,true,false);
}

void AVeyrReplay::Finish(bool bSuccess, const FString& Reason)
{
    if(bFinished)return;
    bFinished=true;bPassed=bSuccess;OutcomeReason=Reason;FinishClock=0;
    Knight->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    CaptureQueue.Reset(); Event(bSuccess?TEXT("result_pass"):TEXT("result_fail")); SaveEvidence(false);
    UE_LOG(LogTemp,Display,TEXT("VEYR_REPLAY_RESULT pass=%d seconds=%.3f reason=%s"),bPassed,Elapsed,*Reason);
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
    Root->SetStringField(TEXT("mode"),ReplayMode); Root->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());
    Root->SetStringField(TEXT("sourceId"),VEYR_SOURCE_ID);
    Root->SetStringField(TEXT("artStatus"),TEXT("temporary original rule-test primitives; Customuse assets and authored animation pending"));
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
    Root->SetBoolField(TEXT("controlStaminaSpent"),bControlStaminaSpent);
    Root->SetBoolField(TEXT("controlStaminaRecovered"),bControlStaminaRecovered);
    Root->SetBoolField(TEXT("allSixMovesAvoided"),AllMovesAvoided());
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
    const double Now=FPlatformTime::Seconds();
    if(LastWallFrameTime>0)WallFrameIntervals.Add(Now-LastWallFrameTime);LastWallFrameTime=Now;
    if(!IsValid(Knight)||!IsValid(Dragon))
    {
        bFinished=true;bPassed=false;OutcomeReason=TEXT("encounter actors lost");SaveEvidence(true);bFinalSaved=true;return;
    }
    CaptureClock+=DeltaSeconds;
    if(bFinished)
    {
        FinishClock+=DeltaSeconds;ServiceCapture();
        if(FinishClock>3.f){SaveEvidence(true);bFinalSaved=true;if(bQuit)FPlatformMisc::RequestExit(false,TEXT("Veyr replay completed"));}
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
    else if(ReplayMode==TEXT("controls")&&ControlStage>=9&&bFullHealthHealRejected&&bLockOffObserved&&bLockOnObserved&&bControlMovement&&bControlStaminaSpent&&bControlStaminaRecovered&&Knight->SuccessfulJumps>0&&Knight->LightAttacks>0&&Knight->HeavyAttacks>0&&Knight->Rolls>0&&Knight->GuardedHits>0&&Knight->SuccessfulHeals>0)
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
    if(bInitialized&&!bFinalSaved&&!bAwaitingReload)
    {
        if(!bFinished){bFinished=true;bPassed=false;OutcomeReason=TEXT("run interrupted before objectives");}
        SaveEvidence(true);
    }
    if(IsValid(Knight))Knight->ClearReplayInput();
    Super::EndPlay(EndPlayReason);
}
