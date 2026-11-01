#include "VeyrDragon.h"
#include "VeyrVisualDefinition.h"
#include "VeyrSkeletalPresentation.h"

bool AVeyrDragon::BeginShowcase()
{
    if(bShowcaseMode||!bUsingCustomuseVisual||!VisualDefinition||!ImportedPresentation||IsDead())return false;
    bShowcaseMode=true;bProofPassive=false;StopDataMove();
    ShowcaseSegment=ShowcaseOverrideClip=NAME_None;ShowcaseLeg=INDEX_NONE;
    EnterState(EVeyrDragonState::Idle,1.f);
    return true;
}

bool AVeyrDragon::StartShowcaseSegment(FName Segment,FString& Error)
{
    if(!bShowcaseMode||State!=EVeyrDragonState::Idle||!ShowcaseSegment.IsNone())
    {Error=TEXT("Showcase segment requires an idle rehearsal actor");return false;}
    ShowcaseSegment=Segment;ShowcaseOverrideClip=NAME_None;ShowcaseLeg=INDEX_NONE;
    const FString Name=Segment.ToString();
    if(Segment==TEXT("Idle")||Segment==TEXT("Roar"))
    {
        const FVeyrVisualClip* Clip=VisualDefinition->Clips.Find(Segment);
        if(!Clip||!Clip->Sequence){Error=TEXT("Missing required showcase clip: ")+Name;return false;}
        if(Segment==TEXT("Roar")&&Clip->ImpactSeconds<0.f)
        {Error=TEXT("Roar needs its measured jaw-opening cue");return false;}
        ShowcaseOverrideClip=Segment;
        EnterState(EVeyrDragonState::Idle,VisualClipDuration(Segment,0.f));
        return StateDuration>0.f;
    }
    if(Segment==TEXT("Walk"))
    {
        const float Duration=VisualClipDuration(TEXT("Walk"),0.f);
        if(Duration<=0.f||WalkCycleDistance()<=0.f){Error=TEXT("Walk has no measured cycle");return false;}
        MoveStart=GetActorLocation();MoveStart.Z=0;
        MoveEnd=MoveStart+GetActorForwardVector()*WalkCycleDistance();
        TurnStart=TurnEnd=GetActorRotation();RepositionYawDelta=0.f;
        RepositionTurnDuration=0.f;RepositionTravelDuration=Duration;
        bRepositionAuthoredTurn=false;bRepositionWalking=true;WalkPhase=0.f;
        EnterState(EVeyrDragonState::Reposition,Duration);return true;
    }
    if(Name.StartsWith(TEXT("Turn")))
    {
        const bool Left=Name.Contains(TEXT("Left")),Fine=Name.Contains(TEXT("Fine"));
        TurnStart=GetActorRotation();RepositionStartTransform=GetActorTransform();
        RepositionTravelDuration=0.f;bRepositionWalking=false;TurnPhase=0.f;
        RepositionTurnClip=Fine?Segment:FName(TEXT("TurnLeft"));
        RepositionTurnSourceDuration=VisualClipDuration(RepositionTurnClip,0.f);
        if(RepositionTurnSourceDuration<=0.f){Error=TEXT("Missing turn: ")+Name;return false;}
        bRepositionAuthoredTurn=!Fine;bRepositionReverseTurn=false;
        if(!Fine)
        {
            FVector Translation;float Yaw=0.f;
            if(!ReadTurnTrajectory(RepositionTurnSourceDuration,Translation,Yaw)||FMath::Abs(Yaw)<45.f)
            {Error=TEXT("Large turn has no measured root trajectory");return false;}
            bRepositionReverseTurn=(Left?-1.f:1.f)*Yaw<0.f;
            const FTransform End=RepositionTurnTransform(1.f);
            TurnEnd=End.Rotator();MoveStart=MoveEnd=End.GetLocation();
            RepositionTurnDuration=RepositionTurnSourceDuration/1.22f;
        }
        else
        {
            TurnEnd=TurnStart+FRotator(0,Left?-20.f:20.f,0);
            MoveStart=MoveEnd=GetActorLocation();
            RepositionTurnDuration=RepositionTurnSourceDuration;
        }
        RepositionYawDelta=FMath::FindDeltaAngleDegrees(TurnStart.Yaw,TurnEnd.Yaw);
        EnterState(EVeyrDragonState::Reposition,RepositionTurnDuration);return true;
    }
    if(Name.StartsWith(TEXT("Stagger")))
    {
        StruckLeg=FCString::Atoi(*Name.Right(1));
        if(StruckLeg<0||StruckLeg>3){Error=TEXT("Invalid stagger limb");return false;}
        EnterState(EVeyrDragonState::Buckle,.65f);return true;
    }
    if(Segment==TEXT("Death")){EnterState(EVeyrDragonState::Dead,3.4f);return true;}
    EVeyrDragonMove Attack;
    if(Segment==TEXT("Fire"))Attack=EVeyrDragonMove::Fire;
    else if(Segment==TEXT("Flight"))Attack=EVeyrDragonMove::FlyAway;
    else if(Segment==TEXT("Bite"))Attack=EVeyrDragonMove::Bite;
    else if(Segment==TEXT("Tail"))Attack=EVeyrDragonMove::TailSmack;
    else if(Name.StartsWith(TEXT("Claw")))
    {Attack=EVeyrDragonMove::ClawSwipe;ClawLeg=Name.EndsWith(TEXT("1"))?1:0;}
    else if(Name.StartsWith(TEXT("Stomp")))
    {Attack=EVeyrDragonMove::BackStomp;ShowcaseLeg=Name.EndsWith(TEXT("3"))?3:2;}
    else{Error=TEXT("Unknown showcase segment: ")+Name;return false;}
    BeginAttack(Attack);return true;
}

bool AVeyrDragon::IsShowcaseSegmentComplete() const
{
    if(!bShowcaseMode||ShowcaseSegment.IsNone())return false;
    if(!ShowcaseOverrideClip.IsNone())return StateElapsed>=StateDuration;
    if(ShowcaseSegment==TEXT("Death"))return IsDead()&&StateElapsed>=StateDuration+1.f;
    return State==EVeyrDragonState::Idle;
}

void AVeyrDragon::RestAfterShowcaseSegment()
{
    if(!bShowcaseMode)return;
    ShowcaseSegment=ShowcaseOverrideClip=NAME_None;ShowcaseLeg=INDEX_NONE;
    if(!IsDead())EnterState(EVeyrDragonState::Idle,.9f);
}

TArray<FTransform> AVeyrDragon::GetShowcaseFramingTransforms() const
{
    TArray<FTransform> Result;
    Result.Add(GetActorTransform());
    if(!bShowcaseMode||State!=EVeyrDragonState::Reposition)return Result;
    for(int32 I=0;I<=8;++I)
    {
        const float T=I/8.f;
        if(bRepositionAuthoredTurn)Result.Add(RepositionTurnTransform(T));
        else Result.Add(FTransform(FQuat::Slerp(TurnStart.Quaternion(),TurnEnd.Quaternion(),T),
            FMath::Lerp(MoveStart,MoveEnd,T),GetActorScale3D()));
    }
    return Result;
}

FVector AVeyrDragon::GetShowcaseFlightFacing() const
{
    // Same hover position/target as the production flight arc at its midpoint.
    const FVector Hover=FMath::Lerp(MoveStart,MoveEnd,.35f)+AttackForward.RotateAngleAxis(90.f,FVector::UpVector)*280.f;
    return (AerialFireTarget-Hover).GetSafeNormal2D();
}
