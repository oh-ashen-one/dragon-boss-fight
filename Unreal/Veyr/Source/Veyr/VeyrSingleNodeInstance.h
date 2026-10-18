#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "VeyrSingleNodeInstance.generated.h"

class UAnimSequence;

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
    void ClearTransitionSource();
    bool HasTransitionSource() const;
    FString GetExplicitEvaluationError() const;
    uint64 GetExplicitEvaluationSerial() const;
    bool SetExplicitLowerBody(UAnimSequence* Sequence, float SequenceSeconds, float Weight);
    void ClearExplicitLowerBody();
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
private:
    /** Keep the proxy's explicitly sampled asset alive without a second instance. */
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> ExplicitLowerSequence;
};
