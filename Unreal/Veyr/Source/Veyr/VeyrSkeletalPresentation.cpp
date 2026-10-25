#include "VeyrSkeletalPresentation.h"
#include "VeyrSingleNodeInstance.h"
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
    bool KnownMesh=GetSkeletalMeshAsset()==VisualDefinition->SkeletalMesh;
    if(!KnownMesh)for(const auto& Entry:VisualDefinition->Clips)
        if(Entry.Value.MeshOverride==GetSkeletalMeshAsset()){KnownMesh=true;break;}
    if(!KnownMesh)return Fail(TEXT("Component mesh is not an approved definition variant"));
#if WITH_EDITOR
    if(GetSkeletalMeshAsset()->IsCompiling())return Fail(TEXT("Skeletal mesh compilation is still in progress"));
#endif
    if(!Cast<UVeyrSingleNodeInstance>(GetSingleNodeInstance()))
        return Fail(TEXT("Explicit sampling requires the Veyr native single-node instance"));
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
    // This setter selects AnimationBlueprint mode internally, but instantiates
    // our native SingleNode subclass. No animation blueprint asset is involved.
    SetAnimInstanceClass(UVeyrSingleNodeInstance::StaticClass());
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
    UVeyrSingleNodeInstance* Instance=CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance());
    Instance->bUseMultiThreadedAnimationUpdate=false;
    Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
    Instance->SetPlaying(false);
    Instance->SetPlayRate(0.f);
    Instance->SetLooping(false); // Trimmed looping is resolved by this component.
    const uint64 PreviousEvaluation=Instance->GetExplicitEvaluationSerial();
    TickAnimation(0.f,false);
    RefreshBoneTransforms(nullptr);
    Instance->ConsumeExtractedRootMotion(1.f); // Never feed presentation root motion into gameplay.
    if(IsRunningParallelEvaluation()||GetNumComponentSpaceTransforms()!=GetSkeletalMeshAsset()->GetRefSkeleton().GetNum())
        return Fail(TEXT("Synchronous evaluation did not produce the complete component-space pose"));
    if(Instance->GetExplicitEvaluationSerial()==PreviousEvaluation)return Fail(TEXT("Native proxy did not evaluate the requested pose"));
    const FString EvaluationError=Instance->GetExplicitEvaluationError();
    if(!EvaluationError.IsEmpty())return Fail(EvaluationError);
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
    UVeyrSingleNodeInstance* Instance=CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance());
    Instance->ClearTransitionSource();
    Instance->ClearExplicitLowerBody();
    Instance->ClearExplicitBoneRotations();
    CurrentLowerClip=NAME_None;CurrentLowerSequenceSeconds=CurrentLowerWeight=0.f;
    bTransitionSourceCaptured=false;CurrentTransitionAlpha=1.f;
    Instance->SetAnimationAsset(nullptr,false,0.f);
    // Native single-node evaluation with no asset produces the reference pose
    // and lets our proxy retain it as a valid future transition source.
    SetForceRefPose(false);
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
    USkeletalMesh* DesiredMesh=OutClip->MeshOverride?OutClip->MeshOverride.Get():VisualDefinition->SkeletalMesh.Get();
    if(DesiredMesh!=GetSkeletalMeshAsset())
    {
        const FReferenceSkeleton& Old=GetSkeletalMeshAsset()->GetRefSkeleton();
        const FReferenceSkeleton& Next=DesiredMesh->GetRefSkeleton();
        if(DesiredMesh->GetSkeleton()!=VisualDefinition->SkeletalMesh->GetSkeleton()||Old.GetNum()!=Next.GetNum())
            return Fail(TEXT("Approved mesh variant has an incompatible skeleton"));
        for(int32 I=0;I<Old.GetNum();++I)
            if(Old.GetBoneName(I)!=Next.GetBoneName(I)||Old.GetParentIndex(I)!=Next.GetParentIndex(I))
                return Fail(TEXT("Approved mesh variant changed the bone layout"));
#if WITH_EDITOR
        if(DesiredMesh->IsCompiling())return Fail(TEXT("Approved mesh variant compilation is pending"));
#endif
        // Compatible skin variants retain the native instance and frozen transition pose.
        SetSkeletalMesh(DesiredMesh,false);
        if(!CheckReady())return false;
    }
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
    return SampleClipTimeInternal(ClipName,ElapsedSeconds,1.f,false);
}

