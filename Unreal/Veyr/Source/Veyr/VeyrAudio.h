#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrCombatTypes.h"
#include "VeyrGroundContacts.h"
#include "Math/RandomStream.h"
#include "Sound/SoundWaveProcedural.h"
#include "VeyrAudio.generated.h"

class AVeyrKnight;
class AVeyrDragon;
class UAudioComponent;
class USoundWaveProcedural;
class FJsonObject;
class USoundEffectSubmixPreset;

/** A procedural wave that notes the wall time of the audio render's first pull (timing evidence only; plays exactly like its parent). */
UCLASS()
class VEYR_API UVeyrProbeWave : public USoundWaveProcedural
{
    GENERATED_BODY()
public:
    UVeyrProbeWave(const FObjectInitializer& ObjectInitializer):Super(ObjectInitializer){}
    volatile double FirstPullWall=-1.0;
    virtual int32 GeneratePCMData(uint8* PCMData,const int32 SamplesNeeded) override
    {
        const int32 N=Super::GeneratePCMData(PCMData,SamplesNeeded);
        if(N>0&&FirstPullWall<0.0)FirstPullWall=FPlatformTime::Seconds();
        return N;
    }
};

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
    float EffectsVolume=1.f, MusicVolume=.55f;
    void RefreshMix();
    void PlayDestruction(const FVector& Position);
    /** Submission evidence only: these do not prove audible output or acoustic acceptance. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 CuesStarted = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 CuesDropped = 0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Audio|Evidence") int32 ActiveVoices = 0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") int32 RecordedCuesLoaded=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") bool bMusicLoaded=false;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") bool bAmbienceLoaded=false;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") bool bOwnerScoreLoaded=false;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") int32 MusicStarts=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") float MusicStartWorldSeconds=-1.f;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") int32 PlayerPainCues=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Audio|Evidence") int32 DragonVocalCues=0;
    /** Quality goal B1-B3 (2026-11-18): the new recorded set, variants, dragon presence, timed sounds. Evidence for evidence.json "audio". */
    TSharedRef<FJsonObject> AudioEvidence() const;      // dynamic counters, one per replay sample
    TSharedRef<FJsonObject> AudioSetupEvidence() const; // static: switches, variants loaded, tables; once at the evidence root
    bool UsesNewSet() const { return bNewSet; }

