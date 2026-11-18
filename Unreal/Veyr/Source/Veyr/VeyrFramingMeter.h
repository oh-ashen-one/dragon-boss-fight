#pragma once
#include "CoreMinimal.h"

class AVeyrKnight;
class AVeyrDragon;
class FJsonObject;

/**
 * Phase D (2026-11-18): what the player's camera shows, measured every replay frame from the combat camera's own
 * pose, lens and viewport aspect (no renderer needed, so headless runs measure it too). Written to evidence.json
 * as `framing`; summarised by tools/unreal/playtest_suite.py.
 *   knightFullyInFrameShare  feet, top and both sides of the knight's capsule inside the screen
 *   headOrChestOnScreenShare the dragon's head or chest inside the screen
 *   knightMeanScreenHeightPct the knight's projected height, percent of the screen height
 *   strikeLimbVisibleShare   per dragon attack, the striking limb's contact point at its closest approach to the
 *                            knight during the active window, inside the screen
 *   cameraInsideBodyFrames   the camerahug check (boom shapes, bare body + 10 cm near plane)
 * Goal row D1: knight fully in frame >= 95 % of frames, striking limb visible at contact >= 90 % of strikes.
 */
class FVeyrFramingMeter
{
public:
    void Begin(AVeyrKnight* InKnight,AVeyrDragon* InDragon);
    void Sample(float DeltaSeconds);
    TSharedPtr<FJsonObject> Evidence() const;
    int32 Frames() const { return FrameCount; }
    float KnightFullyInFrameShare() const { return FrameCount?float(KnightFull)/FrameCount:0.f; }

private:
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    int32 FrameCount=0,KnightFull=0,KnightCenter=0,HeadOrChest=0,HeadOn=0,ChestOn=0,InsideBody=0,LockedFrames=0,LockedKnightFull=0;
    double KnightHeightSum=0.0; int32 KnightHeightFrames=0;
    TArray<float> KnightHeights;
    float SampledSeconds=0.f;
    struct FStrike { int32 Attack=-1; FName Limb; FName Move; float BestCm=TNumericLimits<float>::Max(); bool bVisible=false; FVector2D Screen=FVector2D::ZeroVector; float AtSeconds=0.f; };
    FStrike Current;
    TArray<FStrike> Strikes;
    void Commit();
    bool Project(const FVector& World,FVector2D& OutScreen) const;
    // Camera pose for this frame.
    FVector CamLoc=FVector::ZeroVector,CamF=FVector::ForwardVector,CamR=FVector::RightVector,CamU=FVector::UpVector;
    float TanH=1.f,TanV=.5625f;
    static bool OnScreen(const FVector2D& P){return P.X>=0.f&&P.X<=1.f&&P.Y>=0.f&&P.Y<=1.f;}
};
