#pragma once
#include "CoreMinimal.h"
#include "VeyrCombatTypes.generated.h"

UENUM(BlueprintType)
enum class EVeyrKnightAction : uint8 { Ready, LightAttack, HeavyAttack, Roll, Guard, Heal, Stagger, Dead };
UENUM(BlueprintType)
enum class EVeyrDragonState : uint8 { Idle, Windup, Active, Recovery, Reposition, Buckle, Collapse, Exposed, Rise, Dead };
UENUM(BlueprintType)
enum class EVeyrDragonMove : uint8 { Fire, FlyAway, ClawSwipe, BackStomp, TailSmack, Bite };
