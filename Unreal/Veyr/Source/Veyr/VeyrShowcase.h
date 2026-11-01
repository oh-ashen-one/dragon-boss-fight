#pragma once
#include "CoreMinimal.h"

class AVeyrDragon;
class AVeyrKnight;
class ACameraActor;
class FJsonObject;
class UWorld;

/** Non-combat rehearsal of production move/state playback, with explicit coverage. */
class FVeyrShowcase
{
public:
    struct FHooks
    {
        TFunction<void(const FString&)> Event;
        TFunction<void(bool,const FString&)> Finish;
    };
    bool Begin(UWorld* World,AVeyrKnight* Knight,AVeyrDragon* Dragon,bool PlayerCamera,const FHooks& Hooks);
    void Tick(float DeltaSeconds,float Elapsed);
    void End();
    TSharedPtr<FJsonObject> Evidence() const;
private:
    struct FStep {FName Name;TArray<FName> Clips;TArray<FString> States;};
    struct FSeen {int32 Frames=0,FramedFrames=0;float Min=1.f,Max=0.f;};
    TWeakObjectPtr<AVeyrKnight> Knight;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    TWeakObjectPtr<ACameraActor> Camera;
    FHooks Hooks;
    TArray<FStep> Steps;
    TMap<FName,FSeen> Seen;
    TSet<FString> States;
    TArray<TSharedPtr<class FJsonValue>> Chapters;
    int32 StepIndex=-1,FlightFireFrames=0;
    int32 FrustumMissFrames=0,ObstructedFrames=0;
    float StepStarted=0,RestUntil=0,MinimumCornersVisible=1.f;
    bool bResting=true,bDone=false,bPlayerCamera=false,bWasHidden=false,bHadCollision=true;
    bool bControlsTaken=false;
    uint8 SavedMovementMode=0,SavedCustomMovementMode=0;
    FVector ShotFocus=FVector::ZeroVector;
    FString CameraDiagnostic;
    bool BeginStep(float Elapsed);
    void FrameShot();
    void ObserveFrame();
};
