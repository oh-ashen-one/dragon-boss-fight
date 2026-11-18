#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "VeyrSingleNodeInstance.generated.h"

class UAnimSequence;

/** F3 (2026-11-18): one leg of the dragon floor lock. Bones = upper, knee/elbow, end (wrist/hock), direct chain. */
struct FVeyrLegLock
{
    FName Bones[3];
    /** Paw bones parented to the knee beside the end bone; they keep their pose relative to the end bone. */
    FName Riders[2];
    /** Component-space move of the end bone, cm; applied with Weight. */
    FVector Delta=FVector::ZeroVector;
    float Weight=0.f;
    FVector LastBend=FVector(1,0,0);
};

/** Native single-node sampling with an explicit frozen-source pose transition.
 * No time advances here. Alpha and sequence time belong to the owning actor.
 */
UCLASS(Transient)
class VEYR_API UVeyrSingleNodeInstance : public UAnimSingleNodeInstance
{
    GENERATED_BODY()
public:
    bool CaptureTransitionSource();
    bool SetExplicitTransitionAlpha(float Alpha);
    void SetExplicitRootSpaceBlend(bool bEnabled);
    void ClearTransitionSource();
    bool HasTransitionSource() const;
    bool SetExplicitTransitionSequence(UAnimSequence* Sequence,float SequenceSeconds);
    FString GetExplicitEvaluationError() const;
    uint64 GetExplicitEvaluationSerial() const;
    bool SetExplicitLowerBody(UAnimSequence* Sequence, float SequenceSeconds, float Weight);
    void ClearExplicitLowerBody();
    /** Bounded component-space additive rotations, applied to the next explicit
     * destination pose before transition blending and publication. */
    bool SetExplicitBoneRotations(const TMap<FName,FRotator>& Rotations);
    void ClearExplicitBoneRotations();
    /** Two component-space ankle targets, L/R. Corrective IK only; never stretches limbs. */
    bool SetExplicitFootTargets(const TArray<FTransform>& Targets,const TArray<float>& Weights);
    void ClearExplicitFootTargets();
    /** A1 (2026-11-18): repair for clips mirrored by an older tools/dragon_refine/mirror_v2r_action.py.
     * When enabled, the destination pose keeps every link rigid: bones in RestBones take their whole
     * reference local transform (unpaired side bones the old tool mirrored as midline bones), every
     * other bone except TranslatingBones takes its reference local translation. Rotations are kept. */
    void SetExplicitMirrorRepair(bool bEnabled,const TArray<FName>& RestBones,const TArray<FName>& TranslatingBones);
    int32 GetMirrorRepairEvaluations() const;
    /** F2: apply Spine_0 fix, mirror repair (source's own flag), root offset and bone rotations to a moving source. */
    void SetExplicitTransitionCleanup(bool bEnabled,bool bSourceMirrorRepair);
    /** F4: planar Spine_0 offsets (component cm) removed from the destination and source poses. */
    void SetExplicitRootOffsets(const FVector& Destination,const FVector& Source);
    /** F3: at most four leg locks, applied after blending. */
    bool SetExplicitLegLocks(const TArray<FVeyrLegLock>& Locks);
    void ClearExplicitLegLocks();
    TArray<float> GetLegLockMissCm() const;
    FString GetLegLockError() const;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
private:
    /** Keep the proxy's explicitly sampled asset alive without a second instance. */
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> ExplicitLowerSequence;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> ExplicitTransitionSequence;
};
