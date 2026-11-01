#include "VeyrShowcase.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "VeyrGameMode.h"
#include "VeyrFightFeel.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

namespace
{
    TArray<FVector> Corners(const FBox& Box)
    {
        TArray<FVector> Result;
        for(int32 I=0;I<8;++I)Result.Add(FVector(I&1?Box.Max.X:Box.Min.X,I&2?Box.Max.Y:Box.Min.Y,I&4?Box.Max.Z:Box.Min.Z));
        return Result;
    }
    TArray<FVector> FramingPoints(AVeyrDragon* Dragon)
    {
        TArray<FVector> Points;
        auto Add=[&](const FVector& Center,float Radius){Points.Append(Corners(FBox(Center-FVector(Radius),Center+FVector(Radius))));};
        for(const TCHAR* Name:{TEXT("head"),TEXT("jaw"),TEXT("gaze_neck"),TEXT("leg0"),TEXT("leg1"),TEXT("leg2"),TEXT("leg3"),
            TEXT("foot0"),TEXT("foot1"),TEXT("foot2"),TEXT("foot3"),TEXT("tail0"),TEXT("tail1"),TEXT("tail2"),TEXT("tail3"),TEXT("tail_tip")})
        {
            FTransform T;
            if(Dragon->ImportedPresentation->GetBoneTargetWorldTransform(Name,T))Add(T.GetLocation(),FName(Name)==TEXT("head")?350.f:100.f);
        }
        for(const TCHAR* Name:{TEXT("VeyrWingNegZRoot"),TEXT("VeyrWingNegZElbow"),TEXT("VeyrWingNegZWrist"),TEXT("VeyrWingNegZTip"),TEXT("VeyrWingNegZMembrane"),
            TEXT("VeyrWingPosZRoot"),TEXT("VeyrWingPosZElbow"),TEXT("VeyrWingPosZWrist"),TEXT("VeyrWingPosZTip"),TEXT("VeyrWingPosZMembrane")})
            Add(Dragon->ImportedPresentation->GetBoneLocation(Name),120.f);
        return Points;
    }
    FBox PointBounds(const TArray<FVector>& Points)
    {FBox Box(ForceInit);for(const FVector& P:Points)Box+=P;return Box;}
    float RequiredFOV(const FVector& Position,const FRotator& Rotation,const TArray<FVector>& Points)
    {
        const FRotationMatrix R(Rotation);float Tangent=0.f;
        for(const FVector& P:Points)
        {
            const FVector D=P-Position;const float Depth=FVector::DotProduct(D,R.GetUnitAxis(EAxis::X));
            if(Depth<=10.f)return 170.f;
            Tangent=FMath::Max(Tangent,FMath::Max(FMath::Abs(float(FVector::DotProduct(D,R.GetUnitAxis(EAxis::Y))))/Depth,
                FMath::Abs(float(FVector::DotProduct(D,R.GetUnitAxis(EAxis::Z))))/Depth*16.f/9.f));
        }
        return FMath::RadiansToDegrees(2.f*FMath::Atan(Tangent*1.12f));
    }
}

