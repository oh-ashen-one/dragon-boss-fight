#pragma once
#include "CoreMinimal.h"

/**
 * B4-B6 (2026-11-18): one table for the weight layer: contact thresholds, shake by class, flinch, trail,
 * camera punches and the effect assets. Read once from Data/dragon/ground_fx.json beside moves.json; the
 * compiled defaults carry the same numbers and asset paths for packaged builds (Data/ is not staged). The
 * assets are loaded by path, so they appear in a package only when their folders are in DirectoriesToAlwaysCook.
 * Switches restore the old behaviour piece by piece; -VeyrLegacyFeel restores all of it.
 */
namespace VeyrFeelSwitches
{
    bool GroundContacts();   // -VeyrNoGroundContacts
    bool WeightShake();      // -VeyrLegacyWeightShake (contacts still detected)
    bool ContactDust();      // -VeyrNoContactDust
    bool SpineFlinch();      // -VeyrLegacyFlinch
    bool MeshFlash();        // -VeyrNoMeshFlash
    bool HitBursts();        // -VeyrLegacyHitBurst
    bool RibbonTrail();      // -VeyrLegacyTrail
    bool SlowTail();         // -VeyrNoSlowTail
    bool ZoomPunch();        // -VeyrNoZoomPunch
    bool HurtKick();         // -VeyrNoHurtKick
    // Bfeel (2026-11-19): the reference's measured camera numbers, each with its way back.
    bool ShakePattern();     // -VeyrLegacyShakePattern (the old 13/17/11 x class-rate cosine)
    bool HitShake();         // -VeyrLegacyHitShake (sword hits shake through the distance-faded Impact again)
    bool RefHitStop();       // -VeyrLegacyHitStop (55/95 ms at 0.05 again)
    bool LatePunch();        // -VeyrLegacyPunchOrder (punch before the arm's lens boost, which could open it back up)
    bool DownFlinch();       // -VeyrLegacyDownFlinch (only the small head nudge while the dragon is down)
}

enum class EVeyrFeelClass : uint8 { Footfall=0, Stomp=1, BodyFall=2, Landing=3, Count=4 };

struct FVeyrFeelTuning
{
    struct FPart { float TouchCm=5.f, LiftCm=12.f, MinSpeedMps=.3f; };
    struct FShake { float MinSpeed=.3f, FullSpeed=3.f, AmpMin=.08f, AmpMax=.4f, LifeMin=.16f, LifeMax=.28f, Bounce=0.f; };
    /** One effect tier: a soft path (Cascade or Niagara), its scale at 1x and how long a pooled component may run. */
    struct FEffect
    {
        FString System;
        float Scale=1.f, LifeSeconds=1.5f;
        // Fallback cards when System is empty or fails to load.
        int32 Cards=3; float CardSizeCm=60.f, CardLife=1.1f, CardOpacity=.32f, CardRiseCmS=35.f, CardSpreadCmS=70.f;
        int32 Chips=0; float ChipSizeCm=4.f, ChipSpeedCmS=320.f;
        /** Draw the cards as well as the asset (the asset alone is a hero-sized puff under a dragon foot). */
        bool bCardsWithAsset=false;
        /** Hit bursts: a puff of the dust cards of this tier at the hit point (-1 none), sized by SmokeScale. */
        int32 SmokeTier=-1; float SmokeScale=1.f;
    };

    // Contacts (cm and m/s at 1x; multiplied by BodyScale at run time)
    FPart Foot,Head{14.f,45.f,1.f},Neck{14.f,45.f,1.f},Body{14.f,45.f,1.f},Tail{10.f,35.f,1.2f},Wing{10.f,45.f,1.4f};
    float DustTierMaxSpeed[2]={1.2f,3.5f};
    float StompMinSpeed=1.f;
    float BodyCloudMinSpeed=2.f;      // a body fall at least this fast (m/s at 1x) throws the body cloud
    float LandingWindowSeconds=1.2f;
    float PeakTimeConstant=.08f;
    float MinEventInterval=.12f;

