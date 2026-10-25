#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrCombatTypes.h"
#include "VeyrAudio.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class UAudioComponent;
class USoundWaveProcedural;

/** Original, bounded combat feedback. Observes gameplay; never changes combat state. */
UCLASS()
class VEYR_API AVeyrAudio : public AActor
{
    GENERATED_BODY()
public:
    AVeyrAudio();
    /** Call once after the encounter's pawn and boss have been assigned. Safe to rebind. */
    void Initialize(AVeyrKnight* InKnight, AVeyrDragon* InDragon);
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Audio", meta=(ClampMin="0", ClampMax="1"))
    float MasterVolume = .65f;
    /** Submission evidence only: these do not prove audible output or acoustic acceptance. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 CuesStarted = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 CuesDropped = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 ActiveVoices = 0;

protected:
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    enum class ECue : uint8 { Swing, HeavySwing, Contact, Guard, Impact, Breath, Fire, Heal, Exposed, Death, Victory, Count };
    static constexpr int32 VoiceCount = 6;
    static constexpr int32 CueCount = static_cast<int32>(ECue::Count);
    static constexpr int32 SampleRate = 24000;

    UPROPERTY(Transient) TWeakObjectPtr<AVeyrKnight> Knight;
    UPROPERTY(Transient) TWeakObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY(Transient) TArray<TObjectPtr<UAudioComponent>> Voices;
    UPROPERTY(Transient) TArray<TObjectPtr<USoundWaveProcedural>> VoiceWaves;
    TArray<int16> Samples[CueCount];
    float Durations[CueCount] = {};
    double LastCueTimes[CueCount] = {};
    double VoiceEndTimes[VoiceCount] = {};
    int32 LastLight = 0, LastHeavy = 0, LastSwordContact = 0, LastHeadBonus = 0;
    int32 LastHitsTaken = 0, LastGuardedHits = 0, LastHeals = 0, LastCollapses = 0, LastFireAttacks = 0;
    EVeyrKnightAction LastSwingAction=EVeyrKnightAction::Ready;
    FName LastSwingClip=NAME_None;
    float LastSwingElapsed=0.f;
    TSet<int32> SwingWindowsPlayed;
    EVeyrDragonState LastDragonState = EVeyrDragonState::Idle;
    bool bWasAirborne = false, bInitialized = false, bTerminal = false, bBossDeathSeen = false;

    void BuildSamples();
    void PlayCue(ECue Cue, float Volume = 1.f);
    void StopVoices();
    void ExpireVoices();
    void SnapshotCounters();
};
