#include "VeyrAudio.h"
#include "VeyrKnight.h"
#include "VeyrVisualDefinition.h"
#include "VeyrDragon.h"
#include "Components/AudioComponent.h"
#include "Components/SceneComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "Engine/World.h"
#include <cmath>

namespace
{
    constexpr double Tau = 6.283185307179586;
    double Tone(double Frequency, double T) { return std::sin(Tau * Frequency * T); }
    double Decay(double T, double Rate) { return std::exp(-T * Rate); }
    struct FOriginalNoise
    {
        uint32 Seed = 0xB7471C53u;
        double Low = 0, Mid = 0, Phase = 0;
        double Next()
        {
            Seed ^= Seed << 13; Seed ^= Seed >> 17; Seed ^= Seed << 5;
            return double(Seed) / 2147483648.0 - 1.0;
        }
    };
}

AVeyrAudio::AVeyrAudio()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = false;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("AudioRoot")));
    for (int32 I = 0; I < VoiceCount; ++I)
    {
        UAudioComponent* Voice = CreateDefaultSubobject<UAudioComponent>(*FString::Printf(TEXT("CombatVoice%d"), I));
        Voice->SetupAttachment(GetRootComponent());
        Voice->bAutoActivate = false;
        Voice->bAutoDestroy = false;
        Voice->bStopWhenOwnerDestroyed = true;
        Voice->bAllowSpatialization = false;
        Voice->bIsUISound = false; // Obey game pause; no sound leaking into a paused/restarted encounter.
        Voices.Add(Voice);
    }
    VoiceWaves.SetNum(VoiceCount);
}

void AVeyrAudio::Initialize(AVeyrKnight* InKnight, AVeyrDragon* InDragon)
{
    StopVoices();
    if (Knight.IsValid()) RemoveTickPrerequisiteActor(Knight.Get());
    if (Dragon.IsValid()) RemoveTickPrerequisiteActor(Dragon.Get());
    Knight = InKnight; Dragon = InDragon;
    bInitialized = IsValid(InKnight) && IsValid(InDragon) && GetNetMode() != NM_DedicatedServer;
    SetActorTickEnabled(bInitialized);
    if (!bInitialized) return;
    AddTickPrerequisiteActor(InKnight);
    AddTickPrerequisiteActor(InDragon);
    if (Samples[0].IsEmpty()) BuildSamples();
    for (double& Time : LastCueTimes) Time = -100.0;
    bTerminal = InKnight->IsDead() || InDragon->IsDead();
    bBossDeathSeen = false;
    CuesStarted = CuesDropped = 0;
    SnapshotCounters(); // Binding mid-encounter must not replay historical events.
}

void AVeyrAudio::SnapshotCounters()
{
    const AVeyrKnight* K = Knight.Get();
    const AVeyrDragon* D = Dragon.Get();
    if (!K || !D) return;
    LastLight = K->LightAttacks; LastHeavy = K->HeavyAttacks;
    LastHitsTaken = K->HitsTaken; LastGuardedHits = K->GuardedHits; LastHeals = K->SuccessfulHeals;
    LastSwordContact = D->GetSwordContactCount(); LastHeadBonus = D->GetHeadBonusHitCount();
    LastCollapses = D->GetCollapseCount(); LastFireAttacks = D->GetAttackCount(EVeyrDragonMove::Fire);
    LastDragonState = D->State; bWasAirborne = D->IsAirborne();
}

