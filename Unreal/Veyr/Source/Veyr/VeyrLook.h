#pragma once
#include "CoreMinimal.h"

class UWorld;

/** Phase C picture: one switch for the renderer features and the relit court.
 *  New look is the default; -VeyrLegacyRender brings back the build 16 renderer and lights. */
namespace VeyrLook
{
    /** -VeyrLegacyRender: Lumen/VSM off at runtime, manual exposure, no motion blur, old lights. */
    bool IsLegacy();
    /** New look, -VeyrNoLumenSplit absent and tier < 6: court instances drawn as components Lumen can cache. */
    bool SplitInstancesForLumen();
    /** Applies the runtime renderer cvars for the chosen look, once per process (idempotent). */
    void ApplyRenderer();
    /** -VeyrRenderTier=N (0 = full, 1..10 = cumulative fallback steps in C-notes order). */
    int32 RenderTier();
    /** Tier 0 only: the far breath light casts a (radius-capped) moving shadow. */
    bool BreathShadow();
    /** Tier < 2: the three floor-pool spots cast shadows. */
    bool FloorPoolShadows();
    /** Brazier lights allowed to cast shadows (all below tier 2; the 4 nearest the camera from tier 2). */
    int32 ShadowedFireBudget();
    /** Tells the renderer the view jumped (exposure snaps, no motion-blur or Lumen history smear). */
    void NotifyCameraCut(UWorld* World);
}
