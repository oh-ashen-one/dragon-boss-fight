#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "VeyrSingleNodeInstance.generated.h"

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
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
};
