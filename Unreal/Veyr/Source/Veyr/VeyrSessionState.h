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
    /** Seconds of play the HUD controls box has been shown this session (it fades after 8 s). */
    UPROPERTY() float ControlsShownSeconds=0.f;
};
