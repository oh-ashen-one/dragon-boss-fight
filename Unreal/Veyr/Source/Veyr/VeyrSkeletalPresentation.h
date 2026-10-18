#pragma once

#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "VeyrVisualDefinition.h"
#include "VeyrSkeletalPresentation.generated.h"

/**
 * Explicitly sampled native presentation. The owning gameplay actor supplies
 * time/phase, then reads evaluated bone targets in the same game-thread call.
 * There is no autonomous animation clock, movement, notify or action completion.
 * Create/attach/register this component before SetVisualDefinition.
 */
UCLASS(ClassGroup=(Veyr), meta=(BlueprintSpawnableComponent))
class VEYR_API UVeyrSkeletalPresentation : public USkeletalMeshComponent
{
    GENERATED_BODY()

public:
    UVeyrSkeletalPresentation();

    /** Validates and applies a definition, then explicitly evaluates its reference pose.
     * Partial movesets are allowed only when bRequireCompleteMoveset is false;
     * attempting to sample an absent clip still fails. Never sets art acceptance.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SetVisualDefinition(UVeyrVisualDefinition* InDefinition, bool bRequireCompleteMoveset=false);

    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleReferencePose();

    /** Seconds relative to the clip's trimmed start. Nonloops clamp at the end;
     * loops wrap within the trim, including exactly duration -> start. Negative
     * and non-finite requests fail. Returns only after synchronous evaluation.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleClipTime(FName ClipName, float ElapsedSeconds);

    /** Normalized trimmed time: phase 0=start, 1=end for nonloops/start for loops.
     * Larger phases clamp/wrap using the same policy as SampleClipTime.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleClipPhase(FName ClipName, float Phase);

    /** Freeze the current successfully evaluated pose (including a partial
     * transition). Caller owns the next alpha ramp; this starts no clock.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool BeginTransition();

    /** Alpha 0 reproduces the frozen source exactly; 1 is the unblended target.
     * Alpha < 1 requires BeginTransition. Missing clips still fail at any alpha.
     * Plain SampleClipTime/Phase and reference-pose sampling cancel transitions.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleClipTimeBlended(FName ClipName, float ElapsedSeconds, float Alpha);

    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleClipPhaseBlended(FName ClipName, float Phase, float Alpha);

    /** Offset is applied in bone-local space: LocalOffset * BoneWorldTransform.
     * Requires a successful sample; missing/unevaluated bones fail with Identity
     * output, never a socket fallback to component origin. Check the bool result.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool GetBoneTargetWorldTransform(FName TargetName, FTransform& OutWorldTransform);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") TObjectPtr<UVeyrVisualDefinition> VisualDefinition;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") FName CurrentClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentSequenceSeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentTrimmedSeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentPhase=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bCurrentClipLoops=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bPoseEvaluated=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bTransitionSourceCaptured=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentTransitionAlpha=1.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") int32 SuccessfulPoseEvaluations=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") int32 FailedRequests=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") FString LastError;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") TArray<FString> DefinitionErrors;

private:
    bool Fail(const FString& Reason);
    bool CheckReady();
    bool ResolveClip(FName ClipName, const FVeyrVisualClip*& OutClip, float& OutEnd);
    bool EvaluatePoseSynchronously();
    bool SampleClipTimeInternal(FName ClipName, float ElapsedSeconds, float Alpha, bool bBlend);
};
