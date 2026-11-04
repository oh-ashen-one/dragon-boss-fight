#pragma once
#include "CoreMinimal.h"
class ACameraActor;

/** Owner-approved fortress/mural tour (2026-11-03). Shared by production intro
 * and architectural inspection so shot order, framing and movement stay intact. */
namespace VeyrArenaTour
{
    int32 ShotCount();
    float ShotSeconds();
    float Duration();
    const TCHAR* ShotName(int32 Index);
    int32 Apply(ACameraActor* Camera,float Seconds);
}
