#pragma once
#include "CoreMinimal.h"

class UWorld;

/** Phase C picture: one switch for the renderer features and the relit court.
 *  New look is the default; -VeyrLegacyRender brings back the build 16 renderer and lights. */
namespace VeyrLook
{
    /** -VeyrLegacyRender: Lumen/VSM off at runtime, manual exposure, no motion blur, old lights. */
    bool IsLegacy();
    /** New look and -VeyrNoLumenSplit absent: court instances drawn as components Lumen can cache. */
    bool SplitInstancesForLumen();
    /** Applies the runtime renderer cvars for the chosen look, once per process (idempotent). */
    void ApplyRenderer();
    /** -VeyrRenderTier=N (0 = full, 1..8 = cumulative fallback steps in C-notes order). */
    int32 RenderTier();
    /** Number of brazier lights allowed to cast shadows at the current tier (all at tier < 2). */
    int32 ShadowedFireBudget();
    /** Tells the renderer the view jumped (exposure snaps, no motion-blur or Lumen history smear). */
    void NotifyCameraCut(UWorld* World);
}
