#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class AVeyrDragon;
class AVeyrKnight;
class UWorld;

/** D3 (bigger dragon) windowless size checks, evidence only (-VeyrSizeMeter): wall and prop clearance of the drawn
 * body per state and move, attack reach and arena coverage per attack, knight hits per part standing and down, the
 * knocked-down head height, and the 8 intro shots' framing of the spawn pose. Changes no gameplay. */
struct FVeyrSizeMeter
{
    void Tick(UWorld* World, AVeyrDragon* Dragon, AVeyrKnight* Knight, float Dt);
    TSharedPtr<FJsonObject> ToJson() const;

private:
    struct FMoveStats
    {
        int32 Instances=0, KnightHits=0;
        float MaxReachCm=0.f, MaxCoveragePct=0.f, SumCoveragePct=0.f;
    };
    struct FPlace { float Seconds=0.f; int32 Frames=0; };
    bool bStarted=false, bIntroMeasured=false, bWasActive=false;
    float Clock=0.f, FloorZ=0.f;
    int32 Frames=0, OverlapChecks=0, OverlapFrames=0, ActiveMove=-1, LastHitsTaken=0;
    float LastDragonHealth=-1.f;
    // Clearance: signed distance from any drawn part to the fortress wall line (negative = through the wall line).
    float MinWallMarginCm=1.e9f;
    FString MinWallMarginWhere;
    TMap<FString,int32> OverlapByPlace;
    TMap<FString,int32> OverlapComponents;
    TMap<FString,float> MinMarginByPlace;
    FMoveStats Moves[6];
    TBitArray<> Coverage;
    TMap<FString,int32> HitsStanding, HitsDown;
    float HeadDownMinZ=1.e9f, HeadDownMaxZ=-1.e9f, HeadStandingZ=0.f, LegTopStandingZ=0.f;
    float BodyLengthCm=0.f, BodySpanCm=0.f, BodyHeightCm=0.f;
    float BrainSeed=0.f, BodyScale=0.f;
    bool bTwoHanded=false;
    TArray<TSharedPtr<FJsonValue>> IntroShots;
    int32 FlightsStarted=0;
    bool bWasAirborne=false;
    float MaxAirborneHeightCm=0.f;

    void MeasureIntro(UWorld* World, AVeyrDragon* Dragon);
    void MeasureBody(AVeyrDragon* Dragon);
    FString PlaceName(const AVeyrDragon* Dragon) const;
};