bool FVeyrShowcase::Begin(UWorld* World,AVeyrKnight* InKnight,AVeyrDragon* InDragon,bool PlayerCamera,const FHooks& InHooks)
{
    Hooks=InHooks;Knight=InKnight;Dragon=InDragon;bPlayerCamera=PlayerCamera;
    if(!World||!InKnight||!InDragon||!InDragon->VisualDefinition)return false;
    auto Add=[this](const TCHAR* Name,TArray<FName> Clips,TArray<FString> RequiredStates){Steps.Add({FName(Name),MoveTemp(Clips),MoveTemp(RequiredStates)});};
    Add(TEXT("Idle"),{TEXT("Idle")},{TEXT("Idle")});
    Add(TEXT("Roar"),{TEXT("Roar")},{TEXT("Idle")});
    Add(TEXT("Walk"),{TEXT("Walk")},{TEXT("Reposition")});
    Add(TEXT("TurnLeft"),{TEXT("TurnLeft")},{TEXT("Reposition")});
    Add(TEXT("TurnRight"),{TEXT("TurnLeft")},{TEXT("Reposition")}); // Production reverse of measured root turn.
    Add(TEXT("TurnLeftFine"),{TEXT("TurnLeftFine")},{TEXT("Reposition")});
    Add(TEXT("TurnRightFine"),{TEXT("TurnRightFine")},{TEXT("Reposition")});
    for(const TCHAR* Name:{TEXT("Fire"),TEXT("Flight"),TEXT("Claw0"),TEXT("Claw1"),TEXT("Stomp2"),TEXT("Stomp3"),TEXT("Tail"),TEXT("Bite")})
    {
        const FString N(Name);
        Add(Name,{FName(*(N+TEXT("Windup"))),FName(*(N+TEXT("Active"))),FName(*(N+TEXT("Recovery")))},
            {TEXT("Windup"),TEXT("Active"),TEXT("Recovery")});
    }
    for(int32 I=0;I<4;++I)
        Add(*FString::Printf(TEXT("Stagger%d"),I),{FName(*FString::Printf(TEXT("Buckle%d"),I)),TEXT("Collapse"),TEXT("Exposed"),TEXT("Rise")},
            {TEXT("Buckle"),TEXT("Collapse"),TEXT("Exposed"),TEXT("Rise")});
    Add(TEXT("Death"),{TEXT("DeathFall")},{TEXT("Dead")});
    for(const FStep& Step:Steps)for(FName Name:Step.Clips)
    {
        const FVeyrVisualClip* Clip=InDragon->VisualDefinition->Clips.Find(Name);
        if(!Clip||!Clip->Sequence){Hooks.Finish(false,TEXT("Showcase missing required native clip: ")+Name.ToString());return false;}
    }
    TSet<FName> Accounted;
    for(const FStep& Step:Steps)for(FName Name:Step.Clips)Accounted.Add(Name);
    for(FName Name:{FName(TEXT("TurnRight")),FName(TEXT("FlightHoverAlternate")),FName(TEXT("ClawWindup")),FName(TEXT("ClawActive")),
        FName(TEXT("ClawRecovery")),FName(TEXT("Death")),FName(TEXT("DeathDown")),FName(TEXT("DeathFallDown"))})Accounted.Add(Name);
    for(const auto& Entry:InDragon->VisualDefinition->Clips)
        if(!Accounted.Contains(Entry.Key)){Hooks.Finish(false,TEXT("Unclassified native clip in showcase inventory: ")+Entry.Key.ToString());return false;}
    const auto& Hover=InDragon->VisualDefinition->Clips.FindChecked(TEXT("FlightActive"));
    const auto* Alternate=InDragon->VisualDefinition->Clips.Find(TEXT("FlightHoverAlternate"));
    if(Alternate&&(Alternate->ApprovedSourceSHA256!=Hover.ApprovedSourceSHA256||Alternate->StartSeconds!=Hover.StartSeconds||
        Alternate->EndSeconds!=Hover.EndSeconds||Alternate->bLoop!=Hover.bLoop||Alternate->GameplayPlayRate!=Hover.GameplayPlayRate))
    {Hooks.Finish(false,TEXT("Alternate hover is distinct and needs its own showcase chapter"));return false;}
    if(!InDragon->BeginShowcase())return false;
    for(const TCHAR* Name:{TEXT("VeyrWingNegZRoot"),TEXT("VeyrWingNegZElbow"),TEXT("VeyrWingNegZWrist"),TEXT("VeyrWingNegZTip"),TEXT("VeyrWingNegZMembrane"),
        TEXT("VeyrWingPosZRoot"),TEXT("VeyrWingPosZElbow"),TEXT("VeyrWingPosZWrist"),TEXT("VeyrWingPosZTip"),TEXT("VeyrWingPosZMembrane")})
        if(InDragon->ImportedPresentation->GetBoneIndex(Name)==INDEX_NONE){Hooks.Finish(false,TEXT("Missing framing anchor: ")+FString(Name));return false;}
    bWasHidden=InKnight->IsHidden();bHadCollision=InKnight->GetActorEnableCollision();
    SavedMovementMode=InKnight->GetCharacterMovement()->MovementMode;SavedCustomMovementMode=InKnight->GetCharacterMovement()->CustomMovementMode;
    bControlsTaken=true;
    InKnight->SetActorHiddenInGame(true);InKnight->SetActorEnableCollision(false);
    InKnight->GetCharacterMovement()->DisableMovement();InKnight->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    if(!bPlayerCamera)
    {
        Camera=World->SpawnActor<ACameraActor>();
        if(!Camera.IsValid())return false;
        Camera->GetCameraComponent()->bConstrainAspectRatio=false;
        if(auto* PC=Cast<APlayerController>(InKnight->GetController()))PC->SetViewTarget(Camera.Get());
        else return false;
        FrameShot();
    }
    RestUntil=.6f;
    return true;
}