protected:
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    enum class ECue : uint8 { Swing, HeavySwing, Contact, Guard, Impact, Breath, Fire, Heal, Exposed, Death, Victory, Roll, Blink, Footstep, Wing, Roar, Break, PlayerPain, DragonGrowl, DragonPain,
        ArmorHit, DragonStep, DragonSwing, Bite, Debris, DragonBreathIn, DragonBreathOut, DragonGrowlLow, DragonSnort, Count };
    /** General pool (legacy path uses only this one), then a separate pool so footsteps never starve important cues. */
    static constexpr int32 VoiceCount = 12;
    static constexpr int32 StepVoiceCount = 8;
    static constexpr int32 TotalVoices = VoiceCount + StepVoiceCount;
    static constexpr int32 MaxVariants = 16;
    static constexpr int32 CueCount = static_cast<int32>(ECue::Count);
    static constexpr int32 SampleRate = 24000;

    UPROPERTY(Transient) TWeakObjectPtr<AVeyrKnight> Knight;
    UPROPERTY(Transient) TWeakObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY(Transient) TArray<TObjectPtr<UAudioComponent>> Voices;
    UPROPERTY(Transient) TArray<TObjectPtr<USoundWaveProcedural>> VoiceWaves;
    TArray<int16> Samples[CueCount];
    UPROPERTY(Transient) TArray<TObjectPtr<UAudioComponent>> Beds;
    UPROPERTY(Transient) TArray<TObjectPtr<USoundWaveProcedural>> BedWaves;
    TArray<uint8> BedPCM[2];
    int32 BedOffsets[2]={};
    int32 BedSampleRates[2]={24000,24000},BedChannels[2]={1,1};
    float VoiceLevels[TotalVoices]={};
    bool VoiceFollowsDragon[TotalVoices]={};
    int32 LastRolls=0,LastBlinks=0;
    float FootstepClock=0.f,WingClock=0.f,RoarClock=8.f;
    bool bAudioPolish=false,bFootNearFloor[2]={false,false},bRoarCuePlayed=false,bDrinkCuePlayed=false;
    bool bDragonLibraryLoaded=false;
    FVector LastPlayerPosition=FVector::ZeroVector;
    float PreviousWingHeight=0.f,PreviousWingVelocity=0.f,MusicDuckGain=1.f,MusicEnvelope=0.f;
    double MusicDuckUntil=-1.;
    FVector DestructionLocation=FVector::ZeroVector;
    void UpdateBeds();
    void LoadRecordedSamples();
    float Durations[CueCount] = {};
    double LastCueTimes[CueCount] = {};
    double VoiceEndTimes[TotalVoices] = {};
    double VoiceStartTimes[TotalVoices] = {};
    float VoicePeakAmp[TotalVoices] = {}; // recorded-master peak amplitude of the voice (Level x master x effects x engine factor x sample peak)
    int32 LastLight = 0, LastHeavy = 0, LastSwordContact = 0, LastHeadBonus = 0;
    int32 LastHitsTaken = 0, LastGuardedHits = 0, LastHeals = 0, LastCollapses = 0, LastFireAttacks = 0;
    EVeyrKnightAction LastSwingAction=EVeyrKnightAction::Ready;
    FName LastSwingClip=NAME_None;
    float LastSwingElapsed=0.f; // trimmed source clock, continuous across buffered combo segments
    TSet<int32> SwingWindowsPlayed;
    EVeyrDragonState LastDragonState = EVeyrDragonState::Idle;
    bool bWasAirborne = false, bInitialized = false, bTerminal = false, bBossDeathSeen = false;

    void BuildSamples();
    void PlayCue(ECue Cue, float Volume = 1.f);

    // ---- B1-B3 new behaviour (VeyrAudioNew.cpp). The legacy path above is untouched. ----
    enum class EPlace : uint8 { Flat, Head, Body, Part, World };
    /** Mix pass 5 (2026-11-19): every layer belongs to one event kind; one static gain per kind, one master trim at the end. -VeyrMixPass4 restores pass 4 (solo ceiling + peak budget). */
    enum class EMixKind : uint8 { Other, Landing, Slam, ClawTail, BodyFall, HeadHit, HeavyHit, FireIgnition, LightHit, Hurt, WalkStep, KnightStep, Wing, FireSustain, Presence, Count };
    static constexpr int32 MixKindCount=static_cast<int32>(EMixKind::Count);
    static const TCHAR* KindName(int32 Kind);
    bool bMixTable=true;
    EMixKind CurKind=EMixKind::Other;
    float KindGainDb[MixKindCount]={};
    float LayerGainDb[MixKindCount][CueCount]={}; // per layer where needed: kind x cue (dB), e.g. the light hit's low layers, the knight's swings under Other
    float LayerGain(EMixKind K,ECue Cue) const { return bMixTable?FMath::Pow(10.f,LayerGainDb[static_cast<int32>(K)][static_cast<int32>(Cue)]/20.f):1.f; }
    float MasterTrimDb=0.f,MusicTrimDb=0.f;
    float LimiterDb=-3.0f;
    double LastLimiterOfferWall=-1.0;
    void LoadMixTable();
    float MixTrim() const { return bMixTable?FMath::Pow(10.f,MasterTrimDb/20.f):1.f; }
    float KindGain(EMixKind K) const { return bMixTable?FMath::Pow(10.f,KindGainDb[static_cast<int32>(K)]/20.f):1.f; }
    // Timing and sync evidence: -VeyrAudioTiming (probe waves on hit layers), -VeyrSyncTest (white frame + click, then a loud tone that proves the limiter).
    bool bProbeNext=false,bTiming=false,bSyncTest=false;
    int32 SyncIndex=0; double SyncStartWall=-1.0; bool bSyncFadeOn=false;
    UPROPERTY(Transient) TArray<TObjectPtr<UVeyrProbeWave>> ProbeWaves;
    UPROPERTY(Transient) TObjectPtr<USoundEffectSubmixPreset> MasterLimiterPreset;
    void TickSyncTest();
    float TapTiltFc=0.f,TapTiltK=-1.f; int32 TapProbe=-1;
    struct FCueBank
    {
        TArray<TArray<int16>> Variants;
        TArray<float> Peaks;      // per variant, linear full-scale peak
        TArray<float> LowShare,HighShare,AttackMs,OnsetMs; // per variant: energy share below 200 Hz and above 2 kHz, ms to half peak, ms to 10 % of peak (after the head trim)
        TArray<float> Gains;      // per variant, from the measured level against the cue's target level
        int32 Last=-1;
        bool bMissingLogged=false;
    };
    struct FTimedEvent { float Pos=0.f; bool bPhase=true; ECue Cue=ECue::Count; float Level=1.f; FName Where=NAME_None; uint8 Role=0; float PitchMul=1.f; };
    struct FPending { double At=0.0; ECue Cue=ECue::Count; float Volume=1.f; EPlace Place=EPlace::Flat; FVector World=FVector::ZeroVector; FName Part=NAME_None; float Inner=0.f,Falloff=0.f; uint8 Role=0; float PitchMul=1.f; uint8 Tilt=0; EMixKind Kind=EMixKind::Other; };
    struct FExpect { bool bActive=false; double Deadline=0.0; ECue Cue=ECue::Count; float Volume=1.f; ECue Second=ECue::Count; float SecondVolume=1.f; };

    bool bNewSet=false,bLoadedOnce=false,bLegacyCues=false;
    bool bNoVariants=false,bNoBreath=false,bNoMoveSounds=false,bContactAudio=true,bLogCues=false;
    FCueBank Banks[CueCount];
    FRandomStream Rand{0x6C1A5B07};
    int32 CueCounts[CueCount]={},CueSilent[CueCount]={},VariantPlays[CueCount][MaxVariants]={};
    int32 VoiceCue[TotalVoices]={};
    uint8 VoiceFollowMode[TotalVoices]={};
    FName VoicePart[TotalVoices]={};
    TArray<FPending> Pending;
    FExpect Expect[4]; // 0 collapse/exposed/death body fall, 1 landing, 2 stomp, 3 spare
    int32 LastContactSerial=0;
    int32 ContactsHandled[4]={0,0,0,0},ContactFallbacks=0,TimedEventsFired=0,TimedEventsSkipped=0,SoundsReloads=0;
    int32 BreathIns=0,BreathOuts=0,Growls=0,KnightSteps=0,DragonSteps=0,BodyFallSounds=0,DebrisSounds=0,ArmorLayers=0;
    TMap<FName,TArray<FTimedEvent>> TimedClips;
    FString SoundsFile,SoundsDiagnostic;
    FDateTime SoundsStamp=FDateTime::MinValue();
    double SoundsCheckWall=0.0;
    FName TimedClipKey=NAME_None; float TimedLastPhase=-1.f,TimedLastTime=-1.f; bool bSwingFromData=false;
    float BreathClock=3.f,GrowlClock=9.f; bool bBreathExhaleNext=false,bPresenceCalm=true;
    float FootClock[2]={0.f,0.f};
    float MaxLoad=6.f,MakeupDb=-1.5f; // extra dB on every effect; -VeyrAudioMakeupDb=<dB>
    /** Measured on two captures (flat and spatial alike): the recorded master is about 9 dB under Level x master x effects. Gains and ceilings are set against the recorded level. */
    static constexpr float EngineFactor=.355f; // MakeupDb: -VeyrAudioMakeupDb=<dB> on all effects (calibration against a real capture)
    float DurationLastPlayed=0.f;

    void LoadNewSet();
    void LoadBank(ECue Cue,const FString& Dir);
    struct FChosen { int32 V=0; float Pitch=1.f,Level=0.f,Seconds0=0.f,Seconds=0.f; };
    bool PickVariant(ECue Cue,float Volume,FChosen& C,int32 Force=-1,uint8 Role=0,float PitchMul=1.f);
    void AddVariant(ECue Cue,TArray<int16>&& S);
    static void DefaultRadius(ECue Cue,float& Inner,float& Falloff);
    // ---- verification without a window (VeyrAudioTap.cpp): a software mix of exactly what the code submits ----
    struct FTapItem
    {
        double T=0.0; int32 Cue=0,Variant=0; float Volume=0.f,Level=0.f,Pitch=1.f,Dist=0.f,Gain=1.f,Seconds=0.f;
        uint8 Place=0; bool bRandom=false; FString Label; float Pan=0.f; double Wall=0.0; float GameT=0.f;
        float PeakDb=-120.f,RmsDb=-120.f,MusicRmsDb=-120.f;
        uint8 Kind=0; float KindGain=1.f,Trim=1.f,TiltFc=0.f,TiltK=-1.f; int32 Probe=-1; uint64 Frame=0;
    };
    bool bTap=false,bAudition=false,bAuditionDone=false;
    int32 TapSession=0;
    bool bFireBeamWas=false; double FireStartedAt=-100.0;
    // Stomp policy (one switch, the default is one constant): -VeyrStompHierarchy = walking steps get a light thump scaled by strength and only
    // attacks (stomp class, slams, claws, tail, landing, falls) get the heavy layers; -VeyrStompPass3 = the pass 3 behaviour (strong foot strikes, strength >= 0.65, play the heavy layers too).
    static constexpr bool kStompHierarchyDefault=true; // pass 4: the hierarchy (the critic's blind comparison of passes 2 and 3 chose it)
    bool bStompHierarchy=kStompHierarchyDefault;
    double BackgroundDuckUntil=-100.0;   // brief duck of the small background cues (steps, breath, debris) after a head hit or a flame ignition
    float MusicDuckTarget=.5f;           // the music duck depth: .5 normally, deeper for a head hit
    uint8 TiltMode=0;                    // 0 random tilt, 1 dark, 2 bright (stomp layers alternate so neighbours differ in colour)
    bool bTiltBrightNext=false;
    int32 LastStompRecipe=-1,LastTransient=-1;
    FString TapLabel; // set around a timed-sound play: "<clip>@<phase or time>"
    FString TapDir;
    double TapT0=-1.0,TapMusicStart=-1.0,TapGainLast=-1.0;
    TArray<float> TapFx,TapBeds;                 // interleaved stereo, 48 kHz
    TArray<FTapItem> TapItems;
    struct FTapGain { double T; float Music,Ambience; };
    TArray<FTapGain> TapGains;
    static float TypicalVolume(int32 Cue);
    struct FTapContact { double T=0.0; float GameT=0.f,HandledGameT=0.f,Strength=0.f,SpeedMps=0.f; int32 Serial=0,Part=0,Class=0,Leg=-1,ItemFrom=0,ItemTo=0; };
    struct FTapFrame { double T=0.0; float GameT=0.f,Dt=0.f,KneeL=-1.f,KneeR=-1.f,Speed=0.f,D[4]={-1.f,-1.f,-1.f,-1.f}; };
    TArray<FTapContact> TapContacts;
    TArray<FTapFrame> TapTrace;
    FTapFrame TapNow;
    struct FTapEvent { FString Kind; double T=0.0; double Wall=0.0; float GameT=0.f; uint64 Frame=0; };
    TArray<FTapEvent> TapEvents;
    float TapOffsetDb=-9.f; // the same measured engine factor, so the tap shows what the player hears   // -VeyrAudioTapOffsetDb: what the real output differs from the model (measured on a capture)
    void TapEvent(const TCHAR* Kind);
    void PlayWeaponHit(int32 Weight,bool bHead);
    void PlayStompLayers(const FVector& At,float S,bool bLanding);
    void InstallMasterChain();
    bool bMasterChain=false;
    void TapInit();
    void TapTick();
    void TapAdd(ECue Cue,const TArray<int16>& PCM,int32 Variant,float Volume,float Level,float Pitch,EPlace Place,const FVector& Pos,float Inner,float Falloff,double T,bool bRandom=false);
    void TapAudition();
    void TapWrite(const FString& Stem);
