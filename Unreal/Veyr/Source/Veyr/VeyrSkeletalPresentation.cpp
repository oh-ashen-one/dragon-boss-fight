#include "VeyrSkeletalPresentation.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Engine/SkeletalMesh.h"

UVeyrSkeletalPresentation::UVeyrSkeletalPresentation()
{
    // The owning actor samples once at its chosen combat/movement time. Never
    // let the inherited mesh tick advance or evaluate a second animation clock.
    PrimaryComponentTick.bCanEverTick=false;
    PrimaryComponentTick.bStartWithTickEnabled=false;
    bEnableUpdateRateOptimizations=false;
    bSuppressNotifyEventDispatch=true;
    bPauseAnims=false;
    VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SetGenerateOverlapEvents(false);
    SetCanEverAffectNavigation(false);
}

bool UVeyrSkeletalPresentation::Fail(const FString& Reason)
{
    bPoseEvaluated=false;
    ++FailedRequests;
    if(LastError!=Reason)UE_LOG(LogTemp, Warning, TEXT("VEYR_SKELETAL_PRESENTATION_FAILED %s"),*Reason);
    LastError=Reason;
    return false;
}

bool UVeyrSkeletalPresentation::CheckReady()
{
    if(!IsInGameThread())return false; // Do not mutate component diagnostics from a worker.
    if(!IsRegistered())return Fail(TEXT("Component must be registered before explicit sampling"));
    if(!VisualDefinition||!VisualDefinition->SkeletalMesh)return Fail(TEXT("No applied skeletal visual definition"));
    if(GetSkeletalMeshAsset()!=VisualDefinition->SkeletalMesh)return Fail(TEXT("Component mesh differs from the applied visual definition"));
#if WITH_EDITOR
    if(GetSkeletalMeshAsset()->IsCompiling())return Fail(TEXT("Skeletal mesh compilation is still in progress"));
#endif
    if(GetAnimationMode()!=EAnimationMode::AnimationSingleNode||!GetSingleNodeInstance())
        return Fail(TEXT("Explicit sampling requires a native AnimSingleNodeInstance"));
    return true;
}

bool UVeyrSkeletalPresentation::SetVisualDefinition(UVeyrVisualDefinition* InDefinition, bool bRequireCompleteMoveset)
{
    if(!IsInGameThread())return false;
    bPoseEvaluated=false;
    if(!IsRegistered())return Fail(TEXT("Register the presentation component before setting its definition"));
    DefinitionErrors.Reset();
    if(!InDefinition)return Fail(TEXT("Visual definition is null"));
    DefinitionErrors=InDefinition->ValidateDefinition(bRequireCompleteMoveset);
    if(!DefinitionErrors.IsEmpty())return Fail(FString::Join(DefinitionErrors,TEXT("; ")));
#if WITH_EDITOR
    if(InDefinition->SkeletalMesh->IsCompiling())return Fail(TEXT("Skeletal mesh compilation is still in progress"));
#endif
    HandleExistingParallelEvaluationTask(true,true);
    VisualDefinition=InDefinition;
    SetSkeletalMesh(InDefinition->SkeletalMesh,true);
    SetRelativeTransform(InDefinition->MeshRelativeTransform);
    SetLeaderPoseComponent(nullptr);
    SetAnimationMode(EAnimationMode::AnimationSingleNode);
    SetDisablePostProcessBlueprint(true);
    SetEnableAnimation(true);
    SetSimulatePhysics(false);
    SetComponentTickEnabled(false);
    SetForcedLOD(1); // UE is one-based here: retain LOD0 target bones.
    SetPredictedLODLevel(0);
    return SampleReferencePose();
}

bool UVeyrSkeletalPresentation::EvaluatePoseSynchronously()
{
    if(!CheckReady())return false;
    bPoseEvaluated=false;
    // Join any prior task before changing/evaluating this pose. Passing nullptr
    // to RefreshBoneTransforms prevents a new parallel evaluation in UE5.8.
    HandleExistingParallelEvaluationTask(true,true);
    UAnimSingleNodeInstance* Instance=GetSingleNodeInstance();
    Instance->bUseMultiThreadedAnimationUpdate=false;
    Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
    Instance->SetPlaying(false);
    Instance->SetPlayRate(0.f);
    Instance->SetLooping(false); // Trimmed looping is resolved by this component.
    TickAnimation(0.f,false);
    RefreshBoneTransforms(nullptr);
    Instance->ConsumeExtractedRootMotion(1.f); // Never feed presentation root motion into gameplay.
    if(IsRunningParallelEvaluation()||GetNumComponentSpaceTransforms()!=GetSkeletalMeshAsset()->GetRefSkeleton().GetNum())
        return Fail(TEXT("Synchronous evaluation did not produce the complete component-space pose"));
    UpdateBounds();
    MarkRenderTransformDirty();
    MarkRenderDynamicDataDirty();
    bPoseEvaluated=true;
    ++SuccessfulPoseEvaluations;
    LastError.Reset();
    return true;
}

bool UVeyrSkeletalPresentation::SampleReferencePose()
{
    if(!CheckReady())return false;
    HandleExistingParallelEvaluationTask(true,true);
    GetSingleNodeInstance()->SetAnimationAsset(nullptr,false,0.f);
    SetForceRefPose(true);
    if(!EvaluatePoseSynchronously())return false;
    CurrentClip=NAME_None;
    CurrentSequenceSeconds=CurrentTrimmedSeconds=CurrentPhase=0.f;
    bCurrentClipLoops=false;
    return true;
}