bool FVeyrShowcase::BeginStep(float Elapsed)
{
    if(++StepIndex>=Steps.Num())
    {bDone=true;Hooks.Finish(true,TEXT("Every-move rehearsal completed with native clip/state coverage; not a combat victory"));return false;}
    Seen.Reset();States.Reset();FlightFireFrames=0;MinimumCornersVisible=1.f;FrustumMissFrames=ObstructedFrames=0;
    FString Error;
    if(!Dragon->StartShowcaseSegment(Steps[StepIndex].Name,Error))
    {bDone=true;Hooks.Finish(false,Error);return false;}
    StepStarted=Elapsed;bResting=false;
    if(Camera.IsValid())FrameShot();
    Hooks.Event(TEXT("showcase_begin_")+Steps[StepIndex].Name.ToString());
    return true;
}

void FVeyrShowcase::FrameShot()
{
    TArray<FVector> Points=FramingPoints(Dragon.Get());
    const FName Segment=Steps.IsValidIndex(StepIndex)?Steps[StepIndex].Name:FName(TEXT("Idle"));
    if(Dragon->State==EVeyrDragonState::Reposition)
    {
        const FTransform Start=Dragon->GetActorTransform();const TArray<FVector> Pose=Points;
        for(const FTransform& Frame:Dragon->GetShowcaseFramingTransforms())
            for(const FVector& P:Pose)Points.Add(Frame.TransformPosition(Start.InverseTransformPosition(P)));
    }
    if(Segment==TEXT("Flight"))
    {
        const FVector Travel=Dragon->GetLandingLocation()-Dragon->GetActorLocation();
        const TArray<FVector> Start=Points;
        for(const FVector& P:Start){Points.Add(P+Travel);Points.Add(P+FVector(0,0,1400));Points.Add(P+Travel+FVector(0,0,1400));}
    }
    else
    {
        for(const auto& F:Dragon->GetWarningFootprints())
        {
            if(F.Shape==EVeyrDangerShape::Capsule)
            {
                for(const FVector& P:{F.Origin,F.End}){Points.Add(P+FVector(F.OuterRadius,F.OuterRadius,0));Points.Add(P-FVector(F.OuterRadius,F.OuterRadius,0));}
            }
            else for(float A:{-F.HalfAngleDegrees,0.f,F.HalfAngleDegrees})Points.Add(F.Origin+F.Forward.RotateAngleAxis(A,FVector::UpVector)*F.OuterRadius);
        }
        if(Segment==TEXT("Walk")){const TArray<FVector> Start=Points;const FVector Travel=Dragon->GetLandingLocation()-Dragon->GetActorLocation();for(const FVector& P:Start)Points.Add(P+Travel);}
        if(Segment==TEXT("Roar")){const TArray<FVector> Start=Points;for(const FVector& P:Start)Points.Add(P+FVector(0,0,350));}
    }
    ShotFocus=PointBounds(Points).GetCenter();
    const FString Name=Segment.ToString();
    float Angle=45.f;
    if(Name==TEXT("Fire"))Angle=85.f;
    if(Name.Contains(TEXT("1"))||Name.Contains(TEXT("3")))Angle=-45.f;
    if(Name.StartsWith(TEXT("Stomp"))||Name==TEXT("Tail"))Angle+=100.f;
    FVector Preferred=Dragon->GetActorForwardVector().RotateAngleAxis(Angle,FVector::UpVector);
    FVector Feature=Dragon->GetHeadLocation();
    if(Name.StartsWith(TEXT("Claw"))||Name.StartsWith(TEXT("Stomp"))||Name.StartsWith(TEXT("Stagger")))
        Feature=Dragon->GetLegLocation(FCString::Atoi(*Name.Right(1)));
    if(Name==TEXT("Tail"))Feature=Dragon->GetActorLocation()-Dragon->GetActorForwardVector()*500.f;
    FVector FeatureDirection=(Feature-Dragon->GetActorLocation()).GetSafeNormal2D();
    if(Name.StartsWith(TEXT("Claw"))||Name.StartsWith(TEXT("Stomp"))||Name.StartsWith(TEXT("Stagger")))
        Preferred=FeatureDirection; // The actual anatomical side, not a guessed left/right camera sign.
    if(Segment==TEXT("Flight"))
    {FeatureDirection=Dragon->GetShowcaseFlightFacing();Preferred=FeatureDirection.RotateAngleAxis(-40.f,FVector::UpVector);}
    FVector Best=ShotFocus+Preferred*2400.f+FVector(0,0,450.f);
    float BestScore=TNumericLimits<float>::Max(),BestFOV=60.f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrShowcaseCamera),true,Dragon.Get());Params.AddIgnoredActor(Knight.Get());
    for(int32 I=0;I<16;++I)
    {
        const FVector Direction=Preferred.RotateAngleAxis(I*22.5f,FVector::UpVector);
        FVector P=ShotFocus+Direction*2400.f;
        // Camera remains inside the open court; raise it only when needed to
        // cover a full aerial envelope without looking through architecture.
        P.Z=ShotFocus.Z+(Segment==TEXT("Flight")?1000.f:450.f);
        if(P.SizeSquared2D()>FMath::Square(2800.f))continue;
        FRotator Rotation=(ShotFocus-P).Rotation();float FOV=RequiredFOV(P,Rotation,Points);
        for(int32 Lift=0;FOV>88.f&&Lift<4;++Lift){P.Z+=250.f;Rotation=(ShotFocus-P).Rotation();FOV=RequiredFOV(P,Rotation,Points);}
        FHitResult Hit;const bool Blocked=Dragon->GetWorld()->LineTraceSingleByChannel(Hit,P,ShotFocus,ECC_Camera,Params)||
            Dragon->GetWorld()->LineTraceSingleByChannel(Hit,P,PointBounds(FramingPoints(Dragon.Get())).GetCenter(),ECC_Camera,Params);
        const float FeatureView=FVector::DotProduct((P-Dragon->GetActorLocation()).GetSafeNormal2D(),FeatureDirection);
        const float Score=(1.f-FVector::DotProduct(Direction,Preferred))*100.f+
            FMath::Max(0.f,-FeatureView)*300.f+(Blocked?10000.f:0.f)+FMath::Max(0.f,FOV-88.f)*100.f;
        if(Score<BestScore){BestScore=Score;Best=P;BestFOV=FOV;}
    }
    Camera->SetActorLocationAndRotation(Best,(ShotFocus-Best).Rotation());
    Camera->GetCameraComponent()->SetFieldOfView(FMath::Clamp(BestFOV,48.f,95.f));
    CameraDiagnostic=BestScore>=10000.f?TEXT("No unobstructed candidate: rendered review required"):TEXT("Chapter shot fitted to evaluated anatomical supports and action envelope");
}

