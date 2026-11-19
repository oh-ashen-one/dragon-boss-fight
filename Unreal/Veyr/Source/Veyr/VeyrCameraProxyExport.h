#pragma once
#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "VeyrCameraProxyExport.generated.h"

/** Camera fourth pass: exports the drawn dragon skin (every mesh variant) for the offline proxy fit. Editor only. */
UCLASS()
class UVeyrCameraProxyExportCommandlet : public UCommandlet
{
    GENERATED_BODY()
public:
    UVeyrCameraProxyExportCommandlet();
#if WITH_EDITOR
    virtual int32 Main(const FString& Params) override;
#endif
};