    // Camera shake by contact class: degrees by speed (normalised to 1x) and distance.
    FShake Shake[static_cast<int32>(EVeyrFeelClass::Count)]={
        // Tuned 2026-11-19 on the feel proof's image-shift numbers against the reference footage (2-4 % of the frame
        // height per 30 fps frame on a heavy blow): about 2 % of the height per degree at our lens.
        {.3f,3.f,.25f,.45f,.18f,.32f,0.f},    // Footfall: near the knight a visible tick, about 1 %
        {.8f,6.f,.50f,1.40f,.32f,.75f,4.f},   // Stomp / tail slam: near the knight about 3-4 % per 30 fps frame
        {1.f,8.f,.90f,1.40f,.45f,.80f,9.f},   // BodyFall
        {1.f,8.f,1.00f,1.50f,.50f,.85f,10.f}};// Landing
    float ShakeMaxDistanceCm=5000.f;   // x BodyScale
    float ShakeSizeGain=.35f;          // amplitude x (1 + gain x (BodyScale - 1))
    float ShakeMaxDegrees=3.5f;
    // The reference's waveform (WardenCombatFx::UpdateCamera): pitch A sin(23 2pi t), yaw .6A sin(17 2pi t), roll .4A sin(29 2pi t).
    float ShakeHz[3]={23.f,17.f,29.f},ShakeAxis[3]={1.f,.6f,.4f};
    // A sword blow on the dragon (the reference's BossHit is (.5 + 1.7 W) deg for .28 + .3 W s), no distance fade.
    // Ours: .6 + 1.1 W deg for .3 + .45 W s (heavy 1.7 deg, about 3.5 % of the height per 30 fps frame for ~6 frames).
    float HitShakeMin=.6f,HitShakeGain=1.1f,HitShakeLifeMin=.3f,HitShakeLifeGain=.45f;
    // The stop on a blow: the reference holds a light blow 65 ms, a heavy one 150 ms, at a clock of 0.03.
    float HitStopLight=.065f,HitStopHeavy=.15f,HitStopDilation=.03f;

    // Dragon flinch (degrees at the head, summed along the spine); the spring of the reference.
    float FlinchRockMin=5.f,FlinchRockMax=21.f,FlinchTwistMin=4.f,FlinchTwistMax=18.f,FlinchCapDegrees=34.f;
    float FlinchHeadPart=1.25f,FlinchNeckPart=1.1f,FlinchLegPart=.5f,FlinchBodyShare=.18f,FlinchTailShare=.35f;
    float FlinchSnapSeconds=.04f,FlinchHz=2.f,FlinchDamping=.45f,FlinchLifeSeconds=1.f;
    /** Down on the floor the same blow swings the head and neck sideways along the floor (no pitch into it), capped here.
     *  12 deg: at 30 the downed head swung out of the scripted knight's reach and one-hand fights ran 140 s instead of 93. */
    float FlinchDownCapDegrees=12.f;
    float FlashPeak=1.f,FlashPeakGain=1.2f,FlashRadiusCm=40.f,FlashRadiusGainCm=45.f,FlashFade=.07f,FlashLife=.3f;

    // Knight
    float TrailLife=.22f,TrailBaseFraction=.2f;
    // The reference eases a heavy blow back from 0.3 over .34 s; longer and deeper here so it reads at 60 fps.
    float SlowTailSeconds=.5f,SlowTailFrom=.25f;
    float PunchHeavy=.085f,PunchLight=.04f,PunchSeconds=.3f;
    float KickMin=4.f,KickGain=6.f,KickSeconds=.45f,HurtMin=.55f,HurtGain=.45f;

    // Effects: dust tiers 0..2 (feet), 3 body fall, 4 landing; hit bursts 0..2.
    FEffect Dust[5];
    FEffect Hit[3];
    FString DebrisMesh;
    // Fallback card look (the project's smoke and ember materials).
    FLinearColor DustTint=FLinearColor(.80f,.77f,.72f),ChipTint=FLinearColor(.07f,.065f,.06f),SparkTint=FLinearColor(1.f,.80f,.50f);
    float DustBrightness=.85f,SparkBrightness=4.f;

    FString SourceFile,Diagnostic;
    bool bLoadedFromFile=false;

    FVeyrFeelTuning();
    bool LoadFromFile(const FString& File);
    float ShakeDegrees(EVeyrFeelClass Class,float ScaledSpeed,float DistanceCm,float BodyScale,float& OutLife,float& OutBounce) const;
    float ClassStrength(EVeyrFeelClass Class,float ScaledSpeed) const;
    static float Smooth01(float X){X=FMath::Clamp(X,0.f,1.f);return X*X*(3.f-2.f*X);}
};

/** Lazily loaded shared table (Data/dragon/ground_fx.json or defaults). */
const FVeyrFeelTuning& VeyrFeelTuning();
