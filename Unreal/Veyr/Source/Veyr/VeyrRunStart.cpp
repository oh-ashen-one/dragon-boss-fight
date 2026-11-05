#include "VeyrKnight.h"
#include "VeyrVisualDefinition.h"
#include "GameFramework/CharacterMovementComponent.h"

bool AVeyrKnight::TryBeginRunStart()
{
    // Isolated two-hand trial. Keep the existing one-hand and walking routes
    // until their sourced transitions have their own integration evidence.
    if(!bSourcedRunStart||!bTwoHanded||!bSprintHeld||Action!=EVeyrKnightAction::Ready||
       !CanStartGroundedAction()||MoveIntent.IsNearlyZero()||GetPlanarSpeed()>35.f||
       bGuardRequested||bPrimaryAttackHeld)return false;
    const FName Name=TEXT("RunStartTwoHandSourced");
    const FVeyrVisualClip* Clip=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    if(!Clip||!Clip->Sequence||!Clip->bRootMotionRemoved||Clip->RootTranslationSamplesCm.Num()<2||
       !LocomotionPhaseCache.Contains(SelectDirectionalLocomotion(true)))return false;
    RunStartVelocity=FVector::ZeroVector;
    RunStartLoopClip=NAME_None;RunStartLoopTime=0.f;
    ++RunStarts;
    BeginAction(EVeyrKnightAction::RunStart,VisualClipDuration(Name,2.2f));
    return true;
}
