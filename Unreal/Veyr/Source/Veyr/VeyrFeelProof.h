#pragma once
#include "CoreMinimal.h"
#include "Templates/Function.h"

class AVeyrKnight;
class AVeyrDragon;
class FJsonObject;
class UWorld;

/**
 * Proof mode `feel` for quality-goal B4-B6 (2026-11-18), owned by AVeyrReplay. A short scripted sequence,
 * filmable in about 40 s: the dragon (rehearsal actor, deals no damage) walks, stomps, sweeps its tail,
 * flies and lands, then collapses with its head exposed; the knight walks in and lands light and heavy
 * blows on the head, and takes one scripted blow (labelled scripted in the evidence) during the tail sweep.
 * Drives input only; never moves actors.
 */
class FVeyrFeelProof
{
public:
    struct FHooks
    {
        TFunction<void(const FString&)> Shot;
        TFunction<void(bool,const FString&)> Finish;
    };
    static bool IsMode(const FString& Mode) { return Mode==TEXT("feel"); }
    bool Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,FHooks InHooks);
    /** Owns the knight's input for this tick. */
    void Drive(double Elapsed,float Dt);
    TSharedPtr<FJsonObject> Evidence() const;
    float DurationLimit() const { return 120.f; }

private:
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    FHooks Hooks;
    TArray<FName> Segments;
    int32 SegmentIndex=-1;
    double SegmentStart=0.0,RestUntil=0.0,FirstExposed=-1.0,LastPress=-100.0;
    bool bDone=false,bScriptedHitDone=false,bInSegment=false,bLegStrikeDone=false;
    int32 LegStrikeContacts=-1;double LegStrikeAt=-1.0;
    int32 PressIndex=0,SwordContactsAtStart=0,LastContactSerial=0;
    TArray<TSharedPtr<class FJsonValue>> Contacts;
    float MaxSegmentSeconds=0.f;
    TArray<TSharedPtr<class FJsonValue>> Timeline;
    FString FailReason;
    void Mark(double Elapsed,const FString& Name);
    void Finalize(double Elapsed);
};
