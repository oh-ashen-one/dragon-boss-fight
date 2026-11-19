#pragma once
#include "CoreMinimal.h"

class UWorld;
class UMaterialInstanceDynamic;
class UPrimitiveComponent;

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
    /** -VeyrTune=key=value,key=value: tuning overrides for the relit court so one package serves several
     *  look rounds (keys in C-notes "Tune keys"); Default when the key is absent. Logged once per key. */
    float Tune(const TCHAR* Key,float Default);
    /** -VeyrNoMotionBlur: the new look without its camera motion blur (A/B for smeared trails and shakes). */
    bool MotionBlur();

    // Exposure-following unlit FX. Unlit sprites, the mesh flash and the ribbon were tuned under build 16's
    // manual exposure (about 0.83). Auto exposure can sit about 3 stops above that in a dark corner and 4
    // below it in the breath, so their emissive is scaled by (reference / current exposure)^lock.
    // Lock 1 holds them at their tuned screen brightness; it is 0.5 by default because a full lock feeds
    // back through the histogram (a brighter breath sprite meters the camera darker, which brightens the
    // sprite again) and runs to the exposure clamp; at 0.5 that loop converges.
    /** Game-view exposure scale read back from the renderer (0 until the first readback). */
    float LastExposure();
    float LastSceneLuminance();
    /** -VeyrFxExposureLock=0..1 (default 0.5); 0 under -VeyrLegacyRender or -VeyrNoFxExposureFollow. */
    float FxExposureLock();
    /** Multiplier for unlit FX emissive, clamped to [1/16, 16]; 1 when the lock is 0 or exposure unknown. */
    float FxExposureGain();
    /** Same as FxExposureGain() with an explicit lock (0..1) instead of the global one; 1 when following is off. */
    float FxExposureGainFor(float Lock);
    /** Registers one scalar of a dynamic material: it is set to Base * FxExposureGain() after each world tick. */
    void FollowExposure(UMaterialInstanceDynamic* Mid,FName Param,float Base,float Lock=-1.f);
    /** Unlit materials only: registers every scalar whose name reads as emissive strength
     *  (emiss, intens, bright, glow, hdr). Returns how many were registered. */
    int32 FollowExposureAuto(UMaterialInstanceDynamic* Mid,float Lock=-1.f);
    /** For a component whose materials are not ours (Paragon Cascade): each unlit slot becomes a dynamic
     *  material that follows exposure. Shared per source material through Cache. Returns slots wired. */
    int32 FollowExposureOnComponent(UPrimitiveComponent* Component,UObject* Outer,TMap<UMaterialInterface*,UMaterialInstanceDynamic*>& Cache);
}
