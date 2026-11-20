#pragma once
#include "CoreMinimal.h"
#include "Templates/Function.h"

class AVeyrKnight;
class AVeyrDragon;
class AVeyrArena;
class FJsonObject;
class FJsonValue;
class UWorld;

/**
 * Proof mode `perimeter` (arena gaps, 2026-11-19), owned by AVeyrReplay. Windowless: the dragon is a
 * passive rehearsal actor and the knight's own capsule and movement component are driven into the court
 * boundary all the way round, at walking, sprint and roll speed, every 50 cm (walk every 100 cm) square on,
 * and at every boundary vertex from five approach angles. Each probe starts from a teleport inside the court
 * (test setup only), then drives input only. A probe escapes when the knight gets more than 250 cm behind the
 * boundary line (where the collision ring starts), below the floor, or falling. Run with -VeyrNoFallRecovery to test the walls themselves.
 */
class FVeyrPerimeterProof
{
public:
    struct FHooks { TFunction<void(bool,const FString&)> Finish; };
    static bool IsMode(const FString& Mode) { return Mode==TEXT("perimeter"); }
    bool Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,AVeyrArena* InArena,FHooks InHooks);
    void Drive(double Elapsed,float Dt);
    TSharedPtr<FJsonObject> Evidence() const;
    float DurationLimit() const { return LimitSeconds; }

private:
    struct FProbe { FVector2D Start,Dir,Target; int32 Speed=0; float Angle=0.f; int32 Edge=0; bool bVertex=false; };
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    TWeakObjectPtr<AVeyrArena> Arena;
    FHooks Hooks;
    TArray<FProbe> Probes;
    int32 Index=-1;
    double PhaseStart=0.0;
    bool bPushing=false,bDone=false;
    float MaxOutside=-1e9f,MinBottom=1e9f;
    float SpawnZ=125.f,LimitSeconds=600.f;
    int32 Escapes=0,IntoWall=0,Completed=0;
    float WorstOutside=-1e9f;
    TArray<TSharedPtr<FJsonValue>> EscapeList,DeepList;
    void StartProbe(double Elapsed);
    void EndProbe(double Elapsed);
};
