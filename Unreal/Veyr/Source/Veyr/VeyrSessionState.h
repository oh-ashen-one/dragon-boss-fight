#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "VeyrSessionState.generated.h"

/** Session-local presentation state. Retrying the encounter does not replay
 * the opening tour; a fresh application or PIE session starts with it again. */
UCLASS()
class VEYR_API UVeyrSessionState : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    UPROPERTY() bool bArenaIntroSeen=false;
};
