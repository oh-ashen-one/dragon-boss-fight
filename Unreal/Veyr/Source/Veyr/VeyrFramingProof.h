#pragma once
#include "CoreMinimal.h"
#include "Templates/Function.h"
#include "VeyrFramingMeter.h"

class AVeyrKnight;
class AVeyrDragon;
class FJsonObject;
class UWorld;

/**
 * Phase D (2026-11-18) `framing` replay: one fixed 60 s route so the same film can be made at -VeyrDragonScale=2,
 * 2.5 and 3: stand-off 0-8 s, circle at mid range 8-18, hug a front leg 18-26, under the belly 26-34, back off while it
 * strikes 34-42, sprint away and back 42-52, flight pass 52-60 (asks for the dragon's own flight move through
 * PlayDataMove when none has happened). Locked on; -VeyrFramingUnlocked runs it unlocked with a scripted
 * player-like look toward the dragon. Drives input only (plus the camp mode's health refill); never moves actors.
 * Per-phase framing numbers sit beside the whole-run `framing` block in evidence.json.
 */
class FVeyrFramingProof
{
public:
    struct FHooks
    {
        TFunction<void(const FString&)> Shot;
        TFunction<void(bool,const FString&)> Finish;
    };
    static bool IsMode(const FString& Mode) { return Mode==TEXT("framing"); }
    bool Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,FHooks InHooks);
    void Drive(double Elapsed,float Dt);
    TSharedPtr<FJsonObject> Evidence() const;
    float DurationLimit() const { return 120.f; }

private:
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    FHooks Hooks;
    bool bDone=false,bUnlocked=false,bFlightRequested=false,bFlightSeen=false;
    double Start=-1.0,LastShot=-100.0;
    float S=1.f;
    int32 Phase=-1,HealthRefills=0,FlightRequestAttempts=0,FlightsAtStart=0;
    FVector Away=FVector::ForwardVector;   // dragon -> knight at the start, re-read at each phase start
    float CircleStartYaw=0.f;
    int32 Leg=0;
    FVeyrFramingMeter Meters[7];
    static const TCHAR* PhaseName(int32 Index);
};
