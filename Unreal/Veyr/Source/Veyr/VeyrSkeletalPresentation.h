#pragma once

#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "VeyrVisualDefinition.h"
#include "VeyrDragonGrounding.h"
struct FVeyrLegLock;
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

    /** Construction-time policy only. CPU pose probes remain registered for
     * animation/bone queries but never create a rendering-thread mesh object.
     * A visible Skin Cache request is applied before each mesh activation.
     */
    bool ConfigureRenderPolicy(bool bInCPUPoseOnly, bool bInRequestSkinCache);
    virtual bool ShouldCreateRenderState() const override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation") bool bPreferCanonicalMesh=false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation") bool bRootSpaceBlend=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") int32 MeshVariantSwitchCount=0;

    UFUNCTION(BlueprintPure, Category="Veyr|Presentation|RenderEvidence")
    bool HasPresentationRenderState() const { return IsRenderStateCreated(); }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") bool bCPUPoseOnly=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") bool bCPUPoseOnlyVerified=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") bool bSkinCacheRequested=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") int32 SkinCacheRequestedLODCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") TArray<int32> SkinCacheAllowedLODs;
    /** Eligibility observed at mesh activation, not proof of GPU allocation or raster technique. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") bool bSkinCacheAllRequestedLODsAllowed=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|RenderEvidence") FString RenderPolicyDiagnostic;

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

    /** Optional explicit moving source for a locomotion crossfade. Both clips
     * are sampled at caller-supplied times; no autonomous clock or notifies. */
    bool SampleClipTimeCrossfaded(FName ClipName,float ElapsedSeconds,float Alpha,FName SourceClip,float SourceElapsedSeconds);

    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleClipPhaseBlended(FName ClipName, float Phase, float Alpha);

    /** F2 (2026-11-18): blend from a still-running source. SourceSequenceSeconds is absolute in the source's
     * sequence (it may run past the source trim into the same action's next phase). The source gets the
     * destination's clean-up (Spine_0 fix, its own mirror repair, root offset, aim rotations). Alpha as above. */
    bool SampleClipTimeMovingSource(FName ClipName,float ElapsedSeconds,float Alpha,FName SourceClip,float SourceSequenceSeconds);
    /** F4: planar Spine_0 offsets removed from the next samples (component cm): destination, moving source. */
    void SetRootOffsets(const FVector& Destination,const FVector& Source);
    /** F3: re-evaluate the current explicit pose with up to four leg locks (cleared by ClearLegLocks only). */
    bool SetLegLocks(const TArray<FVeyrLegLock>& Locks);
    void ClearLegLocks();
    TArray<float> GetLegLockMissCm() const;
    FString GetLegLockError() const;

    /** Explicit lower-body overlay, then the frozen whole-pose transition.
     * Times are seconds relative to each clip's trimmed start. Hips and both
     * leg subtrees use LowerClip; upper local bones and curves use UpperClip.
     * Caller selects directional clips and owns both clocks and [0,1] weights.
     * Missing clips/mask fail even at weight zero. TransitionAlpha < 1 requires
     * BeginTransition. All ordinary sample APIs clear this lower-body layer.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool SampleLayeredClips(FName UpperClip, float UpperElapsedSeconds, FName LowerClip,
        float LowerElapsedSeconds, float LowerWeight, float TransitionAlpha);

    /** Configure at most sixteen bounded component-space additive bone rotations
     * for subsequent samples. Applied inside the native proxy before transition
     * blending/publication, so all rendered and queried targets use one pose.
     * Empty map clears; reference-pose sampling also clears. No time advances. */
    bool SetComponentSpaceBoneRotations(const TMap<FName,FRotator>& Rotations);
    /** Re-evaluate the current explicit pose with bounded corrective foot targets. */
    bool SetComponentSpaceFootTargets(const TArray<FTransform>& Targets,const TArray<float>& Weights);
    void ClearFootTargets();
    /** E (Greystone): persistent bone pins (shield on the back, shield away from the face). Kept for every later
     * sample until changed; does not re-evaluate. Returns false (with LastError) for missing bones. */
    bool SetBonePins(const TArray<struct FVeyrBonePin>& Pins);
    void ClearBonePins();

    /** Offset is applied in bone-local space: LocalOffset * BoneWorldTransform.
     * Requires a successful sample; missing/unevaluated bones fail with Identity
     * output, never a socket fallback to component origin. Check the bool result.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    bool GetBoneTargetWorldTransform(FName TargetName, FTransform& OutWorldTransform);

    /** Copy of the actual evaluated bone-local transforms, keyed by mesh bone
     * name. Empty with a diagnostic unless a complete current sample exists.
     * Does not evaluate, advance time, or reconstruct transforms from targets.
     */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    TMap<FName,FTransform> GetEvaluatedLocalPose();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") TObjectPtr<UVeyrVisualDefinition> VisualDefinition;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") FName CurrentClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentSequenceSeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentTrimmedSeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentPhase=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bCurrentClipLoops=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bPoseEvaluated=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") bool bTransitionSourceCaptured=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentTransitionAlpha=1.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") FName CurrentLowerClip=NAME_None;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentLowerSequenceSeconds=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") float CurrentLowerWeight=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") int32 SuccessfulPoseEvaluations=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") int32 FailedRequests=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") FString LastError;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation") TArray<FString> DefinitionErrors;

    // ---- A1 (2026-11-18): mirrored-clip repair. -VeyrLegacyMirrorToe restores the old pose. ----
    /** Sequences whose name contains this tag were written by tools/dragon_refine/mirror_v2r_action.py. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Mirror") FString MirroredSequenceTag=TEXT("_mirror");
    /** Unpaired side bones the old mirror tool treated as midline bones: take their rest local pose. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Mirror") TArray<FName> MirroredClipRestBones;
    /** Bones allowed to translate in mirrored clips; every other link keeps its rest length. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Mirror") TArray<FName> MirroredClipTranslatingBones;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Mirror") bool bRepairMirroredClips=true;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Mirror") bool bCurrentClipMirrorRepaired=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Mirror") int32 MirrorRepairSamples=0;
    /** Largest change of a rigid link's length against the reference pose, in world cm (current pose). */
    float MeasureMaxLinkStretchCm(FName& OutBone);

    // ---- A3 (2026-11-18): sole heights and grounding. -VeyrNoDragonGrounding restores the old height. ----
    /** Measure the four feet's lowest sole points against the floor under them (current pose). */
    bool MeasureSoles(FVeyrSoleSample& Out);
    /** One eased vertical offset of this whole component (never a bone); see VeyrDragonGrounding.h.
     * Safe to call several times per frame: easing advances with world time only. */
    void UpdateGrounding(EVeyrGroundingMode Mode);
    /** Same rule with an explicit time step (proof sweeps on a pose probe). */
    void StepGrounding(EVeyrGroundingMode Mode,float DeltaSeconds);
    void ResetGrounding();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") bool bGroundingEnabled=true;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") float GroundingOffsetCm=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") float GroundingTargetCm=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") int32 GroundingUpdates=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") FString GroundingDiagnostic;
    /** World cm at actor scale 1; multiplied by the actor's scale. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingMaxDropCm=75.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingDropRate=6.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingReleaseRate=3.f;
    /** Ground mode carries the support sole's motion through, eases the rest (rate 20, cap 300 cm/s x scale), and also raises a
     * sunk body (bounded by GroundingMaxDropCm). -VeyrGroundingLowerOnly restores the first rule: lower only,
     * eased at GroundingDropRate. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingTrackRate=20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingMaxSpeedCm=300.f;
    /** A target change faster than this (cm/s x scale) is a hard cut: eased, not carried through. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Veyr|Presentation|Grounding") float GroundingCutSpeedCm=1500.f;
    float LastGroundTargetCm=0.f;bool bGroundTargetValid=false;EVeyrGroundingMode LastGroundingModeForTarget=EVeyrGroundingMode::Release;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|Presentation|Grounding") bool bGroundingLowerOnly=false;
    EVeyrGroundingMode LastGroundingMode=EVeyrGroundingMode::Release;
    FVeyrSoleSample LastSoleSample;
    const FVeyrSoleModel& GetSoleModel() const { return SoleModel; }

private:
    FVeyrSoleModel SoleModel;
    FVector GroundingBaseLocation=FVector::ZeroVector;
    double LastGroundingWorldSeconds=-1.0;
    bool ApplyMeshRenderPolicy(USkeletalMesh* Mesh);
    bool RefreshRenderPolicyEvidence();
    bool Fail(const FString& Reason);
    bool CheckReady();
    bool ResolveClip(FName ClipName, const FVeyrVisualClip*& OutClip, float& OutEnd);
    bool EvaluatePoseSynchronously();
    bool SampleClipTimeInternal(FName ClipName, float ElapsedSeconds, float Alpha, bool bBlend, bool bKeepLowerLayer=false);
};