bool UVeyrSkeletalPresentation::SampleClipTimeBlended(FName ClipName, float ElapsedSeconds, float Alpha)
{
    return SampleClipTimeInternal(ClipName,ElapsedSeconds,Alpha,true);
}

bool UVeyrSkeletalPresentation::BeginTransition()
{
    if(!IsInGameThread())return false;
    if(!bPoseEvaluated)return Fail(TEXT("Transition requires a successfully sampled source pose"));
    if(!CheckReady())return false;
    HandleExistingParallelEvaluationTask(true,true);
    bTransitionSourceCaptured=CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance())->CaptureTransitionSource();
    if(!bTransitionSourceCaptured)return Fail(TEXT("Native proxy has no valid published source pose"));
    LastError.Reset();
    return true;
}

bool UVeyrSkeletalPresentation::SampleClipTimeInternal(FName ClipName, float ElapsedSeconds, float Alpha, bool bBlend, bool bKeepLowerLayer)
{
    if(!IsInGameThread())return false;
    if(!FMath::IsFinite(ElapsedSeconds)||ElapsedSeconds<0.f)return Fail(TEXT("Clip elapsed time must be finite and nonnegative"));
    if(!FMath::IsFinite(Alpha)||Alpha<0.f||Alpha>1.f)return Fail(TEXT("Transition alpha must be finite within [0,1]"));
    const FVeyrVisualClip* Clip=nullptr;float End=0.f;
    if(!ResolveClip(ClipName,Clip,End))return false;
    const float Duration=End-Clip->StartSeconds;
    const float Trimmed=Clip->bLoop?FMath::Fmod(ElapsedSeconds,Duration):FMath::Min(ElapsedSeconds,Duration);
    const float SequenceTime=Clip->StartSeconds+Trimmed;
    HandleExistingParallelEvaluationTask(true,true);
    UVeyrSingleNodeInstance* Instance=CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance());
    if(!bKeepLowerLayer)
    {
        Instance->ClearExplicitLowerBody();
        CurrentLowerClip=NAME_None;CurrentLowerSequenceSeconds=CurrentLowerWeight=0.f;
    }
    if(!bBlend)Instance->ClearTransitionSource();
    bTransitionSourceCaptured=Instance->HasTransitionSource();
    if(!Instance->SetExplicitTransitionAlpha(Alpha))return Fail(TEXT("Blended sample requires BeginTransition before alpha < 1"));
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
    CurrentTransitionAlpha=Alpha;
    return true;
}

