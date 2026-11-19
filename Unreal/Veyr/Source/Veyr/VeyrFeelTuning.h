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
        {.3f,3.f,.08f,.40f,.16f,.28f,0.f},    // Footfall: felt, never in the way of aiming
        {.8f,6.f,.60f,1.80f,.30f,.55f,4.f},   // Stomp / tail slam
        {1.f,8.f,1.20f,2.80f,.45f,.80f,9.f},  // BodyFall
        {1.f,8.f,1.40f,3.00f,.50f,.85f,10.f}};// Landing
    float ShakeMaxDistanceCm=5000.f;   // x BodyScale
    float ShakeSizeGain=.35f;          // amplitude x (1 + gain x (BodyScale - 1))
    float ShakeMaxDegrees=3.5f;

    // Dragon flinch (degrees at the head, summed along the spine); the spring of the reference.
    float FlinchRockMin=5.f,FlinchRockMax=21.f,FlinchTwistMin=4.f,FlinchTwistMax=18.f,FlinchCapDegrees=34.f;
    float FlinchHeadPart=1.25f,FlinchNeckPart=1.1f,FlinchLegPart=.5f,FlinchBodyShare=.18f,FlinchTailShare=.35f;
    float FlinchSnapSeconds=.04f,FlinchHz=2.f,FlinchDamping=.45f,FlinchLifeSeconds=1.f;
    float FlashPeak=1.f,FlashPeakGain=1.2f,FlashRadiusCm=40.f,FlashRadiusGainCm=45.f,FlashFade=.07f,FlashLife=.3f;

    // Knight
    float TrailLife=.22f,TrailBaseFraction=.2f;
    float SlowTailSeconds=.32f,SlowTailFrom=.3f;
    float PunchHeavy=.085f,PunchLight=.0f,PunchSeconds=.3f;
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
