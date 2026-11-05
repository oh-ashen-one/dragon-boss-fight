#include "VeyrKnight.h"
#include "VeyrVisualDefinition.h"
#include "VeyrSkeletalPresentation.h"
#include "GameFramework/CharacterMovementComponent.h"

bool AVeyrKnight::ReadMovementTurnRoot(FName Name,float Seconds,FVector& Translation,float& Yaw) const
{
    const FVeyrVisualClip* Clip=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    if(!Clip||!Clip->Sequence||!Clip->bRootMotionRemoved||Clip->RootSampleRate<=0.f||
       Clip->RootTranslationSamplesCm.Num()<2||Clip->RootYawSamplesDegrees.Num()!=Clip->RootTranslationSamplesCm.Num())return false;
    const float Sample=FMath::Clamp((Clip->StartSeconds+Seconds*VisualClipPlayRate(Name))*Clip->RootSampleRate,
        0.f,float(Clip->RootTranslationSamplesCm.Num()-1));
    const int32 I=FMath::FloorToInt(Sample),J=FMath::Min(I+1,Clip->RootTranslationSamplesCm.Num()-1);
    Translation=FMath::Lerp(Clip->RootTranslationSamplesCm[I],Clip->RootTranslationSamplesCm[J],Sample-I);
    // Root yaw is deliberately unwrapped across180degrees by the adapter.
    Yaw=FMath::Lerp(Clip->RootYawSamplesDegrees[I],Clip->RootYawSamplesDegrees[J],Sample-I);
    return !Translation.ContainsNaN()&&FMath::IsFinite(Yaw);
}

bool AVeyrKnight::TryBeginMovementTurn()
{
    if(!bSourcedMovementTurns||Action!=EVeyrKnightAction::Ready||!CanStartGroundedAction()||
       MoveIntent.IsNearlyZero()||GetPlanarSpeed()>35.f||!CustomuseVisualDefinition)return false;
    const float Desired=FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw,MoveIntent.Rotation().Yaw);
    if(FMath::Abs(Desired)<65.f)return false;
    const FString Suffix=bTwoHanded?TEXT("TwoHand"):TEXT("OneHand");
    FName Chosen=NAME_None;float BestError=25.f;
    for(const TCHAR* Prefix:{TEXT("TurnLeft90"),TEXT("TurnRight90"),TEXT("TurnLeft180"),TEXT("TurnRight180")})
    {
        const FName Name(*(FString(Prefix)+Suffix));
        FVector End;float EndYaw=0.f;
        if(!ReadMovementTurnRoot(Name,VisualClipDuration(Name,0.f),End,EndYaw)||FMath::Abs(EndYaw)<45.f)continue;
        const FQuat Root(FVector::UpVector,FMath::DegreesToRadians(EndYaw));
        const FQuat Basis=CustomuseVisualDefinition->MeshRelativeTransform.GetRotation();
        const float ActorYaw=(Basis*Root*Basis.Inverse()).Rotator().Yaw;
        const float Error=FMath::Abs(FMath::FindDeltaAngleDegrees(ActorYaw,Desired));
        if(Error<BestError){BestError=Error;Chosen=Name;}
    }
    if(Chosen.IsNone())return false; // Unsupported directions/grips keep their existing behavior.
    MovementTurnClip=Chosen;MovementTurnStart=GetActorTransform();
    ++MovementTurnCount;
    BeginAction(EVeyrKnightAction::MovementTurn,VisualClipDuration(Chosen,0.f));
    return true;
}

void AVeyrKnight::ApplyMovementTurnRoot(float Seconds)
{
    if(!IsGrounded()){FinishAction();return;}
    FVector Translation;float Yaw=0.f;
    if(!ReadMovementTurnRoot(ActionPresentationClip,Seconds,Translation,Yaw))
    {SetPresentationDiagnostic(TEXT("Movement turn has no valid authored root trajectory"));FinishAction();return;}
    if(bBlendTurnTrajectory&&ImportedPresentation&&ImportedPresentation->bRootSpaceBlend)
    {
        const float Weight=FMath::Clamp(ProofBlendAlpha,0.f,1.f);
        Translation*=Weight;Yaw*=Weight;
    }
    // Conjugate the imported mesh-local path into actor space, including its
    // scaled/offset pivot. The inverse path is already factored into the clip.
    // Thus actor motion plus the native sampled pose reconstructs the source.
    const FTransform& Component=CustomuseVisualDefinition->MeshRelativeTransform;
    const FQuat Root(FVector::UpVector,FMath::DegreesToRadians(Yaw));
    const FQuat ActorRotation=Component.GetRotation()*Root*Component.GetRotation().Inverse();
    const FVector ActorTranslation=Component.TransformVector(Translation)+Component.GetTranslation()-
        ActorRotation.RotateVector(Component.GetTranslation());
    FVector Target=MovementTurnStart.TransformPosition(ActorTranslation);
    Target.Z=GetActorLocation().Z; // Never undo falling or changing floor height.
    const FQuat Rotation=(MovementTurnStart.GetRotation()*ActorRotation).GetNormalized();
    FHitResult Hit;
    GetCharacterMovement()->SafeMoveUpdatedComponent(Target-GetActorLocation(),Rotation,true,Hit);
    if(Hit.IsValidBlockingHit())
    {
        ++RootMotionBlockedCount;bActionRootBlocked=true;
        FinishAction(); // Never catch up through an obstruction or teleport to the authored endpoint.
    }
}