void FVeyrShowcase::ObserveFrame()
{
    auto* Pose=Dragon->ImportedPresentation.Get();
    if(!Pose||!Pose->bPoseEvaluated||!Dragon->MissingVisualClip.IsNone())
    {bDone=true;Hooks.Finish(false,TEXT("Showcase encountered a missing or unevaluated native pose"));return;}
    FSeen& S=Seen.FindOrAdd(Pose->CurrentClip);++S.Frames;S.Min=FMath::Min(S.Min,Pose->CurrentPhase);S.Max=FMath::Max(S.Max,Pose->CurrentPhase);
    States.Add(StaticEnum<EVeyrDragonState>()->GetNameStringByValue(static_cast<int64>(Dragon->State)));
    if(Dragon->Move==EVeyrDragonMove::FlyAway&&Dragon->GetActiveFlameBeam().bDamaging)
    {
        ++FlightFireFrames;
        if(FlightFireFrames==1)Hooks.Event(TEXT("showcase_flight_fire_down"));
    }
    UCameraComponent* View=Camera.IsValid()?Camera->GetCameraComponent():Knight->CombatCamera.Get();
    if(View)
    {
        const auto Points=FramingPoints(Dragon.Get());
        const float Need=RequiredFOV(View->GetComponentLocation(),View->GetComponentRotation(),Points);
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrShowcaseFraming),true,Dragon.Get());Params.AddIgnoredActor(Knight.Get());
        const bool Blocked=Dragon->GetWorld()->LineTraceSingleByChannel(Hit,View->GetComponentLocation(),PointBounds(Points).GetCenter(),ECC_Camera,Params);
        const float Ratio=Need<=View->FieldOfView&&!Blocked?1.f:0.f;
        if(Need>View->FieldOfView)++FrustumMissFrames;
        if(Blocked)++ObstructedFrames;
        if(Ratio>0.f)++S.FramedFrames;
        MinimumCornersVisible=FMath::Min(MinimumCornersVisible,Ratio);
    }
}