void AVeyrAudio::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    ExpireVoices();
    if (!bInitialized || bTerminal) return;
    const AVeyrKnight* K = Knight.Get();
    const AVeyrDragon* D = Dragon.Get();
    if (!K || !D)
    {
        StopVoices(); bInitialized = false; SetActorTickEnabled(false); return;
    }
    if (K->IsDead())
    {
        StopVoices(); PlayCue(ECue::Death); bTerminal = true; return;
    }
    if (D->IsDead())
    {
        if (!bBossDeathSeen) { StopVoices(); PlayCue(ECue::Impact); bBossDeathSeen = true; }
        // Match the dragon's settled death rather than declaring victory on a contact transient.
        if (D->GetStateElapsed() >= D->GetStateDuration()) { PlayCue(ECue::Victory); bTerminal = true; }
        return;
    }

    const bool SwordAction=K->Action==EVeyrKnightAction::LightAttack||K->Action==EVeyrKnightAction::HeavyAttack||
        K->Action==EVeyrKnightAction::Combo||K->Action==EVeyrKnightAction::RollAttack;
    if(K->Action!=LastSwingAction||K->RequestedPresentationClip!=LastSwingClip||K->GetActionElapsed()<LastSwingElapsed)
        SwingWindowsPlayed.Reset();
    const FVeyrVisualClip* Swing=K->CustomuseVisualDefinition?K->CustomuseVisualDefinition->Clips.Find(K->RequestedPresentationClip):nullptr;
    if(SwordAction&&Swing&&!Swing->DamageWindows.IsEmpty())
    {
        const float Rate=FMath::Max(.1f,Swing->GameplayPlayRate);
        for(int32 I=0;I<Swing->DamageWindows.Num();++I)
        {
            const bool Heavy=K->Action==EVeyrKnightAction::HeavyAttack||(K->Action==EVeyrKnightAction::Combo&&I==2);
            const float CueAt=FMath::Max(0.f,static_cast<float>(Swing->DamageWindows[I].X)/Rate-(Heavy?.35f:.13f));
            if(K->GetActionElapsed()>=CueAt&&!SwingWindowsPlayed.Contains(I))
            {PlayCue(Heavy?ECue::HeavySwing:ECue::Swing);SwingWindowsPlayed.Add(I);}
        }
    }
    else if(!Swing)
    {
        if(K->HeavyAttacks>LastHeavy)PlayCue(ECue::HeavySwing);
        else if(K->LightAttacks>LastLight)PlayCue(ECue::Swing);
    }
    LastSwingAction=K->Action;LastSwingClip=K->RequestedPresentationClip;LastSwingElapsed=K->GetActionElapsed();
    if (D->GetSwordContactCount() > LastSwordContact)
        PlayCue(ECue::Contact, D->GetHeadBonusHitCount() > LastHeadBonus ? 1.f : .8f);
    if (K->GuardedHits > LastGuardedHits) PlayCue(ECue::Guard);
    else if (K->HitsTaken > LastHitsTaken) PlayCue(ECue::Contact, .9f);
    if (K->SuccessfulHeals > LastHeals) PlayCue(ECue::Heal);
    if (D->GetCollapseCount() > LastCollapses) PlayCue(ECue::Impact, .7f);
    if (D->GetAttackCount(EVeyrDragonMove::Fire) > LastFireAttacks) PlayCue(ECue::Breath);
    if (bWasAirborne && !D->IsAirborne()) PlayCue(ECue::Impact);
    if (D->State != LastDragonState)
    {
        if (D->State == EVeyrDragonState::Exposed) { PlayCue(ECue::Impact); PlayCue(ECue::Exposed); }
        else if (D->State == EVeyrDragonState::Active)
        {
            if (D->Move == EVeyrDragonMove::Fire) PlayCue(ECue::Fire);
            else if (D->Move == EVeyrDragonMove::BackStomp) PlayCue(ECue::Impact);
            else if (D->Move != EVeyrDragonMove::FlyAway) PlayCue(ECue::HeavySwing, .75f);
        }
    }
    SnapshotCounters();
}

void AVeyrAudio::PlayCue(ECue Cue, float Volume)
{
    if (!GetWorld() || MasterVolume <= 0.f || !FMath::IsFinite(MasterVolume)) return;
    const int32 Index = static_cast<int32>(Cue);
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now - LastCueTimes[Index] < .06 || Samples[Index].IsEmpty()) return;
    int32 Slot = INDEX_NONE;
    for (int32 I = 0; I < VoiceCount; ++I)
        if (VoiceEndTimes[I] <= 0) { Slot = I; break; }
    if (Slot == INDEX_NONE) { ++CuesDropped; return; } // Never allocate unlimited audio voices.
    UAudioComponent* Voice = Voices[Slot];
    if (!IsValid(Voice)) return;
    // A procedural FIFO is single-consumer. Each play owns a separate wave so overlapping
    // impacts cannot drain one another's PCM or race a ResetAudio on the render thread.
    USoundWaveProcedural* Wave = NewObject<USoundWaveProcedural>(this);
    Wave->SetSampleRate(SampleRate);
    Wave->NumChannels = 1;
    Wave->Duration = Durations[Index];
    Wave->bLooping = false;
    Wave->SoundGroup = SOUNDGROUP_Effects;
    Wave->QueueAudio(reinterpret_cast<const uint8*>(Samples[Index].GetData()), Samples[Index].Num() * sizeof(int16));
    VoiceWaves[Slot] = Wave;
    Voice->SetSound(Wave);
    Voice->SetVolumeMultiplier(.24f * FMath::Clamp(MasterVolume, 0.f, 1.f) * FMath::Clamp(Volume, 0.f, 1.f));
    Voice->Play();
    // Procedural FIFO underflow pads silence; explicitly stop instead of relying on EOF.
    VoiceEndTimes[Slot] = Now + Durations[Index] + .15;
    LastCueTimes[Index] = Now;
    ++CuesStarted; ++ActiveVoices;
}

void AVeyrAudio::ExpireVoices()
{
    if (!GetWorld()) return;
    const double Now = GetWorld()->GetTimeSeconds();
    for (int32 I = 0; I < VoiceCount; ++I)
    {
        if (VoiceEndTimes[I] <= 0 || Now < VoiceEndTimes[I]) continue;
        if (IsValid(Voices[I])) { Voices[I]->Stop(); Voices[I]->SetSound(nullptr); }
        VoiceWaves[I] = nullptr; VoiceEndTimes[I] = 0; ActiveVoices = FMath::Max(0, ActiveVoices - 1);
    }
}

