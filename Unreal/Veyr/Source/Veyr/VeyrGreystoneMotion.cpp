#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrGreystone.h"
#include "VeyrMotionMatcher.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"

// Quality goal E5 (2026-11-19): motion matching for Greystone's Ready locomotion, on his own Paragon jog set
// (Jog_<Fwd|Bwd|Left|Right>{,_Start,_Stop,_Pivot180,_Circle_Left,_Circle_Right}, Turn_<Left|Right>_<90|180>, Idle),
// baked into the fallback feature table by tools/unreal/greystone/bake_motion_features.py (--set source=jogset) and
// played by their DA_Greystone keys MM_<asset>. The capsule stays gameplay-authoritative (owner-fixed hitboxes): the
// matcher only picks what the body shows. Actions keep today's clip path. Off unless VeyrGreystone::MotionMatchEnabled().
//
// Each switch logs VEYR_MOTION_SWITCH (time, gate, clip, clip time, cost, capsule speed, input held) so the proof can
// measure response time offline (tools/unreal/greystone/motion_proof.py).
namespace
{
    constexpr float BlendSeconds=.12f; // cross-fade into a new match (the reference's inertial 0.10 s, our sampler fades)
}

bool AVeyrKnight::UpdateGreystoneMotionMatch(float DeltaSeconds)
{
    if(!ImportedPresentation||!CustomuseVisualDefinition||DeltaSeconds<=0.f||bGreystoneMotionFailed)return false;
    if(!GreystoneMotion)
    {
        GreystoneMotion=MakeShared<FVeyrMotionMatcher>();
        FString Error;
        const FString Table=FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir()/TEXT("Characters/Greystone/MotionMatching/veyr_motion_features.json"));
        if(!GreystoneMotion->Initialize(ImportedPresentation,TEXT("/Game/Characters/Greystone/MotionMatching"),Table,Error))
        {
            UE_LOG(LogTemp,Warning,TEXT("VEYR_MOTION_MATCHER_FAILED %s"),*Error);
            bGreystoneMotionFailed=true;GreystoneMotion.Reset();return false;
        }
        GreystoneMotionYaw=GetActorRotation().Yaw;
    }
    const FVector Intent(MoveIntent.X,MoveIntent.Y,0.f);
    const bool Held=Intent.SizeSquared()>.0025f;
    const float MaxSpeed=GetCharacterMovement()?GetCharacterMovement()->GetMaxSpeed():0.f;
    const FVector Desired=Held?Intent.GetClampedToMaxSize(1.f)*MaxSpeed:FVector::ZeroVector;
    // Facing: the target while locked on (the knight strafes), otherwise the input direction; kept on release.
    if(bLockedOn&&IsValid(Boss))GreystoneMotionYaw=(Boss->GetActorLocation()-GetActorLocation()).Rotation().Yaw;
    else if(Held)GreystoneMotionYaw=Intent.Rotation().Yaw;
    const FVeyrMotionChoice Choice=GreystoneMotion->Step(ImportedPresentation->GetAnimInstance(),GetActorLocation(),GetActorRotation().Yaw,
        Desired,GreystoneMotionYaw,Held,false,DeltaSeconds);
    if(Choice.bSwitched&&!Choice.FallbackClip.IsNone())
    {
        const bool Blend=!GreystoneMotionClip.IsNone()&&ImportedPresentation->bPoseEvaluated&&ImportedPresentation->BeginTransition();
        GreystoneMotionClip=Choice.FallbackClip;GreystoneMotionTime=Choice.Time;GreystoneMotionAlpha=Blend?0.f:1.f;++GreystoneMotionSwitches;
        const TSharedRef<FJsonObject> E=GreystoneMotion->Evidence();
        UE_LOG(LogTemp,Display,TEXT("VEYR_MOTION_SWITCH t=%.3f gate=%s clip=%s time=%.3f cost=%.3f speed=%.1f held=%d blend=%d"),
            GetWorld()?GetWorld()->GetTimeSeconds():0.f,*E->GetStringField(TEXT("gate")),*GreystoneMotionClip.ToString(),GreystoneMotionTime,
            Choice.Cost,GetPlanarSpeed(),Held?1:0,Blend?1:0);
    }
    else if(!GreystoneMotionClip.IsNone())GreystoneMotionTime+=DeltaSeconds;
    if(GreystoneMotionClip.IsNone())return false; // nothing matched yet: today's clip path shows this frame
    GreystoneMotionAlpha=FMath::Min(1.f,GreystoneMotionAlpha+DeltaSeconds/BlendSeconds);
    ImportedPresentation->SetRelativeRotation(CustomuseVisualDefinition->MeshRelativeTransform.GetRotation());
    bool Sampled=ImportedPresentation->SampleClipTimeBlended(GreystoneMotionClip,GreystoneMotionTime,GreystoneMotionAlpha);
    if(!Sampled)
    {
        UE_LOG(LogTemp,Warning,TEXT("VEYR_MOTION_MATCHER_FAILED sample %s: %s"),*GreystoneMotionClip.ToString(),*ImportedPresentation->LastError);
        bGreystoneMotionFailed=true;GreystoneMotionClip=NAME_None;return false;
    }
    // Keep the matcher's continuing time on the clip's own (looped) timeline.
    GreystoneMotion->AdvanceCurrent(ImportedPresentation->CurrentTrimmedSeconds);
    Sampled=UpdateLocomotionFootContacts(DeltaSeconds);
    GreystoneMotion->RecordShownPose(ImportedPresentation,DeltaSeconds);
    // Hand state to today's path so the next action starts its own transition from this pose.
    RequestedPresentationClip=PresentationTransitionClip=GreystoneMotionClip;LastLocomotionClip=NAME_None;
    bPresentationTransitionActive=false;
    PresentationLowerClip=PresentationTransitionLowerClip=RequestedLowerPresentationClip=NAME_None;
    bRequestedPresentationClipSampled=Sampled;bPresentationUsingFallback=!Sampled;PresentationPreviousActionElapsed=-1.f;
    bBlinkHidden=false;ImportedPresentation->SetVisibility(true,true);ImportedPresentation->SetHiddenInGame(false,true);
    SetPresentationDiagnostic(Sampled?FString():TEXT("Motion match foot pass failed: ")+ImportedPresentation->LastError);
    return true;
}