public:
    /** Writes the software mix (wav) and the cue list (json) when -VeyrAudioTap=<dir> is set. */
    void FlushTap();
private:
    void LoadCueSources();
    double AudioNow() const; // real time in the new path (sound does not stretch with hit-stop), game time in the legacy path
    bool ContactAudioActive() const;
    enum class ESourceMode : uint8 { Mixed, Recorded, Generated };
    ESourceMode DefaultSource=ESourceMode::Mixed;
    TMap<FName,ESourceMode> CueSource;
    FString SourcesDiagnostic;
    bool bBodyDownHeard=false;
    int32 GeneratedFiles=0;
    double LastLandingHeard=-100.0;
    TArray<FVeyrGroundContact> ContactScratch;
    void SetBankFromSingle(ECue Cue,const TArray<uint8>& Bytes,bool bNormalize);
    static const TCHAR* CueName(int32 Index);
    static float TargetLevelDb(ECue Cue);
    static bool IsVocal(ECue Cue);
    void LoadTimedSounds(bool bForce);
    void ParseTimedSounds(const FString& Text,const TCHAR* Origin);
    void TickNew(float DeltaSeconds);
    /** Role: 0 any variant, 1 sharp (mid/high, onset under 12 ms), 2 body (mid), 3 low, 4 fast low (low, half peak within 20 ms). PitchMul scales the random pitch. */
    bool PlayCueEx(ECue Cue,float Volume,EPlace Place=EPlace::Flat,const FVector& World=FVector::ZeroVector,FName Part=NAME_None,float Inner=0.f,float Falloff=0.f,uint8 Role=0,float PitchMul=1.f);
    void QueueCue(float Delay,ECue Cue,float Volume,EPlace Place=EPlace::Flat,const FVector& World=FVector::ZeroVector,FName Part=NAME_None,float Inner=0.f,float Falloff=0.f,uint8 Role=0,float PitchMul=1.f,uint8 Tilt=0);
    void UpdatePending();
    void UpdateVoiceFollow();
    void StopCueVoices(ECue A,ECue B=ECue::Count);
    bool ResolvePart(FName Where,FVector& Out) const;
    void UpdateTimedSounds();
    void HandleContacts();
    void HandleContact(const FVeyrGroundContact& C);
    void ArmExpect(int32 Slot,float Seconds,ECue Cue,float Volume,ECue Second=ECue::Count,float SecondVolume=1.f);
    void SatisfyExpect(int32 Slot);
    void UpdateExpectations();
    void UpdatePresence(float DeltaSeconds);
    void UpdateKnightFeet(float DeltaSeconds,float Speed);
    void StopVoices();
    void ExpireVoices();
    void SnapshotCounters();
};