void AVeyrAudio::StopVoices()
{
    for (int32 I = 0; I < VoiceCount; ++I)
    {
        if (Voices.IsValidIndex(I) && IsValid(Voices[I])) { Voices[I]->Stop(); Voices[I]->SetSound(nullptr); }
        if (VoiceWaves.IsValidIndex(I)) VoiceWaves[I] = nullptr;
        VoiceEndTimes[I] = 0;
    }
    ActiveVoices = 0;
}

void AVeyrAudio::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bInitialized = false;
    StopVoices();
    if (Knight.IsValid()) RemoveTickPrerequisiteActor(Knight.Get());
    if (Dragon.IsValid()) RemoveTickPrerequisiteActor(Dragon.Get());
    Knight.Reset(); Dragon.Reset();
    Super::EndPlay(EndPlayReason);
}

void AVeyrAudio::BuildSamples()
{
    // Original oscillator/noise synthesis, adapted from this project's original CombatAudio.cs.
    // No recordings, model services, files, global random state, audio-thread callbacks or loops.
    const float Lengths[CueCount] = {.32f, .55f, .48f, .38f, 1.15f, 1.45f, 2.1f, 1.2f, .65f, 1.6f, 2.2f};
    for (int32 C = 0; C < CueCount; ++C)
    {
        const ECue Cue = static_cast<ECue>(C);
        Durations[C] = Lengths[C];
        const int32 Count = FMath::RoundToInt(Lengths[C] * SampleRate);
        TArray<double> Raw; Raw.SetNumUninitialized(Count);
        FOriginalNoise N;
        double Peak = .001;
        for (int32 I = 0; I < Count; ++I)
        {
            const double T = double(I) / SampleRate;
            const double Noise = N.Next();
            N.Low += .035 * (Noise - N.Low); N.Mid += .25 * (Noise - N.Mid);
            double V = 0;
            switch (Cue)
            {
                case ECue::Swing:
                case ECue::HeavySwing:
                {
                    const double Center = Cue == ECue::HeavySwing ? .35 : .13;
                    const double Width = Cue == ECue::HeavySwing ? .11 : .065;
                    const double X = (T - Center) / Width;
                    V = (N.Mid - N.Low) * std::exp(-X * X) * 1.7 + Tone(1741, T) * .035 * Decay(T, 14);
                    break;
                }
                case ECue::Contact:
                    V = std::sin(Tau * (48*T + 4.5*(1-Decay(T,20)))) * Decay(T,10) * .63
                      + (Noise-N.Mid)*Decay(T,100)*.5 + N.Low*Decay(T,8)*.7 + Tone(851,T)*Decay(T,25)*.06;
                    break;
                case ECue::Guard:
                    V = (Tone(977,T)+.45*Tone(1543,T)+.2*Tone(2311,T))*Decay(T,15)*.4 + Noise*Decay(T,75)*.15;
                    break;
                case ECue::Impact:
                    V = std::sin(Tau*(36*T+4.3*(1-Decay(T,13))))*Decay(T,5)*.7
                      + Tone(118,T)*Decay(T,24)*.18 + N.Low*Decay(T,3) + (N.Mid-N.Low)*Decay(T,7)*.4;
                    break;
                case ECue::Breath:
                    N.Phase += Tau*(45+12*std::sin(T*2.4)+2*Tone(11,T))/SampleRate;
                    V = (std::sin(N.Phase)*.4 + std::sin(N.Phase*2)*.15 + (N.Mid-N.Low)*1.2)
                      * FMath::Min(1.0,T/.22) * FMath::Min(1.0,(Lengths[C]-T)/.4);
                    break;
                case ECue::Fire:
                    V = (N.Low*.9+(N.Mid-N.Low)*.8) * (.8+.2*Tone(17,T))
                      * FMath::Min(1.0,T/.12) * FMath::Min(1.0,(Lengths[C]-T)/.4);
                    break;
                case ECue::Heal:
                case ECue::Exposed:
                case ECue::Victory:
                {
                    const double Frequencies[4] = {329.628, 440, 493.883, 659.255};
                    const double Offset = Cue == ECue::Victory ? .24 : .085;
                    const double Pitch = Cue == ECue::Exposed ? 1.5 : 1.0;
                    for (int32 Note = 0; Note < 4; ++Note)
                    {
                        const double NT = T - Note*Offset;
                        if (NT >= 0) V += (Tone(Frequencies[Note]*Pitch,NT)+.12*Tone(Frequencies[Note]*Pitch*2.003,NT))
                            * (1-Decay(NT,70))*Decay(NT,Cue==ECue::Victory?2.5:5.0)*.2;
                    }
                    break;
                }
                case ECue::Death:
                    V = (std::sin(Tau*(55*T+6*(1-Decay(T,2))))*.5 + N.Low*.5) * Decay(T,2.5);
                    break;
                default: break;
            }
            V *= FMath::Min(1.0,T/.003) * FMath::Min(1.0,(Lengths[C]-T)/.05);
            Raw[I] = V; Peak = FMath::Max(Peak, std::abs(V));
        }
        Samples[C].SetNumUninitialized(Count);
        for (int32 I = 0; I < Count; ++I)
            Samples[C][I] = static_cast<int16>(FMath::Clamp(Raw[I]/Peak*.65,-.65,.65)*32767.0);
    }
}
