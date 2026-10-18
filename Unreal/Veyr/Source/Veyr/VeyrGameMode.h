#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "VeyrGameMode.generated.h"
class AVeyrArena;
class AVeyrDragon;
class AVeyrKnight;
class AVeyrReplay;
class AVeyrAudio;
class AVeyrDragonEffects;

UCLASS()
class VEYR_API AVeyrGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AVeyrGameMode();
    virtual void StartPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    /** Starts the same input-only replay used by packaged validation in a fresh PIE world. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Validation")
    bool StartNativeValidation(const FString& Mode, const FString& EvidenceDirectory);
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrArena> Arena;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrReplay> Replay;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrAudio> Audio;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrDragonEffects> DragonEffects;
    UPROPERTY(BlueprintReadOnly) float EncounterSeconds=0;
    UPROPERTY(BlueprintReadOnly) float VictorySeconds=-1;
private:
    bool bPawnPositioned=false;
};
