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
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    /** Starts the same input-only replay used by packaged validation in a fresh PIE world. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Validation")
    bool StartNativeValidation(const FString& Mode, const FString& EvidenceDirectory);
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrArena> Arena;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrKnight> Knight;
    UPROPERTY() TObjectPtr<AVeyrReplay> Replay;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrAudio> Audio;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AVeyrDragonEffects> DragonEffects;
    UFUNCTION(BlueprintCallable, Category="Veyr|Menu") bool SetPauseMenuOpen(bool bOpen);
    UFUNCTION(BlueprintCallable, Category="Veyr|Settings") void SetMasterVolume(float Value);
    UFUNCTION(BlueprintCallable, Category="Veyr|Settings") void SetMusicVolume(float Value);
    UFUNCTION(BlueprintCallable, Category="Veyr|Settings") void SetEffectsVolume(float Value);
    UFUNCTION(BlueprintCallable, Category="Veyr|Settings") void SetMouseSensitivity(float Value);
    void SaveUserSettings();
    UPROPERTY(BlueprintReadOnly, Category="Veyr|Menu") bool bPauseMenuOpen=false;
    UPROPERTY(BlueprintReadOnly, Category="Veyr|Settings") float UserMasterVolume=.65f;
    UPROPERTY(BlueprintReadOnly, Category="Veyr|Settings") float UserMusicVolume=.55f;
    UPROPERTY(BlueprintReadOnly, Category="Veyr|Settings") float UserEffectsVolume=1.f;
    UPROPERTY(BlueprintReadOnly, Category="Veyr|Settings") float UserMouseSensitivity=1.f;
    UPROPERTY(BlueprintReadOnly) float EncounterSeconds=0;
    UPROPERTY(BlueprintReadOnly) float VictorySeconds=-1;
private:
    bool bPawnPositioned=false;
    FString MixCaptureDirectory,MixCaptureName;
    double MixCaptureStarted=0;
    float MixCaptureDuration=30.f;
    bool bMixCaptureFinished=false;
    void FinishMixCapture();
};