void FVeyrShowcase::Tick(float,float Elapsed)
{
    if(bDone||!Knight.IsValid()||!Dragon.IsValid())return;
    Knight->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    if(Camera.IsValid())
    {
        const auto Points=FramingPoints(Dragon.Get());
        // Keep the planned shot fixed so locomotion remains visible against
        // the arena; widen only as needed, never breathe with each wingbeat.
        const float Need=RequiredFOV(Camera->GetActorLocation(),Camera->GetActorRotation(),Points);
        if(Need>Camera->GetCameraComponent()->FieldOfView)Camera->GetCameraComponent()->SetFieldOfView(FMath::Min(95.f,Need+2.f));
        Dragon->SetViewOcclusion(Camera->GetActorLocation(),ShotFocus,false);
        if(auto* Mode=Dragon->GetWorld()->GetAuthGameMode<AVeyrGameMode>())if(Mode->FightFeel)
            Mode->FightFeel->ApplyCameraShake(Camera->GetCameraComponent());
    }
    if(bResting){if(Elapsed>=RestUntil)BeginStep(Elapsed);return;}
    ObserveFrame();if(bDone)return;
    if(Elapsed-StepStarted>40.f){bDone=true;Hooks.Finish(false,TEXT("Showcase segment timeout: ")+Steps[StepIndex].Name.ToString());return;}
    if(!Dragon->IsShowcaseSegmentComplete())return;
    bool Passed=true;
    for(FName Name:Steps[StepIndex].Clips)
    {
        const FSeen* S=Seen.Find(Name);
        Passed&=S&&S->Frames>=2&&S->Min<=.15f&&S->Max>=.85f;
        if(!bPlayerCamera)Passed&=S&&S->FramedFrames>=FMath::CeilToInt(S->Frames*.9f);
    }
    for(const FString& State:Steps[StepIndex].States)Passed&=States.Contains(State);
    if(Steps[StepIndex].Name==TEXT("Flight"))Passed&=FlightFireFrames>0;
    auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("segment"),Steps[StepIndex].Name.ToString());
    Row->SetNumberField(TEXT("startSeconds"),StepStarted);Row->SetNumberField(TEXT("endSeconds"),Elapsed);Row->SetBoolField(TEXT("passed"),Passed);
    Row->SetNumberField(TEXT("flightFireDownFrames"),FlightFireFrames);Row->SetNumberField(TEXT("minimumAnatomicalSupportsFramed"),MinimumCornersVisible);
    Row->SetNumberField(TEXT("frustumMissFrames"),FrustumMissFrames);Row->SetNumberField(TEXT("obstructedFrames"),ObstructedFrames);
    TSharedPtr<FJsonObject> Clips=MakeShared<FJsonObject>();for(const auto& P:Seen){auto C=MakeShared<FJsonObject>();C->SetNumberField(TEXT("frames"),P.Value.Frames);C->SetNumberField(TEXT("framedFrames"),P.Value.FramedFrames);C->SetNumberField(TEXT("minPhase"),P.Value.Min);C->SetNumberField(TEXT("maxPhase"),P.Value.Max);Clips->SetObjectField(P.Key.ToString(),C);}Row->SetObjectField(TEXT("clips"),Clips);
    Chapters.Add(MakeShared<FJsonValueObject>(Row));Hooks.Event(TEXT("showcase_end_")+Steps[StepIndex].Name.ToString());
    if(!Passed){bDone=true;Hooks.Finish(false,TEXT("Showcase did not cover required clip phases/states: ")+Steps[StepIndex].Name.ToString());return;}
    Dragon->RestAfterShowcaseSegment();bResting=true;RestUntil=Elapsed+.9f;
}

