#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "VeyrGameMode.generated.h"
class AVeyrArena;
class AVeyrDragon;
class AVeyrKnight;
class AVeyrReplay;
class AVeyrAudio;

UCLASS()
class VEYR_API AVeyrGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AVeyrGameMode();
    virtual void StartPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrArena> Arena;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrReplay> Replay;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrAudio> Audio;
    UPROPERTY(BlueprintReadOnly) float EncounterSeconds=0;
    UPROPERTY(BlueprintReadOnly) float VictorySeconds=-1;
private:
    bool bPawnPositioned=false;
};