bool UVeyrSkeletalPresentation::ResolveClip(FName ClipName, const FVeyrVisualClip*& OutClip, float& OutEnd)
{
    OutClip=nullptr;OutEnd=0.f;
    if(!CheckReady())return false;
    OutClip=VisualDefinition->Clips.Find(ClipName);
    if(!OutClip||!OutClip->Sequence)return Fail(TEXT("Requested clip is missing: ")+ClipName.ToString());
    UAnimSequence* Sequence=OutClip->Sequence;
    if(Sequence->GetSkeleton()!=GetSkeletalMeshAsset()->GetSkeleton())return Fail(TEXT("Clip skeleton mismatch: ")+ClipName.ToString());
    // Single-node additive playback is editor-only in the native implementation.
    if(Sequence->IsValidAdditive())return Fail(TEXT("Additive clips require a defined base pose and are unsupported here: ")+ClipName.ToString());
    // UAnimSequence::IsCompiling is protected in UE5.8. The public compressed-
    // data query is available in editor and cooked builds and uses the engine's
    // compressed-data read scope. Do not accept an editor-only raw-data fallback
    // as proof that this clip is ready for the packaged runtime.
    if(!Sequence->IsCompressedDataValid())return Fail(TEXT("Clip compressed runtime data is unavailable; finish import/compression: ")+ClipName.ToString());
    OutEnd=OutClip->EndSeconds<0.f?Sequence->GetPlayLength():OutClip->EndSeconds;
    if(!FMath::IsFinite(OutClip->StartSeconds)||!FMath::IsFinite(OutClip->EndSeconds)||!FMath::IsFinite(OutEnd)||
        OutClip->StartSeconds<0.f||OutEnd<=OutClip->StartSeconds||OutEnd>Sequence->GetPlayLength())
        return Fail(TEXT("Invalid trimmed clip interval: ")+ClipName.ToString());
    return true;
}

bool UVeyrSkeletalPresentation::SampleClipTime(FName ClipName, float ElapsedSeconds)
{
    if(!IsInGameThread())return false;
    if(!FMath::IsFinite(ElapsedSeconds)||ElapsedSeconds<0.f)return Fail(TEXT("Clip elapsed time must be finite and nonnegative"));
    const FVeyrVisualClip* Clip=nullptr;float End=0.f;
    if(!ResolveClip(ClipName,Clip,End))return false;
    const float Duration=End-Clip->StartSeconds;
    const float Trimmed=Clip->bLoop?FMath::Fmod(ElapsedSeconds,Duration):FMath::Min(ElapsedSeconds,Duration);
    const float SequenceTime=Clip->StartSeconds+Trimmed;
    HandleExistingParallelEvaluationTask(true,true);
    UAnimSingleNodeInstance* Instance=GetSingleNodeInstance();
    if(Instance->GetAnimationAsset()!=Clip->Sequence)Instance->SetAnimationAsset(Clip->Sequence,false,0.f);
    SetForceRefPose(false);
    Instance->SetPositionWithPreviousTime(SequenceTime,SequenceTime,false);
    if(!EvaluatePoseSynchronously())return false;
    if(!FMath::IsNearlyEqual(Instance->GetCurrentTime(),SequenceTime,.0001f))
        return Fail(TEXT("Animation time advanced unexpectedly during deterministic sampling"));
    CurrentClip=ClipName;
    CurrentSequenceSeconds=SequenceTime;
    CurrentTrimmedSeconds=Trimmed;
    CurrentPhase=Trimmed/Duration;
    bCurrentClipLoops=Clip->bLoop;
    return true;
}

bool UVeyrSkeletalPresentation::SampleClipPhase(FName ClipName, float Phase)
{
    if(!IsInGameThread())return false;
    if(!FMath::IsFinite(Phase)||Phase<0.f)return Fail(TEXT("Clip phase must be finite and nonnegative"));
    const FVeyrVisualClip* Clip=nullptr;float End=0.f;
    if(!ResolveClip(ClipName,Clip,End))return false;
    const float Normalized=Clip->bLoop?FMath::Fmod(Phase,1.f):FMath::Min(Phase,1.f);
    return SampleClipTime(ClipName,Normalized*(End-Clip->StartSeconds));
}

bool UVeyrSkeletalPresentation::GetBoneTargetWorldTransform(FName TargetName, FTransform& OutWorldTransform)
{
    OutWorldTransform=FTransform::Identity;
    if(!IsInGameThread())return false;
    if(!bPoseEvaluated)return Fail(TEXT("Bone target requested without a successful current pose sample: ")+TargetName.ToString());
    if(!CheckReady())return false;
    const FVeyrVisualBoneTarget* Target=VisualDefinition->BoneTargets.Find(TargetName);
    if(!Target)return Fail(TEXT("Bone target definition is missing: ")+TargetName.ToString());
    const int32 Index=GetBoneIndex(Target->BoneName);
    if(Index==INDEX_NONE||!GetComponentSpaceTransforms().IsValidIndex(Index)||!RequiredBones.Contains(static_cast<FBoneIndexType>(Index)))
        return Fail(TEXT("Target bone was not evaluated at LOD0: ")+Target->BoneName.ToString());
    if(Target->LocalOffset.ContainsNaN())return Fail(TEXT("Bone target offset is non-finite: ")+TargetName.ToString());
    const FTransform Result=Target->LocalOffset*GetBoneTransform(Index);
    if(Result.ContainsNaN())return Fail(TEXT("Bone target produced a non-finite world transform: ")+TargetName.ToString());
    OutWorldTransform=Result;
    LastError.Reset();
    return true;
}