TSharedPtr<FJsonObject> FVeyrShowcase::Evidence() const
{
    auto R=MakeShared<FJsonObject>();R->SetStringField(TEXT("scope"),TEXT("Scripted non-combat rehearsal: production states, poses, trajectories and effects; damage disabled; never a victory proof"));
    R->SetNumberField(TEXT("step"),StepIndex);R->SetNumberField(TEXT("requiredSegments"),Steps.Num());R->SetBoolField(TEXT("playerCameraBaseline"),bPlayerCamera);
    R->SetStringField(TEXT("currentSegment"),Steps.IsValidIndex(StepIndex)?Steps[StepIndex].Name.ToString():bDone?TEXT("complete"):TEXT("preparing"));R->SetStringField(TEXT("cameraDiagnostic"),CameraDiagnostic);R->SetArrayField(TEXT("chapters"),Chapters);
    R->SetStringField(TEXT("retainedEntryPolicy"),TEXT("Generic claw and legacy deaths are compatibility/comparison entries; right large turn uses the production reversed left root track; alternate hover is source-identical; downed death is a trim of the full fall, with separate victory-transition evidence"));
    if(Dragon.IsValid()&&Dragon->ImportedPresentation)
    {
        const FBox Bounds=PointBounds(FramingPoints(Dragon.Get()));auto B=MakeShared<FJsonObject>();
        B->SetNumberField(TEXT("minZ"),Bounds.Min.Z);B->SetNumberField(TEXT("maxZ"),Bounds.Max.Z);
        B->SetNumberField(TEXT("spanX"),Bounds.GetSize().X);B->SetNumberField(TEXT("spanY"),Bounds.GetSize().Y);
        R->SetObjectField(TEXT("anatomicalSupports"),B);
    }
    if(Camera.IsValid()){auto C=MakeShared<FJsonObject>();const FVector P=Camera->GetActorLocation();C->SetNumberField(TEXT("x"),P.X);C->SetNumberField(TEXT("y"),P.Y);C->SetNumberField(TEXT("z"),P.Z);C->SetNumberField(TEXT("fov"),Camera->GetCameraComponent()->FieldOfView);R->SetObjectField(TEXT("camera"),C);}
    return R;
}

void FVeyrShowcase::End()
{
    if(bControlsTaken&&Knight.IsValid())
    {
        if(auto* PC=Cast<APlayerController>(Knight->GetController()))if(Camera.IsValid()&&PC->GetViewTarget()==Camera.Get())PC->SetViewTarget(Knight.Get());
        Knight->SetActorHiddenInGame(bWasHidden);Knight->SetActorEnableCollision(bHadCollision);
        Knight->GetCharacterMovement()->SetMovementMode(static_cast<EMovementMode>(SavedMovementMode),SavedCustomMovementMode);
    }
    if(Camera.IsValid())Camera->Destroy();
}