bool UVeyrSkeletalPresentation::SampleLayeredClips(FName UpperClip, float UpperElapsedSeconds,
    FName LowerClip, float LowerElapsedSeconds, float LowerWeight, float TransitionAlpha)
{
    if(!IsInGameThread())return false;
    if(!FMath::IsFinite(UpperElapsedSeconds)||UpperElapsedSeconds<0.f||
        !FMath::IsFinite(LowerElapsedSeconds)||LowerElapsedSeconds<0.f)
        return Fail(TEXT("Layered clip times must be finite and nonnegative"));
    if(!FMath::IsFinite(LowerWeight)||LowerWeight<0.f||LowerWeight>1.f||
        !FMath::IsFinite(TransitionAlpha)||TransitionAlpha<0.f||TransitionAlpha>1.f)
        return Fail(TEXT("Layer and transition weights must be finite within [0,1]"));
    const FVeyrVisualClip* Upper=nullptr;float UpperEnd=0.f;
    const FVeyrVisualClip* Lower=nullptr;float LowerEnd=0.f;
    // Validate both inputs before installing a layer, including when either
    // weight is zero. No directional clip is silently substituted here.
    if(!ResolveClip(UpperClip,Upper,UpperEnd)||!ResolveClip(LowerClip,Lower,LowerEnd))return false;
    HandleExistingParallelEvaluationTask(true,true);
    UVeyrSingleNodeInstance* Instance=CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance());
    if(TransitionAlpha<1.f&&!Instance->HasTransitionSource())
        return Fail(TEXT("Layered transition requires BeginTransition before alpha < 1"));
    const float Duration=LowerEnd-Lower->StartSeconds;
    const float Trimmed=Lower->bLoop?FMath::Fmod(LowerElapsedSeconds,Duration):FMath::Min(LowerElapsedSeconds,Duration);
    const float SequenceTime=Lower->StartSeconds+Trimmed;
    if(!Instance->SetExplicitLowerBody(Lower->Sequence,SequenceTime,LowerWeight))
        return Fail(TEXT("Native lower-body sample configuration was rejected"));
    if(!SampleClipTimeInternal(UpperClip,UpperElapsedSeconds,TransitionAlpha,true,true))
    {
        Instance->ClearExplicitLowerBody();
        CurrentLowerClip=NAME_None;CurrentLowerSequenceSeconds=CurrentLowerWeight=0.f;
        return false;
    }
    CurrentLowerClip=LowerClip;CurrentLowerSequenceSeconds=SequenceTime;CurrentLowerWeight=LowerWeight;
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

bool UVeyrSkeletalPresentation::SampleClipPhaseBlended(FName ClipName, float Phase, float Alpha)
{
    if(!IsInGameThread())return false;
    if(!FMath::IsFinite(Phase)||Phase<0.f)return Fail(TEXT("Clip phase must be finite and nonnegative"));
    const FVeyrVisualClip* Clip=nullptr;float End=0.f;
    if(!ResolveClip(ClipName,Clip,End))return false;
    const float Normalized=Clip->bLoop?FMath::Fmod(Phase,1.f):FMath::Min(Phase,1.f);
    return SampleClipTimeBlended(ClipName,Normalized*(End-Clip->StartSeconds),Alpha);
}

TMap<FName,FTransform> UVeyrSkeletalPresentation::GetEvaluatedLocalPose()
{
    TMap<FName,FTransform> Result;
    if(!IsInGameThread())return Result;
    if(!bPoseEvaluated)
    {
        Fail(TEXT("Local pose requested without a successful current sample"));return Result;
    }
    if(!CheckReady())return Result;
    const TArray<FTransform> LocalTransforms=GetBoneSpaceTransforms();
    const FReferenceSkeleton& Reference=GetSkeletalMeshAsset()->GetRefSkeleton();
    if(LocalTransforms.Num()!=Reference.GetNum())
    {
        Fail(TEXT("Evaluated local pose does not contain the complete LOD0 bone layout"));return Result;
    }
    for(int32 Index=0;Index<LocalTransforms.Num();++Index)
    {
        if(LocalTransforms[Index].ContainsNaN())
        {
            Fail(TEXT("Evaluated local pose contains a non-finite transform"));return {};
        }
        Result.Add(Reference.GetBoneName(Index),LocalTransforms[Index]);
    }
    LastError.Reset();
    return Result;
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

bool UVeyrSkeletalPresentation::SetComponentSpaceBoneRotations(const TMap<FName,FRotator>& Rotations)
{
    if(!CheckReady())return false;
    HandleExistingParallelEvaluationTask(true,true);
    for(const auto& Entry:Rotations)
        if(GetBoneIndex(Entry.Key)==INDEX_NONE)return Fail(TEXT("Rotation modifier bone is missing: ")+Entry.Key.ToString());
    if(!CastChecked<UVeyrSingleNodeInstance>(GetSingleNodeInstance())->SetExplicitBoneRotations(Rotations))
        return Fail(TEXT("Rotation modifiers require at most four finite bones within 20 degrees per axis and 25 degrees total"));
    return true;
}
